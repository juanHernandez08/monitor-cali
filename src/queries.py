"""Consultas de lectura para el dashboard. Devuelven dicts listos para JSON."""
import datetime as dt
from collections import Counter, defaultdict

from sqlalchemy import func

from src import config
from src.urlnorm import normalize_url
from src.models import (
    ApiUsage, Candidate, Mention, Run, SentimentLabel, SentimentScore, Source, SourceType,
)

CARLOS = "Carlos Arias"
META_TOPICS = ("mención tangencial", "mencion tangencial", "homónimo", "homonimo")  # etiquetas de control, no temas
BOGOTA = dt.timezone(dt.timedelta(hours=-5))


def _since(days: int) -> dt.datetime:
    return dt.datetime.utcnow() - dt.timedelta(days=days)


# Fecha efectiva de una mención: publicación si la fuente la da, si no captura.
WHEN = func.coalesce(Mention.published_at, Mention.fetched_at)


def _when(m: Mention) -> dt.datetime:
    return m.published_at or m.fetched_at


def _local_day(ts: dt.datetime) -> str:
    return ts.replace(tzinfo=dt.timezone.utc).astimezone(BOGOTA).strftime("%Y-%m-%d")


def _avatars(session) -> dict[str, str]:
    """Foto de perfil por candidato, tomada del último post de su cuenta de Instagram/Facebook."""
    accounts = {a["url"]: a["candidate"] for a in config.SOCIAL_ACCOUNTS if a.get("candidate")}
    avatars: dict[str, str] = {}
    posts = (session.query(Mention).join(Source).filter(Source.type == SourceType.SOCIAL)
             .order_by(Mention.id.desc()).all())
    for m in posts:
        raw = m.raw or {}
        cand = accounts.get(raw.get("account"))
        pic = (raw.get("record") or {}).get("profile_image_link")
        if raw.get("kind") == "post" and cand and pic and cand not in avatars:
            avatars[cand] = pic
    return avatars


def summary(session, days: int = 7) -> list[dict]:
    since = _since(days)
    prev_since = since - dt.timedelta(days=days)
    avatars = _avatars(session)
    rows = []
    for c in session.query(Candidate).filter_by(active=True).all():
        q = session.query(Mention).filter(Mention.candidate_id == c.id, Mention.relevant.is_(True))
        current = q.filter(WHEN >= since).all()
        previous = q.filter(WHEN >= prev_since, WHEN < since).count()
        counts = Counter(m.sentiment.label for m in current if m.sentiment)
        rows.append({
            "candidate_id": c.id, "name": c.name, "party": c.party, "avatar": avatars.get(c.name),
            "mentions": len(current), "previous": previous,
            "positive": counts.get(SentimentLabel.POSITIVE, 0),
            "negative": counts.get(SentimentLabel.NEGATIVE, 0),
            "neutral": counts.get(SentimentLabel.NEUTRAL, 0),
            "pending": sum(1 for m in current if not m.sentiment),
        })
    rows.sort(key=lambda r: (r["name"] != CARLOS, -r["mentions"]))
    return rows


def timeline(session, days: int = 7) -> dict:
    since = _since(days)
    today = dt.datetime.utcnow()
    labels = [_local_day(today - dt.timedelta(days=i)) for i in range(days - 1, -1, -1)]
    per: dict[str, Counter] = defaultdict(Counter)
    for m in session.query(Mention).filter(WHEN >= since, Mention.relevant.is_(True)).all():
        per[m.candidate.name][_local_day(_when(m))] += 1
    names = [c.name for c in session.query(Candidate).filter_by(active=True).all()]
    names.sort(key=lambda n: n != CARLOS)
    return {
        "labels": labels,
        "series": [{"name": n, "data": [per[n].get(d, 0) for d in labels]} for n in names],
    }


def _mention_dict(m: Mention) -> dict:
    s = m.sentiment
    return {
        "id": m.id, "candidate": m.candidate.name, "candidate_id": m.candidate_id,
        "source": m.source.name, "source_type": m.source.type.value,
        "text": m.text, "url": m.url, "author": m.author,
        "published_at": _when(m).isoformat(),
        "label": s.label.value if s else None, "score": s.score if s else None,
        "topic": s.topic if s else None, "model": s.model if s else None,
    }


