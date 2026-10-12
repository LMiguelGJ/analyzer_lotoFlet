"""Bounded immutable storage for reference-laboratory run summaries."""

import hashlib
import json
import math
import sqlite3
import uuid
from datetime import UTC, datetime

from laboratorio.storage.quota import QuotaStatus, measure, validate_quota_bytes

SCHEMA_VERSION = 1
MAX_SESSIONS = 50_000
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
_MAX_I64 = 2**63 - 1
_MIN_I64 = -(2**63)
_SUMMARY_MAX_CHARS = 2048
_OUTCOMES = ("goal", "ruin", "incomplete")
_SESSION_KEYS = (
    "outcome",
    "start_index",
    "end_index",
    "draws",
    "final_balance",
    "wagered",
    "paid",
)
_TOTAL_KEYS = frozenset(
    {
        "completed",
        "incomplete",
        "goals",
        "ruins",
        "sessions_total",
        "total_wagered",
        "total_paid",
        "total_net",
        "total_steps",
        "mean_net_closed",
    }
)


class ReferenceLabStoreError(ValueError):
    """Invalid, corrupt, or unsupported reference-laboratory persistence data."""


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _loads(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = item
        return result

    return json.loads(
        value,
        object_pairs_hook=pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )


def _integer(value, *, minimum=_MIN_I64):
    if type(value) is not int or not minimum <= value <= _MAX_I64:
        raise ValueError("invalid persisted integer")
    return value


def _text(value, *, optional=False):
    if optional and value is None:
        return
    if type(value) is not str or not value:
        raise ValueError("invalid persisted text")


def _validate_json_values(value):
    if type(value) is int:
        _integer(value)
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("non-finite persisted number")
    elif type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("invalid JSON object key")
        for item in value.values():
            _validate_json_values(item)
    elif type(value) is list or type(value) is tuple:
        for item in value:
            _validate_json_values(item)
    elif value is not None and type(value) not in (str, bool, float):
        raise ValueError("unsupported JSON value")


def _check_totals(totals):
    if type(totals) is not dict or set(totals) != _TOTAL_KEYS:
        raise ValueError("invalid result totals")
    for key in _TOTAL_KEYS - {"mean_net_closed"}:
        _integer(totals[key], minimum=0 if key != "total_net" else _MIN_I64)
    mean = totals["mean_net_closed"]
    if mean is not None and (type(mean) is not float or not math.isfinite(mean)):
        raise ValueError("invalid mean")
    if (
        totals["completed"] + totals["incomplete"] != totals["sessions_total"]
        or totals["goals"] + totals["ruins"] != totals["completed"]
        or totals["total_net"] != totals["total_paid"] - totals["total_wagered"]
    ):
        raise ValueError("inconsistent result totals")


def _check_session(session, capital):
    """Validate one session summary strictly and return its digest row."""
    if type(session) is not dict or set(session) != set(_SESSION_KEYS):
        raise ValueError("invalid session summary")
    outcome = session["outcome"]
    if type(outcome) is not str or outcome not in _OUTCOMES:
        raise ValueError("invalid outcome")
    start = _integer(session["start_index"], minimum=0)
    end = _integer(session["end_index"], minimum=0)
    draws = _integer(session["draws"], minimum=1)
    final = _integer(session["final_balance"], minimum=0)
    wagered = _integer(session["wagered"], minimum=0)
    paid = _integer(session["paid"], minimum=0)
    if end < start or end - start + 1 != draws:
        raise ValueError("invalid session range")
    if final != capital + paid - wagered:
        raise ValueError("session balance disagrees with capital, paid and wagered")
    return outcome, start, end, draws, final, wagered, paid


def _session_digest(rows):
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def _validate_input(run_id, lab_id, config, provenance, result):
    try:
        if type(run_id) is not str or str(uuid.UUID(run_id)) != run_id:
            raise ValueError("run id must be a canonical UUID")
        _text(lab_id)
        if type(config) is not dict or config.get("lab_id") != lab_id:
            raise ValueError("config lab id mismatch")
        _validate_json_values(config)
        capital = _integer(config.get("capital"), minimum=1)
        if type(provenance) is not dict:
            raise ValueError("invalid provenance")
        _validate_json_values(provenance)
        history = provenance.get("history_sha256")
        rankings = provenance.get("rankings_sha256")
        if (
            type(history) is not str
            or len(history) != 64
            or any(char not in "0123456789abcdef" for char in history)
            or type(rankings) is not str
            or len(rankings) != 64
            or any(char not in "0123456789abcdef" for char in rankings)
            or provenance.get("history_origin") != "frozen"
        ):
            raise ValueError("invalid provenance")
        if type(result) is not dict or result.get("lab_id") != lab_id:
            raise ValueError("invalid result")
        _validate_json_values(result)
        sessions, totals = result.get("sessions"), result.get("totals")
        if type(sessions) is tuple:
            result = {**result, "sessions": list(sessions)}
            sessions = result["sessions"]
        if type(sessions) is not list or len(sessions) > MAX_SESSIONS or type(totals) is not dict:
            raise ValueError("invalid session summaries")
        _check_totals(totals)
        if totals["sessions_total"] != len(sessions):
            raise ValueError("inconsistent result totals")
        if set(result) != {
            "lab_id",
            "sessions",
            "totals",
            "eligible_draws",
            "gaps",
            "first",
            "last",
            "session_sha256",
        }:
            raise ValueError("unknown result fields")
        _integer(result["eligible_draws"], minimum=0)
        _integer(result["gaps"], minimum=0)
        _text(result["first"], optional=True)
        _text(result["last"], optional=True)
        digest = result["session_sha256"]
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ValueError("invalid session digest")
        session_totals = {"goal": 0, "ruin": 0, "incomplete": 0}
        session_wagered = session_paid = session_steps = closed_count = closed_net = 0
        digest_rows = []
        for session in sessions:
            row = _check_session(session, capital)
            digest_rows.append(row)
            outcome, _start, _end, draws, final, wagered, paid = row
            session_totals[outcome] += 1
            if outcome != "incomplete":
                closed_count += 1
                closed_net += final - capital
            session_wagered += wagered
            session_paid += paid
            session_steps += draws
        if (
            session_totals["goal"] != totals["goals"]
            or session_totals["ruin"] != totals["ruins"]
            or session_totals["incomplete"] != totals["incomplete"]
            or session_wagered != totals["total_wagered"]
            or session_paid != totals["total_paid"]
            or session_steps != totals["total_steps"]
        ):
            raise ValueError("session summaries disagree with totals")
        if totals["mean_net_closed"] != (closed_net / closed_count if closed_count else None):
            raise ValueError("mean net disagrees with completed sessions")
        if digest != _session_digest(digest_rows):
            raise ValueError("session digest disagrees with the sessions")
        metadata = _canonical(
            {"schema_version": SCHEMA_VERSION, "config": config, "provenance": provenance}
        )
        result_json = _canonical({"schema_version": SCHEMA_VERSION, "result": result})
        sessions_json = [_canonical(session) for session in sessions]
        return metadata, result_json, sessions_json
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ReferenceLabStoreError("invalid reference-laboratory run") from exc


def _created_at_valid(value):
    if type(value) is not str:
        raise ValueError
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError


def _check_header(identifier, lab_id, version, created_at):
    if (
        type(identifier) is not str
        or str(uuid.UUID(identifier)) != identifier
        or type(lab_id) is not str
        or not lab_id
        or type(version) is not int
        or version != SCHEMA_VERSION
    ):
        raise ValueError
    _created_at_valid(created_at)


def _decode_run(row, session_rows):
    identifier, lab_id, version, created_at, metadata_json, result_json = row
    try:
        _check_header(identifier, lab_id, version, created_at)
        metadata, result_envelope = _loads(metadata_json), _loads(result_json)
        if (
            type(metadata) is not dict
            or set(metadata) != {"schema_version", "config", "provenance"}
            or type(metadata["schema_version"]) is not int
            or metadata["schema_version"] != SCHEMA_VERSION
            or type(metadata["config"]) is not dict
            or metadata["config"].get("lab_id") != lab_id
            or type(metadata["provenance"]) is not dict
            or type(result_envelope) is not dict
            or set(result_envelope) != {"schema_version", "result"}
            or type(result_envelope["schema_version"]) is not int
            or result_envelope["schema_version"] != SCHEMA_VERSION
        ):
            raise ValueError
        result = result_envelope["result"]
        sessions = result.get("sessions") if type(result) is dict else None
        if type(sessions) is not list or len(sessions) != len(session_rows):
            raise ValueError
        capital = _integer(metadata["config"].get("capital"), minimum=1)
        for index, (ordinal, session_json) in enumerate(session_rows):
            copy = _loads(session_json)
            _check_session(copy, capital)
            if (
                type(ordinal) is not int
                or ordinal != index
                or _canonical(copy) != _canonical(sessions[index])
            ):
                raise ValueError
        _validate_input(identifier, lab_id, metadata["config"], metadata["provenance"], result)
        return {
            "id": identifier,
            "lab_id": lab_id,
            "contract_version": version,
            "created_at": created_at,
            "config": metadata["config"],
            "provenance": metadata["provenance"],
            "result": result,
            "sessions": sessions,
        }
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
        raise ReferenceLabStoreError("stored reference-laboratory run is corrupt") from exc


def _read_run(db, run_id):
    row = db.execute(
        "SELECT id,lab_id,contract_version,created_at,metadata_json,result_json "
        "FROM reference_lab_runs WHERE id=?",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    sessions = db.execute(
        "SELECT ordinal,session_json FROM reference_lab_sessions WHERE run_id=? ORDER BY ordinal",
        (run_id,),
    ).fetchall()
    return _decode_run(row, sessions)


def _summary_item(row):
    identifier, lab_id, version, created_at, text = row
    try:
        _check_header(identifier, lab_id, version, created_at)
        if type(text) is not str:
            raise ValueError
        totals, eligible_draws, gaps = _loads(text)
        _check_totals(totals)
        _integer(eligible_draws, minimum=0)
        _integer(gaps, minimum=0)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ReferenceLabStoreError("stored reference-laboratory run is corrupt") from exc
    return {
        "id": identifier,
        "lab_id": lab_id,
        "contract_version": version,
        "created_at": created_at,
        "summary": {"eligible_draws": eligible_draws, "gaps": gaps, "totals": totals},
    }


def _paging(offset, limit):
    if type(offset) is not int or not 0 <= offset <= _MAX_I64:
        raise ValueError("offset out of range")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit out of range")


def create_reference_lab_run(
    repo, run_id, lab_id, config, provenance, result, *, quota_bytes, quota_explicit
):
    import shutil
    from dataclasses import fields

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

    metadata_json, result_json, sessions_json = _validate_input(
        run_id, lab_id, config, provenance, result
    )
    created_at = _now_iso()
    payload_bytes = (
        len(run_id.encode("utf-8"))
        + len(lab_id.encode("utf-8"))
        + 8
        + len(created_at.encode("utf-8"))
        + len(metadata_json.encode("utf-8"))
        + len(result_json.encode("utf-8"))
        + sum(len(run_id.encode("utf-8")) + 8 + len(item.encode("utf-8")) for item in sessions_json)
    )
    if payload_bytes > MAX_PAYLOAD_BYTES:
        raise ReferenceLabStoreError("reference-laboratory payload exceeds storage limit")
    effective = repo.effective_quota(quota_bytes, quota_explicit=quota_explicit)
    limit = validate_quota_bytes(effective.effective_bytes)
    with _transaction(repo.path) as db:
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
            "(id, lab_id, contract_version, created_at, metadata_json, result_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, lab_id, SCHEMA_VERSION, created_at, metadata_json, result_json),
        )
        db.executemany(
            "INSERT INTO reference_lab_sessions (run_id,ordinal,session_json) VALUES (?,?,?)",
            [(run_id, index, value) for index, value in enumerate(sessions_json)],
        )
    return run_id


def get_reference_lab_run(repo, run_id):
    from laboratorio.storage.database import connection

    with connection(repo.path) as db:
        return _read_run(db, run_id)


def list_reference_lab_runs(repo, *, lab_id=None, offset=0, limit=20):
    from laboratorio.storage.database import connection

    _paging(offset, limit)
    if lab_id is not None and (type(lab_id) is not str or not lab_id):
        raise ValueError("lab_id must be non-empty text")
    with connection(repo.path) as db:
        db.execute("BEGIN")
        total = db.execute(
            "SELECT count(*) FROM reference_lab_runs WHERE (? IS NULL OR lab_id=?)",
            (lab_id, lab_id),
        ).fetchone()[0]
        try:
            rows = db.execute(
                "WITH page AS MATERIALIZED ("
                "SELECT id,lab_id,contract_version,created_at,"
                "json_extract(result_json,'$.result.totals','$.result.eligible_draws',"
                "'$.result.gaps') AS summary "
                "FROM reference_lab_runs WHERE (? IS NULL OR lab_id=?) "
                "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?) "
                "SELECT id,lab_id,contract_version,created_at,"
                "CASE WHEN length(summary)<=? THEN summary END "
                "FROM page ORDER BY created_at DESC,id DESC",
                (lab_id, lab_id, limit, offset, _SUMMARY_MAX_CHARS),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "malformed JSON" not in str(exc):
                raise
            raise ReferenceLabStoreError("stored reference-laboratory run is corrupt") from exc
    items = [_summary_item(row) for row in rows]
    return {"total": total, "offset": offset, "limit": limit, "items": items}


def list_reference_lab_sessions(repo, run_id, *, offset=0, limit=50):
    from laboratorio.storage.database import connection

    _paging(offset, limit)
    with connection(repo.path) as db:
        head = db.execute(
            "SELECT id,lab_id,contract_version,created_at,metadata_json,result_json "
            "FROM reference_lab_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if head is None:
            return None
        session_rows = db.execute(
            "SELECT ordinal,session_json FROM reference_lab_sessions WHERE run_id=? "
            "ORDER BY ordinal",
            (run_id,),
        ).fetchall()
        _decode_run(head, session_rows)
        total = len(session_rows)
        page = session_rows[offset : offset + limit]
        return {
            "run_id": run_id,
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [
                {"ordinal": ordinal, "summary": _loads(payload)} for ordinal, payload in page
            ],
        }


def delete_reference_lab_run(repo, run_id):
    from laboratorio.storage.repository import _transaction

    with _transaction(repo.path) as db:
        cursor = db.execute("DELETE FROM reference_lab_runs WHERE id=?", (run_id,))
        return cursor.rowcount > 0
