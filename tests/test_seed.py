from src.config import CANDIDATES, RSS_SOURCES, COUNCILORS
from src.models import Candidate, Source, SourceType
from scripts.seed_sources import seed, EXTRA_SOURCES


def test_seed_creates_candidates_and_all_sources(db_session):
    seed(db_session)
    assert db_session.query(Candidate).count() == len(CANDIDATES) + len(COUNCILORS) + 1  # + concejales + Cali (ciudad)
    assert db_session.query(Source).count() == len(RSS_SOURCES) + len(EXTRA_SOURCES) + 2  # + fuentes de ciudad
    assert db_session.query(Source).filter_by(type=SourceType.GOOGLE_NEWS).count() == 2  # candidatos + ciudad


def test_seed_is_idempotent(db_session):
    seed(db_session)
    seed(db_session)
    assert db_session.query(Candidate).count() == len(CANDIDATES) + len(COUNCILORS) + 1  # + concejales + Cali (ciudad)
    assert db_session.query(Source).count() == len(RSS_SOURCES) + len(EXTRA_SOURCES) + 2  # + fuentes de ciudad


def test_seed_includes_carlos_with_aliases(db_session):
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").first()
    assert "@soycarlosaarias" in carlos.aliases


def test_seed_updates_aliases_and_party_of_existing_candidates(db_session):
    db_session.add(Candidate(name="Carlos Arias", party="viejo", aliases=["alias-viejo"]))
    db_session.commit()
    seed(db_session)
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    assert "alias-viejo" not in carlos.aliases and "@soycarlosaarias" in carlos.aliases
    assert carlos.party == "Partido de la U"


def test_seed_creates_city_candidate_and_city_sources(db_session):
    from src.pipeline import CITY_NAME
    seed(db_session)
    city = db_session.query(Candidate).filter_by(name=CITY_NAME).one()
    assert city.kind == "city"
    assert db_session.query(Source).filter_by(name="Google News Cali").one().config == {"city": True, "terms": ["Cali"], "context": ""}
    assert db_session.query(Source).filter_by(name="YouTube Cali").one().config["city"] is True
    assert db_session.query(Source).filter_by(name="El País Cali").one().config["city"] is True
    assert db_session.query(Source).filter_by(name="Semana").one().config["city"] is False
