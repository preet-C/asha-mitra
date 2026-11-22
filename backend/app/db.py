# backend/app/db.py
# P7 — SQLAlchemy 2 engine setup (synchronous).
#
# WHY synchronous instead of async:
#   dialogue.py and repo functions are called from sync code paths.
#   Mixing sync callers with an async engine requires run_sync() wrappers
#   everywhere — that's complexity without benefit for this scale.
#   FastAPI runs sync routes in a thread pool automatically, so sync DB calls
#   are fine here. Switch to async only if profiling shows it's needed.
#
# Usage:
#   with get_session() as session:
#       session.add(row)
#   # commit happens automatically on exit; rollback on exception

from contextlib import contextmanager
from typing import Generator

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.config import get_settings

# Module-level engine — built lazily on first use, then reused.
# WHY lazy: tests override DATABASE_URL before importing this module,
# so we must not create the engine at import time.
_engine: sa.Engine | None = None


def _engine_url(raw_url: str) -> sa.engine.URL:
    """Parse DATABASE_URL and select the psycopg 3 driver for Postgres.

    WHY: managed Postgres providers commonly give URLs starting with
    ``postgres://`` or ``postgresql://``. SQLAlchemy may otherwise select
    psycopg2, which this project does not install.
    """
    url = sa.engine.make_url(raw_url.strip())
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


def get_engine() -> sa.Engine:
    """Return (and lazily create) the shared SQLAlchemy engine.

    Raises RuntimeError if DATABASE_URL is empty.
    """
    global _engine
    if _engine is None:
        url = get_settings().DATABASE_URL
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set in backend/.env.\n"
                "Set it to your Neon/Supabase postgres URL and restart."
            )
        # echo=False: don't print every SQL statement in production
        _engine = sa.create_engine(
            _engine_url(url),
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy Session, then commit or roll back automatically.

    Usage:
        with get_session() as session:
            session.add(row)
        # commit happens here; rollback happens on any exception

    WHY context manager: guarantees cleanup even if an exception is raised.
    """
    with Session(get_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_tables() -> None:
    """Create all ORM tables in the database if they don't exist yet.

    Safe to call on every restart — SQLAlchemy uses CREATE TABLE IF NOT EXISTS.
    Called from main.py lifespan and from scripts/seed.py.
    """
    from app.models import Base   # local import avoids circular dependency
    Base.metadata.create_all(get_engine(), checkfirst=True)
