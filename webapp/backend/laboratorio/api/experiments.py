"""Experiment snapshots, bounded replay and explicit lifecycle actions."""

import json
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from laboratorio.api import StrictBody, experiment, jobs, missing, repo
from laboratorio.api.profile_views import attach_source_indices, v5_strategy_result
from laboratorio.domain.contracts import ExperimentRequest, ExperimentStatus
from laboratorio.domain.profile_request import _bad_constant, _unique_pairs, load_profile_request
from laboratorio.domain.profile_request_v2 import load_profile_cycling_request
from laboratorio.domain.profile_request_v3 import load_profile_audaz_request
from laboratorio.domain.profile_request_v4 import load_profile_recovery_request
from laboratorio.domain.session import preflight_initial_stake
from laboratorio.domain.trajectory import reduce_trajectory
from laboratorio.settings import RANKINGS_SHA256
from laboratorio.storage.quota import PendingRunsExceeded, QuotaExceeded

router = APIRouter(prefix="/experiments")
PROFILE_BODY_LIMIT = 64 * 1024


async def bounded_profile_body(request: Request) -> str:
    """Limit actual streamed bytes before parsing; Content-Length is not trusted."""
    lengths = request.headers.getlist("content-length")
    if any(value.isdecimal() and int(value) > PROFILE_BODY_LIMIT for value in lengths):
        raise HTTPException(413, "profile request exceeds 64 KiB")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > PROFILE_BODY_LIMIT:
            raise HTTPException(413, "profile request exceeds 64 KiB")
        chunks.append(chunk)
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "invalid profile JSON") from exc


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
    for index, strategy in enumerate(body.request.strategies, start=1):
        try:
            preflight_initial_stake(body.request.conditions, strategy)
        except ValueError as exc:
            raise HTTPException(400, f"strategy {index} ({strategy.name}): {exc}") from exc
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
    except PendingRunsExceeded as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, "queue is unavailable") from exc
    return {"id": identifier, "status": "pending"}


@router.post("/profiles", status_code=201)
async def create_profile(request: Request):
    """Dispatch exact profile request versions; never fall back to legacy."""
    try:
        raw = await bounded_profile_body(request)
        document = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
        if type(document) is not dict or document.get("kind") != "profile":
            raise ValueError("invalid profile kind")
        version = document.get("schema_version")
        if type(version) is not int or version not in (1, 2, 3, 4):
            raise ValueError("unsupported profile version")
        loader = (
            load_profile_request
            if version == 1
            else load_profile_cycling_request
            if version == 2
            else load_profile_audaz_request
            if version == 3
            else load_profile_recovery_request
        )
        profile_request = loader(raw)
    except (ValueError, TypeError, RecursionError) as exc:
        raise HTTPException(422, "invalid profile request") from exc
    try:
        queue = jobs(request)
        submit = (
            queue.submit_profile
            if version == 1
            else queue.submit_profile_cycling
            if version == 2
            else queue.submit_profile_audaz
            if version == 3
            else queue.submit_profile_recovery
        )
        identifier = await run_in_threadpool(submit, profile_request)
    except QuotaExceeded as exc:
        raise HTTPException(507, "profile quota has insufficient headroom") from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(409, "profile admission failed: incompatible binding or stake") from exc
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
    try:
        total, rows = repo(request).search_experiments(
            offset,
            limit,
            name_contains=name_contains,
            status=status,
            sort=sort,
            order=order,
            include_completed_cycling=True,
        )
    except ValueError as exc:
        raise HTTPException(409, "stored experiment snapshot is corrupt") from exc
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [experiment(row) for row in rows],
    }


def public_experiment(identifier: str, request: Request):
    try:
        saved = missing(repo(request).get_experiment(identifier))
        # The same projection gate applies to detail, comparison and replay.
        experiment(saved)
    except ValueError as exc:
        raise HTTPException(409, "stored experiment snapshot is corrupt") from exc
    return saved


