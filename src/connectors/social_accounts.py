"""Instagram / Facebook por cuenta conocida (Bright Data Web Scraper API).

Lee los posts recientes de cuentas específicas (candidatos, medios) y los comentarios de
esos posts. Un post o comentario en la cuenta de un candidato se atribuye a ese candidato
(`search_term`); en cuentas de medios solo cuenta si el texto nombra a alguno.

Créditos: 1 por registro. Con 10 cuentas × (5 posts + 3 posts × 25 comentarios) ≈ 800 por
corrida → el plan gratuito (5.000/mes) aguanta ~6 corridas al mes; ver scheduler.

Los nombres de campo de Bright Data no están documentados en el SDK: `_pick` prueba varias
claves plausibles. Con la primera corrida real, revisar `raw` de un post y un comentario.
"""
import asyncio
import datetime as dt
import logging

from brightdata import BrightDataClient

from src.connectors.base import RawItem

log = logging.getLogger(__name__)

ACCOUNT_KEYS = {
    "text": ("description", "caption", "content", "post_text", "text"),
    "comment_text": ("comment", "comment_text", "text", "content"),
    "post_id": ("post_id", "id", "shortcode", "pk"),
    "comment_id": ("comment_id", "id"),
    "url": ("url", "post_url", "link", "permalink"),
    "author": ("user_posted", "username", "user_name", "profile_name", "author", "page_name"),
    "comment_author": ("comment_user", "commenter_username", "user_name", "username", "author"),
    "date": ("date_posted", "timestamp", "created_at", "date", "post_date"),
    "comment_date": ("comment_date", "date_created", "timestamp", "created_at", "date"),
    "num_comments": ("num_comments", "comments_count", "comment_count", "comments"),
}


def _pick(record: dict, key: str):
    for k in ACCOUNT_KEYS[key]:
        v = record.get(k)
        if v not in (None, ""):
            return v
    return None


def _parse_date(value) -> dt.datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return dt.datetime.utcfromtimestamp(value)
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


class SocialAccountConnector:
    source_name = "social_accounts"

    def __init__(self, api_token: str, accounts: list[dict], max_posts: int = 5,
                 max_comments: int = 25, comment_posts: int = 3):
        self.api_token = api_token
        self.accounts = accounts  # [{"platform": "instagram"|"facebook", "url": ..., "candidate": name|None}]
        self.max_posts = max_posts
        self.max_comments = max_comments
        self.comment_posts = comment_posts  # de cuántos posts (los más comentados) se piden comentarios

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        return asyncio.run(self._fetch_async())

    async def _fetch_async(self) -> list[RawItem]:
        items: list[RawItem] = []
        async with BrightDataClient(token=self.api_token) as client:
            for account in self.accounts:
                try:
                    items.extend(await self._fetch_account(client, account))
                except Exception:  # una cuenta caída no debe tumbar las demás
                    log.exception("cuenta %s falló", account.get("url"))
        return items

    async def _fetch_account(self, client, account: dict) -> list[RawItem]:
        platform = account["platform"]
        candidate = account.get("candidate")
        prefix = "ig" if platform == "instagram" else "fb"
        if platform == "instagram":
            posts_fn, comments_fn = client.scrape.instagram.posts, client.scrape.instagram.comments
        elif platform == "facebook":
            posts_fn, comments_fn = client.scrape.facebook.posts_by_profile, client.scrape.facebook.comments
        else:
            raise ValueError(f"plataforma no soportada: {platform}")

        result = await posts_fn(url=account["url"], num_of_posts=self.max_posts)
        posts = [p for p in (result.data or []) if isinstance(p, dict)]
        items: list[RawItem] = []
        for post in posts:
            post_id = _pick(post, "post_id") or _pick(post, "url")
            if not post_id:
                continue
            items.append(RawItem(
                external_id=f"{prefix}:post:{post_id}",
                text=str(_pick(post, "text") or "").strip(),
                url=_pick(post, "url"),
                author=_pick(post, "author"),
                published_at=_parse_date(_pick(post, "date")),
                raw={"kind": "post", "platform": platform, "account": account["url"],
                     "num_comments": _pick(post, "num_comments"), "record": post},
                search_term=candidate,
            ))

        with_comments = sorted(
            (p for p in posts if _pick(p, "url") and (_pick(p, "num_comments") or 0)),
            key=lambda p: -(int(_pick(p, "num_comments") or 0)),
        )[: self.comment_posts]
        for post in with_comments:
            post_url = _pick(post, "url")
            result = await comments_fn(url=post_url, num_of_comments=self.max_comments)
            post_title = str(_pick(post, "text") or "")[:120]
            for c in (result.data or []):
                if not isinstance(c, dict):
                    continue
                cid = _pick(c, "comment_id")
                text = str(_pick(c, "comment_text") or "").strip()
                if not cid or not text:
                    continue
                items.append(RawItem(
                    external_id=f"{prefix}:comment:{cid}",
                    text=text,
                    url=post_url,
                    author=_pick(c, "comment_author"),
                    published_at=_parse_date(_pick(c, "comment_date")),
                    raw={"kind": "comment", "platform": platform, "account": account["url"],
                         "post_title": post_title, "record": c},  # contexto para el clasificador
                    search_term=candidate,
                ))
        return items
