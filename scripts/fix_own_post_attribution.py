"""Corrige publicaciones propias (Instagram/Facebook/X) mal atribuidas a otro candidato.

Bug real 2026-09-26: el reel más visto de Carlos Arias ("¿Trincheras en Cali?") empezaba "No
Alfredo Mondragón, nuestro presidente..." -- el titular nombraba a otro candidato completo, así
que `find_matching_candidate` lo atrapaba antes de mirar quién es el dueño real de la cuenta
(`search_term`). Corregido en `pipeline.ingest()` para publicaciones nuevas; este script repara
las que ya quedaron mal atribuidas, usando `config.SOCIAL_ACCOUNTS` como fuente de verdad de a
quién pertenece cada cuenta.

    python -m scripts.fix_own_post_attribution
"""
from src import config
from src.db import get_session, init_db
from src.models import Candidate, Mention, Source, SourceType


def run(session) -> int:
    owner_by_url = {a["url"]: a.get("candidate") for a in config.SOCIAL_ACCOUNTS}
    by_name = {c.name: c for c in session.query(Candidate).all()}
    fixed = 0
    posts = (session.query(Mention).join(Source)
             .filter(Source.type == SourceType.SOCIAL, Mention.raw.op("->>")("kind") == "post").all())
    for m in posts:
        true_owner = owner_by_url.get((m.raw or {}).get("account"))
        if true_owner and m.candidate.name != true_owner and true_owner in by_name:
            m.candidate_id = by_name[true_owner].id
            fixed += 1
    session.commit()
    return fixed


if __name__ == "__main__":
    init_db()
    with get_session() as s:
        n = run(s)
    print(f"listo: {n} publicaciones reatribuidas a su dueño real")
