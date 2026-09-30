"""Consultas de lectura para el dashboard. Devuelven dicts listos para JSON."""
import datetime as dt
import re
import unicodedata
from collections import Counter, defaultdict

from sqlalchemy import func, or_

from src import config, stats
from src.urlnorm import normalize_url
from src.models import (
    ApiUsage, Candidate, Mention, Run, SentimentLabel, SentimentScore, Source, SourceType,
)

CARLOS = "Carlos Arias"
META_TOPICS = ("mención tangencial", "mencion tangencial", "homónimo", "homonimo", "sin tema", "etiqueta a otra cuenta")  # etiquetas de control, no temas
BOGOTA = dt.timezone(dt.timedelta(hours=-5))
# "deporte" nunca es una novedad para sugerir: recomendar que Carlos hable de un equipo o partido
# alimenta la rivalidad entre hinchas en vez de ayudarlo (pedido del cliente 2026-09-28) -- si hay
# una situación real (violencia, obra pública), entra por otra categoría (seguridad, infraestructura...).
NOVEDADES_EXCLUDED_CATEGORIES = {"deporte"}
_STOPWORDS = {"de", "la", "el", "en", "y", "del", "los", "las", "un", "una", "con", "para", "por",
              "que", "se", "su", "a", "al", "lo", "sus", "sobre", "tras"}


def _keywords(text: str) -> set[str]:
    """Palabras distintivas de un texto: sin tildes, en minúscula, sin conectores ni palabras muy
    cortas. Se usa para reconocer el mismo asunto real aunque el LLM le haya puesto una etiqueta
    de "topic" distinta en cada mención (ver mentions_covering_topic)."""
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", plain.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def mention_keywords(mentions: list[Mention]) -> list[set[str]]:
    """Palabras distintivas de cada mención (texto + topic), precalculadas una sola vez para
    comparar contra muchos temas sin repetir el trabajo por cada uno."""
    return [_keywords((m.sentiment.topic or "") + " " + (m.text or "")) for m in mentions]


def mentions_covering_topic(topic: str, keywords: list[set[str]]) -> int:
    """Cuántas menciones (ya reducidas a palabras con mention_keywords) hablan de `topic`. No
    exige el topic idéntico -- el LLM no siempre etiqueta igual el mismo asunto real en dos
    menciones distintas (p. ej. un post sobre la Operación Iron quedó con topic "seguridad", no
    "Operación Iron"): alcanza con que las palabras distintivas del tema estén en la mención."""
    topic_words = _keywords(topic)
    if not topic_words:
        return 0
    return sum(1 for kw in keywords if topic_words <= kw)


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
            "positive_ci": stats.wilson(counts.get(SentimentLabel.POSITIVE, 0), sum(counts.values())),
            "change": stats.count_change_test(len(current), previous),
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
        "summary": (s.summary if s else None) or None,
        "emotion": (s.emotion if s else None) or None,
        "emotion_nuance": (s.emotion_nuance if s else None) or None,
        "apalancador": (s.apalancador if s else None) or None,
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


def _week_bounds(week: str) -> tuple[dt.datetime, dt.datetime]:
    """Inicio y fin (UTC, naive) de una semana ISO 'YYYY-Sww' en hora Bogotá -- mismo formato que
    strftime('%G-S%V'), usado en el gráfico de participación semanal."""
    year, wk = week.split("-S")
    monday = dt.date.fromisocalendar(int(year), int(wk), 1)
    start = dt.datetime.combine(monday, dt.time()).replace(tzinfo=BOGOTA).astimezone(dt.timezone.utc).replace(tzinfo=None)
    return start, start + dt.timedelta(days=7)


