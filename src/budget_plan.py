"""Presupuesto GLOBAL del mes: todo lo que cuesta el monitor tiene que sumar menos que `MONTHLY_BUDGET_COP`.

El cliente aprobó (2026-10-23) hasta 300.000 COP al mes "sin pasarse por nada del mundo". Hay tres gastos:
  1. Servidor (Hostinger): fijo, en pesos (`FIXED_MONTHLY_COP`: plan 57.900 + respaldo 9.900).
  2. Apify (redes sociales): en dólares, con tope por ciclo (`APIFY_CYCLE_BUDGET_USD`, src/apify_budget.py).
  3. Claude (clasificación y análisis): en dólares, con tope por mes (`CLAUDE_MONTHLY_BUDGET_USD`, src/claude_budget.py).
Los dos últimos se convierten a pesos con un dólar CONSERVADOR (`BUDGET_FX_COP_PER_USD`, bastante por encima del real: el
gasto de septiembre-octubre salió a ~3.220 COP por dólar con todo incluido), así que el peor caso calculado aquí queda por
encima de lo que de verdad se pagaría.

Este módulo no gasta nada: suma los topes y recorta el de Claude si, junto con el de Apify, no cupieran en el presupuesto.
Los topes de cada servicio son los que frenan de verdad; esto garantiza que, sumados, nunca superen el total."""
import dataclasses
import logging
import math

from src import config

log = logging.getLogger(__name__)


def variable_usd() -> float:
    """Dólares disponibles para Apify + Claude una vez descontado lo fijo, al dólar conservador."""
    return max(0.0, (config.MONTHLY_BUDGET_COP - config.FIXED_MONTHLY_COP) / config.BUDGET_FX_COP_PER_USD)


def claude_limit_usd() -> float:
    """Tope duro de Claude: el configurado, pero nunca más de lo que sobra tras el tope de Apify."""
    limit = max(0.0, min(config.CLAUDE_MONTHLY_BUDGET_USD, variable_usd() - config.APIFY_CYCLE_BUDGET_USD))
    return math.floor(limit * 100) / 100  # siempre hacia abajo: redondear hacia arriba podría pasarse por centavos


@dataclasses.dataclass
class Plan:
    limit_cop: int
    fixed_cop: int
    apify_usd: float
    claude_usd: float
    fx: float
    worst_case_cop: int
    margin_cop: int
    ok: bool

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def worst_case() -> Plan:
    """Peor caso del mes si cada servicio gasta TODO su tope, al dólar conservador."""
    apify, claude = config.APIFY_CYCLE_BUDGET_USD, claude_limit_usd()
    total = round(config.FIXED_MONTHLY_COP + (apify + claude) * config.BUDGET_FX_COP_PER_USD)
    margin = config.MONTHLY_BUDGET_COP - total
    return Plan(limit_cop=config.MONTHLY_BUDGET_COP, fixed_cop=config.FIXED_MONTHLY_COP, apify_usd=apify, claude_usd=claude,
                fx=config.BUDGET_FX_COP_PER_USD, worst_case_cop=total, margin_cop=margin, ok=margin >= 0)


def check_and_alert() -> Plan:
    """Al arrancar: si el tope de Apify solo ya no cabe en el presupuesto, avisa a soporte (Claude queda recortado a 0)."""
    plan = worst_case()
    log.info("presupuesto del mes: peor caso %s COP de %s (margen %s); Apify %.2f USD + Claude %.2f USD + fijo %s COP",
             plan.worst_case_cop, plan.limit_cop, plan.margin_cop, plan.apify_usd, plan.claude_usd, plan.fixed_cop)
    if not plan.ok or plan.claude_usd < config.CLAUDE_MONTHLY_BUDGET_USD:
        from src import notify
        notify.send(config.NTFY_TOPIC_TECH, "⚠️ Presupuesto mensual ajustado",
                    f"Peor caso {plan.worst_case_cop:,} COP de {plan.limit_cop:,}. Claude quedó limitado a {plan.claude_usd:.2f} USD "
                    f"(configurado {config.CLAUDE_MONTHLY_BUDGET_USD:.2f}) porque Apify permite hasta {plan.apify_usd:.2f} USD.",
                    priority=4, tags=["moneybag"])
    return plan
