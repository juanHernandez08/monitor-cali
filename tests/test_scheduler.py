from src.models import Source, SourceType
from src.scheduler import build_connector, run_group
from src.connectors.google_news import GoogleNewsConnector
from src.connectors.reddit_rss import RedditRSSConnector
from src.connectors.news_rss import RSSConnector


def test_build_connector_by_type(db_session, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    assert isinstance(build_connector(Source(type=SourceType.GOOGLE_NEWS, name="g"), db_session), GoogleNewsConnector)
    assert isinstance(build_connector(Source(type=SourceType.RSS, name="r", config={"feed_url": "x"}), db_session), RSSConnector)
    assert isinstance(build_connector(Source(type=SourceType.REDDIT, name="rd", config={"via": "rss"}), db_session), RedditRSSConnector)
    assert build_connector(Source(type=SourceType.GOOGLE_CSE, name="c", config={}), db_session) is None  # sin key


def test_run_group_skips_sources_without_connector(db_session, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    db_session.add(Source(type=SourceType.GOOGLE_CSE, name="c", config={}))
    db_session.commit()
    import src.scheduler as m
    monkeypatch.setattr(m, "ingest", lambda s, src, conn: 99)
    assert run_group(db_session, [SourceType.GOOGLE_CSE]) == {}
