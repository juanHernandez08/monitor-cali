"""Reclasifica la emoción de menciones que quedaron con una emoción retirada de sentiment.EMOTIONS:
"anticipación" (2026-09-28) y ahora también "alegría", "confianza" y "orgullo" (2026-09-29, al
alinear la taxonomía con la rueda de emociones del cliente -- "sorpresa" vuelve a ser válida).
No toca label, score, topic, category ni summary ya guardados -- solo pide al LLM una
emoción y un matiz nuevos, que ahora saldrán forzosamente de la lista vigente.

    python -m scripts.reclassify_retired_emotions
"""
import logging

from src.db import get_session, init_db
from src.models import Mention, SentimentScore
from src.pipeline import context_text
from src.sentiment import build_sentiment_engine

log = logging.getLogger(__name__)
RETIRED_EMOTIONS = ("anticipación", "alegría", "confianza", "orgullo")


def run(session, engine) -> int:
    pending = (
        session.query(Mention).join(SentimentScore)
        .filter(SentimentScore.emotion.in_(RETIRED_EMOTIONS))
        .order_by(Mention.id)
        .all()
    )
    done = 0
    for mention in pending:
        is_city = mention.candidate.kind == "city"
        try:
            result = engine.score(context_text(mention), candidate=mention.candidate.name, city=is_city)
        except Exception:
            log.exception("reclasificación de emoción falló para mention %s", mention.id)
            continue
        mention.sentiment.emotion = getattr(result, "emotion", None) or "sin emoción marcada"
        mention.sentiment.emotion_nuance = getattr(result, "emotion_nuance", "")
        mention.sentiment.apalancador = getattr(result, "apalancador", "")
        done += 1
        session.commit()
    return done


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    with get_session() as s:
        n = run(s, build_sentiment_engine())
    print(f"listo: {n} menciones reclasificadas")
