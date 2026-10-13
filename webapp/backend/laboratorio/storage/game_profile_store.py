"""Validated immutable v2 profiles, with serialized quota admission."""

import hashlib
import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass, fields
from datetime import datetime

from laboratorio.domain.quiniela_profiles import QuinielaProfile, create_profile
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
_COLUMNS = "id,name,name_key,profile_json,profile_bytes,profile_sha256,created_at"


class GameProfileStoreError(ValueError):
    """A stored v2 profile is corrupt or cannot be safely persisted."""


class GameProfileConflict(GameProfileStoreError):
    """A case-folded display name is already used by another immutable profile."""


@dataclass(frozen=True)
class ProfileRecord:
    profile: QuinielaProfile
    sha256: str
    created_at: str

    def to_mapping(self):
        return {
            "profile": self.profile.to_mapping(),
            "sha256": self.sha256,
            "created_at": self.created_at,
        }


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

    def reject_constant(_token):
        raise ValueError("nonfinite JSON number")

    try:
        return json.loads(value, object_pairs_hook=pairs, parse_constant=reject_constant)
    except (TypeError, ValueError, RecursionError) as error:
        raise GameProfileStoreError("stored profile JSON is invalid") from error


def _canonical_identifier(identifier):
    if type(identifier) is not str:
        raise ValueError("id must be a canonical UUID")
    try:
        if str(uuid.UUID(identifier)) != identifier:
            raise ValueError("id must be a canonical UUID")
    except (ValueError, AttributeError) as error:
        raise ValueError("id must be a canonical UUID") from error


def _decode(row):
    identifier, name, name_key, snapshot, byte_count, digest, created_at = row
    try:
        if type(snapshot) is not str or type(byte_count) is not int:
            raise ValueError("invalid stored payload")
        profile = QuinielaProfile.from_mapping(_loads(snapshot))
        encoded = snapshot.encode("utf-8")
        if (
            profile.id != identifier
            or profile.name != name
            or name_key != profile.name.casefold()
            or _canonical(profile.to_mapping()) != snapshot
            or len(encoded) != byte_count
            or hashlib.sha256(encoded).hexdigest() != digest
            or type(created_at) is not str
        ):
            raise ValueError("stored profile metadata mismatch")
        parsed = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
        if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != created_at:
            raise ValueError("noncanonical creation timestamp")
        return ProfileRecord(profile, digest, created_at)
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as error:
        raise GameProfileStoreError("stored quiniela profile is corrupt") from error


def create_game_profile(repo, name, rules, *, quota_bytes=None, quota_explicit=None):
    # Revalidate through the same public codec used for persisted reads. Even a
    # trusted caller's constructed model cannot bypass the persistence boundary.
    profile = create_profile(name, rules)
    profile = QuinielaProfile.from_mapping(profile.to_mapping())
    snapshot = _canonical(profile.to_mapping())
    encoded = snapshot.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    created_at = _now_iso()
    try:
        with _transaction(repo.path) as db:
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
            status = RepositoryQuotaStatus(
                **{field.name: getattr(measured, field.name) for field in fields(QuotaStatus)},
                history_artifact_bytes=_history_artifact_bytes(db),
                run_artifact_bytes=_run_artifact_bytes(db),
                laboratory_definition_bytes=_laboratory_definition_bytes(db),
            )
            status.require_capacity(len(encoded))
            db.execute(
                "INSERT INTO quiniela_game_profiles (" + _COLUMNS + ") VALUES (?,?,?,?,?,?,?)",
                (
                    profile.id,
                    profile.name,
                    profile.name.casefold(),
                    snapshot,
                    len(encoded),
                    digest,
                    created_at,
                ),
            )
    except sqlite3.IntegrityError as error:
        if "quiniela_game_profiles.name_key" in str(error):
            raise GameProfileConflict("profile name already exists") from None
        raise GameProfileStoreError("could not store quiniela profile") from error
    return ProfileRecord(profile, digest, created_at)


def get_game_profile(repo, identifier):
    _canonical_identifier(identifier)
    with connection(repo.path) as db:
        row = db.execute(
            "SELECT " + _COLUMNS + " FROM quiniela_game_profiles WHERE id=?", (identifier,)
        ).fetchone()
    return None if row is None else _decode(row)


def list_game_profiles(repo, *, offset=0, limit=20):
    if type(offset) is not int or not 0 <= offset <= MAX_SAFE_INTEGER:
        raise ValueError("offset out of range")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit out of range")
    with connection(repo.path) as db:
        db.execute("BEGIN")
        total = db.execute("SELECT count(*) FROM quiniela_game_profiles").fetchone()[0]
        rows = db.execute(
            "SELECT " + _COLUMNS + " FROM quiniela_game_profiles "
            "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_decode(row) for row in rows],
    }
