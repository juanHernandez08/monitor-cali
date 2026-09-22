"""Instagram / Facebook por cuenta conocida (Bright Data Web Scraper API).

Lee TODOS los posts de los últimos `window_days` de cada cuenta (candidatos, medios) y los
comentarios de esos posts, una sola vez por post. Un post o comentario en la cuenta de un
candidato se atribuye a ese candidato (`search_term`); en cuentas de medios solo cuenta si el
texto nombra a alguno.

Créditos (1 por registro, 5.000/mes gratis): los posts ya guardados se excluden de la consulta
(`posts_to_not_include`) y los comentarios se piden solo para posts que aún no los tienen
(`pending_comment_posts`, que el scheduler saca de la base). `credits` frena al llegar al tope.

Los nombres de campo de Bright Data se verificaron con datos reales el 2026-09-20 (`_pick`
tolera variantes por si cambian).
"""
import asyncio
import datetime as dt
import logging
import time

import requests
from brightdata import BrightDataClient

from src.connectors.base import RawItem

log = logging.getLogger(__name__)

# X no está en el SDK de Python; se usa la API REST del Web Scraper con el dataset
# "X (formerly Twitter) - Posts" (verificado el 2026-09-22: discover_by=profile_url + fechas).
BRIGHTDATA_API = "https://api.brightdata.com/datasets/v3"
X_POSTS_DATASET = "gd_lwxkxvnf1cynvib9co"

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


def _to_int(value) -> int:
    try:
        return int(str(value).replace(",", "").replace(".", ""))
    except (TypeError, ValueError):
        return 0


