from src.models import Candidate


def all_search_terms(candidate: Candidate) -> list[str]:
    return [candidate.name, *(candidate.aliases or [])]


def all_search_terms_flat(candidates: list[Candidate]) -> list[str]:
    terms: list[str] = []
    for candidate in candidates:
        terms.extend(all_search_terms(candidate))
    return terms


def find_matching_candidate(text: str, candidates: list[Candidate]) -> Candidate | None:
    lowered = text.lower()
    for candidate in candidates:
        if any(term.lower() in lowered for term in all_search_terms(candidate)):
            return candidate
    return None


def find_candidate_by_term(term: str | None, candidates: list[Candidate]) -> Candidate | None:
    """Atribuye por el término de búsqueda que produjo el item (p. ej. comentarios de YouTube)."""
    if not term:
        return None
    lowered = term.lower()
    for candidate in candidates:
        if any(t.lower() == lowered for t in all_search_terms(candidate)):
            return candidate
    return None


def is_excluded(text: str, candidate: Candidate) -> bool:
    """True si el texto contiene una frase de exclusión del candidato (homónimo conocido)."""
    lowered = (text or "").lower()
    return any(phrase.lower() in lowered for phrase in (candidate.exclusions or []))


def mentions_candidate(text: str, candidate: Candidate) -> bool:
    """True si el texto contiene el nombre del candidato o alguno de sus alias."""
    lowered = (text or "").lower()
    return any(term.lower() in lowered for term in all_search_terms(candidate))
