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


def has_required_context(text: str, candidate: Candidate) -> bool:
    """True si el texto trae el contexto exigido por el candidato (p. ej. "Cali" o "Concejo").

    Los nombres de los concejales son comunes ("Carlos Patiño" también es un frente armado del
    Cauca); sin una palabra de contexto local la mención no es de ellos.
    """
    terms = candidate.context_terms or []
    if not terms:
        return True
    lowered = (text or "").lower()
    return any(t.lower() in lowered for t in terms)


def _specific_aliases(candidate: Candidate) -> list[str]:
    """Alias que no se confunden con un homónimo: el nombre largo ("Carlos Andrés Arias", 3 o más
    palabras) o un @usuario. "Buenos Ciudadanos" o el nombre corto no sirven de prueba."""
    return [a for a in (candidate.aliases or []) if a.startswith("@") or len(a.split()) >= 3]


def parent_confirms(parent_text: str, candidate: Candidate) -> bool:
    """True si el video/post al que responde un comentario (o el propio video) es de ESTE candidato.

    "Carlos Arias" también es un famoso que sale con una reina de belleza: un video sobre él no
    nombra Cali, el Concejo ni la Alcaldía, pero sus comentarios heredaban al candidato solo por
    el nombre. Se exige el contexto local del candidato (context_terms) o un alias específico. Sin
    context_terms configurados no hay nada que exigir."""
    if not candidate.context_terms:
        return True
    lowered = (parent_text or "").lower()
    if has_required_context(parent_text, candidate):
        return True
    return any(a.lower() in lowered for a in _specific_aliases(candidate))


def attribution_problem(candidate: Candidate, text: str, raw: dict | None, source_type: str | None = None) -> str | None:
    """Motivo por el que una mención de YouTube/redes NO es del candidato, o None si es válida.

    Reglas deterministas (una sola función para el ingreso, la clasificación y el script que limpia
    lo ya guardado):
      * una frase de homónimo en el texto, o en el video/post al que responde un comentario;
      * un comentario que no nombra al candidato y cuyo video/post no es de él (ver parent_confirms);
      * un video de YouTube que ni nombra al candidato ni trae su contexto local.
    Los comentarios en la publicación de la propia cuenta del candidato valen siempre."""
    if getattr(candidate, "kind", None) == "city":
        return None
    raw = raw or {}
    kind = raw.get("kind")
    parent = raw.get("video_context") or raw.get("video_title") or raw.get("post_title") or ""
    own_post = raw.get("account_candidate") == candidate.name
    if is_excluded(text, candidate):
        return "homónimo"
    if kind == "comment" and parent and not own_post:
        if is_excluded(parent, candidate):
            return "homónimo en el video o publicación"
        if (getattr(candidate, "strict_attribution", False) and not mentions_candidate(text, candidate)
                and not parent_confirms(parent, candidate)):
            return "el video o publicación no es del candidato"
    if kind == "video" and getattr(candidate, "strict_attribution", False):
        if not mentions_candidate(text, candidate):
            return "el video no nombra al candidato"
        if is_excluded(text, candidate) or not parent_confirms(text, candidate):
            return "el video no es del candidato"
    return None
