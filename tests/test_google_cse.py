from src.connectors.google_cse import GoogleCSEConnector, QuotaTracker
from src.models import ApiUsage


def test_quota_tracker_counts_per_day(db_session):
    q = QuotaTracker(db_session, service="google_cse", daily_limit=3, today="2026-09-19")
    assert q.remaining() == 3
    q.consume(2)
    assert q.remaining() == 1
    assert db_session.query(ApiUsage).one().count == 2


def test_cse_connector_builds_site_queries_and_respects_quota(db_session, monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["q"])

        class R:
            def raise_for_status(self): pass
            def json(self):
                return {"items": [{"title": "Post", "link": "https://instagram.com/p/1", "snippet": "Mabel Lara hoy"}]}
        return R()

    import src.connectors.google_cse as m
    monkeypatch.setattr(m.requests, "get", fake_get)

    quota = QuotaTracker(db_session, "google_cse", daily_limit=3, today="2026-09-19")
    c = GoogleCSEConnector(api_key="k", cse_id="cx", sites=["instagram.com", "facebook.com"],
                           quota=quota, pause_seconds=0)
    items = c.fetch(["Mabel Lara", "Carlos Arias"])

    # 2 términos × 2 sitios = 4 consultas, pero la cuota permite 3
    assert len(calls) == 3
    assert calls[0] == '"Mabel Lara" site:instagram.com'
    assert items[0].url == "https://instagram.com/p/1"
    assert items[0].search_term == "Mabel Lara"
    assert items[0].raw["site"] == "instagram.com"
