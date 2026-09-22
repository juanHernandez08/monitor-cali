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
