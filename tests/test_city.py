import datetime as dt

from src.connectors.base import RawItem
from src.models import Candidate, Source, SourceType, Mention, SentimentScore, SentimentLabel
from src.pipeline import ingest, score_pending, CITY_NAME
from src.sentiment import _parse_payload, CATEGORIES, SentimentResult


class ListConnector:
    def __init__(self, items): self.items = items
    def fetch(self, terms): return self.items


def test_parse_payload_reads_category_and_falls_back_to_otro():
    r = _parse_payload('{"label":"negative","score":-0.5,"topic":"agua en Terrón","category":"servicios públicos"}', "m")
    assert r.category == "servicios públicos"
    r2 = _parse_payload('{"label":"neutral","score":0,"topic":"x","category":"cosa rara"}', "m")
    assert r2.category == "otro"
    assert "seguridad" in CATEGORIES and "otro" in CATEGORIES


def test_city_source_items_without_candidate_go_to_city_and_with_candidate_to_candidate(db_session):
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="El País Cali", config={"feed_url": "x", "city": True})
    other = Source(type=SourceType.GOOGLE_NEWS, name="Google News", config={})
    db_session.add_all([city, carlos, feed, other])
    db_session.commit()
    n = ingest(db_session, feed, ListConnector([
        RawItem(external_id="a", text="Cortes de agua en Cali este lunes", url="https://x/a"),
        RawItem(external_id="b", text="Carlos Arias pide plan de choque", url="https://x/b"),
    ]))
    assert n == 2
    assert db_session.query(Mention).filter_by(external_id="a").one().candidate.name == CITY_NAME
    assert db_session.query(Mention).filter_by(external_id="b").one().candidate.name == "Carlos Arias"
    # una fuente que no es de ciudad sigue descartando lo que no nombra a nadie
    assert ingest(db_session, other, ListConnector([RawItem(external_id="c", text="Clima en Cali", url="https://x/c")])) == 0


def test_city_items_are_scored_with_city_prompt_and_store_category(db_session):
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    db_session.add_all([city, feed])
    db_session.commit()
    ingest(db_session, feed, ListConnector([RawItem(external_id="a", text="Vecinos protestan por falta de agua", url="https://x/a")]))

    class Engine:
        def __init__(self): self.calls = []
        def score(self, text, candidate=None, city=False):
            self.calls.append((candidate, city))
            return SentimentResult(SentimentLabel.NEGATIVE, -0.6, "agua", "f", category="servicios públicos")

    e = Engine()
    assert score_pending(db_session, e, limit=10) == 1
    assert e.calls == [(CITY_NAME, True)]
    sc = db_session.query(SentimentScore).one()
    assert sc.category == "servicios públicos" and sc.label == SentimentLabel.NEGATIVE


def _seed_city(db_session):
    from src.queries import summary
    city = Candidate(name=CITY_NAME, kind="city", aliases=[])
    carlos = Candidate(name="Carlos Arias", aliases=[])
    feed = Source(type=SourceType.RSS, name="Q'hubo", config={"feed_url": "x", "city": True})
    yt = Source(type=SourceType.YOUTUBE, name="YouTube Cali", config={"city": True})
    db_session.add_all([city, carlos, feed, yt])
    db_session.commit()
    now = dt.datetime.utcnow()
    rows = [
        # (candidato, ext, texto, fuente, categoría, topic, label, score, hace_días, raw)
        (city, "a", "Sin agua en Terrón", feed, "servicios públicos", "agua en terrón colorado", "negative", -0.7, 1, {}),
        (city, "b", "Otra vez sin agua", yt, "servicios públicos", "agua en terrón colorado", "negative", -0.9, 2, {"kind": "comment", "video_title": "Cali sin agua"}),
        (city, "c", "Emcali responde", feed, "servicios públicos", "emcali", "neutral", 0.0, 3, {}),
        (city, "d", "Feria de Cali confirmada", feed, "cultura y eventos", "feria de cali", "positive", 0.6, 1, {}),
        (city, "e", "Atracos en el MIO", feed, "seguridad", "atracos mio", "negative", -0.6, 2, {}),
        (city, "f", "Semana pasada: robos", feed, "seguridad", "robos", "negative", -0.5, 10, {}),  # período anterior
        (city, "g", "Semana pasada: más robos", feed, "seguridad", "robos", "negative", -0.5, 11, {}),
        (carlos, "h", "Carlos Arias anuncia plan de cultura", feed, "cultura y eventos", "plan cultura", "positive", 0.5, 1, {}),
        (carlos, "i", "Carlos Arias apoya la Feria", feed, "cultura y eventos", "feria", "positive", 0.4, 2, {}),
        (carlos, "j", "Carlos Arias en evento cultural", feed, "cultura y eventos", "evento", "positive", 0.3, 2, {}),
    ]
    for cand, ext, text, src, cat, topic, label, score, ago, raw in rows:
        when = now - dt.timedelta(days=ago)
        m = Mention(candidate_id=cand.id, source_id=src.id, external_id=ext, text=text, url=f"https://x/{ext}",
                    raw=raw, author="u", published_at=when, fetched_at=when)
        db_session.add(m)
        db_session.flush()
        db_session.add(SentimentScore(mention_id=m.id, label=SentimentLabel(label), score=score, topic=topic, model="f", category=cat))
    db_session.commit()
    return city, carlos


def test_city_is_excluded_from_candidate_views(db_session):
    from src.queries import summary, timeline, sources_by_candidate, feed
    _seed_city(db_session)
    assert [r["name"] for r in summary(db_session, days=7)] == ["Carlos Arias"]
    assert [s["name"] for s in timeline(db_session, days=7)["series"]] == ["Carlos Arias"]
    assert sources_by_candidate(db_session, days=7)["candidates"] == ["Carlos Arias"]
    assert all(r["candidate"] == "Carlos Arias" for r in feed(db_session, days=7))


def test_city_topics_with_trend_perception_subtopics_and_samples(db_session):
    from src.queries import city_topics
    _seed_city(db_session)
    rows = {r["category"]: r for r in city_topics(db_session, days=7)}
    sp = rows["servicios públicos"]
    assert sp["count"] == 3 and sp["previous"] == 0 and sp["negative"] == 2 and sp["neutral"] == 1
    assert sp["subtopics"][0] == {"topic": "agua en terrón colorado", "count": 2}
    assert sp["samples"][0]["text"] == "Otra vez sin agua" and sp["samples"][0]["url"] == "https://x/b"
    sec = rows["seguridad"]
    assert sec["count"] == 1 and sec["previous"] == 2 and sec["trend_pct"] == -50
    assert "cultura y eventos" in rows and "Carlos Arias" not in str(rows)  # solo ciudad


def test_city_opportunities_for_carlos(db_session):
    from src.queries import city_opportunities
    _seed_city(db_session)
    o = city_opportunities(db_session, days=7)
    hot = [x["category"] for x in o["hot_without_carlos"]]
    assert "servicios públicos" in hot  # molestia alta, Carlos no habla de eso
    assert "cultura y eventos" not in hot
    strong = [x["category"] for x in o["carlos_strong"]]
    assert strong == ["cultura y eventos"]  # 3 menciones positivas de Carlos


def test_city_kpis(db_session):
    from src.queries import city_kpis
    _seed_city(db_session)
    k = city_kpis(db_session, days=7)
    assert k["total"] == 5 and k["top_category"] == "servicios públicos"
    assert k["negative_pct"] == 60  # 3 de 5 negativas
