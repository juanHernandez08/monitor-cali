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
from sqlalchemy import func

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


def send(topic: str | None, title: str, message: str, priority: int = 3, tags: list[str] | None = None,
         click: str | None = None, view_label: str | None = None, view_url: str | None = None) -> bool:
    """Envía una notificación por la API JSON de ntfy (evita el problema de tildes/ñ en cabeceras
    HTTP, que sí tiene la API simple por headers). priority: 1 (min) a 5 (urgente). `click` es a
    dónde lleva tocar la notificación misma (normalmente, el monitor); `view_label`/`view_url`
    agregan un botón aparte (p. ej. "Ver original", al post/nota real). Nunca lanza excepción --
    un fallo de red no debe tumbar el job que la dispara."""
    if not topic:
        return False
    payload = {"topic": topic, "title": title, "message": message, "priority": priority}
    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click
    if view_label and view_url:
        payload["actions"] = [{"action": "view", "label": view_label, "url": view_url}]
    try:
        r = requests.post(f"{config.NTFY_SERVER}/", json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception:
        log.exception("no se pudo enviar la notificación ntfy: %s", title)
        return False


def check_negative_mentions(session) -> int:
    """Menciones de Carlos con score <= -0.5 (mismo umbral que /api/alerts) desde la última
    revisada. Se guía por el id de mención, no por fecha: así no se pierde ni se repite nada
    aunque el job se reinicie o corra atrasado.

    Descarta 'mención tangencial'/'homónimo' (META_TOPICS) -- son casos donde el propio
    clasificador ya marcó que el texto no es realmente sobre Carlos. Si la mención es un
    comentario en una publicación PROPIA de Carlos, el mensaje lo aclara: un comentario
    combativo ahí puede ser negativo sin ser un ataque externo a su imagen."""
    from src.queries import CARLOS, META_TOPICS
    from src.models import Candidate, Mention, SentimentScore

    state_key = "last_negative_id"
    raw_state = _get_state(session, state_key)
    if raw_state is None:
        # primera vez que corre esto: no notificar todo el historial de golpe, solo lo que
        # pase desde ahora -- confirmado 2026-09-30, sin esto mandó de una vez 23 avisos viejos.
        max_id = session.query(Mention.id).order_by(Mention.id.desc()).limit(1).scalar() or 0
        _set_state(session, state_key, str(max_id))
        return 0
    last_id = int(raw_state)

    candidate = session.query(Candidate).filter_by(name=CARLOS).first()
    if not candidate:
        return 0
    own_accounts = {a["url"] for a in config.SOCIAL_ACCOUNTS if a.get("candidate") == CARLOS}

    rows = (session.query(Mention).join(SentimentScore).join(Candidate)
            .filter(Candidate.name == CARLOS, SentimentScore.score <= -0.5, Mention.id > last_id,
                    func.lower(SentimentScore.topic).notin_(META_TOPICS))
            .order_by(Mention.id).limit(20).all())
    if not rows:
        return 0
    for m in rows:
        own_post = (m.raw or {}).get("account") in own_accounts
        prefix = "Comentario en publicación PROPIA de Carlos" if own_post else "Mención sobre Carlos"
        send(config.NTFY_TOPIC_TEAM, "⚠️ Mención negativa fuerte de Carlos Arias",
             f"{prefix} · {m.sentiment.score}\n{(m.text or '')[:220]}",
             priority=4, tags=["warning"],
             click=f"{config.DASHBOARD_URL}/?perfil={candidate.id}",
             view_label="Ver original" if m.url else None, view_url=m.url)
    _set_state(session, state_key, str(max(m.id for m in rows)))
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
             priority=3, tags=["chart_with_upwards_trend"],
             click=f"{config.DASHBOARD_URL}/?perfil={p['candidate_id']}",
             view_label="Ver publicación" if p.get("url") else None, view_url=p.get("url"))
    notified |= {p["id"] for p in new}
    # se guardan como máximo los últimos 500 ids para que el estado no crezca sin límite
    _set_state(session, "notified_strong_ids", ",".join(str(x) for x in sorted(notified)[-500:]))
    return len(new)


