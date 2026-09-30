"""Herramientas estadísticas pequeñas y sin dependencias (no hace falta scipy) para que las cifras
del dashboard digan cuánto se puede confiar en ellas.

Por qué existe (auditoría estadística 2026-09-29, docs/auditoria/04-estadistica-y-estrategia-redes.md):
  * Un "100% positivo" con 3 comentarios y uno con 300 se mostraban igual. Ahora cada proporción
    lleva su intervalo de confianza (Wilson) y el tamaño de muestra.
  * Una variación "+200%" pasando de 1 a 3 menciones parecía una tendencia. Ahora cada comparación
    entre períodos lleva una prueba de significancia (binomial condicional para conteos).
  * El alcance por publicación tiene cola pesada (un reel viral pesa por veinte posts normales):
    se reporta la mediana además del promedio, y los picos se detectan contra la mediana propia.
"""
from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Intervalo de confianza de Wilson (en %, 0-100) para k éxitos en n. None si n == 0.
    Mejor que la aproximación normal con n chico o proporciones cercanas a 0% o 100%."""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half) * 100, 1), round(min(1.0, centre + half) * 100, 1)


def _binom_pmf_log(k: int, n: int, p: float) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) + (n - k) * math.log(1 - p)


def binom_two_sided_p(k: int, n: int, p: float = 0.5) -> float:
    """p-valor exacto de dos colas (método de sumar las probabilidades <= la observada)."""
    if n == 0:
        return 1.0
    observed = _binom_pmf_log(k, n, p)
    total = 0.0
    for i in range(n + 1):
        lp = _binom_pmf_log(i, n, p)
        if lp <= observed + 1e-9:
            total += math.exp(lp)
    return min(1.0, total)


def count_change_test(current: int, previous: int) -> dict:
    """¿El cambio entre dos conteos de igual duración es real o ruido?

    Con conteos tipo Poisson, condicionado al total, el actual sigue una Binomial(total, 0.5) si
    la tasa no cambió. Devuelve p-valor y si es significativo al 5%. Con total < 10 no hay poder
    para afirmar nada: se marca "muestra chica" en vez de dar un porcentaje engañoso."""
    total = current + previous
    if total < 10:
        return {"p_value": None, "significant": False, "small_sample": True}
    p = binom_two_sided_p(current, total, 0.5)
    return {"p_value": round(p, 4), "significant": p < 0.05, "small_sample": False}


def median(values: Sequence[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def mad(values: Sequence[float]) -> float | None:
    """Desviación absoluta mediana: dispersión robusta a publicaciones virales."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    m = statistics.median(vals)
    return statistics.median(abs(v - m) for v in vals)


def robust_z(x: float, values: Sequence[float]) -> float | None:
    """Z robusto (Iglewicz y Hoaglin): 0,6745·(x − mediana)/MAD. > 3,5 suele leerse como atípico."""
    m, d = median(values), mad(values)
    if m is None or not d:
        return None
    return round(0.6745 * (x - m) / d, 2)


def bootstrap_median_ci(values: Sequence[float], reps: int = 1000, seed: int = 7) -> tuple[float, float] | None:
    """Intervalo de confianza del 95% para la mediana por bootstrap percentil (semilla fija: el
    dashboard muestra siempre lo mismo para los mismos datos)."""
    vals = [v for v in values if v is not None]
    if len(vals) < 5:
        return None
    rng = random.Random(seed)
    meds = sorted(statistics.median(rng.choices(vals, k=len(vals))) for _ in range(reps))
    return meds[int(0.025 * reps)], meds[int(0.975 * reps) - 1]


def quantiles(values: Sequence[float]) -> dict | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return {"q1": vals[0], "median": vals[0], "q3": vals[0]}
    q = statistics.quantiles(vals, n=4, method="inclusive")
    return {"q1": q[0], "median": q[1], "q3": q[2]}
