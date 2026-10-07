"""Versioned HTTP resources and presentation helpers."""

import json

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict

from laboratorio.api.profile_views import BatchRunContext, run_summary, v5_strategy_result
from laboratorio.api.profile_views import v5_run_summary as v5_run_summary
from laboratorio.domain.profile_request import serialize_profile_request
from laboratorio.domain.profile_request_v2 import serialize_profile_cycling_request
from laboratorio.domain.profile_request_v3 import serialize_profile_audaz_request
from laboratorio.domain.profile_request_v4 import serialize_profile_recovery_request
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5, serialize_profile_batch_v5
from laboratorio.domain.profile_result_v2 import ProfileCyclingResult
from laboratorio.domain.profile_result_v3 import ProfileAudazResult
from laboratorio.domain.profile_result_v4 import ProfileRecoveryResult
from laboratorio.domain.profile_session_v5 import ProfileBatchResultV5


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def repo(request: Request):
    return request.app.state.repo


def jobs(request: Request):
    return request.app.state.jobs


def missing(value):
    if value is None:
        raise HTTPException(404, "resource not found")
    return value


def experiment(saved):
    cycling = saved.request_kind == "profile" and saved.request_schema_version == 2
    audaz = saved.request_kind == "profile" and saved.request_schema_version == 3
    recovery = saved.request_kind == "profile" and saved.request_schema_version == 4
    batch = saved.request_kind == "profile" and saved.request_schema_version == 5
    if batch:
        admission = saved.batch_admission
        batch_request = saved.request
        if (
            not isinstance(batch_request, ProfileBatchRequestV5)
            or len(saved.runs) != len(batch_request.strategies)
            or admission is None
            or len(admission["strategy_refs"]) != len(saved.runs)
            or any(
                run.ordinal != index
                or run.result_kind != "profile"
                or run.result_schema_version not in (None, 5)
                or (run.result is not None and not isinstance(run.result, ProfileBatchResultV5))
                or (run.result is not None and run.result_schema_version != 5)
                or (run.result is None and run.result_schema_version is not None)
                or (run.status == "completed") != (run.result is not None)
                for index, run in enumerate(saved.runs)
            )
            or (saved.status == "completed" and any(run.result is None for run in saved.runs))
        ):
            raise HTTPException(409, "stored profile batch is not publicly supported")
        for index, run in enumerate(saved.runs):
            if run.result is not None:
                v5_strategy_result(run)
                if run.result.results[0].definition != batch_request.strategies[index]:
                    raise HTTPException(409, "stored profile batch result association is corrupt")
    if cycling or audaz or recovery:
        if (
            len(saved.runs) != 1
            or any(
                run.ordinal != 0
                or run.result_kind != "profile"
                or (run.result_schema_version not in (None, saved.request_schema_version))
                or (
                    run.result is not None
                    and not isinstance(
                        run.result,
                        (ProfileCyclingResult, ProfileAudazResult, ProfileRecoveryResult),
                    )
                )
                or (run.result is None and run.result_schema_version is not None)
                or (run.status == "completed") != (run.result is not None)
                for run in saved.runs
            )
            or (saved.status == "completed" and saved.runs[0].result is None)
        ):
            raise HTTPException(409, "stored experiment version is not publicly supported")
    elif not batch and (
        saved.request_schema_version != 1
        or any(run.result_schema_version not in (None, 1) for run in saved.runs)
    ):
        raise HTTPException(409, "stored experiment version is not publicly supported")
    is_profile = saved.request_kind == "profile"
    profile_request = None
    if is_profile:
        try:
            if batch:
                profile_request = json.loads(serialize_profile_batch_v5(saved.request))
            else:
                serializer = (
                    serialize_profile_cycling_request
                    if cycling
                    else serialize_profile_audaz_request
                    if audaz
                    else serialize_profile_recovery_request
                    if recovery
                    else serialize_profile_request
                )
                profile_request = json.loads(serializer(saved.request))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("corrupt saved profile request") from exc
    response = {
        "id": saved.id,
        "status": saved.status,
        "created_at": saved.created_at,
        "request": profile_request if is_profile else saved.request.model_dump(mode="json"),
        "profile": saved.profile.model_dump(mode="json"),
        "sources": {
            "history_id": saved.history_id,
            "history_sha256": saved.history_sha256,
            "rankings_id": saved.rankings_id,
            "rankings_sha256": saved.rankings_sha256,
            "code_version": saved.code_version,
        },
        "runs": [
            run_summary(
                run,
                saved.request.conditions.capital,
                batch_context=(
                    BatchRunContext(
                        saved.batch_admission["source_identity"]["row_count"],
                        saved.batch_admission["requested_constraints"],
                        saved.batch_admission["effective_constraints"],
                        saved.batch_admission["strategy_refs"][index],
                    )
                    if batch
                    else None
                ),
            )
            for index, run in enumerate(saved.runs)
        ],
    }
    if batch:
        response["request_kind"] = "profile"
        response["request_schema_version"] = 5
        response["batch_admission"] = saved.batch_admission
    if is_profile:
        response["request_kind"] = "profile"
        response["display"] = {
            "name": (saved.request.strategies[0].name if batch else saved.request.name),
            "currency": saved.profile.currency,
            "scale": saved.profile.scale,
            "capital": saved.request.conditions.capital,
            "goal": saved.request.conditions.goal,
            "selector_label": ("Strategy batch" if batch else saved.request.selector.capability),
            "staking_label": (
                "Per-strategy definitions"
                if batch
                else "Escalera cíclica Q80 · apuesta dinámica por sorteo"
                if cycling
                else "Audaz · apuesta dinámica por sorteo"
                if audaz
                else "Escalera de recuperación · parámetros explícitos por perfil"
                if recovery
                else saved.request.staking.capability
            ),
        }
    return response


def configuration(saved):
    return {"id": saved.id, "name": saved.name, "strategy": saved.strategy.model_dump(mode="json")}
