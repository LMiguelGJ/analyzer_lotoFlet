"""Small transactional repository for saved strategies and immutable run snapshots."""

import hashlib
import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from laboratorio.domain.contracts import (
    ExperimentRequest,
    ExperimentStatus,
    GameProfile,
    Outcome,
    RunStatus,
    Strategy,
    legacy_quiniela_80_profile,
)
from laboratorio.domain.profile_request import (
    ProfileExperimentRequest,
    load_profile_request,
    profile_sha256,
    serialize_profile_request,
)
from laboratorio.domain.profile_request_v2 import (
    ProfileCyclingRequest,
    load_profile_cycling_request,
    serialize_profile_cycling_request,
)
from laboratorio.domain.profile_request_v3 import (
    ProfileAudazRequest,
    load_profile_audaz_request,
    serialize_profile_audaz_request,
)
from laboratorio.domain.profile_request_v4 import (
    ProfileRecoveryRequest,
    load_profile_recovery_request,
    serialize_profile_recovery_request,
)
from laboratorio.domain.profile_result import (
    load_profile_result,
    serialize_profile_result,
    validate_profile_result,
)
from laboratorio.domain.profile_result_v2 import (
    ProfileCyclingResult,
    load_profile_cycling_result,
    serialize_profile_cycling_result,
    validate_profile_cycling_result,
)
from laboratorio.domain.profile_result_v3 import (
    ProfileAudazResult,
    load_profile_audaz_result,
    serialize_profile_audaz_result,
    validate_profile_audaz_result,
)
from laboratorio.domain.profile_result_v4 import (
    ProfileRecoveryResult,
    load_profile_recovery_result,
    serialize_profile_recovery_result,
    validate_profile_recovery_result,
)
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileDraw,
    ProfileSelector,
    ProfileSessionResult,
    ProfileStaking,
    _minute,
    run_profile_session,
)
from laboratorio.domain.session import Bet, SessionResult
from laboratorio.importing.datasets import Promotion, checked_dataset
from laboratorio.importing.records import (
    ClockDeclaration,
    ColumnMapping,
    SourceMetadata,
    canonical_bytes,
    parse_records,
)
from laboratorio.settings import DEFAULT_QUOTA_BYTES
from laboratorio.storage.database import connection, require_database
from laboratorio.storage.quota import measure, validate_quota_bytes

SQLITE_MAX = 2**63 - 1


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
    result: (
        SessionResult
        | ProfileSessionResult
        | ProfileCyclingResult
        | ProfileAudazResult
        | ProfileRecoveryResult
        | None
    )
    result_kind: Literal["legacy", "profile"] = "legacy"
    result_schema_version: int | None = None


@dataclass(frozen=True)
class SavedExperiment:
    id: str
    status: ExperimentStatus
    request: (
        ExperimentRequest
        | ProfileExperimentRequest
        | ProfileCyclingRequest
        | ProfileAudazRequest
        | ProfileRecoveryRequest
    )
    history_id: str
    history_sha256: str
    rankings_id: str
    rankings_sha256: str
    code_version: str
    created_at: str | None
    runs: tuple[SavedRun, ...]
    profile: GameProfile
    request_kind: Literal["legacy", "profile"] = "legacy"
    request_schema_version: int = 1


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
    if not isinstance(data, dict) or "kind" in data or "schema_version" in data:
        raise ValueError("legacy result wire cannot carry a versioned envelope")
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


def _dataset_draws(dataset):
    """Use every digest-checked source row, including pre-start rows."""
    return tuple(
        ProfileDraw(
            1, f"{row.date} {row.time}", _minute(f"{row.date} {row.time}"), row.numbers, True
        )
        for row in dataset.preview.records
    )