def _v5_source_indices(saved, run, request):
    strategy = v5_strategy_result(run)
    try:
        dataset = repo(request).get_dataset(saved.request.dataset_sha256)
    except ValueError as exc:
        raise HTTPException(409, "stored profile batch source is corrupt") from exc
    admission = saved.batch_admission
    if dataset is None or admission is None:
        raise HTTPException(409, "stored profile batch source is unavailable")
    identity = admission["source_identity"]
    labels = [f"{record.date} {record.time}" for record in dataset.preview.records]
    if (
        dataset.dataset_sha256 != strategy.dataset_sha256
        or dataset.dataset_sha256 != identity["dataset_sha256"]
        or dataset.source_sha256 != identity["source_sha256"]
        or len(labels) != identity["row_count"]
        or strategy.start_draw_index >= len(labels)
        or labels[strategy.start_draw_index] != saved.request.conditions.start_draw
    ):
        raise HTTPException(409, "stored profile batch source association is corrupt")
    by_label = {label: index for index, label in enumerate(labels)}
    try:
        indices = [by_label[bet.label] for bet in strategy.session.bets]
    except KeyError as exc:
        raise HTTPException(409, "stored profile bet is outside its saved source") from exc
    if indices != sorted(set(indices)) or any(
        index < strategy.start_draw_index
        or index >= strategy.start_draw_index + strategy.session.elapsed_draws
        for index in indices
    ):
        raise HTTPException(409, "stored profile bet order is corrupt")
    return strategy, indices


@router.get("/{identifier}")
def detail(identifier: str, request: Request):
    return experiment(public_experiment(identifier, request))


@router.get("/{identifier}/runs/{ordinal}/replay")
def replay(
    identifier: str,
    ordinal: int,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    saved = public_experiment(identifier, request)
    if not 0 <= ordinal < len(saved.runs):
        raise HTTPException(404, "run not found")
    run = saved.runs[ordinal]
    result = run.result
    if result is None:
        raise HTTPException(409, "run has no completed replay")
    source_indices = None
    if run.result_schema_version == 5:
        strategy, source_indices = _v5_source_indices(saved, run, request)
        result = strategy.session
    elif run.result_schema_version in (2, 3, 4):
        result = result.session
    items = [asdict(bet) for bet in result.bets[offset : offset + limit]]
    if source_indices is not None:
        for index, item in enumerate(items, start=offset):
            item["bet_index"] = index
            item["source_index"] = source_indices[index]
    page = {
        "total": len(result.bets),
        "offset": offset,
        "limit": limit,
        "items": items,
    }
    if run.result_kind == "profile":
        page["result_kind"] = "profile"
    if run.result_schema_version in (2, 3, 4, 5):
        page["schema_version"] = run.result_schema_version
    return page


@router.get("/{identifier}/runs/{ordinal}/trajectory")
def trajectory(
    identifier: str,
    ordinal: int,
    request: Request,
    max_points: int = Query(500, ge=4, le=2000),
):
    saved = public_experiment(identifier, request)
    if not 0 <= ordinal < len(saved.runs):
        raise HTTPException(404, "run not found")
    run = saved.runs[ordinal]
    result = run.result
    if result is None:
        raise HTTPException(409, "run has no completed replay")
    source_indices = None
    if run.result_schema_version == 5:
        strategy, source_indices = _v5_source_indices(saved, run, request)
        result = strategy.session
    elif run.result_schema_version in (2, 3, 4):
        result = result.session
    response = reduce_trajectory(saved.request.conditions.capital, result.bets, max_points)
    if source_indices is not None:
        response = attach_source_indices(response, result.bets, source_indices)
    if run.result_kind == "profile":
        response["result_kind"] = "profile"
    if run.result_schema_version in (2, 3, 4, 5):
        response["schema_version"] = run.result_schema_version
    return response


@router.get("/{identifier}/compare")
def compare(identifier: str, request: Request):
    saved = public_experiment(identifier, request)
    completed = sum(run.result is not None for run in saved.runs)
    comparison = {
        "id": saved.id,
        "status": saved.status,
        "completed": completed,
        "requested": len(saved.runs),
        "complete": completed == len(saved.runs),
        "runs": experiment(saved)["runs"],
    }
    if saved.request_kind == "profile":
        comparison["request_kind"] = "profile"
    return comparison


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
