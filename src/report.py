"""Reporte diario (lunes a viernes): método y alcance explícitos, cambios frente al informe
anterior, comparación de cuentas, conversación de ciudad con emoción y apalancador (qué la
dispara), activación vs. respuesta factual, plan concreto de 72 horas, y fuentes/límites/pendientes
-- para no tener que revisar cada pestaña por separado cada mañana.

Estructura y contenido rediseñados 2026-10-01 a partir de una revisión detallada del cliente
comparando el reporte automático con su informe manual anterior: le faltaba la capa de
interpretación, evidencia trazable y seguimiento que ya tenían, aunque las métricas nuevas
(comparación entre cuentas, tendencias, publicaciones extraordinarias) se conservan."""
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
BOGOTA = dt.timezone(dt.timedelta(hours=-5))
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


# ---------- Método y alcance (computado en Python, no depende del LLM) ----------

def _method_scope(session) -> dict:
    """Ventana y alcance explícitos de cada sección -- antes el reporte mezclaba "últimos 3 días",
    "últimos 7 días" y un período general sin decir claramente cuál aplicaba a qué (feedback del
    cliente 2026-10-01). Hora de generación en hora de Colombia."""
    now_bog = dt.datetime.now(BOGOTA)
    windows = {
        "actividad_redes": {"days": SOCIAL_WINDOW_DAYS,
                            "proposito": "actividad en redes, publicaciones con fuerza inusual y pendientes de clasificar"},
        "conversacion_ciudad": {"days": CITY_WINDOW_DAYS,
                                "proposito": "conversación de ciudad, temas, emociones y oportunidades"},
        "comparacion_cuentas": {"days": COMPARISON_WINDOW_DAYS,
                                "proposito": "comparación de alcance y tendencia entre cuentas (necesita más volumen para no ser ruido)"},
    }
    for w in windows.values():
        start = now_bog - dt.timedelta(days=w["days"])
        w["inicio"] = start.strftime("%Y-%m-%d %H:%M")
        w["fin"] = now_bog.strftime("%Y-%m-%d %H:%M")
    scope7 = queries.report_scope(session, CITY_WINDOW_DAYS)
    return {
        "generado": now_bog.strftime("%Y-%m-%d %H:%M") + " (hora de Colombia)",
        "ventanas": windows,
        "publicaciones_revisadas_7d": scope7["publications"],
        "comentarios_revisados_7d": scope7["comments"],
        "plataformas": scope7["platforms"],
        "cuentas_y_medios_revisados": scope7["account_count"],
    }


# ---------- Cambios frente al informe anterior (diff computado, no LLM) ----------

def _changes_vs_previous(session, date: str, city_topics: list[dict]) -> dict | None:
    """Compara los temas de ciudad de hoy contra el último reporte guardado antes de `date` --
    qué apareció, qué persiste, qué cambió y qué no se pudo volver a comprobar. Pedido del cliente
    2026-10-01: "la tendencia de una métrica no reemplaza esta comparación". None si no hay un
    reporte anterior con qué comparar (primer corte)."""
    prev = (session.query(Report).filter(Report.date < date).order_by(Report.date.desc()).first())
    if prev is None:
        return None
    prev_topics = {t["category"]: t["count"] for t in (prev.data or {}).get("city_topics", [])}
    cur_topics = {t["category"]: t["count"] for t in city_topics}
    appeared = [c for c in cur_topics if c not in prev_topics]
    persisted = [c for c in cur_topics if c in prev_topics]
    not_reverified = [c for c in prev_topics if c not in cur_topics]  # estaba antes, ya no aparece en esta ventana
    changed = []
    for c in persisted:
        before, now = prev_topics[c], cur_topics[c]
        if before and now != before:
            changed.append({"category": c, "antes": before, "ahora": now,
                            "variacion_pct": round((now - before) / before * 100)})
    return {
        "informe_anterior": prev.date,
        "aparecio": appeared, "persiste": persisted,
        "cambio": sorted(changed, key=lambda r: -abs(r["variacion_pct"]))[:8],
        "no_se_pudo_volver_a_comprobar": not_reverified,
    }


# ---------- Conversación y emociones (computado a partir de city_topics, no LLM) ----------

def _conversation_emotions(city_topics: list[dict], limit: int = 6) -> list[dict]:
    """Qué situación concreta genera cada tema y qué emoción predomina -- con su apalancador
    (qué la dispara) y evidencia textual con link. Pedido del cliente 2026-10-01: "el apalancador
    es lo más valioso del reconocimiento de emociones, porque permite instrumentalizar la
    lectura"; "'Seguridad: 356 menciones' indica volumen, pero no explica la preocupación"."""
    out = []
    for t in city_topics[:limit]:
        samples = t.get("samples") or []
        apalancadores = [s["apalancador"] for s in samples if s.get("apalancador")]
        out.append({
            "category": t["category"], "count": t["count"], "dominant_emotion": t.get("dominant_emotion"),
            "apalancadores": list(dict.fromkeys(apalancadores))[:3],  # sin duplicados, conserva el orden
            "evidencia": [{"text": s["text"][:220], "url": s.get("url"), "source": s.get("source"),
                          "published_at": s.get("published_at")} for s in samples[:2]],
        })
    return out


# ---------- Análisis narrativo (LLM, grounded en las cifras ya calculadas) ----------

