import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///monitor.db")

# El servidor web (scheduler + peticiones) y scripts como backfill_emotions.py escriben a la
# misma monitor.db desde procesos distintos. Con el modo por defecto de SQLite, un escritor
# choca con "database is locked" casi de inmediato (pasó en vivo: tumbó el arranque del
# servidor). WAL permite lectores y un escritor a la vez sin bloquearse entre sí, y el
# busy_timeout hace que un choque de dos escritores espere en vez de fallar al instante.
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args={"timeout": 30})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    if not DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


# Índices para los filtros que usan todas las consultas del dashboard (candidato, fecha, relevancia).
# create_all() no agrega índices a tablas que ya existen, así que se crean aquí de forma idempotente.
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_mentions_candidate_rel ON mentions (candidate_id, relevant)",
    "CREATE INDEX IF NOT EXISTS ix_mentions_published ON mentions (published_at)",
    "CREATE INDEX IF NOT EXISTS ix_mentions_fetched ON mentions (fetched_at)",
    "CREATE INDEX IF NOT EXISTS ix_mentions_source ON mentions (source_id)",
    "CREATE INDEX IF NOT EXISTS ix_runs_source_started ON runs (source_id, started_at)",
]


def init_db():
    Base.metadata.create_all(engine)
    _add_missing_columns()
    _ensure_indexes()


def _ensure_indexes():
    from sqlalchemy import text
    with engine.begin() as conn:
        for ddl in _INDEXES:
            conn.execute(text(ddl))


def _add_missing_columns():
    """Migración mínima: añade columnas nuevas de los modelos a tablas ya existentes (SQLite)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = column.type.compile(engine.dialect)
                default = column.default.arg if column.default is not None and column.default.is_scalar else None
                if isinstance(default, str):
                    ddl += f" DEFAULT '{default}'"  # p. ej. Candidate.kind = 'candidate' para filas existentes
                elif isinstance(default, (int, float, bool)):
                    ddl += f" DEFAULT {int(default) if isinstance(default, bool) else default}"
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl}'))


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
