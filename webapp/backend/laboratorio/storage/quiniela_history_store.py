"""Atomic quota admission and verified reads for immutable v2 history sources."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass, fields
from datetime import datetime

from laboratorio.domain.configurable_laboratories import SourceReference
from laboratorio.domain.quiniela_profiles import QuinielaProfile
from laboratorio.engine.quiniela_import import (
    MAX_INPUT_ROWS,
    MAX_RAW_BYTES,
    HistoryPreview,
    preview_history,
    preview_included_history,
    source_reference,
)
from laboratorio.settings import HISTORY_SHA256
from laboratorio.storage.database import connection
from laboratorio.storage.quota import QuotaStatus, measure, validate_quota_bytes
from laboratorio.storage.repository import (
    RepositoryQuotaStatus,
    _dataset_artifact_bytes,
    _effective_quota,
    _history_artifact_bytes,
    _laboratory_definition_bytes,
    _logical_experiment_bytes,
    _now_iso,
    _profile_artifact_bytes,
    _run_artifact_bytes,
    _strategy_artifact_bytes,
    _transaction,
)

MAX_SAFE_INTEGER = 2**53 - 1
_SELECT_SOURCE_BY_ID = (
    "SELECT id,profile_id,profile_sha256,origin,name,raw_sha256,canonical_sha256,"
    "preview_sha256,raw_bytes,canonical_json,source_bytes,timezone,timezone_confirmed,"
    "draws,duplicates,first_timestamp,last_timestamp,created_at "
    "FROM quiniela_history_sources WHERE id=?"
)
_SELECT_SOURCE_BY_PREVIEW = (
    "SELECT id,profile_id,profile_sha256,origin,name,raw_sha256,canonical_sha256,"
    "preview_sha256,raw_bytes,canonical_json,source_bytes,timezone,timezone_confirmed,"
    "draws,duplicates,first_timestamp,last_timestamp,created_at "
    "FROM quiniela_history_sources WHERE preview_sha256=?"
)
_SELECT_SOURCE_IDS = (
    "SELECT id FROM quiniela_history_sources ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?"
)
_SELECT_PROFILE_SOURCE_IDS = (
    "SELECT id FROM quiniela_history_sources WHERE profile_id=? "
    "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?"
)


class HistorySourceStoreError(ValueError):
    """Stored history bytes, metadata, or canonical digest failed verification."""


class HistorySourceConflict(HistorySourceStoreError):
    """A confirmed immutable source identity conflicts with stored data."""


class HistorySourceQuotaExceeded(RuntimeError):
    """No history source was written because the atomic quota check failed."""


@dataclass(frozen=True, slots=True)
class HistorySourceRecord:
    reference: SourceReference
    preview_sha256: str
    profile_id: str
    name: str
    timezone: str
    timezone_confirmed: bool
    draw_count: int
    duplicate_count: int
    first_timestamp: str | None
    last_timestamp: str | None
    created_at: str
    raw_bytes: bytes
    canonical_json: str
    draws: tuple

    def to_mapping(self, *, include_sample=True):
        result = {
            "source": self.reference.to_mapping(),
            "preview_sha256": self.preview_sha256,
            "profile_id": self.profile_id,
            "name": self.name,
            "timezone": self.timezone,
            "timezone_confirmed": self.timezone_confirmed,
            "input_rows": self.draw_count + self.duplicate_count,
            "draw_count": self.draw_count,
            "duplicate_count": self.duplicate_count,
            "max_raw_bytes": MAX_RAW_BYTES,
            "max_input_rows": MAX_INPUT_ROWS,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "created_at": self.created_at,
        }
        if include_sample:
            result["sample"] = [item.to_mapping() for item in self.draws[:3]]
        return result


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _parse_timestamp(value):
    if type(value) is not str:
        raise ValueError("creation time is not text")
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value:
        raise ValueError("creation time is not canonical")
    return value


def _validate_record(row, profile_row):
    (
        identifier,
        profile_id,
        profile_sha,
        origin,
        name,
        raw_sha,
        canonical_sha,
        preview_sha,
        raw,
        canonical_json,
        source_bytes,
        timezone,
        confirmed,
        count,
        duplicates,
        first,
        last,
        created_at,
    ) = row
    try:
        if type(raw) is not bytes or type(canonical_json) is not str:
            raise ValueError("invalid source payload type")
        if origin == "included" and raw_sha != HISTORY_SHA256:
            raise ValueError("included source does not match the frozen input hash")
        encoded = canonical_json.encode("utf-8")
        if type(source_bytes) is not int or source_bytes != len(raw) + len(encoded):
            raise ValueError("stored source byte count mismatch")
        if hashlib.sha256(raw).hexdigest() != raw_sha:
            raise ValueError("stored raw source hash mismatch")
        if hashlib.sha256(encoded).hexdigest() != canonical_sha:
            raise ValueError("stored canonical hash mismatch")
        profile_json, profile_bytes, stored_profile_sha = profile_row
        profile_encoded = profile_json.encode("utf-8")
        if (
            type(profile_bytes) is not int
            or len(profile_encoded) != profile_bytes
            or hashlib.sha256(profile_encoded).hexdigest() != stored_profile_sha
            or stored_profile_sha != profile_sha
        ):
            raise ValueError("stored profile binding mismatch")
        profile_value = json.loads(profile_json)
        profile = QuinielaProfile.from_mapping(profile_value)
        if _canonical(profile.to_mapping()) != profile_json or profile.id != profile_id:
            raise ValueError("stored profile snapshot is noncanonical")
        if origin == "included":
            preview = preview_included_history(raw, profile, name=name)
        else:
            preview = preview_history(
                raw,
                profile,
                name=name,
                origin=origin,
                timezone=timezone,
                timezone_confirmed=bool(confirmed),
            )
        if (
            preview.preview_sha256 != preview_sha
            or preview.canonical_sha256 != canonical_sha
            or preview.canonical_json != canonical_json
            or preview.draw_count != count
            or preview.duplicate_count != duplicates
            or preview.first_timestamp != first
            or preview.last_timestamp != last
            or type(confirmed) is not int
            or confirmed not in (0, 1)
            or origin not in ("included", "imported")
        ):
            raise ValueError("stored source metadata does not match recomputed preview")
        reference = source_reference(preview, identifier)
        return HistorySourceRecord(
            reference,
            preview_sha,
            profile_id,
            name,
            timezone,
            bool(confirmed),
            count,
            duplicates,
            first,
            last,
            _parse_timestamp(created_at),
            raw,
            canonical_json,
            preview.draws,
        )
    except (
        TypeError,
        ValueError,
        KeyError,
        OverflowError,
        RecursionError,
        json.JSONDecodeError,
    ) as error:
        raise HistorySourceStoreError("stored quiniela history source is corrupt") from error


def _record(db, identifier):
    row = db.execute(_SELECT_SOURCE_BY_ID, (identifier,)).fetchone()
    if row is None:
        return None
    profile_row = db.execute(
        "SELECT profile_json, profile_bytes, profile_sha256 FROM quiniela_game_profiles WHERE id=?",
        (row[1],),
    ).fetchone()
    if profile_row is None:
        raise HistorySourceStoreError("stored history references a missing profile")
    return _validate_record(row, profile_row)


def _quota_status(db, repo, quota_bytes, quota_explicit):
    effective = _effective_quota(db, quota_bytes, quota_explicit)
    limit = validate_quota_bytes(effective.effective_bytes)
    measured = measure(
        repo.path,
        limit,
        _logical_experiment_bytes(db),
        profile_artifact_bytes=_profile_artifact_bytes(db),
        dataset_artifact_bytes=_dataset_artifact_bytes(db),
        strategy_artifact_bytes=_strategy_artifact_bytes(db),
        disk_usage=shutil.disk_usage,
    )
    return RepositoryQuotaStatus(
        **{item.name: getattr(measured, item.name) for item in fields(QuotaStatus)},
        history_artifact_bytes=_history_artifact_bytes(db),
        run_artifact_bytes=_run_artifact_bytes(db),
        laboratory_definition_bytes=_laboratory_definition_bytes(db),
    )


def confirm_history_source(
    repo,
    preview: HistoryPreview,
    *,
    quota_bytes=None,
    quota_explicit=None,
):
    """Reparse the bound bytes and admit once within the serialized writer transaction."""
    if not isinstance(preview, HistoryPreview):
        raise TypeError("preview must be a validated HistoryPreview")
    with _transaction(repo.path) as db:
        profile_row = db.execute(
            "SELECT profile_json, profile_bytes, profile_sha256 "
            "FROM quiniela_game_profiles WHERE id=?",
            (preview.profile_id,),
        ).fetchone()
        if profile_row is None:
            raise HistorySourceConflict("selected profile no longer exists")
        profile_json, profile_bytes, profile_sha = profile_row
        if preview.origin == "included" and preview.raw_sha256 != HISTORY_SHA256:
            raise HistorySourceConflict("included input no longer matches the frozen hash")
        if (
            len(profile_json.encode("utf-8")) != profile_bytes
            or hashlib.sha256(profile_json.encode("utf-8")).hexdigest() != profile_sha
            or profile_sha != preview.profile_sha256
        ):
            raise HistorySourceConflict("selected profile changed after preview")
        try:
            profile = QuinielaProfile.from_mapping(json.loads(profile_json))
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError) as error:
            raise HistorySourceConflict("selected profile is corrupt") from error
        if preview.origin == "included":
            verified = preview_included_history(preview.raw_bytes, profile, name=preview.name)
        else:
            verified = preview_history(
                preview.raw_bytes,
                profile,
                name=preview.name,
                origin=preview.origin,
                timezone=preview.timezone,
                timezone_confirmed=preview.timezone_confirmed,
            )
        if verified != preview:
            raise HistorySourceConflict("preview identity or raw hash changed")
        existing = db.execute(
            _SELECT_SOURCE_BY_PREVIEW,
            (preview.preview_sha256,),
        ).fetchone()
        if existing is not None:
            record = _validate_record(existing, profile_row)
            return record, False
        status = _quota_status(db, repo, quota_bytes, quota_explicit)
        source_bytes = len(preview.raw_bytes) + len(preview.canonical_json.encode("utf-8"))
        identifier = str(uuid.uuid4())
        created_at = _now_iso()
        status.require_capacity(
            source_bytes + len(identifier.encode()) + len(preview.name.encode()) + 384
        )
        db.execute(
            "INSERT INTO quiniela_history_sources "
            "(id,profile_id,profile_sha256,origin,name,raw_sha256,canonical_sha256,"
            "preview_sha256,raw_bytes,canonical_json,source_bytes,timezone,timezone_confirmed,"
            "draws,duplicates,first_timestamp,last_timestamp,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                preview.profile_id,
                preview.profile_sha256,
                preview.origin,
                preview.name,
                preview.raw_sha256,
                preview.canonical_sha256,
                preview.preview_sha256,
                preview.raw_bytes,
                preview.canonical_json,
                source_bytes,
                preview.timezone,
                int(preview.timezone_confirmed),
                preview.draw_count,
                preview.duplicate_count,
                preview.first_timestamp,
                preview.last_timestamp,
                created_at,
            ),
        )
        record = _record(db, identifier)
        return record, True


def list_history_sources(repo, *, offset=0, limit=20, profile_id=None):
    if type(offset) is not int or not 0 <= offset <= MAX_SAFE_INTEGER:
        raise ValueError("offset out of range")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit out of range")
    with connection(repo.path) as db:
        db.execute("BEGIN")
        if profile_id is None:
            total = db.execute("SELECT count(*) FROM quiniela_history_sources").fetchone()[0]
            identifiers = db.execute(_SELECT_SOURCE_IDS, (limit, offset)).fetchall()
        else:
            total = db.execute(
                "SELECT count(*) FROM quiniela_history_sources WHERE profile_id=?",
                (profile_id,),
            ).fetchone()[0]
            identifiers = db.execute(
                _SELECT_PROFILE_SOURCE_IDS, (profile_id, limit, offset)
            ).fetchall()
        items = []
        for (identifier,) in identifiers:
            record = _record(db, identifier)
            if record is None:
                raise HistorySourceStoreError("history source disappeared during page read")
            items.append(record.to_mapping())
    return {"total": total, "offset": offset, "limit": limit, "items": items}


def get_history_source(repo, identifier):
    try:
        if type(identifier) is not str or str(uuid.UUID(identifier)) != identifier:
            raise ValueError("id must be a canonical UUID")
    except (ValueError, AttributeError) as error:
        raise ValueError("id must be a canonical UUID") from error
    with connection(repo.path) as db:
        return _record(db, identifier)
