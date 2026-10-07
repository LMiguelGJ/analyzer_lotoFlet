"""Bounded local upload preview and immutable promotion; no execution selection."""

import base64
import binascii
import json
import re
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, ValidationError

from laboratorio.api import StrictBody, repo
from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.importing.history import history_options, parse_history
from laboratorio.importing.records import (
    MAX_INPUT_BYTES,
    ClockDeclaration,
    ColumnMapping,
    SourceMetadata,
    parse_records,
)
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/imports")
StrictText = Annotated[str, Field(strict=True)]
Hash = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]


class MappingBody(StrictBody):
    date: StrictText
    time: StrictText
    positions: tuple[StrictText, ...]


class SourceBody(StrictBody):
    source_id: StrictText
    kind: Literal["historical", "artificial"]
    revision: StrictText
    provenance: StrictText


class ClockBody(StrictBody):
    mode: Literal["naive_legacy", "iana"]
    zone: StrictText | None = None


class ImportBody(StrictBody):
    raw_base64: StrictText
    format: Literal["csv", "json"]
    mapping: MappingBody
    source: SourceBody
    clock: ClockBody
    profile: GameProfile


class PromoteBody(ImportBody):
    expected_dataset_sha256: Hash


def import_mode(request: Request, *, native_mode: Literal["history"] | None = None):
    """One strict discriminator for admission and dispatch; absence is legacy-compatible."""
    values = request.headers.getlist("x-import-mode")
    if len(values) > 1 or (values and values[0] not in ("history", "records")):
        raise HTTPException(422, "invalid import mode")
    mode = values[0] if values else native_mode or "records"
    if native_mode is not None and mode != native_mode:
        raise HTTPException(422, "import mode conflicts with native history route")
    return mode


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-standard JSON constant")


async def _input(request: Request, model):
    try:
        document = json.loads(
            await request.body(), object_pairs_hook=_object, parse_constant=_reject_constant
        )
        body = model.model_validate(document)
        raw = base64.b64decode(body.raw_base64, validate=True)
        if base64.b64encode(raw).decode("ascii") != body.raw_base64:
            raise ValueError("non-canonical base64")
    except (ValueError, ValidationError, RecursionError, UnicodeError, binascii.Error) as exc:
        raise HTTPException(422, "invalid import request") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise HTTPException(413, "decoded import exceeds 2 MiB")
    return body, raw


def _options(body):
    return {
        "format": body.format,
        "mapping": ColumnMapping(body.mapping.date, body.mapping.time, body.mapping.positions),
        "source": SourceMetadata(**body.source.model_dump()),
        "clock": ClockDeclaration(**body.clock.model_dump()),
        "profile": body.profile,
    }


def _preview(result):
    return {
        "promotable": result.promotable,
        "source_sha256": result.source_sha256,
        "dataset_sha256": result.dataset_sha256,
        "rows_seen": result.rows_seen,
        "records_total": len(result.records),
        "duplicates_merged": result.duplicates_merged,
        "error_count": result.error_count,
        "errors_truncated": result.errors_truncated,
        "errors": [asdict(error) for error in result.errors],
        "sample": [asdict(record) for record in result.records[:20]],
        "execution_supported": False,
    }


def _history_context(request: Request, raw: bytes):
    profile_id = request.headers.get("x-profile-id", "")
    revision_text = request.headers.get("x-profile-revision", "")
    if not profile_id or not revision_text.isdecimal():
        raise HTTPException(422, "registered profile identity headers are required")
    try:
        profile = repo(request).get_game_profile(profile_id, int(revision_text))
    except (ValueError, TypeError):
        profile = None
    if profile is None:
        raise HTTPException(422, "registered profile identity was not found")
    supplied_profile_hash = request.headers.get("x-profile-sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", supplied_profile_hash):
        raise HTTPException(422, "registered profile hash header is required")
    if supplied_profile_hash != profile_sha256(profile):
        raise HTTPException(409, "registered profile hash does not match identity")
    try:
        document = json.loads(raw, object_pairs_hook=_object, parse_constant=_reject_constant)
        context = history_options(document, profile)
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as exc:
        raise HTTPException(422, "invalid canonical history document") from exc
    metadata = document["metadata"]
    if request.headers.get("x-confirm-source") != metadata.get("origen"):
        raise HTTPException(409, "explicit source confirmation must match metadata origin")
    if request.headers.get("x-confirm-timezone") != metadata.get("zona_horaria"):
        raise HTTPException(409, "explicit timezone confirmation must match metadata")
    return profile, context


