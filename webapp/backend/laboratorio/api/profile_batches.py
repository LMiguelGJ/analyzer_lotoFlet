"""Native API for strictly referenced, bounded profile batches."""

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import ConfigDict, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool

from laboratorio.api import StrictBody, jobs, repo
from laboratorio.api.experiments import bounded_profile_body, experiment, public_experiment
from laboratorio.domain.batch_admission import (
    PreparedProfileBatch,
    ProfileBatchSubmission,
    StrategyReference,
    prepare_profile_batch,
)
from laboratorio.domain.contracts import SettlementMode
from laboratorio.domain.profile_request import _bad_constant, _unique_pairs
from laboratorio.domain.profile_session import ProfileConditions
from laboratorio.storage.quota import PendingRunsExceeded, QuotaExceeded
from laboratorio.storage.repository import IdempotencyConflict

router = APIRouter(prefix="/profile-batches")
_SUBMISSION_LOCK = asyncio.Lock()


class _ClosedBody(StrictBody):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProfileIdentity(_ClosedBody):
    id: str = Field(min_length=1, max_length=80)
    revision: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StrategyRefBody(_ClosedBody):
    id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def as_reference(self) -> StrategyReference:
        return StrategyReference(self.id, self.revision, self.definition_sha256)


class ConditionsBody(_ClosedBody):
    schema_version: Literal[1]
    start_draw: str
    capital: int = Field(ge=1)
    goal: int = Field(ge=2)
    settlement: Literal["all", "best"]
    max_elapsed_draws: int | None
    max_bet_draws: int | None
    end_minute: int | None
    duration_minutes: int | None

    @field_validator("schema_version", mode="before")
    @classmethod
    def _require_exact_schema_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be the integer 1")
        return value

    def to_conditions(self) -> ProfileConditions:
        return ProfileConditions(
            self.schema_version,
            self.start_draw,
            self.capital,
            self.goal,
            SettlementMode(self.settlement),
            self.max_elapsed_draws,
            self.max_bet_draws,
            self.end_minute,
            self.duration_minutes,
        )


class BatchSubmissionBody(_ClosedBody):
    schema_version: Literal[1]
    profile: ProfileIdentity
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategies: list[StrategyRefBody] = Field(min_length=1, max_length=3)
    conditions: ConditionsBody
    max_draws: int = Field(ge=1, le=10_000)
    client_request_id: str = Field(min_length=1, max_length=128)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _require_exact_schema_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be the integer 1")
        return value

    @model_validator(mode="after")
    def _unique_references(self):
        refs = [(ref.id, ref.revision) for ref in self.strategies]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate strategy revision references are not allowed")
        if len(self.client_request_id.encode("utf-8")) > 128:
            raise ValueError("client_request_id exceeds 128 UTF-8 bytes")
        return self

    def to_submission(self) -> ProfileBatchSubmission:
        return ProfileBatchSubmission(
            tuple(ref.as_reference() for ref in self.strategies),
            self.profile.id,
            self.profile.revision,
            self.profile.sha256,
            self.dataset_sha256,
            self.conditions.to_conditions(),
            self.max_draws,
            self.client_request_id,
        )


def _decode_submission(raw: str) -> ProfileBatchSubmission:
    try:
        document = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except (ValueError, RecursionError) as exc:
        raise ValueError("invalid profile batch JSON") from exc
    return BatchSubmissionBody.model_validate(document).to_submission()


def _is_admission_conflict(exc: ValueError) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "corrupt",
            "stored profile",
            "singleton is missing",
            "execution policy changed during admission",
            "changed during batch admission",
        )
    )


def _prepare(request: Request, submission: ProfileBatchSubmission) -> PreparedProfileBatch:
    try:
        return prepare_profile_batch(repo(request), submission, settings=request.app.state.settings)
    except ValueError as exc:
        status_code = 409 if _is_admission_conflict(exc) else 422
        raise HTTPException(status_code, str(exc)) from exc


def _validation_projection(prepared: PreparedProfileBatch) -> dict:
    policy = prepared.policy
    return {
        "valid": True,
        "reasons": [],
        "profile": {
            "id": prepared.request.profile_id,
            "revision": prepared.request.profile_revision,
            "sha256": prepared.request.profile_sha256,
        },
        "dataset": prepared.source_identity,
        "strategies": list(prepared.strategy_refs),
        "requested_constraints": prepared.requested_constraints,
        "effective_constraints": prepared.effective_constraints,
        "limits": {
            "worker_count": policy.worker_count,
            "max_strategies_per_batch": policy.max_strategies_per_batch,
            "max_pending_runs": policy.max_pending_runs,
            "run_timeout_seconds": policy.run_timeout_seconds,
            "reservation_created": False,
        },
        "policy": {"revision": prepared.policy_revision, **policy.as_dict()},
    }


@router.post("/validate")
async def validate(request: Request):
    try:
        submission = _decode_submission(await bounded_profile_body(request))
    except HTTPException:
        raise
    except (TypeError, ValueError, RecursionError) as exc:
        raise HTTPException(422, f"invalid profile batch request: {exc}") from exc
    return _validation_projection(_prepare(request, submission))


def _with_links(saved, *, created: bool):
    result = experiment(saved)
    base = f"/api/v1/experiments/{saved.id}"
    result["created"] = created
    result["links"] = {
        "self": base,
        "compare": f"{base}/compare",
        "runs": [
            {
                "ordinal": run.ordinal,
                "replay": f"{base}/runs/{run.ordinal}/replay",
                "trajectory": f"{base}/runs/{run.ordinal}/trajectory",
            }
            for run in saved.runs
        ],
    }
    return result


@router.post("", status_code=201)
async def create(request: Request, response: Response):
    try:
        submission = _decode_submission(await bounded_profile_body(request))
    except HTTPException:
        raise
    except (TypeError, ValueError, RecursionError) as exc:
        raise HTTPException(422, f"invalid profile batch request: {exc}") from exc
    queue = jobs(request)
    repository = repo(request)
    # Keep API identity inspection and submit classification atomic across callers.
    async with _SUBMISSION_LOCK:
        try:
            previous = repository.get_profile_batch_request_id(submission.client_request_id)
        except ValueError as exc:
            raise HTTPException(409, "stored profile batch identity is corrupt") from exc
        try:
            identifier = await run_in_threadpool(queue.submit_profile_batch, submission)
        except IdempotencyConflict as exc:
            raise HTTPException(
                409, "client_request_id was already used for another request"
            ) from exc
        except PendingRunsExceeded as exc:
            raise HTTPException(409, "global pending run capacity exceeded") from exc
        except QuotaExceeded as exc:
            raise HTTPException(409, "profile batch exceeds available quota") from exc
        except (TypeError, ValueError) as exc:
            status_code = (
                409 if isinstance(exc, ValueError) and _is_admission_conflict(exc) else 422
            )
            raise HTTPException(status_code, "profile batch admission failed") from exc
        except RuntimeError as exc:
            raise HTTPException(409, "queue is unavailable") from exc
    saved = public_experiment(identifier, request)
    created = previous is None
    response.status_code = 201 if created else 200
    return _with_links(saved, created=created)


@router.get("/by-client-request/{client_request_id:path}")
def by_client_request(client_request_id: str, request: Request):
    try:
        identifier = repo(request).get_profile_batch_request_id(client_request_id)
    except ValueError as exc:
        raise HTTPException(409, "stored profile batch identity is corrupt") from exc
    if identifier is None:
        raise HTTPException(404, "resource not found")
    saved = public_experiment(identifier, request)
    return _with_links(saved, created=False)
