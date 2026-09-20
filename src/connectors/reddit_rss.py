import datetime as dt
import html
import re
import time
import urllib.request
from urllib.parse import quote

import feedparser

from src.connectors.base import RawItem

# Reddit devuelve 403 a user-agents genéricos; uno de navegador funciona.
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) monitor-cali/0.1"
_TAG = re.compile(r"<[^>]+>")


def build_search_url(term: str) -> str:
    return "https://www.reddit.com/search.rss?q=" + quote(f'"{term}"') + "&sort=new"


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


class RedditRSSConnector:
    """Búsqueda pública de Reddit vía RSS (sin API key)."""
    source_name = "reddit_rss"

    def __init__(self, pause_seconds: float = 2.0):
        self.pause_seconds = pause_seconds

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        for term in search_terms:
            parsed = feedparser.parse(_download(build_search_url(term)))
            for entry in parsed.entries:
                ext_id = entry.get("id") or entry.get("link")
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)
                published = None
                if getattr(entry, "updated_parsed", None):
                    published = dt.datetime(*entry.updated_parsed[:6])
                body = html.unescape(_TAG.sub(" ", entry.get("summary", "") or "")).strip()
                items.append(RawItem(
                    external_id=ext_id,
                    text=f"{entry.get('title', '')} {body}".strip(),
                    url=entry.get("link"),
                    author=entry.get("author"),
                    published_at=published,
                    raw={"title": entry.get("title")},
                    search_term=term,
                ))
            time.sleep(self.pause_seconds)
        return items
