"""Freno de gasto de la API de Claude (clasificación y análisis narrativo).

El código no tenía ningún freno para Claude (solo para Apify, src/apify_budget.py). Aquí se mide el gasto REAL de
cada llamada (tokens de `response.usage` x precio del modelo) y se acumula por mes calendario en `api_usage`
(servicio "claude_usd_micro", en millonésimas de dólar). Al llegar al tope mensual (`CLAUDE_MONTHLY_BUDGET_USD`) la
clasificación pasa sola al modelo barato de respaldo en vez de detenerse (sin el PC del cliente nadie la
reanudaría), y se avisa a soporte técnico. Un tope duro (1,5 x) corta todo por si el respaldo también se disparara.
También avisa, una vez por día, si Anthropic rechaza por saldo agotado o clave inválida."""
import datetime as dt
import logging

from sqlalchemy import func

from src import config
from src.db import get_session
from src.models import ApiUsage, NotifyState

log = logging.getLogger("claude_budget")

SERVICE = "claude_usd_micro"
HARD_STOP_FACTOR = 1.5
WARN_AT = 0.8

# USD por millón de tokens (entrada, salida). Lectura de caché = 0,1 x entrada; escritura de caché (5 min) = 1,25 x entrada.
PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0), "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-5-5": (0.10, 0.50), "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5-5": (4.0, 20.0), "claude-opus-5": (5.0, 25.0),
}
DEFAULT_PRICE = (3.0, 15.0)  # un modelo desconocido se cuenta caro: preferible sobrestimar el gasto


class BudgetExceeded(RuntimeError):
    """Se pasó el tope duro de gasto del mes: no se llama más a Claude hasta el mes siguiente."""


def cost_usd(model: str, usage) -> float:
    """Costo en dólares de una respuesta, según sus tokens. Sin `usage` (p. ej. un doble de prueba) cuesta 0."""
    if usage is None:
        return 0.0
    price_in, price_out = PRICES.get(model, DEFAULT_PRICE)
    n = lambda name: getattr(usage, name, 0) or 0
    tokens_in = n("input_tokens") + 1.25 * n("cache_creation_input_tokens") + 0.1 * n("cache_read_input_tokens")
    return (tokens_in * price_in + n("output_tokens") * price_out) / 1_000_000


def _month(today: dt.date | None = None) -> str:
    return (today or dt.datetime.utcnow().date()).strftime("%Y-%m")


class ClaudeBudget:
    def __init__(self, monthly_usd: float | None = None, fallback_model: str | None = None):
        self.monthly_usd = config.CLAUDE_MONTHLY_BUDGET_USD if monthly_usd is None else monthly_usd
        self.fallback_model = fallback_model or config.CLAUDE_FALLBACK_MODEL

    # ---- medición ----
    def spent(self, month: str | None = None) -> float:
        month = month or _month()
        with get_session() as s:
            micro = (s.query(func.coalesce(func.sum(ApiUsage.count), 0))
                     .filter(ApiUsage.service == SERVICE, ApiUsage.day.like(f"{month}-%")).scalar())
        return (micro or 0) / 1_000_000

    def add(self, model: str, usage) -> float:
        usd = cost_usd(model, usage)
        micro = round(usd * 1_000_000)
        if micro <= 0:
            return usd
        day = dt.datetime.utcnow().strftime("%Y-%m-%d")
        with get_session() as s:
            row = s.query(ApiUsage).filter_by(service=SERVICE, day=day).first()
            if row is None:
                s.add(ApiUsage(service=SERVICE, day=day, count=micro))
            else:
                row.count += micro
            s.commit()
        return usd

    # ---- decisión ----
    def model_for(self, preferred: str) -> str:
        """El modelo a usar ahora: el preferido mientras haya presupuesto; el barato al llegar al tope del mes."""
        spent = self.spent()
        if spent >= self.monthly_usd * HARD_STOP_FACTOR:
            self._alert("claude_hard_stop", "🛑 Claude: tope duro de gasto alcanzado",
                        f"Se gastaron USD {spent:.2f} este mes (tope {self.monthly_usd:.2f}). La clasificación se detuvo hasta el mes siguiente.",
                        monthly=True, priority=5)
            raise BudgetExceeded(f"gasto del mes USD {spent:.2f} >= tope duro")
        if spent >= self.monthly_usd:
            self._alert("claude_cap", "⚠️ Claude: tope mensual alcanzado",
                        f"Se gastaron USD {spent:.2f} de {self.monthly_usd:.2f}. Hasta fin de mes se clasifica con {self.fallback_model} "
                        "(más barato, menos preciso). Para seguir con el modelo bueno, subir CLAUDE_MONTHLY_BUDGET_USD en el .env del servidor.",
                        monthly=True, priority=4)
            return self.fallback_model
        if spent >= self.monthly_usd * WARN_AT:
            self._alert("claude_warn", "💵 Claude: 80 % del tope mensual",
                        f"Van USD {spent:.2f} de {self.monthly_usd:.2f} este mes.", monthly=True, priority=3)
        return preferred

    def status(self) -> dict:
        spent = self.spent()
        return {"month": _month(), "spent_usd": round(spent, 3), "cap_usd": self.monthly_usd,
                "degraded": spent >= self.monthly_usd, "model": config.CLAUDE_CLASSIFY_MODEL,
                "fallback_model": self.fallback_model}

    # ---- avisos ----
    def report_api_error(self, exc: Exception) -> None:
        """Avisa (una vez al día) si Anthropic rechaza por saldo agotado o clave inválida: sin el PC del cliente
        como respaldo, la clasificación se queda parada hasta que alguien lo arregle."""
        status = getattr(exc, "status_code", None)
        text = str(exc).lower()
        if status in (401, 403):
            self._alert("claude_auth", "🔴 Claude: clave rechazada",
                        "Anthropic rechazó la clave (401/403). La clasificación está detenida; revisar ANTHROPIC_API_KEY.", monthly=False, priority=5)
        elif status in (400, 402) and ("credit" in text or "balance" in text or "billing" in text):
            self._alert("claude_credit", "🔴 Claude: saldo agotado",
                        "Anthropic dice que no hay saldo. La clasificación está detenida: recargar créditos en console.anthropic.com.",
                        monthly=False, priority=5)

    def _alert(self, key: str, title: str, message: str, monthly: bool, priority: int) -> None:
        from src import notify
        stamp = _month() if monthly else dt.datetime.utcnow().strftime("%Y-%m-%d")
        full = f"{key}:{stamp}"
        with get_session() as s:
            if s.get(NotifyState, full) is not None:
                return
            s.add(NotifyState(key=full, value="1"))
            s.commit()
        log.warning("%s: %s", title, message)
        notify.send(config.NTFY_TOPIC_TECH, title, message, priority=priority, tags=["moneybag"])
