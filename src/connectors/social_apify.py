"""Instagram / Facebook vía Apify — reemplazo de Bright Data.

Bright Data se agotó (0 de 5.000 créditos gratis, 2026-09-25) y "Customer is not active" en su
Marketplace de datasets. Este conector cubre lo mismo con actores oficiales de Apify:
`apify/instagram-scraper` + `apify/instagram-comment-scraper` para Instagram,
`apify/facebook-posts-scraper` + `apify/facebook-comments-scraper` para Facebook.

A diferencia del SDK de Bright Data, estos actores no aceptan "posts ya conocidos, no los traigas
de nuevo": se filtran del lado de acá (`known_post_ids`) después de pagarlos. Para no repetir el
mismo gasto corrida tras corrida, `known_last_dates` estrecha la ventana a "desde el último post
guardado" en vez de pedir siempre los últimos `window_days`.

Campos verificados contra datos reales el 2026-09-25 (cuenta @soycarlosaarias y la página de
Facebook de Clara Luz Roldán).
"""
import datetime as dt
import logging

import requests

from src.connectors.base import RawItem

log = logging.getLogger(__name__)

ENDPOINT = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
IG_POSTS_ACTOR = "apify~instagram-scraper"
IG_COMMENTS_ACTOR = "apify~instagram-comment-scraper"
FB_POSTS_ACTOR = "apify~facebook-posts-scraper"
FB_COMMENTS_ACTOR = "apify~facebook-comments-scraper"


def _parse_date(value) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(dt.timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class SocialApifyConnector:
    source_name = "social_apify"

    def __init__(self, token: str, accounts: list[dict], window_days: int = 60, max_posts: int = 40,
                 max_comments: int = 30, comment_posts: int = 4, known_post_ids: dict[str, list[str]] | None = None,
                 pending_comment_posts: list[dict] | None = None, credits=None,
                 known_last_dates: dict[str, str] | None = None, timeout: int = 180):
        self.token = token
        self.accounts = [a for a in accounts if a.get("platform") in ("instagram", "facebook")]
        self.window_days = window_days
        self.max_posts = max_posts
        self.max_comments = max_comments
        self.comment_posts = comment_posts
        self.known_post_ids = known_post_ids or {}
        self.pending_comment_posts = pending_comment_posts or []
        self.credits = credits
        self.known_last_dates = known_last_dates or {}
        self.timeout = timeout
        self.comments_attempted: set[str] = set()

    def _remaining(self) -> int:
        return self.credits.remaining() if self.credits else 10**9

    def _consume(self, n: int) -> None:
        if self.credits and n:
            self.credits.consume(n)

    def _run(self, actor: str, payload: dict) -> list[dict]:
        r = requests.post(ENDPOINT.format(actor=actor), params={"token": self.token}, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return [x for x in r.json() if isinstance(x, dict)]

    def _since(self, account: dict) -> str:
        last = self.known_last_dates.get(account["url"])
        if last:
            return (dt.date.fromisoformat(last) + dt.timedelta(days=1)).isoformat()
        return (dt.date.today() - dt.timedelta(days=self.window_days)).isoformat()

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        if not self.accounts:
            return items
        candidates_for_comments: list[dict] = list(self.pending_comment_posts)
        for account in self.accounts:
            if self._remaining() <= 0:
                log.warning("Apify: tope mensual alcanzado; se omite %s", account.get("url"))
                break
            try:
                new_items, new_posts = self._fetch_posts(account)
                items.extend(new_items)
                candidates_for_comments.extend(new_posts)
            except Exception:  # una cuenta caída no debe tumbar las demás
                log.exception("Apify: cuenta %s falló", account.get("url"))
        candidates_for_comments.sort(key=lambda p: -_to_int(p.get("num_comments")))
        for post in candidates_for_comments[: self.comment_posts]:
            if self._remaining() <= 0:
                break
            try:
                items.extend(self._fetch_comments(post))
            except Exception:
                log.exception("Apify: comentarios de %s fallaron", post.get("url"))
        return items

    def _fetch_posts(self, account: dict) -> tuple[list[RawItem], list[dict]]:
        platform = account["platform"]
        candidate = account.get("candidate")
        prefix = "ig" if platform == "instagram" else "fb"
        known = {str(x) for x in (self.known_post_ids.get(account["url"]) or [])}
        since = self._since(account)
        if platform == "instagram":
            raw_posts = self._run(IG_POSTS_ACTOR, {"directUrls": [account["url"]], "resultsType": "posts",
                                                     "resultsLimit": self.max_posts, "onlyPostsNewerThan": since})
        else:
            raw_posts = self._run(FB_POSTS_ACTOR, {"startUrls": [{"url": account["url"]}],
                                                     "resultsLimit": self.max_posts, "onlyPostsNewerThan": since})
        self._consume(len(raw_posts))  # Apify cobra lo que devuelve, así ya lo tuviéramos guardado
        items: list[RawItem] = []
        new_posts: list[dict] = []
        for p in raw_posts:
            if platform == "instagram":
                post_id, text, url = p.get("id"), str(p.get("caption") or "").strip(), p.get("url")
                published, author = _parse_date(p.get("timestamp")), p.get("ownerUsername")
                num_comments = _to_int(p.get("commentsCount"))
            else:
                post_id, text, url = p.get("postId"), str(p.get("text") or "").strip(), p.get("url")
                published, author = _parse_date(p.get("time")), (p.get("user") or {}).get("name")
                num_comments = _to_int(p.get("comments"))
            if not post_id or str(post_id) in known:
                continue
            items.append(RawItem(
                external_id=f"{prefix}:post:{post_id}", text=text, url=url, author=author, published_at=published,
                raw={"kind": "post", "platform": platform, "account": account["url"], "num_comments": num_comments, "record": p},
                search_term=candidate,
            ))
            if url and num_comments > 0:
                new_posts.append({"url": url, "platform": platform, "candidate": candidate, "account": account["url"],
                                  "title": text[:120], "num_comments": num_comments})
        return items, new_posts

    def _fetch_comments(self, post: dict) -> list[RawItem]:
        platform, post_url, candidate = post["platform"], post["url"], post.get("candidate")
        prefix = "ig" if platform == "instagram" else "fb"
        self.comments_attempted.add(post_url)
        if platform == "instagram":
            raw_comments = self._run(IG_COMMENTS_ACTOR, {"directUrls": [post_url], "resultsLimit": self.max_comments})
        else:
            raw_comments = self._run(FB_COMMENTS_ACTOR, {"startUrls": [{"url": post_url}], "resultsLimit": self.max_comments})
        self._consume(len(raw_comments))
        items: list[RawItem] = []
        for c in raw_comments[: self.max_comments]:
            if platform == "instagram":
                cid, text, author, published = c.get("id"), str(c.get("text") or "").strip(), c.get("ownerUsername"), _parse_date(c.get("timestamp"))
            else:
                cid = c.get("commentId") or c.get("id")
                text, author, published = str(c.get("text") or "").strip(), c.get("profileName"), _parse_date(c.get("date"))
            if not cid or not text:
                continue
            items.append(RawItem(
                external_id=f"{prefix}:comment:{cid}", text=text, url=post_url, author=author, published_at=published,
                raw={"kind": "comment", "platform": platform, "account": post.get("account"),
                     "account_candidate": candidate, "post_title": post.get("title", ""), "record": c},
                search_term=candidate,
            ))
        return items
