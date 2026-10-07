from src.config import (CANDIDATES, RSS_SOURCES, CITY_SOURCES, COUNCILORS, COUNCIL_ALSO_CANDIDATES,
                        COUNCIL_CONTEXT)
from src.db import init_db, get_session
from src.models import Candidate, Source, SourceType
from src.pipeline import CITY_NAME

EXTRA_SOURCES = [
    {"type": SourceType.GOOGLE_NEWS, "name": "Google News", "config": {}},
    {"type": SourceType.REDDIT, "name": "Reddit", "config": {"via": "rss"}},
    {"type": SourceType.GOOGLE_CSE, "name": "Instagram / Facebook / X (Google)", "config": {}},
    # YouTube cuesta 100 unidades por término (cuota 10.000/día): solo candidatos.
    {"type": SourceType.YOUTUBE, "name": "YouTube", "config": {"terms_for": "candidates"}},
    # city=True: cuentas de medios sin candidato asociado (p. ej. noticalioficial, candidate=None
    # en config.SOCIAL_ACCOUNTS) deben caer en la conversación de ciudad, no perderse. Bug real
    # 2026-09-30: sin esto, ingest() las descartaba en silencio (candidate=None y sin bandera
    # "city" en la fuente = ninguna a dónde atribuirlas) y la pestaña Ciudad nunca mostraba
    # publicaciones de Instagram/Facebook/X.
    {"type": SourceType.SOCIAL, "name": "Instagram / Facebook (cuentas)", "config": {"city": True}},
]


def seed(session):
    for c in CANDIDATES:
        row = session.query(Candidate).filter_by(name=c["name"]).first()
        if row is None:
            session.add(Candidate(
                name=c["name"], party=c.get("party"), aliases=c.get("aliases", []),
                exclusions=c.get("exclusions", []), context_terms=c.get("context_terms", []),
                strict_attribution=c.get("strict_attribution", False),
            ))
        else:  # config.py es la fuente de verdad de alias, exclusiones, contexto y partido
            row.aliases = c.get("aliases", [])
            row.exclusions = c.get("exclusions", [])
            row.context_terms = c.get("context_terms", [])
            row.strict_attribution = c.get("strict_attribution", False)
            row.party = c.get("party")
    for c in COUNCILORS:
        row = session.query(Candidate).filter_by(name=c["name"]).first()
        if row is None:
            session.add(Candidate(name=c["name"], party=c["party"], aliases=c.get("aliases", []),
                                  exclusions=c.get("exclusions", []), kind="councilor", council=True,
                                  context_terms=list(COUNCIL_CONTEXT)))
        else:
            row.aliases, row.party, row.kind, row.council = c.get("aliases", []), c["party"], "councilor", True
            row.exclusions, row.context_terms = c.get("exclusions", []), list(COUNCIL_CONTEXT)
    for name, party in COUNCIL_ALSO_CANDIDATES.items():  # candidatos que además son concejales
        row = session.query(Candidate).filter_by(name=name).first()
        if row is not None:
            row.council = True
            row.party = row.party or party
    if not session.query(Candidate).filter_by(name=CITY_NAME).first():
        session.add(Candidate(name=CITY_NAME, kind="city", aliases=[], exclusions=[]))
    for s in RSS_SOURCES:
        exists = session.query(Source).filter_by(
            type=SourceType.RSS, name=s["name"],
        ).first()
        city = bool(s.get("city", False))
        if not exists:
            session.add(Source(type=SourceType.RSS, name=s["name"], config={"feed_url": s["url"], "city": city}))
        elif (exists.config or {}).get("city") != city:  # config.py es la fuente de verdad
            exists.config = {**(exists.config or {}), "city": city}
    for s in CITY_SOURCES:
        if not session.query(Source).filter_by(type=SourceType(s["type"]), name=s["name"]).first():
            session.add(Source(type=SourceType(s["type"]), name=s["name"], config=s["config"]))
    for s in EXTRA_SOURCES:
        exists = session.query(Source).filter_by(type=s["type"], name=s["name"]).first()
        if not exists:
            session.add(Source(type=s["type"], name=s["name"], config=s["config"]))
        elif exists.config != s["config"]:  # este archivo es la fuente de verdad del config
            exists.config = s["config"]
    session.commit()


if __name__ == "__main__":
    init_db()
    with get_session() as session:
        seed(session)
