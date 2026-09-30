"""Notificaciones push por ntfy.sh (gratis, sin cuenta ni tarjeta -- pedido del cliente
2026-09-30). Dos canales (src/config.py): NTFY_TOPIC_TEAM para el equipo de campaña (mención
negativa fuerte, actividad inusual en redes, resumen diario) y NTFY_TOPIC_TECH solo para Juan
(túnel de Ollama caído). Si un topic no está configurado, esa notificación simplemente no se
envía -- nunca rompe el resto del sistema.

Cada función de "revisar y avisar" guarda en NotifyState hasta dónde ya avisó, para no repetir el
mismo aviso en cada corrida del job (cada 2 minutos para menciones negativas).
"""
import logging
import time

import requests

from src import config
from src.models import NotifyState

log = logging.getLogger(__name__)


def _get_state(session, key: str) -> str | None:
    row = session.get(NotifyState, key)
    return row.value if row else None


def _set_state(session, key: str, value: str) -> None:
    row = session.get(NotifyState, key)
    if row is None:
        session.add(NotifyState(key=key, value=value))
    else:
        row.value = value
    session.commit()


def send(topic: str | None, title: str, message: str, priority: int = 3, tags: list[str] | None = None) -> bool:
    """Envía una notificación por la API JSON de ntfy (evita el problema de tildes/ñ en cabeceras
    HTTP, que sí tiene la API simple por headers). priority: 1 (min) a 5 (urgente). Nunca lanza
    excepción -- un fallo de red no debe tumbar el job que la dispara."""
    if not topic:
        return False
    try:
        r = requests.post(f"{config.NTFY_SERVER}/", json={
            "topic": topic, "title": title, "message": message,
            "priority": priority, **({"tags": tags} if tags else {}),
        }, timeout=10)
        r.raise_for_status()
        return True
    except Exception:
        log.exception("no se pudo enviar la notificación ntfy: %s", title)
        return False


def check_negative_mentions(session) -> int:
    """Menciones de Carlos con score <= -0.5 (mismo umbral que /api/alerts) desde la última
    revisada. Se guía por el id de mención, no por fecha: así no se pierde ni se repite nada
    aunque el job se reinicie o corra atrasado."""
    from src.queries import CARLOS
    from src.models import Candidate, Mention, SentimentScore

    last_id = int(_get_state(session, "last_negative_id") or 0)
    rows = (session.query(Mention).join(SentimentScore).join(Candidate)
            .filter(Candidate.name == CARLOS, SentimentScore.score <= -0.5, Mention.id > last_id)
            .order_by(Mention.id).limit(20).all())
    if not rows:
        return 0
    for m in rows:
        send(config.NTFY_TOPIC_TEAM, "⚠️ Mención negativa fuerte de Carlos Arias",
             f"{m.sentiment.score} · {(m.text or '')[:200]}",
             priority=4, tags=["warning"])
    _set_state(session, "last_negative_id", str(max(m.id for m in rows)))
    return len(rows)


def check_strong_posts(session) -> int:
    """Publicaciones (de cualquier candidato o concejal) con actividad muy por encima de lo
    habitual de esa cuenta -- ver queries.social_strong_posts. Se dedupe por id de mención."""
    from src.queries import social_strong_posts

    notified = {int(x) for x in (_get_state(session, "notified_strong_ids") or "").split(",") if x}
    strong = social_strong_posts(session, days=3)
    new = [p for p in strong if p["id"] not in notified]
    if not new:
        return 0
    for p in new:
        send(config.NTFY_TOPIC_TEAM, f"📈 Actividad fuerte en redes: {p['candidate']}",
             f"{p['multiplier']}× lo habitual · {(p.get('text') or '')[:180]}",
             priority=3, tags=["chart_with_upwards_trend"])
    notified |= {p["id"] for p in new}
    # se guardan como máximo los últimos 500 ids para que el estado no crezca sin límite
    _set_state(session, "notified_strong_ids", ",".join(str(x) for x in sorted(notified)[-500:]))
    return len(new)


def notify_daily_summary(report_data: dict) -> None:
    """Resumen corto del reporte diario recién generado (job_daily_report) -- lo mismo que dice
    el reporte completo, pero en 3 líneas para no tener que abrir el dashboard."""
    kpis = report_data.get("social_kpis") or {}
    narrative = report_data.get("narrative") or {}
    resumen = narrative.get("resumen_ejecutivo") or "Reporte generado -- ver el dashboard para el detalle."
    msg = f"{kpis.get('total_posts', 0)} publicaciones · {kpis.get('total_likes', 0)} likes · {kpis.get('total_comments', 0)} comentarios\n\n{resumen[:500]}"
    send(config.NTFY_TOPIC_TEAM, "📊 Resumen diario — Monitor Cali", msg, priority=3, tags=["bar_chart"])


def check_ollama_tunnel(session) -> None:
    """Avisa (solo a Juan, NTFY_TOPIC_TECH) si la clasificación por Ollama lleva caída un rato --
    y avisa también cuando vuelve, para no dejar la duda. Solo aplica si el backend activo es
    Ollama; con Claude no hay túnel que vigilar."""
    if config.SENTIMENT_BACKEND != "ollama":
        return
    up = False
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        up = r.ok
    except Exception:
        up = False

    was_down = _get_state(session, "ollama_down") == "1"
    if up and was_down:
        _set_state(session, "ollama_down", "0")
        send(config.NTFY_TOPIC_TECH, "✅ Túnel de Ollama recuperado",
             "La clasificación de sentimiento volvió a funcionar.", priority=3, tags=["white_check_mark"])
    elif not up and not was_down:
        # Un solo fallo puede ser una red lenta pasajera -- se confirma con un segundo chequeo
        # 20s después antes de avisar, para no despertar a nadie por un timeout suelto.
        time.sleep(20)
        try:
            r2 = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
            up2 = r2.ok
        except Exception:
            up2 = False
        if not up2:
            _set_state(session, "ollama_down", "1")
            send(config.NTFY_TOPIC_TECH, "🔴 Túnel de Ollama caído",
                 "La PC no está clasificando menciones. Revisa la tarea programada MonitorCaliOllamaTunnel.",
                 priority=4, tags=["red_circle"])
