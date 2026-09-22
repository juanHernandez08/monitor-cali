from src.models import Candidate, Source, SourceType, Mention, SentimentScore
from src.pipeline import run_pipeline
from src.sentiment import SentimentResult, SentimentLabel
from src.connectors.news_rss import RSSConnector
from tests.test_news_rss import SAMPLE_FEED


class FakeSentimentEngine:
    def score(self, text, candidate=None, city=False):
        return SentimentResult(
            label=SentimentLabel.NEUTRAL, score=0.0, topic="general", model="fake",
        )


def _seed_candidate_and_source(db_session):
    candidate = Candidate(name="Ana Pérez", aliases=[])
    source = Source(
        type=SourceType.RSS, name="Feed Test",
        config={"feed_url": "https://x.test/feed"},
    )
    db_session.add_all([candidate, source])
    db_session.commit()
    return candidate, source


def _patch_feed(monkeypatch):
    import feedparser
    real_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda url: real_parse(SAMPLE_FEED))


def test_run_pipeline_stores_new_mentions(db_session, monkeypatch):
    _, source = _seed_candidate_and_source(db_session)
    _patch_feed(monkeypatch)

    connector = RSSConnector(feed_url=source.config["feed_url"])
    count = run_pipeline(db_session, source, connector, FakeSentimentEngine())

    assert count == 1  # solo la nota de Ana Pérez matchea, sin Carlos sembrado
    assert db_session.query(Mention).count() == 1
    assert db_session.query(SentimentScore).count() == 1


def test_run_pipeline_is_idempotent(db_session, monkeypatch):
    _, source = _seed_candidate_and_source(db_session)
    _patch_feed(monkeypatch)

    connector = RSSConnector(feed_url=source.config["feed_url"])
    run_pipeline(db_session, source, connector, FakeSentimentEngine())
    second_count = run_pipeline(db_session, source, connector, FakeSentimentEngine())

    assert second_count == 0
    assert db_session.query(Mention).count() == 1
