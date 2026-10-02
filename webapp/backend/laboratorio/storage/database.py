"""Versioned SQLite bootstrap and short-lived, foreign-key-enabled connections."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from laboratorio.domain.contracts import legacy_quiniela_80_profile

SCHEMA_VERSION = 9
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Ordered, sequential migration scripts; each key is the schema version it produces.
_MIGRATIONS = {
    1: _MIGRATIONS_DIR / "0001_initial.sql",
    2: _MIGRATIONS_DIR / "0002_experiment_created_at.sql",
    3: _MIGRATIONS_DIR / "0003_settings.sql",
    4: _MIGRATIONS_DIR / "0004_game_profiles.sql",
    5: _MIGRATIONS_DIR / "0005_datasets.sql",
    6: _MIGRATIONS_DIR / "0006_profile_requests.sql",
    7: _MIGRATIONS_DIR / "0007_profile_cycling_storage.sql",
    8: _MIGRATIONS_DIR / "0008_profile_audaz_storage.sql",
    9: _MIGRATIONS_DIR / "0009_profile_recovery_storage.sql",
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
    try:
        # The script starts its own guarded transaction because executescript commits
        # an existing one. Do not append COMMIT: Python backfill and version bump must
        # be in the *same* transaction as all DDL, including upgrades from v1/v2.
        db.executescript(guard + scripts)
        if 4 in versions:
            profile = legacy_quiniela_80_profile()
            snapshot = profile.model_dump_json()
            db.execute(
                "INSERT INTO game_profiles (profile_id, revision, profile_json) VALUES (?, ?, ?)",
                (profile.profile_id, profile.revision, snapshot),
            )
            db.execute(
                "INSERT INTO experiment_profiles "
                "(experiment_id, profile_id, revision, profile_json) "
                "SELECT id, ?, ?, ? FROM experiments",
                (profile.profile_id, profile.revision, snapshot),
            )
        db.execute(f"PRAGMA user_version = {target}")
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        # The guard can fail after another initializer wins. Do not mask a real
        # backfill failure when the version remained at its prior value.
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise
    except BaseException:
        db.rollback()
        raise


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
