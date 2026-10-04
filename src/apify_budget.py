"""Presupuesto en DÓLARES de Apify -- freno duro para no pasarse del tope aprobado por el cliente.

Contexto (2026-10-04): se gastó el 73 % de los USD 19 del ciclo en 6 días porque el único freno
(`APIFY_MONTHLY_ITEMS`) cuenta ítems, no dólares, y no sabía cuántos días faltaban. El cliente pidió
cumplir el presupuesto "sí o sí": de eso depende que le renueven la aprobación del proyecto.

Reglas, todas fallan CERRADO (ante la duda no se gasta):
- El saldo se lee de Apify (`/v2/users/me/limits`), no de un contador propio.
- Techo efectivo = el MENOR entre el tope de la cuenta de Apify y `APIFY_CYCLE_BUDGET_USD`.
- Siempre se deja una reserva intocable (`APIFY_RESERVE_USD`).
- Lo disponible se reparte en partes iguales entre las vueltas que faltan hasta el fin del ciclo.
- El techo configurado vale solo para el ciclo que termina en `APIFY_CYCLE_BUDGET_END`; si Apify
  abre un ciclo nuevo, no se gasta hasta que alguien confirme un presupuesto nuevo.
- Durante la vuelta se vuelve a consultar el gasto real antes de cada llamada.
"""
import dataclasses
import datetime as dt
import logging

import requests

from src import config

log = logging.getLogger(__name__)

LIMITS_URL = "https://api.apify.com/v2/users/me/limits"

# Costos por llamada, en USD, deliberadamente por ENCIMA de lo medido el 2026-10-04 con corridas reales
# (Instagram posts 0,002-0,011 por cuenta; X 0,001-0,012 por corrida salvo el primer backfill de 0,12;
# comentarios de Instagram 0,0023 por comentario, 0,069 por 30).
COST_IG_ACCOUNT = 0.010
COST_FB_ACCOUNT = 0.010
COST_X_ACCOUNT = 0.030
COST_COMMENT_EACH = 0.0030
COST_COMMENT_RUN = 0.004
COST_CALL_OVERHEAD = 0.002  # por llamada, para la estimación corrida a corrida


@dataclasses.dataclass
class Status:
    used: float
    cap: float
    cycle_start: dt.date
    cycle_end: dt.date


@dataclasses.dataclass
class Plan:
    ok: bool
    reason: str
    used: float = 0.0
    ceiling: float = 0.0
    reserve: float = 0.0
    available: float = 0.0
    days_left: int = 0
    job_budget: float = 0.0
    cycle_end: str = ""

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(str(value)[:10])


