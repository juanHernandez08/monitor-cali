import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.models import Candidate, Source, SourceType, Mention


@pytest.fixture
def client(db_session):
    app = create_app(session_factory=lambda: db_session, start_jobs=False)
    c = Candidate(name="Carlos Arias", aliases=[])
    s = Source(type=SourceType.GOOGLE_NEWS, name="Google News")
    db_session.add_all([c, s])
    db_session.commit()
    db_session.add(Mention(candidate_id=c.id, source_id=s.id, external_id="m1", text="hola", url="https://x/1"))
    db_session.commit()
    with TestClient(app) as tc:
        yield tc


def test_dashboard_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "Monitor" in r.text


def test_json_routes(client):
    assert client.get("/api/summary?days=7").json()[0]["name"] == "Carlos Arias"
    assert len(client.get("/api/timeline?days=3").json()["labels"]) == 3
    assert client.get("/api/mentions?limit=5").json()[0]["text"] == "hola"
    assert client.get("/api/feed?days=7").json()[0]["kind"] == "news"
    assert client.get("/api/alerts").json() == []
    assert client.get("/api/topics").json() == []
    assert client.get("/health").json()["total_mentions"] == 1
    assert client.get("/api/city/topics").json() == []
    assert client.get("/api/city/emotions").json() == []
    assert client.get("/api/city/opportunities").json() == {"novedades": [], "carlos_strong": []}
    assert client.get("/api/city/kpis").json()["total"] == 0
    assert client.get("/api/agenda").json() == {"speak": [], "avoid": []}
    assert client.get("/api/perception").json() == []
    assert client.get("/api/candidate/topics?name=Carlos Arias").json() == []
    assert client.get("/api/social/posts").json() == []
    assert client.get("/api/social/kpis").json()["total_posts"] == 0


def test_refresh_returns_202(client, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m, "run_everything", lambda: None)
    assert client.post("/api/refresh").status_code == 202
