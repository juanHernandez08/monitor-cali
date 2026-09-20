"""Consultas de lectura para el dashboard. Devuelven dicts listos para JSON."""
import datetime as dt
from collections import Counter, defaultdict

from sqlalchemy import func

from src.models import (
    ApiUsage, Candidate, Mention, Run, SentimentLabel, SentimentScore, Source, SourceType,
)

CARLOS = "Carlos Arias"
BOGOTA = dt.timezone(dt.timedelta(hours=-5))


def _since(days: int) -> dt.datetime:
    return dt.datetime.utcnow() - dt.timedelta(days=days)


# Fecha efectiva de una mención: publicación si la fuente la da, si no captura.
WHEN = func.coalesce(Mention.published_at, Mention.fetched_at)


def _when(m: Mention) -> dt.datetime:
    return m.published_at or m.fetched_at


def _local_day(ts: dt.datetime) -> str:
    return ts.replace(tzinfo=dt.timezone.utc).astimezone(BOGOTA).strftime("%Y-%m-%d")


def summary(session, days: int = 7) -> list[dict]:
    since = _since(days)
    prev_since = since - dt.timedelta(days=days)
    rows = []
    for c in session.query(Candidate).filter_by(active=True).all():
        q = session.query(Mention).filter(Mention.candidate_id == c.id)
        current = q.filter(WHEN >= since).all()
        previous = q.filter(WHEN >= prev_since, WHEN < since).count()
        counts = Counter(m.sentiment.label for m in current if m.sentiment)
        rows.append({
            "candidate_id": c.id, "name": c.name, "party": c.party,
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
    for m in session.query(Mention).filter(WHEN >= since).all():
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
         .filter(WHEN >= _since(days)))
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
                WHEN >= _since(days))
        .order_by(WHEN.desc()).limit(limit).all()
    )
    return [_mention_dict(m) for m in rows]


def topics(session, days: int = 7, limit: int = 10) -> list[dict]:
    topic = func.lower(SentimentScore.topic)
    rows = (
        session.query(topic, func.count(SentimentScore.id))
        .join(Mention)
        .filter(WHEN >= _since(days), SentimentScore.topic != "")
        .group_by(topic).order_by(func.count(SentimentScore.id).desc())
        .limit(limit).all()
    )
    return [{"topic": t, "count": n} for t, n in rows]


def status(session) -> dict:
    total = session.query(Mention).count()
    scored = session.query(SentimentScore).count()
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
        "last_run": last_run.isoformat() if last_run else None,
        "cse_used_today": cse.count if cse else 0,
        "sources": sources,
    }
