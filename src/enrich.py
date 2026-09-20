"""Enriquecimiento de menciones de prensa: URL real + cuerpo del artículo.

Google News RSS solo entrega el titular y un link opaco (news.google.com/rss/articles/...).
Antes de clasificar, resolvemos el link, descargamos el artículo y extraemos el texto.
`Mention.body`: None = pendiente, "" = intentado sin éxito, texto = listo.
"""
import logging

from src.models import Mention, Source, SourceType
from src.urlnorm import normalize_url

log = logging.getLogger(__name__)

NEWS_TYPES = (SourceType.GOOGLE_NEWS, SourceType.RSS)
MAX_BODY_CHARS = 6000


def resolve_url(url: str) -> str | None:
    """Convierte un link de Google News en la URL del medio. Devuelve None si falla."""
    if "news.google.com" not in url:
        return url
    from googlenewsdecoder import gnewsdecoder
    try:
        result = gnewsdecoder(url, interval=1)
    except Exception:
        log.exception("gnewsdecoder falló para %s", url)
        return None
    return result.get("decoded_url") if result.get("status") else None


def fetch_body(url: str) -> str | None:
    """Descarga y extrae el texto principal del artículo. None si no se pudo."""
    import trafilatura
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return None
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
    except Exception:
        log.exception("trafilatura falló para %s", url)
        return None
    return text.strip() if text else None


def enrich_pending(session, limit: int = 20) -> int:
    """Enriquece menciones de prensa sin `body`. Devuelve cuántas procesó (incluye fallidas)."""
    pending = (
        session.query(Mention).join(Source)
        .filter(Source.type.in_(NEWS_TYPES), Mention.body.is_(None))
        .order_by(Mention.fetched_at.desc()).limit(limit).all()
    )
    processed = 0
    for mention in pending:
        processed += 1
        if not mention.url:
            mention.body = ""
            session.commit()
            continue

        real_url = resolve_url(mention.url)
        if real_url and real_url != mention.url:
            url_norm = normalize_url(real_url)
            duplicate = (
                session.query(Mention)
                .filter(Mention.url_normalized == url_norm, Mention.id != mention.id).first()
            )
            if duplicate:  # la misma nota ya entró por otra fuente (p. ej. el RSS del medio)
                session.delete(mention)
                session.commit()
                continue
            mention.raw = {**(mention.raw or {}), "google_news_url": mention.url}
            mention.url = real_url
            mention.url_normalized = url_norm

        body = fetch_body(real_url) if real_url else None
        mention.body = (body or "")[:MAX_BODY_CHARS]
        session.commit()
    return processed
