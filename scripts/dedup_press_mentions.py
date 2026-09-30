"""Elimina notas de prensa YA GUARDADAS por duplicado (mismo titular, mismo candidato/ciudad).

El dedup por título se agregó en ingest() el 2026-09-30 (ver src/pipeline.py:_title_key), pero
solo evita duplicados NUEVOS a partir de ese momento -- esto limpia los que ya estaban guardados
(frecuente con Google News: el mismo artículo llega con un link de redirección distinto según qué
término de búsqueda lo encontró, así que el dedup por URL no los atrapaba). Se queda con la copia
más vieja de cada grupo (la que se capturó primero) y borra el resto, junto con su clasificación.

Uso: python -m scripts.dedup_press_mentions (dentro del contenedor, con DATABASE_URL real).
"""
import datetime as dt
from collections import defaultdict

from src.db import get_session
from src.models import Mention, SentimentScore, Source, SourceType
from src.pipeline import _title_key


def main() -> None:
    with get_session() as s:
        rows = (s.query(Mention).join(Source)
                .filter(Source.type.in_((SourceType.GOOGLE_NEWS, SourceType.RSS))).all())
        groups: dict[tuple[int, str], list[Mention]] = defaultdict(list)
        for m in rows:
            key = _title_key(m.text)
            if len(key) > 15:
                groups[(m.candidate_id, key)].append(m)
        deleted = 0
        for ms in groups.values():
            if len(ms) < 2:
                continue
            ms.sort(key=lambda m: m.fetched_at or dt.datetime.min)
            keep, *dupes = ms
            for d in dupes:
                s.query(SentimentScore).filter_by(mention_id=d.id).delete()
                s.delete(d)
                deleted += 1
        s.commit()
        print(f"grupos con duplicados: {sum(1 for ms in groups.values() if len(ms) > 1)} -- eliminados: {deleted}")


if __name__ == "__main__":
    main()
