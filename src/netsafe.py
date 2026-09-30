"""Descargas a URLs que vienen de terceros (RSS, Google News, scrapers) sin abrir la red interna.

El enriquecimiento de prensa descarga la URL que trae cada nota. Esa URL la controla quien
publica el feed: podría apuntar a http://169.254.169.254 (metadatos del VPS), a
http://localhost:11434 (Ollama) o a cualquier servicio interno, o redirigir hacia ellos. Aquí se
valida cada salto: solo http/https, solo direcciones públicas, tope de tamaño y de tiempo.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)

MAX_BYTES = 3_000_000
TIMEOUT = 15
MAX_REDIRECTS = 5
USER_AGENT = "Mozilla/5.0 (compatible; MonitorCali/1.0; +https://monitordescucha.tech)"


def _public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return addr.is_global and not addr.is_multicast


def is_public_http_url(url: str) -> bool:
    """True si la URL es http(s) y TODAS las direcciones a las que resuelve son públicas."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return False
    return bool(infos) and all(_public_ip(info[4][0]) for info in infos)


def safe_get_text(url: str, session=None) -> str | None:
    """HTML de una URL pública, siguiendo redirecciones solo hacia URLs públicas. None si falla
    o si en algún salto la URL deja de ser pública."""
    import requests

    http = session or requests
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_public_http_url(current):
            log.warning("descarga bloqueada (URL no pública): %s", current[:200])
            return None
        try:
            resp = http.get(current, timeout=TIMEOUT, allow_redirects=False, stream=True,
                            headers={"User-Agent": USER_AGENT})
        except Exception as exc:
            log.info("descarga fallida %s: %s", current[:200], type(exc).__name__)
            return None
        if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("location")
            resp.close()
            if not location:
                return None
            current = urljoin(current, location)
            continue
        if resp.status_code != 200:
            resp.close()
            return None
        chunks, size = [], 0
        for chunk in resp.iter_content(64_000):
            size += len(chunk)
            if size > MAX_BYTES:
                resp.close()
                log.info("descarga truncada por tamaño: %s", current[:200])
                break
            chunks.append(chunk)
        resp.close()
        return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
    return None
