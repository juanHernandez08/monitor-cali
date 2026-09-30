"""Limpia las etiquetas HTML (<p>, <a href=...>) que quedaron guardadas en mentions.text antes
del arreglo de 2026-09-30 en los conectores RSS (Google News, RSS genérico, Reddit RSS) -- solo
afecta a los registros ya guardados; los nuevos ya entran limpios. Uso: python -m
scripts.backfill_strip_html (dentro del contenedor, con DATABASE_URL apuntando a la base real)."""
from src.connectors.base import strip_html
from src.db import get_session
from src.models import Mention


def main() -> None:
    with get_session() as s:
        rows = s.query(Mention).filter(Mention.text.contains("<")).all()
        changed = 0
        for m in rows:
            cleaned = strip_html(m.text)
            if cleaned != m.text:
                m.text = cleaned
                changed += 1
        s.commit()
        print(f"revisados: {len(rows)} -- limpiados: {changed}")


if __name__ == "__main__":
    main()
