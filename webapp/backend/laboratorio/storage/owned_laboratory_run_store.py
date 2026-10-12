"""Read validated runs owned by an explicit laboratory identifier."""

import copy
import json
import uuid

from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage.reference_lab_store import (
    SCHEMA_VERSION,
    _check_header,
    _loads,
    _validate_result,
    _validate_session_rows,
)


class OwnedLaboratoryRunStoreError(ValueError):
    """Invalid identifiers or corrupt owned-laboratory run storage data."""


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