def mentions(session, candidate_id: int | None = None, source_type: str | None = None,
             label: str | None = None, days: int = 30, limit: int = 100, offset: int = 0) -> list[dict]:
    q = (session.query(Mention).outerjoin(SentimentScore).join(Source)
         .filter(WHEN >= _since(days), Mention.relevant.is_(True)))
    if candidate_id:
        q = q.filter(Mention.candidate_id == candidate_id)
    if source_type:
        q = q.filter(Source.type == SourceType(source_type))
    if label:
        q = q.filter(SentimentScore.label == SentimentLabel(label))
    rows = q.order_by(WHEN.desc(), Mention.id.desc()).offset(offset).limit(limit).all()
    return [_mention_dict(m) for m in rows]


def alerts(session, candidate_name: str = CARLOS, threshold: float = -0.5,
           days: int = 30, limit: int = 20) -> list[dict]:
    rows = (
        session.query(Mention).join(SentimentScore).join(Candidate)
        .filter(Candidate.name == candidate_name, SentimentScore.score <= threshold,
                WHEN >= _since(days), Mention.relevant.is_(True))
        .order_by(WHEN.desc()).limit(limit).all()
    )
    return [_mention_dict(m) for m in rows]


def topics(session, days: int = 7, limit: int = 10) -> list[dict]:
    topic = func.lower(SentimentScore.topic)
    rows = (
        session.query(topic, func.count(SentimentScore.id))
        .join(Mention)
        .filter(WHEN >= _since(days), SentimentScore.topic != "", Mention.relevant.is_(True))
        .filter(topic.notin_(META_TOPICS))
        .group_by(topic).order_by(func.count(SentimentScore.id).desc())
        .limit(limit).all()
    )
    return [{"topic": t, "count": n} for t, n in rows]


def status(session) -> dict:
    total = session.query(Mention).count()
    scored = session.query(SentimentScore).count()
    discarded = session.query(Mention).filter(Mention.relevant.is_(False)).count()
    unenriched = (session.query(Mention).join(Source)
                  .filter(Source.type.in_((SourceType.GOOGLE_NEWS, SourceType.RSS)), Mention.body.is_(None)).count())
    sources = []
    for s in session.query(Source).order_by(Source.id).all():
        last = session.query(Run).filter_by(source_id=s.id).order_by(Run.started_at.desc()).first()
        sources.append({
            "name": s.name, "type": s.type.value,
            "last_run": last.started_at.isoformat() if last else None,
            "last_new": last.new_mentions if last else None,
            "error": last.error if last else None,
            "total": session.query(Mention).filter_by(source_id=s.id).count(),
        })
    last_run = session.query(func.max(Run.finished_at)).scalar()
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    cse = session.query(ApiUsage).filter_by(service="google_cse", day=today).first()
    return {
        "total_mentions": total, "scored": scored, "pending": total - scored,
        "discarded": discarded, "unenriched": unenriched,
        "last_run": last_run.isoformat() if last_run else None,
        "cse_used_today": cse.count if cse else 0,
        "sources": sources,
    }


# ---------- Feed agrupado por publicación ----------

def _parent_key(m: Mention) -> str | None:
    """Clave que une un comentario con su publicación (o una publicación consigo misma)."""
    raw = m.raw or {}
    kind = raw.get("kind")
    if kind == "comment":
        if raw.get("video_id"):
            return f"yt:video:{raw['video_id']}"
        return f"url:{normalize_url(m.url)}" if m.url else None
    if kind == "video":
        return m.external_id  # yt:video:<id>
    if kind == "post":
        return f"url:{normalize_url(m.url)}" if m.url else m.external_id
    return None


def _thumbnail(m: Mention) -> str | None:
    raw = m.raw or {}
    kind = raw.get("kind")
    if kind == "video":
        return f"https://i.ytimg.com/vi/{m.external_id.split(':')[-1]}/hqdefault.jpg"
    if kind == "comment" and raw.get("video_id"):
        return f"https://i.ytimg.com/vi/{raw['video_id']}/hqdefault.jpg"
    rec = raw.get("record") or {}
    if kind == "post":
        images = rec.get("images") or rec.get("photos") or []
        first = images[0] if isinstance(images, list) and images else None
        if isinstance(first, dict):
            first = first.get("url") or first.get("src")
        return rec.get("thumbnail") or rec.get("post_image") or first
    return raw.get("image")  # notas de prensa: imagen principal si el enriquecimiento la trajo


