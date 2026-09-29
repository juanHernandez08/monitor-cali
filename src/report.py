"""Reporte diario (lunes a viernes): actividad fuerte en redes, comportamiento comparado de
candidatos y concejales, temas de ciudad fuertes o desatendidos, tendencias, análisis de por qué
el alcance de Carlos es el que es frente a sus rivales, estrategia propuesta y lo que aún no se ha
analizado -- para no tener que revisar cada pestaña por separado cada mañana."""
import datetime as dt
import io
import json
import logging
import re

from src import queries
from src.models import Mention, SentimentScore, Report

log = logging.getLogger(__name__)

SOCIAL_WINDOW_DAYS = 3  # cubre el fin de semana cuando el reporte del lunes mira "desde el viernes"
CITY_WINDOW_DAYS = 7
COMPARISON_WINDOW_DAYS = 30  # alcance, tendencia y reacción necesitan más volumen que 3 días para no ser ruido
_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _pending_review(session, days: int) -> dict:
    since = dt.datetime.utcnow() - dt.timedelta(days=days)
    q = (session.query(Mention).outerjoin(SentimentScore)
         .filter(Mention.relevant.is_(True), SentimentScore.id.is_(None)))
    total = q.count()
    recent = q.filter(Mention.fetched_at >= since).order_by(Mention.fetched_at.desc()).limit(8).all()
    return {
        "total": total,
        "samples": [{"text": m.text[:200], "candidate": m.candidate.name, "source": m.source.name,
                     "url": m.url} for m in recent],
    }


# ---------- Análisis narrativo (LLM, grounded en las cifras calculadas arriba) ----------

ANALYST_PROMPT = """Eres un analista de datos y estratega de comunicación de la campaña de Carlos Andrés Arias a la Alcaldía de Cali 2027.

Con las cifras REALES de abajo (ventana de {days} días en redes), escribe un análisis para el equipo de campaña. Básate ÚNICAMENTE en estos datos -- no inventes publicaciones, eventos, cifras ni causas que no estén aquí. Si algo no se puede explicar con los datos disponibles, dilo explícitamente ("no se puede determinar con los datos actuales") en vez de especular como si fuera un hecho comprobado. Nunca sugieras que Carlos participe de rivalidades entre hinchadas de equipos deportivos.

## Alcance por candidato o concejal (likes+comentarios promedio por publicación, ritmo de publicación, tendencia entre la primera y la segunda mitad del período)
{reach}

## Cómo reacciona la gente en los comentarios de las publicaciones de cada quien (solo comentarios en su propia publicación)
{reaction}

## Categorías de temas de ciudad de las que Carlos NO ha hablado en los últimos {city_days} días
{gaps}

## Publicaciones que se dispararon muy por encima de lo habitual de esa misma cuenta
{strong}

Responde SOLO con un JSON de la forma:
{{"resumen_ejecutivo": "<2-4 frases: el hallazgo más importante de este corte>",
  "analisis": "<4-7 frases explicando, con los números de arriba, POR QUÉ el alcance de Carlos es el que es frente a sus rivales -- ritmo de publicación, respuesta de la audiencia, temas cubiertos o no cubiertos; si los datos no alcanzan para explicar algo, dilo en vez de adivinar>",
  "estrategia": ["<acción concreta 1, ligada a un hallazgo de arriba>", "<acción 2>", "... entre 3 y 5 acciones>"]}}
"""


def _fmt_reach(rows: list[dict]) -> str:
    if not rows:
        return "Sin publicaciones suficientes de nadie en este período."
    lines = []
    for r in rows:
        trend = (f"tendencia {r['trend_pct']:+d}% entre la primera y la segunda mitad del período"
                 if r["trend_pct"] is not None else "sin tendencia calculable (pocas publicaciones)")
        lines.append(f"- {r['candidate']}: {r['posts']} publicaciones ({r['posts_per_week']}/semana), "
                     f"alcance promedio {r['avg_engagement']} (likes+comentarios) por publicación, {trend}.")
    return "\n".join(lines)


def _fmt_reaction(rows: list[dict]) -> str:
    if not rows:
        return "Sin comentarios suficientes en publicaciones propias en este período."
    return "\n".join(
        f"- {r['candidate']}: {r['comments']} comentarios en sus propias publicaciones -- "
        f"{r['positive_pct']}% positivos, {r['neutral_pct']}% neutrales, {r['negative_pct']}% negativos."
        for r in rows
    )


def _fmt_gaps(rows: list[dict]) -> str:
    if not rows:
        return "No se detectaron categorías sin cubrir en este período."
    return "\n".join(f"- {g['category']}: {g['count']} menciones en la conversación de la ciudad, "
                     f"ninguna publicación de Carlos sobre el tema." for g in rows)


