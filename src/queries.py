"""Consultas de lectura para el dashboard. Devuelven dicts listos para JSON."""
import datetime as dt
from collections import Counter, defaultdict

from sqlalchemy import func, or_

from src import config
from src.urlnorm import normalize_url
from src.models import (
    ApiUsage, Candidate, Mention, Run, SentimentLabel, SentimentScore, Source, SourceType,
)

CARLOS = "Carlos Arias"
META_TOPICS = ("mención tangencial", "mencion tangencial", "homónimo", "homonimo", "sin tema", "etiqueta a otra cuenta")  # etiquetas de control, no temas
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
    for c in session.query(Candidate).filter_by(active=True).filter(Candidate.kind == "candidate").all():
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
    for m in session.query(Mention).join(Candidate).filter(WHEN >= since, Mention.relevant.is_(True), Candidate.kind == "candidate").all():
        per[m.candidate.name][_local_day(_when(m))] += 1
    names = [c.name for c in session.query(Candidate).filter_by(active=True).filter(Candidate.kind == "candidate").all()]
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
        "platform": (m.raw or {}).get("platform"),
        "text": m.text, "url": m.url, "author": m.author,
        "link": (m.raw or {}).get("reply_url") or m.url,  # para respuestas de X: el link de la respuesta, no del post
        "published_at": _when(m).isoformat(),
        "label": s.label.value if s else None, "score": s.score if s else None,
        "topic": s.topic if s else None, "model": s.model if s else None,
    }


def mentions(session, candidate_id: int | None = None, source_type: str | None = None,
             label: str | None = None, days: int = 30, limit: int = 100, offset: int = 0) -> list[dict]:
    q = (session.query(Mention).outerjoin(SentimentScore).join(Source).join(Candidate)
         .filter(WHEN >= _since(days), Mention.relevant.is_(True)))
    q = q.filter(Mention.candidate_id == candidate_id) if candidate_id else q.filter(Candidate.kind == "candidate")
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


def topics(session, days: int = 7, limit: int = 10, kind: str | None = None) -> list[dict]:
    """Temas más frecuentes. kind="publications" (notas, posts, videos) o "comments"; None = todo."""
    topic = func.lower(SentimentScore.topic)
    is_comment = func.json_extract(Mention.raw, "$.kind") == "comment"
    rows = (
        session.query(topic, func.count(SentimentScore.id))
        .join(Mention).join(Candidate)
        .filter(WHEN >= _since(days), SentimentScore.topic != "", Mention.relevant.is_(True), Candidate.kind == "candidate")
        .filter(topic.notin_(META_TOPICS))
    )
    if kind == "comments":
        rows = rows.filter(is_comment)
    elif kind == "publications":
        rows = rows.filter(or_(func.json_extract(Mention.raw, "$.kind").is_(None), func.json_extract(Mention.raw, "$.kind") != "comment"))
    rows = rows.group_by(topic).order_by(func.count(SentimentScore.id).desc()).limit(limit).all()
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


def _day_bounds(day: str) -> tuple[dt.datetime, dt.datetime]:
    """Inicio y fin (UTC, naive) de un día en hora Bogotá."""
    start = dt.datetime.fromisoformat(day).replace(tzinfo=BOGOTA).astimezone(dt.timezone.utc).replace(tzinfo=None)
    return start, start + dt.timedelta(days=1)


def feed(session, candidate_id: int | None = None, source_type: str | None = None,
         label: str | None = None, days: int = 30, limit: int = 100, offset: int = 0,
         day: str | None = None) -> list[dict]:
    """Filas = publicaciones (post, video, nota); los comentarios cuelgan de su publicación.

    Los filtros se aplican a las menciones; una publicación aparece si ella o alguno de sus
    comentarios pasa el filtro. Comentarios sin publicación guardada forman una fila sintética
    (kind="comments") con el título del video/post.
    """
    q = (session.query(Mention).outerjoin(SentimentScore).join(Source).join(Candidate)
         .filter(WHEN >= _since(days), Mention.relevant.is_(True)))
    q = q.filter(Mention.candidate_id == candidate_id) if candidate_id else q.filter(Candidate.kind == "candidate")
    if source_type:
        q = q.filter(Source.type == SourceType(source_type))
    if day:
        d0, d1 = _day_bounds(day)
        q = q.filter(WHEN >= d0, WHEN < d1)
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
    names = [c.name for c in session.query(Candidate).filter_by(active=True).filter(Candidate.kind == "candidate").all()]
    names.sort(key=lambda n: n != CARLOS)
    idx = {n: i for i, n in enumerate(names)}
    series: dict[str, list[int]] = {}
    platform = func.json_extract(Mention.raw, "$.platform")
    rows = (
        session.query(Candidate.name, Source.type, platform, func.count(Mention.id))
        .select_from(Mention).join(Candidate).join(Source)
        .filter(WHEN >= _since(days), Mention.relevant.is_(True), Candidate.kind == "candidate")
        .group_by(Candidate.name, Source.type, platform).all()
    )
    for name, stype, plat, n in rows:
        key = plat if (stype == SourceType.SOCIAL and plat) else stype.value  # instagram / facebook / x
        series.setdefault(key, [0] * len(names))
        series[key][idx[name]] += n
    return {"candidates": names, "series": series}