def feed(session, candidate_id: int | None = None, source_type: str | None = None,
         label: str | None = None, emotion: str | None = None, category: str | None = None,
         city: bool = False, days: int = 30, limit: int = 100, offset: int = 0,
         day: str | None = None, week: str | None = None) -> list[dict]:
    """Filas = publicaciones (post, video, nota); los comentarios cuelgan de su publicación.

    Los filtros se aplican a las menciones; una publicación aparece si ella o alguno de sus
    comentarios pasa el filtro. Comentarios sin publicación guardada forman una fila sintética
    (kind="comments") con el título del video/post. `city=True` trae solo lo que no nombra a
    ningún candidato (la conversación general de Cali), igual que la pestaña Ciudad.

    `day` (YYYY-MM-DD) o `week` (YYYY-Sww) acotan a esa fecha exacta EN VEZ del rango relativo
    `days` (no además de él: si no, una semana fuera de los últimos `days` días no traería nada).
    """
    q = (session.query(Mention).outerjoin(SentimentScore).join(Source).join(Candidate)
         .filter(Mention.relevant.is_(True)))
    if week:
        d0, d1 = _week_bounds(week)
        q = q.filter(WHEN >= d0, WHEN < d1)
    elif day:
        d0, d1 = _day_bounds(day)
        q = q.filter(WHEN >= d0, WHEN < d1)
    else:
        q = q.filter(WHEN >= _since(days))
    if city:
        q = q.filter(Candidate.kind == "city")
    elif candidate_id:
        q = q.filter(Mention.candidate_id == candidate_id)
    else:
        q = q.filter(Candidate.kind == "candidate")
    if source_type == "prensa":  # Google News + RSS combinados -- pestaña Publicaciones > Prensa
        q = q.filter(Source.type.in_([SourceType.GOOGLE_NEWS, SourceType.RSS]))
    elif source_type:
        q = q.filter(Source.type == SourceType(source_type))
    filtered = q.order_by(WHEN.desc(), Mention.id.desc()).limit(3000).all()

    def passes_filters(m: Mention) -> bool:
        if label and (m.sentiment is None or m.sentiment.label.value != label):
            return False
        if emotion and (m.sentiment is None or (m.sentiment.emotion or "sin emoción marcada") != emotion):
            return False
        if category and (m.sentiment is None or (m.sentiment.category or "otro") != category):
            return False
        return True

    rows: dict[str, dict] = {}
    order: list[str] = []
    comments_by_parent: dict[str, list[Mention]] = defaultdict(list)
    for m in filtered:
        if (m.raw or {}).get("kind") == "comment":
            key = _parent_key(m) or f"solo:{m.id}"
            comments_by_parent[key].append(m)
        elif passes_filters(m):
            key = _parent_key(m) or f"solo:{m.id}"
            raw = m.raw or {}
            row = _mention_dict(m)
            row["kind"] = raw.get("kind") or "news"
            row["thumbnail"] = _thumbnail(m)
            row["comments"], row["comments_summary"] = [], _summary_of([])
            rows[key] = row
            order.append(key)

    for key, comments in comments_by_parent.items():
        matching = [c for c in comments if passes_filters(c)]
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
                "label": None, "score": None, "topic": None, "model": None, "summary": None, "emotion": None,
                "emotion_nuance": None, "apalancador": None,
                "thumbnail": _thumbnail(first),
                "comments": [], "comments_summary": _summary_of([]),
            }
            order.append(key)
        shown = matching if (label or emotion or category) else comments
        rows[key]["comments"] = [_mention_dict(c) for c in shown]
        rows[key]["comments_summary"] = _summary_of([_mention_dict(c) for c in comments])
        rows[key]["last_activity"] = max(rows[key]["published_at"], max(_when(c) for c in comments).isoformat())

    result = [rows[k] for k in order]
    for r in result:
        r.setdefault("last_activity", r["published_at"])  # una publicación con actividad reciente sube
    result.sort(key=lambda r: r["last_activity"], reverse=True)
    return result[offset:offset + limit]


# ---------- Meta y redes: publicaciones de Instagram/Facebook/X con métricas de alcance ----------

