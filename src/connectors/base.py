import html
import re
from dataclasses import dataclass, field
from typing import Protocol
import datetime as dt

_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Quita etiquetas HTML (<p>, <a href=...>, etc.) y decodifica entidades (&quot;, &amp;...).

    Varios feeds RSS (no Google News, que ya venía limpio) meten el resumen completo en HTML --
    sin esto, el texto de la publicación mostraba las etiquetas crudas (reporte 2026-09-30)."""
    return html.unescape(_TAG.sub(" ", text or "")).strip()


@dataclass
class RawItem:
    external_id: str
    text: str
    url: str | None = None
    author: str | None = None
    published_at: dt.datetime | None = None
    raw: dict = field(default_factory=dict)
    search_term: str | None = None  # término que produjo el item (para atribuir candidato)


class Connector(Protocol):
    source_name: str

    def fetch(self, search_terms: list[str]) -> list[RawItem]:
        """Devuelve los items nuevos que contienen alguno de los términos de búsqueda."""
        ...