# ---------- Ciudad: temas y percepción ----------

def _city_id(session) -> int | None:
    c = session.query(Candidate).filter_by(kind="city").first()
    return c.id if c else None


def _city_rows(session, since: dt.datetime, until: dt.datetime | None = None) -> list[Mention]:
    cid = _city_id(session)
    if cid is None:
        return []
    q = (session.query(Mention).join(SentimentScore)
         .filter(Mention.candidate_id == cid, Mention.relevant.is_(True), WHEN >= since))
    if until is not None:
        q = q.filter(WHEN < until)
    return q.all()


def city_topics(session, days: int = 7, samples_per: int = 3, subtopics_per: int = 5) -> list[dict]:
    """Por categoría: volumen, tendencia vs período anterior, percepción, subtemas y comentarios de muestra."""
    since = _since(days)
    current = _city_rows(session, since)
    previous = Counter(m.sentiment.category or "otro" for m in _city_rows(session, since - dt.timedelta(days=days), since))
    by_cat: dict[str, list[Mention]] = defaultdict(list)
    for m in current:
        by_cat[m.sentiment.category or "otro"].append(m)
    rows = []
    for cat, ms in by_cat.items():
        labels = Counter(m.sentiment.label for m in ms)
        prev = previous.get(cat, 0)
        trend = None if prev == 0 else round((len(ms) - prev) / prev * 100)
        sub = Counter((m.sentiment.topic or "").lower() for m in ms if (m.sentiment.topic or "").lower() not in META_TOPICS and m.sentiment.topic)
        comments = [m for m in ms if (m.raw or {}).get("kind") == "comment"]
        pool = comments or ms
        samples = sorted(pool, key=lambda m: -abs(m.sentiment.score))[:samples_per]
        rows.append({
            "category": cat, "count": len(ms), "previous": prev, "trend_pct": trend,
            "positive": labels.get(SentimentLabel.POSITIVE, 0), "neutral": labels.get(SentimentLabel.NEUTRAL, 0),
            "negative": labels.get(SentimentLabel.NEGATIVE, 0),
            "subtopics": [{"topic": t, "count": n} for t, n in sub.most_common(subtopics_per)],
            "samples": [_mention_dict(m) for m in samples],
            "sources": dict(Counter(((m.raw or {}).get("platform") or m.source.type.value) for m in ms)),
        })
    rows.sort(key=lambda r: -r["count"])
    return rows


