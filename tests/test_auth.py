import pytest
from fastapi.testclient import TestClient

from src.api import create_app


@pytest.fixture
def app(db_session):
    return create_app(session_factory=lambda: db_session, start_jobs=False)


def test_no_auth_required_when_dashboard_password_not_set(app, monkeypatch):
    """Comportamiento por defecto (desarrollo local, como hasta ahora): sin DASHBOARD_PASSWORD
    configurada, el sitio sigue abierto -- no cambia nada para quien lo corre en su PC."""
    import src.api as m
    monkeypatch.setattr(m.config, "DASHBOARD_PASSWORD", None)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_requests_without_credentials_are_rejected_when_password_is_set(app, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m.config, "DASHBOARD_USER", "carlos")
    monkeypatch.setattr(m.config, "DASHBOARD_PASSWORD", "s3cret")
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 401
        assert "WWW-Authenticate" in r.headers


def test_wrong_credentials_are_rejected(app, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m.config, "DASHBOARD_USER", "carlos")
    monkeypatch.setattr(m.config, "DASHBOARD_PASSWORD", "s3cret")
    with TestClient(app) as client:
        r = client.get("/health", auth=("carlos", "wrong"))
        assert r.status_code == 401


def test_correct_credentials_are_accepted(app, monkeypatch):
    import src.api as m
    monkeypatch.setattr(m.config, "DASHBOARD_USER", "carlos")
    monkeypatch.setattr(m.config, "DASHBOARD_PASSWORD", "s3cret")
    with TestClient(app) as client:
        r = client.get("/health", auth=("carlos", "s3cret"))
        assert r.status_code == 200


def test_security_headers_are_present_on_every_response(app):
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "same-origin"


def test_static_files_are_also_protected(app, monkeypatch):
    """No solo las rutas de la API -- el JS/CSS también debe quedar detrás del login, si no
    alguien sin acceso igual podría ver la estructura del dashboard."""
    import src.api as m
    monkeypatch.setattr(m.config, "DASHBOARD_USER", "carlos")
    monkeypatch.setattr(m.config, "DASHBOARD_PASSWORD", "s3cret")
    with TestClient(app) as client:
        assert client.get("/static/dashboard.js").status_code == 401
        assert client.get("/static/dashboard.js", auth=("carlos", "s3cret")).status_code == 200
