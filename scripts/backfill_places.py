"""Calcula la zona (comuna, barrio, corregimiento, vereda, municipio) de todas las menciones relevantes
ya guardadas -- las nuevas la reciben solas al clasificarse (pipeline.score_pending). Idempotente:
volver a correrlo recalcula todo con el diccionario actual (p. ej. tras agregar alias).

Uso: python scripts/backfill_places.py"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import SessionLocal, init_db  # noqa: E402
from src.geo import assign_places  # noqa: E402
from src.models import Mention  # noqa: E402


def main():
    init_db()
    s = SessionLocal()
    ids = [i for (i,) in s.query(Mention.id).filter(Mention.relevant.is_(True)).all()]
    counts = collections.Counter()
    for k in range(0, len(ids), 500):
        for m in s.query(Mention).filter(Mention.id.in_(ids[k:k + 500])).all():
            n = assign_places(s, m)
            counts["con_lugar" if n else "sin_lugar"] += 1
        s.commit()
    print(f"{len(ids)} menciones: {counts['con_lugar']} con algún lugar, {counts['sin_lugar']} sin lugar")


if __name__ == "__main__":
    main()
