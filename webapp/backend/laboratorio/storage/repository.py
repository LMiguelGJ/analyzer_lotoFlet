"""Small transactional repository for saved strategies and immutable run snapshots."""

import hashlib
import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, replace
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
    make_game,
)
from laboratorio.domain.execution_policy import EDITABLE_FIELDS, ExecutionPolicy
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
from laboratorio.domain.profile_request_v5 import (
    ProfileBatchRequestV5,
    load_profile_batch_v5,
    serialize_profile_batch_v5,
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
from laboratorio.domain.profile_result_v5 import (
    load_profile_batch_result_v5,
    serialize_profile_batch_result_v5,
    validate_profile_batch_result_v5,
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
from laboratorio.domain.profile_session_v5 import ProfileBatchResultV5
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.domain.session import Bet, SessionResult
from laboratorio.domain.strategy_library import (
    PRESETS,
    compatibility_projection,
    definition_snapshot,
    registered_preset_definition,
    strategy_payload,
)
from laboratorio.importing.datasets import Promotion, SavedDataset, checked_dataset
from laboratorio.importing.history import history_options, parse_history
from laboratorio.importing.records import (
    ClockDeclaration,
    ColumnMapping,
    SourceMetadata,
    canonical_bytes,
    parse_records,
)
from laboratorio.settings import DEFAULT_QUOTA_BYTES
from laboratorio.storage.database import connection, require_database
from laboratorio.storage.quota import PendingRunsExceeded, measure, validate_quota_bytes

SQLITE_MAX = 2**63 - 1


class QuotaReadOnly(RuntimeError):
    """An explicit environment quota forbids changing the persisted preference."""


class QuotaBelowUsage(RuntimeError):
    """A new preference cannot be less than existing admitted logical artifacts."""


class IdempotencyConflict(ValueError):
    """A client request identity was reused for different canonical batch content."""


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
        | ProfileBatchResultV5
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
        | ProfileBatchRequestV5
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
    batch_admission: dict | None = None


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _profile_conditions_dict(conditions):
    return {
        "schema_version": conditions.schema_version,
        "start_draw": conditions.start_draw,
        "capital": conditions.capital,
        "goal": conditions.goal,
        "settlement": conditions.settlement.value,
        "max_elapsed_draws": conditions.max_elapsed_draws,
        "max_bet_draws": conditions.max_bet_draws,
        "end_minute": conditions.end_minute,
        "duration_minutes": conditions.duration_minutes,
    }


def _batch_identity_hash(profile_id, profile_revision, profile_hash, dataset_hash, refs, requested):
    payload = {
        "profile_id": profile_id,
        "profile_revision": profile_revision,
        "profile_sha256": profile_hash,
        "dataset_sha256": dataset_hash,
        "strategy_refs": refs,
        "requested_constraints": requested,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def _load_dataset_in_transaction(db, dataset_sha256: str):
    row = db.execute(
        "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
        "FROM datasets WHERE dataset_sha256 = ?",
        (dataset_sha256,),
    ).fetchone()
    return None if row is None else checked_dataset(row)


def _load_experiment(db, identifier: str, dataset_loader=None) -> SavedExperiment | None:
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
    elif request_kind == "profile" and type(request_version) is int and request_version == 5:
        request = load_profile_batch_v5(row[2])
    else:
        raise ValueError("unsupported stored request kind/version")
    dataset = None
    if request_kind == "profile":
        if not isinstance(
            request,
            (
                ProfileExperimentRequest,
                ProfileCyclingRequest,
                ProfileAudazRequest,
                ProfileRecoveryRequest,
                ProfileBatchRequestV5,
            ),
        ):
            raise ValueError("profile request binding mismatch")
        if (
            request.profile_id != profile.profile_id
            or request.profile_revision != profile.revision
            or request.profile_sha256 != profile_sha256(profile)
        ):
            raise ValueError("profile request differs from experiment profile snapshot")
        if request_version == 5:
            dataset = dataset_loader(request.dataset_sha256) if dataset_loader is not None else None
            if dataset is None:
                raise ValueError("missing verified profile batch dataset")
            try:
                dataset_profile = GameProfile.model_validate(
                    json.loads(dataset.canonical_json)["profile"]
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("corrupt profile batch dataset profile") from exc
            if dataset_profile != profile:
                raise ValueError("profile dataset differs from experiment profile snapshot")
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
        elif result_kind == "profile" and result_version == 5:
            result = load_profile_batch_result_v5(value)
        elif result_kind == "profile" and result_version == 1:
            result = load_profile_result(value)
        elif result_kind == "legacy" and result_version == 1:
            result = _read_result(value)
        else:
            raise ValueError("unsupported stored result kind/version")
        saved_runs.append(
            SavedRun(ordinal, link, RunStatus(status), result, result_kind, result_version)
        )
    admission = None
    if request_kind == "profile" and request_version == 5:
        metadata = db.execute(
            "SELECT client_request_id, request_sha256, strategy_refs_json, "
            "requested_constraints_json, effective_constraints_json, policy_revision, "
            "policy_json, source_identity_json FROM profile_batch_admissions "
            "WHERE experiment_id = ?",
            (identifier,),
        ).fetchone()
        if not isinstance(request, ProfileBatchRequestV5):
            raise ValueError("stored v5 request has the wrong codec type")
        if metadata is None or len(saved_runs) != len(request.strategies):
            raise ValueError("missing profile batch admission snapshot or runs")
        for index, saved_run in enumerate(saved_runs):
            if saved_run.ordinal != index or (
                saved_run.result is not None
                and (
                    not isinstance(saved_run.result, ProfileBatchResultV5)
                    or len(saved_run.result.results) != 1
                    or saved_run.result.results[0].ordinal != 0
                    or saved_run.result.results[0].definition != request.strategies[index]
                    or saved_run.result.profile_id != request.profile_id
                    or saved_run.result.profile_revision != request.profile_revision
                    or saved_run.result.profile_sha256 != request.profile_sha256
                    or saved_run.result.dataset_sha256 != request.dataset_sha256
                )
            ):
                raise ValueError("profile batch run ordinal/result association mismatch")
        try:
            admission = {
                "client_request_id": metadata[0],
                "request_sha256": metadata[1],
                "strategy_refs": json.loads(metadata[2]),
                "requested_constraints": json.loads(metadata[3]),
                "effective_constraints": json.loads(metadata[4]),
                "policy_revision": metadata[5],
                "policy": json.loads(metadata[6]),
                "source_identity": json.loads(metadata[7]),
            }
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("corrupt profile batch admission snapshot") from exc
        if (
            serialize_profile_batch_v5(request) != row[2]
            or type(admission["strategy_refs"]) is not list
            or len(admission["strategy_refs"]) != len(request.strategies)
            or _json(admission["strategy_refs"]) != metadata[2]
            or _json(admission["requested_constraints"]) != metadata[3]
            or _json(admission["effective_constraints"]) != metadata[4]
            or _json(admission["policy"]) != metadata[6]
            or _json(admission["source_identity"]) != metadata[7]
            or type(admission["policy_revision"]) is not int
            or _batch_identity_hash(
                request.profile_id,
                request.profile_revision,
                request.profile_sha256,
                request.dataset_sha256,
                admission["strategy_refs"],
                admission["requested_constraints"],
            )
            != admission["request_sha256"]
        ):
            raise ValueError("profile batch request or identity snapshot hash mismatch")
        saved_policy = ExecutionPolicy.from_values(admission["policy"])
        expected_effective = {
            **_profile_conditions_dict(request.conditions),
            "max_draws": request.max_draws,
            "policy_revision": admission["policy_revision"],
            "policy": saved_policy.as_dict(),
        }
        requested = admission["requested_constraints"]
        if type(requested) is not dict or requested.keys() != (
            set(_profile_conditions_dict(request.conditions)) | {"max_draws"}
        ):
            raise ValueError("corrupt requested batch constraints")
        if (
            type(requested["max_draws"]) is not int
            or not 1 <= requested["max_draws"] <= 10_000
            or any(
                value is not None and (type(value) is not int or not 1 <= value <= 10_000)
                for value in (
                    requested["max_bet_draws"],
                    requested["max_elapsed_draws"],
                )
            )
        ):
            raise ValueError("invalid requested batch limit snapshot")
        requested_shared = _profile_conditions_dict(request.conditions)
        for field in (
            "schema_version",
            "start_draw",
            "capital",
            "goal",
            "settlement",
            "end_minute",
            "duration_minutes",
        ):
            if requested[field] != requested_shared[field]:
                raise ValueError("shared batch condition changed after admission")
        source = admission["source_identity"]
        if type(source) is not dict or source.keys() != {
            "dataset_sha256",
            "source_sha256",
            "canonical_sha256",
            "row_count",
            "profile_id",
            "profile_revision",
            "profile_sha256",
            "archive_bound",
            "archive_history_sha256",
            "archive_rank_row_ids",
        }:
            raise ValueError("corrupt profile batch source identity shape")
        max_bet_draws = request.conditions.max_bet_draws
        max_elapsed_draws = request.conditions.max_elapsed_draws
        if (
            admission["effective_constraints"] != expected_effective
            or requested["max_draws"] < request.max_draws
            or source.get("dataset_sha256") != request.dataset_sha256
            or source.get("profile_id") != request.profile_id
            or source.get("profile_revision") != request.profile_revision
            or source.get("profile_sha256") != request.profile_sha256
            or type(source.get("archive_bound")) is not bool
            or type(source.get("row_count")) is not int
            or source["row_count"] < 1
            or any(
                type(source[field]) is not str
                or len(source[field]) != 64
                or any(char not in "0123456789abcdef" for char in source[field])
                for field in ("source_sha256", "canonical_sha256")
            )
            or (
                source["archive_bound"]
                and (
                    type(source["archive_history_sha256"]) is not str
                    or len(source["archive_history_sha256"]) != 64
                    or type(source["archive_rank_row_ids"]) is not list
                    or any(
                        type(row_id) is not int or row_id < 0
                        for row_id in source["archive_rank_row_ids"]
                    )
                )
            )
            or (
                not source["archive_bound"]
                and (
                    source["archive_history_sha256"] is not None
                    or source["archive_rank_row_ids"] is not None
                )
            )
            or max_bet_draws is None
            or max_elapsed_draws is None
        ):
            raise ValueError("corrupt profile batch source or policy snapshot")
        if dataset is None:
            raise ValueError("missing verified profile batch dataset")
        try:
            dataset_profile = GameProfile.model_validate(
                json.loads(dataset.canonical_json)["profile"]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("corrupt profile batch dataset profile") from exc
        canonical_sha256 = hashlib.sha256(dataset.canonical_json).hexdigest()
        row_count = len(dataset.preview.records)
        if (
            dataset.dataset_sha256 != request.dataset_sha256
            or dataset.source_sha256 != source["source_sha256"]
            or canonical_sha256 != source["canonical_sha256"]
            or row_count != source["row_count"]
            or dataset_profile != profile
            or dataset_profile.profile_id != source["profile_id"]
            or dataset_profile.revision != source["profile_revision"]
            or profile_sha256(dataset_profile) != source["profile_sha256"]
        ):
            raise ValueError("profile batch source identity differs from verified dataset")
        if (
            max_bet_draws > saved_policy.max_bet_draws
            or max_elapsed_draws > saved_policy.max_elapsed_draws
            or request.max_draws > max_elapsed_draws
            or saved_policy.max_strategies_per_batch < len(request.strategies)
            or (
                requested["max_bet_draws"] is not None
                and requested["max_bet_draws"] < max_bet_draws
            )
            or (
                requested["max_elapsed_draws"] is not None
                and requested["max_elapsed_draws"] < max_elapsed_draws
            )
        ):
            raise ValueError("corrupt profile batch effective constraints")
        for index, (ref, definition) in enumerate(
            zip(admission["strategy_refs"], request.strategies, strict=True)
        ):
            if type(ref) is not dict or ref.keys() != {"id", "revision", "definition_sha256"}:
                raise ValueError("corrupt profile batch strategy reference")
            strategy_row = db.execute(
                "SELECT s.id, s.name, s.created_at, s.protected, s.preset_explanation, "
                "s.latest_revision, r.revision, r.definition_version, r.definition_sha256, "
                "r.definition_json, r.created_at FROM strategies AS s "
                "JOIN strategy_revisions AS r ON r.strategy_id = s.id "
                "WHERE s.id = ? AND r.revision = ?",
                (ref["id"], ref["revision"]),
            ).fetchone()
            snapshot = Repository._strategy_snapshot(strategy_row)
            if (
                snapshot is None
                or snapshot["definition_sha256"] != ref["definition_sha256"]
                or snapshot["definition"] != definition
                or type(ref["revision"]) is not int
            ):
                raise ValueError(f"profile batch strategy reference mismatch at ordinal {index}")
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
        admission,
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

    @staticmethod
    def _pending_run_count(db) -> int:
        return db.execute(
            "SELECT count(*) FROM runs WHERE status IN ('pending', 'held', 'running')"
        ).fetchone()[0]

    @staticmethod
    def _policy_row(db):
        row = db.execute(
            "SELECT revision, max_strategies_per_batch, worker_count, max_pending_runs, "
            "max_bet_draws, max_elapsed_draws, run_timeout_seconds "
            "FROM execution_policy WHERE id = 1"
        ).fetchone()
        if row is None:
            raise ValueError("execution policy singleton is missing")
        return row[0], ExecutionPolicy.from_values(
            dict(
                zip(
                    (
                        "max_strategies_per_batch",
                        "worker_count",
                        "max_pending_runs",
                        "max_bet_draws",
                        "max_elapsed_draws",
                        "run_timeout_seconds",
                    ),
                    row[1:],
                    strict=True,
                )
            )
        )

    @classmethod
    def _check_pending_capacity(cls, db, incoming_runs: int) -> None:
        if type(incoming_runs) is not int or incoming_runs < 1:
            raise ValueError("incoming run count must be positive")
        _, policy = cls._policy_row(db)
        if cls._pending_run_count(db) + incoming_runs > policy.max_pending_runs:
            raise PendingRunsExceeded(
                f"pending run capacity ({policy.max_pending_runs}) would be exceeded"
            )

    def execution_policy(self) -> tuple[int, ExecutionPolicy]:
        with connection(self.path) as db:
            return self._policy_row(db)

    def update_execution_policy(self, changes: dict, *, expected_revision: int | None = None):
        if type(changes) is not dict or not changes or set(changes) - EDITABLE_FIELDS:
            raise ValueError("only bounded editable execution policy fields may be changed")
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision < 1
        ):
            raise ValueError("expected execution policy revision must be positive")
        with _transaction(self.path) as db:
            revision, current = self._policy_row(db)
            if expected_revision is not None and expected_revision != revision:
                raise ValueError("execution policy revision conflict")
            updated = ExecutionPolicy.from_values({**current.as_dict(), **changes})
            db.execute(
                "UPDATE execution_policy SET revision = ?, max_strategies_per_batch = ?, "
                "worker_count = ?, max_pending_runs = ?, max_bet_draws = ?, "
                "max_elapsed_draws = ?, run_timeout_seconds = ? WHERE id = 1 AND revision = ?",
                (
                    revision + 1,
                    updated.max_strategies_per_batch,
                    updated.worker_count,
                    updated.max_pending_runs,
                    updated.max_bet_draws,
                    updated.max_elapsed_draws,
                    updated.run_timeout_seconds,
                    revision,
                ),
            )
        return revision + 1, updated

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
        format: Literal["csv", "json", "history_json"],
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
        if format == "history_json":
            preview = parse_history(data, profile)
            try:
                document = json.loads(data)
                history = history_options(document, profile)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError("dataset source is not promotable") from exc
            if (history["mapping"], history["source"], history["clock"]) != (
                mapping,
                source,
                clock,
            ):
                raise ValueError("history context changed")
        else:
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
                strategy_artifact_bytes=_strategy_artifact_bytes(db),
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

    def get_game_settings(self):
        """Stored game rules as a validated Game, or None when never edited."""
        with connection(self.path) as db:
            row = db.execute(
                "SELECT name, numbers, positions, prizes, allows_repeats, minimum_stake "
                "FROM settings_game WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        name, numbers, positions, prizes, repeats, stake = row
        return make_game(
            name, numbers, positions, [int(p) for p in prizes.split(",")], bool(repeats), stake
        )

    def save_game_settings(self, game) -> None:
        """Persist the rules; existing experiments keep the rules they were created with."""
        with _transaction(self.path) as db:
            db.execute(
                "INSERT INTO settings_game "
                "(id, name, numbers, positions, prizes, allows_repeats, minimum_stake) "
                "VALUES (1, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "name = excluded.name, numbers = excluded.numbers, "
                "positions = excluded.positions, prizes = excluded.prizes, "
                "allows_repeats = excluded.allows_repeats, "
                "minimum_stake = excluded.minimum_stake",
                (
                    game.name,
                    game.numbers,
                    game.positions,
                    ",".join(str(p) for p in game.prizes),
                    int(game.allows_repeats),
                    game.minimum_stake,
                ),
            )

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
                    strategy_artifact_bytes=_strategy_artifact_bytes(db),
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

    @staticmethod
    def _strategy_snapshot(row):
        if row is None:
            return None
        (
            identifier,
            name,
            created_at,
            protected,
            explanation,
            latest_revision,
            revision,
            version,
            digest,
            serialized,
            revision_created_at,
        ) = row
        try:
            definition = strategy_payload(json.loads(serialized))
            canonical, actual_digest = definition_snapshot(definition)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("corrupt stored strategy definition") from exc
        if (
            canonical != serialized
            or actual_digest != digest
            or definition.definition_version != version
            or (revision == latest_revision and definition.name != name)
            or revision > latest_revision
        ):
            raise ValueError("corrupt stored strategy revision")
        preset_ids = {preset_id for preset_id, _, _ in PRESETS}
        if protected or identifier in preset_ids:
            if not protected:
                raise ValueError("corrupt stored protected preset identity")
            try:
                expected_explanation, expected_definition = registered_preset_definition(identifier)
            except ValueError as exc:
                raise ValueError("corrupt stored protected preset identity") from exc
            expected_json, expected_digest = definition_snapshot(expected_definition)
            if (
                identifier not in preset_ids
                or latest_revision != 1
                or revision != 1
                or version != expected_definition.definition_version
                or name != expected_definition.name
                or explanation != expected_explanation
                or serialized != expected_json
                or canonical != expected_json
                or digest != expected_digest
                or actual_digest != expected_digest
                or created_at != revision_created_at
            ):
                raise ValueError("corrupt stored protected preset snapshot")
        return {
            "id": identifier,
            "name": definition.name,
            "created_at": created_at,
            "protected": bool(protected),
            "preset_explanation": explanation,
            "latest_revision": latest_revision,
            "revision": revision,
            "definition_version": version,
            "definition_sha256": digest,
            "definition_json": serialized,
            "revision_created_at": revision_created_at,
            "definition": definition,
            **compatibility_projection(
                definition,
                reference_preset_id=identifier if protected else None,
            ),
        }

    def _strategy_row(self, db, identifier, revision=None):
        query = (
            "SELECT s.id, s.name, s.created_at, s.protected, s.preset_explanation, "
            "s.latest_revision, r.revision, r.definition_version, r.definition_sha256, "
            "r.definition_json, r.created_at FROM strategies AS s "
            "JOIN strategy_revisions AS r ON r.strategy_id = s.id WHERE s.id = ? "
        )
        if revision is None:
            row = db.execute(query + "AND r.revision = s.latest_revision", (identifier,)).fetchone()
            if (
                row is None
                and db.execute("SELECT 1 FROM strategies WHERE id = ?", (identifier,)).fetchone()
            ):
                raise ValueError("corrupt stored strategy head")
        else:
            row = db.execute(query + "AND r.revision = ?", (identifier, revision)).fetchone()
            head = db.execute(
                "SELECT latest_revision FROM strategies WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None and head is not None and revision <= head[0]:
                raise ValueError("corrupt stored strategy revision history")
        return row

    def get_strategy(self, identifier: str):
        with connection(self.path) as db:
            row = self._strategy_row(db, identifier)
        return self._strategy_snapshot(row)

    def get_strategy_revision(self, identifier: str, revision: int):
        if type(revision) is not int or revision < 1:
            raise ValueError("revision out of range")
        with connection(self.path) as db:
            row = self._strategy_row(db, identifier, revision)
        return self._strategy_snapshot(row)

    def page_strategies(self, offset: int, limit: int):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        with connection(self.path) as db:
            db.execute("BEGIN")
            total = db.execute("SELECT count(*) FROM strategies").fetchone()[0]
            identifiers = db.execute(
                "SELECT id FROM strategies ORDER BY created_at, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            rows = [self._strategy_row(db, identifier) for (identifier,) in identifiers]
        return total, [self._strategy_snapshot(row) for row in rows]

    def _admit_strategy_bytes(self, db, projected, quota_bytes, quota_explicit, disk_usage):
        effective = _effective_quota(db, quota_bytes, quota_explicit)
        measure(
            self.path,
            effective.effective_bytes,
            _logical_experiment_bytes(db),
            profile_artifact_bytes=_profile_artifact_bytes(db),
            dataset_artifact_bytes=_dataset_artifact_bytes(db),
            strategy_artifact_bytes=_strategy_artifact_bytes(db),
            disk_usage=disk_usage,
        ).require_capacity(projected)

    def _insert_strategy(self, db, identifier, definition, explanation, protected, created_at):
        serialized, digest = definition_snapshot(definition)
        db.execute(
            "INSERT INTO strategies VALUES (?, ?, ?, ?, ?, 1)",
            (identifier, definition.name, created_at, int(protected), explanation),
        )
        db.execute(
            "INSERT INTO strategy_revisions VALUES (?, 1, ?, ?, ?, ?)",
            (identifier, definition.definition_version, digest, serialized, created_at),
        )

    def create_strategy(
        self,
        definition: StrategyDefinition,
        *,
        preset_explanation="",
        quota_bytes=None,
        quota_explicit=None,
        disk_usage=shutil.disk_usage,
    ):
        if type(definition) is not StrategyDefinition:
            raise ValueError("a closed StrategyDefinition is required")
        definition.__post_init__()
        if type(preset_explanation) is not str or len(preset_explanation.encode("utf-8")) > 4000:
            raise ValueError("preset explanation exceeds its bounded text limit")
        identifier = uuid4().hex
        created_at = _now_iso()
        serialized, digest = definition_snapshot(definition)
        projected = (
            len(identifier.encode("utf-8"))
            + len(definition.name.encode("utf-8"))
            + len(created_at.encode("utf-8")) * 2
            + len(preset_explanation.encode("utf-8"))
            + 9
            + len(identifier.encode("utf-8"))
            + 16
            + len(digest)
            + len(serialized.encode("utf-8"))
        )
        with _transaction(self.path) as db:
            self._admit_strategy_bytes(db, projected, quota_bytes, quota_explicit, disk_usage)
            self._insert_strategy(db, identifier, definition, preset_explanation, False, created_at)
        return self.get_strategy(identifier)

    def append_strategy_revision(
        self,
        identifier,
        expected_latest_revision,
        definition,
        *,
        quota_bytes=None,
        quota_explicit=None,
        disk_usage=shutil.disk_usage,
    ):
        if type(expected_latest_revision) is not int or expected_latest_revision < 1:
            raise ValueError("expected_latest_revision must be a positive integer")
        if type(definition) is not StrategyDefinition:
            raise ValueError("a closed StrategyDefinition is required")
        definition.__post_init__()
        serialized, digest = definition_snapshot(definition)
        created_at = _now_iso()
        with _transaction(self.path) as db:
            row = db.execute(
                "SELECT latest_revision, protected, name FROM strategies WHERE id = ?",
                (identifier,),
            ).fetchone()
            if row is None:
                raise KeyError("strategy not found")
            latest, protected, old_name = row
            if protected:
                raise ValueError("protected strategy cannot be revised; create a copy")
            if latest != expected_latest_revision:
                raise ValueError("strategy revision conflict")
            revision = latest + 1
            projected = (
                len(identifier.encode("utf-8"))
                + 16
                + len(digest)
                + len(serialized.encode("utf-8"))
                + len(created_at.encode("utf-8"))
                + len(definition.name.encode("utf-8"))
                - len(old_name.encode("utf-8"))
            )
            self._admit_strategy_bytes(db, projected, quota_bytes, quota_explicit, disk_usage)
            db.execute(
                "INSERT INTO strategy_revisions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    identifier,
                    revision,
                    definition.definition_version,
                    digest,
                    serialized,
                    created_at,
                ),
            )
            db.execute(
                "UPDATE strategies SET latest_revision = ?, name = ? WHERE id = ? "
                "AND latest_revision = ?",
                (revision, definition.name, identifier, latest),
            )
        return self.get_strategy_revision(identifier, revision)

    def seed_strategy_presets(
        self, presets, *, quota_bytes=None, quota_explicit=None, disk_usage=shutil.disk_usage
    ):
        seeded = []
        for identifier, explanation, constructor in presets:
            definition = constructor()
            expected, digest = definition_snapshot(definition)
            with _transaction(self.path) as db:
                existing = self._strategy_row(db, identifier)
                if existing is not None:
                    saved = self._strategy_snapshot(existing)
                    if saved is None:
                        raise ValueError("corrupt stored protected preset")
                    if (
                        not saved["protected"]
                        or saved["preset_explanation"] != explanation
                        or saved["definition_json"] != expected
                        or saved["definition_sha256"] != digest
                    ):
                        raise ValueError("protected preset identity already has different content")
                else:
                    created_at = _now_iso()
                    projected = (
                        len(identifier.encode("utf-8"))
                        + len(definition.name.encode("utf-8"))
                        + len(created_at.encode("utf-8")) * 2
                        + len(explanation.encode("utf-8"))
                        + 9
                        + len(identifier.encode("utf-8"))
                        + 16
                        + len(digest)
                        + len(expected.encode("utf-8"))
                    )
                    self._admit_strategy_bytes(
                        db, projected, quota_bytes, quota_explicit, disk_usage
                    )
                    self._insert_strategy(db, identifier, definition, explanation, True, created_at)
            seeded.append(self.get_strategy(identifier))
        return seeded

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

    def get_profile_batch_request_id(self, client_request_id: str) -> str | None:
        """Read a batch ID by caller identity and verify its stored experiment snapshot."""
        if (
            type(client_request_id) is not str
            or not 1 <= len(client_request_id.encode("utf-8")) <= 128
        ):
            raise ValueError("invalid client request identity")
        with connection(self.path) as db:
            row = db.execute(
                "SELECT experiment_id FROM profile_batch_admissions WHERE client_request_id = ?",
                (client_request_id,),
            ).fetchone()
        if row is None:
            return None
        if self.get_experiment(row[0]) is None:
            raise ValueError("profile batch identity points to a missing experiment")
        return row[0]

    def find_profile_batch_request(self, client_request_id: str, request_digest: str) -> str | None:
        if (
            type(client_request_id) is not str
            or not 1 <= len(client_request_id.encode("utf-8")) <= 128
            or type(request_digest) is not str
            or len(request_digest) != 64
            or any(char not in "0123456789abcdef" for char in request_digest)
        ):
            raise ValueError("invalid client request identity")
        with connection(self.path) as db:
            row = db.execute(
                "SELECT experiment_id, request_sha256 FROM profile_batch_admissions "
                "WHERE client_request_id = ?",
                (client_request_id,),
            ).fetchone()
        if row is None:
            return None
        if row[1] != request_digest:
            raise IdempotencyConflict("client_request_id was already used for another request")
        if self.get_experiment(row[0]) is None:
            raise ValueError("idempotent profile batch points to a missing experiment")
        return row[0]

    def create_profile_batch_experiment(
        self,
        request: ProfileBatchRequestV5,
        *,
        strategy_refs: tuple[dict, ...],
        client_request_id: str,
        requested_constraints: dict,
        effective_constraints: dict,
        policy_revision: int,
        policy: ExecutionPolicy,
        source_identity: dict,
        dataset_snapshot,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> str:
        """Atomically persist an exact v5 request, ordered runs, policy and idempotency key."""
        if type(request) is not ProfileBatchRequestV5:
            raise ValueError("request must be a closed ProfileBatchRequestV5")
        request.__post_init__()
        wire = serialize_profile_batch_v5(request)
        request_digest = _batch_identity_hash(
            request.profile_id,
            request.profile_revision,
            request.profile_sha256,
            request.dataset_sha256,
            strategy_refs,
            requested_constraints,
        )
        if (
            type(client_request_id) is not str
            or not 1 <= len(client_request_id.encode("utf-8")) <= 128
            or type(strategy_refs) is not tuple
            or len(strategy_refs) != len(request.strategies)
            or type(policy_revision) is not int
            or policy_revision < 1
            or type(policy) is not ExecutionPolicy
        ):
            raise ValueError("invalid profile batch admission metadata")
        refs_wire = _json(strategy_refs)
        requested_wire = _json(requested_constraints)
        effective_wire = _json(effective_constraints)
        policy_wire = _json(policy.as_dict())
        source_wire = _json(source_identity)
        snapshot = self.get_game_profile(request.profile_id, request.profile_revision)
        if snapshot is None or profile_sha256(snapshot) != request.profile_sha256:
            raise ValueError("missing or mismatched registered profile")
        if (
            type(dataset_snapshot) is not SavedDataset
            or dataset_snapshot.dataset_sha256 != request.dataset_sha256
            or hashlib.sha256(dataset_snapshot.canonical_json).hexdigest()
            != dataset_snapshot.dataset_sha256
            or hashlib.sha256(dataset_snapshot.raw_bytes).hexdigest()
            != dataset_snapshot.source_sha256
        ):
            raise ValueError("batch dataset snapshot is not a checked saved artifact")
        dataset = dataset_snapshot
        try:
            embedded = GameProfile.model_validate(json.loads(dataset.canonical_json)["profile"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("corrupt dataset profile snapshot") from exc
        if embedded != snapshot:
            raise ValueError("dataset profile differs from registered profile")

        identifier = uuid4().hex
        created_at = _now_iso()
        profile_json = snapshot.model_dump_json()
        with _transaction(self.path) as db:
            duplicate = db.execute(
                "SELECT experiment_id, request_sha256 FROM profile_batch_admissions "
                "WHERE client_request_id = ?",
                (client_request_id,),
            ).fetchone()
            if duplicate is not None:
                if duplicate[1] != request_digest:
                    raise IdempotencyConflict(
                        "client_request_id was already used for another request"
                    )
                return duplicate[0]
            current_revision, current_policy = self._policy_row(db)
            if current_revision != policy_revision or current_policy != policy:
                raise ValueError(
                    "execution policy changed during admission; retry with current policy"
                )
            self._check_pending_capacity(db, len(request.strategies))
            registered = db.execute(
                "SELECT profile_json FROM game_profiles WHERE profile_id = ? AND revision = ?",
                (request.profile_id, request.profile_revision),
            ).fetchone()
            dataset_row = db.execute(
                "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, created_at "
                "FROM datasets WHERE dataset_sha256 = ?",
                (request.dataset_sha256,),
            ).fetchone()
            if registered != (profile_json,) or dataset_row != (
                dataset.dataset_sha256,
                dataset.source_sha256,
                dataset.canonical_json.decode("utf-8"),
                dataset.raw_bytes,
                dataset.created_at,
            ):
                raise ValueError("profile or dataset changed during batch admission")
            for definition, ref in zip(request.strategies, strategy_refs, strict=True):
                if type(ref) is not dict or ref.keys() != {"id", "revision", "definition_sha256"}:
                    raise ValueError("strategy reference must be exact id/revision/hash")
                row = self._strategy_row(db, ref["id"], ref["revision"])
                saved = self._strategy_snapshot(row)
                if (
                    saved is None
                    or saved["definition_sha256"] != ref["definition_sha256"]
                    or saved["definition"] != definition
                ):
                    raise ValueError("strategy reference does not match immutable revision")
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            projected = sum(
                len(value.encode("utf-8"))
                for value in (
                    identifier,
                    wire,
                    request.dataset_sha256,
                    dataset.source_sha256,
                    "profile-v5",
                    created_at,
                    "profile",
                    refs_wire,
                    requested_wire,
                    effective_wire,
                    policy_wire,
                    source_wire,
                    client_request_id,
                    request_digest,
                )
            ) + len(profile_json.encode("utf-8"))
            projected += len(ExperimentStatus.PENDING.value) + 1
            admission_copy_bytes = len(identifier.encode("utf-8")) + 8
            projected += admission_copy_bytes  # experiment_id plus policy_revision
            projected += len(request.strategies) * (len(identifier.encode("utf-8")) + 8 + 7 + 7)
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                strategy_artifact_bytes=_strategy_artifact_bytes(db),
                disk_usage=disk_usage,
            ).require_capacity(projected)
            db.execute(
                "INSERT INTO experiments (id, status, request_json, history_id, history_sha256, "
                "rankings_id, rankings_sha256, code_version, created_at, request_kind, "
                "request_schema_version) VALUES (?, 'pending', ?, ?, ?, '', '', 'profile-v5', ?, "
                "'profile', 5)",
                (identifier, wire, request.dataset_sha256, dataset.dataset_sha256, created_at),
            )
            db.executemany(
                "INSERT INTO runs (experiment_id, ordinal, configuration_id, status, "
                "result_json, result_kind) VALUES (?, ?, NULL, 'pending', NULL, 'profile')",
                [(identifier, ordinal) for ordinal in range(len(request.strategies))],
            )
            db.execute(
                "INSERT INTO experiment_profiles VALUES (?, ?, ?, ?)",
                (identifier, snapshot.profile_id, snapshot.revision, profile_json),
            )
            db.execute(
                "INSERT INTO profile_batch_admissions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    identifier,
                    client_request_id,
                    request_digest,
                    refs_wire,
                    requested_wire,
                    effective_wire,
                    policy_revision,
                    policy_wire,
                    source_wire,
                ),
            )
        return identifier

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
            self._check_pending_capacity(db, 1)
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            before = _admission_logical_bytes(db)
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                strategy_artifact_bytes=_strategy_artifact_bytes(db),
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
            self._check_pending_capacity(db, len(request.strategies))
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
                strategy_artifact_bytes=_strategy_artifact_bytes(db),
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
            db.execute("BEGIN")  # coherent parent, children and dataset dependencies
            return _load_experiment(
                db, identifier, lambda digest: _load_dataset_in_transaction(db, digest)
            )

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
        # Explicit profile schema versions are public only through their validated projection.
        with connection(self.path) as db:
            db.create_function("unicode_casefold", 1, str.casefold, deterministic=True)
            db.execute("BEGIN")  # total, IDs and snapshots share one read view
            total = db.execute(
                "SELECT count(*) FROM experiments WHERE (request_kind = 'legacy' OR "
                "(request_kind = 'profile' AND request_schema_version = 1) OR "
                "(? = 1 AND ((request_kind = 'profile' AND request_schema_version IN (2, 3, 4) "
                "AND (SELECT count(*) FROM runs WHERE experiment_id = experiments.id) = 1 "
                "AND EXISTS (SELECT 1 FROM runs WHERE experiment_id = experiments.id "
                "AND ordinal = 0 AND result_kind = 'profile')) OR "
                "(request_kind = 'profile' AND request_schema_version = 5 "
                "AND EXISTS (SELECT 1 FROM profile_batch_admissions "
                "WHERE experiment_id = experiments.id))))) AND "
                "(? IS NULL OR unicode_casefold(coalesce(json_extract(request_json, '$.name'), "
                "(SELECT client_request_id FROM profile_batch_admissions "
                "WHERE experiment_id = experiments.id))) LIKE ? ESCAPE '\\') "
                "AND (? IS NULL OR status = ?)",
                (include_completed_cycling, pattern, pattern, status, status),
            ).fetchone()[0]
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM experiments WHERE (request_kind = 'legacy' OR "
                    "(request_kind = 'profile' AND request_schema_version = 1) OR "
                    "(? = 1 AND ((request_kind = 'profile' AND request_schema_version IN (2, 3, 4) "
                    "AND (SELECT count(*) FROM runs WHERE experiment_id = experiments.id) = 1 "
                    "AND EXISTS (SELECT 1 FROM runs WHERE experiment_id = experiments.id "
                    "AND ordinal = 0 AND result_kind = 'profile')) OR "
                    "(request_kind = 'profile' AND request_schema_version = 5 "
                    "AND EXISTS (SELECT 1 FROM profile_batch_admissions "
                    "WHERE experiment_id = experiments.id))))) AND "
                    "(? IS NULL OR unicode_casefold(coalesce(json_extract(request_json, '$.name'), "
                    "(SELECT client_request_id FROM profile_batch_admissions "
                    "WHERE experiment_id = experiments.id))) LIKE ? ESCAPE '\\') "
                    "AND (? IS NULL OR status = ?) ORDER BY "
                    "CASE WHEN ? = 'created_at' AND ? = 'asc' THEN created_at END ASC, "
                    "CASE WHEN ? = 'created_at' AND ? = 'desc' THEN created_at END DESC, "
                    "CASE WHEN ? = 'name' AND ? = 'asc' "
                    "THEN json_extract(request_json, '$.name') END COLLATE NOCASE ASC, "
                    "CASE WHEN ? = 'name' AND ? = 'desc' "
                    "THEN json_extract(request_json, '$.name') END COLLATE NOCASE DESC, "
                    "CASE WHEN ? = 'status' AND ? = 'asc' THEN status END ASC, "
                    "CASE WHEN ? = 'status' AND ? = 'desc' THEN status END DESC, "
                    "CASE WHEN ? = 'asc' THEN id END ASC, id DESC LIMIT ? OFFSET ?",
                    (
                        include_completed_cycling,
                        pattern,
                        pattern,
                        status,
                        status,
                        *(sort, order) * 6,
                        order,
                        limit,
                        offset,
                    ),
                )
            ]
            rows = [
                _load_experiment(
                    db, identifier, lambda digest: _load_dataset_in_transaction(db, digest)
                )
                for identifier in ids
            ]
        return total, [row for row in rows if row is not None]

    def search_simulations(
        self,
        offset: int,
        limit: int,
        *,
        scope: str | None = None,
        name_contains: str | None = None,
        status: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
        validate_experiment=None,
        settings=None,
    ):
        """Validate all public snapshots in one read view, then return one bounded page."""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset and limit out of range")
        if scope not in (None, "classic", "profile", "historical"):
            raise ValueError("invalid simulation scope")
        if name_contains is not None and not isinstance(name_contains, str):
            raise ValueError("name_contains must be a string")
        if status is not None and status not in {item.value for item in ExperimentStatus}:
            raise ValueError("invalid simulation status")
        if sort not in _SEARCH_SORTS or order not in _SEARCH_ORDERS:
            raise ValueError("invalid simulation sort")
        if validate_experiment is None:
            raise ValueError("public experiment validator is required")
        pattern = None if name_contains is None else f"%{_escape_like(name_contains.casefold())}%"
        eligible = (
            "(request_kind = 'legacy' AND request_schema_version = 1) OR "
            "(request_kind = 'profile' AND request_schema_version BETWEEN 1 AND 5)"
        )
        eligible_e = (
            "(e.request_kind = 'legacy' AND e.request_schema_version = 1) OR "
            "(e.request_kind = 'profile' AND e.request_schema_version BETWEEN 1 AND 5)"
        )
        with connection(self.path) as db:
            db.create_function("unicode_casefold", 1, str.casefold, deterministic=True)
            db.execute("BEGIN")

            cached_dataset_sha256 = None
            cached_dataset = None
            cached_draws_sha256 = None
            cached_draws = None
            cached_binding_sha256 = None
            cached_binding = None

            def load_dataset(dataset_sha256):
                nonlocal cached_dataset_sha256, cached_dataset
                if dataset_sha256 != cached_dataset_sha256:
                    row = db.execute(
                        "SELECT dataset_sha256, source_sha256, canonical_json, raw_bytes, "
                        "created_at FROM datasets WHERE dataset_sha256 = ?",
                        (dataset_sha256,),
                    ).fetchone()
                    cached_dataset = None if row is None else checked_dataset(row)
                    cached_dataset_sha256 = dataset_sha256
                return cached_dataset

            # Discriminators define public eligibility. Validate sequentially before filters
            # so neither page boundaries nor caller filters can hide damaged eligible rows.
            experiment_ids = db.execute(
                "SELECT id FROM experiments WHERE "
                f"{eligible} ORDER BY CASE WHEN request_kind = 'profile' "
                "AND json_valid(request_json) THEN 'profile:' || "
                "json_extract(request_json, '$.dataset_sha256') ELSE 'other:' || id END, id"
            )
            for (identifier,) in experiment_ids:
                try:
                    saved = _load_experiment(db, identifier, load_dataset)
                    if saved is None:
                        raise ValueError("eligible experiment disappeared from its read snapshot")
                    if not isinstance(saved.request, ExperimentRequest):
                        dataset = load_dataset(saved.request.dataset_sha256)
                        if dataset is None:
                            raise ValueError("missing verified profile dataset")
                        try:
                            dataset_profile = GameProfile.model_validate(
                                json.loads(dataset.canonical_json)["profile"]
                            )
                        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                            raise ValueError("corrupt profile dataset profile") from exc
                        if dataset_profile != saved.profile:
                            raise ValueError(
                                "profile dataset differs from experiment profile snapshot"
                            )
                    validate_experiment(saved)
                    if isinstance(saved.request, ExperimentRequest):
                        for provenance in (saved.history_sha256, saved.rankings_sha256):
                            if (
                                type(provenance) is not str
                                or len(provenance) != 64
                                or any(char not in "0123456789abcdef" for char in provenance)
                            ):
                                raise ValueError("stored experiment provenance hash is invalid")
                        if any(
                            type(value) is not str or not value
                            for value in (
                                saved.history_id,
                                saved.rankings_id,
                                saved.code_version,
                            )
                        ):
                            raise ValueError("stored experiment provenance is incomplete")
                        for run in saved.runs:
                            if run.result is not None:
                                if run.ordinal >= len(saved.request.strategies):
                                    raise ValueError("legacy result has no matching strategy")
                                _validate_result(
                                    run.result,
                                    saved.request.conditions.capital,
                                    saved.request.strategies[run.ordinal].coverage,
                                )
                    else:
                        profile_request = saved.request
                        if (
                            saved.history_id != profile_request.dataset_sha256
                            or saved.history_sha256 != profile_request.dataset_sha256
                            or saved.rankings_id != ""
                            or saved.rankings_sha256 != ""
                            or saved.code_version != f"profile-v{saved.request_schema_version}"
                        ):
                            raise ValueError("stored profile provenance differs from request")
                    if isinstance(saved.request, ProfileBatchRequestV5) and any(
                        run.result is not None for run in saved.runs
                    ):
                        from laboratorio.domain.profile_archive import bind_archived_dataset
                        from laboratorio.settings import Settings

                        dataset_hash = saved.request.dataset_sha256
                        dataset = load_dataset(dataset_hash)
                        if dataset is None:
                            raise ValueError("missing verified v5 dataset")
                        archive_needed = any(
                            strategy.selector.startswith("archived-")
                            for strategy in saved.request.strategies
                        )
                        binding = None
                        if archive_needed:
                            if not isinstance(settings, Settings):
                                raise ValueError(
                                    "trusted Settings required for archived batch results"
                                )
                            if dataset_hash != cached_binding_sha256:
                                cached_binding = bind_archived_dataset(dataset, settings)
                                cached_binding_sha256 = dataset_hash
                            if cached_binding is None:
                                raise ValueError("archived source binding is unavailable")
                            binding = cached_binding
                        if saved.batch_admission is None:
                            raise ValueError("missing v5 batch admission")
                        identity = saved.batch_admission["source_identity"]
                        if identity.get("archive_bound") != (binding is not None):
                            raise ValueError("stored archive binding differs from admission")
                        if binding is not None and (
                            identity.get("archive_history_sha256") != binding.history.sha256
                            or identity.get("archive_rank_row_ids") != list(binding.rank_row_ids)
                        ):
                            raise ValueError("stored archive source differs from admission")
                        for run in saved.runs:
                            if run.result is not None:
                                if not isinstance(run.result, ProfileBatchResultV5):
                                    raise ValueError("stored v5 result has the wrong result type")
                                single = replace(
                                    saved.request,
                                    strategies=(saved.request.strategies[run.ordinal],),
                                )
                                validate_profile_batch_result_v5(
                                    run.result,
                                    single,
                                    saved.profile,
                                    dataset,
                                    binding,
                                    operation_budget=saved.request.max_draws,
                                )
                    elif isinstance(
                        saved.request,
                        (
                            ProfileExperimentRequest,
                            ProfileCyclingRequest,
                            ProfileAudazRequest,
                            ProfileRecoveryRequest,
                        ),
                    ) and any(run.result is not None for run in saved.runs):
                        profile_request = saved.request
                        dataset_hash = profile_request.dataset_sha256
                        if dataset_hash != cached_draws_sha256:
                            dataset = load_dataset(dataset_hash)
                            if dataset is None:
                                raise ValueError("missing verified profile result dataset")
                            cached_draws = _dataset_draws(dataset)
                            cached_draws_sha256 = dataset_hash
                        validator = {
                            1: validate_profile_result,
                            2: validate_profile_cycling_result,
                            3: validate_profile_audaz_result,
                            4: validate_profile_recovery_result,
                        }[saved.request_schema_version]
                        for run in saved.runs:
                            if run.result is not None:
                                validator(run.result, profile_request, saved.profile, cached_draws)
                except (KeyError, TypeError, IndexError) as exc:
                    raise ValueError("stored experiment snapshot is corrupt") from exc
            for row in db.execute(
                "SELECT id, name, config_json, result_json, created_at FROM backtests ORDER BY id"
            ):
                self._validate_simulation_backtest(row)

            rows = db.execute(
                "WITH candidates AS ("
                "SELECT 'experiment' AS source_kind, "
                "CASE WHEN e.request_kind = 'legacy' THEN 'classic' ELSE 'profile' END AS scope, "
                "e.id, e.created_at, CASE WHEN e.request_kind = 'profile' AND "
                "e.request_schema_version = 5 THEN json_extract(e.request_json, "
                "'$.strategies[0].name') ELSE json_extract(e.request_json, '$.name') END AS name, "
                "e.status, e.id AS experiment_id, NULL AS backtest_config, NULL AS backtest_result "
                f"FROM experiments e WHERE {eligible_e} "
                "UNION ALL SELECT 'backtest', 'historical', b.id, b.created_at, b.name, "
                "'completed', NULL, b.config_json, b.result_json FROM backtests b), "
                "filtered AS (SELECT * FROM candidates WHERE (? IS NULL OR scope = ?) "
                "AND (? IS NULL OR status = ?) AND (? IS NULL OR "
                "unicode_casefold(name) LIKE ? ESCAPE '\\')), page AS ("
                "SELECT * FROM filtered ORDER BY "
                "CASE WHEN ? = 'created_at' AND ? = 'asc' THEN created_at END ASC, "
                "CASE WHEN ? = 'created_at' AND ? = 'desc' THEN created_at END DESC, "
                "CASE WHEN ? = 'name' AND ? = 'asc' THEN unicode_casefold(name) END ASC, "
                "CASE WHEN ? = 'name' AND ? = 'desc' THEN unicode_casefold(name) END DESC, "
                "CASE WHEN ? = 'status' AND ? = 'asc' THEN status END ASC, "
                "CASE WHEN ? = 'status' AND ? = 'desc' THEN status END DESC, "
                "source_kind ASC, id ASC LIMIT ? OFFSET ?) "
                "SELECT (SELECT count(*) FROM filtered) AS total, page.* FROM page "
                "UNION ALL SELECT (SELECT count(*) FROM filtered), NULL, NULL, NULL, NULL, "
                "NULL, NULL, NULL, NULL, NULL WHERE NOT EXISTS (SELECT 1 FROM page)",
                (
                    scope,
                    scope,
                    status,
                    status,
                    pattern,
                    pattern,
                    *(sort, order) * 6,
                    limit,
                    offset,
                ),
            ).fetchall()
            total = rows[0][0]
            items = []
            for row in rows:
                if row[1] is None:
                    continue
                source_kind, item_scope, identifier = row[1:4]
                if source_kind == "experiment":
                    saved = _load_experiment(db, identifier, load_dataset)
                    if saved is None:
                        raise ValueError("stored experiment disappeared from its read snapshot")
                    items.append((source_kind, item_scope, saved))
                else:
                    items.append(
                        (
                            source_kind,
                            item_scope,
                            self._backtest_row((identifier, row[5], row[8], row[9], row[4])),
                        )
                    )
        return total, items

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
                strategy_artifact_bytes=_strategy_artifact_bytes(db),
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

    def complete_profile_batch_run(
        self,
        identifier: str,
        ordinal: int,
        result: ProfileBatchResultV5,
        *,
        settings,
        quota_bytes: int | None = None,
        quota_explicit: bool | None = None,
        disk_usage=shutil.disk_usage,
    ) -> None:
        """Validate one worker result against full saved data and trusted archive context.

        The worker's inner result ordinal is zero; this method binds it to the actual
        outer run ordinal and exact persisted strategy revision before storing it.
        """
        from laboratorio.domain.profile_archive import bind_archived_dataset
        from laboratorio.settings import Settings

        if type(settings) is not Settings:
            raise ValueError("trusted Settings context is required to complete a v5 run")
        saved = self.get_experiment(identifier)
        if (
            saved is None
            or saved.request_kind != "profile"
            or saved.request_schema_version != 5
            or not isinstance(saved.request, ProfileBatchRequestV5)
            or saved.status is not ExperimentStatus.RUNNING
            or type(ordinal) is not int
            or not 0 <= ordinal < len(saved.request.strategies)
            or len(saved.runs) != len(saved.request.strategies)
            or saved.runs[ordinal].ordinal != ordinal
            or saved.runs[ordinal].status is not RunStatus.RUNNING
            or saved.runs[ordinal].result is not None
        ):
            raise ValueError("v5 profile run not owned, running or missing")
        request = saved.request
        dataset = self.get_dataset(request.dataset_sha256)
        if dataset is None:
            raise ValueError("v5 profile dataset missing")
        archive_needed = any(
            definition.selector.startswith("archived-") for definition in request.strategies
        )
        binding = bind_archived_dataset(dataset, settings) if archive_needed else None
        identity = saved.batch_admission["source_identity"] if saved.batch_admission else None
        if (
            identity is None
            or identity.get("dataset_sha256") != dataset.dataset_sha256
            or identity.get("source_sha256") != dataset.source_sha256
            or identity.get("canonical_sha256")
            != hashlib.sha256(dataset.canonical_json).hexdigest()
            or identity.get("archive_bound") != (binding is not None)
            or (
                binding is not None
                and (
                    identity.get("archive_history_sha256") != binding.history.sha256
                    or identity.get("archive_rank_row_ids") != list(binding.rank_row_ids)
                )
            )
        ):
            raise ValueError("trusted source context differs from frozen batch admission")
        single = replace(request, strategies=(request.strategies[ordinal],))
        admitted = validate_profile_batch_result_v5(
            result,
            single,
            saved.profile,
            dataset,
            binding,
            operation_budget=request.max_draws,
        )
        serialized = serialize_profile_batch_result_v5(admitted)
        wire = serialize_profile_batch_v5(request)
        profile_json = saved.profile.model_dump_json()
        with _transaction(self.path) as db:
            experiment_row = db.execute(
                "SELECT status, request_json, request_kind, history_id, history_sha256, "
                "rankings_id, rankings_sha256, code_version, request_schema_version "
                "FROM experiments WHERE id = ?",
                (identifier,),
            ).fetchone()
            run_row = db.execute(
                "SELECT ordinal, status, result_json, result_kind, result_schema_version "
                "FROM runs WHERE experiment_id = ? AND ordinal = ?",
                (identifier, ordinal),
            ).fetchone()
            profile_row = db.execute(
                "SELECT profile_id, revision, profile_json FROM experiment_profiles "
                "WHERE experiment_id = ?",
                (identifier,),
            ).fetchone()
            if (
                experiment_row
                != (
                    "running",
                    wire,
                    "profile",
                    request.dataset_sha256,
                    request.dataset_sha256,
                    "",
                    "",
                    "profile-v5",
                    5,
                )
                or run_row != (ordinal, "running", None, "profile", None)
                or profile_row != (request.profile_id, request.profile_revision, profile_json)
            ):
                raise ValueError("v5 profile request/run association changed during replay")
            effective = _effective_quota(db, quota_bytes, quota_explicit)
            projected = len(serialized.encode("utf-8")) + len("completed") - len("running") + 1
            measure(
                self.path,
                effective.effective_bytes,
                _logical_experiment_bytes(db),
                profile_artifact_bytes=_profile_artifact_bytes(db),
                dataset_artifact_bytes=_dataset_artifact_bytes(db),
                strategy_artifact_bytes=_strategy_artifact_bytes(db),
                disk_usage=disk_usage,
            ).require_capacity(projected)
            changed = db.execute(
                "UPDATE runs SET status = 'completed', result_json = ?, result_schema_version = 5 "
                "WHERE experiment_id = ? AND ordinal = ? AND status = 'running' "
                "AND result_kind = 'profile' AND result_schema_version IS NULL "
                "AND result_json IS NULL",
                (serialized, identifier, ordinal),
            ).rowcount
            if changed != 1:
                raise ValueError("v5 profile run no longer running")

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
                strategy_artifact_bytes=_strategy_artifact_bytes(db),
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

    def create_backtest(self, name: str, config: dict, result):
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
        config_json = json.dumps(
            config, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        result_json = json.dumps(
            result_payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        with _transaction(self.path) as db:
            db.execute(
                "INSERT INTO backtests (id, name, config_json, result_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (identifier, name, config_json, result_json, created_at),
            )
        return identifier, created_at

    @staticmethod
    def _backtest_row(row):
        identifier, name, config_json, result_json, created_at = row
        try:
            config = json.loads(config_json)
            result = json.loads(result_json)
            if type(config) is not dict or type(result) is not dict:
                raise ValueError("saved backtest fields must be objects")
            return {
                "id": identifier,
                "name": name,
                "created_at": created_at,
                **result,
                "config": config,
            }
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("stored backtest snapshot is corrupt") from exc

    @staticmethod
    def _validate_simulation_backtest(row):
        import math
        from decimal import ROUND_HALF_UP, Decimal

        from laboratorio.api.backtests import CreateBacktest
        from laboratorio.domain.backtest import BacktestConfig
        from laboratorio.domain.contracts import make_game

        identifier, name, _, result_json, _ = row
        saved = Repository._backtest_row(row)
        try:
            config = CreateBacktest.model_validate(saved["config"])
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
            if type(result) is not dict or result.keys() != expected:
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
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"stored backtest {identifier} is corrupt") from exc

    def get_backtest(self, identifier: str):
        with connection(self.path) as db:
            row = db.execute(
                "SELECT id, name, config_json, result_json, created_at FROM backtests WHERE id = ?",
                (identifier,),
            ).fetchone()
        return None if row is None else self._backtest_row(row)

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