class SocialAccountConnector:
    source_name = "social_accounts"

    def __init__(self, api_token: str, accounts: list[dict], window_days: int = 60, max_posts: int = 40,
                 max_comments: int = 60, comment_posts: int = 10, known_post_ids: dict[str, list[str]] | None = None,
                 pending_comment_posts: list[dict] | None = None, credits=None,
                 known_last_dates: dict[str, str] | None = None):
        self.api_token = api_token
        self.accounts = accounts  # [{"platform": "instagram"|"facebook", "url": ..., "candidate": name|None}]
        self.window_days = window_days
        self.max_posts = max_posts
        self.max_comments = max_comments
        self.comment_posts = comment_posts  # máximo de posts por corrida a los que se piden comentarios
        self.known_post_ids = known_post_ids or {}  # account url -> ids ya guardados (no se vuelven a pagar)
        # posts ya guardados sin comentarios: [{"url", "platform", "candidate", "account", "title", "num_comments"}]
        self.pending_comment_posts = pending_comment_posts or []
        self.credits = credits  # QuotaTracker mensual; None = sin límite
        self.known_last_dates = known_last_dates or {}  # account url -> fecha del último post guardado (X)
        self.comments_attempted: set[str] = set()  # URLs de posts cuyos comentarios se pidieron en esta corrida

    def _remaining(self) -> int:
        return self.credits.remaining() if self.credits else 10**9

    def _consume(self, n: int) -> None:
        if self.credits and n:
            self.credits.consume(n)

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        return asyncio.run(self._fetch_async())

    async def _fetch_async(self) -> list[RawItem]:
        items: list[RawItem] = []
        candidates_for_comments: list[dict] = list(self.pending_comment_posts)
        x_accounts = [a for a in self.accounts if a["platform"] == "x"]
        if x_accounts and self._remaining() > 0:
            try:
                items.extend(self._fetch_x_posts(x_accounts))
            except Exception:
                log.exception("X falló")
        async with BrightDataClient(token=self.api_token, auto_create_zones=False) as client:
            for account in [a for a in self.accounts if a["platform"] != "x"]:
                if self._remaining() <= 0:
                    log.warning("Bright Data: tope mensual de créditos alcanzado; se omite %s", account.get("url"))
                    break
                try:
                    new_items, new_posts = await self._fetch_posts(client, account)
                    items.extend(new_items)
                    candidates_for_comments.extend(new_posts)
                except Exception:  # una cuenta caída no debe tumbar las demás
                    log.exception("cuenta %s falló", account.get("url"))
            # Comentarios: primero los posts más comentados, máximo `comment_posts` por corrida.
            candidates_for_comments.sort(key=lambda p: -_to_int(p.get("num_comments")))
            for post in candidates_for_comments[: self.comment_posts]:
                if self._remaining() <= 0:
                    break
                try:
                    items.extend(await self._fetch_comments(client, post))
                except Exception:  # timeout de Bright Data: se conservan los demás
                    log.exception("comentarios de %s fallaron", post.get("url"))
        return items

    async def _fetch_posts(self, client, account: dict) -> tuple[list[RawItem], list[dict]]:
        platform = account["platform"]
        candidate = account.get("candidate")
        prefix = "ig" if platform == "instagram" else "fb"
        end = dt.date.today()
        start = end - dt.timedelta(days=self.window_days)
        known = self.known_post_ids.get(account["url"]) or []
        kwargs = dict(url=account["url"], num_of_posts=self.max_posts, start_date=start.isoformat(),
                      end_date=end.isoformat(), posts_to_not_include=known or None)
        # Firmas verificadas contra brightdata-sdk 2.5.
        if platform == "instagram":
            result = await client.search.instagram.posts(**kwargs)
        elif platform == "facebook":
            result = await client.scrape.facebook.posts_by_profile(**kwargs)
        else:
            raise ValueError(f"plataforma no soportada: {platform}")

        posts = [p for p in (result.data or []) if isinstance(p, dict)]
        self._consume(len(posts))
        items: list[RawItem] = []
        new_posts: list[dict] = []
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
            if _pick(post, "url") and _to_int(_pick(post, "num_comments")) > 0:
                new_posts.append({"url": _pick(post, "url"), "platform": platform, "candidate": candidate,
                                  "account": account["url"], "title": str(_pick(post, "text") or "")[:120],
                                  "num_comments": _to_int(_pick(post, "num_comments"))})
        return items, new_posts

    async def _fetch_comments(self, client, post: dict) -> list[RawItem]:
        platform, post_url, candidate = post["platform"], post["url"], post.get("candidate")
        prefix = "ig" if platform == "instagram" else "fb"
        self.comments_attempted.add(post_url)
        if platform == "instagram":
            result = await client.scrape.instagram.comments(url=post_url)
        else:
            result = await client.scrape.facebook.comments(url=post_url, num_of_comments=self.max_comments)
        records = [c for c in (result.data or []) if isinstance(c, dict)]
        self._consume(len(records))
        items: list[RawItem] = []
        for c in records[: self.max_comments]:  # Instagram no acepta límite en la API; se recorta aquí
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
                raw={"kind": "comment", "platform": platform, "account": post.get("account"),
                     "account_candidate": candidate,  # comentario en un post del propio candidato
                     "post_title": post.get("title", ""), "record": c},
                search_term=candidate,
            ))
        return items

    # ---------- X (REST) ----------

    def _fetch_x_posts(self, accounts: list[dict]) -> list[RawItem]:
        """Posts de varias cuentas de X en una sola consulta (hasta 20 perfiles por lote)."""
        end = dt.date.today()
        default_start = end - dt.timedelta(days=self.window_days)
        inputs = []
        for a in accounts:
            last = self.known_last_dates.get(a["url"])
            start = (dt.date.fromisoformat(last) + dt.timedelta(days=1)) if last else default_start
            if start > end:
                continue  # ya está al día
            inputs.append({"url": a["url"], "start_date": start.isoformat(), "end_date": end.isoformat()})
        if not inputs:
            return []
        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}
        by_url = {a["url"].rstrip("/").lower(): a for a in accounts}
        items: list[RawItem] = []
        for i in range(0, len(inputs), 20):
            batch = inputs[i:i + 20]
            r = requests.post(f"{BRIGHTDATA_API}/trigger", headers=headers, timeout=60,
                              params={"dataset_id": X_POSTS_DATASET, "type": "discover_new",
                                      "discover_by": "profile_url", "include_errors": "true"}, json=batch)
            r.raise_for_status()
            snapshot = r.json()["snapshot_id"]
            progress = {}
            for _ in range(90):  # hasta 15 min
                time.sleep(10)
                progress = requests.get(f"{BRIGHTDATA_API}/progress/{snapshot}", headers=headers, timeout=30).json()
                if progress.get("status") in ("ready", "failed"):
                    break
            if progress.get("status") != "ready":
                log.warning("X: snapshot %s terminó en %s", snapshot, progress.get("status"))
                continue
            d = requests.get(f"{BRIGHTDATA_API}/snapshot/{snapshot}", headers=headers,
                             params={"format": "json"}, timeout=120)
            d.raise_for_status()
            records = [x for x in d.json() if isinstance(x, dict) and x.get("id")]
            self._consume(len(records))
            for rec in records:
                input_url = str(((rec.get("input") or {}).get("url")) or ((rec.get("discovery_input") or {}).get("url")) or "")
                account = by_url.get(input_url.rstrip("/").lower())
                if account is None:  # asociar por handle si la API no devolvió el input
                    handle = str(rec.get("user_posted") or "").lower()
                    account = next((a for a in accounts if a["url"].rstrip("/").lower().endswith("/" + handle)), None)
                if account is None:
                    continue
                items.append(RawItem(
                    external_id=f"x:post:{rec['id']}",
                    text=str(rec.get("description") or "").strip(),
                    url=rec.get("url"),
                    author=rec.get("user_posted"),
                    published_at=_parse_date(rec.get("date_posted")),
                    raw={"kind": "post", "platform": "x", "account": account["url"],
                         "num_comments": rec.get("replies"), "record": rec},
                    search_term=account.get("candidate"),
                ))
        return items
