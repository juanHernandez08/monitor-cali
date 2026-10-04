import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.models import Candidate, Source, SourceType, Mention

CSRF = {"X-Requested-With": "monitor"}  # el dashboard la manda en todo POST (src/security.py)


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
    assert client.get("/api/city/emotion-by-topic").json() == []
    assert client.get("/api/feed?city=true").json() == []
    assert client.get("/api/city/opportunities").json() == {"novedades": [], "carlos_strong": []}
    assert client.get("/api/city/kpis").json()["total"] == 0
    assert client.get("/api/agenda").json() == {"speak": [], "avoid": []}
    assert client.get("/api/perception").json() == []
    assert client.get("/api/candidate/topics?name=Carlos Arias").json() == []
    assert client.get("/api/social/posts").json() == []
    assert client.get("/api/social/kpis").json()["total_posts"] == 0
    assert client.get("/api/social/candidates").json() == [{"candidate_id": 1, "name": "Carlos Arias", "party": None, "is_councilor": False}]
    assert client.get("/api/social/strong").json() == []
    assert client.get("/api/social/reach").json() == []
    assert client.get("/api/social/reaction").json() == []
    hist = client.get("/api/institutional-history").json()
    assert len(hist["administrations"]) == 5
    assert len(hist["debt_timeline"]) == 2
    city = client.get("/api/city-history").json()
    assert city["years"][0] == 2008 and len(city["periods"]) == 5 and city["strategies"]
    assert client.get("/api/social/insights").json()["posts_total"] == 0
    assert client.get("/api/conversation/weekly").json()["candidate"] == "Carlos Arias"


def test_refresh_returns_202(client, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m, "run_everything", lambda: None)
    assert client.post("/api/refresh", headers=CSRF).status_code == 202


def test_investigate_requires_a_real_instagram_or_facebook_url(client, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m.config, "APIFY_TOKEN", "fake-token")
    r = client.post("/api/investigate", json={"url": "https://example.com/x", "platform": "instagram"}, headers=CSRF)
    assert r.status_code == 400


def test_investigate_requires_apify_token_configured(client, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m.config, "APIFY_TOKEN", None)
    monkeypatch.setattr(m.config, "INVESTIGATE_ENABLED", True)
    r = client.post("/api/investigate", json={"url": "https://www.instagram.com/unrival/", "platform": "instagram"}, headers=CSRF)
    assert r.status_code == 400


def test_reports_generate_list_get_and_pdf(client):
    r = client.post("/api/reports/generate", headers=CSRF)
    assert r.status_code == 200
    date = r.json()["date"]

    assert len(client.get("/api/reports").json()) == 1
    assert client.get("/api/reports/latest").json()["date"] == date
    assert client.get(f"/api/reports/{date}").json()["date"] == date
    assert client.get("/api/reports/2000-01-01").status_code == 404

    pdf = client.get(f"/api/reports/{date}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"


def test_investigate_returns_live_stats_for_a_profile(client, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m.config, "APIFY_TOKEN", "fake-token")
    monkeypatch.setattr(m.config, "INVESTIGATE_ENABLED", True)
    fake_posts = [
        {"id": "1", "text": "post fuerte", "url": "https://www.instagram.com/p/1/", "author": "unrival",
         "published_at": "2026-09-20T00:00:00", "likes": 900, "comments": 100, "views": 0, "engagement": 1000},
        {"id": "2", "text": "post normal", "url": "https://www.instagram.com/p/2/", "author": "unrival",
         "published_at": "2026-09-10T00:00:00", "likes": 40, "comments": 5, "views": 0, "engagement": 45},
    ]
    monkeypatch.setattr(m, "investigate_profile", lambda token, url, platform, **k: fake_posts)
    r = client.post("/api/investigate", json={"url": "https://www.instagram.com/unrival/", "platform": "instagram"}, headers=CSRF)
    assert r.status_code == 200
    body = r.json()
    assert body["total_posts"] == 2
    assert body["total_likes"] == 940 and body["total_comments"] == 105
    assert body["top_post"]["text"] == "post fuerte"


def test_investigate_is_disabled_by_default_to_protect_the_apify_budget(client, monkeypatch):
    """Cada clic en «Investigar un perfil» gasta dinero de Apify: apagado salvo que se active expresamente."""
    import src.api as m
    monkeypatch.setattr(m.config, "APIFY_TOKEN", "fake-token")
    monkeypatch.setattr(m.config, "INVESTIGATE_ENABLED", False)
    called = []
    monkeypatch.setattr(m, "investigate_profile", lambda *a, **k: called.append(1) or [])
    r = client.post("/api/investigate", json={"url": "https://www.instagram.com/unrival/", "platform": "instagram"}, headers=CSRF)
    assert r.status_code == 403 and not called
