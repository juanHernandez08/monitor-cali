import datetime as dt

from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel


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


def test_generate_and_store_persists_and_is_idempotent_per_day(db_session):
    from src.report import generate_and_store
    from src.models import Report
    carlos = Candidate(name="Carlos Arias", aliases=[])
    db_session.add(carlos)
    db_session.commit()

    r1 = generate_and_store(db_session, date="2026-09-28")
    assert db_session.query(Report).count() == 1
    r2 = generate_and_store(db_session, date="2026-09-28")
    assert db_session.query(Report).count() == 1  # mismo día: actualiza, no duplica
    assert r1.id == r2.id


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

    report = build_report(db_session, date="2026-09-28")
    assert report["city_topics"][0]["category"] == "movilidad y transporte"
    pdf_bytes = report_to_pdf(report)
    assert pdf_bytes[:4] == b"%PDF"
