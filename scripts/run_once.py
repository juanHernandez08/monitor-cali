"""Ingesta + scoring manual: python -m scripts.run_once [--no-score]"""
import logging
import sys

from src.db import init_db, get_session
from src.enrich import enrich_pending
from src.pipeline import score_pending
from src.scheduler import run_everything
from src.sentiment import build_sentiment_engine
from scripts.seed_sources import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    init_db()
    with get_session() as s:
        seed(s)
    run_everything()
    if "--no-score" not in sys.argv:
        engine = build_sentiment_engine()
        with get_session() as s:
            while enrich_pending(s, limit=20):
                pass
            while score_pending(s, engine, limit=20):
                pass
