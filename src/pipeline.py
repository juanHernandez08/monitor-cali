import datetime as dt
import logging
import re
import unicodedata

from src.connectors.base import Connector
from src.matching import (all_search_terms_flat, attribution_problem, find_matching_candidate, find_candidate_by_term,
                          is_excluded)
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from src.models import Candidate, Mention, Run, SentimentLabel, SentimentScore, Source, SourceType
from src.urlnorm import normalize_url

log = logging.getLogger(__name__)


MAX_AGE_DAYS = 60  # menciones más viejas no se guardan (el dashboard muestra hasta 30 días)
CITY_NAME = "Cali (ciudad)"  # candidato especial (kind="city") que recibe la conversación de la ciudad
TITLE_DEDUP_DAYS = 14  # ventana para detectar la misma nota repetida (un ciclo de noticias, no más)

_HANDLE = re.compile(r"@[\w.]+")
_TITLE_JUNK = re.compile(r"[^a-z0-9 ]")
_PRESS_TYPES = (SourceType.GOOGLE_NEWS, SourceType.RSS)
_CITY_NAME_RE = re.compile(r"\bcali\b|\bcaleñ", re.IGNORECASE)  # "Cali" o "caleño/a(s)"


def is_bare_mention(text: str) -> bool:
    """True si el comentario es solo etiquetas a otras cuentas ("@a @b"), sin ningún otro texto."""
    stripped = _HANDLE.sub("", text or "").strip()
    return bool(_HANDLE.search(text or "")) and stripped == ""


def _city_relevance_text(item) -> str:
    """Texto contra el que se evalúa si algo es conversación de Cali. Un comentario casi nunca
    repite el nombre de la ciudad (p. ej. "qué belleza" o "bendiciones") aunque esté respondiendo
    a un video o post que sí es de Cali -- lo relevante ahí es el video/post al que responde, no
    el comentario suelto."""
    raw = item.raw or {}
    if raw.get("kind") == "comment":
        return raw.get("video_title") or raw.get("post_title") or item.text
    return item.text


def mentions_city(item) -> bool:
    """Un medio local o regional también publica notas nacionales o de otros municipios (Buga,
    Tolima, Cauca...) que no tienen nada que ver con Cali -- que la CUENTA sea local no basta,
    hay que exigir que la nota misma nombre la ciudad (pedido del cliente 2026-10-01: "el filtro
    debe hacerlo en cualquier noticia que mencione a Cali")."""
    return bool(_CITY_NAME_RE.search(_city_relevance_text(item) or ""))


def _title_key(text: str) -> str:
    """Encabezado normalizado para reconocer la MISMA nota de prensa capturada dos veces con URLs
    distintas. Google News no siempre da el mismo link para el mismo artículo -- el que devuelve
    depende de qué término de búsqueda lo encontró, así que el dedup por URL (ver ingest) no
    bastaba y la misma nota podía quedar guardada 2 o 3 veces (reporte 2026-09-30)."""
    t = (text or "").split(" - ")[0].strip().lower()  # Google News agrega " - Medio" al final
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return _TITLE_JUNK.sub("", t)[:90]


