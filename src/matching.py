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
