"""SQLite persistence: quota accounting and saved runs."""

import shutil
from contextlib import contextmanager
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

from laboratorio.settings import DEFAULT_QUOTA_BYTES
from laboratorio.storage.database import connection, require_database
from laboratorio.storage.quota import QuotaStatus, measure, validate_quota_bytes


class QuotaReadOnly(RuntimeError):
    """An explicit environment quota forbids changing the persisted preference."""


class QuotaBelowUsage(RuntimeError):
    """A new preference cannot be less than existing admitted logical artifacts."""


@dataclass(frozen=True)
class EffectiveQuota:
    effective_bytes: int
    persisted_bytes: int | None
    source: str
    writable: bool


def _now_iso() -> str:
    """UTC ISO 8601 with an explicit Z suffix and microsecond resolution."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@contextmanager
def _transaction(path):
    with connection(path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise


def _logical_experiment_bytes(db):
    """UTF-8 bytes of experiment, run and batch-admission fields.

    Includes copied requests, IDs, provenance, statuses and completed result JSON.
    This is not SQLite page allocation or a reclaimable-byte estimate.
    """
    experiment_fields = (
        "id",
        "status",
        "request_json",
        "request_kind",
        "request_schema_version",
        "history_id",
        "history_sha256",
        "rankings_id",
        "rankings_sha256",
        "code_version",
        "created_at",
    )
    run_fields = (
        "experiment_id",
        "configuration_id",
        "status",
        "result_json",
        "result_kind",
        "result_schema_version",
    )

    def total(table, fields):
        parts = " + ".join(f"coalesce(length(CAST({field} AS BLOB)), 0)" for field in fields)
        return db.execute(f"SELECT coalesce(sum({parts}), 0) FROM {table}").fetchone()[0]

    return (
        total("experiments", experiment_fields)
        + total("runs", run_fields)
        + db.execute(
            "SELECT 8 * count(*) FROM runs"  # fixed-width ordinal in the logical contract
        ).fetchone()[0]
        + db.execute(
            "SELECT coalesce(sum(length(CAST(experiment_id AS BLOB)) + "
            "length(CAST(client_request_id AS BLOB)) + length(CAST(request_sha256 AS BLOB)) + "
            "length(CAST(strategy_refs_json AS BLOB)) + "
            "length(CAST(requested_constraints_json AS BLOB)) + "
            "length(CAST(effective_constraints_json AS BLOB)) + 8 + "
            "length(CAST(policy_json AS BLOB)) + "
            "length(CAST(source_identity_json AS BLOB))), 0) "
            "FROM profile_batch_admissions"
        ).fetchone()[0]
    )


def _profile_artifact_bytes(db) -> int:
    """Count every v1/v2 profile JSON copy, including experiment snapshots."""
    row = db.execute(
        "SELECT (SELECT coalesce(sum(length(CAST(profile_json AS BLOB))), 0) "
        "FROM game_profiles) + (SELECT coalesce(sum(length(CAST(profile_json AS BLOB))), 0) "
        "FROM experiment_profiles)"
    ).fetchone()
    # Preserve the reader on explicitly prepared historical schemas; normal
    # Repository instances are bootstrapped to the current schema before use.
    has_v2 = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='quiniela_game_profiles'"
    ).fetchone()
    v2_bytes = (
        db.execute(
            "SELECT coalesce(sum(length(CAST(profile_json AS BLOB))), 0) "
            "FROM quiniela_game_profiles"
        ).fetchone()[0]
        if has_v2
        else 0
    )
    return row[0] + v2_bytes


def _dataset_artifact_bytes(db) -> int:
    """Every persisted dataset BLOB and TEXT byte, each column exactly once."""
    return db.execute(
        "SELECT coalesce(sum(length(CAST(dataset_sha256 AS BLOB)) + "
        "length(CAST(source_sha256 AS BLOB)) + length(CAST(canonical_json AS BLOB)) + "
        "length(raw_bytes) + length(CAST(created_at AS BLOB))), 0) FROM datasets"
    ).fetchone()[0]


def _strategy_artifact_bytes(db) -> int:
    """Count strategy metadata and every immutable UTF-8 definition snapshot."""
    return db.execute(
        "SELECT "
        "(SELECT coalesce(sum(length(CAST(id AS BLOB)) + length(CAST(name AS BLOB)) + "
        "length(CAST(created_at AS BLOB)) + length(CAST(preset_explanation AS BLOB)) + 9), 0) "
        "FROM strategies) + "
        "(SELECT coalesce(sum(length(CAST(strategy_id AS BLOB)) + 8 + 8 + "
        "length(CAST(definition_sha256 AS BLOB)) + length(CAST(definition_json AS BLOB)) + "
        "length(CAST(created_at AS BLOB))), 0) FROM strategy_revisions)"
    ).fetchone()[0]


def _history_artifact_bytes(db) -> int:
    """Every persisted v1/v2 history column byte, each column exactly once."""
    legacy = db.execute(
        "SELECT "
        "(SELECT coalesce(sum(length(CAST(sha256 AS BLOB)) + length(CAST(created_at AS BLOB)) + "
        "8 + 8 + length(CAST(first_label AS BLOB)) + length(CAST(last_label AS BLOB)) + "
        "length(raw_bytes)), 0) FROM history_sources) + "
        "(SELECT coalesce(sum(8 + length(CAST(sha256 AS BLOB))), 0) FROM history_active)"
    ).fetchone()[0]
    has_v2 = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='quiniela_history_sources'"
    ).fetchone()
    if not has_v2:
        return legacy
    v2 = db.execute(
        "SELECT coalesce(sum(length(CAST(id AS BLOB)) + length(CAST(profile_id AS BLOB)) + "
        "length(CAST(profile_sha256 AS BLOB)) + length(CAST(origin AS BLOB)) + "
        "length(CAST(name AS BLOB)) + length(CAST(raw_sha256 AS BLOB)) + "
        "length(CAST(canonical_sha256 AS BLOB)) + length(CAST(preview_sha256 AS BLOB)) + "
        "length(raw_bytes) + length(CAST(canonical_json AS BLOB)) + 8 + "
        "length(CAST(timezone AS BLOB)) + 1 + 8 + 8 + "
        "coalesce(length(CAST(first_timestamp AS BLOB)), 0) + "
        "coalesce(length(CAST(last_timestamp AS BLOB)), 0) + "
        "length(CAST(created_at AS BLOB))), 0) FROM quiniela_history_sources"
    ).fetchone()[0]
    return legacy + v2


@dataclass(frozen=True)
class RepositoryQuotaStatus(QuotaStatus):
    """Quota status plus persisted history, run and laboratory-definition bytes."""

    history_artifact_bytes: int = 0
    run_artifact_bytes: int = 0
    laboratory_definition_bytes: int = 0

    @property
    def admission_logical_bytes(self) -> int:
        return (
            super().admission_logical_bytes
            + self.history_artifact_bytes
            + self.run_artifact_bytes
            + self.laboratory_definition_bytes
        )


def _laboratory_definition_bytes(db) -> int:
    """Count canonical definition JSON bytes once, without folding them into run bytes."""
    return db.execute(
        "SELECT coalesce(sum(definition_bytes), 0) FROM laboratory_definitions"
    ).fetchone()[0]


def _run_artifact_bytes(db) -> int:
    return db.execute(
        "SELECT (SELECT coalesce(sum(length(CAST(id AS BLOB)) + length(CAST(name AS BLOB)) + "
        "8 + length(CAST(config_json AS BLOB)) + length(CAST(summary_json AS BLOB)) + "
        "length(CAST(created_at AS BLOB))), 0) FROM saved_runs) + "
        "(SELECT coalesce(sum(length(CAST(run_id AS BLOB)) + 8 + length(CAST(outcome AS BLOB)) + "
        "8 + 8 + length(CAST(start_label AS BLOB)) + length(CAST(end_label AS BLOB)) + "
        "8 + 8 + 8 + 8 + 8 + coalesce(length(CAST(bets_json AS BLOB)), 0)), 0) "
        "FROM saved_run_sessions) + "
        "(SELECT coalesce(sum(length(CAST(id AS BLOB)) + length(CAST(lab_id AS BLOB)) + "
        "8 + length(CAST(created_at AS BLOB)) + length(CAST(metadata_json AS BLOB)) + "
        "length(CAST(result_json AS BLOB))), 0) FROM reference_lab_runs) + "
        "(SELECT coalesce(sum(length(CAST(run_id AS BLOB)) + 8 + "
        "length(CAST(session_json AS BLOB))), 0) FROM reference_lab_sessions)"
    ).fetchone()[0]


def _admission_logical_bytes(db) -> int:
    return (
        _logical_experiment_bytes(db)
        + _profile_artifact_bytes(db)
        + _dataset_artifact_bytes(db)
        + _strategy_artifact_bytes(db)
        + _history_artifact_bytes(db)
        + _run_artifact_bytes(db)
        + _laboratory_definition_bytes(db)
    )


def _persisted_quota(db) -> int | None:
    row = db.execute("SELECT quota_bytes FROM settings_quota WHERE id = 1").fetchone()
    return None if row is None else validate_quota_bytes(row[0])


def _effective_quota(db, quota_bytes: int | None, quota_explicit: bool | None) -> EffectiveQuota:
    if quota_explicit is not None and type(quota_explicit) is not bool:
        raise ValueError("quota_explicit must be a boolean")
    if quota_bytes is not None:
        validate_quota_bytes(quota_bytes)
    if quota_explicit and quota_bytes is None:
        raise ValueError("explicit environment quota requires quota_bytes")
    persisted = _persisted_quota(db)
    if quota_explicit:
        assert quota_bytes is not None
        return EffectiveQuota(quota_bytes, persisted, "environment", False)
    if quota_bytes is not None and quota_explicit is None:
        return EffectiveQuota(quota_bytes, persisted, "override", True)
    if persisted is not None:
        return EffectiveQuota(persisted, persisted, "persisted", True)
    return EffectiveQuota(
        quota_bytes if quota_bytes is not None else DEFAULT_QUOTA_BYTES,
        None,
        "default",
        True,
    )


class Repository:
    def __init__(self, path: Path):
        from laboratorio.storage.owned_laboratory_read_cache import OwnedLaboratoryReadCache

        self.path = Path(path)
        require_database(self.path)
        self._owned_laboratory_database_id = self.path.resolve().as_uri()
        self._owned_laboratory_read_cache = OwnedLaboratoryReadCache()

    def logical_experiment_bytes(self) -> int:
        with connection(self.path) as db:
            return _logical_experiment_bytes(db)

    def profile_artifact_bytes(self) -> int:
        with connection(self.path) as db:
            return _profile_artifact_bytes(db)

    def admission_logical_bytes(self) -> int:
        with connection(self.path) as db:
            return _admission_logical_bytes(db)

    def dataset_artifact_bytes(self) -> int:
        with connection(self.path) as db:
            return _dataset_artifact_bytes(db)

    def strategy_artifact_bytes(self) -> int:
        with connection(self.path) as db:
            return _strategy_artifact_bytes(db)

    def history_artifact_bytes(self) -> int:
        with connection(self.path) as db:
            return _history_artifact_bytes(db)

    def get_active_history_sha(self) -> str | None:
        with connection(self.path) as db:
            row = db.execute("SELECT sha256 FROM history_active WHERE id = 1").fetchone()
        return None if row is None else row[0]

    def get_history_source(self, sha256: str) -> dict | None:
        with connection(self.path) as db:
            row = db.execute(
                "SELECT sha256, created_at, draws, added_draws, first_label, last_label, "
                "raw_bytes FROM history_sources WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
        if row is None:
            return None
        keys = ("sha256", "created_at", "draws", "added_draws", "first_label", "last_label")
        return {**dict(zip(keys, row, strict=False)), "raw_bytes": bytes(row[6])}

    def list_history_sources(self) -> list[dict]:
        with connection(self.path) as db:
            rows = db.execute(
                "SELECT sha256, created_at, draws, added_draws, first_label, last_label "
                "FROM history_sources ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
        keys = ("sha256", "created_at", "draws", "added_draws", "first_label", "last_label")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def import_history_source(
        self,
        sha256: str,
        raw_bytes: bytes,
        *,
        draws: int,
        added_draws: int,
        first_label: str,
        last_label: str,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> bool:
        """Store and activate a history; True when new, False when it only reactivated."""
        # Measure disk outside the write transaction, as the other capacity checks do.
        limit = self.effective_quota(quota_bytes, quota_explicit=quota_explicit).effective_bytes
        with _transaction(self.path) as db:
            created = (
                db.execute("SELECT 1 FROM history_sources WHERE sha256 = ?", (sha256,)).fetchone()
                is None
            )
            if created:
                status = measure(
                    self.path,
                    limit,
                    _logical_experiment_bytes(db),
                    profile_artifact_bytes=_profile_artifact_bytes(db),
                    dataset_artifact_bytes=_dataset_artifact_bytes(db),
                    strategy_artifact_bytes=_strategy_artifact_bytes(db),
                    disk_usage=disk_usage,
                )
                status = RepositoryQuotaStatus(
                    **{f.name: getattr(status, f.name) for f in fields(QuotaStatus)},
                    history_artifact_bytes=_history_artifact_bytes(db),
                    run_artifact_bytes=_run_artifact_bytes(db),
                    laboratory_definition_bytes=_laboratory_definition_bytes(db),
                )
                status.require_capacity(len(raw_bytes) + len(sha256) + 128)
                db.execute(
                    "INSERT INTO history_sources (sha256, created_at, draws, added_draws, "
                    "first_label, last_label, raw_bytes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        sha256,
                        _now_iso(),
                        draws,
                        added_draws,
                        first_label,
                        last_label,
                        raw_bytes,
                    ),
                )
            db.execute(
                "INSERT INTO history_active (id, sha256) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET sha256 = excluded.sha256",
                (sha256,),
            )
        return created

    def get_quota_preference(self) -> int | None:
        with connection(self.path) as db:
            return _persisted_quota(db)

    def set_quota_preference(self, quota_bytes: int, *, quota_explicit: bool = False) -> int:
        validate_quota_bytes(quota_bytes)
        if type(quota_explicit) is not bool:
            raise ValueError("quota_explicit must be a boolean")
        if quota_explicit:
            raise QuotaReadOnly("environment quota is read-only")
        with _transaction(self.path) as db:
            if quota_bytes < _admission_logical_bytes(db):
                raise QuotaBelowUsage("quota cannot be below current logical usage")
            db.execute(
                "INSERT INTO settings_quota (id, quota_bytes) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET quota_bytes = excluded.quota_bytes",
                (quota_bytes,),
            )
        return quota_bytes

    def effective_quota(
        self, quota_bytes: int | None = None, *, quota_explicit: bool | None = None
    ) -> EffectiveQuota:
        with connection(self.path) as db:
            return _effective_quota(db, quota_bytes, quota_explicit)

    def quota_status(
        self,
        quota_bytes: int | None = None,
        *,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ):
        # Legacy explicit limits need no database read; opening SQLite can remove stale
        # sidecars before a physical-size snapshot.
        if quota_bytes is not None and quota_explicit is None:
            limit = validate_quota_bytes(quota_bytes)
        else:
            limit = self.effective_quota(quota_bytes, quota_explicit=quota_explicit).effective_bytes
        with connection(self.path) as db:
            db.execute("BEGIN")  # both components share the same read snapshot
            experiment_bytes = _logical_experiment_bytes(db)
            profile_bytes = _profile_artifact_bytes(db)
            dataset_bytes = _dataset_artifact_bytes(db)
            strategy_bytes = _strategy_artifact_bytes(db)
            history_bytes = _history_artifact_bytes(db)
            run_bytes = _run_artifact_bytes(db)
            laboratory_definition_bytes = _laboratory_definition_bytes(db)
        status = measure(
            self.path,
            limit,
            experiment_bytes,
            profile_artifact_bytes=profile_bytes,
            dataset_artifact_bytes=dataset_bytes,
            strategy_artifact_bytes=strategy_bytes,
            disk_usage=disk_usage,
        )
        return RepositoryQuotaStatus(
            **{f.name: getattr(status, f.name) for f in fields(QuotaStatus)},
            history_artifact_bytes=history_bytes,
            run_artifact_bytes=run_bytes,
            laboratory_definition_bytes=laboratory_definition_bytes,
        )

    def require_capacity(
        self,
        quota_bytes: int | None = None,
        *,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ):
        status = self.quota_status(
            quota_bytes, quota_explicit=quota_explicit, disk_usage=disk_usage
        )
        status.require_capacity()
        return status

    def create_run(
        self, run_id, name, config, summary, session_rows, *, quota_bytes, quota_explicit
    ):
        from laboratorio.storage.run_store import create_run

        return create_run(
            self,
            run_id,
            name,
            config,
            summary,
            session_rows,
            quota_bytes=quota_bytes,
            quota_explicit=quota_explicit,
        )

    def get_run(self, run_id):
        from laboratorio.storage.run_store import get_run

        return get_run(self, run_id)

    def search_runs(self, offset, limit):
        from laboratorio.storage.run_store import search_runs

        return search_runs(self, offset, limit)

    def page_run_sessions(self, run_id, offset, limit, outcome=None):
        from laboratorio.storage.run_store import page_run_sessions

        return page_run_sessions(self, run_id, offset, limit, outcome)

    def page_run_bets(self, run_id, ordinal, offset, limit):
        from laboratorio.storage.run_store import page_run_bets

        return page_run_bets(self, run_id, ordinal, offset, limit)

    def delete_run(self, run_id):
        from laboratorio.storage.run_store import delete_run

        return delete_run(self, run_id)

    def create_reference_lab_run(
        self, run_id, lab_id, config, provenance, result, *, quota_bytes, quota_explicit
    ):
        from laboratorio.storage.reference_lab_store import create_reference_lab_run

        return create_reference_lab_run(
            self,
            run_id,
            lab_id,
            config,
            provenance,
            result,
            quota_bytes=quota_bytes,
            quota_explicit=quota_explicit,
        )

    def get_reference_lab_run(self, run_id):
        from laboratorio.storage.reference_lab_store import get_reference_lab_run

        return get_reference_lab_run(self, run_id)

    def list_reference_lab_runs(self, *, lab_id=None, offset=0, limit=20):
        from laboratorio.storage.reference_lab_store import list_reference_lab_runs

        return list_reference_lab_runs(self, lab_id=lab_id, offset=offset, limit=limit)

    def list_reference_lab_sessions(self, run_id, *, offset=0, limit=50):
        from laboratorio.storage.reference_lab_store import list_reference_lab_sessions

        return list_reference_lab_sessions(self, run_id, offset=offset, limit=limit)

    def delete_reference_lab_run(self, run_id):
        from laboratorio.storage.reference_lab_store import delete_reference_lab_run

        return delete_reference_lab_run(self, run_id)

    def create_owned_laboratory_run(
        self, run_id, owner_laboratory_id, snapshot, result, *, quota_bytes, quota_explicit
    ):
        from laboratorio.storage.owned_laboratory_run_store import create_run

        return create_run(
            self,
            run_id,
            owner_laboratory_id,
            snapshot,
            result,
            quota_bytes=quota_bytes,
            quota_explicit=quota_explicit,
        )

    def list_owned_laboratory_runs(self, owner_laboratory_id, *, offset=0, limit=20):
        from laboratorio.storage.owned_laboratory_run_store import list_runs

        return list_runs(self, owner_laboratory_id, offset=offset, limit=limit)

    def get_owned_laboratory_run(self, owner_laboratory_id, run_id):
        from laboratorio.storage.database import connection
        from laboratorio.storage.owned_laboratory_run_store import get_run

        with connection(self.path) as db:
            return get_run(db, owner_laboratory_id, run_id)

    def list_owned_laboratory_run_summaries(self, owner_laboratory_id, *, offset=0, limit=20):
        from laboratorio.storage.owned_laboratory_run_store import list_run_summaries

        return list_run_summaries(self, owner_laboratory_id, offset=offset, limit=limit)

    def get_owned_laboratory_run_summary(self, owner_laboratory_id, run_id):
        from laboratorio.storage.owned_laboratory_run_store import get_run_summary

        return get_run_summary(self, owner_laboratory_id, run_id)

    def list_owned_laboratory_run_sessions(
        self, owner_laboratory_id, run_id, *, offset=0, limit=50
    ):
        from laboratorio.storage.owned_laboratory_run_store import list_run_sessions

        return list_run_sessions(self, owner_laboratory_id, run_id, offset=offset, limit=limit)

    def create_laboratory_definition(self, name, config, *, quota_bytes=None, quota_explicit=None):
        from laboratorio.storage.laboratory_store import create_laboratory_definition

        return create_laboratory_definition(
            self,
            name,
            config,
            quota_bytes=quota_bytes,
            quota_explicit=quota_explicit,
        )

    def get_laboratory_definition(self, identifier):
        from laboratorio.storage.laboratory_store import get_laboratory_definition

        return get_laboratory_definition(self, identifier)

    def list_laboratory_definitions(self, *, offset=0, limit=20):
        from laboratorio.storage.laboratory_store import list_laboratory_definitions

        return list_laboratory_definitions(self, offset=offset, limit=limit)

    def get_laboratory_owned_counts(self, identifier):
        from laboratorio.storage.laboratory_store import get_laboratory_owned_counts

        return get_laboratory_owned_counts(self, identifier)

    def delete_laboratory_definition(self, identifier, *, confirmed_run_count):
        from laboratorio.storage.laboratory_store import delete_laboratory_definition

        return delete_laboratory_definition(
            self, identifier, confirmed_run_count=confirmed_run_count
        )