def city_opportunities(session, days: int = 7, min_negative_pct: int = 40, carlos_min: int = 3, carlos_pos_pct: int = 60) -> dict:
    """Temas calientes donde Carlos no aparece, y temas donde Carlos ya tiene presencia positiva."""
    topics = city_topics(session, days=days, samples_per=1, subtopics_per=3)
    carlos = session.query(Candidate).filter_by(name=CARLOS).first()
    carlos_by_cat: dict[str, Counter] = defaultdict(Counter)
    if carlos:
        for m in (session.query(Mention).join(SentimentScore)
                  .filter(Mention.candidate_id == carlos.id, Mention.relevant.is_(True), WHEN >= _since(days))):
            carlos_by_cat[m.sentiment.category or "otro"][m.sentiment.label] += 1
    counts = sorted(r["count"] for r in topics) or [0]
    median = counts[len(counts) // 2]
    hot, strong = [], []
    for r in topics:
        carlos_n = sum(carlos_by_cat[r["category"]].values())
        neg_pct = pct(r["negative"], r["count"])
        if r["count"] >= median and neg_pct >= min_negative_pct and carlos_n <= 2 and r["category"] != "otro":
            hot.append({**r, "negative_pct": neg_pct, "carlos_mentions": carlos_n})
    for cat, c in carlos_by_cat.items():
        n = sum(c.values())
        if n >= carlos_min and pct(c[SentimentLabel.POSITIVE], n) >= carlos_pos_pct:
            city = next((r for r in topics if r["category"] == cat), None)
            strong.append({"category": cat, "carlos_mentions": n, "carlos_positive_pct": pct(c[SentimentLabel.POSITIVE], n),
                           "city_count": city["count"] if city else 0})
    hot.sort(key=lambda r: (-r["negative_pct"], -r["count"]))
    strong.sort(key=lambda r: -r["carlos_mentions"])
    return {"hot_without_carlos": hot, "carlos_strong": strong}


def city_kpis(session, days: int = 7) -> dict:
    topics = city_topics(session, days=days, samples_per=0, subtopics_per=0)
    total = sum(r["count"] for r in topics)
    negative = sum(r["negative"] for r in topics)
    rising = [r for r in topics if r["trend_pct"] is not None]
    rising.sort(key=lambda r: -r["trend_pct"])
    return {
        "total": total, "top_category": topics[0]["category"] if topics else None,
        "rising_category": rising[0]["category"] if rising else None,
        "rising_pct": rising[0]["trend_pct"] if rising else None,
        "negative_pct": pct(negative, total),
    }


def pct(n: int, t: int) -> int:
    return round(n / t * 100) if t else 0


def peak_publication(session, candidate_name: str, day: str) -> dict | None:
    """La publicación (post/video/nota + sus comentarios) que más menciones generó ese día (hora Bogotá)."""
    cand = session.query(Candidate).filter_by(name=candidate_name).first()
    if cand is None:
        return None
    start_local = dt.datetime.fromisoformat(day).replace(tzinfo=BOGOTA)
    start = start_local.astimezone(dt.timezone.utc).replace(tzinfo=None)
    end = start + dt.timedelta(days=1)
    ms = (session.query(Mention).filter(Mention.candidate_id == cand.id, Mention.relevant.is_(True),
                                        WHEN >= start, WHEN < end).all())
    if not ms:
        return None
    groups: dict[str, list[Mention]] = defaultdict(list)
    for m in ms:
        groups[_parent_key(m) or f"solo:{m.id}"].append(m)
    key, members = max(groups.items(), key=lambda kv: len(kv[1]))
    parent = next((m for m in members if (m.raw or {}).get("kind") != "comment"), None)
    if parent is None:  # solo comentarios: describir por el título del video/post
        first = members[0]
        raw = first.raw or {}
        title = raw.get("video_title") or raw.get("post_title") or first.text
        url = f"https://www.youtube.com/watch?v={raw['video_id']}" if raw.get("video_id") else first.url
        return {"text": title, "url": url, "kind": "comments", "source_type": first.source.type.value,
                "platform": raw.get("platform"), "mentions_that_day": len(members), "day": day}
    row = _mention_dict(parent)
    row.update({"kind": (parent.raw or {}).get("kind") or "news", "mentions_that_day": len(members), "day": day,
                "thumbnail": _thumbnail(parent)})
    return row


def timeline_details(session, days: int = 7) -> dict:
    """Para cada candidato y día: la publicación que más menciones reunió (para el tooltip de la gráfica)."""
    since = _since(days)
    ms = (session.query(Mention).join(Candidate)
          .filter(WHEN >= since, Mention.relevant.is_(True), Candidate.kind == "candidate").all())
    groups: dict[tuple[str, str], dict[str, list[Mention]]] = defaultdict(lambda: defaultdict(list))
    for m in ms:
        groups[(m.candidate.name, _local_day(_when(m)))][_parent_key(m) or f"solo:{m.id}"].append(m)
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for (name, day), by_parent in groups.items():
        total = sum(len(v) for v in by_parent.values())
        members = max(by_parent.values(), key=len)
        parent = next((m for m in members if (m.raw or {}).get("kind") != "comment"), None)
        if parent is not None:
            raw = parent.raw or {}
            text, url, kind, plat, stype = parent.text, parent.url, raw.get("kind") or "news", raw.get("platform"), parent.source.type.value
        else:
            raw = members[0].raw or {}
            text = raw.get("video_title") or raw.get("post_title") or members[0].text
            url = f"https://www.youtube.com/watch?v={raw['video_id']}" if raw.get("video_id") else members[0].url
            kind, plat, stype = "comments", raw.get("platform"), members[0].source.type.value
        out[name][day] = {"text": text, "url": url, "kind": kind, "platform": plat, "source_type": stype,
                          "count": len(members), "total": total}
    return out


# ---------- Agenda: de qué hablar y qué evitar ----------

PROBLEM_MIN_NEGATIVE_PCT = 35   # por debajo de esto el tema no es un problema que resolver
RISK_MIN_NEGATIVE_PCT = 55      # a quien habló del tema le respondieron mal
RISK_MIN_COMMENTS = 4           # mínimo de reacciones ciudadanas para afirmar algo


def _candidate_comments(session, days: int, only: str | None = None) -> list[Mention]:
    """Comentarios y respuestas de la gente a publicaciones de candidatos (no de la ciudad)."""
    q = (session.query(Mention).join(SentimentScore).join(Candidate)
         .filter(WHEN >= _since(days), Mention.relevant.is_(True), Candidate.kind == "candidate"))
    if only:
        q = q.filter(Candidate.name == only)
    return [m for m in q.all() if (m.raw or {}).get("kind") == "comment"]


def citizen_perception(session, days: int = 30, samples_per: int = 3) -> list[dict]:
    """Cómo reacciona la gente a las publicaciones de cada candidato (solo comentarios y respuestas)."""
    by_cand: dict[str, list[Mention]] = defaultdict(list)
    for m in _candidate_comments(session, days):
        by_cand[m.candidate.name].append(m)
    rows = []
    for name, ms in by_cand.items():
        labels = Counter(m.sentiment.label for m in ms)
        pos, neg, neu = (labels.get(SentimentLabel.POSITIVE, 0), labels.get(SentimentLabel.NEGATIVE, 0),
                         labels.get(SentimentLabel.NEUTRAL, 0))
        topics = Counter((m.sentiment.topic or "").lower() for m in ms
                         if m.sentiment.topic and (m.sentiment.topic or "").lower() not in META_TOPICS)
        rows.append({
            "name": name, "comments": len(ms), "positive": pos, "negative": neg, "neutral": neu,
            "positive_pct": pct(pos, len(ms)), "negative_pct": pct(neg, len(ms)),
            "topics": [{"topic": t, "count": n} for t, n in topics.most_common(5)],
            "samples": [_mention_dict(m) for m in sorted(ms, key=lambda m: -abs(m.sentiment.score))[:samples_per]],
        })
    rows.sort(key=lambda r: (r["name"] != CARLOS, -r["comments"]))
    return rows


def candidate_topic_map(session, candidate_name: str, days: int = 30, samples_per: int = 4) -> list[dict]:
    """Mapa de un candidato por tema concreto: de qué se habla sobre él y qué dice la gente en cada
    tema (positivo/negativo/neutral, con comentarios de muestra). A diferencia de `city_topics`
    (que agrupa por categoría amplia), esto agrupa por `topic` -el asunto puntual- para un solo
    candidato, y sirve tanto para publicaciones propias como para lo que rivales o prensa dicen de él."""
    candidate = session.query(Candidate).filter_by(name=candidate_name).first()
    if not candidate:
        return []
    since = _since(days)
    rows = (session.query(Mention).join(SentimentScore)
            .filter(Mention.candidate_id == candidate.id, Mention.relevant.is_(True), WHEN >= since)
            .all())
    by_topic: dict[str, list[Mention]] = defaultdict(list)
    for m in rows:
        topic = (m.sentiment.topic or "").strip().lower()
        if not topic or topic in META_TOPICS:
            continue
        by_topic[topic].append(m)
    out = []
    for topic, ms in by_topic.items():
        labels = Counter(m.sentiment.label for m in ms)
        pos, neg, neu = (labels.get(SentimentLabel.POSITIVE, 0), labels.get(SentimentLabel.NEGATIVE, 0),
                         labels.get(SentimentLabel.NEUTRAL, 0))
        comments = [m for m in ms if (m.raw or {}).get("kind") == "comment"]
        pool = comments or ms
        out.append({
            "topic": topic, "count": len(ms),
            "positive": pos, "negative": neg, "neutral": neu, "positive_pct": pct(pos, len(ms)),
            "sources": dict(Counter(((m.raw or {}).get("platform") or m.source.type.value) for m in ms)),
            "samples": [_mention_dict(m) for m in sorted(pool, key=lambda m: -abs(m.sentiment.score))[:samples_per]],
        })
    out.sort(key=lambda r: -r["count"])
    return out


def agenda(session, days: int = 30) -> dict:
    """Temas de los que conviene hablar (problema ciudadano sin respuesta) y temas de riesgo."""
    topics = city_topics(session, days=days, samples_per=3, subtopics_per=5)
    carlos = session.query(Candidate).filter_by(name=CARLOS).first()
    carlos_by_cat: Counter = Counter()
    if carlos:
        for m in (session.query(Mention).join(SentimentScore)
                  .filter(Mention.candidate_id == carlos.id, Mention.relevant.is_(True), WHEN >= _since(days))):
            carlos_by_cat[m.sentiment.category or "otro"] += 1
    # Reacción ciudadana a los candidatos, por tema: dónde le fue mal a quien habló
    reactions: dict[str, Counter] = defaultdict(Counter)
    by_cat_cands: dict[str, set] = defaultdict(set)
    for m in _candidate_comments(session, days):
        cat = m.sentiment.category or "otro"
        reactions[cat][m.sentiment.label] += 1
        by_cat_cands[cat].add(m.candidate.name)

    volumes = sorted(t["count"] for t in topics) or [0]
    median = volumes[len(volumes) // 2]
    speak, avoid = [], []
    for t in topics:
        cat = t["category"]
        if cat == "otro":
            continue
        neg_pct = pct(t["negative"], t["count"])
        carlos_n = carlos_by_cat.get(cat, 0)
        if neg_pct >= PROBLEM_MIN_NEGATIVE_PCT and t["count"] >= median:
            speak.append({**t, "negative_pct": neg_pct, "carlos_mentions": carlos_n,
                          "priority": round(t["count"] * neg_pct / 100 * (1 if carlos_n == 0 else 0.5), 1)})
        r = reactions.get(cat)
        if r:
            total = sum(r.values())
            r_neg = pct(r[SentimentLabel.NEGATIVE], total)
            if total >= RISK_MIN_COMMENTS and r_neg >= RISK_MIN_NEGATIVE_PCT:
                avoid.append({"category": cat, "city_count": t["count"], "city_negative_pct": neg_pct,
                              "candidate_comments": total, "candidate_negative_pct": r_neg,
                              "candidates": sorted(by_cat_cands[cat]), "subtopics": t["subtopics"][:3],
                              "samples": t["samples"][:2]})
    speak.sort(key=lambda t: -t["priority"])
    avoid.sort(key=lambda t: -t["candidate_negative_pct"])
    return {"speak": speak, "avoid": avoid}


# ---------- Concejo de Cali ----------

def council_overview(session, days: int = 30) -> dict:
    """Concejales (incluidos los que además son candidatos): menciones y sentimiento, por persona y por partido."""
    members = (session.query(Candidate).filter_by(active=True, council=True)
               .order_by(Candidate.name).all())
    since = _since(days)
    rows = []
    for c in members:
        ms = [m for m in c.mentions if m.relevant and _when(m) >= since]
        labels = Counter(m.sentiment.label for m in ms if m.sentiment)
        comments = [m for m in ms if (m.raw or {}).get("kind") == "comment" and m.sentiment]
        com_labels = Counter(m.sentiment.label for m in comments)
        topics = Counter((m.sentiment.topic or "").lower() for m in ms
                         if m.sentiment and m.sentiment.topic and (m.sentiment.topic or "").lower() not in META_TOPICS)
        categories = Counter(m.sentiment.category for m in ms if m.sentiment and m.sentiment.category)
        rows.append({
            "candidate_id": c.id, "name": c.name, "party": c.party, "is_candidate": c.kind == "candidate",
            "mentions": len(ms),
            "positive": labels.get(SentimentLabel.POSITIVE, 0), "negative": labels.get(SentimentLabel.NEGATIVE, 0),
            "neutral": labels.get(SentimentLabel.NEUTRAL, 0),
            "comments": len(comments),
            "comments_positive_pct": pct(com_labels.get(SentimentLabel.POSITIVE, 0), len(comments)),
            "comments_negative_pct": pct(com_labels.get(SentimentLabel.NEGATIVE, 0), len(comments)),
            "topics": [{"topic": t, "count": n} for t, n in topics.most_common(4)],
            "categories": [{"category": t, "count": n} for t, n in categories.most_common(3)],
            "samples": [_mention_dict(m) for m in sorted((m for m in ms if m.sentiment),
                                                         key=lambda m: -abs(m.sentiment.score))[:2]],
        })
    by_party: dict[str, dict] = {}
    for r in rows:
        p = by_party.setdefault(r["party"] or "Sin partido",
                                {"party": r["party"] or "Sin partido", "members": 0, "mentions": 0,
                                 "positive": 0, "negative": 0, "neutral": 0, "names": []})
        p["members"] += 1
        p["names"].append(r["name"])
        for k in ("mentions", "positive", "negative", "neutral"):
            p[k] += r[k]
    parties = sorted(by_party.values(), key=lambda p: (-p["mentions"], -p["members"]))
    rows.sort(key=lambda r: (r["name"] != CARLOS, -r["mentions"]))
    return {"members": rows, "parties": parties}
