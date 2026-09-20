from src.config import CANDIDATES, RSS_SOURCES
from src.models import Candidate, Source, SourceType
from scripts.seed_sources import seed, EXTRA_SOURCES


def test_seed_creates_candidates_and_all_sources(db_session):
    seed(db_session)
    assert db_session.query(Candidate).count() == len(CANDIDATES)
    assert db_session.query(Source).count() == len(RSS_SOURCES) + len(EXTRA_SOURCES)
    assert db_session.query(Source).filter_by(type=SourceType.GOOGLE_NEWS).count() == 1


def test_seed_is_idempotent(db_session):
    seed(db_session)
    seed(db_session)
    assert db_session.query(Candidate).count() == len(CANDIDATES)
    assert db_session.query(Source).count() == len(RSS_SOURCES) + len(EXTRA_SOURCES)


def test_seed_includes_carlos_with_aliases(db_session):
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").first()
    assert "@soycarlosaarias" in carlos.aliases
