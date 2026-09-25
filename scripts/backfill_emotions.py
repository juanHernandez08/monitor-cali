"""Rellena la "emotion" de menciones ya clasificadas antes de que ese campo existiera.

Solo agrega la emoción a SentimentScore.emotion cuando está vacía; no toca label, score,
topic, category ni summary ya guardados -- el resto del análisis ya fue revisado por el
cliente y no hay que arriesgarlo.

    python -m scripts.backfill_emotions              # todo lo pendiente
    python -m scripts.backfill_emotions --limit 200   # una tanda
"""
import argparse
import logging

from src.db import get_session, init_db
from src.models import Mention, SentimentScore
from src.pipeline import context_text
from src.sentiment import build_sentiment_engine

log = logging.getLogger(__name__)


def run(session, engine, limit: int | None = None, batch: int = 1) -> int:
    """Clasifica la emoción de menciones ya puntuadas que aún no la tienen. Devuelve cuántas.

    batch=1: confirma cada mención por separado. El servidor web escribe a la misma base de
    datos cada pocos minutos; con WAL (ver src/db.py) ya no debería chocar, pero mantener la
    transacción abierta el menor tiempo posible mientras Ollama piensa (varios segundos) es
    una segunda capa de seguridad barata.
    """
    done = 0
    while limit is None or done < limit:
        take = batch if limit is None else min(batch, limit - done)
        pending = (
            session.query(Mention).join(SentimentScore)
            .filter(SentimentScore.emotion.is_(None))
            .order_by(Mention.id)
            .limit(take)
            .all()
        )
        if not pending:
            break
        for mention in pending:
            is_city = mention.candidate.kind == "city"
            try:
                result = engine.score(context_text(mention), candidate=mention.candidate.name, city=is_city)
            except Exception:
                log.exception("backfill de emoción falló para mention %s", mention.id)
                return done  # Ollama caído u otro fallo: parar aquí, reintentar más tarde
            mention.sentiment.emotion = getattr(result, "emotion", None) or "sin emoción marcada"
            done += 1
        session.commit()
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    init_db()
    with get_session() as s:
        n = run(s, build_sentiment_engine(), limit=args.limit)
    print(f"listo: {n} menciones con emoción nueva")
