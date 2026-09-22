"""X (Twitter) vía Apify — actor apidojo/tweet-scraper ("Tweet Scraper V2").

Trae (a) los posts de cada cuenta configurada y (b) las respuestas que la gente le escribe a esa
cuenta (`inReplyTo`), que es donde está la opinión ciudadana. Precio: ~USD 0,40 por 1.000 tuits;
el plan gratuito de Apify da USD 5/mes (~12.000 tuits). `credits` lleva el conteo mensual.

Verificado contra la documentación del actor el 2026-09-22 (campos: id, url, text, createdAt,
author.userName, likeCount, replyCount, retweetCount, isReply, inReplyToId, conversationId).
"""
import datetime as dt
import logging

import requests

from src.connectors.base import RawItem

log = logging.getLogger(__name__)

ACTOR = "apidojo~tweet-scraper"
ENDPOINT = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"


def _handle(url: str) -> str:
    return url.rstrip("/").split("/")[-1].lstrip("@")


def _parse_date(value) -> dt.datetime | None:
    if not value:
        return None
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return dt.datetime.strptime(str(value), fmt).astimezone(dt.timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(dt.timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


class XApifyConnector:
    source_name = "x_apify"

    def __init__(self, token: str, accounts: list[dict], window_days: int = 60, max_posts: int = 100,
                 max_replies: int = 200, known_last_dates: dict[str, str] | None = None,
                 known_post_texts: dict[str, str] | None = None, credits=None, timeout: int = 300):
        self.token = token
        self.accounts = [a for a in accounts if a.get("platform") == "x"]
        self.window_days = window_days
        self.max_posts = max_posts
        self.max_replies = max_replies
        self.known_last_dates = known_last_dates or {}   # account url -> YYYY-MM-DD del último item guardado
        self.known_post_texts = known_post_texts or {}   # tweet id -> texto (para dar contexto a las respuestas)
        self.credits = credits
        self.timeout = timeout

    def _remaining(self) -> int:
        return self.credits.remaining() if self.credits else 10**9

    def _consume(self, n: int) -> None:
        if self.credits and n:
            self.credits.consume(n)

    def _run(self, payload: dict) -> list[dict]:
        r = requests.post(ENDPOINT, params={"token": self.token}, json=payload, timeout=self.timeout)
        r.raise_for_status()
        items = [x for x in r.json() if isinstance(x, dict) and x.get("id")]
        self._consume(len(items))
        return items

    def _start(self, account: dict) -> str:
        last = self.known_last_dates.get(account["url"])
        if last:
            return (dt.date.fromisoformat(last) + dt.timedelta(days=1)).isoformat()
        return (dt.date.today() - dt.timedelta(days=self.window_days)).isoformat()

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        if not self.accounts or self._remaining() <= 0:
            return items
        end = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        by_handle = {_handle(a["url"]).lower(): a for a in self.accounts}

        # (a) posts de todas las cuentas en una sola corrida
        start = min(self._start(a) for a in self.accounts)
        try:
            for t in self._run({"twitterHandles": list(by_handle.keys()), "maxItems": self.max_posts * len(self.accounts),
                                "start": start, "end": end, "sort": "Latest"}):
                account = by_handle.get(str((t.get("author") or {}).get("userName") or "").lower())
                if account is None or t.get("isReply"):
                    continue
                items.append(self._item(t, account, kind="post"))
        except Exception:
            log.exception("Apify X: posts fallaron")

        # (b) respuestas de la gente a cada cuenta
        for handle, account in by_handle.items():
            if self._remaining() <= 0:
                break
            try:
                for t in self._run({"inReplyTo": handle, "maxItems": self.max_replies, "start": self._start(account),
                                    "end": end, "sort": "Latest"}):
                    if str((t.get("author") or {}).get("userName") or "").lower() == handle:
                        continue  # la cuenta respondiéndose a sí misma no es opinión ciudadana
                    items.append(self._item(t, account, kind="comment"))
            except Exception:
                log.exception("Apify X: respuestas a @%s fallaron", handle)
        return items

    def _item(self, t: dict, account: dict, kind: str) -> RawItem:
        author = (t.get("author") or {}).get("userName")
        tid = str(t["id"])
        handle = _handle(account["url"])
        raw = {"kind": kind, "platform": "x", "account": account["url"], "record": t,
               "num_comments": t.get("replyCount"), "likes": t.get("likeCount"), "reposts": t.get("retweetCount")}
        if kind == "post":
            return RawItem(external_id=f"x:post:{tid}", text=str(t.get("text") or "").strip(), url=t.get("url") or t.get("twitterUrl"),
                           author=author, published_at=_parse_date(t.get("createdAt")), raw=raw, search_term=account.get("candidate"))
        parent_id = str(t.get("inReplyToId") or t.get("conversationId") or "")
        parent_url = f"https://x.com/{handle}/status/{parent_id}" if parent_id else (t.get("url") or t.get("twitterUrl"))
        raw.update({"account_candidate": account.get("candidate"), "parent_id": parent_id,
                    "post_title": self.known_post_texts.get(parent_id, f"publicación de @{handle}")[:120],
                    "reply_url": t.get("url") or t.get("twitterUrl")})
        return RawItem(external_id=f"x:reply:{tid}", text=str(t.get("text") or "").strip(), url=parent_url,
                       author=author, published_at=_parse_date(t.get("createdAt")), raw=raw, search_term=account.get("candidate"))
