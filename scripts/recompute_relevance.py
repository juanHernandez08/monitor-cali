"""Recalcula `Mention.relevant` con las reglas vigentes, por tipo de fuente.

Úsalo después de cambiar alias, exclusiones o contexto en `config.py`. Las reglas de prensa
(nombrar al candidato, contexto local) NO aplican a redes: ahí la atribución viene de la cuenta.

    python -m scripts.recompute_relevance
"""
from src.db import get_session, init_db
from src.matching import attribution_problem, has_required_context, is_excluded, mentions_candidate
from src.models import Candidate, SourceType

PRESS = (SourceType.GOOGLE_NEWS, SourceType.RSS)


def is_relevant(mention, candidate) -> bool:
    raw = mention.raw or {}
    topic = (mention.sentiment.topic or "").lower() if mention.sentiment else ""
    # El LLM puede reconocer un homónimo aunque el texto nombre literalmente al candidato (por
    # eso "exclusions" no lo atrapó) y aunque body/contexto local estén presentes. pipeline.py
    # aplica esta señal en vivo sin importar el tipo de fuente; recompute debe hacer lo mismo,
    # antes de las reglas específicas de prensa o redes.
    if "homónimo" in topic or "homonimo" in topic or topic == "etiqueta a otra cuenta":
        return False
    if mention.source.type in PRESS:
        blob = f"{mention.text} {mention.body or ''}"
        if is_excluded(blob, candidate):
            return False
        if mention.body is None:  # aún no se intentó enriquecer: se resolverá luego
            return True
        # body == "" (se intentó y no se pudo) cuenta igual que tener cuerpo: exigir
        # nombre/contexto sobre lo que sí tenemos (el titular), no darlo por bueno para siempre.
        return has_required_context(blob, candidate) and mentions_candidate(blob, candidate)
    if is_excluded(mention.text, candidate):
        return False
    if attribution_problem(candidate, mention.text, raw, mention.source.type.value):
        return False  # homónimo en el video/post, o el video/post no es del candidato (matching.py)
    is_comment = raw.get("kind") == "comment"
    own_post = is_comment and raw.get("account_candidate") == candidate.name
    if is_comment and not own_post and "tangencial" in topic:
        return False
    if mention.source.type == SourceType.YOUTUBE and is_comment:
        # El video hereda al candidato solo si el título/descripción lo nombran; si no, el
        # comentario solo cuenta si él mismo lo nombra. No depende de si el LLM etiquetó el tema
        # como "tangencial" arriba: un comentario puede ser un insulto o un dato ("magnitud 7.4")
        # sin que el LLM lo marque tangencial, aunque hable de un video que no es sobre el candidato.
        video_named = raw.get("video_about_candidate")
        if video_named is None:  # dato de antes de guardar esta marca: recalcular contra el título
            video_named = mentions_candidate(raw.get("video_title") or "", candidate)
        if not video_named and not mentions_candidate(mention.text, candidate):
            return False
    return True


def recompute(session, only_council: bool = False) -> tuple[int, int]:
    q = session.query(Candidate)
    if only_council:
        q = q.filter_by(council=True)
    restored = dropped = 0
    for c in q:
        if c.kind == "city":
            continue
        for m in c.mentions:
            ok = is_relevant(m, c)
            restored += ok and not m.relevant
            dropped += m.relevant and not ok
            m.relevant = ok
    session.commit()
    return restored, dropped


if __name__ == "__main__":
    init_db()
    with get_session() as s:
        print("restauradas: %d | descartadas: %d" % recompute(s))