def _summary_of(comments: list[dict]) -> dict:
    c = Counter(x["label"] for x in comments)
    return {"total": len(comments), "positive": c.get("positive", 0),
            "negative": c.get("negative", 0), "neutral": c.get("neutral", 0)}


def feed(session, candidate_id: int | None = None, source_type: str | None = None,
         label: str | None = None, days: int = 30, limit: int = 100, offset: int = 0) -> list[dict]:
    """Filas = publicaciones (post, video, nota); los comentarios cuelgan de su publicación.

    Los filtros se aplican a las menciones; una publicación aparece si ella o alguno de sus
    comentarios pasa el filtro. Comentarios sin publicación guardada forman una fila sintética
    (kind="comments") con el título del video/post.
    """
    q = (session.query(Mention).outerjoin(SentimentScore).join(Source)
         .filter(WHEN >= _since(days), Mention.relevant.is_(True)))
    if candidate_id:
        q = q.filter(Mention.candidate_id == candidate_id)
    if source_type:
        q = q.filter(Source.type == SourceType(source_type))
    filtered = q.order_by(WHEN.desc(), Mention.id.desc()).limit(3000).all()

    def passes_label(m: Mention) -> bool:
        return not label or (m.sentiment is not None and m.sentiment.label.value == label)

    rows: dict[str, dict] = {}
    order: list[str] = []
    comments_by_parent: dict[str, list[Mention]] = defaultdict(list)
    for m in filtered:
        if (m.raw or {}).get("kind") == "comment":
            key = _parent_key(m) or f"solo:{m.id}"
            comments_by_parent[key].append(m)
        elif passes_label(m):
            key = _parent_key(m) or f"solo:{m.id}"
            raw = m.raw or {}
            row = _mention_dict(m)
            row["kind"] = raw.get("kind") or "news"
            row["thumbnail"] = _thumbnail(m)
            row["comments"], row["comments_summary"] = [], _summary_of([])
            rows[key] = row
            order.append(key)

    for key, comments in comments_by_parent.items():
        matching = [c for c in comments if passes_label(c)]
        if not matching and key not in rows:
            continue
        if key not in rows:  # publicación no guardada: fila sintética a partir del primer comentario
            first = comments[0]
            raw = first.raw or {}
            title = raw.get("video_title") or raw.get("post_title") or "(publicación)"
            url = f"https://www.youtube.com/watch?v={raw['video_id']}" if raw.get("video_id") else first.url
            rows[key] = {
                "id": None, "kind": "comments", "candidate": first.candidate.name,
                "candidate_id": first.candidate_id, "source": first.source.name,
                "source_type": first.source.type.value, "text": title, "url": url, "author": None,
                "published_at": max(_when(c) for c in comments).isoformat(),
                "label": None, "score": None, "topic": None, "model": None,
                "thumbnail": _thumbnail(first),
                "comments": [], "comments_summary": _summary_of([]),
            }
            order.append(key)
        shown = matching if label else comments
        rows[key]["comments"] = [_mention_dict(c) for c in shown]
        rows[key]["comments_summary"] = _summary_of([_mention_dict(c) for c in comments])
        rows[key]["last_activity"] = max(rows[key]["published_at"], max(_when(c) for c in comments).isoformat())

    result = [rows[k] for k in order]
    for r in result:
        r.setdefault("last_activity", r["published_at"])  # una publicación con actividad reciente sube
    result.sort(key=lambda r: r["last_activity"], reverse=True)
    return result[offset:offset + limit]


def sources_by_candidate(session, days: int = 30) -> dict:
    """Menciones relevantes por candidato y tipo de fuente (para la gráfica de canales)."""
    names = [c.name for c in session.query(Candidate).filter_by(active=True).all()]
    names.sort(key=lambda n: n != CARLOS)
    idx = {n: i for i, n in enumerate(names)}
    series: dict[str, list[int]] = {}
    rows = (
        session.query(Candidate.name, Source.type, func.count(Mention.id))
        .select_from(Mention).join(Candidate).join(Source)
        .filter(WHEN >= _since(days), Mention.relevant.is_(True))
        .group_by(Candidate.name, Source.type).all()
    )
    for name, stype, n in rows:
        key = stype.value
        series.setdefault(key, [0] * len(names))
        series[key][idx[name]] = n
    return {"candidates": names, "series": series}
