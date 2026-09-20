from types import SimpleNamespace
from src.connectors.serp import SerpConnector


class FakeSyncClient:
    def __init__(self, results):
        self._results = results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def search(self):
        return SimpleNamespace(google=lambda query: SimpleNamespace(data=self._results))


def test_serp_connector_restricts_by_site(monkeypatch):
    fake_results = [{
        "title": "Ana Pérez - Instagram", "snippet": "Publicación sobre seguridad",
        "link": "https://instagram.com/p/xyz",
    }]

    import src.connectors.serp as serp_module
    monkeypatch.setattr(
        serp_module, "SyncBrightDataClient", lambda token, auto_create_zones: FakeSyncClient(fake_results),
    )

    connector = SerpConnector(api_token="fake-token", site="instagram.com")
    items = connector.fetch(search_terms=["Ana Pérez"])

    assert len(items) == 1
    assert items[0].url == "https://instagram.com/p/xyz"
