import datetime as dt
import time

import requests

from src.connectors.base import RawItem
from src.models import ApiUsage

CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


class QuotaTracker:
    """Contador diario persistido en ApiUsage; free tier de CSE = 100 consultas/día."""

    def __init__(self, session, service: str, daily_limit: int, today: str | None = None):
        self.session = session
        self.service = service
        self.daily_limit = daily_limit
        self.today = today or dt.datetime.utcnow().strftime("%Y-%m-%d")

    def _row(self) -> ApiUsage:
        row = self.session.query(ApiUsage).filter_by(service=self.service, day=self.today).first()
        if row is None:
            row = ApiUsage(service=self.service, day=self.today, count=0)
            self.session.add(row)
            self.session.flush()
        return row

    def remaining(self) -> int:
        return max(0, self.daily_limit - self._row().count)

    def consume(self, n: int = 1) -> None:
        row = self._row()
        row.count += n
        self.session.commit()


class GoogleCSEConnector:
    """Busca posts indexados de IG/FB/X con el índice de Google (Custom Search JSON API)."""
    source_name = "google_cse"

    def __init__(self, api_key: str, cse_id: str, sites: list[str], quota: QuotaTracker,
                 pause_seconds: float = 1.0, num: int = 10):
        self.api_key = api_key
        self.cse_id = cse_id
        self.sites = sites
        self.quota = quota
        self.pause_seconds = pause_seconds
        self.num = num

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        for term in search_terms:
            for site in self.sites:
                if self.quota.remaining() <= 0:
                    return items
                query = f'"{term}" site:{site}'
                resp = requests.get(CSE_ENDPOINT, params={
                    "key": self.api_key, "cx": self.cse_id, "q": query,
                    "num": self.num, "gl": "co", "hl": "es",
                }, timeout=15)
                self.quota.consume(1)
                resp.raise_for_status()
                for entry in resp.json().get("items", []):
                    link = entry.get("link")
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    items.append(RawItem(
                        external_id=link,
                        text=f"{entry.get('title', '')} {entry.get('snippet', '')}".strip(),
                        url=link,
                        raw={"site": site, "title": entry.get("title")},
                        search_term=term,
                    ))
                time.sleep(self.pause_seconds)
        return items
