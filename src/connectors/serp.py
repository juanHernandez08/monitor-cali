from brightdata import SyncBrightDataClient
from src.connectors.base import RawItem


class SerpConnector:
    """Busca menciones indexadas en Google, opcionalmente restringidas a un dominio."""
    source_name = "serp"

    def __init__(self, api_token: str, site: str | None = None):
        self.api_token = api_token
        self.site = site

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        with SyncBrightDataClient(token=self.api_token) as client:
            for term in search_terms:
                query = f'"{term}"' + (f" site:{self.site}" if self.site else "")
                result = client.search.google(query=query)
                # Nombres de campo asumidos — verificar con result.data[0] real y ajustar.
                for entry in result.data:
                    link = entry.get("link") or entry.get("url")
                    items.append(RawItem(
                        external_id=link,
                        text=f"{entry.get('title', '')} {entry.get('snippet', '')}".strip(),
                        url=link,
                        raw=entry,
                    ))
        return items
