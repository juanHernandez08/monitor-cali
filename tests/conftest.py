import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base


@pytest.fixture
def db_session():
    # StaticPool + check_same_thread=False: una sola conexión compartida entre hilos
    # (el TestClient de FastAPI ejecuta los endpoints en un threadpool).
    engine = create_engine(
        "sqlite:///:memory:", future=True,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    yield session
    session.close()
