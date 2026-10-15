"""Persist and read validated runs owned by an explicit laboratory identifier."""

import copy
import hashlib
import json
import shutil
import uuid
from dataclasses import fields

from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.storage.laboratory_store import LaboratoryStoreError
from laboratorio.storage.laboratory_store import _decode as _decode_definition
from laboratorio.storage.laboratory_store import _row as _definition_row
from laboratorio.storage.owned_laboratory_read_cache import OwnedLaboratoryReadCertificate
from laboratorio.storage.quota import QuotaStatus, measure, validate_quota_bytes
from laboratorio.storage.reference_lab_store import (
    MAX_PAYLOAD_BYTES,
    SCHEMA_VERSION,
    _canonical,
    _check_header,
    _check_session,
    _loads,
    _paging,
    _validate_result,
    _validate_session_rows,
)


class OwnedLaboratoryRunStoreError(ValueError):
    """Invalid owned-run inputs or corrupt owned-laboratory storage data."""


class OwnedLaboratoryRunCapacityError(OwnedLaboratoryRunStoreError):
    """A valid complete owned result exceeds the per-run payload byte limit."""


def _max_owned_sessions(result):
    """Return the strict eligible-draw bound, or an invalid sentinel for bad input."""
    if type(result) is not dict:
        return -1
    eligible_draws = result.get("eligible_draws")
    return eligible_draws if type(eligible_draws) is int else -1


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
        _validate_result(
            lab_id,
            definition.config.capital,
            result,
            max_sessions=_max_owned_sessions(result),
        )
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
            owner_laboratory_id,
            definition.config.capital,
            result,
            max_sessions=_max_owned_sessions(result),
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
        raise OwnedLaboratoryRunCapacityError("owned-laboratory payload exceeds storage limit")
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


def list_runs(repo, owner_laboratory_id, *, offset=0, limit=20):
    """Return only the selected owner's validated run summaries in one read view."""
    from laboratorio.storage.database import connection

    if not _canonical_uuid(owner_laboratory_id):
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory owner identifier")
    try:
        _paging(offset, limit)
    except ValueError as exc:
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory run pagination") from exc

    with connection(repo.path) as db:
        db.execute("BEGIN")
        total = db.execute(
            "SELECT count(*) FROM reference_lab_runs WHERE owner_laboratory_id=?",
            (owner_laboratory_id,),
        ).fetchone()[0]
        identifiers = db.execute(
            "SELECT id FROM reference_lab_runs WHERE owner_laboratory_id=? "
            "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (owner_laboratory_id, limit, offset),
        ).fetchall()
        items = []
        for (identifier,) in identifiers:
            run = get_run(db, owner_laboratory_id, identifier)
            if run is None:
                raise OwnedLaboratoryRunStoreError("corrupt owned-laboratory run")
            items.append(
                {
                    **{
                        key: run[key]
                        for key in (
                            "id",
                            "owner_laboratory_id",
                            "lab_id",
                            "contract_version",
                            "created_at",
                        )
                    },
                    "summary": {
                        key: run["result"][key] for key in ("totals", "eligible_draws", "gaps")
                    },
                }
            )
    return {"total": total, "offset": offset, "limit": limit, "items": items}


def _read_epoch(db):
    row = db.execute("SELECT epoch FROM owned_run_integrity_epoch WHERE singleton=1").fetchone()
    if row is None or type(row[0]) is not int or row[0] < 0:
        raise OwnedLaboratoryRunStoreError("corrupt owned-run integrity epoch")
    return row[0]


def _compact_record(record):
    result = record["result"]
    return {
        **{
            key: record[key]
            for key in ("id", "owner_laboratory_id", "lab_id", "contract_version", "created_at")
        },
        "snapshot": record["snapshot"],
        "summary": {
            **{
                key: result[key]
                for key in ("eligible_draws", "gaps", "first", "last", "session_sha256")
            },
            "session_count": result["totals"]["sessions_total"],
            "totals": result["totals"],
        },
    }


def _certificate_for(record):
    compact = _compact_record(record)
    metadata = _canonical(compact).encode("utf-8")
    digests = b"".join(
        hashlib.sha256(_canonical(session).encode("utf-8")).digest()
        for session in record["sessions"]
    )
    return OwnedLaboratoryReadCertificate(metadata, digests)


def _decode_certificate(certificate, owner_id, run_id):
    try:
        value = json.loads(certificate.metadata)
        if (
            type(value) is not dict
            or set(value)
            != {
                "id",
                "owner_laboratory_id",
                "lab_id",
                "contract_version",
                "created_at",
                "snapshot",
                "summary",
            }
            or value["id"] != run_id
            or value["owner_laboratory_id"] != owner_id
            or value["lab_id"] != owner_id
        ):
            raise ValueError("invalid compact run metadata")
        _check_header(value["id"], value["lab_id"], value["contract_version"], value["created_at"])
        value["snapshot"] = OwnedLaboratoryRunSnapshot.from_mapping(value["snapshot"]).to_mapping()
        summary = value["summary"]
        if (
            type(summary) is not dict
            or set(summary)
            != {
                "eligible_draws",
                "gaps",
                "first",
                "last",
                "session_sha256",
                "session_count",
                "totals",
            }
            or type(summary["totals"]) is not dict
            or type(summary["session_count"]) is not int
            or summary["session_count"] < 0
            or len(certificate.session_digests) != summary["session_count"] * 32
        ):
            raise ValueError("invalid compact run summary")
        return value
    except (
        TypeError,
        ValueError,
        KeyError,
        OverflowError,
        RecursionError,
        json.JSONDecodeError,
    ) as exc:
        raise OwnedLaboratoryRunStoreError("corrupt owned-laboratory run certificate") from exc


