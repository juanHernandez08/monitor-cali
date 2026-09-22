import pytest

from src.models import Candidate, Source, SourceType, Mention


def test_create_candidate_source_and_mention(db_session):
    candidate = Candidate(name="Ana Pérez", party="Partido X", aliases=[])
    source = Source(type=SourceType.RSS, name="El País Cali")
    db_session.add_all([candidate, source])
    db_session.commit()

    mention = Mention(
        candidate_id=candidate.id,
        source_id=source.id,
        external_id="noticia-123",
        url="https://example.com/noticia-123",
        text="Ana Pérez propuso un nuevo plan de seguridad.",
    )
    db_session.add(mention)
    db_session.commit()

    assert mention.id is not None
    assert mention.fetched_at is not None
    assert mention.candidate.name == "Ana Pérez"
    assert mention.source.type == SourceType.RSS


def test_mention_external_id_unique_per_source(db_session):
    candidate = Candidate(name="Ana Pérez")
    source = Source(type=SourceType.RSS, name="El País Cali")
    db_session.add_all([candidate, source])
    db_session.commit()

    db_session.add(Mention(
        candidate_id=candidate.id, source_id=source.id,
        external_id="dup-1", text="texto 1",
    ))
    db_session.commit()

    db_session.add(Mention(
        candidate_id=candidate.id, source_id=source.id,
        external_id="dup-1", text="texto 2",
    ))
    with pytest.raises(Exception):
        db_session.commit()


def test_candidate_stores_aliases(db_session):
    candidate = Candidate(
        name="Carlos Arias",
        aliases=["Carlos Andrés Arias Rueda", "@soycarlosaarias", "Buenos Ciudadanos"],
    )
    db_session.add(candidate)
    db_session.commit()

    fetched = db_session.query(Candidate).filter_by(name="Carlos Arias").first()
    assert "@soycarlosaarias" in fetched.aliases


def test_run_and_api_usage_tables(db_session):
    from src.models import Run, ApiUsage

    source = Source(type=SourceType.RSS, name="X")
    db_session.add(source)
    db_session.commit()
    run = Run(source_id=source.id, new_mentions=3)
    usage = ApiUsage(service="google_cse", day="2026-09-19", count=27)
    db_session.add_all([run, usage])
    db_session.commit()
    assert run.started_at is not None
    assert db_session.query(ApiUsage).filter_by(service="google_cse", day="2026-09-19").one().count == 27


def test_init_db_adds_missing_columns(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text, inspect
    import src.db as dbmod
    engine = create_engine(f"sqlite:///{tmp_path/'old.db'}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE candidates (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, party VARCHAR, active BOOLEAN NOT NULL, aliases JSON)"))
    monkeypatch.setattr(dbmod, "engine", engine)
    dbmod.init_db()
    assert "exclusions" in {c["name"] for c in inspect(engine).get_columns("candidates")}
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO candidates (name, active) VALUES ('X', 1)"))
        assert conn.execute(text("SELECT kind FROM candidates WHERE name='X'")).scalar() == "candidate"
