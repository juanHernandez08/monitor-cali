import datetime as dt
import html
import logging
import re
import time
import urllib.error
import urllib.request
from urllib.parse import quote

import feedparser

from src.connectors.base import RawItem

# Reddit devuelve 403 a user-agents genéricos; uno de navegador funciona.
log = logging.getLogger(__name__)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) monitor-cali/0.1"
_TAG = re.compile(r"<[^>]+>")


def build_search_url(terms: str | list[str]) -> str:
    """Reddit acepta OR entre términos: una consulta por lote reduce el rate limit (429)."""
    if isinstance(terms, str):
        terms = [terms]
    query = " OR ".join(f'"{t}"' for t in terms)
    return "https://www.reddit.com/search.rss?q=" + quote(query) + "&sort=new"


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


class RedditRSSConnector:
    """Búsqueda pública de Reddit vía RSS (sin API key)."""
    source_name = "reddit_rss"

    def __init__(self, pause_seconds: float = 4.0, batch_size: int = 5):
        self.pause_seconds = pause_seconds
        self.batch_size = batch_size

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        batches = [search_terms[i:i + self.batch_size] for i in range(0, len(search_terms), self.batch_size)]
        for batch in batches:
            try:
                parsed = feedparser.parse(_download(build_search_url(batch)))
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    log.warning("Reddit 429: se detiene este ciclo, se reintenta en el siguiente")
                    break
                raise
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
                    search_term=None,  # atribución por texto (el post contiene el nombre)
                ))
            time.sleep(self.pause_seconds)
        return items
