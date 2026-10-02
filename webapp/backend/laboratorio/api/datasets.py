"""Bounded, verified metadata and draw-label discovery for imported datasets."""

import json
from bisect import bisect_left
from datetime import date as calendar_date

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import ValidationError

from laboratorio.api.catalog import profile_execution
from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_request import profile_sha256

router = APIRouter(prefix="/datasets")


def _metadata(request: Request, saved, *, include_profile: bool):
    # Repository has already verified the raw source and canonical context. Decode
    # the canonical envelope only once here; never return its records or provenance.
    try:
        snapshot = json.loads(saved.canonical_json)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid dataset context") from exc
    profile = GameProfile.model_validate(snapshot["profile"])
    digest = profile_sha256(profile)
    registered = request.app.state.repo.get_game_profile(profile.profile_id, profile.revision)
    ready = registered is not None and profile_sha256(registered) == digest
    records = saved.preview.records
    item = {
        "dataset_sha256": saved.dataset_sha256,
        "source_sha256": saved.source_sha256,
        "created_at": saved.created_at,
        "source_id": snapshot["source"]["source_id"],
        "source_kind": snapshot["source"]["kind"],
        "source_revision": snapshot["source"]["revision"],
        "profile_id": profile.profile_id,
        "profile_revision": profile.revision,
        "profile_sha256": digest,
        "positions": profile.positions,
        "universe_size": profile.universe_size,
        "records_total": len(records),
        "first_draw": f"{records[0].date} {records[0].time}",
        "last_draw": f"{records[-1].date} {records[-1].time}",
        "clock": snapshot["clock"],
        "execution_supported": False,  # legacy flag, not profile-engine readiness
        "profile_execution": profile_execution(ready),
    }
    if include_profile:
        item["profile"] = profile.model_dump(mode="json")
    return item


def _verified_dataset(request: Request, digest: str):
    try:
        saved = request.app.state.repo.get_dataset(digest)
    except (ValueError, TypeError) as exc:
        raise HTTPException(409, "dataset integrity check failed") from exc
    if saved is None:
        raise HTTPException(404, "dataset not found")
    return saved


@router.get("")
def datasets(request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    try:
        total, rows = request.app.state.repo.page_datasets(offset, limit)
        items = [_metadata(request, saved, include_profile=False) for saved in rows]
    except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
        raise HTTPException(409, "dataset integrity check failed") from exc
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@router.get("/{sha256}")
def dataset_detail(request: Request, sha256: str = Path(pattern=r"^[0-9a-f]{64}$")):
    saved = _verified_dataset(request, sha256)
    try:
        return _metadata(request, saved, include_profile=True)
    except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
        raise HTTPException(409, "dataset integrity check failed") from exc


@router.get("/{sha256}/draws")
def dataset_draws(
    request: Request,
    sha256: str = Path(pattern=r"^[0-9a-f]{64}$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    draw_date: str | None = Query(None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    if draw_date is not None:
        try:
            calendar_date.fromisoformat(draw_date)
        except ValueError as exc:
            raise HTTPException(422, "invalid ISO calendar date") from exc
    saved = _verified_dataset(request, sha256)
    # The verified preview contains at most 10,000 sorted records from a 2 MiB source.
    # No separate ranking filter applies: all imported rows are eligible start draws.
    labels = [f"{record.date} {record.time}" for record in saved.preview.records]
    first, end = 0, len(labels)
    if draw_date is not None:
        first = bisect_left(labels, f"{draw_date} ")
        end = bisect_left(labels, f"{draw_date} 24:00")
    return {
        "total": end - first,
        "offset": offset,
        "limit": limit,
        "items": labels[first + offset : min(first + offset + limit, end)],
    }
