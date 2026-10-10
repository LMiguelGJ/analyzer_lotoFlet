"""SQLite persistence: quota accounting and saved backtests."""

import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from laboratorio.settings import DEFAULT_QUOTA_BYTES
from laboratorio.storage.backtest_trace import (
    bet_projection,
    build_trace,
    session_summary,
    trace_metadata,
    validate_trace,
)
from laboratorio.storage.database import connection, require_database
from laboratorio.storage.quota import measure, validate_quota_bytes


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
    """Count each stored profile JSON copy, including immutable experiment snapshots."""
    row = db.execute(
        "SELECT (SELECT coalesce(sum(length(CAST(profile_json AS BLOB))), 0) "
        "FROM game_profiles) + (SELECT coalesce(sum(length(CAST(profile_json AS BLOB))), 0) "
        "FROM experiment_profiles)"
    ).fetchone()
    return row[0]


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


def _admission_logical_bytes(db) -> int:
    return (
        _logical_experiment_bytes(db)
        + _profile_artifact_bytes(db)
        + _dataset_artifact_bytes(db)
        + _strategy_artifact_bytes(db)
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
        return measure(
            self.path,
            limit,
            experiment_bytes,
            profile_artifact_bytes=profile_bytes,
            dataset_artifact_bytes=dataset_bytes,
            strategy_artifact_bytes=strategy_bytes,
            disk_usage=disk_usage,
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

    def create_backtest(self, name: str, config: dict, result, rows=None):
        identifier = str(uuid4())
        created_at = _now_iso()
        result_payload = {
            "reached_goal": result.reached_goal,
            "quiebres": result.quiebre,
            "completed": result.completed,
            "goal_rate": result.goal_rate,
            "neto_medio": result.neto_medio,
            "incomplete": result.incomplete,
            "window": {
                "bets": result.window.bets,
                "wagered": result.window.wagered,
                "paid": result.window.paid,
                "sessions": len(result.sessions),
                "incomplete": result.incomplete,
            },
        }
        result_payload["trace"] = build_trace(result, config, result_payload, rows)
        config_json = json.dumps(
            config, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        result_json = json.dumps(
            result_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        self._validate_simulation_backtest((identifier, name, config_json, result_json, created_at))
        with _transaction(self.path) as db:
            db.execute(
                "INSERT INTO backtests (id, name, config_json, result_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (identifier, name, config_json, result_json, created_at),
            )
        return identifier, created_at

    @staticmethod
    def _backtest_row(row):
        identifier, name, _, _, created_at = row
        config, result = Repository._validate_simulation_backtest(row)
        return {
            "id": identifier,
            "name": name,
            "created_at": created_at,
            **{key: value for key, value in result.items() if key != "trace"},
            "trace": trace_metadata(result.get("trace")),
            "config": config,
        }

    @staticmethod
    def _validate_simulation_backtest(row):
        import math
        from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

        from laboratorio.api.backtests import CreateBacktest
        from laboratorio.domain.backtest import BacktestConfig
        from laboratorio.domain.contracts import make_game

        identifier, name, config_json, result_json, _ = row
        try:
            config_payload = json.loads(config_json)
            config = CreateBacktest.model_validate(config_payload)
            if config.name != name:
                raise ValueError("backtest database and config names differ")
            game = make_game(
                "Backtest game",
                config.game.numbers,
                config.game.positions,
                config.game.prizes,
                True,
                config.game.min_stake,
            )
            BacktestConfig(
                config.conditions.capital,
                config.conditions.goal,
                game.numbers,
                game.positions,
                game.prizes,
                game.minimum_stake,
                config.strategy.coverage,
                config.strategy.staking,
            )
            if config.strategy.selector == "parity" and config.strategy.coverage > 50:
                raise ValueError("parity selection exceeds the producer coverage limit")
            result = json.loads(result_json)
            expected = {
                "reached_goal",
                "completed",
                "goal_rate",
                "quiebres",
                "neto_medio",
                "incomplete",
                "window",
            }
            if type(result) is not dict or result.keys() not in (expected, expected | {"trace"}):
                raise ValueError("saved backtest report has an invalid shape")
            counts = (
                result["reached_goal"],
                result["completed"],
                result["quiebres"],
                result["incomplete"],
            )
            if any(type(value) is not int or value < 0 for value in counts):
                raise ValueError("saved backtest counts are invalid")
            if result["completed"] != result["reached_goal"] + result["quiebres"]:
                raise ValueError("saved backtest completed count does not reconcile")
            expected_rate = (
                0.0
                if result["completed"] == 0
                else float(
                    (Decimal(result["reached_goal"] * 100) / result["completed"]).quantize(
                        Decimal("0.1"), rounding=ROUND_HALF_UP
                    )
                )
            )
            if result["goal_rate"] != expected_rate:
                raise ValueError("saved backtest goal rate does not reconcile")
            if (
                type(result["goal_rate"]) not in (int, float)
                or not math.isfinite(result["goal_rate"])
                or not 0 <= result["goal_rate"] <= 100
                or type(result["neto_medio"]) not in (int, float)
                or not math.isfinite(result["neto_medio"])
            ):
                raise ValueError("saved backtest metrics are invalid")
            window = result["window"]
            if type(window) is not dict or window.keys() != {
                "bets",
                "wagered",
                "paid",
                "sessions",
                "incomplete",
            }:
                raise ValueError("saved backtest window has an invalid shape")
            if any(type(window[key]) is not int or window[key] < 0 for key in window):
                raise ValueError("saved backtest window totals are invalid")
            if (
                window["sessions"] != result["completed"] + result["incomplete"]
                or window["incomplete"] != result["incomplete"]
            ):
                raise ValueError("saved backtest window does not reconcile")
            if window["bets"] == 0 and (window["wagered"] != 0 or window["paid"] != 0):
                raise ValueError("empty backtest window has stake or payout totals")
            if window["bets"] > 0 and window["wagered"] == 0:
                raise ValueError("betting window has no wagered amount")
            if "trace" in result:
                validate_trace(
                    result["trace"],
                    config_payload,
                    {key: value for key, value in result.items() if key != "trace"},
                )
            return config_payload, result
        except (
            TypeError,
            ValueError,
            KeyError,
            OverflowError,
            RecursionError,
            InvalidOperation,
        ) as exc:
            raise ValueError(f"stored backtest {identifier} is corrupt") from exc

    def get_backtest(self, identifier: str):
        with connection(self.path) as db:
            row = db.execute(
                "SELECT id, name, config_json, result_json, created_at FROM backtests WHERE id = ?",
                (identifier,),
            ).fetchone()
        return None if row is None else self._backtest_row(row)

    def page_backtest_trace(self, identifier: str, offset: int, limit: int, ordinal=None):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        if ordinal is not None and (type(ordinal) is not int or ordinal < 0):
            raise ValueError("session ordinal out of range")
        with connection(self.path) as db:
            row = db.execute(
                "SELECT id, name, config_json, result_json, created_at FROM backtests WHERE id = ?",
                (identifier,),
            ).fetchone()
        if row is None:
            return None
        _, result = self._validate_simulation_backtest(row)
        trace = result.get("trace")
        metadata = trace_metadata(trace)
        if ordinal is None:
            sessions = trace["sessions"] if trace is not None else []
            return {
                "id": identifier,
                "trace": metadata,
                "total": len(sessions),
                "offset": offset,
                "limit": limit,
                "items": [session_summary(item) for item in sessions[offset : offset + limit]],
            }
        # An existing but uncaptured original ordinal is unavailable, not missing.
        if ordinal >= result["window"]["sessions"]:
            return None
        if trace is None or ordinal >= trace["stored_sessions"]:
            raise ValueError("session detail was not stored")
        session = trace["sessions"][ordinal]
        return {
            "id": identifier,
            "ordinal": ordinal,
            "trace": metadata,
            "session": session_summary(session),
            "total": len(session["bets"]),
            "offset": offset,
            "limit": limit,
            "items": [bet_projection(bet) for bet in session["bets"][offset : offset + limit]],
        }

    def search_backtests(self, offset: int, limit: int):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        with connection(self.path) as db:
            db.execute("BEGIN")
            total = db.execute("SELECT count(*) FROM backtests").fetchone()[0]
            rows = db.execute(
                "SELECT id, name, config_json, result_json, created_at FROM backtests "
                "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return total, [self._backtest_row(row) for row in rows]