ANALYST_PROMPT = """Eres un analista de datos y estratega de comunicación de la campaña de Carlos Andrés Arias a la Alcaldía de Cali 2027.

Con las cifras REALES de abajo (ventana de {days} días en redes), escribe un análisis para el equipo de campaña. Básate ÚNICAMENTE en estos datos -- no inventes publicaciones, eventos, cifras ni causas que no estén aquí. Si algo no se puede explicar con los datos disponibles, dilo explícitamente ("no se puede determinar con los datos actuales") en vez de especular como si fuera un hecho comprobado. Nunca sugieras que Carlos participe de rivalidades entre hinchadas de equipos deportivos.

REGLA CRÍTICA sobre números: NUNCA repitas de memoria un porcentaje, conteo o cifra exacta de las tablas de abajo -- aunque te parezca fácil de recordar, un número mal transcrito en el texto queda contradiciendo a la tabla real que el lector ve más abajo en el mismo reporte (esto ya pasó: un informe mostró "+17%" en el resumen y "+20%" en la tabla para el mismo dato). Cuando necesites referirte a un número, escribe "ver tabla de arriba" o describe la dirección del cambio sin el valor exacto ("subió de forma notable", "se mantuvo estable"), nunca el dígito.

REGLA IMPORTANTE sobre la sección "temas sin cubrir" de abajo: mide solo los últimos {city_days} días. NUNCA la redactes como si fuera una ausencia total o permanente ("Carlos no habla de X", "nunca ha tocado Y") -- el candidato puede haber cubierto ese tema semanas antes, fuera de esta ventana. Escribe siempre "en los últimos {city_days} días" o "en este corte" al mencionar un tema sin cubrir, y usa la fórmula "no se detectaron publicaciones clasificadas sobre este tema en las cuentas y la ventana revisadas" en vez de afirmar que no habló.

## Alcance por candidato o concejal -- "alcance típico por publicación" es la MEDIANA de likes+comentarios (no promedio: un post viral lo infla), con su intervalo de confianza; también ritmo de publicación y tendencia de la mediana entre la primera y la segunda mitad del período. Si dos intervalos se cruzan, no afirmes que uno supera al otro.
{reach}

## Cómo reacciona la gente en los comentarios de las publicaciones de cada quien (solo comentarios en su propia publicación)
{reaction}

## Categorías de temas de ciudad que Carlos NO cubrió en los últimos {city_days} días (puede haberlas cubierto antes; esto es SOLO de esta ventana)
{gaps}

## Publicaciones que se dispararon muy por encima de lo habitual de esa misma cuenta
{strong}

Responde SOLO con un JSON de la forma:
{{"resumen_ejecutivo": "<2-4 frases: el hallazgo más importante de este corte, sin repetir cifras exactas de memoria>",
  "factores_hipotesis": "<4-7 frases explicando, con los datos de arriba, qué factores se observan en el alcance de Carlos frente a sus rivales -- ritmo de publicación, respuesta de la audiencia, temas cubiertos o no EN ESTA VENTANA. Deja explícito que son CORRELACIONES/factores observados, no causas demostradas: los datos describen frecuencia y rendimiento, no prueban que la ausencia de un tema cause el alcance. Si los datos no alcanzan para explicar algo, dilo en vez de adivinar.>",
  "activacion_respuesta": "<3-5 frases: de lo que dice la gente, qué es intensidad emocional pasajera y qué es una señal real de activación (repetición del mismo reclamo, urgencia, peticiones concretas) -- un comentario positivo aislado no demuestra por sí solo alta activación. Señala qué información VERIFICABLE (no opinión) podría responder a esas peticiones, si los datos la contienen.>",
  "limitaciones": "<3-5 frases: qué preguntas relevantes NO se pueden responder con estos datos -- sesgo de audiencia propia (quien comenta en la cuenta de Carlos no es una muestra de toda Cali), cobertura incompleta, posible duplicación de la misma publicación entre plataformas, pauta paga, tamaño de audiencia de cada cuenta, o causas específicas detrás de una subida/bajada puntual, cuando esa información no está en las cifras de arriba. Sé específico sobre qué falta, no genérico.>",
  "plan_72h": [{{"dia": "Día 1", "accion": "<acción concreta y ejecutable>", "dato_necesario": "<qué información hace falta confirmar antes de publicar>", "fuente": "<de dónde sale ese dato -- un hallazgo de arriba, o a quién preguntarle>", "condicion_para_publicar": "<qué tiene que cumplirse antes de sacarlo -- p. ej. confirmar una cifra oficial>"}}, "... un ítem por cada uno de los 3 días, 2 a 3 acciones por día"]}}
"""


def _fmt_reach(rows: list[dict]) -> str:
    if not rows:
        return "Sin publicaciones suficientes de nadie en este período."
    lines = []
    for r in rows:
        t = r.get("median_trend_pct", r["trend_pct"])
        trend = (f"la mediana varió {t:+d}% entre la primera y la segunda mitad del período"
                 if t is not None and r["posts"] >= 6 else "sin tendencia confiable (menos de 6 publicaciones)")
        med = r.get("median_engagement", r["avg_engagement"])
        ci = r.get("median_ci")
        lines.append(f"- {r['candidate']}: {r['posts']} publicaciones ({r['posts_per_week']}/semana), "
                     f"alcance típico (mediana) {med}" + (f" [IC 95%: {ci[0]} a {ci[1]}]" if ci else "") +
                     f", promedio {r['avg_engagement']} (likes+comentarios) por publicación, {trend}.")
    return "\n".join(lines)


