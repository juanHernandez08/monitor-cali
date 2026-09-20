"""Enriquece y clasifica todo lo pendiente hasta vaciar la cola. Uso: python -m scripts.score_all"""
import logging

from src.db import get_session
from src.enrich import enrich_pending
from src.pipeline import score_pending
from src.sentiment import build_sentiment_engine

logging.basicConfig(level=logging.WARNING)

if __name__ == "__main__":
    engine = build_sentiment_engine()
    with get_session() as s:
        while enrich_pending(s, limit=20):
            pass
        total = 0
        while (n := score_pending(s, engine, limit=20)):
            total += n
            print(f"clasificadas {total}", flush=True)
    print("FIN", total)