def _num(value) -> int | None:
    """Número de un campo del scraper: None si falta o no es numérico ("1,234" también sirve)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace(".", ""))
    except ValueError:
        return None


def _first(*values):
    return next((v for v in values if v is not None), None)


# Formato de la publicación, igual para los dos scrapers (Apify: productType/type; Bright Data:
# content_type) -- sirve para comparar qué formato rinde más.
_FORMAT = {"clips": "reel", "reel": "reel", "igtv": "reel", "video": "video", "carousel_container": "carrusel",
           "sidecar": "carrusel", "carousel": "carrusel", "feed": "imagen", "image": "imagen", "photo": "imagen",
           "post": "imagen"}


def _social_metrics(m: Mention) -> dict:
    """Likes/comentarios/vistas/compartidos desde el registro crudo del scraper.

    El nombre del campo cambia por plataforma Y por proveedor. Auditoría estadística 2026-09-29:
    antes solo se leían los campos de Apify, así que (1) las 17 publicaciones de Instagram que
    trajo Bright Data (campo `likes`, no `likesCount`) contaban con 0 likes -- entre ellas los reels
    de Carlos de septiembre, lo que fabricaba una "caída" de su alcance --, (2) X nunca sumaba likes
    (`likeCount`) y (3) Instagram devuelve likesCount = -1 cuando la cuenta oculta los likes, y se
    restaba como si fuera un dato. Ahora un like oculto queda marcado (`likes_hidden`) y esas
    publicaciones no entran en los promedios de alcance, porque su cifra real es desconocida."""
    raw = m.raw or {}
    rec = raw.get("record") or {}
    platform = raw.get("platform")
    shares = None
    if platform == "instagram":
        likes = _num(_first(rec.get("likesCount"), rec.get("likes")))
        views = _num(_first(rec.get("videoPlayCount"), rec.get("videoViewCount"), rec.get("video_view_count"),
                            rec.get("video_play_count"), rec.get("views")))
        fmt = _FORMAT.get(str(rec.get("productType") or rec.get("content_type") or rec.get("type") or "").lower(), "otro")
    elif platform == "facebook":
        likes = _num(_first(rec.get("likes"), rec.get("reactionLikeCount")))
        views = _num(_first(rec.get("viewsCount"), rec.get("videoPostViewCount")))
        shares = _num(rec.get("shares"))
        fmt = "video" if rec.get("isVideo") else "imagen"
    elif platform == "x":
        likes = _num(_first(rec.get("likeCount"), raw.get("likes")))
        views = _num(rec.get("viewCount"))
        shares = _num(_first(rec.get("retweetCount"), raw.get("reposts")))
        fmt = "trino"
    else:
        likes = views = None
        fmt = "otro"
    hidden = likes is not None and likes < 0
    comments = _num(raw.get("num_comments")) or 0
    return {"likes": 0 if (likes is None or hidden) else likes, "comments": max(comments, 0),
            "views": views if (views and views > 0) else 0, "shares": shares if (shares and shares > 0) else 0,
            "likes_hidden": hidden, "format": fmt}


def social_posts(session, days: int = 30, candidate_id: int | None = None, platform: str | None = None,
                 sort: str = "engagement", limit: int = 200) -> list[dict]:
    """Publicaciones (no comentarios) de Instagram/Facebook/X, con alcance para ordenar por
    desempeño real en vez de solo cronología -- lo que pidió el cliente para "el análisis de las
    publicaciones" en la pestaña Meta y redes. Incluye candidatos Y concejales (kind != "city"):
    antes solo miraba kind == "candidate" y una publicación con mucha fuerza de un concejal (p.
    ej. un reel de Audry Toro) quedaba invisible en esta pestaña -- justo lo que se supone que
    este monitor debe detectar."""
    q = (session.query(Mention).outerjoin(SentimentScore).join(Source).join(Candidate)
         .filter(WHEN >= _since(days), Mention.relevant.is_(True), Source.type == SourceType.SOCIAL,
                 Candidate.kind != "city"))
    if candidate_id:
        q = q.filter(Mention.candidate_id == candidate_id)
    rows = [m for m in q.all() if (m.raw or {}).get("kind") == "post"]
    if platform:
        rows = [m for m in rows if (m.raw or {}).get("platform") == platform]
    result = []
    for m in rows:
        d = _mention_dict(m)
        d["thumbnail"] = _thumbnail(m)
        d["platform"] = (m.raw or {}).get("platform")
        d.update(_social_metrics(m))
        d["engagement"] = d["likes"] + d["comments"]
        result.append(d)
    if sort == "engagement":
        result.sort(key=lambda r: -r["engagement"])
    elif sort == "views":
        result.sort(key=lambda r: -r["views"])
    else:
        result.sort(key=lambda r: r["published_at"], reverse=True)
    return result[:limit]


def social_kpis(session, days: int = 30) -> dict:
    posts = social_posts(session, days=days, limit=10000, sort="recent")
    by_candidate = Counter(p["candidate"] for p in posts)
    return {
        "total_posts": len(posts),
        "total_likes": sum(p["likes"] for p in posts),
        "total_comments": sum(p["comments"] for p in posts),
        "total_views": sum(p["views"] for p in posts),
        "top_post": max(posts, key=lambda p: p["engagement"]) if posts else None,
        "by_candidate": [{"candidate": k, "count": v} for k, v in by_candidate.most_common()],
    }


def social_strong_posts(session, days: int = 7, multiplier: float = 3.0, min_history: int = 2,
                        min_engagement: int = 30, window: int = 10) -> list[dict]:
    """Publicaciones (de cualquier candidato o concejal) cuyo alcance dispara muy por encima de lo
    habitual en esa MISMA cuenta -- alerta de actividad fuerte en redes sin un umbral fijo igual
    para una cuenta grande que para una chica.

    Lo habitual es la MEDIANA de las últimas `window` publicaciones anteriores (antes era el
    promedio de todo el historial: un solo reel viral inflaba la base y escondía los siguientes
    picos, y lo muy viejo pesaba igual que lo reciente). Necesita al menos `min_history`
    publicaciones previas; las de likes ocultos no cuentan como base ni se alertan."""
    since = _since(days).isoformat()
    by_account: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in social_posts(session, days=365, limit=10000, sort="recent"):
        if not p["likes_hidden"]:
            by_account[(p["candidate"], p["platform"])].append(p)
    strong = []
    for posts in by_account.values():
        posts.sort(key=lambda p: p["published_at"])
        for i, p in enumerate(posts):
            history = posts[max(0, i - window):i]
            if len(history) < min_history or p["published_at"] < since:
                continue
            baseline = stats.median([h["engagement"] for h in history])
            if not baseline or baseline <= 0:
                continue
            if p["engagement"] >= max(min_engagement, baseline * multiplier):
                strong.append({**p, "baseline": round(baseline), "multiplier": round(p["engagement"] / baseline, 1),
                               "robust_z": stats.robust_z(p["engagement"], [h["engagement"] for h in history])})
    strong.sort(key=lambda p: -p["multiplier"])
    return strong


def social_candidates(session) -> list[dict]:
    """Candidatos y concejales (todo menos el candidato especial de ciudad), para poblar el
    filtro de "Meta y redes" -- antes ese filtro solo listaba a los 9 candidatos a la alcaldía."""
    rows = (session.query(Candidate).filter_by(active=True).filter(Candidate.kind != "city")
            .order_by(Candidate.name).all())
    rows.sort(key=lambda c: c.name != CARLOS)
    return [{"candidate_id": c.id, "name": c.name, "party": c.party, "is_councilor": c.kind == "councilor"}
            for c in rows]


def candidate_reach_comparison(session, days: int = 30, min_posts: int = 2) -> list[dict]:
    """Alcance real por cuenta: interacción por publicación (mediana y promedio), ritmo de
    publicación y tendencia (mitad reciente del período vs. la mitad anterior) -- la base numérica
    para explicar por qué a Carlos le va mejor o peor que a sus rivales en redes.

    Se ordena por MEDIANA: el promedio lo mueve un solo reel viral (en los datos reales, un reel
    de Carlos con 11.321 interacciones triplicaba su promedio). Las publicaciones con likes
    ocultos se excluyen (su alcance real es desconocido) y se informan en `hidden_likes_posts`."""
    posts = social_posts(session, days=days, limit=10000, sort="recent")
    by_cand: dict[str, list[dict]] = defaultdict(list)
    hidden: Counter = Counter()
    for p in posts:
        if p["likes_hidden"]:
            hidden[p["candidate"]] += 1
            continue
        by_cand[p["candidate"]].append(p)

    rows = []
    for cand, ps in by_cand.items():
        if len(ps) < min_posts:
            continue
        ps.sort(key=lambda p: p["published_at"])
        n = len(ps)
        eng = [p["engagement"] for p in ps]
        avg_engagement = round(sum(eng) / n)
        half = n // 2
        first, second = ps[:half], ps[half:]
        avg_first = sum(p["engagement"] for p in first) / len(first) if first else None
        avg_second = sum(p["engagement"] for p in second) / len(second) if second else None
        trend_pct = (round((avg_second - avg_first) / avg_first * 100)
                    if avg_first and avg_second is not None else None)
        med_first = stats.median([p["engagement"] for p in first]) if first else None
        med_second = stats.median([p["engagement"] for p in second]) if second else None
        ci = stats.bootstrap_median_ci(eng)
        with_views = [p for p in ps if p["views"]]
        rows.append({
            "candidate": cand, "posts": n, "posts_per_week": round(n / (days / 7), 1),
            "avg_engagement": avg_engagement, "median_engagement": round(stats.median(eng)),
            "median_ci": [round(ci[0]), round(ci[1])] if ci else None,
            "total_engagement": sum(eng), "trend_pct": trend_pct,
            "median_trend_pct": (round((med_second - med_first) / med_first * 100)
                                 if med_first and med_second is not None else None),
            "engagement_per_view_pct": (round(stats.median([p["engagement"] / p["views"] * 100 for p in with_views]), 1)
                                        if len(with_views) >= 3 else None),
            "hidden_likes_posts": hidden.get(cand, 0),
        })
    rows.sort(key=lambda r: -r["median_engagement"])
    return rows


def candidate_comment_reaction(session, days: int = 30, min_comments: int = 3) -> list[dict]:
    """Cómo responde la ciudadanía a los posts PROPIOS de cada candidato/concejal (solo
    comentarios dejados en su publicación, identificados por raw.account_candidate -- no
    cualquier comentario que lo nombre de pasada)."""
    since = _since(days)
    rows = (session.query(Mention).join(SentimentScore).join(Source)
            .filter(WHEN >= since, Source.type == SourceType.SOCIAL, Mention.relevant.is_(True)).all())
    by_cand: dict[str, Counter] = defaultdict(Counter)
    for m in rows:
        raw = m.raw or {}
        owner = raw.get("account_candidate")
        if raw.get("kind") != "comment" or not owner:
            continue
        # Un comentario en el post de X que en realidad insulta o habla de Y queda atribuido a Y
        # (pipeline.ingest() lo hace por texto, no por dueño de cuenta) -- no cuenta como reacción
        # a X, aunque esté físicamente en su publicación.
        if m.candidate.name != owner:
            continue
        by_cand[owner][m.sentiment.label] += 1
    out = []
    for cand, c in by_cand.items():
        n = sum(c.values())
        if n < min_comments:
            continue
        out.append({"candidate": cand, "comments": n,
                    "positive_pct": pct(c.get(SentimentLabel.POSITIVE, 0), n),
                    "neutral_pct": pct(c.get(SentimentLabel.NEUTRAL, 0), n),
                    "negative_pct": pct(c.get(SentimentLabel.NEGATIVE, 0), n),
                    # Con pocos comentarios, "100% positivo" puede ser 60%: el intervalo lo dice.
                    "positive_ci": stats.wilson(c.get(SentimentLabel.POSITIVE, 0), n),
                    "negative_ci": stats.wilson(c.get(SentimentLabel.NEGATIVE, 0), n)})
    out.sort(key=lambda r: -r["comments"])
    return out


def candidate_topic_gaps(session, candidate_name: str, days: int = 7, limit: int = 6) -> list[dict]:
    """De las categorías de ciudad más mencionadas en el período, en cuáles este candidato no
    aparece para NADA en sus propias menciones -- una categoría entera sin ninguna mención suya es
    un hueco real de cobertura (usa la "category" fija del LLM, no el "topic" libre)."""
    topics = city_topics(session, days=days)
    candidate = session.query(Candidate).filter_by(name=candidate_name).first()
    if not candidate:
        return []
    covered = {cat for (cat,) in (
        session.query(SentimentScore.category).join(Mention)
        .filter(Mention.candidate_id == candidate.id, Mention.relevant.is_(True), WHEN >= _since(days))
        .distinct()
    )}
    gaps = [t for t in topics if t["category"] not in covered and t["category"] not in NOVEDADES_EXCLUDED_CATEGORIES]
    return gaps[:limit]


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
        change = stats.count_change_test(len(ms), prev)
        rows.append({
            "category": cat, "count": len(ms), "previous": prev, "trend_pct": trend,
            "trend_significant": change["significant"], "trend_p": change["p_value"],
            "small_sample": change["small_sample"],
            "positive": labels.get(SentimentLabel.POSITIVE, 0), "neutral": labels.get(SentimentLabel.NEUTRAL, 0),
            "negative": labels.get(SentimentLabel.NEGATIVE, 0),
            "subtopics": [{"topic": t, "count": n} for t, n in sub.most_common(subtopics_per)],
            "samples": [_mention_dict(m) for m in samples],
            "sources": dict(Counter(((m.raw or {}).get("platform") or m.source.type.value) for m in ms)),
        })
    rows.sort(key=lambda r: -r["count"])
    return rows


def city_emotions(session, days: int = 7, samples_per: int = 2) -> list[dict]:
    """Qué emoción transmite la conversación de la ciudad (rueda de emociones), con muestras."""
    current = _city_rows(session, _since(days))
    by_emotion: dict[str, list[Mention]] = defaultdict(list)
    for m in current:
        by_emotion[m.sentiment.emotion or "sin emoción marcada"].append(m)
    rows = []
    for emotion, ms in by_emotion.items():
        comments = [m for m in ms if (m.raw or {}).get("kind") == "comment"]
        pool = comments or ms
        samples = sorted(pool, key=lambda m: -abs(m.sentiment.score))[:samples_per]
        rows.append({"emotion": emotion, "count": len(ms), "samples": [_mention_dict(m) for m in samples]})
    rows.sort(key=lambda r: -r["count"])
    return rows


def city_emotion_by_topic(session, days: int = 7) -> list[dict]:
    """Cruce tema x emoción: para cada categoría, cuántas menciones de cada emoción -- para el
    mapa de calor "qué emoción transmite cada tema" (pedido del cliente 2026-09-26)."""
    current = _city_rows(session, _since(days))
    by_cat: dict[str, Counter] = defaultdict(Counter)
    for m in current:
        cat = m.sentiment.category or "otro"
        emo = m.sentiment.emotion or "sin emoción marcada"
        by_cat[cat][emo] += 1
    rows = [{"category": cat, "emotions": dict(counter), "total": sum(counter.values())} for cat, counter in by_cat.items()]
    rows.sort(key=lambda r: -r["total"])
    return rows


def city_opportunities(session, days: int = 7, carlos_max: int = 2, min_count: int = 3,
                       min_trend_pct: int = 80, limit: int = 8, carlos_min: int = 3, carlos_pos_pct: int = 60) -> dict:
    """Novedades sobre las que Carlos podría hablar (temas nuevos o en fuerte alza, sea cual sea
    su tono -- no solo molestia; un evento informativo o positivo, como la visita de una figura
    nacional, es tan buena oportunidad como una queja), y temas donde Carlos ya tiene presencia
    positiva sostenida."""
    since = _since(days)
    current = _city_rows(session, since)
    previous = _city_rows(session, since - dt.timedelta(days=days), since)

    def _topic_rows(rows: list[Mention]) -> dict[str, list[Mention]]:
        by_topic: dict[str, list[Mention]] = defaultdict(list)
        for m in rows:
            t = (m.sentiment.topic or "").lower()
            if t and t not in META_TOPICS:
                by_topic[t].append(m)
        return by_topic

    current_by_topic = _topic_rows(current)
    previous_counts = Counter({t: len(ms) for t, ms in _topic_rows(previous).items()})

    carlos = session.query(Candidate).filter_by(name=CARLOS).first()
    carlos_mentions: list[Mention] = []
    carlos_by_cat: dict[str, Counter] = defaultdict(Counter)
    if carlos:
        carlos_mentions = (session.query(Mention).join(SentimentScore)
                           .filter(Mention.candidate_id == carlos.id, Mention.relevant.is_(True), WHEN >= since).all())
        for m in carlos_mentions:
            carlos_by_cat[m.sentiment.category or "otro"][m.sentiment.label] += 1
    # Palabras de cada mención de Carlos, precalculadas una vez (no por cada tema que se evalúa).
    carlos_keywords = mention_keywords(carlos_mentions)

    novedades = []
    for topic, ms in current_by_topic.items():
        count = len(ms)
        prev = previous_counts.get(topic, 0)
        trend = None if prev == 0 else round((count - prev) / prev * 100)
        is_new = prev == 0 and count >= min_count
        is_rising = trend is not None and trend >= min_trend_pct and count >= min_count
        category = Counter(m.sentiment.category or "otro" for m in ms).most_common(1)[0][0]
        if category in NOVEDADES_EXCLUDED_CATEGORIES:
            continue
        carlos_n = mentions_covering_topic(topic, carlos_keywords)
        if (is_new or is_rising) and carlos_n <= carlos_max:
            labels = Counter(m.sentiment.label for m in ms)
            samples = sorted(ms, key=lambda m: -abs(m.sentiment.score))[:2]
            novedades.append({
                "topic": topic, "category": category, "count": count, "is_new": is_new, "trend_pct": trend,
                "positive": labels.get(SentimentLabel.POSITIVE, 0), "neutral": labels.get(SentimentLabel.NEUTRAL, 0),
                "negative": labels.get(SentimentLabel.NEGATIVE, 0), "carlos_mentions": carlos_n,
                "samples": [_mention_dict(m) for m in samples],
            })
    novedades.sort(key=lambda r: -r["count"])
    novedades = novedades[:limit]

    strong = []
    for cat, c in carlos_by_cat.items():
        n = sum(c.values())
        if n >= carlos_min and pct(c[SentimentLabel.POSITIVE], n) >= carlos_pos_pct:
            city_count = sum(1 for m in current if (m.sentiment.category or "otro") == cat)
            strong.append({"category": cat, "carlos_mentions": n, "carlos_positive_pct": pct(c[SentimentLabel.POSITIVE], n),
                           "city_count": city_count})
    strong.sort(key=lambda r: -r["carlos_mentions"])
    return {"novedades": novedades, "carlos_strong": strong}


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


# ---------- Análisis estadístico de redes (auditoría 2026-09-29) ----------

_WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_HOUR_BLOCKS = [("madrugada", 0, 6), ("mañana", 6, 12), ("tarde", 12, 18), ("noche", 18, 24)]


def _local(ts_iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts_iso).replace(tzinfo=dt.timezone.utc).astimezone(BOGOTA)


def _hour_block(h: int) -> str:
    return next(name for name, a, b in _HOUR_BLOCKS if a <= h < b)


def social_insights(session, days: int = 90, candidate: str = CARLOS, min_n: int = 5) -> dict:
    """Qué le funciona a cada cuenta, medido con ALCANCE RELATIVO: interacción de la publicación
    dividida por la mediana de SU propia cuenta. Así se puede juntar a una cuenta de 600 mil
    seguidores con una de 20 mil sin que la grande domine (1,0 = una publicación típica de esa
    cuenta; 2,0 = el doble de lo habitual).

    Devuelve, para el conjunto de candidatos y concejales y para `candidate`:
      * por formato (reel, carrusel, imagen, video, trino),
      * por día de la semana y por franja horaria (hora Bogotá),
      * por largo del texto,
      * evolución semanal de la mediana de interacción de `candidate` vs. la del resto,
      * ritmo de publicación semanal por cuenta.
    Toda celda trae su n; con menos de `min_n` publicaciones la UI la marca como no concluyente."""
    posts = [p for p in social_posts(session, days=days, limit=100000, sort="recent") if not p["likes_hidden"]]
    by_account: dict[tuple, list[dict]] = defaultdict(list)
    for p in posts:
        by_account[(p["candidate"], p["platform"])].append(p)
    for (_, _), ps in by_account.items():
        base = stats.median([p["engagement"] for p in ps]) or 0
        for p in ps:
            p["rel"] = (p["engagement"] / base) if base > 0 else None

    def group(rows: list[dict], key) -> list[dict]:
        g: dict[str, list[float]] = defaultdict(list)
        for p in rows:
            if p.get("rel") is not None:
                g[key(p)].append(p["rel"])
        out = []
        for k, vals in g.items():
            q = stats.quantiles(vals)
            out.append({"key": k, "n": len(vals), "median_rel": round(q["median"], 2), "q1": round(q["q1"], 2),
                        "q3": round(q["q3"], 2), "conclusive": len(vals) >= min_n})
        return out

    def length_bucket(p):
        n = len(p["text"] or "")
        return "corto (<100)" if n < 100 else "medio (100-300)" if n < 300 else "largo (300-800)" if n < 800 else "muy largo (800+)"

    mine = [p for p in posts if p["candidate"] == candidate]
    order_days = {d: i for i, d in enumerate(_WEEKDAYS)}
    order_blocks = {b[0]: i for i, b in enumerate(_HOUR_BLOCKS)}
    order_len = {"corto (<100)": 0, "medio (100-300)": 1, "largo (300-800)": 2, "muy largo (800+)": 3}

    def dims(rows):
        return {
            "format": sorted(group(rows, lambda p: p["format"]), key=lambda r: -r["median_rel"]),
            "weekday": sorted(group(rows, lambda p: _WEEKDAYS[_local(p["published_at"]).weekday()]),
                              key=lambda r: order_days[r["key"]]),
            "hour_block": sorted(group(rows, lambda p: _hour_block(_local(p["published_at"]).hour)),
                                 key=lambda r: order_blocks[r["key"]]),
            "length": sorted(group(rows, length_bucket), key=lambda r: order_len[r["key"]]),
        }

    # Semana a semana: mediana de interacción de la cuenta vs. mediana del resto de candidatos.
    weekly: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"mine": [], "others": []})
    for p in posts:
        wk = _local(p["published_at"]).strftime("%G-S%V")
        weekly[wk]["mine" if p["candidate"] == candidate else "others"].append(p["engagement"])
    weeks = sorted(weekly)
    cadence = []
    for (cand, platform), ps in by_account.items():
        cadence.append({"candidate": cand, "platform": platform, "posts": len(ps),
                        "posts_per_week": round(len(ps) / (days / 7), 1)})
    cadence.sort(key=lambda r: -r["posts_per_week"])
    views = [p for p in mine if p["views"]]
    return {
        "candidate": candidate, "days": days, "posts_total": len(posts), "posts_candidate": len(mine),
        "all": dims(posts), "candidate_dims": dims(mine),
        "weekly": {"weeks": weeks,
                   "mine": [stats.median(weekly[w]["mine"]) for w in weeks],
                   "mine_n": [len(weekly[w]["mine"]) for w in weeks],
                   "others": [stats.median(weekly[w]["others"]) for w in weeks]},
        "cadence": cadence,
        "engagement_per_view_pct": round(stats.median([p["engagement"] / p["views"] * 100 for p in views]), 1) if len(views) >= 3 else None,
    }


def weekly_conversation(session, days: int = 90, candidate: str = CARLOS) -> dict:
    """Semana a semana: participación de `candidate` en la conversación sobre los candidatos (share
    of voice) y su sentimiento neto con intervalo de confianza.

    Sentimiento neto = % positivas − % negativas sobre las menciones clasificadas de esa semana. El
    intervalo sale de Wilson aplicado a positivas y negativas (conservador); con pocas menciones es
    ancho a propósito: dice que esa semana no permite concluir nada."""
    since = _since(days)
    rows = (session.query(Mention).outerjoin(SentimentScore).join(Candidate)
            .filter(WHEN >= since, Mention.relevant.is_(True), Candidate.kind == "candidate").all())
    total: Counter = Counter()
    mine: Counter = Counter()
    labels: dict[str, Counter] = defaultdict(Counter)
    for m in rows:
        wk = _when(m).replace(tzinfo=dt.timezone.utc).astimezone(BOGOTA).strftime("%G-S%V")
        total[wk] += 1
        if m.candidate.name == candidate:
            mine[wk] += 1
            if m.sentiment:
                labels[wk][m.sentiment.label] += 1
    weeks = sorted(total)
    out = []
    for w in weeks:
        c = labels[w]
        n = sum(c.values())
        pos, neg = c.get(SentimentLabel.POSITIVE, 0), c.get(SentimentLabel.NEGATIVE, 0)
        net = round((pos - neg) / n * 100) if n else None
        pci, nci = stats.wilson(pos, n), stats.wilson(neg, n)
        out.append({"week": w, "mentions": mine[w], "all_mentions": total[w],
                    "share_pct": round(mine[w] / total[w] * 100, 1) if total[w] else 0,
                    "scored": n, "net_sentiment": net,
                    "net_low": round(pci[0] - nci[1]) if n else None,
                    "net_high": round(pci[1] - nci[0]) if n else None})
    return {"candidate": candidate, "weeks": out}