def _fmt_reaction(rows: list[dict]) -> str:
    if not rows:
        return "Sin comentarios suficientes en publicaciones propias en este período."
    return "\n".join(
        f"- {r['candidate']}: {r['comments']} comentarios en sus propias publicaciones -- "
        f"{r['positive_pct']}% positivos, {r['neutral_pct']}% neutrales, {r['negative_pct']}% negativos."
        for r in rows
    )


def _fmt_gaps(rows: list[dict], city_days: int = CITY_WINDOW_DAYS) -> str:
    if not rows:
        return f"No se detectaron categorías sin cubrir por Carlos en los últimos {city_days} días."
    return "\n".join(f"- {g['category']}: {g['count']} menciones en la conversación de la ciudad, "
                     f"ninguna publicación de Carlos sobre el tema EN LOS ÚLTIMOS {city_days} DÍAS "
                     f"(puede haberlo cubierto antes de esta ventana)." for g in rows)


def _fmt_strong(rows: list[dict]) -> str:
    if not rows:
        return "Ninguna publicación se disparó por encima de lo habitual en este período."
    return "\n".join(f"- {p['candidate']} ({p['platform']}): \"{p['text'][:100]}\" -- {p['engagement']} de "
                     f"alcance ({p['multiplier']}× su propio promedio de ~{p['baseline']})." for p in rows)


def generate_narrative(engine, reach: list[dict], reaction: list[dict], gaps: list[dict],
                       strong: list[dict], days: int = COMPARISON_WINDOW_DAYS, city_days: int = CITY_WINDOW_DAYS) -> dict | None:
    """Pide al LLM que analice y proponga un plan SOLO a partir de las cifras ya calculadas (nunca
    le pasamos texto libre de menciones para que no "descubra" hechos por su cuenta, y se le pide
    explícitamente que nunca repita un número exacto de memoria -- ver ANALYST_PROMPT). Si el LLM
    falla o responde algo no parseable, el reporte igual se genera sin esta sección -- nunca debe
    tumbar el resto del reporte."""
    prompt = ANALYST_PROMPT.format(days=days, city_days=city_days, reach=_fmt_reach(reach),
                                   reaction=_fmt_reaction(reaction), gaps=_fmt_gaps(gaps, city_days), strong=_fmt_strong(strong))
    try:
        text = engine.generate_text(prompt, max_tokens=3500)
        payload = json.loads(_JSON_FENCE.sub("", text).strip())
        plan = []
        for item in payload.get("plan_72h", []):
            if not isinstance(item, dict):
                continue
            plan.append({
                "dia": str(item.get("dia", "")).strip(),
                "accion": str(item.get("accion", "")).strip(),
                "dato_necesario": str(item.get("dato_necesario", "")).strip(),
                "fuente": str(item.get("fuente", "")).strip(),
                "condicion_para_publicar": str(item.get("condicion_para_publicar", "")).strip(),
            })
        return {
            "resumen_ejecutivo": str(payload.get("resumen_ejecutivo", "")).strip(),
            "factores_hipotesis": str(payload.get("factores_hipotesis", "")).strip(),
            "activacion_respuesta": str(payload.get("activacion_respuesta", "")).strip(),
            "limitaciones": str(payload.get("limitaciones", "")).strip(),
            "plan_72h": plan[:12],
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
    city_topics = queries.city_topics(session, days=CITY_WINDOW_DAYS)[:10]
    narrative = generate_narrative(engine, reach, reaction, gaps, strong) if engine is not None else None
    return {
        "date": date,
        "social_window_days": SOCIAL_WINDOW_DAYS,
        "city_window_days": CITY_WINDOW_DAYS,
        "comparison_window_days": COMPARISON_WINDOW_DAYS,
        "method_scope": _method_scope(session),
        "changes_vs_previous": _changes_vs_previous(session, date, city_topics),
        "social_kpis": queries.social_kpis(session, days=SOCIAL_WINDOW_DAYS),
        "strong_social": strong,
        "city_topics": city_topics,
        "conversation_emotions": _conversation_emotions(city_topics),
        "emotion_heatmap": queries.city_emotion_heatmap(session, days=CITY_WINDOW_DAYS),
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
    # Si la IA no estuvo disponible ahora pero hoy ya se había redactado el análisis, se conserva: antes un
    # reporte automático de las 7 a. m. (con el PC del cliente apagado) pisaba al que sí tenía análisis
    # (2026-10-01). Las cifras sí se refrescan.
    if data.get("narrative") is None and report is not None and (report.data or {}).get("narrative"):
        data["narrative"] = report.data["narrative"]
    if report is None:
        report = Report(date=date, data=data)
        session.add(report)
    else:
        report.data = data
        report.generated_at = dt.datetime.utcnow()
    session.commit()
    return report


def fill_missing_narrative(session, engine=None, max_age_days: int = 1) -> Report | None:
    """Redacta el análisis narrativo de un reporte reciente que quedó sin él -- la IA vive en el PC del
    cliente y a las 7 a. m. (hora del reporte automático) suele estar apagado. Usa las cifras YA guardadas en
    el reporte (no recalcula nada), así que el texto es coherente con las tablas que el equipo ya vio.
    Devuelve el reporte actualizado, o None si no había nada que completar o la IA sigue sin responder."""
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=max_age_days)).strftime("%Y-%m-%d")
    report = session.query(Report).filter(Report.date >= cutoff).order_by(Report.date.desc()).first()
    if report is None or (report.data or {}).get("narrative"):
        return None
    if engine is None:
        from src.sentiment import build_sentiment_engine
        engine = build_sentiment_engine()
    d = report.data or {}
    narrative = generate_narrative(
        engine, d.get("reach_comparison", []), d.get("comment_reaction", []), d.get("topic_gaps", []), d.get("strong_social", []),
        days=d.get("comparison_window_days", COMPARISON_WINDOW_DAYS), city_days=d.get("city_window_days", CITY_WINDOW_DAYS))
    if not narrative:
        return None
    report.data = {**d, "narrative": narrative}
    session.commit()
    return report


