import datetime as dt
import time

import requests

from src.connectors.base import RawItem

API = "https://www.googleapis.com/youtube/v3"


def _parse(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    try:
        return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


class YouTubeConnector:
    """YouTube Data API v3: search.list (100 unidades) por término + commentThreads.list (1) por video."""
    source_name = "youtube"

    # Cuota: cada search.list cuesta 100 unidades (10.000/día gratis). 30 términos × 100 = 3.000
    # por corrida → máximo 2-3 corridas al día (ver scheduler). Los videos populares (relevance)
    # concentran los comentarios; un comentario reciente en un video viejo sigue siendo mención.
    def __init__(self, api_key: str, max_videos: int = 8, max_comments: int = 50,
                 pause_seconds: float = 0.5, published_after_days: int = 180, context: str = "Cali"):
        self.api_key = api_key
        self.context = context  # evita homónimos (p. ej. "Carlos Arias" → futbolistas Arias)
        self.max_videos = max_videos
        self.max_comments = max_comments
        self.pause_seconds = pause_seconds
        self.published_after_days = published_after_days

    def _get(self, path: str, **params):
        params["key"] = self.api_key
        resp = requests.get(f"{API}/{path}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        after = (dt.datetime.utcnow() - dt.timedelta(days=self.published_after_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for term in search_terms:
            query = f'"{term}" {self.context}'.strip()
            data = self._get("search", part="snippet", q=query, type="video", regionCode="CO",
                             relevanceLanguage="es", order="relevance", maxResults=self.max_videos,
                             publishedAfter=after)
            for v in data.get("items", []):
                vid = v.get("id", {}).get("videoId")
                if not vid or f"yt:video:{vid}" in seen:
                    continue
                seen.add(f"yt:video:{vid}")
                s = v["snippet"]
                # La búsqueda de YouTube es laxa: solo atribuimos el video (y sus comentarios) al
                # candidato si el título o la descripción lo nombran; si no, cuenta únicamente lo
                # que mencione al candidato por su propio texto.
                about = f"{s.get('title', '')} {s.get('description', '')}".lower()
                hint = term if term.lower() in about else None
                items.append(RawItem(
                    external_id=f"yt:video:{vid}",
                    text=f"{s.get('title', '')} {s.get('description', '')}".strip(),
                    url=f"https://www.youtube.com/watch?v={vid}",
                    author=s.get("channelTitle"),
                    published_at=_parse(s.get("publishedAt")),
                    raw={"kind": "video", "title": s.get("title")},
                    search_term=hint,
                ))
                try:
                    comments = self._get("commentThreads", part="snippet", videoId=vid,
                                         maxResults=self.max_comments, order="relevance", textFormat="plainText")
                except requests.HTTPError:
                    comments = {"items": []}  # comentarios deshabilitados → 403
                for c in comments.get("items", []):
                    cid = c.get("id")
                    cs = c.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    if not cid or f"yt:comment:{cid}" in seen or not cs.get("textDisplay"):
                        continue
                    seen.add(f"yt:comment:{cid}")
                    items.append(RawItem(
                        external_id=f"yt:comment:{cid}",
                        text=cs["textDisplay"].strip(),
                        url=f"https://www.youtube.com/watch?v={vid}&lc={cid}",
                        author=cs.get("authorDisplayName"),
                        published_at=_parse(cs.get("publishedAt")),
                        raw={"kind": "comment", "video_id": vid, "video_title": s.get("title"),
                             "video_about_candidate": hint is not None},
                        search_term=hint,
                    ))
                time.sleep(self.pause_seconds)
        return items
