"""SQLAlchemy engine/session ve şema sabitleri.

Postgres şemaları:
- raw      — Logo aynası (yalnız ingest yazar)
- derived  — job çıktıları (her job kendi tablolarını yönetir)
- app      — platform metası (users, jobs, runs, dashboards, ingest_state, permissions)
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

SCHEMA_APP = "app"
SCHEMA_RAW = "raw"
SCHEMA_DERIVED = "derived"

engine = create_engine(settings.APP_PG_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
