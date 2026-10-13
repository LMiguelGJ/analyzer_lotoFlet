"""Persist and read validated runs owned by an explicit laboratory identifier."""

import copy
import json
import shutil
import uuid
from dataclasses import fields

from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage.laboratory_store import LaboratoryStoreError
from laboratorio.storage.laboratory_store import _decode as _decode_definition
from laboratorio.storage.laboratory_store import _row as _definition_row
from laboratorio.storage.quota import QuotaStatus, measure, validate_quota_bytes
from laboratorio.storage.reference_lab_store import (
    MAX_PAYLOAD_BYTES,
    SCHEMA_VERSION,
    _canonical,
    _check_header,
    _loads,
    _validate_result,
    _validate_session_rows,
)


class OwnedLaboratoryRunStoreError(ValueError):
    """Invalid owned-run inputs or corrupt owned-laboratory storage data."""


def _canonical_uuid(value):
    if type(value) is not str:
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _decode_run(row, session_rows):
    identifier, owner_id, lab_id, version, created_at, metadata_json, result_json = row
    try:
        _check_header(identifier, lab_id, version, created_at)
        snapshot = OwnedLaboratoryRunSnapshot.from_mapping(_loads(metadata_json))
        envelope = _loads(result_json)
        if (
            type(envelope) is not dict
            or set(envelope) != {"schema_version", "result"}
            or type(envelope["schema_version"]) is not int
            or envelope["schema_version"] != SCHEMA_VERSION
        ):
            raise ValueError("invalid result envelope")
        result = envelope["result"]
        definition = snapshot.definition
        if (
            owner_id != lab_id
            or definition.id != lab_id
            or type(result) is not dict
            or result.get("lab_id") != lab_id
        ):
            raise ValueError("owner, snapshot and result identities disagree")
        sessions = result.get("sessions")
        _validate_result(lab_id, definition.config.capital, result)
        _validate_session_rows(sessions, session_rows, definition.config.capital)
        return {
            "id": identifier,
            "owner_laboratory_id": owner_id,
            "lab_id": lab_id,
            "contract_version": version,
            "created_at": created_at,
            "snapshot": snapshot.to_mapping(),
            "result": result,
            "sessions": copy.deepcopy(sessions),
        }
    except (
        TypeError,
        ValueError,
        KeyError,
        OverflowError,
        RecursionError,
        json.JSONDecodeError,
    ) as exc:
        raise OwnedLaboratoryRunStoreError("corrupt owned-laboratory run") from exc


def create_run(repo, run_id, owner_laboratory_id, snapshot, result, *, quota_bytes, quota_explicit):
    from laboratorio.storage.repository import (
        RepositoryQuotaStatus,
        _dataset_artifact_bytes,
        _history_artifact_bytes,
        _laboratory_definition_bytes,
        _logical_experiment_bytes,
        _now_iso,
        _profile_artifact_bytes,
        _run_artifact_bytes,
        _strategy_artifact_bytes,
        _transaction,
    )

    try:
        if not _canonical_uuid(run_id) or not _canonical_uuid(owner_laboratory_id):
            raise ValueError("invalid identifiers")
        if type(snapshot) is not OwnedLaboratoryRunSnapshot:
            raise ValueError("snapshot must be an owned-laboratory run snapshot")
        # Round-trip the strict codec rather than trusting a potentially forged object.
        validated = OwnedLaboratoryRunSnapshot.from_mapping(snapshot.to_mapping())
        definition = validated.definition
        if definition.id != owner_laboratory_id:
            raise ValueError("snapshot owner mismatch")
        result_json, sessions_json = _validate_result(
            owner_laboratory_id, definition.config.capital, result
        )
        metadata_json = _canonical(validated.to_mapping())
        definition_json = _canonical(definition.to_mapping())
    except (AttributeError, TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory run input") from exc

    created_at = _now_iso()
    payload_bytes = (
        len(run_id.encode("utf-8"))
        + len(owner_laboratory_id.encode("utf-8"))
        + 8
        + len(created_at.encode("utf-8"))
        + len(metadata_json.encode("utf-8"))
        + len(result_json.encode("utf-8"))
        + sum(len(run_id.encode("utf-8")) + 8 + len(item.encode("utf-8")) for item in sessions_json)
    )
    if payload_bytes > MAX_PAYLOAD_BYTES:
        raise OwnedLaboratoryRunStoreError("owned-laboratory payload exceeds storage limit")
    effective = repo.effective_quota(quota_bytes, quota_explicit=quota_explicit)
    limit = validate_quota_bytes(effective.effective_bytes)
    with _transaction(repo.path) as db:
        # Hold the writer lock through the definition check, quota admission and inserts.
        row = _definition_row(db, owner_laboratory_id)
        if row is None:
            raise OwnedLaboratoryRunStoreError("owned-laboratory definition is missing or changed")
        try:
            current = _decode_definition(row)
        except LaboratoryStoreError as exc:
            raise OwnedLaboratoryRunStoreError("corrupt owned-laboratory definition") from exc
        if _canonical(current.to_mapping()) != definition_json:
            raise OwnedLaboratoryRunStoreError("owned-laboratory definition is missing or changed")
        base = measure(
            repo.path,
            limit,
            _logical_experiment_bytes(db),
            profile_artifact_bytes=_profile_artifact_bytes(db),
            dataset_artifact_bytes=_dataset_artifact_bytes(db),
            strategy_artifact_bytes=_strategy_artifact_bytes(db),
            disk_usage=shutil.disk_usage,
        )
        status = RepositoryQuotaStatus(
            **{field.name: getattr(base, field.name) for field in fields(QuotaStatus)},
            history_artifact_bytes=_history_artifact_bytes(db),
            run_artifact_bytes=_run_artifact_bytes(db),
            laboratory_definition_bytes=_laboratory_definition_bytes(db),
        )
        status.require_capacity(payload_bytes)
        db.execute(
            "INSERT INTO reference_lab_runs "
            "(id,lab_id,contract_version,created_at,metadata_json,result_json,"
            "owner_laboratory_id) VALUES (?,?,?,?,?,?,?)",
            (
                run_id,
                owner_laboratory_id,
                SCHEMA_VERSION,
                created_at,
                metadata_json,
                result_json,
                owner_laboratory_id,
            ),
        )
        db.executemany(
            "INSERT INTO reference_lab_sessions (run_id,ordinal,session_json) VALUES (?,?,?)",
            [(run_id, index, value) for index, value in enumerate(sessions_json)],
        )
    return run_id


def get_run(conn, owner_laboratory_id, run_id):
    if not _canonical_uuid(owner_laboratory_id) or not _canonical_uuid(run_id):
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory run identifiers")
    row = conn.execute(
        "SELECT id,owner_laboratory_id,lab_id,contract_version,created_at,"
        "metadata_json,result_json "
        "FROM reference_lab_runs WHERE id=? AND owner_laboratory_id=?",
        (run_id, owner_laboratory_id),
    ).fetchone()
    if row is None:
        return None
    session_rows = conn.execute(
        "SELECT ordinal,session_json FROM reference_lab_sessions WHERE run_id=? ORDER BY ordinal",
        (run_id,),
    ).fetchall()
    return _decode_run(row, session_rows)
