from types import SimpleNamespace
from src.connectors.reddit import RedditConnector


class FakeAsyncClient:
    def __init__(self, posts):
        self._posts = posts

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def scrape(self):
        return SimpleNamespace(reddit=SimpleNamespace(
            posts_by_keyword=self._posts_by_keyword,
        ))

    async def _posts_by_keyword(self, keyword, sort_by):
        return SimpleNamespace(data=self._posts)


def test_reddit_connector_normalizes_posts(monkeypatch):
    fake_posts = [{
        "id": "abc123", "title": "Ana Pérez y su plan de seguridad",
        "body": "Comentarios sobre la propuesta", "author": "user1",
        "url": "https://reddit.com/r/cali/abc123", "created_at": "2026-09-01T10:00:00",
    }]

    import src.connectors.reddit as reddit_module
    monkeypatch.setattr(
        reddit_module, "BrightDataClient", lambda token: FakeAsyncClient(fake_posts),
    )

    connector = RedditConnector(api_token="fake-token")
    items = connector.fetch(search_terms=["Ana Pérez"])

    assert len(items) == 1
    assert items[0].external_id == "abc123"
    assert "Ana Pérez" in items[0].text