def fetch_status(token: str | None, timeout: int = 20) -> Status | None:
    """Gasto del ciclo según Apify; None si no se pudo consultar (quien llama debe fallar cerrado)."""
    if not token:
        return None
    try:
        r = requests.get(LIMITS_URL, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
        r.raise_for_status()
        d = r.json()["data"]
        cyc = d["monthlyUsageCycle"]
        return Status(used=float(d["current"]["monthlyUsageUsd"]), cap=float(d["limits"]["maxMonthlyUsageUsd"]),
                      cycle_start=_date(cyc["startAt"]), cycle_end=_date(cyc["endAt"]))
    except Exception:
        log.exception("no se pudo consultar el saldo de Apify")
        return None


def compute_plan(status: Status | None, today: dt.date, ceiling: float | None = None, ceiling_end: str | None = None,
                 reserve: float | None = None, interval_hours: int | None = None) -> Plan:
    ceiling = config.APIFY_CYCLE_BUDGET_USD if ceiling is None else ceiling
    ceiling_end = config.APIFY_CYCLE_BUDGET_END if ceiling_end is None else ceiling_end
    reserve = config.APIFY_RESERVE_USD if reserve is None else reserve
    interval_hours = interval_hours or config.SOCIAL_INTERVAL_HOURS
    if status is None:
        return Plan(False, "no se pudo consultar el saldo de Apify; no se gasta nada hasta poder verificarlo")
    if status.cycle_end.isoformat() != ceiling_end:
        return Plan(False, f"Apify abrió un ciclo nuevo (termina {status.cycle_end}); el presupuesto aprobado era para el ciclo que "
                           f"termina {ceiling_end}. No se gasta hasta confirmar un presupuesto nuevo", cycle_end=status.cycle_end.isoformat())
    effective = min(status.cap, ceiling)
    available = round(effective - status.used - reserve, 4)
    days_left = max(1, (status.cycle_end - today).days + 1)
    jobs_left = max(1, round(days_left * 24 / interval_hours))
    plan = Plan(True, "ok", used=status.used, ceiling=effective, reserve=reserve, available=max(0.0, available),
                days_left=days_left, cycle_end=status.cycle_end.isoformat())
    if available < 0.05:
        plan.ok, plan.reason = False, "sin saldo disponible: queda solo la reserva del ciclo"
        return plan
    # parte justa de cada vuelta que falta; si una vuelta se salta, lo no gastado se reparte solo entre las siguientes
    plan.job_budget = round(available / jobs_left, 4)
    return plan


def current_plan(token: str | None) -> tuple[Plan, Status | None]:
    status = fetch_status(token)
    return compute_plan(status, dt.datetime.utcnow().date()), status


def _account_cost(a: dict) -> float:
    return {"instagram": COST_IG_ACCOUNT, "facebook": COST_FB_ACCOUNT, "x": COST_X_ACCOUNT}.get(a.get("platform"), COST_IG_ACCOUNT)


def comment_post_cost(max_comments: int) -> float:
    return COST_COMMENT_RUN + COST_COMMENT_EACH * max_comments


def select_accounts(accounts: list[dict], kinds: dict[str, str], last_dates: dict[str, str], budget: float,
                    carlos: str, pending_posts: list[dict], max_comments: int,
                    include_media: bool = False) -> tuple[list[dict], int, float]:
    """Elige qué cuentas visitar con `budget` dólares, por prioridad:
    1) las de Carlos Arias, 2) comentarios de UN post suyo, 3) rivales, 4) concejales, 5) medios (apagado por defecto: su prensa ya
    entra por Google News y RSS). Dentro de cada grupo, primero la que lleva más tiempo sin revisarse.
    Devuelve (cuentas, posts_con_comentarios, gasto estimado)."""
    def oldest_first(group):
        return sorted(group, key=lambda a: last_dates.get(a["url"], ""))

    carlos_accts = [a for a in accounts if a.get("candidate") == carlos]
    rivals = [a for a in accounts if a.get("candidate") and a["candidate"] != carlos and kinds.get(a["candidate"]) == "candidate"]
    councilors = [a for a in accounts if a.get("candidate") and a["candidate"] != carlos and kinds.get(a["candidate"]) != "candidate"]
    media = [a for a in accounts if not a.get("candidate")] if include_media else []

    chosen: list[dict] = []
    spent = 0.0
    comment_posts = 0

    def take(group):
        nonlocal spent
        for a in oldest_first(group):
            c = _account_cost(a)
            if spent + c <= budget:
                chosen.append(a)
                spent += c

    take(carlos_accts)
    if any(p.get("candidate") == carlos for p in pending_posts) or carlos_accts:
        c = comment_post_cost(max_comments)
        if spent + c <= budget:
            comment_posts, spent = 1, spent + c
    take(rivals)
    take(councilors)
    take(media)
    return chosen, comment_posts, round(spent, 4)


class JobSpend:
    """Se pasa a los conectores como `credits`: `remaining()` > 0 mientras no se haya gastado el presupuesto
    de la vuelta. Mide el gasto REAL contra Apify antes de cada llamada y, si no puede, usa una estimación
    conservadora -- el menor de los dos manda."""

    def __init__(self, token: str, budget: float, start_used: float, status_fn=fetch_status):
        self.token, self.budget, self.start_used, self.status_fn = token, budget, start_used, status_fn
        self.est = 0.0
        self.real = 0.0

    def consume(self, n: int = 1) -> None:
        self.est += COST_CALL_OVERHEAD + COST_COMMENT_EACH * max(0, n)

    def remaining_usd(self) -> float:
        st = self.status_fn(self.token)
        if st is not None:
            self.real = max(0.0, st.used - self.start_used)
        return min(self.budget - self.est, self.budget - self.real)

    def remaining(self) -> int:
        return max(0, int(self.remaining_usd() * 1000))
