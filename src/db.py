import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///monitor.db")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db():
    Base.metadata.create_all(engine)
    _add_missing_columns()


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