def _history_preview(result, profile):
    return {
        **_preview(result),
        "profile_compatibility": {
            "profile_id": profile.profile_id,
            "profile_revision": profile.revision,
            "profile_sha256": profile_sha256(profile),
            "registered": True,
            "execution_supported": False,
            "rules_source": "registered_game_profile",
        },
    }


@router.post("/history/preview")
async def history_preview(request: Request):
    import_mode(request, native_mode="history")
    raw = await request.body()
    profile, _context = _history_context(request, raw)
    return _history_preview(parse_history(raw, profile), profile)


@router.post("/history/promote")
async def history_promote(request: Request):
    import_mode(request, native_mode="history")
    raw = await request.body()
    profile, context = _history_context(request, raw)
    result = parse_history(raw, profile)
    if not result.promotable or result.dataset_sha256 is None:
        raise HTTPException(422, "history is not promotable")
    expected = request.headers.get("x-expected-dataset-sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or expected != result.dataset_sha256:
        raise HTTPException(409, "dataset hash does not match preview")
    settings = request.app.state.settings
    try:
        saved = repo(request).promote_dataset(
            raw,
            **context,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
    except QuotaExceeded as exc:
        raise HTTPException(409, "dataset quota has insufficient headroom") from exc
    except ValueError as exc:
        raise HTTPException(409, "dataset integrity or source changed") from exc
    return {
        "dataset_sha256": saved.dataset.dataset_sha256,
        "created_at": saved.dataset.created_at,
        "created": saved.created,
        "duplicate_source_differs": saved.duplicate_source_differs,
        "retained_source_sha256": saved.dataset.source_sha256,
        "submitted_source_sha256": saved.submitted_source_sha256,
        "rows_seen": result.rows_seen,
        "records_total": len(result.records),
        "duplicates_merged": result.duplicates_merged,
        "profile_compatibility": _history_preview(result, profile)["profile_compatibility"],
        "execution_supported": False,
    }


@router.post("/preview")
async def preview(request: Request):
    if import_mode(request) == "history":
        return await history_preview(request)
    body, raw = await _input(request, ImportBody)
    return _preview(parse_records(raw, **_options(body)))


@router.post("/promote")
async def promote(request: Request):
    if import_mode(request) == "history":
        return await history_promote(request)
    body, raw = await _input(request, PromoteBody)
    options = _options(body)
    result = parse_records(raw, **options)
    if not result.promotable:
        raise HTTPException(422, "dataset source is not promotable")
    if result.dataset_sha256 != body.expected_dataset_sha256:
        raise HTTPException(409, "dataset hash does not match preview")
    settings = request.app.state.settings
    try:
        saved = repo(request).promote_dataset(
            raw,
            **options,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
    except QuotaExceeded as exc:
        raise HTTPException(409, "dataset quota has insufficient headroom") from exc
    except ValueError as exc:
        # Includes an unexpected stored integrity failure. Never echo stored bytes/context.
        raise HTTPException(409, "dataset integrity or source changed") from exc
    return {
        "dataset_sha256": saved.dataset.dataset_sha256,
        "created_at": saved.dataset.created_at,
        "created": saved.created,
        "duplicate_source_differs": saved.duplicate_source_differs,
        "retained_source_sha256": saved.dataset.source_sha256,
        "submitted_source_sha256": saved.submitted_source_sha256,
        "rows_seen": result.rows_seen,
        "records_total": len(result.records),
        "duplicates_merged": result.duplicates_merged,
        "execution_supported": False,
    }