def check_city_trends(session) -> int:
    """Temas nuevos o en fuerte alza en la conversación general de Cali (no solo sobre
    candidatos) -- reutiliza queries.city_opportunities, lo mismo que arma el reporte diario.
    Se dedupe por categoría+tema, no por id: un mismo tema puede seguir sumando menciones
    varios días y no tiene sentido avisar de nuevo cada vez."""
    from src.queries import city_opportunities

    data = city_opportunities(session, days=7)
    novedades = data.get("novedades") or []
    notified = set((_get_state(session, "notified_city_topics") or "").split("␟")) - {""}
    new = [n for n in novedades if f"{n['category']}:{n['topic']}" not in notified]
    if not new:
        return 0
    for n in new:
        sample = (n.get("samples") or [None])[0]
        etiqueta = "🆕 Tema nuevo" if n["is_new"] else f"📈 Tema en alza (+{n['trend_pct']}%)"
        send(config.NTFY_TOPIC_TEAM, f"{etiqueta} en Cali: {n['topic']}",
             f"{n['category']} · {n['count']} menciones en los últimos 7 días" +
             (f"\n{sample['text'][:200]}" if sample else ""),
             priority=3, tags=["newspaper"],
             click=f"{config.DASHBOARD_URL}/#ciudad",
             view_label="Ver noticia" if sample and sample.get("url") else None,
             view_url=sample.get("url") if sample else None)
    notified |= {f"{n['category']}:{n['topic']}" for n in new}
    _set_state(session, "notified_city_topics", "␟".join(sorted(notified)[-300:]))
    return len(new)


def notify_daily_summary(report_data: dict) -> None:
    """Resumen corto del reporte diario recién generado (job_daily_report) -- lo mismo que dice
    el reporte completo, pero en 3 líneas para no tener que abrir el dashboard."""
    kpis = report_data.get("social_kpis") or {}
    narrative = report_data.get("narrative") or {}
    resumen = narrative.get("resumen_ejecutivo") or "Reporte generado -- ver el dashboard para el detalle."
    msg = f"{kpis.get('total_posts', 0)} publicaciones · {kpis.get('total_likes', 0)} likes · {kpis.get('total_comments', 0)} comentarios\n\n{resumen[:500]}"
    send(config.NTFY_TOPIC_TEAM, "📊 Resumen diario — Monitor Cali", msg, priority=3, tags=["bar_chart"],
         click=f"{config.DASHBOARD_URL}/#reporte")


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


def notify_apify_blocked(session, reason: str) -> None:
    """La vuelta de redes NO corrió por presupuesto (ver src/apify_budget.py). Un aviso por día y por
    motivo: el job se revisa cada 24 h, pero "Actualizar ahora" puede reintentar varias veces."""
    import datetime as dt
    key = f"apify_blocked:{dt.datetime.utcnow().strftime('%Y-%m-%d')}"
    if _get_state(session, key) == reason[:80]:
        return
    _set_state(session, key, reason[:80])
    send(config.NTFY_TOPIC_TECH, "⛔ Apify: la captura de redes NO corrió",
         f"{reason}\nNo se gastó nada. Para reanudarla hace falta confirmar presupuesto.", priority=4, tags=["no_entry"])


def notify_apify_job(session, plan, spent: float | None, estimate: float, n_accounts: int, comment_posts: int,
                     used_after: float | None) -> None:
    """Cierre de cada vuelta de redes: cuánto costó contra lo presupuestado, y cuánto queda del ciclo."""
    import json
    left = max(0.0, plan.ceiling - plan.reserve - used_after) if used_after is not None else None
    over = spent is not None and spent > plan.job_budget * 1.25
    resumen = (f"Gasto real: ${spent:.2f} de ${plan.job_budget:.2f} presupuestados "
               f"({n_accounts} cuentas, comentarios de {comment_posts} post). "
               if spent is not None else "No se pudo medir el gasto real. ")
    if left is not None:
        resumen += f"Quedan ${left:.2f} utilizables hasta el {plan.cycle_end} ({plan.days_left} días)."
    _set_state(session, "apify_last_job", json.dumps({"spent": spent, "budget": plan.job_budget, "estimate": estimate,
                                                      "left": left, "cycle_end": plan.cycle_end}))
    if over:
        send(config.NTFY_TOPIC_TECH, "⚠️ Apify: la vuelta se pasó de lo presupuestado", resumen, priority=5, tags=["warning"])
    else:
        send(config.NTFY_TOPIC_TECH, "💵 Apify: vuelta de redes terminada", resumen, priority=2, tags=["moneybag"])
    if plan.days_left <= 3:
        send(config.NTFY_TOPIC_TECH, "📅 Apify: el ciclo termina pronto",
             f"El ciclo cierra el {plan.cycle_end}. Si el cliente aprueba presupuesto para el siguiente, hay que confirmarlo "
             "(APIFY_CYCLE_BUDGET_USD / APIFY_CYCLE_BUDGET_END); si no, la captura de redes se detiene sola.", priority=3, tags=["calendar"])
