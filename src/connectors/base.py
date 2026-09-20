from dataclasses import dataclass, field
from typing import Protocol
import datetime as dt


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
