"""Strict immutable library API; definitions are not an execution dispatch."""

import json

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ConfigDict

from laboratorio.api import StrictBody, repo
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.strategy_library import compatibility_projection, strategy_payload
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/strategies")


class StrategyBody(StrictBody):
    model_config = ConfigDict(extra="forbid", strict=True)
    definition: dict


class RevisionBody(StrategyBody):
    expected_latest_revision: int


def _item(saved, profile=None):
    if saved is None:
        raise HTTPException(404, "resource not found")
    projection = compatibility_projection(
        saved["definition"],
        profile,
        reference_preset_id=saved["id"] if saved["protected"] else None,
    )
    execution_available = profile is not None and bool(projection["profile_compatible"])
    projection["execution_available"] = execution_available
    if execution_available:
        projection["execution_unavailable_reason"] = None
    try:
        definition_wire = json.loads(saved["definition_json"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(409, "corrupt stored strategy snapshot") from exc
    return {
        "id": saved["id"],
        "name": saved["name"],
        "revision": saved["revision"],
        "latest_revision": saved["latest_revision"],
        "definition_version": saved["definition_version"],
        "definition": definition_wire,
        "definition_sha256": saved["definition_sha256"],
        "created_at": saved["created_at"],
        "revision_created_at": saved["revision_created_at"],
        "protected": saved["protected"],
        "preset_explanation": saved["preset_explanation"],
        **projection,
    }


def _profile_context(repository, profile_id, profile_revision, expected_sha256):
    if profile_id is None and profile_revision is None and expected_sha256 is None:
        return None
    if profile_id is None or profile_revision is None or expected_sha256 is None:
        raise HTTPException(
            422, "profile_id, profile_revision and profile_sha256 are required together"
        )
    try:
        profile = repository.get_game_profile(profile_id, profile_revision)
    except ValueError as exc:
        raise HTTPException(409, "corrupt stored profile") from exc
    if profile is None:
        raise HTTPException(404, "registered profile revision not found")
    if profile_sha256(profile) != expected_sha256:
        raise HTTPException(409, "registered profile identity hash mismatch")
    return profile


@router.post("", status_code=201)
def create(body: StrategyBody, request: Request):
    try:
        definition = strategy_payload(body.definition)
        saved = repo(request).create_strategy(
            definition,
            quota_bytes=request.app.state.settings.quota_bytes
            if hasattr(request.app.state, "settings")
            else None,
            quota_explicit=request.app.state.settings.is_quota_explicit
            if hasattr(request.app.state, "settings")
            else None,
        )
    except QuotaExceeded as exc:
        raise HTTPException(507, str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return _item(saved)


@router.get("")
def list_all(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        total, rows = repo(request).page_strategies(offset, limit)
        items = [_item(row) for row in rows]
    except ValueError as exc:
        raise HTTPException(409, "corrupt stored strategy") from exc
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
    }


@router.get("/{identifier}/revisions")
def revisions(
    identifier: str,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    repository = repo(request)
    if offset < 0 or limit < 1 or limit > 100:
        raise HTTPException(422, "offset and limit out of range")
    try:
        head = repository.get_strategy(identifier)
        if head is None:
            raise HTTPException(404, "resource not found")
        start = max(1, head["latest_revision"] - offset - limit + 1)
        stop = head["latest_revision"] - offset
        values = [
            repository.get_strategy_revision(identifier, revision)
            for revision in range(stop, start - 1, -1)
        ]
        values = [value for value in values if value is not None]
        items = [_item(value) for value in values]
    except ValueError as exc:
        raise HTTPException(409, "corrupt stored strategy") from exc
    return {
        "total": head["latest_revision"],
        "offset": offset,
        "limit": limit,
        "items": items,
    }


@router.get("/{identifier}")
def detail(
    identifier: str,
    request: Request,
    profile_id: str | None = None,
    profile_revision: int | None = Query(None, ge=1),
    profile_sha256: str | None = None,
):
    repository = repo(request)
    try:
        profile = _profile_context(repository, profile_id, profile_revision, profile_sha256)
        return _item(repository.get_strategy(identifier), profile)
    except ValueError as exc:
        raise HTTPException(409, "corrupt stored strategy or profile") from exc


@router.post("/{identifier}/revisions", status_code=201)
def revise(identifier: str, body: RevisionBody, request: Request):
    try:
        definition = strategy_payload(body.definition)
        saved = repo(request).append_strategy_revision(
            identifier,
            body.expected_latest_revision,
            definition,
            quota_bytes=request.app.state.settings.quota_bytes
            if hasattr(request.app.state, "settings")
            else None,
            quota_explicit=request.app.state.settings.is_quota_explicit
            if hasattr(request.app.state, "settings")
            else None,
        )
    except KeyError as exc:
        raise HTTPException(404, "resource not found") from exc
    except QuotaExceeded as exc:
        raise HTTPException(507, str(exc)) from exc
    except ValueError as exc:
        status_code = 409 if "conflict" in str(exc) or "protected" in str(exc) else 422
        raise HTTPException(status_code, str(exc)) from exc
    return _item(saved)
