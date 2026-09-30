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


def test_seed_marks_the_social_source_as_a_city_source(db_session):
    """Bug real 2026-09-30: sin 'city' en el config de la fuente SOCIAL, las cuentas de medios sin
    candidato asociado (candidate=None en config.SOCIAL_ACCOUNTS) se descartaban en silencio en
    ingest() -- la pestaña Ciudad nunca mostraba publicaciones de Instagram/Facebook/X."""
    seed(db_session)
    social = db_session.query(Source).filter_by(type=SourceType.SOCIAL).one()
    assert social.config.get("city") is True


def test_seed_updates_config_of_an_extra_source_already_in_the_db(db_session):
    """Si el config.py de un EXTRA_SOURCES cambia (como pasó con SOCIAL), una fuente ya guardada
    con el config viejo debe actualizarse al re-sembrar, no quedarse pegada para siempre."""
    db_session.add(Source(type=SourceType.SOCIAL, name="Instagram / Facebook (cuentas)", config={}))
    db_session.commit()
    seed(db_session)
    social = db_session.query(Source).filter_by(type=SourceType.SOCIAL).one()
    assert social.config.get("city") is True


def test_seed_creates_city_candidate_and_city_sources(db_session):
    from src.pipeline import CITY_NAME
    seed(db_session)
    city = db_session.query(Candidate).filter_by(name=CITY_NAME).one()
    assert city.kind == "city"
    assert db_session.query(Source).filter_by(name="Google News Cali").one().config == {"city": True, "terms": ["Cali"], "context": ""}
    assert db_session.query(Source).filter_by(name="YouTube Cali").one().config["city"] is True
    assert db_session.query(Source).filter_by(name="El País Cali").one().config["city"] is True
    assert db_session.query(Source).filter_by(name="Semana").one().config["city"] is False


def test_seed_sets_context_terms_for_candidates_that_declare_them(db_session):
    """Francia Márquez e Irene Vélez son figuras nacionales (Vicepresidenta y exministra); Carlos
    Arias es un nombre común (hay un futbolista "Luis Carlos Arias"): sin exigir "Cali"/"Alcaldía"
    en el texto, la prensa nacional sobre ellos se cuela como si fuera de la contienda por la
    Alcaldía. Bug real: seed() solo aplicaba context_terms a concejales; luego Carlos Arias se
    quedó sin la regla que sí se le dio a los demás nombres comunes/figuras nacionales
    (2026-09-29, auditoría encontró prensa de fútbol colándose)."""
    seed(db_session)
    fm = db_session.query(Candidate).filter_by(name="Francia Márquez").one()
    assert fm.context_terms and "Cali" in fm.context_terms
    iv = db_session.query(Candidate).filter_by(name="Irene Vélez").one()
    assert iv.context_terms and "Cali" in iv.context_terms
    carlos = db_session.query(Candidate).filter_by(name="Carlos Arias").one()
    assert carlos.context_terms and "Cali" in carlos.context_terms
    roberto = db_session.query(Candidate).filter_by(name="Roberto Ortiz").one()
    assert not roberto.context_terms  # no todos los candidatos necesitan esta regla
