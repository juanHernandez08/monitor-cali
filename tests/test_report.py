import datetime as dt
import json

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel


class FakeNarrativeEngine:
    def __init__(self, payload=None, raise_error=False):
        self.payload = payload or {
            "resumen_ejecutivo": "Resumen de prueba.",
            "factores_hipotesis": "Factores de prueba.",
            "activacion_respuesta": "Activación de prueba.",
            "plan_72h": [{"dia": "Día 1", "accion": "Acción 1", "dato_necesario": "Dato 1",
                         "fuente": "Fuente 1", "condicion_para_publicar": "Condición 1"}],
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
        "factores_hipotesis": "Factores de prueba.",
        "activacion_respuesta": "Activación de prueba.",
        "limitaciones": "",
        "plan_72h": [{"dia": "Día 1", "accion": "Acción 1", "dato_necesario": "Dato 1",
                     "fuente": "Fuente 1", "condicion_para_publicar": "Condición 1"}],
    }
    # el prompt real que se le mandó al LLM debe tener las cifras calculadas, no solo pedirle que opine
    assert "Clara Luz Roldán" in engine.prompts[0]
    assert "Carlos Arias" in engine.prompts[0]
    assert "alcance típico (mediana)" in engine.prompts[0]
    # regla anti-inconsistencia de números (reporte del cliente: +17% en un lado, +20% en otro)
    assert "nunca" in engine.prompts[0].lower() and "número" in engine.prompts[0].lower()


def test_narrative_includes_limitaciones_when_the_llm_returns_it(db_session):
    """Pedido del cliente (2026-09-29): la estrategia debe decir explícitamente qué NO se puede
    determinar con los datos actuales (pauta paga, tamaño de audiencia, causas de una subida/bajada
    puntual), no solo lo que sí se puede afirmar."""
    from src.report import build_report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    engine = FakeNarrativeEngine(payload={
        "resumen_ejecutivo": "Resumen.", "factores_hipotesis": "Factores.", "activacion_respuesta": "Activación.",
        "limitaciones": "No se puede determinar si el alcance depende de pauta paga o del tamaño de audiencia.",
        "plan_72h": [],
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


def test_build_report_includes_method_scope_and_conversation_emotions(db_session):
    """Pedido del cliente 2026-10-01: ventana y metodología claras (qué se revisó, de dónde, en
    qué ventana) y conversación con emoción + apalancador, no solo volumen por tema."""
    from src.report import build_report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    cali = Candidate(name="Cali (ciudad)", aliases=[], kind="city")
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([carlos, cali, src])
    db_session.commit()
    now = dt.datetime.utcnow()
    m = Mention(candidate_id=cali.id, source_id=src.id, external_id="c1", text="partido del América",
               url="https://x/c1", raw={}, published_at=now, fetched_at=now, relevant=True)
    db_session.add(m)
    db_session.flush()
    db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.POSITIVE, score=0.6,
                                  topic="futbol", category="deporte", model="f",
                                  emotion="felicidad", apalancador="triunfo del América"))
    db_session.commit()

    report = build_report(db_session, date="2026-09-28")
    scope = report["method_scope"]
    assert scope["publicaciones_revisadas_7d"] >= 1
    assert "google_news" in scope["plataformas"]
    assert "ventanas" in scope and set(scope["ventanas"]) == {"actividad_redes", "conversacion_ciudad", "comparacion_cuentas"}

    ce = next(c for c in report["conversation_emotions"] if c["category"] == "deporte")
    assert ce["dominant_emotion"] == "felicidad"
    assert "triunfo del América" in ce["apalancadores"]


