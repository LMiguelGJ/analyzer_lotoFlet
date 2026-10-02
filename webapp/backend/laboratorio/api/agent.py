"""Fixed allowlist facade over the application's existing API services."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response

from laboratorio.api import (
    catalog,
    datasets,
    experiments,
    imports,
    profile_batches,
    queue,
    strategies,
)


def bearer_authorized(values: list[str], expected: str | None) -> bool:
    """Accept exactly one well-formed ASCII Bearer value, comparing bytes safely."""
    if len(values) != 1 or not isinstance(expected, str):
        return False
    supplied = values[0]
    try:
        supplied.encode("ascii")
        expected_bytes = expected.encode("ascii")
    except UnicodeEncodeError:
        return False
    scheme, separator, credential = supplied.partition(" ")
    if (
        scheme.lower() != "bearer"
        or not separator
        or not credential
        or credential != credential.strip()
        or any(character.isspace() for character in credential)
    ):
        return False
    return secrets.compare_digest(credential.encode("ascii"), expected_bytes)


def _require_bearer(request: Request):
    expected = getattr(request.app.state, "agent_token", None)
    if not bearer_authorized(request.headers.getlist("authorization"), expected):
        raise HTTPException(401, "agent authentication required")


router = APIRouter(prefix="/agent/v1", dependencies=[Depends(_require_bearer)])


@router.get("/catalog")
def read_catalog(request: Request):
    return catalog.read_catalog(request)


@router.get("/starting-draws")
def starting_draws(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    return catalog.starting_draws(request, offset, limit, date)


@router.get("/profiles")
def list_profiles(
    request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
):
    return catalog.profiles(request, offset, limit)


@router.get("/profiles/{identifier}/revisions/{revision}")
def profile_detail(identifier: str, revision: int, request: Request):
    if revision < 1:
        raise HTTPException(422, "profile revision must be positive")
    try:
        profile = request.app.state.repo.get_game_profile(identifier, revision)
    except ValueError as exc:
        raise HTTPException(409, "corrupt stored profile") from exc
    if profile is None:
        raise HTTPException(404, "resource not found")
    return catalog._profile_item(profile)


@router.get("/datasets")
def list_datasets(
    request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
):
    return datasets.datasets(request, offset, limit)


@router.get("/datasets/{sha256}")
def dataset_detail(request: Request, sha256: str = Path(pattern=r"^[0-9a-f]{64}$")):
    return datasets.dataset_detail(request, sha256)


@router.get("/datasets/{sha256}/draws")
def dataset_draws(
    request: Request,
    sha256: str = Path(pattern=r"^[0-9a-f]{64}$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    return datasets.dataset_draws(request, sha256, offset, limit, date)


@router.get("/strategies")
def list_strategies(
    request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
):
    return strategies.list_all(request, offset, limit)


@router.post("/strategies", status_code=201)
def create_strategy(body: strategies.StrategyBody, request: Request):
    return strategies.create(body, request)


@router.get("/strategies/{identifier}")
def strategy_detail(
    identifier: str,
    request: Request,
    profile_id: str | None = None,
    profile_revision: int | None = Query(None, ge=1),
    profile_sha256: str | None = None,
):
    return strategies.detail(identifier, request, profile_id, profile_revision, profile_sha256)


@router.get("/strategies/{identifier}/revisions")
def strategy_revisions(
    identifier: str,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return strategies.revisions(identifier, request, offset, limit)


@router.get("/strategies/{identifier}/revisions/{revision}")
def strategy_revision(identifier: str, revision: int, request: Request):
    if revision < 1:
        raise HTTPException(422, "strategy revision must be positive")
    try:
        saved = request.app.state.repo.get_strategy_revision(identifier, revision)
    except ValueError as exc:
        raise HTTPException(409, "corrupt stored strategy") from exc
    if saved is None:
        raise HTTPException(404, "resource not found")
    return strategies._item(saved)


@router.get("/experiments")
def list_experiments(
    request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
):
    return experiments.list_all(request, offset, limit)


@router.get("/experiments/{identifier}")
def experiment_detail(identifier: str, request: Request):
    return experiments.detail(identifier, request)


@router.get("/experiments/{identifier}/compare")
def experiment_compare(identifier: str, request: Request):
    return experiments.compare(identifier, request)


@router.get("/experiments/{identifier}/runs/{ordinal}/replay")
def experiment_replay(
    identifier: str,
    ordinal: int,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return experiments.replay(identifier, ordinal, request, offset, limit)


@router.get("/experiments/{identifier}/runs/{ordinal}/trajectory")
def experiment_trajectory(
    identifier: str, ordinal: int, request: Request, max_points: int = Query(500, ge=4, le=2000)
):
    return experiments.trajectory(identifier, ordinal, request, max_points)


@router.post("/experiments/{identifier}/cancel")
def cancel_experiment(identifier: str, request: Request):
    return queue.cancel(identifier, request)


@router.post("/profile-batches/validate")
async def validate_batch(request: Request):
    return await profile_batches.validate(request)


@router.post("/profile-batches", status_code=201)
async def create_batch(request: Request, response: Response):
    result = await profile_batches.create(request, response)
    links = result.get("links") if isinstance(result, dict) else None
    if links:
        base = f"/api/agent/v1/experiments/{result['id']}"
        links["self"] = base
        links["compare"] = f"{base}/compare"
        for item in links.get("runs", []):
            ordinal = item["ordinal"]
            item["replay"] = f"{base}/runs/{ordinal}/replay"
            item["trajectory"] = f"{base}/runs/{ordinal}/trajectory"
    return result


@router.get("/profile-batches/by-client-request/{client_request_id:path}")
def batch_by_client_request(client_request_id: str, request: Request):
    result = profile_batches.by_client_request(client_request_id, request)
    links = result.get("links") if isinstance(result, dict) else None
    if links:
        base = f"/api/agent/v1/experiments/{result['id']}"
        links["self"] = base
        links["compare"] = f"{base}/compare"
        for item in links.get("runs", []):
            ordinal = item["ordinal"]
            item["replay"] = f"{base}/runs/{ordinal}/replay"
            item["trajectory"] = f"{base}/runs/{ordinal}/trajectory"
    return result


@router.post("/history/preview")
async def preview_history(request: Request):
    return await imports.history_preview(request)


@router.post("/history/promote")
async def promote_history(request: Request):
    return await imports.history_promote(request)