def _load_certificate(db, repo, owner_id, run_id, epoch):
    cache = repo._owned_laboratory_read_cache
    certificate = cache.get(repo._owned_laboratory_database_id, epoch, owner_id, run_id)
    if certificate is not None:
        return _decode_certificate(certificate, owner_id, run_id), certificate

    row = db.execute(
        "SELECT id,owner_laboratory_id,lab_id,contract_version,created_at,metadata_json,"
        "result_json "
        "FROM reference_lab_runs WHERE id=? AND owner_laboratory_id=?",
        (run_id, owner_id),
    ).fetchone()
    if row is None:
        return None, None
    session_rows = db.execute(
        "SELECT ordinal,session_json FROM reference_lab_sessions WHERE run_id=? ORDER BY ordinal",
        (run_id,),
    ).fetchall()
    record = _decode_run(row, session_rows)
    certificate = _certificate_for(record)
    cache.put(repo._owned_laboratory_database_id, epoch, owner_id, run_id, certificate)
    return _compact_record(record), certificate


def list_run_summaries(repo, owner_laboratory_id, *, offset=0, limit=20):
    """Return page summaries with cold validation and bounded warm reads."""
    from laboratorio.storage.database import connection

    if not _canonical_uuid(owner_laboratory_id):
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory owner identifier")
    try:
        _paging(offset, limit)
    except ValueError as exc:
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory run pagination") from exc

    with connection(repo.path) as db:
        db.execute("BEGIN")
        epoch = _read_epoch(db)
        total = db.execute(
            "SELECT count(*) FROM reference_lab_runs WHERE owner_laboratory_id=?",
            (owner_laboratory_id,),
        ).fetchone()[0]
        identifiers = db.execute(
            "SELECT id FROM reference_lab_runs WHERE owner_laboratory_id=? "
            "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (owner_laboratory_id, limit, offset),
        ).fetchall()
        items = []
        for (identifier,) in identifiers:
            record, _certificate = _load_certificate(
                db, repo, owner_laboratory_id, identifier, epoch
            )
            if record is None:
                raise OwnedLaboratoryRunStoreError("corrupt owned-laboratory run")
            items.append(
                {
                    **{
                        key: record[key]
                        for key in (
                            "id",
                            "owner_laboratory_id",
                            "lab_id",
                            "contract_version",
                            "created_at",
                        )
                    },
                    "summary": {
                        key: record["summary"][key] for key in ("totals", "eligible_draws", "gaps")
                    },
                }
            )
    return {"total": total, "offset": offset, "limit": limit, "items": items}


def get_run_summary(repo, owner_id, run_id):
    """Read the public compact detail projection without retaining full results."""
    from laboratorio.storage.database import connection

    if not _canonical_uuid(owner_id) or not _canonical_uuid(run_id):
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory run identifiers")
    with connection(repo.path) as db:
        db.execute("BEGIN")
        epoch = _read_epoch(db)
        record, _certificate = _load_certificate(db, repo, owner_id, run_id, epoch)
    return record


def list_run_sessions(repo, owner_id, run_id, *, offset=0, limit=50):
    """Fetch and validate only the requested session page against its certificate."""
    from laboratorio.storage.database import connection

    if not _canonical_uuid(owner_id) or not _canonical_uuid(run_id):
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory run identifiers")
    try:
        _paging(offset, limit)
    except ValueError as exc:
        raise OwnedLaboratoryRunStoreError("invalid owned-laboratory run pagination") from exc

    with connection(repo.path) as db:
        db.execute("BEGIN")
        epoch = _read_epoch(db)
        record, certificate = _load_certificate(db, repo, owner_id, run_id, epoch)
        if record is None:
            return None
        if certificate is None:
            raise OwnedLaboratoryRunStoreError("missing owned-laboratory run certificate")
        total = record["summary"]["session_count"]
        page_rows = db.execute(
            "SELECT ordinal,session_json FROM reference_lab_sessions WHERE run_id=? "
            "ORDER BY ordinal LIMIT ? OFFSET ?",
            (run_id, limit, offset),
        ).fetchall()
        items = []
        capital = OwnedLaboratoryRunSnapshot.from_mapping(
            record["snapshot"]
        ).definition.config.capital
        for index, (ordinal, session_json) in enumerate(page_rows):
            try:
                if type(ordinal) is not int or ordinal != offset + index:
                    raise ValueError("invalid session ordinal")
                session = _loads(session_json)
                _check_session(session, capital)
                expected = certificate.session_digests[ordinal * 32 : (ordinal + 1) * 32]
                actual = hashlib.sha256(_canonical(session).encode("utf-8")).digest()
                if actual != expected:
                    raise ValueError("session digest mismatch")
            except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
                raise OwnedLaboratoryRunStoreError("corrupt owned-laboratory session") from exc
            items.append({"ordinal": ordinal, "summary": session})
    return {"run_id": run_id, "total": total, "offset": offset, "limit": limit, "items": items}
