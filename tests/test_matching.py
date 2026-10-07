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


def test_is_excluded_matches_homonym_phrases_case_insensitive():
    from src.matching import is_excluded
    carlos = Candidate(id=1, name="Carlos Arias", aliases=[], exclusions=["Arias Orjuela", "Jhon Arias"])
    assert is_excluded("Mauricio Maestre asumirá el cargo que deja Carlos Andrés ARIAS ORJUELA", carlos)
    assert not is_excluded("la mayor Marta Orejuela y el concejal Carlos Andrés Arias Rueda", carlos)
    assert not is_excluded("texto", Candidate(id=2, name="X", aliases=[], exclusions=None))


def _carlos():
    return Candidate(id=1, name="Carlos Arias", aliases=["Carlos Andrés Arias", "@soycarlosaarias", "Buenos Ciudadanos"],
                     exclusions=["Sheynnis", "Juan Carlos Arias"], context_terms=["Cali", "Alcaldía", "Concejo"])


def test_comment_on_homonym_video_is_rejected():
    """Bug real 2026-10-07: el video "¿Habrá boda? Carlos Arias sorprende a Sheynnis Palacios" (un famoso)
    heredó sus comentarios al candidato y salían como menciones negativas suyas."""
    from src.matching import attribution_problem
    raw = {"kind": "comment", "video_title": "😱 ¿Habrá boda? Carlos Arias sorprende a Sheynnis Palacios"}
    assert attribution_problem(_carlos(), "No me parece muy seria esa proposición", raw)


def test_comment_without_local_context_in_video_is_rejected_even_without_exclusion():
    from src.matching import attribution_problem
    raw = {"kind": "comment", "video_title": "Entrevista a Carlos Arias sobre su nueva serie"}
    assert attribution_problem(_carlos(), "qué buena entrevista", raw)


def test_comment_on_candidates_video_is_accepted():
    from src.matching import attribution_problem
    by_context = {"kind": "comment", "video_title": "Carlos Arias presenta su propuesta para Cali"}
    by_alias = {"kind": "comment", "video_title": "El concejal Carlos Andrés Arias Rueda propuso mapear predios"}
    assert attribution_problem(_carlos(), "buena propuesta", by_context) is None
    assert attribution_problem(_carlos(), "buena propuesta", by_alias) is None
    # un comentario que nombra al candidato por sí mismo no depende del video
    assert attribution_problem(_carlos(), "Carlos Arias no me convence", {"kind": "comment", "video_title": "otro tema"}) is None


def test_comment_on_own_account_post_is_always_accepted():
    from src.matching import attribution_problem
    raw = {"kind": "comment", "post_title": "Un mensaje", "account_candidate": "Carlos Arias"}
    assert attribution_problem(_carlos(), "👏👏", raw) is None


def test_video_must_name_the_candidate_and_have_context():
    from src.matching import attribution_problem
    assert attribution_problem(_carlos(), "El tenso momento en que ciudadanos corren al alcalde de Cali", {"kind": "video"})
    assert attribution_problem(_carlos(), "Carlos Arias sorprende a su novia", {"kind": "video"})
    assert attribution_problem(_carlos(), "Carlos Arias, concejal de Cali, habla del terremoto", {"kind": "video"}) is None


def test_candidates_without_context_terms_only_check_exclusions():
    from src.matching import attribution_problem
    ana = Candidate(id=2, name="Ana Pérez", aliases=[], exclusions=["Ana Pérez actriz"], context_terms=[])
    assert attribution_problem(ana, "gran idea", {"kind": "comment", "video_title": "Entrevista a Ana Pérez"}) is None
    assert attribution_problem(ana, "gran idea", {"kind": "comment", "video_title": "Ana Pérez actriz en gala"})