def report_to_pdf(report: dict) -> bytes:
    """Arma un PDF legible del reporte, con el mismo análisis y gráficas que la pestaña, para
    bajar y reenviar por fuera del dashboard. Formato ejecutivo pedido por el cliente 2026-09-30:
    secciones numeradas, tipografía serif, tablas numeradas en vez de texto en forma de lista, y
    gráficas con pie de figura -- resumen → método y alcance → cambios frente al informe anterior →
    métricas y comparación entre cuentas → conversación y emociones → activación y respuesta
    factual → plan de 72 horas → fuentes, límites y pendientes."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, CondPageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.graphics.charts.barcharts import HorizontalBarChart
    from reportlab.pdfgen.canvas import Canvas

    BLUE = "#2a78d6"
    RED = "#b0432e"
    MUTED = HexColor("#6e6d66")
    INK = HexColor("#1a1a16")
    HEAD_BG = HexColor("#eef2f8")
    GRID = HexColor("#d8d8d0")

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("RTitle", parent=base["Title"], fontName="Times-Bold", fontSize=17,
                                 alignment=TA_CENTER, spaceAfter=3),
        "subtitle": ParagraphStyle("RSubtitle", parent=base["Normal"], fontName="Times-Italic", fontSize=11,
                                    textColor=MUTED, alignment=TA_CENTER, spaceAfter=2),
        "meta": ParagraphStyle("RMeta", parent=base["Normal"], fontName="Times-Roman", fontSize=9.5,
                                textColor=MUTED, alignment=TA_CENTER),
        "h1": ParagraphStyle("RH1", parent=base["Heading1"], fontName="Times-Bold", fontSize=13,
                              spaceBefore=16, spaceAfter=6, textColor=INK),
        "h2": ParagraphStyle("RH2", parent=base["Heading2"], fontName="Times-Bold", fontSize=10.5,
                              spaceBefore=10, spaceAfter=4, textColor=INK),
        "body": ParagraphStyle("RBody", parent=base["Normal"], fontName="Times-Roman", fontSize=10,
                                leading=14, alignment=TA_JUSTIFY, spaceAfter=5),
        "note": ParagraphStyle("RNote", parent=base["Normal"], fontName="Times-Italic", fontSize=8.5,
                                leading=11, textColor=MUTED, spaceAfter=7),
        "caption": ParagraphStyle("RCaption", parent=base["Normal"], fontName="Times-Italic", fontSize=8.5,
                                   textColor=MUTED, spaceBefore=2, spaceAfter=12),
        "cell": ParagraphStyle("RCell", parent=base["Normal"], fontName="Times-Roman", fontSize=8.5, leading=11),
        "cellhead": ParagraphStyle("RCellHead", parent=base["Normal"], fontName="Times-Bold", fontSize=8.5,
                                    leading=11, textColor=INK),
        "quote": ParagraphStyle("RQuote", parent=base["Normal"], fontName="Times-Italic", fontSize=9.5,
                                 leading=13, leftIndent=10, textColor=INK, spaceAfter=4),
    }

    class _NumberedCanvas(Canvas):
        """Pie de página con 'Página X de Y' -- requiere dos pasadas (patrón estándar de reportlab:
        la cuenta total de páginas solo se sabe al final, así que se guarda el estado de cada
        página y se dibuja el pie recién al cerrar el documento)."""
        def __init__(self, *args, **kwargs):
            Canvas.__init__(self, *args, **kwargs)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for state in self._saved:
                self.__dict__.update(state)
                self.setFont("Times-Italic", 8)
                self.setFillColor(MUTED)
                self.drawString(2 * cm, 1.3 * cm, "Monitor de Sentimiento -- Alcaldía de Cali 2027 -- uso interno de campaña")
                self.drawRightString(letter[0] - 2 * cm, 1.3 * cm, f"Página {self._pageNumber} de {total}")
                Canvas.showPage(self)
            Canvas.save(self)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=2 * cm, bottomMargin=2.3 * cm)
    counters = {"section": 0, "sub": 0, "table": 0, "fig": 0}
    story = [
        Paragraph("Monitor de Sentimiento -- Alcaldía de Cali 2027", styles["title"]),
        Paragraph("Informe diario de monitoreo de opinión pública", styles["subtitle"]),
        Paragraph(f"Candidato: Carlos Arias (Partido de la U) &nbsp;|&nbsp; Fecha de corte: {report['date']}",
                   styles["meta"]),
        Spacer(1, 8), HRFlowable(width="100%", thickness=0.75, color=GRID), Spacer(1, 12),
    ]

    def h(text):
        counters["section"] += 1
        counters["sub"] = 0
        story.append(Paragraph(f"{counters['section']}. {text}", styles["h1"]))

    def h3(text):
        counters["sub"] += 1
        story.append(Paragraph(f"{counters['section']}.{counters['sub']} {text}", styles["h2"]))

    def p(text):
        story.append(Paragraph(text, styles["body"]))

    def note(text):
        story.append(Paragraph(text, styles["note"]))

    def quote(text):
        story.append(Paragraph(f"“{text}”", styles["quote"]))

    def table(headers, rows, col_widths=None, caption=None):
        if not rows:
            p("Sin datos para esta tabla en el período revisado.")
            return
        data = [[Paragraph(str(hd), styles["cellhead"]) for hd in headers]]
        for r in rows:
            data.append([Paragraph(str(c), styles["cell"]) for c in r])
        t = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
            ("GRID", (0, 0), (-1, -1), 0.5, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#faf9f6")]),
        ]))
        story.append(t)
        if caption:
            counters["table"] += 1
            story.append(Paragraph(f"Tabla {counters['table']}. {caption}", styles["caption"]))
        else:
            story.append(Spacer(1, 10))

    def chart(labels, series_list, series_names=None, hexcolors=(BLUE, RED), width=460, height=180, caption=None):
        """series_list: una o varias listas de valores alineadas con labels (varias = barras
        agrupadas, p. ej. positivos vs. negativos por candidato)."""
        if not labels or not any(series_list):
            p("Sin datos para graficar.")
            return
        n = min(12, len(labels))
        labels_c, series_c = labels[:n], [s[:n] for s in series_list]
        d = Drawing(width, height)
        c = HorizontalBarChart()
        c.x, c.y, c.width, c.height = 150, 10, width - 170, height - 20
        c.data = series_c
        c.categoryAxis.categoryNames = [str(lbl)[:26] for lbl in labels_c]
        c.categoryAxis.labels.fontSize = 7
        c.barLabels.nudge = 7
        c.barLabelFormat = "%d"
        c.barLabels.fontSize = 7
        for i, hexcol in enumerate(hexcolors[:len(series_c)]):
            c.bars[i].fillColor = HexColor(hexcol)
        d.add(c)
        story.append(d)
        if series_names and len(series_c) > 1:
            legend = "&nbsp;&nbsp;&nbsp;".join(
                f'<font color="{hexcolors[i]}">■</font> {name}' for i, name in enumerate(series_names))
            story.append(Paragraph(legend, styles["note"]))
        if caption:
            counters["fig"] += 1
            story.append(Paragraph(f"Figura {counters['fig']}. {caption}", styles["caption"]))
        else:
            story.append(Spacer(1, 10))

    def _num(v: float) -> str:
        return f"{v:.2f}".replace(".", ",")

    def _intensity_word(v: float) -> str:
        return "alta" if v >= 0.6 else "media" if v >= 0.35 else "leve"

    def heatmap_drawing(hm: dict):
        rows, emos = hm["rows"], hm["emotions"]
        label_w, rh, head, foot = 138, 27, 24, 34
        cw = (460 - label_w) / len(emos)
        width, height = 460, head + rh * len(rows) + foot
        d = Drawing(width, height)
        mx = max((c["count"] for r in rows for c in r["cells"].values()), default=1)

        def shade(t):
            return HexColor("#%02x%02x%02x" % (round(255 - (255 - 31) * t), round(255 - (255 - 111) * t), round(255 - (255 - 181) * t)))

        for j, e in enumerate(emos):
            lab = {"sin emoción marcada": "Sin emoción"}.get(e, e.capitalize())
            d.add(String(label_w + cw * (j + 0.5), height - 15, lab, fontName="Times-Bold", fontSize=7.4, textAnchor="middle", fillColor=HexColor("#1d2330")))
        for i, r in enumerate(rows):
            y = height - head - rh * (i + 1)
            d.add(String(label_w - 6, y + rh / 2 - 1, _topic_label(r["category"], {"subtopics": []}).split(" -- ")[0][:30],
                         fontName="Times-Roman", fontSize=7.6, textAnchor="end", fillColor=HexColor("#1d2330")))
            d.add(String(label_w - 6, y + rh / 2 - 9, f"{r['total']} menciones", fontName="Times-Italic", fontSize=6.2, textAnchor="end", fillColor=HexColor("#6e6d66")))
            for j, e in enumerate(emos):
                x = label_w + cw * j
                c = r["cells"].get(e)
                t = (c["count"] / mx) if c else 0
                d.add(Rect(x + 1, y + 1, cw - 2, rh - 2, fillColor=shade(t) if c else HexColor("#f1f2f5"), strokeColor=HexColor("#ffffff"), strokeWidth=0.8))
                if c:
                    dark = t > 0.5
                    d.add(String(x + cw / 2, y + rh - 11, str(c["count"]), fontName="Times-Bold", fontSize=8.6, textAnchor="middle",
                                 fillColor=HexColor("#ffffff") if dark else HexColor("#1d2330")))
                    d.add(String(x + cw / 2, y + 7.5, f"int. {_num(c['intensity'])}", fontName="Times-Roman", fontSize=5.9, textAnchor="middle",
                                 fillColor=HexColor("#ffffff") if dark else HexColor("#5b6475")))
                    d.add(Rect(x + 4, y + 2.5, cw - 8, 1.8, fillColor=HexColor("#e6e1d8"), strokeColor=None))
                    d.add(Rect(x + 4, y + 2.5, (cw - 8) * c["intensity"], 1.8, fillColor=HexColor("#d9822b"), strokeColor=None))
        ly = 8
        d.add(String(label_w, ly + 12, "Menos menciones", fontName="Times-Roman", fontSize=6.6, fillColor=HexColor("#5b6475")))
        for k in range(6):
            d.add(Rect(label_w + 62 + k * 16, ly + 10, 16, 8, fillColor=shade(k / 5), strokeColor=None))
        d.add(String(label_w + 62 + 6 * 16 + 4, ly + 12, f"Más ({mx})", fontName="Times-Roman", fontSize=6.6, fillColor=HexColor("#5b6475")))
        d.add(Rect(label_w + 230, ly + 10, 22, 2, fillColor=HexColor("#d9822b"), strokeColor=None))
        d.add(String(label_w + 256, ly + 8, "Intensidad (0 leve a 1 muy fuerte)", fontName="Times-Roman", fontSize=6.6, fillColor=HexColor("#5b6475")))
        return d

    def _no_presence(topic_count: int) -> str:
        return ("no se detectaron publicaciones clasificadas sobre este tema en las cuentas y la ventana revisadas"
                if topic_count == 0 else f"{topic_count} menciones")

    def _topic_label(cat: str, row: dict) -> str:
        """"otro" desagregado en sus subtemas reales -- un cajón de sastre sin abrir no dice nada
        (pedido del cliente 2026-10-01)."""
        if cat != "otro" or not row.get("subtopics"):
            return cat
        subs = ", ".join(f"{s['topic']} ({s['count']})" for s in row["subtopics"][:4])
        return f"otro -- principalmente: {subs}"

    narrative = report.get("narrative")
    if narrative:
        h("Resumen ejecutivo")
        p(narrative.get("resumen_ejecutivo") or "Sin resumen disponible.")
    else:
        h("Resumen ejecutivo")
        p("El análisis narrativo aún no se redactó: lo hace la inteligencia artificial del PC del cliente, que estaba apagado o sin conexión al generar este reporte. Se completa solo cuando vuelve a estar en línea. Las cifras de este reporte son reales e íntegras igual.")

    # ---------- Método y alcance ----------
    h("Método y alcance")
    scope = report.get("method_scope") or {}
    p(f"Generado el {scope.get('generado', '—')}.")
    windows = list((scope.get("ventanas") or {}).values())
    table(["Ventana temporal", "Período", "Días"],
          [[w["proposito"].capitalize(), f"{w['inicio']} a {w['fin']}", w["days"]] for w in windows],
          col_widths=[6.5 * cm, 7 * cm, 2 * cm],
          caption="Ventanas de tiempo usadas para cada análisis de este informe.")
    p(f"En los últimos {report.get('city_window_days', CITY_WINDOW_DAYS)} días se revisaron "
      f"{scope.get('publicaciones_revisadas_7d', 0)} publicaciones y {scope.get('comentarios_revisados_7d', 0)} "
      f"comentarios, de {scope.get('cuentas_y_medios_revisados', 0)} cuentas/medios distintos "
      f"({', '.join(scope.get('plataformas', [])) or 'sin datos'}).")
    note("\"Alcance\" en este reporte significa likes + comentarios por publicación, tal como el scraper los "
         "captura en el momento (no incluye reproducciones ni \"personas alcanzadas\": las plataformas no entregan "
         "esa cifra fuera de sus propias herramientas internas de cada cuenta). Se usa la mediana en vez del "
         "promedio porque una sola publicación viral infla el promedio; el intervalo de confianza del 95% viene de "
         "un bootstrap sobre esas mismas publicaciones. La comparación entre plataformas es aproximada: cada una "
         "mide y expone sus métricas de forma distinta.")

    # ---------- Cambios frente al informe anterior ----------
    changes = report.get("changes_vs_previous")
    h("Cambios frente al informe anterior")
    if not changes:
        p("No hay un reporte anterior guardado con el cual comparar (primer corte).")
    else:
        p(f"Comparado con el reporte del {changes['informe_anterior']}:")
        table(["Categoría", "Antes", "Ahora", "Variación"],
              [[c["category"], c["antes"], c["ahora"], f"{c['variacion_pct']:+d}%"] for c in changes["cambio"]],
              col_widths=[7 * cm, 2.5 * cm, 2.5 * cm, 3.5 * cm],
              caption="Categorías de conversación de ciudad con cambio de volumen frente al informe anterior.")
        otras = ([("Apareció", cat) for cat in changes["aparecio"]]
                 + [("Persiste", cat) for cat in changes["persiste"]]
                 + [("No se pudo volver a comprobar", cat) for cat in changes["no_se_pudo_volver_a_comprobar"]])
        table(["Estado", "Categoría"], [[estado, cat] for estado, cat in otras],
              col_widths=[6 * cm, 9.5 * cm],
              caption="Otras novedades frente al informe anterior (sin cifra comparable directa).")

    # ---------- Métricas y comparación entre cuentas ----------
    h("Métricas y comparación entre cuentas")
    h3("Alcance típico por publicación (mediana) -- candidatos y concejales")
    reach = report.get("reach_comparison", [])
    reach_vals = [r.get("median_engagement", r["avg_engagement"]) for r in reach]
    chart([r["candidate"] for r in reach], [reach_vals],
          caption="Alcance típico por publicación (mediana de likes + comentarios), candidatos y concejales.")
    table(["Candidato/concejal", "Alcance mediana", "IC 95%", "Publicaciones", "Por semana", "Tendencia"],
          [[r["candidate"], r.get("median_engagement", r["avg_engagement"]),
            f"{r['median_ci'][0]} a {r['median_ci'][1]}" if r.get("median_ci") else "—",
            r["posts"], r["posts_per_week"], f"{r['trend_pct']:+d}%" if r["trend_pct"] is not None else "—"]
           for r in reach],
          col_widths=[4 * cm, 2.3 * cm, 2.7 * cm, 2.3 * cm, 2.2 * cm, 2 * cm],
          caption="Detalle de alcance por publicación, candidatos y concejales.")

    h3("Reacción ciudadana en comentarios propios")
    reaction = report.get("comment_reaction", [])
    note("Solo comentarios de ciudadanos en las publicaciones PROPIAS de cada quien (no menciones de paso en otro "
         "lado) -- quien comenta en una cuenta no es una muestra representativa de toda Cali, es la audiencia que "
         "ya sigue a esa cuenta.")
    chart([r["candidate"] for r in reaction],
          [[r["positive_pct"] for r in reaction], [r["negative_pct"] for r in reaction]],
          series_names=["% positivos", "% negativos"],
          caption="Reacción ciudadana (% positivos vs. % negativos) en comentarios propios.")
    table(["Candidato/concejal", "Comentarios clasificados", "% positivos", "% negativos"],
          [[r["candidate"], r["comments"], r["positive_pct"], r["negative_pct"]] for r in reaction],
          col_widths=[5.5 * cm, 4 * cm, 3 * cm, 3 * cm],
          caption="Detalle de reacción ciudadana en comentarios propios.")

    k = report["social_kpis"]
    h3("Actividad en redes (candidatos y concejales)")
    p(f"{k['total_posts']} publicaciones, {k['total_likes']} likes y {k['total_comments']} comentarios "
      f"en los últimos {report['social_window_days']} días.")
    chart([c["candidate"] for c in k["by_candidate"]], [[c["count"] for c in k["by_candidate"]]],
          caption="Publicaciones por candidato o concejal en la ventana revisada.")
    table(["Candidato/concejal", "Publicaciones"], [[c["candidate"], c["count"]] for c in k["by_candidate"]],
          col_widths=[9 * cm, 6.5 * cm], caption="Detalle de publicaciones por candidato o concejal.")

    h3("Publicaciones con fuerza fuera de lo habitual")
    table(["Candidato/concejal", "Plataforma", "Publicación", "Alcance", "Veces su propio promedio"],
          [[sp["candidate"], sp["platform"], sp["text"][:100], sp["engagement"], f"{sp['multiplier']}× (~{sp['baseline']})"]
           for sp in report["strong_social"]],
          col_widths=[2.8 * cm, 2 * cm, 6.2 * cm, 1.6 * cm, 2.3 * cm],
          caption="Publicaciones con alcance muy por encima del promedio propio de cada cuenta.")

    h3("Temas de ciudad más mencionados")
    topics = report["city_topics"]
    chart([_topic_label(t["category"], t) for t in topics], [[t["count"] for t in topics]],
          caption="Temas de ciudad con más menciones en la ventana revisada.")
    table(["Tema", "Menciones"], [[_topic_label(t["category"], t), t["count"]] for t in topics],
          col_widths=[11.5 * cm, 4 * cm], caption="Detalle de temas de ciudad por volumen de menciones.")

    h3("Temas de ciudad que Carlos no cubrió en esta ventana")
    table(["Categoría", "Menciones en la ciudad", "Cobertura de Carlos"],
          [[g["category"], g["count"], _no_presence(0)] for g in report.get("topic_gaps", [])],
          col_widths=[5 * cm, 4 * cm, 6.5 * cm],
          caption="Temas con conversación activa en Cali sin presencia detectada de Carlos.")

    h3("Novedades donde Carlos podría hablar")
    table(["Tema", "Categoría", "Menciones", "Cobertura de Carlos"],
          [[t["topic"], t["category"], t["count"], _no_presence(t["carlos_mentions"])]
           for t in report["city_opportunities"]["novedades"]],
          col_widths=[5 * cm, 4 * cm, 2.5 * cm, 4 * cm],
          caption="Novedades de ciudad con oportunidad de pronunciamiento.")

    # ---------- Conversación y emociones ----------
    h("Conversación y emociones")
    note("Emoción y matiz vienen de la clasificación automática de cada mención (rueda de 6 emociones núcleo + "
         "\"sin emoción marcada\"); el apalancador es lo que el texto deja ver como disparador concreto de esa "
         "emoción -- es la parte más útil para decidir qué hacer, no solo el volumen.")
    conv = report.get("conversation_emotions", [])
    hm = report.get("emotion_heatmap")
    if hm and hm.get("rows"):
        story.append(CondPageBreak(11 * cm))  # título, nota y mapa juntos: el mapa necesita ~9 cm
        h3("Mapa de calor: emociones percibidas por tema")
        note(f"Últimos {report.get('city_window_days', CITY_WINDOW_DAYS)} días. El color y el número grande son las menciones de cada celda; "
             "la barra naranja y «int.» son la <b>intensidad</b>: fuerza media de la carga emocional de esas menciones, de 0 (leve) a 1 (muy fuerte), "
             "medida con el valor absoluto del puntaje que la IA asigna a cada texto.")
        story.append(heatmap_drawing(hm))
        counters["fig"] += 1
        story.append(Paragraph(f"Figura {counters['fig']}. Mapa de calor de emociones por tema: menciones (color y número) e intensidad (barra e «int.»).", styles["caption"]))
        h3("Apalancadores: qué dispara cada emoción")
        rows_l = []
        for lv in hm.get("levers", []):
            apal = "<br/>".join(f"• {a['text']} (n={a['count']}, int. {_num(a['intensity'])})" for a in lv["apalancadores"]) or "sin apalancador registrado"
            ej = lv.get("ejemplo") or {}
            if ej.get("text"):
                link = f' (<link href="{ej["url"]}">ver original</link>)' if ej.get("url") else ""
                apal += f"<br/><i>Ejemplo: “{ej['text'][:140]}” -- {ej.get('source', '')}{link}</i>"
            rows_l.append([_topic_label(lv["category"], {"subtopics": []}), lv["emotion"].capitalize(),
                           f"{lv['count']} ({lv['pct']} % del tema)", f"{_num(lv['intensity'])} ({_intensity_word(lv['intensity'])})", apal])
        table(["Tema", "Emoción", "Menciones", "Intensidad", "Apalancadores (n = veces que se repite)"], rows_l,
              col_widths=[2.6 * cm, 2 * cm, 2.4 * cm, 2.2 * cm, 6.8 * cm],
              caption="Apalancadores más repetidos de las dos emociones principales de cada tema, con intensidad y un ejemplo citable.")
    else:
        table(["Tema", "Menciones", "Emoción predominante", "Apalancadores"],
              [[_topic_label(ce["category"], {"subtopics": []}), ce["count"], ce["dominant_emotion"] or "sin emoción marcada",
                "; ".join(ce["apalancadores"]) or "—"] for ce in conv],
              col_widths=[3.5 * cm, 2 * cm, 3.5 * cm, 6.5 * cm],
              caption="Emoción predominante y apalancadores por tema de conversación de ciudad.")
    for ce in conv:
        if ce["evidencia"]:
            h3(f"Evidencia -- {_topic_label(ce['category'], {'subtopics': []})}")
            for ev in ce["evidencia"]:
                link = f' (<link href="{ev["url"]}">ver original</link>)' if ev.get("url") else ""
                quote(f"{ev['text']} -- {ev.get('source', '')}{link}")

    # ---------- Activación y respuesta factual / Factores observados ----------
    if narrative:
        h("Activación y respuesta factual")
        p(narrative.get("activacion_respuesta") or "Sin análisis disponible en este corte.")
        h("Factores observados e hipótesis por comprobar")
        note("Describe correlaciones y factores observados en los datos, no causas demostradas.")
        p(narrative.get("factores_hipotesis") or "Sin análisis disponible.")

        h("Plan de 72 horas")
        plan = narrative.get("plan_72h") or []
        if not plan:
            p("Sin plan generado en este corte.")
        else:
            table(["Día", "Acción", "Dato necesario", "Fuente", "Condición para publicar"],
                  [[item.get(k, "") for k in ("dia", "accion", "dato_necesario", "fuente", "condicion_para_publicar")]
                   for item in plan],
                  col_widths=[1.8 * cm, 4.8 * cm, 3.4 * cm, 2.5 * cm, 3.3 * cm],
                  caption="Plan de acción recomendado para las próximas 72 horas.")

    # ---------- Fuentes, límites y pendientes ----------
    h("Fuentes, límites y pendientes")
    if narrative and narrative.get("limitaciones"):
        p(narrative["limitaciones"])
    pend = report["pending_review"]
    pend_pct = round(pend["total"] / max(scope.get("publicaciones_revisadas_7d", 0) + scope.get("comentarios_revisados_7d", 0), 1) * 100, 1)
    note(f"{pend['total']} menciones capturadas aún sin clasificar en el momento de este corte (~{pend_pct}% del "
         f"volumen revisado en los últimos {report.get('city_window_days', CITY_WINDOW_DAYS)} días) -- lo que digan "
         f"no está reflejado en las cifras de arriba todavía. Límites conocidos: la audiencia que comenta en cada "
         f"cuenta no es una muestra de toda Cali; la misma noticia puede aparecer por más de un medio o plataforma "
         f"y contarse más de una vez pese al filtro de duplicados; la cobertura depende de qué cuentas y medios "
         f"están configurados hoy, no de todo lo que se publica en Cali.")
    table(["Candidato/concejal", "Fuente", "Texto"],
          [[s["candidate"], s["source"],
            (f'<link href="{s["url"]}">{s["text"][:100]}</link>' if s.get("url") else s["text"][:100])]
           for s in pend["samples"]],
          col_widths=[3.5 * cm, 3 * cm, 9 * cm],
          caption="Muestra de menciones capturadas aún sin clasificar.")

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buf.getvalue()
