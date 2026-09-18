from src.config import CANDIDATES, RSS_SOURCES
from src.db import init_db, get_session
from src.models import Candidate, Source, SourceType


def seed(session):
    for c in CANDIDATES:
        if not session.query(Candidate).filter_by(name=c["name"]).first():
            session.add(Candidate(
                name=c["name"], party=c.get("party"), aliases=c.get("aliases", []),
            ))
    for s in RSS_SOURCES:
        exists = session.query(Source).filter_by(
            type=SourceType.RSS, name=s["name"],
        ).first()
        if not exists:
            session.add(Source(
                type=SourceType.RSS, name=s["name"], config={"feed_url": s["url"]},
            ))
    session.commit()


if __name__ == "__main__":
    init_db()
    with get_session() as session:
        seed(session)
