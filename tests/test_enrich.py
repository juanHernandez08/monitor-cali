from src.connectors.base import RawItem
from src.models import Candidate, Source, SourceType, Mention
from src.pipeline import ingest, score_pending
from src.enrich import enrich_pending
from src.sentiment import SentimentResult, SentimentLabel


class ListConnector:
    def __init__(self, items): self.items = items
    def fetch(self, terms): return self.items


class FakeEngine:
    def __init__(self, topic="tema"): self.topic = topic; self.calls = []
    def score(self, text, candidate=None):
        self.calls.append(text)
        return SentimentResult(SentimentLabel.NEGATIVE, -0.6, self.topic, "fake")


def _seed(db_session):
    c = Candidate(name="Carlos Arias", aliases=[])
    gn = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    rss = Source(type=SourceType.RSS, name="El País", config={"feed_url": "x"})
    db_session.add_all([c, gn, rss]); db_session.commit()
    return c, gn, rss


def test_enrich_resolves_url_fetches_body_and_dedups(db_session, monkeypatch):
    _, gn, rss = _seed(db_session)
    ingest(db_session, rss, ListConnector([RawItem(external_id="r1", text="Carlos Arias nota", url="https://elpais.com.co/n/1")]))
    ingest(db_session, gn, ListConnector([
        RawItem(external_id="g1", text="Carlos Arias nota", url="https://news.google.com/rss/articles/AAA"),
        RawItem(external_id="g2", text="Carlos Arias otra", url="https://news.google.com/rss/articles/BBB"),
    ]))
    import src.enrich as m
    real = {"AAA": "https://www.elpais.com.co/n/1/", "BBB": "https://x.co/2"}
    monkeypatch.setattr(m, "resolve_url", lambda url: real[url[-3:]] if "news.google.com" in url else url)
    monkeypatch.setattr(m, "fetch_body", lambda url: "Cuerpo del artículo sobre Carlos Arias" if "x.co" in url else None)

    assert enrich_pending(db_session, limit=10) == 3  # 1 RSS + 2 Google News
    assert db_session.query(Mention).filter_by(external_id="g1").first() is None  # duplicado del RSS → eliminado
    g2 = db_session.query(Mention).filter_by(external_id="g2").one()
    assert g2.url == "https://x.co/2" and g2.body == "Cuerpo del artículo sobre Carlos Arias"
    assert enrich_pending(db_session, limit=10) == 0


def test_enrich_marks_failed_fetch_as_empty_body(db_session, monkeypatch):
    _, gn, _ = _seed(db_session)
    ingest(db_session, gn, ListConnector([RawItem(external_id="g1", text="Carlos Arias", url="https://news.google.com/rss/articles/AAA")]))
    import src.enrich as m
    monkeypatch.setattr(m, "resolve_url", lambda url: None)
    monkeypatch.setattr(m, "fetch_body", lambda url: None)
    enrich_pending(db_session, limit=10)
    assert db_session.query(Mention).one().body == ""


def test_score_waits_for_enrichment_and_uses_body(db_session):
    _, gn, _ = _seed(db_session)
    ingest(db_session, gn, ListConnector([RawItem(external_id="g1", text="Titular sobre Carlos Arias", url="https://news.google.com/x")]))
    engine = FakeEngine()
    assert score_pending(db_session, engine, limit=10) == 0  # sin enriquecer todavía
    m = db_session.query(Mention).one(); m.body = "Cuerpo largo"; db_session.commit()
    assert score_pending(db_session, engine, limit=10) == 1
    assert engine.calls[0] == "Titular sobre Carlos Arias\n\nCuerpo largo"


def test_homonym_topic_marks_mention_irrelevant(db_session):
    _, gn, _ = _seed(db_session)
    ingest(db_session, gn, ListConnector([RawItem(external_id="g1", text="Carlos Arias futbolista", url=None)]))
    m = db_session.query(Mention).one(); m.body = ""; db_session.commit()
    score_pending(db_session, FakeEngine(topic="homónimo"), limit=10)
    assert db_session.query(Mention).one().relevant is False