def test_changes_vs_previous_diffs_against_the_last_stored_report(db_session):
    """Pedido del cliente 2026-10-01: tabla de qué apareció, qué persiste, qué cambió y qué no se
    pudo volver a comprobar frente al corte anterior -- "la tendencia de una métrica no reemplaza
    esta comparación"."""
    from src.report import build_report
    cali = Candidate(name="Cali (ciudad)", aliases=[], kind="city")
    src = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([cali, src])
    db_session.commit()
    now = dt.datetime.utcnow()

    def _add(ext, cat, score, ago):
        m = Mention(candidate_id=cali.id, source_id=src.id, external_id=ext, text=ext, url=f"https://x/{ext}",
                    raw={}, published_at=now - dt.timedelta(days=ago), fetched_at=now - dt.timedelta(days=ago), relevant=True)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel.NEUTRAL, score=0.0, topic="t",
                                      category=cat, model="f"))

    _add("a", "seguridad y convivencia", 0.0, 2)
    db_session.commit()
    from src.models import Report
    # informe anterior guardado directo (sin motor de sentimiento real): solo "seguridad"
    db_session.add(Report(date="2026-09-27", data=build_report(db_session, date="2026-09-27")))
    db_session.commit()

    _add("b", "seguridad y convivencia", 0.0, 1)  # persiste
    _add("c", "seguridad y convivencia", 0.0, 1)
    _add("d", "cultura y eventos", 0.0, 1)  # apareció
    db_session.commit()

    report = build_report(db_session, date="2026-09-28")
    changes = report["changes_vs_previous"]
    assert changes["informe_anterior"] == "2026-09-27"
    assert "cultura y eventos" in changes["aparecio"]
    assert "seguridad y convivencia" in changes["persiste"]


def test_report_to_pdf_without_narrative_still_works(db_session):
    from src.report import build_report, report_to_pdf
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()
    report = build_report(db_session, date="2026-09-28")  # sin engine -> narrative None
    pdf_bytes = report_to_pdf(report)
    assert pdf_bytes[:4] == b"%PDF"


def test_an_automatic_report_without_the_llm_does_not_wipe_the_narrative_already_written_today(db_session):
    """El reporte de las 7 a. m. corre con el PC del cliente apagado: antes pisaba al reporte del día que SÍ
    tenía análisis (pasó el 2026-10-01). Las cifras se refrescan, el análisis ya redactado se conserva."""
    from src.report import generate_and_store
    first = generate_and_store(db_session, date="2026-10-01", engine=FakeNarrativeEngine())
    assert first.data["narrative"]["resumen_ejecutivo"] == "Resumen de prueba."
    second = generate_and_store(db_session, date="2026-10-01", engine=FakeNarrativeEngine(raise_error=True))
    assert second.data["narrative"]["resumen_ejecutivo"] == "Resumen de prueba."


def test_fill_missing_narrative_completes_a_recent_report_from_its_stored_numbers(db_session):
    from src.models import Report
    from src.report import generate_and_store, fill_missing_narrative
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    generate_and_store(db_session, date=today, engine=FakeNarrativeEngine(raise_error=True))
    assert db_session.query(Report).one().data["narrative"] is None

    engine = FakeNarrativeEngine()
    done = fill_missing_narrative(db_session, engine=engine)
    assert done is not None and done.data["narrative"]["plan_72h"][0]["accion"] == "Acción 1"
    assert db_session.query(Report).one().data["narrative"]["resumen_ejecutivo"] == "Resumen de prueba."
    assert len(engine.prompts) == 1
    # ya completo: no vuelve a pedirle nada a la IA
    assert fill_missing_narrative(db_session, engine=engine) is None and len(engine.prompts) == 1


def test_fill_missing_narrative_leaves_the_report_alone_while_the_llm_is_still_down(db_session):
    from src.models import Report
    from src.report import generate_and_store, fill_missing_narrative
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    generate_and_store(db_session, date=today, engine=FakeNarrativeEngine(raise_error=True))
    assert fill_missing_narrative(db_session, engine=FakeNarrativeEngine(raise_error=True)) is None
    assert db_session.query(Report).one().data["narrative"] is None


def test_fill_missing_narrative_ignores_old_reports(db_session):
    from src.report import generate_and_store, fill_missing_narrative
    generate_and_store(db_session, date="2020-01-01", engine=FakeNarrativeEngine(raise_error=True))
    assert fill_missing_narrative(db_session, engine=FakeNarrativeEngine()) is None
