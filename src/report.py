"""Reporte diario (lunes a viernes): actividad fuerte en redes, comportamiento de candidatos y
concejales, temas de ciudad fuertes o desatendidos, tendencias y lo que aún no se ha analizado --
para no tener que revisar cada pestaña por separado cada mañana."""
import datetime as dt
import io

from src import queries
from src.models import Mention, SentimentScore, Report

SOCIAL_WINDOW_DAYS = 3  # cubre el fin de semana cuando el reporte del lunes mira "desde el viernes"
CITY_WINDOW_DAYS = 7


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


def build_report(session, date: str | None = None) -> dict:
    """Calcula el reporte para `date` (YYYY-MM-DD) a partir del estado ACTUAL de la base de
    datos. No lo guarda -- eso lo hace generate_and_store()."""
    date = date or dt.datetime.utcnow().strftime("%Y-%m-%d")
    return {
        "date": date,
        "social_window_days": SOCIAL_WINDOW_DAYS,
        "city_window_days": CITY_WINDOW_DAYS,
        "social_kpis": queries.social_kpis(session, days=SOCIAL_WINDOW_DAYS),
        "strong_social": queries.social_strong_posts(session, days=SOCIAL_WINDOW_DAYS),
        "city_topics": queries.city_topics(session, days=CITY_WINDOW_DAYS)[:10],
        "city_opportunities": queries.city_opportunities(session, days=CITY_WINDOW_DAYS),
        "pending_review": _pending_review(session, SOCIAL_WINDOW_DAYS),
    }


def generate_and_store(session, date: str | None = None) -> Report:
    """Genera el reporte de `date` (hoy si no se da) y lo guarda. Si ya existe uno para ese día,
    lo reemplaza -- un solo reporte por día, no uno por cada vez que corre el job."""
    date = date or dt.datetime.utcnow().strftime("%Y-%m-%d")
    data = build_report(session, date=date)
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
    """Arma un PDF simple y legible del reporte, para bajar y reenviar por fuera del dashboard."""
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
    story = [Paragraph(f"Reporte diario -- Monitor Alcaldía de Cali 2027", styles["Title"]),
             Paragraph(f"{report['date']}", styles["Normal"]), Spacer(1, 14)]

    def h(text):
        story.append(Spacer(1, 10))
        story.append(Paragraph(text, styles["Heading2"]))

    def bullets(items):
        if not items:
            story.append(Paragraph("Sin novedades en este punto.", styles["Normal"]))
            return
        story.append(ListFlowable([ListItem(Paragraph(i, styles["Normal"])) for i in items], bulletType="bullet"))

    def bar_chart(labels, values, width=460, height=180):
        """Barras horizontales simples -- misma idea que el hbar() del dashboard, en reportlab."""
        if not labels:
            story.append(Paragraph("Sin datos para graficar.", styles["Normal"]))
            return
        pairs = list(zip(labels, values))[:12]
        d = Drawing(width, height)
        chart = HorizontalBarChart()
        chart.x, chart.y, chart.width, chart.height = 140, 10, width - 160, height - 20
        chart.data = [[v for _, v in pairs]]
        chart.categoryAxis.categoryNames = [str(lbl)[:26] for lbl, _ in pairs]
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0
        chart.bars[0].fillColor = BLUE
        chart.barLabels.nudge = 7
        chart.barLabelFormat = "%d"
        chart.barLabels.fontSize = 7
        d.add(chart)
        story.append(d)

    k = report["social_kpis"]
    h("Actividad en redes (candidatos y concejales)")
    bullets([f"{k['total_posts']} publicaciones · {k['total_likes']} likes · {k['total_comments']} comentarios"
             f" en los últimos {report['social_window_days']} días."])
    bar_chart([c["candidate"] for c in k["by_candidate"]], [c["count"] for c in k["by_candidate"]])

    h("Publicaciones con fuerza fuera de lo habitual")
    bullets([f"{p['candidate']} ({p['platform']}): \"{p['text'][:100]}\" -- {p['engagement']} de alcance "
             f"({p['multiplier']}× su propio promedio de ~{p['baseline']})" for p in report["strong_social"]])

    h("Temas de ciudad -- los más mencionados")
    bar_chart([t["category"] for t in report["city_topics"]], [t["count"] for t in report["city_topics"]])
    bullets([f"{t['category']}: {t['count']} menciones" for t in report["city_topics"]])

    h("Novedades donde Carlos podría hablar")
    def _carlos_presence(t):
        return "sin presencia" if t["carlos_mentions"] == 0 else f"{t['carlos_mentions']} menciones"
    bullets([f"{t['topic']} ({t['category']}): {t['count']} menciones, Carlos: {_carlos_presence(t)}"
             for t in report["city_opportunities"]["novedades"]])

    h("Pendiente de análisis")
    p = report["pending_review"]
    bullets([f"{p['total']} menciones aún sin clasificar."] +
            [f"{s['candidate']} · {s['source']}: \"{s['text'][:100]}\"" for s in p["samples"]])

    doc.build(story)
    return buf.getvalue()
