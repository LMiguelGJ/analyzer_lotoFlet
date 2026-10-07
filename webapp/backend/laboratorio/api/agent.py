"""Fixed allowlist facade over the application's existing API services."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

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

# Register only signature-compatible native callables, never entire native routers.
# Explicit names retain the facade's OpenAPI summaries and operation identifiers.
router.add_api_route("/catalog", catalog.read_catalog, methods=["GET"], name="read_catalog")
router.add_api_route(
    "/starting-draws", catalog.starting_draws, methods=["GET"], name="starting_draws"
)
router.add_api_route("/profiles", catalog.profiles, methods=["GET"], name="list_profiles")


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


router.add_api_route("/datasets", datasets.datasets, methods=["GET"], name="list_datasets")
router.add_api_route(
    "/datasets/{sha256}", datasets.dataset_detail, methods=["GET"], name="dataset_detail"
)
router.add_api_route(
    "/datasets/{sha256}/draws", datasets.dataset_draws, methods=["GET"], name="dataset_draws"
)
router.add_api_route("/strategies", strategies.list_all, methods=["GET"], name="list_strategies")
router.add_api_route(
    "/strategies", strategies.create, methods=["POST"], status_code=201, name="create_strategy"
)
router.add_api_route(
    "/strategies/{identifier}", strategies.detail, methods=["GET"], name="strategy_detail"
)
router.add_api_route(
    "/strategies/{identifier}/revisions",
    strategies.revisions,
    methods=["GET"],
    name="strategy_revisions",
)


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
    # Native search also accepts filters/sorting; the agent exposes pagination only.
    return experiments.list_all(request, offset, limit, name_contains=None)


router.add_api_route(
    "/experiments/{identifier}", experiments.detail, methods=["GET"], name="experiment_detail"
)
router.add_api_route(
    "/experiments/{identifier}/compare",
    experiments.compare,
    methods=["GET"],
    name="experiment_compare",
)
router.add_api_route(
    "/experiments/{identifier}/runs/{ordinal}/replay",
    experiments.replay,
    methods=["GET"],
    name="experiment_replay",
)
router.add_api_route(
    "/experiments/{identifier}/runs/{ordinal}/trajectory",
    experiments.trajectory,
    methods=["GET"],
    name="experiment_trajectory",
)
router.add_api_route(
    "/experiments/{identifier}/cancel", queue.cancel, methods=["POST"], name="cancel_experiment"
)
router.add_api_route(
    "/profile-batches/validate", profile_batches.validate, methods=["POST"], name="validate_batch"
)


def _agent_batch_links(result):
    """Project facade URLs without changing native responses or stored snapshots."""
    links = result.get("links") if isinstance(result, dict) else None
    if not links:
        return result
    base = f"/api/agent/v1/experiments/{result['id']}"
    projected = {**links, "self": base, "compare": f"{base}/compare"}
    if "runs" in links:
        projected["runs"] = [
            {
                **item,
                "replay": f"{base}/runs/{item['ordinal']}/replay",
                "trajectory": f"{base}/runs/{item['ordinal']}/trajectory",
            }
            for item in links["runs"]
        ]
    return {**result, "links": projected}


@router.post("/profile-batches", status_code=201)
async def create_batch(request: Request, response: Response):
    return _agent_batch_links(await profile_batches.create(request, response))


@router.get("/profile-batches/by-client-request/{client_request_id:path}")
def batch_by_client_request(client_request_id: str, request: Request):
    return _agent_batch_links(profile_batches.by_client_request(client_request_id, request))


router.add_api_route(
    "/history/preview", imports.history_preview, methods=["POST"], name="preview_history"
)
router.add_api_route(
    "/history/promote", imports.history_promote, methods=["POST"], name="promote_history"
)