def ingest(session, source, connector: Connector, max_age_days: int = MAX_AGE_DAYS) -> int:
    """Corre un conector, guarda menciones nuevas SIN score y registra un Run. Nunca lanza."""
    run = Run(source_id=source.id)
    session.add(run)
    session.commit()

    all_active = session.query(Candidate).filter_by(active=True).all()
    # `terms_for: "candidates"` limita la búsqueda a los candidatos (fuentes con cuota, p. ej. YouTube);
    # por defecto se buscan también los concejales (fuentes gratuitas como Google News).
    scope = (source.config or {}).get("terms_for", "all")
    candidates = [c for c in all_active if c.kind != "city" and (scope != "candidates" or c.kind == "candidate")]
    city = next((c for c in all_active if c.kind == "city"), None) if (source.config or {}).get("city") else None
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=max_age_days)
    new_mentions = 0
    # Notas de prensa ya guardadas (cualquier fuente) por candidato en los últimos
    # TITLE_DEDUP_DAYS -- para reconocer la misma nota repetida con una URL distinta (ver
    # _title_key). Se arma una sola vez por corrida, no por cada item.
    seen_titles: dict[int, set[str]] = {}
    if source.type in _PRESS_TYPES:
        title_since = dt.datetime.utcnow() - dt.timedelta(days=TITLE_DEDUP_DAYS)
        when = func.coalesce(Mention.published_at, Mention.fetched_at)
        for cand_id, text in (session.query(Mention.candidate_id, Mention.text).join(Source)
                              .filter(Source.type.in_(_PRESS_TYPES), when >= title_since)):
            seen_titles.setdefault(cand_id, set()).add(_title_key(text))
    try:
        items = connector.fetch(all_search_terms_flat(candidates))
        for item in items:
            if item.published_at and item.published_at < cutoff:
                continue
            if session.query(Mention).filter_by(source_id=source.id, external_id=item.external_id).first():
                continue
            url_norm = normalize_url(item.url)
            is_comment = (item.raw or {}).get("kind") == "comment"
            # Dedup entre fuentes por URL (misma nota vía RSS y Google News). Los comentarios
            # comparten la URL de su post, así que para ellos solo cuenta el external_id.
            if url_norm and not is_comment and session.query(Mention).filter_by(url_normalized=url_norm).first():
                continue
            # Una publicación propia (post/tweet en la cuenta de un candidato) trae en search_term
            # un hecho conocido por el conector -- el dueño de la cuenta -- no una inferencia. Debe
            # ganarle a una mención textual de un tercero en su propio texto (p. ej. un candidato
            # respondiéndole a un rival por su nombre completo en el titular de su propio reel).
            if (item.raw or {}).get("kind") == "post" and source.type == SourceType.SOCIAL:
                candidate = (find_candidate_by_term(item.search_term, candidates)
                             or find_matching_candidate(item.text, candidates))
            else:
                candidate = (find_matching_candidate(item.text, candidates)
                             or find_candidate_by_term(item.search_term, candidates))
            if candidate is not None and is_excluded(item.text, candidate):
                continue
            if candidate is not None and source.type in (SourceType.YOUTUBE, SourceType.SOCIAL)                     and attribution_problem(candidate, item.text, item.raw, source.type.value):
                continue  # homónimo, o el video/post al que responde no es del candidato
            if candidate is None:
                # fuente de ciudad: lo que no nombra a nadie SOLO es conversación de Cali si
                # nombra la ciudad -- si no, es ruido de otro municipio o nacional (ver mentions_city)
                if city is not None and mentions_city(item):
                    candidate = city
                else:
                    continue
            if source.type in _PRESS_TYPES:
                title_key = _title_key(item.text)
                if len(title_key) > 15 and title_key in seen_titles.get(candidate.id, ()):
                    continue
                seen_titles.setdefault(candidate.id, set()).add(title_key)
            session.add(Mention(
                candidate_id=candidate.id, source_id=source.id, external_id=item.external_id,
                url=item.url, url_normalized=url_norm, author=item.author, text=item.text,
                published_at=item.published_at, raw=item.raw,
            ))
            new_mentions += 1
        session.commit()
    except Exception as exc:  # una fuente caída no debe tumbar las demás
        session.rollback()
        log.exception("ingest %s falló", source.name)
        run.error = f"{type(exc).__name__}: {exc}"[:500]
    run.new_mentions = new_mentions
    run.finished_at = dt.datetime.utcnow()
    session.commit()
    return new_mentions


def context_text(mention) -> str:
    """Texto que se manda al LLM, con el contexto que le falta a un comentario suelto (el video o
    el post al que responde). Compartido por score_pending() y scripts/backfill_emotions.py --
    mantenerlos en el mismo lugar evita que uno se corrija y el otro se quede desactualizado."""
    raw = mention.raw or {}
    text = f"{mention.text}\n\n{mention.body}" if mention.body else mention.text
    if raw.get("video_title"):  # comentario de YouTube: el título del video da el contexto
        return f"[Comentario en el video: {raw['video_title']}]\n{text}"
    if raw.get("post_title"):  # comentario de Instagram/Facebook: el post da el contexto
        if raw.get("account_candidate") == mention.candidate.name:
            return (f"[Comentario en una publicación del propio candidato {mention.candidate.name}: "
                    f"{raw['post_title']}] (aplausos, gracias o apoyo hacia {mention.candidate.name} aquí "
                    f"son POSITIVOS; críticas o burlas hacia {mention.candidate.name} son NEGATIVAS; no es "
                    f"tangencial; OJO: si el insulto o rechazo del comentario va hacia un tercero nombrado "
                    f"en la publicación -no hacia {mention.candidate.name}-, eso NO es negativo para "
                    f"{mention.candidate.name} -- evalúa si el comentario apoya o no la publicación de "
                    f"{mention.candidate.name}, normalmente POSITIVO aunque el lenguaje contra ese tercero "
                    f"sea agresivo)\n{text}")
        return f"[Comentario en la publicación: {raw['post_title']}]\n{text}"
    return text


