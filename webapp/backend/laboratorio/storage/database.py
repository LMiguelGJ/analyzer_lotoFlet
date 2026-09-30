"""Versioned SQLite bootstrap and short-lived, foreign-key-enabled connections."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

SCHEMA_VERSION = 3
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Ordered, sequential migration scripts; each key is the schema version it produces.
_MIGRATIONS = {
    1: _MIGRATIONS_DIR / "0001_initial.sql",
    2: _MIGRATIONS_DIR / "0002_experiment_created_at.sql",
    3: _MIGRATIONS_DIR / "0003_settings.sql",
}


class UnsupportedSchema(RuntimeError):
    """Database is not a version this application can safely open."""


@contextmanager
def connection(path: Path):
    """Open an existing database, always closing even after rollback or error."""
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        yield db
    finally:
        db.close()


def _check_version(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise UnsupportedSchema(
            f"unsupported database schema version {version}; expected {SCHEMA_VERSION}"
        )


def _run_migrations(db, expected_prior: int, versions: list[int]):
    """Apply one or more sequential migration scripts atomically under a single guard.

    executescript commits the preliminary lock: recheck the prior version under
    its own writer lock before running the packaged, trusted DDL, so a concurrent
    initializer that already advanced the schema loses the race cleanly.
    """
    scripts = "\n".join(_MIGRATIONS[v].read_text(encoding="utf-8") for v in versions)
    target = versions[-1]
    guard = (
        "BEGIN IMMEDIATE;\n"
        "CREATE TEMP TABLE migration_guard "
        f"(version INTEGER CHECK(version = {expected_prior}));\n"
        "INSERT INTO migration_guard SELECT user_version FROM pragma_user_version;\n"
        "DROP TABLE migration_guard;\n"
    )
    tail = f"\nPRAGMA user_version = {target};\nCOMMIT;"
    try:
        db.executescript(guard + scripts + tail)
    except sqlite3.IntegrityError:
        db.rollback()
        # Another initializer may have won the race; accept only the final version.
        _check_version(db)


def initialize_database(path: Path):
    """Explicit bootstrap or upgrade; refuse unknown schemas, never overwrite data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # SQLite serializes the bootstrap writer; its version check occurs under the lock.
    with closing(sqlite3.connect(path, timeout=10)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            return
        has_tables = bool(
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()
        )
        if version == 0 and not has_tables:
            _run_migrations(db, 0, list(range(1, SCHEMA_VERSION + 1)))
            return
        if version in _MIGRATIONS and has_tables:
            _run_migrations(db, version, list(range(version + 1, SCHEMA_VERSION + 1)))
            return
        raise UnsupportedSchema(f"unsupported database schema version {version}")


def require_database(path: Path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"database is not initialized: {path}")
    with connection(path) as db:
        _check_version(db)
