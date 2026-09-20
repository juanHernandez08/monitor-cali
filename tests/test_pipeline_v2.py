from src.connectors.base import RawItem
from src.models import Candidate, Source, SourceType, Mention, SentimentScore, Run
from src.pipeline import ingest, score_pending
from src.sentiment import SentimentResult, SentimentLabel


class ListConnector:
    def __init__(self, items): self.items = items
    def fetch(self, search_terms): return self.items


class FakeEngine:
    def __init__(self): self.calls = []
    def score(self, text, candidate=None):
        self.calls.append((text, candidate))
        return SentimentResult(SentimentLabel.NEGATIVE, -0.8, "tema", "fake")


def _seed(db_session):
    carlos = Candidate(name="Carlos Arias", aliases=["Buenos Ciudadanos"])
    ana = Candidate(name="Ana Pérez", aliases=[])
    s1 = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    s2 = Source(type=SourceType.RSS, name="El País", config={"feed_url": "x"})
    db_session.add_all([carlos, ana, s1, s2])
    db_session.commit()
    return carlos, ana, s1, s2


def test_ingest_dedups_across_sources_by_url(db_session):
    _, _, s1, s2 = _seed(db_session)
    a = RawItem(external_id="g1", text="Carlos Arias habló", url="https://www.elpais.com.co/n/1/?utm_source=x")
    b = RawItem(external_id="r1", text="Carlos Arias habló", url="https://elpais.com.co/n/1")

    assert ingest(db_session, s1, ListConnector([a])) == 1
    assert ingest(db_session, s2, ListConnector([b])) == 0
    assert db_session.query(Mention).count() == 1
    assert db_session.query(Mention).one().url_normalized == "elpais.com.co/n/1"


def test_ingest_uses_search_term_when_text_has_no_name(db_session):
    carlos, _, s1, _ = _seed(db_session)
    item = RawItem(external_id="c1", text="este señor no me convence", url=None, search_term="Buenos Ciudadanos")
    assert ingest(db_session, s1, ListConnector([item])) == 1
    assert db_session.query(Mention).one().candidate_id == carlos.id


def test_ingest_records_run_and_score_pending_scores(db_session):
    carlos, _, s1, _ = _seed(db_session)
    ingest(db_session, s1, ListConnector([RawItem(external_id="g1", text="Carlos Arias habló")]))

    run = db_session.query(Run).one()
    assert run.new_mentions == 1 and run.finished_at is not None and run.error is None
    assert db_session.query(SentimentScore).count() == 0

    engine = FakeEngine()
    assert score_pending(db_session, engine, limit=10) == 0  # Google News espera el cuerpo
    db_session.query(Mention).one().body = ""
    db_session.commit()
    assert score_pending(db_session, engine, limit=10) == 1
    assert engine.calls[0][1] == "Carlos Arias"
    assert db_session.query(SentimentScore).one().score == -0.8
    assert score_pending(db_session, engine, limit=10) == 0


def test_ingest_records_error_when_connector_fails(db_session):
    _, _, s1, _ = _seed(db_session)

    class Boom:
        def fetch(self, terms): raise RuntimeError("red caída")

    assert ingest(db_session, s1, Boom()) == 0
    assert "red caída" in db_session.query(Run).one().error


def test_ingest_skips_items_older_than_max_age(db_session):
    import datetime as dt
    _, _, s1, _ = _seed(db_session)
    old = RawItem(external_id="old", text="Carlos Arias hace un año", published_at=dt.datetime.utcnow() - dt.timedelta(days=400))
    new = RawItem(external_id="new", text="Carlos Arias hoy", published_at=dt.datetime.utcnow())
    assert ingest(db_session, s1, ListConnector([old, new]), max_age_days=60) == 1
    assert db_session.query(Mention).one().external_id == "new"