def _fmt_strong(rows: list[dict]) -> str:
    if not rows:
        return "Ninguna publicación se disparó por encima de lo habitual en este período."
    return "\n".join(f"- {p['candidate']} ({p['platform']}): \"{p['text'][:100]}\" -- {p['engagement']} de "
                     f"alcance ({p['multiplier']}× su propio promedio de ~{p['baseline']})." for p in rows)


def generate_narrative(engine, reach: list[dict], reaction: list[dict], gaps: list[dict],
                       strong: list[dict], days: int = COMPARISON_WINDOW_DAYS, city_days: int = CITY_WINDOW_DAYS) -> dict | None:
    """Pide al LLM que analice y proponga estrategia SOLO a partir de las cifras ya calculadas
    (nunca le pasamos texto libre de menciones para que no "descubra" hechos por su cuenta).
    Si el LLM falla o responde algo no parseable, el reporte igual se genera sin esta sección --
    nunca debe tumbar el resto del reporte."""
    prompt = ANALYST_PROMPT.format(days=days, city_days=city_days, reach=_fmt_reach(reach),
                                   reaction=_fmt_reaction(reaction), gaps=_fmt_gaps(gaps), strong=_fmt_strong(strong))
    try:
        text = engine.generate_text(prompt, max_tokens=3000)
        payload = json.loads(_JSON_FENCE.sub("", text).strip())
        return {
            "resumen_ejecutivo": str(payload.get("resumen_ejecutivo", "")).strip(),
            "analisis": str(payload.get("analisis", "")).strip(),
            "estrategia": [str(x).strip() for x in payload.get("estrategia", []) if str(x).strip()][:6],
        }
    except Exception:
        log.exception("no se pudo generar el análisis narrativo del reporte")
        return None


def build_report(session, date: str | None = None, engine=None) -> dict:
    """Calcula el reporte para `date` (YYYY-MM-DD) a partir del estado ACTUAL de la base de
    datos. No lo guarda -- eso lo hace generate_and_store(). `engine` es opcional: sin él, el
    reporte se arma igual pero sin la sección de análisis narrativo (útil para pruebas rápidas o
    si el LLM no está disponible en el momento)."""
    date = date or dt.datetime.utcnow().strftime("%Y-%m-%d")
    reach = queries.candidate_reach_comparison(session, days=COMPARISON_WINDOW_DAYS)
    reaction = queries.candidate_comment_reaction(session, days=COMPARISON_WINDOW_DAYS)
    gaps = queries.candidate_topic_gaps(session, queries.CARLOS, days=CITY_WINDOW_DAYS)
    strong = queries.social_strong_posts(session, days=SOCIAL_WINDOW_DAYS)
    narrative = generate_narrative(engine, reach, reaction, gaps, strong) if engine is not None else None
    return {
        "date": date,
        "social_window_days": SOCIAL_WINDOW_DAYS,
        "city_window_days": CITY_WINDOW_DAYS,
        "comparison_window_days": COMPARISON_WINDOW_DAYS,
        "social_kpis": queries.social_kpis(session, days=SOCIAL_WINDOW_DAYS),
        "strong_social": strong,
        "city_topics": queries.city_topics(session, days=CITY_WINDOW_DAYS)[:10],
        "city_opportunities": queries.city_opportunities(session, days=CITY_WINDOW_DAYS),
        "reach_comparison": reach,
        "comment_reaction": reaction,
        "topic_gaps": gaps,
        "narrative": narrative,
        "pending_review": _pending_review(session, SOCIAL_WINDOW_DAYS),
    }


def generate_and_store(session, date: str | None = None, engine=None) -> Report:
    """Genera el reporte de `date` (hoy si no se da) y lo guarda. Si ya existe uno para ese día,
    lo reemplaza -- un solo reporte por día, no uno por cada vez que corre el job. Sin `engine`
    explícito, construye el configurado (Ollama/Claude) para el análisis narrativo."""
    if engine is None:
        from src.sentiment import build_sentiment_engine
        engine = build_sentiment_engine()
    date = date or dt.datetime.utcnow().strftime("%Y-%m-%d")
    data = build_report(session, date=date, engine=engine)
    report = session.query(Report).filter_by(date=date).first()
    if report is None:
        report = Report(date=date, data=data)
        session.add(report)
    else:
        report.data = data
        report.generated_at = dt.datetime.utcnow()
    session.commit()
    return report


