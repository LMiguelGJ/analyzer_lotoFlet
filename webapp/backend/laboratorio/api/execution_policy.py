"""Operator-visible admission policy with compare-and-swap updates."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import ConfigDict, Field

from laboratorio.api import StrictBody, repo
from laboratorio.domain.execution_policy import POLICY_BOUNDS, POLICY_DEFAULTS

router = APIRouter(prefix="/execution-policy")


class PolicyUpdateBody(StrictBody):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: int = Field(ge=1)
    max_strategies_per_batch: int | None = Field(default=None, ge=1, le=3)
    worker_count: int | None = Field(default=None, ge=1, le=1)
    max_pending_runs: int | None = Field(default=None, ge=1, le=100)
    max_bet_draws: int | None = Field(default=None, ge=1, le=10_000)
    max_elapsed_draws: int | None = Field(default=None, ge=1, le=10_000)
    run_timeout_seconds: int | None = Field(default=None, ge=1, le=3_600)

    def changes(self) -> dict[str, int]:
        values = self.model_dump(exclude={"expected_revision"}, exclude_none=True)
        if not values:
            raise ValueError("at least one editable execution policy value is required")
        if "worker_count" in values:
            raise ValueError("worker_count is fixed at one")
        if set(values) - POLICY_BOUNDS.keys():
            raise ValueError("unsupported execution policy field")
        return values


_EXPLANATION = (
    "These are operator-configured admission limits, not performance or runtime guarantees. "
    "Updates apply only to future admissions; already queued batches retain frozen limits."
)


def _projection(repository) -> dict:
    try:
        revision, policy = repository.execution_policy()
    except ValueError as exc:
        raise HTTPException(409, "stored execution policy is corrupt") from exc
    return {
        "revision": revision,
        "policy": policy.as_dict(),
        "effective": policy.as_dict(),
        "defaults": dict(POLICY_DEFAULTS),
        "bounds": {key: list(value) for key, value in POLICY_BOUNDS.items()},
        "explanation": _EXPLANATION,
    }


@router.get("")
def get_policy(request: Request):
    return _projection(repo(request))


@router.put("")
def put_policy(body: PolicyUpdateBody, request: Request):
    try:
        changes = body.changes()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        repo(request).update_execution_policy(changes, expected_revision=body.expected_revision)
    except ValueError as exc:
        status_code = 409 if "conflict" in str(exc) else 422
        raise HTTPException(status_code, str(exc)) from exc
    return _projection(repo(request))
