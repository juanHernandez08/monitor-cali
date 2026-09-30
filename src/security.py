"""Controles de seguridad HTTP del dashboard, separados de api.py para poder probarlos solos.

Resumen (detalle y motivos en docs/auditoria/01-seguridad.md):
  * Autenticación: HTTP Basic (DASHBOARD_USER/DASHBOARD_PASSWORD) y, opcional, validación del
    token de Cloudflare Access (CF_ACCESS_TEAM_DOMAIN + CF_ACCESS_AUD). Con Access configurado,
    una petición que llegue directo al puerto del servidor (saltándose Cloudflare) no pasa.
  * CSRF: toda petición que cambia estado (POST) exige la cabecera X-Requested-With que solo
    manda el propio dashboard, y si el navegador envía Origin, debe coincidir con el host.
  * Límite de gasto: las rutas que cuestan dinero (Apify, LLM) corren de a una y con espera
    mínima entre llamadas, para que un doble clic o un script no multiplique la factura.
"""
from __future__ import annotations

import base64
import datetime as dt
import logging
import re
import secrets
import threading
import time
from urllib.parse import urlparse

log = logging.getLogger(__name__)

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "monitor"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_PATHS = {"/healthz"}  # solo {"ok": true}: lo usan deploy.sh y el HEALTHCHECK de Docker

# Solo los orígenes que el dashboard usa de verdad. Sin 'unsafe-inline' en script-src: aunque un
# texto scrapeado lograra colarse como HTML, un <img onerror=...> no se ejecuta. style-src sí
# necesita 'unsafe-inline' porque ApexCharts y la plantilla usan atributos style.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "img-src 'self' https: data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WEEK = re.compile(r"^\d{4}-S\d{2}$")


def valid_date(value: str) -> bool:
    """YYYY-MM-DD real (no solo el formato): evita inyectar texto en el nombre del PDF y
    consultas con fechas imposibles."""
    if not _DATE.match(value or ""):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def valid_week(value: str) -> bool:
    """YYYY-Sww real (mismo formato que strftime('%G-S%V')), para el clic en las gráficas
    semanales de 'Análisis en gráficas'."""
    if not _WEEK.match(value or ""):
        return False
    year, wk = value.split("-S")
    try:
        dt.date.fromisocalendar(int(year), int(wk), 1)
    except ValueError:
        return False
    return True


# ------------------------------------------------------------------ autenticación

def basic_auth_ok(header: str, user: str | None, password: str | None) -> bool:
    if not password or not header.startswith("Basic "):
        return False
    try:
        got_user, _, got_pwd = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except Exception:
        return False
    return secrets.compare_digest(got_user, user or "") and secrets.compare_digest(got_pwd, password)


class CloudflareAccessVerifier:
    """Valida el JWT que Cloudflare Access agrega en Cf-Access-Jwt-Assertion.

    Sin esto, Access solo protege el dominio: cualquiera que llegue a la IP del VPS por el puerto
    publicado se lo salta. Las llaves públicas se descargan de <equipo>.cloudflareaccess.com y se
    guardan en caché (PyJWKClient)."""

    def __init__(self, team_domain: str, audience: str):
        import jwt  # pyjwt[crypto]; solo se importa si Access está configurado
        self._jwt = jwt
        domain = team_domain.removeprefix("https://").rstrip("/")
        self.issuer = f"https://{domain}"
        self.audience = audience
        self._jwks = jwt.PyJWKClient(f"{self.issuer}/cdn-cgi/access/certs", cache_keys=True, lifespan=3600)

    def verify(self, token: str | None) -> dict | None:
        if not token:
            return None
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            return self._jwt.decode(token, key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer)
        except Exception as exc:  # token vencido, firma inválida, audiencia equivocada...
            log.warning("token de Cloudflare Access rechazado: %s", type(exc).__name__)
            return None


def auth_mode(password: str | None, cf_verifier) -> str:
    if cf_verifier and password:
        return "cloudflare+basic"
    if cf_verifier:
        return "cloudflare"
    if password:
        return "basic"
    return "abierto"


# ------------------------------------------------------------------ CSRF

def csrf_ok(method: str, headers, host: str | None) -> bool:
    if method.upper() in SAFE_METHODS:
        return True
    if headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
        return False
    origin = headers.get("origin")
    if origin and host and (urlparse(origin).netloc or "").lower() != host.lower():
        return False
    return True


# ------------------------------------------------------------------ límite de gasto

class Throttle:
    """Una sola ejecución a la vez + espera mínima entre ejecuciones (por nombre de acción)."""

    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}
        self._last: dict[str, float] = {}
        self._guard = threading.Lock()

    def _lock(self, name: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(name, threading.Lock())

    def try_start(self, name: str, min_interval: float) -> tuple[bool, str | None]:
        lock = self._lock(name)
        if not lock.acquire(blocking=False):
            return False, "ya hay una ejecución en curso"
        wait = self._last.get(name, 0) + min_interval - time.monotonic()
        if wait > 0:
            lock.release()
            return False, f"espera {int(wait) + 1} s antes de repetir"
        self._last[name] = time.monotonic()
        return True, None

    def finish(self, name: str) -> None:
        lock = self._lock(name)
        if lock.locked():
            lock.release()


THROTTLE = Throttle()
