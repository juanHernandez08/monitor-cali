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


def test_social_connector_gets_known_posts_pending_comments_and_marks_attempted(db_session, monkeypatch):
    import datetime as dt
    from src.models import Candidate, Mention
    import src.scheduler as m
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "t")
    monkeypatch.setattr(m.config, "SOCIAL_ACCOUNTS", [{"platform": "instagram", "url": "https://www.instagram.com/x/", "candidate": "Carlos Arias"}])
    c = Candidate(name="Carlos Arias", aliases=[])
    src = Source(type=SourceType.SOCIAL, name="IG")
    db_session.add_all([c, src])
    db_session.commit()
    now = dt.datetime.utcnow()
    db_session.add(Mention(candidate_id=c.id, source_id=src.id, external_id="ig:post:p1", text="Trincheras en Cali", url="https://www.instagram.com/p/T/",
                           raw={"kind": "post", "account": "https://www.instagram.com/x/", "num_comments": "300", "record": {"post_id": "p1"}}, published_at=now, fetched_at=now))
    db_session.add(Mention(candidate_id=c.id, source_id=src.id, external_id="ig:post:p2", text="ya con comentarios", url="https://www.instagram.com/p/D/",
                           raw={"kind": "post", "account": "https://www.instagram.com/x/", "num_comments": "5", "comments_fetched": True, "record": {"post_id": "p2"}}, published_at=now, fetched_at=now))
    db_session.commit()

    conn = build_connector(src, db_session)
    assert conn.known_post_ids == {"https://www.instagram.com/x/": ["p1", "p2"]}
    assert [p["url"] for p in conn.pending_comment_posts] == ["https://www.instagram.com/p/T/"]
    assert conn.pending_comment_posts[0]["title"] == "Trincheras en Cali" and conn.pending_comment_posts[0]["candidate"] == "Carlos Arias"
    assert conn.credits.remaining() > 0

    conn.comments_attempted = {"https://www.instagram.com/p/T/"}
    m.mark_comments_fetched(db_session, conn)
    assert db_session.query(Mention).filter_by(external_id="ig:post:p1").one().raw["comments_fetched"] is True


def test_city_sources_use_their_own_terms(db_session, monkeypatch):
    from src.scheduler import build_connector
    gn = Source(type=SourceType.GOOGLE_NEWS, name="Google News Cali", config={"city": True, "terms": ["Cali"], "context": ""})
    conn = build_connector(gn, db_session)
    captured = {}

    class Inner:
        def fetch(self, terms): captured["terms"] = terms; return []
    conn.inner = Inner()
    conn.fetch(["Carlos Arias", "Roberto Ortiz"])
    assert captured["terms"] == ["Cali"]
