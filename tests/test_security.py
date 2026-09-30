import pytest
from fastapi.testclient import TestClient

from src import security
from src.api import create_app

CSRF = {"X-Requested-With": "monitor"}


@pytest.fixture
def app_client(db_session):
    app = create_app(session_factory=lambda: db_session, start_jobs=False)
    with TestClient(app) as tc:
        yield tc


@pytest.fixture(autouse=True)
def fresh_throttle(monkeypatch):
    monkeypatch.setattr(security, "THROTTLE", security.Throttle())


def test_post_without_csrf_header_is_rejected(app_client):
    assert app_client.post("/api/refresh").status_code == 403


def test_post_from_another_origin_is_rejected(app_client):
    r = app_client.post("/api/refresh", headers={**CSRF, "Origin": "https://evil.example"})
    assert r.status_code == 403


def test_investigate_is_no_longer_a_get(app_client):
    r = app_client.get("/api/investigate", params={"url": "https://www.instagram.com/x/"})
    assert r.status_code == 405


def test_refresh_is_single_flight(app_client, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m, "run_everything", lambda: None)
    assert app_client.post("/api/refresh", headers=CSRF).status_code == 202
    assert app_client.post("/api/refresh", headers=CSRF).status_code == 429  # espera mínima


def test_healthz_is_public_but_health_is_not(app_client, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m.config, "DASHBOARD_USER", "equipo")
    monkeypatch.setattr(m.config, "DASHBOARD_PASSWORD", "clave")
    assert app_client.get("/healthz").json() == {"ok": True}
    assert app_client.get("/health").status_code == 401


def test_security_headers_include_csp_and_no_store(app_client):
    r = app_client.get("/api/summary")
    assert "script-src 'self' https://cdn.jsdelivr.net" in r.headers["content-security-policy"]
    assert "unsafe-inline" not in r.headers["content-security-policy"].split("script-src")[1].split(";")[0]
    assert r.headers["cache-control"] == "no-store"


def test_api_docs_are_disabled_by_default(app_client):
    assert app_client.get("/openapi.json").status_code == 404
    assert app_client.get("/docs").status_code == 404


@pytest.mark.parametrize("bad", ["2026-13-01", "2026-02-30", "x", "2026-01-01%0D%0ASet-Cookie:a=b", "2026-1-1"])
def test_dates_are_validated(app_client, bad):
    assert app_client.get(f"/api/reports/{bad}/pdf").status_code in (400, 404)
    assert app_client.get("/api/feed", params={"day": bad}).status_code == 400


def test_invalid_enum_filters_return_422_not_500(app_client):
    assert app_client.get("/api/mentions", params={"source_type": "nope"}).status_code == 422
    assert app_client.get("/api/feed", params={"label": "nope"}).status_code == 422
    assert app_client.get("/api/social/posts", params={"sort": "nope"}).status_code == 422


def test_cloudflare_access_token_is_enough_when_configured(db_session, monkeypatch):
    import src.api as m

    class FakeVerifier:
        def verify(self, token):
            return {"email": "equipo@campana.co"} if token == "valido" else None

    monkeypatch.setattr(m.config, "DASHBOARD_PASSWORD", None)
    app = create_app(session_factory=lambda: db_session, start_jobs=False, cf_verifier=FakeVerifier())
    with TestClient(app) as c:
        assert c.get("/api/summary").status_code == 401  # directo a la IP, sin pasar por Access
        assert c.get("/api/summary", headers={"Cf-Access-Jwt-Assertion": "falso"}).status_code == 401
        assert c.get("/api/summary", headers={"Cf-Access-Jwt-Assertion": "valido"}).status_code == 200


def test_basic_auth_helper():
    import base64
    good = "Basic " + base64.b64encode(b"u:p").decode()
    assert security.basic_auth_ok(good, "u", "p")
    assert not security.basic_auth_ok(good, "u", "otra")
    assert not security.basic_auth_ok("Basic !!!", "u", "p")
    assert not security.basic_auth_ok(good, "u", None)
