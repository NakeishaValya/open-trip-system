"""
Shared test fixtures.
Override the PostgreSQL database with an in-memory SQLite database
so that tests run fast and without external dependencies.
"""
import os, pytest

# ── Force SQLite BEFORE any backend module is imported ────────────────────
os.environ["DATABASE_URL"] = "sqlite:///./local_open_trip.db"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import backend.database as _db

# Build a test engine (SQLite, file-based so it's shared across sessions)
_test_engine = create_engine(
    "sqlite:///./local_open_trip.db",
    echo=False,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode and foreign key support for SQLite
@event.listens_for(_test_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

_TestSessionLocal = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)

# Monkey-patch the database module so every Storage class uses the test DB
_db.engine = _test_engine
_db.SessionLocal = _TestSessionLocal


@pytest.fixture(autouse=True)
def _setup_test_db():
    """Create all tables before each test; drop them after."""
    _db.Base.metadata.create_all(bind=_test_engine)
    yield
    _db.Base.metadata.drop_all(bind=_test_engine)