def report_to_pdf(report: dict) -> bytes:
    """Arma un PDF legible del reporte, con el mismo análisis y gráficas que la pestaña, para
    bajar y reenviar por fuera del dashboard."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import HorizontalBarChart

    BLUE = HexColor("#2a78d6")
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=2 * cm, bottomMargin=2 * cm)
    story = [Paragraph("Reporte diario -- Monitor Alcaldía de Cali 2027", styles["Title"]),
             Paragraph(f"{report['date']}", styles["Normal"]), Spacer(1, 14)]

    def h(text):
        story.append(Spacer(1, 10))
        story.append(Paragraph(text, styles["Heading2"]))

    def p(text):
        story.append(Paragraph(text, styles["Normal"]))

    def bullets(items):
        if not items:
            story.append(Paragraph("Sin novedades en este punto.", styles["Normal"]))
            return
        story.append(ListFlowable([ListItem(Paragraph(i, styles["Normal"])) for i in items], bulletType="bullet"))

    def bar_chart(labels, values, width=460, height=180, color=BLUE, value_fmt="%d"):
        if not labels:
            story.append(Paragraph("Sin datos para graficar.", styles["Normal"]))
            return
        pairs = list(zip(labels, values))[:12]
        d = Drawing(width, height)
        chart = HorizontalBarChart()
        chart.x, chart.y, chart.width, chart.height = 150, 10, width - 170, height - 20
        chart.data = [[v for _, v in pairs]]
        chart.categoryAxis.categoryNames = [str(lbl)[:26] for lbl, _ in pairs]
        chart.categoryAxis.labels.fontSize = 7
        chart.bars[0].fillColor = color
        chart.barLabels.nudge = 7
        chart.barLabelFormat = value_fmt
        chart.barLabels.fontSize = 7
        d.add(chart)
        story.append(d)

    narrative = report.get("narrative")
    if narrative:
        h("Resumen ejecutivo")
        p(narrative["resumen_ejecutivo"] or "Sin resumen disponible.")
        h("Por qué el alcance de Carlos es el que es")
        p(narrative["analisis"] or "Sin análisis disponible.")
        h("Estrategia recomendada")
        bullets(narrative["estrategia"])
    else:
        h("Análisis narrativo")
        p("No se generó en este corte (el motor de análisis no estaba disponible). Las cifras de abajo son reales e íntegras igual.")

    h("Alcance promedio por publicación (candidatos y concejales)")
    reach = report.get("reach_comparison", [])
    bar_chart([r["candidate"] for r in reach], [r["avg_engagement"] for r in reach])
    bullets([f"{r['candidate']}: {r['avg_engagement']} de alcance promedio, {r['posts']} publicaciones "
             f"({r['posts_per_week']}/semana)" + (f", tendencia {r['trend_pct']:+d}%" if r["trend_pct"] is not None else "")
             for r in reach])

    h("Reacción ciudadana en comentarios propios")
    reaction = report.get("comment_reaction", [])
    bullets([f"{r['candidate']}: {r['comments']} comentarios -- {r['positive_pct']}% positivos, "
             f"{r['negative_pct']}% negativos" for r in reaction])

    k = report["social_kpis"]
    h("Actividad en redes (candidatos y concejales)")
    bullets([f"{k['total_posts']} publicaciones · {k['total_likes']} likes · {k['total_comments']} comentarios"
             f" en los últimos {report['social_window_days']} días."])
    bar_chart([c["candidate"] for c in k["by_candidate"]], [c["count"] for c in k["by_candidate"]])

    h("Publicaciones con fuerza fuera de lo habitual")
    bullets([f"{sp['candidate']} ({sp['platform']}): \"{sp['text'][:100]}\" -- {sp['engagement']} de alcance "
             f"({sp['multiplier']}× su propio promedio de ~{sp['baseline']})" for sp in report["strong_social"]])

    h("Temas de ciudad -- los más mencionados")
    bar_chart([t["category"] for t in report["city_topics"]], [t["count"] for t in report["city_topics"]])
    bullets([f"{t['category']}: {t['count']} menciones" for t in report["city_topics"]])

    h("Temas de ciudad de los que Carlos no ha hablado")
    bullets([f"{g['category']}: {g['count']} menciones en la ciudad, sin ninguna publicación de Carlos"
             for g in report.get("topic_gaps", [])])

    h("Novedades donde Carlos podría hablar")
    def _carlos_presence(t):
        return "sin presencia" if t["carlos_mentions"] == 0 else f"{t['carlos_mentions']} menciones"
    bullets([f"{t['topic']} ({t['category']}): {t['count']} menciones, Carlos: {_carlos_presence(t)}"
             for t in report["city_opportunities"]["novedades"]])

    h("Pendiente de análisis")
    pend = report["pending_review"]
    bullets([f"{pend['total']} menciones aún sin clasificar."] +
            [f"{s['candidate']} · {s['source']}: \"{s['text'][:100]}\"" for s in pend["samples"]])

    doc.build(story)
    return buf.getvalue()
