"""Recalcula `Mention.relevant` con las reglas vigentes, por tipo de fuente.

Úsalo después de cambiar alias, exclusiones o contexto en `config.py`. Las reglas de prensa
(nombrar al candidato, contexto local) NO aplican a redes: ahí la atribución viene de la cuenta.

    python -m scripts.recompute_relevance
"""
from src.db import get_session, init_db
from src.matching import has_required_context, is_excluded, mentions_candidate
from src.models import Candidate, SourceType

PRESS = (SourceType.GOOGLE_NEWS, SourceType.RSS)


def is_relevant(mention, candidate) -> bool:
    raw = mention.raw or {}
    topic = (mention.sentiment.topic or "").lower() if mention.sentiment else ""
    if mention.source.type in PRESS:
        blob = f"{mention.text} {mention.body or ''}"
        if is_excluded(blob, candidate):
            return False
        if mention.body:  # con el cuerpo ya se puede exigir contexto y nombre
            return has_required_context(blob, candidate) and mentions_candidate(blob, candidate)
        return True
    if is_excluded(mention.text, candidate):
        return False
    is_comment = raw.get("kind") == "comment"
    own_post = is_comment and raw.get("account_candidate") == candidate.name
    if "homónimo" in topic or "homonimo" in topic or topic == "etiqueta a otra cuenta":
        return False
    if is_comment and not own_post and "tangencial" in topic:
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
