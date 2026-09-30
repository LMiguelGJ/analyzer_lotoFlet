"""Small transactional repository for saved strategies and immutable run snapshots."""

import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from laboratorio.domain.contracts import (
    ExperimentRequest,
    ExperimentStatus,
    Outcome,
    RunStatus,
    Strategy,
)
from laboratorio.domain.session import Bet, SessionResult
from laboratorio.settings import DEFAULT_QUOTA_BYTES
from laboratorio.storage.database import connection, require_database
from laboratorio.storage.quota import measure, validate_quota_bytes

SQLITE_MAX = 2**63 - 1


class QuotaReadOnly(RuntimeError):
    """An explicit environment quota forbids changing the persisted preference."""


class QuotaBelowUsage(RuntimeError):
    """A new preference cannot be less than existing logical experiment bytes."""


@dataclass(frozen=True)
class EffectiveQuota:
    effective_bytes: int
    persisted_bytes: int | None
    source: str
    writable: bool


@dataclass(frozen=True)
class SavedConfiguration:
    id: str
    name: str
    strategy: Strategy


@dataclass(frozen=True)
class SavedRun:
    ordinal: int
    configuration_id: str | None
    status: RunStatus
    result: SessionResult | None


@dataclass(frozen=True)
class SavedExperiment:
    id: str
    status: ExperimentStatus
    request: ExperimentRequest
    history_id: str
    history_sha256: str
    rankings_id: str
    rankings_sha256: str
    code_version: str
    created_at: str | None
    runs: tuple[SavedRun, ...]


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _now_iso() -> str:
    """UTC ISO 8601 with an explicit Z suffix and microsecond resolution."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so a literal %, _ or the escape char never behaves as one."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


_SEARCH_SORTS = frozenset(("created_at", "name", "status"))
_SEARCH_ORDERS = frozenset(("asc", "desc"))


def _result_json(result):
    return _json(
        {
            "outcome": result.outcome.value,
            "bets_count": result.bets_count,
            "wagered": result.wagered,
            "paid": result.paid,
            "final_balance": result.final_balance,
            "bets": [
                {
                    "label": bet.label,
                    "numbers": bet.numbers,
                    "per_number": bet.per_number,
                    "wagered": bet.wagered,
                    "results": bet.results,
                    "paid": bet.paid,
                    "balance": bet.balance,
                }
                for bet in result.bets
            ],
        }
    )


def _read_result(value):
    if value is None:
        return None
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("corrupt stored result JSON") from exc
    return SessionResult(
        Outcome(data["outcome"]),
        data["bets_count"],
        data["wagered"],
        data["paid"],
        data["final_balance"],
        tuple(
            Bet(**{**bet, "numbers": tuple(bet["numbers"]), "results": tuple(bet["results"])})
            for bet in data["bets"]
        ),
    )


def _load_experiment(db, identifier: str) -> SavedExperiment | None:
    row = db.execute("SELECT * FROM experiments WHERE id = ?", (identifier,)).fetchone()
    if row is None:
        return None
    runs = db.execute(
        "SELECT ordinal, configuration_id, status, result_json FROM runs "
        "WHERE experiment_id = ? ORDER BY ordinal",
        (identifier,),
    ).fetchall()
    return SavedExperiment(
        row[0],
        ExperimentStatus(row[1]),
        ExperimentRequest.model_validate_json(row[2]),
        row[3],
        row[4],
        row[5],
        row[6],
        row[7],
        row[8],
        tuple(
            SavedRun(i, link, RunStatus(status), _read_result(value))
            for i, link, status, value in runs
        ),
    )


def _validate_result(result, capital, coverage):
    if not isinstance(result, SessionResult) or not isinstance(result.outcome, Outcome):
        raise ValueError("invalid completed result")
    if result.bets_count != len(result.bets) or not result.bets:
        raise ValueError("bets_count must match nonempty replay")
    balance = capital
    wagered = paid = 0
    for bet in result.bets:
        values = (bet.per_number, bet.wagered, bet.paid, bet.balance)
        if any(type(n) is not int or not 0 <= n <= SQLITE_MAX for n in values):
            raise ValueError("bet money must be nonnegative SQLite-safe integers")
        if bet.per_number < 1 or len(bet.numbers) != coverage or len(bet.results) != 5:
            raise ValueError("invalid bet replay")
        if bet.wagered != bet.per_number * coverage or bet.wagered > balance:
            raise ValueError("wagered amount does not match funded stake")
        balance += bet.paid - bet.wagered
        if bet.balance != balance or balance > SQLITE_MAX:
            raise ValueError("bet balance does not reconcile")
        wagered += bet.wagered
        paid += bet.paid
    if any(
        type(n) is not int or not 0 <= n <= SQLITE_MAX
        for n in (result.wagered, result.paid, result.final_balance)
    ):
        raise ValueError("totals must be SQLite-safe integers")
    if (result.wagered, result.paid, result.final_balance) != (wagered, paid, balance):
        raise ValueError("paid, wagered or final balance does not reconcile")


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
    """UTF-8 bytes of experiment and run fields, excluding reusable configurations.

    Includes copied requests, IDs, provenance, statuses and completed result JSON.
    This is not SQLite page allocation or a reclaimable-byte estimate.
    """
    experiment_fields = (
        "id",
        "status",
        "request_json",
        "history_id",
        "history_sha256",
        "rankings_id",
        "rankings_sha256",
        "code_version",
        "created_at",
    )
    run_fields = ("experiment_id", "configuration_id", "status", "result_json")

    def total(table, fields):
        parts = " + ".join(f"coalesce(length(CAST({field} AS BLOB)), 0)" for field in fields)
        return db.execute(f"SELECT coalesce(sum({parts}), 0) FROM {table}").fetchone()[0]

    return (
        total("experiments", experiment_fields)
        + total("runs", run_fields)
        + db.execute(
            "SELECT 8 * count(*) FROM runs"  # fixed-width ordinal in the logical contract
        ).fetchone()[0]
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
        self.path = Path(path)
        require_database(self.path)

    def logical_experiment_bytes(self) -> int:
        with connection(self.path) as db:
            return _logical_experiment_bytes(db)

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
            if quota_bytes < _logical_experiment_bytes(db):
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
        return measure(self.path, limit, self.logical_experiment_bytes(), disk_usage=disk_usage)

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

    def create_configuration(self, name: str, strategy: Strategy) -> str:
        if not name.strip() or not isinstance(strategy, Strategy):
            raise ValueError("configuration needs a name and validated strategy")
        identifier = uuid4().hex
        with _transaction(self.path) as db:
            db.execute(
                "INSERT INTO configurations VALUES (?, ?, ?)",
                (identifier, name, strategy.model_dump_json()),
            )
        return identifier

    def get_configuration(self, identifier: str) -> SavedConfiguration | None:
        with connection(self.path) as db:
            row = db.execute(
                "SELECT id, name, strategy_json FROM configurations WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            return None
        return SavedConfiguration(row[0], row[1], Strategy.model_validate_json(row[2]))

    def list_configurations(self) -> list[SavedConfiguration]:
        with connection(self.path) as db:
            rows = db.execute(
                "SELECT id, name, strategy_json FROM configurations ORDER BY rowid"
            ).fetchall()
        return [SavedConfiguration(i, n, Strategy.model_validate_json(s)) for i, n, s in rows]

    def update_configuration(self, identifier: str, name: str, strategy: Strategy) -> bool:
        if not name.strip() or not isinstance(strategy, Strategy):
            raise ValueError("configuration needs a name and validated strategy")
        with _transaction(self.path) as db:
            changed = db.execute(
                "UPDATE configurations SET name = ?, strategy_json = ? WHERE id = ?",
                (name, strategy.model_dump_json(), identifier),
            ).rowcount
        return bool(changed)

    def delete_configuration(self, identifier: str) -> bool:
        with _transaction(self.path) as db:
            changed = db.execute("DELETE FROM configurations WHERE id = ?", (identifier,)).rowcount
        return bool(changed)

    def create_experiment(
        self,
        request: ExperimentRequest,
        *,
        history_id: str,
        history_sha256: str,
        rankings_id: str,
        rankings_sha256: str,
        code_version: str,
        configuration_ids: tuple[str | None, ...] | None = None,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> str:
        if not isinstance(request, ExperimentRequest):
            raise ValueError("experiment requires a validated request")
        sources = (history_id, rankings_id, code_version)
        hashes = (history_sha256, rankings_sha256)
        if any(not s for s in sources) or any(
            len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in hashes
        ):
            raise ValueError("source IDs, lowercase SHA-256 hashes and code version required")
        links = (
            configuration_ids
            if configuration_ids is not None
            else (None,) * len(request.strategies)
        )
        if len(links) != len(request.strategies):
            raise ValueError("configuration links must match strategies")
        identifier = uuid4().hex
        with _transaction(self.path) as db:
            for ordinal, link in enumerate(links):
                if link is None:
                    continue
                saved = db.execute(
                    "SELECT strategy_json FROM configurations WHERE id = ?", (link,)
                ).fetchone()
                if saved is None:
                    raise ValueError(f"configuration not found: {link}")
                if Strategy.model_validate_json(saved[0]) != request.strategies[ordinal]:
                    raise ValueError("configuration differs from experiment strategy")
            experiment_fields = (
                identifier,
                ExperimentStatus.PENDING.value,
                request.model_dump_json(),
                history_id,
                history_sha256,
                rankings_id,
                rankings_sha256,
                code_version,
                _now_iso(),
            )
            run_fields = [
                (identifier, i, link, RunStatus.PENDING.value) for i, link in enumerate(links)
            ]
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            projected = sum(len(value.encode("utf-8")) for value in experiment_fields)
            projected += sum(
                len(identifier.encode("utf-8"))
                + 8
                + len(status.encode("utf-8"))
                + (len(link.encode("utf-8")) if link else 0)
                for _, _, link, status in run_fields
            )
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                disk_usage=disk_usage,
            ).require_capacity(projected)
            db.execute(
                "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                experiment_fields,
            )
            db.executemany("INSERT INTO runs VALUES (?, ?, ?, ?, NULL)", run_fields)
        return identifier

    def get_experiment(self, identifier: str) -> SavedExperiment | None:
        with connection(self.path) as db:
            db.execute("BEGIN")  # coherent parent and children, even under another writer
            return _load_experiment(db, identifier)

    def list_experiments(self) -> list[SavedExperiment]:
        with connection(self.path) as db:
            ids = [row[0] for row in db.execute("SELECT id FROM experiments ORDER BY rowid")]
        return [
            saved for identifier in ids if (saved := self.get_experiment(identifier)) is not None
        ]

    def delete_experiment(self, identifier: str) -> bool:
        # A pending/running row may be owned by a queue; never remove active work.
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT status FROM experiments WHERE id = ?", (identifier,)
            ).fetchone()
            if row is not None and row[0] == "running":
                raise ValueError("cannot delete a running experiment")
            if row is not None and row[0] == "pending":
                raise ValueError("cannot delete an active experiment")
            changed = db.execute("DELETE FROM experiments WHERE id = ?", (identifier,)).rowcount
        return bool(changed)

    def discard_pending(self, identifier: str) -> None:
        """Compensate a failed enqueue only if no worker has claimed the row."""
        with _transaction(self.path) as db:
            changed = db.execute(
                "DELETE FROM experiments WHERE id = ? AND status = 'pending'", (identifier,)
            ).rowcount
            if changed != 1:
                raise RuntimeError("could not discard unqueued experiment")

    def search_experiments(
        self,
        offset: int,
        limit: int,
        *,
        name_contains: str | None = None,
        status: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[int, list[SavedExperiment]]:
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        if name_contains is not None and not isinstance(name_contains, str):
            raise ValueError("name_contains must be a string")
        if status is not None and status not in {item.value for item in ExperimentStatus}:
            raise ValueError("invalid experiment status")
        if sort not in _SEARCH_SORTS or order not in _SEARCH_ORDERS:
            raise ValueError("invalid experiment sort")
        pattern = None if name_contains is None else f"%{_escape_like(name_contains.casefold())}%"
        filters = (pattern, pattern, status, status)
        with connection(self.path) as db:
            db.create_function("unicode_casefold", 1, str.casefold, deterministic=True)
            db.execute("BEGIN")  # total, IDs and snapshots share one read view
            total = db.execute(
                "SELECT count(*) FROM experiments WHERE "
                "(? IS NULL OR unicode_casefold(json_extract(request_json, '$.name')) "
                "LIKE ? ESCAPE '\\') AND (? IS NULL OR status = ?)",
                filters,
            ).fetchone()[0]
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM experiments WHERE "
                    "(? IS NULL OR unicode_casefold(json_extract(request_json, '$.name')) "
                    "LIKE ? ESCAPE '\\') AND (? IS NULL OR status = ?) ORDER BY "
                    "CASE WHEN ? = 'created_at' AND ? = 'asc' THEN created_at END ASC, "
                    "CASE WHEN ? = 'created_at' AND ? = 'desc' THEN created_at END DESC, "
                    "CASE WHEN ? = 'name' AND ? = 'asc' "
                    "THEN json_extract(request_json, '$.name') END COLLATE NOCASE ASC, "
                    "CASE WHEN ? = 'name' AND ? = 'desc' "
                    "THEN json_extract(request_json, '$.name') END COLLATE NOCASE DESC, "
                    "CASE WHEN ? = 'status' AND ? = 'asc' THEN status END ASC, "
                    "CASE WHEN ? = 'status' AND ? = 'desc' THEN status END DESC, "
                    "CASE WHEN ? = 'asc' THEN id END ASC, id DESC LIMIT ? OFFSET ?",
                    (*filters, *(sort, order) * 6, order, limit, offset),
                )
            ]
            rows = [_load_experiment(db, identifier) for identifier in ids]
        return total, [row for row in rows if row is not None]

    def page_experiments(self, offset: int, limit: int):
        with connection(self.path) as db:
            total = db.execute("SELECT count(*) FROM experiments").fetchone()[0]
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM experiments ORDER BY rowid DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]
        return total, [
            saved for identifier in ids if (saved := self.get_experiment(identifier)) is not None
        ]

    def page_held_ids(self, offset: int, limit: int):
        with connection(self.path) as db:
            total = db.execute("SELECT count(*) FROM experiments WHERE status = 'held'").fetchone()[
                0
            ]
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM experiments WHERE status = 'held' "
                    "ORDER BY rowid LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]
        return total, ids

    def page_configurations(self, offset: int, limit: int):
        with connection(self.path) as db:
            total = db.execute("SELECT count(*) FROM configurations").fetchone()[0]
            rows = db.execute(
                "SELECT id, name, strategy_json FROM configurations "
                "ORDER BY rowid DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return total, [
            SavedConfiguration(i, n, Strategy.model_validate_json(s)) for i, n, s in rows
        ]

    def start_run(self, identifier: str, ordinal: int):
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT status FROM experiments WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None or row[0] not in ("pending", "held", "running"):
                raise ValueError("experiment not startable or missing")
            if db.execute(
                "SELECT 1 FROM runs WHERE experiment_id = ? AND status = 'running'",
                (identifier,),
            ).fetchone():
                raise ValueError("another run is already running")
            changed = db.execute(
                "UPDATE runs SET status = 'running' WHERE experiment_id = ? AND ordinal = ? "
                "AND status = 'pending'",
                (identifier, ordinal),
            ).rowcount
            if not changed:
                raise ValueError("run not pending or missing")
            db.execute("UPDATE experiments SET status = 'running' WHERE id = ?", (identifier,))

    def complete_run(
        self,
        identifier: str,
        ordinal: int,
        result: SessionResult,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ):
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT request_json, status FROM experiments WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None or row[1] != "running":
                raise ValueError("experiment not running or missing")
            request = ExperimentRequest.model_validate_json(row[0])
            if not 0 <= ordinal < len(request.strategies):
                raise ValueError("run ordinal missing")
            _validate_result(
                result, request.conditions.capital, request.strategies[ordinal].coverage
            )
            serialized = _result_json(result)
            # Resolve persisted preference under the same writer lock as the result update.
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            status = measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                disk_usage=disk_usage,
            )
            status.require_capacity(len(serialized.encode("utf-8")) + 2)  # completed vs running
            changed = db.execute(
                "UPDATE runs SET status = 'completed', result_json = ? "
                "WHERE experiment_id = ? AND ordinal = ? AND status = 'running'",
                (serialized, identifier, ordinal),
            ).rowcount
            if not changed:
                raise ValueError("run not running or already completed")

    def complete_experiment(self, identifier: str):
        with _transaction(self.path) as db:
            changed = db.execute(
                "UPDATE experiments SET status = 'completed' WHERE id = ? AND status = 'running' "
                "AND NOT EXISTS (SELECT 1 FROM runs WHERE experiment_id = ? "
                "AND status != 'completed')",
                (identifier, identifier),
            ).rowcount
            if not changed:
                raise ValueError("experiment missing, not running or has incomplete runs")

    def recover_jobs(self):
        """At server startup, atomically interrupt abandoned work and hold unstarted jobs.

        Only call before accepting new work; no other live queue may own this database.
        """
        with _transaction(self.path) as db:
            db.execute("UPDATE runs SET status = 'interrupted' WHERE status = 'running'")
            db.execute(
                "UPDATE runs SET status = 'not_run' WHERE status = 'pending' AND "
                "experiment_id IN (SELECT id FROM experiments WHERE status = 'running')"
            )
            db.execute("UPDATE experiments SET status = 'interrupted' WHERE status = 'running'")
            db.execute("UPDATE experiments SET status = 'held' WHERE status = 'pending'")

    def finish_incomplete(self, identifier: str, status: ExperimentStatus):
        """Atomically finish active work (or cancel a queued job) without touching results."""
        if status not in (
            ExperimentStatus.CANCELLED,
            ExperimentStatus.INTERRUPTED,
            ExperimentStatus.FAILED,
        ):
            raise ValueError("invalid incomplete experiment status")
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT status FROM experiments WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None or row[0] not in ("running", "pending", "held"):
                raise ValueError("experiment is not active or queued")
            if row[0] != "running" and status is not ExperimentStatus.CANCELLED:
                raise ValueError("only running work can fail or be interrupted")
            run_status = {
                ExperimentStatus.CANCELLED: RunStatus.CANCELLED,
                ExperimentStatus.INTERRUPTED: RunStatus.INTERRUPTED,
                ExperimentStatus.FAILED: RunStatus.FAILED,
            }[status]
            db.execute(
                "UPDATE runs SET status = ? WHERE experiment_id = ? AND status = 'running'",
                (run_status.value, identifier),
            )
            db.execute(
                "UPDATE runs SET status = 'not_run' WHERE experiment_id = ? AND status = 'pending'",
                (identifier,),
            )
            db.execute(
                "UPDATE experiments SET status = ? WHERE id = ?",
                (status.value, identifier),
            )

    def mark_run(self, identifier: str, ordinal: int, status: RunStatus):
        if status not in (
            RunStatus.CANCELLED,
            RunStatus.NOT_RUN,
            RunStatus.INTERRUPTED,
            RunStatus.FAILED,
        ):
            raise ValueError("invalid incomplete run status")
        expected = "pending" if status is RunStatus.NOT_RUN else "running"
        with _transaction(self.path) as db:
            changed = db.execute(
                "UPDATE runs SET status = ? WHERE experiment_id = ? AND ordinal = ? AND status = ?",
                (status.value, identifier, ordinal, expected),
            ).rowcount
            if not changed:
                raise ValueError("run missing or not in expected state")

    def mark_experiment(self, identifier: str, status: ExperimentStatus):
        if status not in (
            ExperimentStatus.HELD,
            ExperimentStatus.CANCELLED,
            ExperimentStatus.INTERRUPTED,
            ExperimentStatus.FAILED,
        ):
            raise ValueError("invalid experiment transition")
        expected = "pending" if status is ExperimentStatus.HELD else "running"
        with _transaction(self.path) as db:
            changed = db.execute(
                "UPDATE experiments SET status = ? WHERE id = ? AND status = ?",
                (status.value, identifier, expected),
            ).rowcount
            if not changed:
                raise ValueError("experiment missing or not in expected state")
