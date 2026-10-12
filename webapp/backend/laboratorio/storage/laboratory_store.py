"""Validated persistence for immutable manual laboratory definitions."""

import json
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime

from laboratorio.domain.laboratories import LaboratoryDefinition
from laboratorio.domain.laboratories import (
    create_laboratory_definition as _create_laboratory_definition,
)
from laboratorio.storage.database import connection
from laboratorio.storage.quota import QuotaStatus, measure, validate_quota_bytes

_MAX_I64 = 2**63 - 1


class LaboratoryStoreError(ValueError):
    """Invalid or corrupt laboratory-definition storage data."""


class LaboratoryDefinitionConflict(LaboratoryStoreError):
    """A definition name conflicts with an existing case-folded name."""


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


def _paging(offset, limit):
    if type(offset) is not int or not 0 <= offset <= _MAX_I64:
        raise ValueError("offset out of range")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit out of range")


def _created_at_valid(value):
    if type(value) is not str:
        raise ValueError
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    if parsed.utcoffset() is None:
        raise ValueError


def _decode(row):
    identifier, name, name_key, snapshot, byte_count, created_at = row
    try:
        if type(snapshot) is not str or type(byte_count) is not int:
            raise ValueError
        definition = LaboratoryDefinition.from_mapping(_loads(snapshot))
        if (
            definition.id != identifier
            or definition.name != name
            or type(name_key) is not str
            or name_key != definition.name.casefold()
            or _canonical(definition.to_mapping()) != snapshot
            or len(snapshot.encode("utf-8")) != byte_count
        ):
            raise ValueError
        _created_at_valid(created_at)
        return definition
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
        raise LaboratoryStoreError("stored laboratory definition is corrupt") from exc


def _row(db, identifier):
    return db.execute(
        "SELECT id,name,name_key,definition_json,definition_bytes,created_at "
        "FROM laboratory_definitions WHERE id=?",
        (identifier,),
    ).fetchone()


def create_laboratory_definition(repo, name, config, *, quota_bytes=None, quota_explicit=None):
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

    definition = _create_laboratory_definition(name, config)
    # Exercise the same strict v1 snapshot codec used by persisted reads.
    definition = LaboratoryDefinition.from_mapping(definition.to_mapping())
    snapshot = _canonical(definition.to_mapping())
    payload_bytes = len(snapshot.encode("utf-8"))
    effective = repo.effective_quota(quota_bytes, quota_explicit=quota_explicit)
    limit = validate_quota_bytes(effective.effective_bytes)
    created_at = _now_iso()
    try:
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
                **{item.name: getattr(base, item.name) for item in fields(QuotaStatus)},
                history_artifact_bytes=_history_artifact_bytes(db),
                run_artifact_bytes=_run_artifact_bytes(db),
                laboratory_definition_bytes=_laboratory_definition_bytes(db),
            )
            status.require_capacity(payload_bytes)
            db.execute(
                "INSERT INTO laboratory_definitions "
                "(id,name,name_key,definition_json,definition_bytes,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    definition.id,
                    definition.name,
                    definition.name.casefold(),
                    snapshot,
                    payload_bytes,
                    created_at,
                ),
            )
    except sqlite3.IntegrityError as exc:
        if "laboratory_definitions.name_key" in str(exc):
            raise LaboratoryDefinitionConflict("laboratory name already exists") from None
        raise LaboratoryStoreError("could not store laboratory definition") from None
    return definition


def get_laboratory_definition(repo, identifier):
    if type(identifier) is not str:
        raise ValueError("id must be a canonical UUID")
    try:
        if str(uuid.UUID(identifier)) != identifier:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise ValueError("id must be a canonical UUID") from exc
    with connection(repo.path) as db:
        row = _row(db, identifier)
    return None if row is None else _decode(row)


def list_laboratory_definitions(repo, *, offset=0, limit=20):
    _paging(offset, limit)
    with connection(repo.path) as db:
        db.execute("BEGIN")
        total = db.execute("SELECT count(*) FROM laboratory_definitions").fetchone()[0]
        rows = db.execute(
            "SELECT id,name,name_key,definition_json,definition_bytes,created_at "
            "FROM laboratory_definitions ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_decode(row) for row in rows],
    }
