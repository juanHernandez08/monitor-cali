import datetime as dt
import html
import re
import time
from urllib.parse import quote

import feedparser

from src.connectors.base import RawItem

_TAG = re.compile(r"<[^>]+>")


def build_query_url(term: str) -> str:
    return (
        "https://news.google.com/rss/search?q=" + quote(f'"{term}"')
        + "&hl=es-419&gl=CO&ceid=" + quote("CO:es-419")
    )


def _clean(text: str) -> str:
    return html.unescape(_TAG.sub(" ", text or "")).strip()


class GoogleNewsConnector:
    """Prensa vía Google News RSS: una búsqueda por término, restringida a Colombia."""
    source_name = "google_news"

    def __init__(self, pause_seconds: float = 1.0):
        self.pause_seconds = pause_seconds

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        for term in search_terms:
            parsed = feedparser.parse(build_query_url(term))
            for entry in parsed.entries:
                ext_id = entry.get("id") or entry.get("link")
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)
                published = None
                if getattr(entry, "published_parsed", None):
                    published = dt.datetime(*entry.published_parsed[:6])
                source_title = getattr(getattr(entry, "source", None), "title", None)
                title = _clean(entry.get("title", ""))
                items.append(RawItem(
                    external_id=ext_id,
                    text=f"{title} {_clean(entry.get('summary', ''))}".strip(),
                    url=entry.get("link"),
                    author=source_title,
                    published_at=published,
                    raw={"title": title, "source": source_title},
                    search_term=term,
                ))
            time.sleep(self.pause_seconds)
        return items
