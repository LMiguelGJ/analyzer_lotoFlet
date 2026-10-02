"""Versioned HTTP resources and presentation helpers."""

import json
from dataclasses import asdict

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict

from laboratorio.domain.metrics import financial_metrics
from laboratorio.domain.profile_request import serialize_profile_request
from laboratorio.domain.profile_request_v2 import serialize_profile_cycling_request
from laboratorio.domain.profile_request_v3 import serialize_profile_audaz_request
from laboratorio.domain.profile_request_v4 import serialize_profile_recovery_request
from laboratorio.domain.profile_result_v2 import ProfileCyclingResult
from laboratorio.domain.profile_result_v3 import ProfileAudazResult
from laboratorio.domain.profile_result_v4 import ProfileRecoveryResult


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


def run_summary(run, capital):
    result = run.result
    if isinstance(result, (ProfileCyclingResult, ProfileAudazResult, ProfileRecoveryResult)):
        result = result.session
    summary = {
        "ordinal": run.ordinal,
        "configuration_id": run.configuration_id,
        "status": run.status,
        "result": None
        if result is None
        else {
            **{key: value for key, value in asdict(result).items() if key != "bets"},
            "delta": result.final_balance - capital,
            **financial_metrics(result, capital),
        },
        "bets_count": 0 if result is None else len(result.bets),
    }
    if run.result_kind == "profile":
        summary["result_kind"] = "profile"
    if run.result_schema_version in (2, 3, 4) and summary["result"] is not None:
        summary["result"]["schema_version"] = run.result_schema_version
    return summary


def experiment(saved):
    cycling = saved.request_kind == "profile" and saved.request_schema_version == 2
    audaz = saved.request_kind == "profile" and saved.request_schema_version == 3
    recovery = saved.request_kind == "profile" and saved.request_schema_version == 4
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
    elif saved.request_schema_version != 1 or any(
        run.result_schema_version not in (None, 1) for run in saved.runs
    ):
        raise HTTPException(409, "stored experiment version is not publicly supported")
    is_profile = saved.request_kind == "profile"
    profile_request = None
    if is_profile:
        try:
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
        "runs": [run_summary(run, saved.request.conditions.capital) for run in saved.runs],
    }
    if is_profile:
        response["request_kind"] = "profile"
        response["display"] = {
            "name": saved.request.name,
            "currency": saved.profile.currency,
            "scale": saved.profile.scale,
            "capital": saved.request.conditions.capital,
            "goal": saved.request.conditions.goal,
            "selector_label": saved.request.selector.capability,
            "staking_label": (
                "Escalera cíclica Q80 · apuesta dinámica por sorteo"
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
