"""Bounded local upload preview and immutable promotion; no execution selection."""

import base64
import binascii
import json
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, ValidationError

from laboratorio.api import StrictBody, repo
from laboratorio.domain.contracts import GameProfile
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


@router.post("/preview")
async def preview(request: Request):
    body, raw = await _input(request, ImportBody)
    return _preview(parse_records(raw, **_options(body)))


@router.post("/promote")
async def promote(request: Request):
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
