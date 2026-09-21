import datetime as dt
import logging
import re

from src.connectors.base import Connector
from src.matching import all_search_terms_flat, find_matching_candidate, find_candidate_by_term, is_excluded
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from src.models import Candidate, Mention, Run, SentimentLabel, SentimentScore, Source, SourceType
from src.urlnorm import normalize_url

log = logging.getLogger(__name__)


MAX_AGE_DAYS = 60  # menciones más viejas no se guardan (el dashboard muestra hasta 30 días)

_HANDLE = re.compile(r"@[\w.]+")


def is_bare_mention(text: str) -> bool:
    """True si el comentario es solo etiquetas a otras cuentas ("@a @b"), sin ningún otro texto."""
    stripped = _HANDLE.sub("", text or "").strip()
    return bool(_HANDLE.search(text or "")) and stripped == ""


def ingest(session, source, connector: Connector, max_age_days: int = MAX_AGE_DAYS) -> int:
    """Corre un conector, guarda menciones nuevas SIN score y registra un Run. Nunca lanza."""
    run = Run(source_id=source.id)
    session.add(run)
    session.commit()

    candidates = session.query(Candidate).filter_by(active=True).all()
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=max_age_days)
    new_mentions = 0
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
            candidate = (find_matching_candidate(item.text, candidates)
                         or find_candidate_by_term(item.search_term, candidates))
            if candidate is None or is_excluded(item.text, candidate):
                continue
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
        if is_excluded(f"{mention.text} {mention.body or ''}", mention.candidate):
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
        text = f"{mention.text}\n\n{mention.body}" if mention.body else mention.text
        if raw.get("video_title"):  # comentario de YouTube: el título del video da el contexto
            text = f"[Comentario en el video: {raw['video_title']}]\n{text}"
        elif raw.get("post_title"):  # comentario de Instagram/Facebook: el post da el contexto
            if raw.get("account_candidate") == mention.candidate.name:
                text = (f"[Comentario en una publicación del propio candidato {mention.candidate.name}: "
                        f"{raw['post_title']}] (aplausos, gracias o apoyo aquí son POSITIVOS hacia él; "
                        f"críticas o burlas son NEGATIVAS; no es tangencial)\n{text}")
            else:
                text = f"[Comentario en la publicación: {raw['post_title']}]\n{text}"
        try:
            result = engine.score(text, candidate=mention.candidate.name)
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
                                   topic=result.topic, model=result.model))
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
