import datetime as dt
import html
import re
import time
from urllib.parse import quote

import feedparser

from src.connectors.base import RawItem

_TAG = re.compile(r"<[^>]+>")


def build_query_url(term: str, window: str | None = None, context: str = "Cali") -> str:
    """Búsqueda de Google News acotada a Colombia con contexto ("Cali").

    `when:Nd` se comporta mal con frases entre comillas (devuelve 1 resultado donde sin
    ventana devuelve 48), así que por defecto no se usa; el dashboard filtra por fecha.
    """
    query = f'"{term}" {context}' + (f" when:{window}" if window else "")
    return (
        "https://news.google.com/rss/search?q=" + quote(query)
        + "&hl=es-419&gl=CO&ceid=" + quote("CO:es-419")
    )


def _clean(text: str) -> str:
    return html.unescape(_TAG.sub(" ", text or "")).strip()


class GoogleNewsConnector:
    """Prensa vía Google News RSS: una búsqueda por término, restringida a Colombia."""
    source_name = "google_news"

    # Google News ordena por relevancia (hasta 100, cubre años) y `when:` devuelve máximo 10
    # recientes. Combinar ambas trae lo importante y lo nuevo; se deduplica por id.
    DEFAULT_WINDOWS: tuple[str | None, ...] = (None, "60d", "7d")

    def __init__(self, pause_seconds: float = 1.0, windows: tuple[str | None, ...] = DEFAULT_WINDOWS,
                 context: str = "Cali"):
        self.pause_seconds = pause_seconds
        self.windows = windows
        self.context = context

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        for term in search_terms:
            entries = []
            for window in self.windows:
                entries.extend(feedparser.parse(build_query_url(term, window, self.context)).entries)
                time.sleep(self.pause_seconds)
            for entry in entries:
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
        return items
