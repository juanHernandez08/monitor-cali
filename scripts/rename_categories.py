"""Renombra en la base ya guardada las categorías que cambiaron de nombre el 2026-09-30 (pedido
del cliente: nombres más claros). Sin esto, los registros viejos quedarían con el nombre
anterior y el selector de categorías de la pestaña Ciudad los dejaría fuera de la categoría nueva.
Uso: python -m scripts.rename_categories (dentro del contenedor, con DATABASE_URL real)."""
from src.db import get_session
from src.models import SentimentScore

RENAMES = {
    "seguridad": "seguridad y convivencia",
    "salud": "salud pública",
    "empleo y economía": "economía y empleo",
    "medio ambiente y clima": "medioambiente y gestión de riesgo",
}


def main() -> None:
    with get_session() as s:
        total = 0
        for old, new in RENAMES.items():
            n = s.query(SentimentScore).filter(SentimentScore.category == old).update({"category": new})
            print(f"{old!r} -> {new!r}: {n} registros")
            total += n
        s.commit()
        print(f"total renombrados: {total}")


if __name__ == "__main__":
    main()