def _load_experiment(db, identifier: str) -> SavedExperiment | None:
    row = db.execute("SELECT * FROM experiments WHERE id = ?", (identifier,)).fetchone()
    if row is None:
        return None
    snapshot = db.execute(
        "SELECT s.profile_id, s.revision, s.profile_json, p.profile_json "
        "FROM experiment_profiles AS s LEFT JOIN game_profiles AS p "
        "ON p.profile_id = s.profile_id AND p.revision = s.revision "
        "WHERE s.experiment_id = ?",
        (identifier,),
    ).fetchone()
    if snapshot is None or snapshot[2] != snapshot[3]:
        raise ValueError("missing or corrupt experiment profile snapshot")
    try:
        profile = GameProfile.model_validate_json(snapshot[2])
    except ValueError as exc:
        raise ValueError("corrupt experiment profile snapshot") from exc
    if (profile.profile_id, profile.revision) != snapshot[:2]:
        raise ValueError("corrupt experiment profile snapshot identity")
    request_kind, request_version = row[9], row[10]
    if request_kind == "legacy" and type(request_version) is int and request_version == 1:
        request = ExperimentRequest.model_validate_json(row[2])
    elif request_kind == "profile" and type(request_version) is int and request_version == 1:
        request = load_profile_request(row[2])
    elif request_kind == "profile" and type(request_version) is int and request_version == 2:
        request = load_profile_cycling_request(row[2])
    elif request_kind == "profile" and type(request_version) is int and request_version == 3:
        request = load_profile_audaz_request(row[2])
    elif request_kind == "profile" and type(request_version) is int and request_version == 4:
        request = load_profile_recovery_request(row[2])
    else:
        raise ValueError("unsupported stored request kind/version")
    if request_kind == "profile":
        if not isinstance(
            request,
            (
                ProfileExperimentRequest,
                ProfileCyclingRequest,
                ProfileAudazRequest,
                ProfileRecoveryRequest,
            ),
        ):
            raise ValueError("profile request binding mismatch")
        if (
            request.profile_id != profile.profile_id
            or request.profile_revision != profile.revision
            or request.profile_sha256 != profile_sha256(profile)
        ):
            raise ValueError("profile request differs from experiment profile snapshot")
    runs = db.execute(
        "SELECT ordinal, configuration_id, status, result_json, result_kind, "
        "result_schema_version FROM runs "
        "WHERE experiment_id = ? ORDER BY ordinal",
        (identifier,),
    ).fetchall()
    saved_runs = []
    for ordinal, link, status, value, result_kind, result_version in runs:
        if result_kind != request_kind:
            raise ValueError("mixed request/result kind corruption")
        if value is None:
            if result_version is not None:
                raise ValueError("absent result has a schema version")
            result = None
        elif type(result_version) is not int or result_version != request_version:
            raise ValueError("mixed request/result schema version corruption")
        elif result_kind == "profile" and result_version == 2:
            result = load_profile_cycling_result(value)
        elif result_kind == "profile" and result_version == 3:
            result = load_profile_audaz_result(value)
        elif result_kind == "profile" and result_version == 4:
            result = load_profile_recovery_result(value)
        elif result_kind == "profile" and result_version == 1:
            result = load_profile_result(value)
        elif result_kind == "legacy" and result_version == 1:
            result = _read_result(value)
        else:
            raise ValueError("unsupported stored result kind/version")
        saved_runs.append(
            SavedRun(ordinal, link, RunStatus(status), result, result_kind, result_version)
        )
    return SavedExperiment(
        row[0],
        ExperimentStatus(row[1]),
        request,
        row[3],
        row[4],
        row[5],
        row[6],
        row[7],
        row[8],
        tuple(saved_runs),
        profile,
        request_kind,
        request_version,
    )


def _validate_result(result, capital, coverage):
    if not isinstance(result, SessionResult) or not isinstance(result.outcome, Outcome):
        raise ValueError("invalid completed result")
    if type(result.bets_count) is not int or not isinstance(result.bets, tuple):
        raise ValueError("invalid completed replay structure")
    if result.bets_count != len(result.bets) or not result.bets:
        raise ValueError("bets_count must match nonempty replay")
    balance = capital
    wagered = paid = 0
    for bet in result.bets:
        if (
            not isinstance(bet, Bet)
            or not isinstance(bet.label, str)
            or not bet.label
            or not isinstance(bet.numbers, tuple)
            or not isinstance(bet.results, tuple)
            or any(type(n) is not int or not 0 <= n < 100 for n in (*bet.numbers, *bet.results))
        ):
            raise ValueError("invalid bet replay structure")
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


def validate_result_payload(result, capital, coverage):
    """Use the same semantic and JSON contract at IPC admission and persistence."""
    _validate_result(result, capital, coverage)
    return _result_json(result)


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


