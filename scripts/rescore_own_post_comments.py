"""Reclasifica comentarios en publicaciones propias con el prompt corregido (2026-09-26).

Bug real reportado por el cliente: un comentario insultando a un tercero nombrado en la propia
publicación de un candidato (p. ej. "MONDRAGON TRAPO SUCIO" en un post de Carlos Arias titulado
"No Alfredo Mondragón...") se clasificaba como NEGATIVO hacia el candidato -- disparaba alertas
falsas -- porque la instrucción no distinguía hacia quién iba el insulto. Corregido en
`pipeline.context_text()`; este script reclasifica (label/score/topic/summary/emotion, todo) los
comentarios en publicaciones propias ya puntuados con el prompt viejo.

    python -m scripts.rescore_own_post_comments
"""
import logging

from src.db import get_session, init_db
from src.models import Mention, SentimentScore
from src.pipeline import context_text
from src.sentiment import build_sentiment_engine

log = logging.getLogger(__name__)


def run(session, engine, limit: int | None = None) -> int:
    q = (session.query(Mention).join(SentimentScore)
         .filter(Mention.raw.op("->>")("kind") == "comment")
         .order_by(Mention.id))
    own_post = [m for m in q.all() if (m.raw or {}).get("account_candidate") == m.candidate.name]
    if limit is not None:
        own_post = own_post[:limit]
    done = 0
    for mention in own_post:
        try:
            result = engine.score(context_text(mention), candidate=mention.candidate.name, city=False)
        except Exception:
            log.exception("rescore falló para mention %s", mention.id)
            return done
        sc = mention.sentiment
        sc.label, sc.score, sc.topic = result.label, result.score, result.topic
        sc.category = getattr(result, "category", None)
        sc.summary = getattr(result, "summary", None) or None
        sc.emotion = getattr(result, "emotion", None) or None
        done += 1
        session.commit()
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    with get_session() as s:
        n = run(s, build_sentiment_engine())
    print(f"listo: {n} comentarios de publicaciones propias reclasificados")
