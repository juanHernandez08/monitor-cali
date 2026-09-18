import asyncio
import datetime as dt

from brightdata import BrightDataClient
from src.connectors.base import RawItem


class RedditConnector:
    source_name = "reddit"

    def __init__(self, api_token: str, sort_by: str = "new"):
        self.api_token = api_token
        self.sort_by = sort_by

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        return asyncio.run(self._fetch_async(search_terms))

    async def _fetch_async(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        async with BrightDataClient(token=self.api_token) as client:
            for term in search_terms:
                result = await client.scrape.reddit.posts_by_keyword(
                    keyword=term, sort_by=self.sort_by,
                )
                # Nombres de campo asumidos — verificar con result.data[0] real y ajustar.
                for post in result.data:
                    items.append(RawItem(
                        external_id=post["id"],
                        text=f"{post.get('title', '')} {post.get('body', '')}".strip(),
                        url=post.get("url"),
                        author=post.get("author"),
                        published_at=_parse_date(post.get("created_at")),
                        raw=post,
                    ))
        return items


def _parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None