def _admission_logical_bytes(db) -> int:
    return _logical_experiment_bytes(db) + _profile_artifact_bytes(db) + _dataset_artifact_bytes(db)


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

    def get_dataset(self, dataset_sha256: str):
        """Read an immutable artifact only after verifying raw bytes and canonical context."""
        with connection(self.path) as db:
            row = db.execute(
                "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
                "FROM datasets WHERE dataset_sha256 = ?",
                (dataset_sha256,),
            ).fetchone()
            return None if row is None else checked_dataset(row)

    def page_datasets(self, offset: int, limit: int):
        """Slice by indexed metadata first; verify only selected immutable artifacts."""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        with connection(self.path) as db:
            db.execute("BEGIN")  # count, keys and selected blobs share a read snapshot
            total = db.execute("SELECT count(*) FROM datasets").fetchone()[0]
            keys = db.execute(
                "SELECT dataset_sha256 FROM datasets ORDER BY created_at, dataset_sha256 "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            rows = [
                db.execute(
                    "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
                    "FROM datasets WHERE dataset_sha256 = ?",
                    (key,),
                ).fetchone()
                for (key,) in keys
            ]
            return total, [checked_dataset(row) for row in rows]

    def preflight_profile_dataset(
        self,
        dataset_sha256: str,
        profile: GameProfile,
        conditions: ProfileConditions,
        selector: ProfileSelector,
        staking: ProfileStaking,
    ):
        """Check persisted identity and static session admission; do not execute draws.

        Inline import snapshots are discoverable even without a registered profile.
        Execution callers must register the exact snapshot separately before this gate.
        """
        if not isinstance(profile, GameProfile):
            raise TypeError("a validated game profile is required")
        profile = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
        saved = self.get_dataset(dataset_sha256)
        if saved is None:
            raise ValueError("dataset not found")
        persisted = self.get_game_profile(profile.profile_id, profile.revision)
        if persisted is None:
            raise ValueError("dataset profile must be persisted before execution")
        try:
            embedded = GameProfile.model_validate(json.loads(saved.canonical_json)["profile"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("corrupt dataset profile snapshot") from exc
        if embedded != profile or persisted != profile:
            raise ValueError("dataset profile differs from selected persisted profile")
        if (
            type(conditions) is not ProfileConditions
            or type(selector) is not ProfileSelector
            or type(staking) is not ProfileStaking
        ):
            raise TypeError("typed session conditions, selector and staking are required")
        for config in (conditions, selector, staking):
            config.__post_init__()
        if selector.coverage > profile.max_coverage or selector.coverage > profile.universe_size:
            raise ValueError("selector coverage exceeds profile")
        if selector.numbers is not None and any(
            number >= profile.universe_size for number in selector.numbers
        ):
            raise ValueError("static number exceeds profile universe")
        stake = staking.per_number_stake
        if (
            not profile.minimum_stake <= stake <= profile.maximum_stake
            or stake % profile.stake_increment
        ):
            raise ValueError("stake is incompatible with profile bounds or increment")
        cost = stake * selector.coverage
        if cost > profile.max_exposure or cost > conditions.capital or cost > SQLITE_MAX:
            raise ValueError("initial capital or profile exposure cannot afford the prescribed bet")
        if not any(
            f"{record.date} {record.time}" == conditions.start_draw
            for record in saved.preview.records
        ):
            raise ValueError("start draw must exist in dataset")
        return saved

    def promote_dataset(
        self,
        data: bytes,
        *,
        format: Literal["csv", "json"],
        mapping: ColumnMapping,
        source: SourceMetadata,
        clock: ClockDeclaration,
        profile: GameProfile,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> Promotion:
        """Reparse original bytes; preview data is never an input to promotion."""
        if not isinstance(profile, GameProfile):
            raise ValueError("a validated game profile is required")
        profile = GameProfile.model_validate_json(profile.model_dump_json())
        preview = parse_records(
            data, format=format, mapping=mapping, source=source, clock=clock, profile=profile
        )
        if not preview.promotable or preview.dataset_sha256 is None:
            raise ValueError("dataset source is not promotable")
        canonical = canonical_bytes(preview.records, format, mapping, clock, source, profile)
        if hashlib.sha256(canonical).hexdigest() != preview.dataset_sha256:
            raise ValueError("dataset canonical hash mismatch")
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
                "FROM datasets WHERE dataset_sha256 = ?",
                (preview.dataset_sha256,),
            ).fetchone()
            if row is not None:
                saved = checked_dataset(row)
                return Promotion(
                    saved,
                    False,
                    saved.source_sha256 != preview.source_sha256,
                    preview.source_sha256,
                )
            created_at = _now_iso()
            projected = len(canonical) + len(data) + 128 + len(created_at.encode("utf-8"))
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                disk_usage=disk_usage,
            ).require_capacity(projected)
            db.execute(
                "INSERT INTO datasets VALUES (?, ?, ?, ?, ?)",
                (
                    preview.dataset_sha256,
                    preview.source_sha256,
                    canonical.decode("utf-8"),
                    data,
                    created_at,
                ),
            )
            row = db.execute(
                "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
                "FROM datasets WHERE dataset_sha256 = ?",
                (preview.dataset_sha256,),
            ).fetchone()
            return Promotion(checked_dataset(row), True, False, preview.source_sha256)

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
        return measure(
            self.path,
            limit,
            experiment_bytes,
            profile_artifact_bytes=profile_bytes,
            dataset_artifact_bytes=dataset_bytes,
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

    def create_game_profile(
        self,
        profile: GameProfile,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> GameProfile:
        """Append a version with admission; an identical retry is a zero-growth no-op."""
        if not isinstance(profile, GameProfile):
            raise ValueError("a validated game profile is required")
        # model_copy(update=...) bypasses Pydantic validation, including reserved IDs.
        profile = GameProfile.model_validate_json(profile.model_dump_json())
        serialized = profile.model_dump_json()
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT profile_json FROM game_profiles WHERE profile_id = ? AND revision = ?",
                (profile.profile_id, profile.revision),
            ).fetchone()
            if row is None:
                effective = _effective_quota(db, quota_bytes, quota_explicit)
                measure(
                    self.path,
                    effective.effective_bytes,
                    _logical_experiment_bytes(db),
                    profile_artifact_bytes=_profile_artifact_bytes(db),
                    dataset_artifact_bytes=_dataset_artifact_bytes(db),
                    disk_usage=disk_usage,
                ).require_capacity(len(serialized.encode("utf-8")))
                db.execute(
                    "INSERT INTO game_profiles VALUES (?, ?, ?)",
                    (profile.profile_id, profile.revision, serialized),
                )
            elif row[0] != serialized:
                raise ValueError("game profile version already exists with different content")
        return profile

    def get_game_profile(self, profile_id: str, revision: int) -> GameProfile | None:
        with connection(self.path) as db:
            row = db.execute(
                "SELECT profile_json FROM game_profiles WHERE profile_id = ? AND revision = ?",
                (profile_id, revision),
            ).fetchone()
        if row is None:
            return None
        profile = GameProfile.model_validate_json(row[0])
        if (profile.profile_id, profile.revision) != (profile_id, revision):
            raise ValueError("corrupt game profile identity")
        return profile

    def list_game_profiles(self) -> list[GameProfile]:
        with connection(self.path) as db:
            keys = db.execute(
                "SELECT profile_id, revision FROM game_profiles ORDER BY profile_id, revision"
            ).fetchall()
        profiles = [self.get_game_profile(identifier, revision) for identifier, revision in keys]
        if any(profile is None for profile in profiles):
            raise ValueError("missing game profile")
        return [profile for profile in profiles if profile is not None]

    def page_game_profiles(self, offset: int, limit: int) -> tuple[int, list[GameProfile]]:
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        with connection(self.path) as db:
            db.execute("BEGIN")  # count and rows share one read snapshot
            total = db.execute("SELECT count(*) FROM game_profiles").fetchone()[0]
            rows = db.execute(
                "SELECT profile_id, revision, profile_json FROM game_profiles "
                "ORDER BY profile_id, revision LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        profiles = []
        for identifier, revision, serialized in rows:
            try:
                profile = GameProfile.model_validate_json(serialized)
            except ValueError as exc:
                raise ValueError("corrupt game profile") from exc
            if (profile.profile_id, profile.revision) != (identifier, revision):
                raise ValueError("corrupt game profile identity")
            profiles.append(profile)
        return total, profiles

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

    def create_profile_experiment(
        self,
        request: ProfileExperimentRequest,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> str:
        """Persist one bound profile run; no queue or public API is created here.

        Synchronous and potentially expensive: the future queue must call this
        off the API event loop. Preflight authenticates the complete dataset before
        taking the writer lock; immutable bytes and identity are rechecked inside it.
        """
        wire = serialize_profile_request(request)
        profile = self.get_game_profile(request.profile_id, request.profile_revision)
        if profile is None or profile_sha256(profile) != request.profile_sha256:
            raise ValueError("missing or mismatched registered profile")
        saved = self.preflight_profile_dataset(
            request.dataset_sha256, profile, request.conditions, request.selector, request.staking
        )
        return self._create_bound_profile(
            request, profile, saved, wire, 1, quota_bytes, quota_explicit, disk_usage
        )

    def create_profile_audaz_experiment(
        self,
        request: ProfileAudazRequest,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> str:
        """Admit schema-3 audaz after profile/dataset and initial affordability checks."""
        wire = serialize_profile_audaz_request(request)
        profile = self.get_game_profile(request.profile_id, request.profile_revision)
        if profile is None or profile_sha256(profile) != request.profile_sha256:
            raise ValueError("missing or mismatched registered profile")
        saved = self.get_dataset(request.dataset_sha256)
        if saved is None:
            raise ValueError("dataset not found")
        try:
            embedded = GameProfile.model_validate(json.loads(saved.canonical_json)["profile"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("corrupt dataset profile snapshot") from exc
        if embedded != profile:
            raise ValueError("dataset profile differs from registered profile")
        run_profile_session(
            profile, request.conditions, request.selector, request.staking, _dataset_draws(saved)
        )
        return self._create_bound_profile(
            request, profile, saved, wire, 3, quota_bytes, quota_explicit, disk_usage
        )

    def create_profile_recovery_experiment(
        self,
        request: ProfileRecoveryRequest,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> str:
        """Admit schema-4 recovery only after full profile/dataset validation."""
        wire = serialize_profile_recovery_request(request)
        profile = self.get_game_profile(request.profile_id, request.profile_revision)
        if profile is None or profile_sha256(profile) != request.profile_sha256:
            raise ValueError("missing or mismatched registered profile")
        saved = self.get_dataset(request.dataset_sha256)
        if saved is None:
            raise ValueError("dataset not found")
        try:
            embedded = GameProfile.model_validate(json.loads(saved.canonical_json)["profile"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("corrupt dataset profile snapshot") from exc
        if embedded != profile:
            raise ValueError("dataset profile differs from registered profile")
        run_profile_session(
            profile, request.conditions, request.selector, request.staking, _dataset_draws(saved)
        )
        return self._create_bound_profile(
            request, profile, saved, wire, 4, quota_bytes, quota_explicit, disk_usage
        )

    def create_profile_cycling_experiment(
        self,
        request: ProfileCyclingRequest,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> str:
        """Store a private v2 preparation; the queue intentionally cannot run it."""
        wire = serialize_profile_cycling_request(request)
        profile = self.get_game_profile(request.profile_id, request.profile_revision)
        if profile is None or profile_sha256(profile) != request.profile_sha256:
            raise ValueError("missing or mismatched registered profile")
        saved = self.get_dataset(request.dataset_sha256)
        if saved is None:
            raise ValueError("dataset not found")
        try:
            embedded = GameProfile.model_validate(json.loads(saved.canonical_json)["profile"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("corrupt dataset profile snapshot") from exc
        if embedded != profile:
            raise ValueError("dataset profile differs from registered profile")
        # Pure validation against all authenticated rows, not a queue execution bridge.
        run_profile_session(
            profile, request.conditions, request.selector, request.staking, _dataset_draws(saved)
        )
        return self._create_bound_profile(
            request, profile, saved, wire, 2, quota_bytes, quota_explicit, disk_usage
        )

    def _create_bound_profile(
        self, request, profile, saved, wire, version, quota_bytes, quota_explicit, disk_usage
    ):
        identifier = uuid4().hex
        snapshot = profile.model_dump_json()
        created_at = _now_iso()
        experiment_fields = (
            identifier,
            ExperimentStatus.PENDING.value,
            wire,
            request.dataset_sha256,  # authenticated canonical dataset identity
            request.dataset_sha256,
            "",  # profile sessions do not consume legacy rankings
            "",
            f"profile-v{version}",
            created_at,
            "profile",
            version,
        )
        projected = sum(len(value.encode("utf-8")) for value in experiment_fields[:-1]) + 1
        projected += len(identifier.encode("utf-8")) + 8 + len("pending") + len("profile")
        projected += len(snapshot.encode("utf-8"))
        with _transaction(self.path) as db:
            registered = db.execute(
                "SELECT profile_json FROM game_profiles WHERE profile_id = ? AND revision = ?",
                (request.profile_id, request.profile_revision),
            ).fetchone()
            dataset = db.execute(
                "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
                "FROM datasets WHERE dataset_sha256 = ?",
                (request.dataset_sha256,),
            ).fetchone()
            if (
                registered is None
                or registered[0] != snapshot
                or dataset
                != (
                    saved.dataset_sha256,
                    saved.source_sha256,
                    saved.canonical_json.decode("utf-8"),
                    saved.raw_bytes,
                    saved.created_at,
                )
            ):
                raise ValueError("profile or dataset changed during admission")
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            before = _admission_logical_bytes(db)
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                disk_usage=disk_usage,
            ).require_capacity(projected)
            db.execute(
                "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
                "rankings_id, rankings_sha256, code_version, created_at, request_kind, "
                "request_schema_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                experiment_fields,
            )
            db.execute(
                "INSERT INTO runs (experiment_id, ordinal, configuration_id, status, "
                "result_json, result_kind) VALUES (?, 0, NULL, 'pending', NULL, 'profile')",
                (identifier,),
            )
            db.execute(
                "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
                (identifier, profile.profile_id, profile.revision, snapshot),
            )
            if _admission_logical_bytes(db) - before != projected:
                raise ValueError("profile quota projection differs from actual delta")
        return identifier

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
            profile = legacy_quiniela_80_profile()
            snapshot = profile.model_dump_json()
            stored = db.execute(
                "SELECT profile_json FROM game_profiles WHERE profile_id = ? AND revision = ?",
                (profile.profile_id, profile.revision),
            ).fetchone()
            if stored is None or stored[0] != snapshot:
                raise ValueError("missing or corrupt legacy game profile")
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
            projected += len("legacy") + 1  # request kind and schema version
            projected += sum(
                len(identifier.encode("utf-8"))
                + 8
                + len(status.encode("utf-8"))
                + len("legacy")  # result_kind
                + (len(link.encode("utf-8")) if link else 0)
                for _, _, link, status in run_fields
            )
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                disk_usage=disk_usage,
            ).require_capacity(projected + len(snapshot.encode("utf-8")))
            db.execute(
                "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
                "rankings_id, rankings_sha256, code_version, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                experiment_fields,
            )
            db.executemany(
                "INSERT INTO runs (experiment_id, ordinal, configuration_id, status, result_json) "
                "VALUES (?, ?, ?, ?, NULL)",
                run_fields,
            )
            db.execute(
                "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
                (identifier, profile.profile_id, profile.revision, snapshot),
            )
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
        include_completed_cycling: bool = False,
    ) -> tuple[int, list[SavedExperiment]]:
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        if name_contains is not None and not isinstance(name_contains, str):
            raise ValueError("name_contains must be a string")
        if status is not None and status not in {item.value for item in ExperimentStatus}:
            raise ValueError("invalid experiment status")
        if sort not in _SEARCH_SORTS or order not in _SEARCH_ORDERS:
            raise ValueError("invalid experiment sort")
        if type(include_completed_cycling) is not bool:
            raise ValueError("include_completed_cycling must be a bool")
        pattern = None if name_contains is None else f"%{_escape_like(name_contains.casefold())}%"
        filters = (pattern, pattern, status, status)
        # Use the identical visibility predicate for total and page IDs before OFFSET.
        # Explicit profile schema versions are public only through their validated projection.
        visible = (
            "request_kind = 'legacy' OR (request_kind = 'profile' AND request_schema_version = 1)"
        )
        if include_completed_cycling:
            visible += (
                " OR (request_kind = 'profile' AND request_schema_version IN (2, 3, 4) "
                "AND (SELECT count(*) FROM runs WHERE experiment_id = experiments.id) = 1 "
                "AND EXISTS (SELECT 1 FROM runs WHERE experiment_id = experiments.id "
                "AND ordinal = 0 AND result_kind = 'profile'))"
            )
        with connection(self.path) as db:
            db.create_function("unicode_casefold", 1, str.casefold, deterministic=True)
            db.execute("BEGIN")  # total, IDs and snapshots share one read view
            total = db.execute(
                f"SELECT count(*) FROM experiments WHERE ({visible}) AND "
                "(? IS NULL OR unicode_casefold(json_extract(request_json, '$.name')) "
                "LIKE ? ESCAPE '\\') AND (? IS NULL OR status = ?)",
                filters,
            ).fetchone()[0]
            ids = [
                row[0]
                for row in db.execute(
                    f"SELECT id FROM experiments WHERE ({visible}) AND "
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
            total = db.execute(
                "SELECT count(*) FROM experiments WHERE request_schema_version = 1"
            ).fetchone()[0]
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM experiments WHERE request_schema_version = 1 "
                    "ORDER BY rowid DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]
        return total, [
            saved for identifier in ids if (saved := self.get_experiment(identifier)) is not None
        ]

    def page_held_ids(self, offset: int, limit: int):
        with connection(self.path) as db:
            visible = (
                "status = 'held' AND (request_schema_version = 1 OR "
                "(request_kind = 'profile' AND request_schema_version IN (2, 3, 4)))"
            )
            total = db.execute(f"SELECT count(*) FROM experiments WHERE {visible}").fetchone()[0]
            ids = [
                row[0]
                for row in db.execute(
                    f"SELECT id FROM experiments WHERE {visible} ORDER BY rowid LIMIT ? OFFSET ?",
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
                "SELECT request_json, status, request_kind FROM experiments WHERE id = ?",
                (identifier,),
            ).fetchone()
            if row is None or row[1] != "running":
                raise ValueError("experiment not running or missing")
            if row[2] != "legacy":
                raise ValueError("profile completed results are not supported")
            request = ExperimentRequest.model_validate_json(row[0])
            if not 0 <= ordinal < len(request.strategies):
                raise ValueError("run ordinal missing")
            serialized = validate_result_payload(
                result, request.conditions.capital, request.strategies[ordinal].coverage
            )
            # Resolve persisted preference under the same writer lock as the result update.
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            status = measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                disk_usage=disk_usage,
            )
            status.require_capacity(len(serialized.encode("utf-8")) + 3)  # status delta + version
            changed = db.execute(
                "UPDATE runs SET status = 'completed', result_json = ?, result_schema_version = 1 "
                "WHERE experiment_id = ? AND ordinal = ? AND status = 'running' "
                "AND result_kind = 'legacy' AND result_schema_version IS NULL",
                (serialized, identifier, ordinal),
            ).rowcount
            if not changed:
                raise ValueError("run not running or already completed")

    def complete_profile_run(
        self,
        identifier: str,
        ordinal: int,
        result: ProfileSessionResult,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> None:
        """Replay one owned profile result from the complete authenticated artifact.

        This synchronous, potentially heavy operation must run off the API event
        loop when a queue is wired. Replay happens outside the write transaction;
        every binding and running status is checked again before quota and UPDATE.
        """
        self._complete_bound_profile_run(
            identifier, ordinal, result, 1, quota_bytes, quota_explicit, disk_usage
        )

    def complete_profile_audaz_run(
        self,
        identifier: str,
        ordinal: int,
        result: ProfileAudazResult,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> None:
        """Complete and independently replay one authenticated schema-3 job."""
        self._complete_bound_profile_run(
            identifier, ordinal, result, 3, quota_bytes, quota_explicit, disk_usage
        )

    def complete_profile_recovery_run(
        self,
        identifier: str,
        ordinal: int,
        result: ProfileRecoveryResult,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> None:
        """Complete and independently replay one authenticated schema-4 job."""
        self._complete_bound_profile_run(
            identifier, ordinal, result, 4, quota_bytes, quota_explicit, disk_usage
        )

    def complete_profile_cycling_run(
        self,
        identifier: str,
        ordinal: int,
        result: ProfileCyclingResult,
        *,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> None:
        """Complete a privately owned v2 run; this is not wired to the queue."""
        self._complete_bound_profile_run(
            identifier, ordinal, result, 2, quota_bytes, quota_explicit, disk_usage
        )

    def _complete_bound_profile_run(
        self, identifier, ordinal, result, version, quota_bytes, quota_explicit, disk_usage
    ):
        saved = self.get_experiment(identifier)
        if (
            saved is None
            or saved.request_kind != "profile"
            or saved.request_schema_version != version
            or saved.status is not ExperimentStatus.RUNNING
            or type(ordinal) is not int
            or ordinal != 0
            or len(saved.runs) != 1
            or saved.runs[0].ordinal != ordinal
            or saved.runs[0].status is not RunStatus.RUNNING
            or saved.runs[0].result_kind != "profile"
            or saved.runs[0].result is not None
        ):
            raise ValueError("profile run not owned, running or missing")
        request = saved.request
        if type(request) is not (
            ProfileExperimentRequest
            if version == 1
            else ProfileCyclingRequest
            if version == 2
            else ProfileAudazRequest
            if version == 3
            else ProfileRecoveryRequest
        ):
            raise ValueError("profile request binding mismatch")
        dataset = self.get_dataset(request.dataset_sha256)
        if dataset is None:
            raise ValueError("profile dataset missing")
        try:
            embedded = GameProfile.model_validate(json.loads(dataset.canonical_json)["profile"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("corrupt dataset profile snapshot") from exc
        if (
            embedded != saved.profile
            or saved.history_id != request.dataset_sha256
            or saved.history_sha256 != request.dataset_sha256
            or saved.rankings_id != ""
            or saved.rankings_sha256 != ""
            or saved.code_version != f"profile-v{version}"
        ):
            raise ValueError("profile dataset/request binding mismatch")
        # Never slice from start_draw: pre-start rows are part of the authenticated
        # all_rows/v1 artifact and the validator's row-budget admission.
        draws = _dataset_draws(dataset)
        if version == 1 and isinstance(request, ProfileExperimentRequest):
            admitted = validate_profile_result(result, request, saved.profile, draws)
            serialized = serialize_profile_result(admitted)
            request_wire = serialize_profile_request(request)
        elif version == 2 and isinstance(request, ProfileCyclingRequest):
            admitted = validate_profile_cycling_result(result, request, saved.profile, draws)
            serialized = serialize_profile_cycling_result(admitted)
            request_wire = serialize_profile_cycling_request(request)
        elif version == 3 and isinstance(request, ProfileAudazRequest):
            admitted = validate_profile_audaz_result(result, request, saved.profile, draws)
            serialized = serialize_profile_audaz_result(admitted)
            request_wire = serialize_profile_audaz_request(request)
        elif version == 4 and isinstance(request, ProfileRecoveryRequest):
            admitted = validate_profile_recovery_result(result, request, saved.profile, draws)
            serialized = serialize_profile_recovery_result(admitted)
            request_wire = serialize_profile_recovery_request(request)
        else:
            raise ValueError("profile request binding mismatch")
        snapshot = saved.profile.model_dump_json()
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT status, request_json, request_kind, history_id, history_sha256, "
                "rankings_id, rankings_sha256, code_version, request_schema_version "
                "FROM experiments WHERE id = ?",
                (identifier,),
            ).fetchone()
            run = db.execute(
                "SELECT ordinal, configuration_id, status, result_json, result_kind, "
                "result_schema_version FROM runs WHERE experiment_id = ?",
                (identifier,),
            ).fetchall()
            profile_row = db.execute(
                "SELECT profile_id, revision, profile_json FROM experiment_profiles "
                "WHERE experiment_id = ?",
                (identifier,),
            ).fetchone()
            registered = db.execute(
                "SELECT profile_json FROM game_profiles WHERE profile_id = ? AND revision = ?",
                (request.profile_id, request.profile_revision),
            ).fetchone()
            artifact = db.execute(
                "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
                "FROM datasets WHERE dataset_sha256 = ?",
                (request.dataset_sha256,),
            ).fetchone()
            if (
                row
                != (
                    "running",
                    request_wire,
                    "profile",
                    saved.history_id,
                    request.dataset_sha256,
                    saved.rankings_id,
                    saved.rankings_sha256,
                    saved.code_version,
                    version,
                )
                or run != [(0, None, "running", None, "profile", None)]
                or profile_row != (request.profile_id, request.profile_revision, snapshot)
                or registered != (snapshot,)
                or artifact
                != (
                    dataset.dataset_sha256,
                    dataset.source_sha256,
                    dataset.canonical_json.decode("utf-8"),
                    dataset.raw_bytes,
                    dataset.created_at,
                )
            ):
                raise ValueError("profile run or immutable bindings changed during replay")
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            before = _admission_logical_bytes(db)
            projected = len(serialized.encode("utf-8")) + len("completed") - len("running") + 1
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                disk_usage=disk_usage,
            ).require_capacity(projected)
            changed = db.execute(
                "UPDATE runs SET status = 'completed', result_json = ?, result_schema_version = ? "
                "WHERE experiment_id = ? AND ordinal = 0 AND status = 'running' "
                "AND result_kind = 'profile' AND result_schema_version IS NULL "
                "AND result_json IS NULL",
                (serialized, version, identifier),
            ).rowcount
            if changed != 1:
                raise ValueError("profile run no longer running")
            if _admission_logical_bytes(db) - before != projected:
                raise ValueError("profile result quota projection differs from actual delta")

    def fail_run(self, identifier: str, ordinal: int):
        """Record one local failure atomically without discarding independent runs."""
        with _transaction(self.path) as db:
            changed = db.execute(
                "UPDATE runs SET status = 'failed' WHERE experiment_id = ? AND ordinal = ? "
                "AND status = 'running' AND result_json IS NULL AND EXISTS "
                "(SELECT 1 FROM experiments WHERE id = ? AND status = 'running')",
                (identifier, ordinal, identifier),
            ).rowcount
            if changed != 1:
                raise ValueError("run missing, not running or already has a result")

    def fail_experiment_after_runs(self, identifier: str):
        """Finish a mixed batch only after every run is terminal and one has failed."""
        with _transaction(self.path) as db:
            changed = db.execute(
                "UPDATE experiments SET status = 'failed' WHERE id = ? AND status = 'running' "
                "AND EXISTS (SELECT 1 FROM runs WHERE experiment_id = ? AND status = 'failed') "
                "AND NOT EXISTS (SELECT 1 FROM runs WHERE experiment_id = ? "
                "AND status NOT IN ('completed', 'failed'))",
                (identifier, identifier, identifier),
            ).rowcount
            if changed != 1:
                raise ValueError("experiment missing, not running or has nonterminal runs")

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
