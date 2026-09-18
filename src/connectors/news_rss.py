import datetime as dt
import feedparser

from src.connectors.base import RawItem


class RSSConnector:
    source_name = "rss"

    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        parsed = feedparser.parse(self.feed_url)
        items = []
        for entry in parsed.entries:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            if not any(term.lower() in text.lower() for term in search_terms):
                continue
            published = None
            if getattr(entry, "published_parsed", None):
                published = dt.datetime(*entry.published_parsed[:6])
            items.append(RawItem(
                external_id=entry.get("id", entry.link),
                text=text.strip(),
                url=entry.get("link"),
                author=entry.get("author"),
                published_at=published,
                raw={"title": entry.get("title"), "summary": entry.get("summary")},
            ))
        return items
