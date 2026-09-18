from src.models import Candidate
from src.matching import all_search_terms_flat, find_matching_candidate


def test_find_matching_candidate_by_alias():
    carlos = Candidate(id=1, name="Carlos Arias", aliases=["@soycarlosaarias", "Buenos Ciudadanos"])
    ana = Candidate(id=2, name="Ana Pérez", aliases=[])

    result = find_matching_candidate("Vi el post de @soycarlosaarias hoy", [carlos, ana])

    assert result is carlos


def test_find_matching_candidate_by_primary_name():
    ana = Candidate(id=2, name="Ana Pérez", aliases=[])
    result = find_matching_candidate("Ana Pérez habló de seguridad", [ana])
    assert result is ana


def test_find_matching_candidate_returns_none_if_no_match():
    ana = Candidate(id=2, name="Ana Pérez", aliases=[])
    result = find_matching_candidate("Texto sin relación", [ana])
    assert result is None


def test_all_search_terms_flat_includes_aliases():
    carlos = Candidate(id=1, name="Carlos Arias", aliases=["@soycarlosaarias"])
    terms = all_search_terms_flat([carlos])

    assert "Carlos Arias" in terms
    assert "@soycarlosaarias" in terms
