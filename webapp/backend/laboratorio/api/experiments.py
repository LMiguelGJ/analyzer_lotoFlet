"""Experiment snapshots, bounded replay and explicit lifecycle actions."""

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from laboratorio.api import StrictBody, experiment, jobs, missing, repo
from laboratorio.domain.contracts import ExperimentRequest, ExperimentStatus
from laboratorio.settings import RANKINGS_SHA256
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/experiments")


class CreateExperiment(StrictBody):
    request: ExperimentRequest
    configuration_ids: tuple[str | None, ...] | None = None


class ConfirmDelete(StrictBody):
    confirm_id: str


@router.post("", status_code=201)
def create(body: CreateExperiment, request: Request):
    data = request.app.state.data
    if body.request.conditions.start_draw not in {
        data.history.labels[int(index)] for index in data.rankings.row_ids
    }:
        raise HTTPException(400, "start draw has no ranking")
    settings = request.app.state.settings
    try:
        identifier = jobs(request).submit(
            body.request,
            history_id=settings.history_path.name,
            history_sha256=data.history.sha256,
            rankings_id=settings.rankings_path.name,
            rankings_sha256=RANKINGS_SHA256,
            code_version=request.app.version,
            configuration_ids=body.configuration_ids,
        )
    except QuotaExceeded as exc:
        raise HTTPException(507, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, "queue is unavailable") from exc
    return {"id": identifier, "status": "pending"}


@router.get("")
def list_all(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    name_contains: str | None = Query(None, max_length=80),
    status: ExperimentStatus | None = None,
    sort: Literal["created_at", "name", "status"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
):
    total, rows = repo(request).search_experiments(
        offset, limit, name_contains=name_contains, status=status, sort=sort, order=order
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [experiment(row) for row in rows],
    }


@router.get("/{identifier}")
def detail(identifier: str, request: Request):
    return experiment(missing(repo(request).get_experiment(identifier)))


@router.get("/{identifier}/runs/{ordinal}/replay")
def replay(
    identifier: str,
    ordinal: int,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    saved = missing(repo(request).get_experiment(identifier))
    if not 0 <= ordinal < len(saved.runs):
        raise HTTPException(404, "run not found")
    result = saved.runs[ordinal].result
    if result is None:
        raise HTTPException(409, "run has no completed replay")
    return {
        "total": len(result.bets),
        "offset": offset,
        "limit": limit,
        "items": [asdict(bet) for bet in result.bets[offset : offset + limit]],
    }


@router.get("/{identifier}/compare")
def compare(identifier: str, request: Request):
    saved = missing(repo(request).get_experiment(identifier))
    completed = sum(run.result is not None for run in saved.runs)
    return {
        "id": saved.id,
        "status": saved.status,
        "completed": completed,
        "requested": len(saved.runs),
        "complete": completed == len(saved.runs),
        "runs": experiment(saved)["runs"],
    }


@router.delete("/{identifier}", status_code=204)
def delete(identifier: str, body: ConfirmDelete, request: Request):
    if body.confirm_id != identifier:
        raise HTTPException(400, "confirmation must match experiment id")
    try:
        if not jobs(request).delete_experiment(identifier):
            raise HTTPException(404, "resource not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, "queue is unavailable") from exc
