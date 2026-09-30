import datetime as dt
import json

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel


class FakeNarrativeEngine:
    def __init__(self, payload=None, raise_error=False):
        self.payload = payload or {
            "resumen_ejecutivo": "Resumen de prueba.",
            "analisis": "Análisis de prueba.",
            "estrategia": ["Acción 1", "Acción 2"],
        }
        self.raise_error = raise_error
        self.prompts = []

    def generate_text(self, prompt, max_tokens=1400):
        self.prompts.append(prompt)
        if self.raise_error:
            raise RuntimeError("Ollama caído")
        return json.dumps(self.payload)


def _social_post(db_session, cand, src, ext, likes, comments, when_ago):
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=ext,
                url=f"https://x/{ext}", raw={"kind": "post", "platform": "instagram",
                                             "num_comments": comments, "record": {"likesCount": likes}},
                published_at=now - dt.timedelta(days=when_ago), fetched_at=now)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.5, topic="t", model="f"))


def test_build_report_includes_social_and_pending_sections(db_session):
    from src.report import build_report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, src])
    db_session.commit()
    _social_post(db_session, carlos, src, "p1", likes=40, comments=10, when_ago=1)
    db_session.commit()
    # una mención sin puntuar todavía: cuenta como "pendiente de análisis".
    news = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add(news)
    db_session.commit()
    pending = Mention(candidate_id=carlos.id, source_id=news.id, external_id="pend1", text="nota sin analizar aún",
                      url="https://x/pend1", raw={}, published_at=dt.datetime.utcnow(), fetched_at=dt.datetime.utcnow(),
                      relevant=True)
    db_session.add(pending)
    db_session.commit()

    report = build_report(db_session, date="2026-09-28")
    assert report["date"] == "2026-09-28"
    assert report["social_kpis"]["total_posts"] == 1
    assert report["pending_review"]["total"] == 1
    assert report["pending_review"]["samples"][0]["text"].startswith("nota sin analizar")
    assert "city_topics" in report and "city_opportunities" in report
    assert "reach_comparison" in report and "comment_reaction" in report and "topic_gaps" in report


def test_build_report_without_engine_has_no_narrative(db_session):
    from src.report import build_report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    report = build_report(db_session, date="2026-09-28")
    assert report["narrative"] is None


def test_build_report_with_engine_includes_narrative_grounded_in_real_numbers(db_session):
    from src.report import build_report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    clara = Candidate(name="Clara Luz Roldán", aliases=[])
    social = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, clara, social])
    db_session.commit()
    _social_post(db_session, carlos, social, "p1", likes=20, comments=2, when_ago=1)
    _social_post(db_session, carlos, social, "p2", likes=15, comments=1, when_ago=5)
    _social_post(db_session, clara, social, "p3", likes=400, comments=50, when_ago=1)
    _social_post(db_session, clara, social, "p4", likes=350, comments=40, when_ago=5)
    db_session.commit()

    engine = FakeNarrativeEngine()
    report = build_report(db_session, date="2026-09-28", engine=engine)

    assert report["narrative"] == {
        "resumen_ejecutivo": "Resumen de prueba.",
        "analisis": "Análisis de prueba.",
        "limitaciones": "",
        "estrategia": ["Acción 1", "Acción 2"],
    }
    # el prompt real que se le mandó al LLM debe tener las cifras calculadas, no solo pedirle que opine
    assert "Clara Luz Roldán" in engine.prompts[0]
    assert "Carlos Arias" in engine.prompts[0]
    assert "alcance típico (mediana)" in engine.prompts[0]


def test_narrative_includes_limitaciones_when_the_llm_returns_it(db_session):
    """Pedido del cliente (2026-09-29): la estrategia debe decir explícitamente qué NO se puede
    determinar con los datos actuales (pauta paga, tamaño de audiencia, causas de una subida/bajada
    puntual), no solo lo que sí se puede afirmar."""
    from src.report import build_report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    engine = FakeNarrativeEngine(payload={
        "resumen_ejecutivo": "Resumen.", "analisis": "Análisis.",
        "limitaciones": "No se puede determinar si el alcance depende de pauta paga o del tamaño de audiencia.",
        "estrategia": ["Acción 1"],
    })
    report = build_report(db_session, date="2026-09-28", engine=engine)
    assert "pauta paga" in report["narrative"]["limitaciones"]


def test_fmt_gaps_never_implies_a_permanent_absence(db_session):
    """Bug real (2026-09-29): el reporte decía "Carlos no ha hablado de la reconstrucción" cuando
    sí lo había cubierto, semanas antes de la ventana de 7 días que mide esta sección -- el texto
    que se le manda al LLM debe dejar el plazo explícito para que su redacción no lo pierda."""
    from src.report import _fmt_gaps
    text = _fmt_gaps([{"category": "terremoto y reconstrucción", "count": 12}], city_days=7)
    assert "últimos 7 días" in text.lower()


def test_narrative_generation_fails_gracefully_without_breaking_the_report(db_session):
    from src.report import build_report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    report = build_report(db_session, date="2026-09-28", engine=FakeNarrativeEngine(raise_error=True))
    assert report["narrative"] is None  # no revienta el resto del reporte
    assert report["date"] == "2026-09-28"


def test_generate_and_store_persists_and_is_idempotent_per_day(db_session):
    from src.report import generate_and_store
    from src.models import Report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()

    engine = FakeNarrativeEngine()
    r1 = generate_and_store(db_session, date="2026-09-28", engine=engine)
    assert db_session.query(Report).count() == 1
    r2 = generate_and_store(db_session, date="2026-09-28", engine=engine)
    assert db_session.query(Report).count() == 1  # mismo día: actualiza, no duplica
    assert r1.id == r2.id
    assert r2.data["narrative"]["resumen_ejecutivo"] == "Resumen de prueba."


def test_report_to_pdf_bytes(db_session):
    from src.report import build_report, report_to_pdf
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    report = build_report(db_session, date="2026-09-28")
    pdf_bytes = report_to_pdf(report)
    assert pdf_bytes[:4] == b"%PDF"


def test_report_to_pdf_with_real_city_topics_and_social_data(db_session):
    # Regresión: city_topics() devuelve "category", no "topic" -- una vez rompió el PDF con
    # KeyError en cuanto hubo datos reales de ciudad (los tests con listas vacías no lo detectaban).
    from src.report import build_report, report_to_pdf
    carlos = Candidate(name="Carlos Arias", aliases=[])
    cali = Candidate(name="Cali (ciudad)", aliases=[], kind="city")
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    social = Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)")
    db_session.add_all([carlos, cali, src, social])
    db_session.commit()
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=cali.id, source_id=src.id, external_id="c1", text="hueco en la via",
               url="https://x/c1", raw={}, published_at=now, fetched_at=now, relevant=True)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEGATIVE, score=-0.5,
                                  topic="huecos", category="movilidad y transporte", model="f"))
    db_session.commit()
    _social_post(db_session, carlos, social, "p1", likes=10, comments=2, when_ago=1)
    db_session.commit()

    report = build_report(db_session, date="2026-09-28", engine=FakeNarrativeEngine())
    assert report["city_topics"][0]["category"] == "movilidad y transporte"
    pdf_bytes = report_to_pdf(report)
    assert pdf_bytes[:4] == b"%PDF"


def test_report_to_pdf_without_narrative_still_works(db_session):
    from src.report import build_report, report_to_pdf
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    report = build_report(db_session, date="2026-09-28")  # sin engine -> narrative None
    pdf_bytes = report_to_pdf(report)
    assert pdf_bytes[:4] == b"%PDF"