def score_pending(session, engine, limit: int = 20) -> int:
    """Clasifica menciones sin SentimentScore, en lotes. Devuelve cuántas clasificó."""
    pending = (
        session.query(Mention).join(Source, Mention.source_id == Source.id)
        .outerjoin(SentimentScore, SentimentScore.mention_id == Mention.id)
        .filter(SentimentScore.id.is_(None))
        # Google News solo trae el titular: esperar a que enrich_pending traiga el cuerpo.
        .filter(or_(Source.type != SourceType.GOOGLE_NEWS, Mention.body.isnot(None)))
        .order_by(Mention.fetched_at.desc())
        .limit(limit)
        .all()
    )
    scored = 0
    for mention in pending:
        raw = mention.raw or {}
        is_city = mention.candidate.kind == "city"
        if not is_city and (is_excluded(f"{mention.text} {mention.body or ''}", mention.candidate)
                            or attribution_problem(mention.candidate, mention.text, raw, mention.source.type.value)):
            mention.relevant = False
            session.add(SentimentScore(mention_id=mention.id, label=SentimentLabel.NEUTRAL, score=0.0,
                                       topic="homónimo", model="regla"))
            session.commit()
            scored += 1
            continue
        if raw.get("kind") == "comment" and is_bare_mention(mention.text):
            # "@alguien" sin texto: no expresa nada; no gastar modelo ni contarlo.
            mention.relevant = False
            session.add(SentimentScore(mention_id=mention.id, label=SentimentLabel.NEUTRAL, score=0.0,
                                       topic="etiqueta a otra cuenta", model="regla"))
            session.commit()
            scored += 1
            continue
        text = context_text(mention)
        try:
            result = engine.score(text, candidate=mention.candidate.name, city=is_city)
        except Exception:
            log.exception("score falló para mention %s", mention.id)
            break  # Ollama caído: reintentar en el próximo ciclo
        topic = (result.topic or "").lower()
        is_comment = (mention.raw or {}).get("kind") == "comment"
        # Homónimo → fuera. Un comentario "tangencial" habla del video, no del candidato → fuera.
        # Una nota de prensa tangencial sí menciona al candidato → se conserva.
        own_post = is_comment and raw.get("account_candidate") == mention.candidate.name
        if "homónimo" in topic or "homonimo" in topic or (is_comment and not own_post and "tangencial" in topic):
            mention.relevant = False
        session.add(SentimentScore(mention_id=mention.id, label=result.label, score=result.score,
                                   topic=result.topic, model=result.model,
                                   category=getattr(result, "category", None),
                                   summary=getattr(result, "summary", None) or None,
                                   emotion=getattr(result, "emotion", None) or None,
                                   # "" (no "" -> None) para nuance/apalancador: distingue "ya se
                                   # clasificó y no aplica" (emoción neutra) de "aún sin clasificar"
                                   # (None) -- si no, backfill_emotions.py reprocesaría sin parar
                                   # cada mención neutra, que siempre vuelve a salir vacía.
                                   emotion_nuance=getattr(result, "emotion_nuance", ""),
                                   apalancador=getattr(result, "apalancador", "")))
        try:
            session.commit()
        except IntegrityError:  # otro proceso (el scheduler del servidor) ya la clasificó
            session.rollback()
            continue
        scored += 1
    return scored


def run_pipeline(session, source, connector: Connector, sentiment_engine) -> int:
    """Compatibilidad: ingesta + scoring en un paso."""
    count = ingest(session, source, connector)
    score_pending(session, sentiment_engine, limit=max(count, 1))
    return count
