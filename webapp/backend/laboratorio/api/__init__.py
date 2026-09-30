"""Versioned HTTP resources and presentation helpers."""

from dataclasses import asdict

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict


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
    return {
        "ordinal": run.ordinal,
        "configuration_id": run.configuration_id,
        "status": run.status,
        "result": None
        if result is None
        else {
            **{key: value for key, value in asdict(result).items() if key != "bets"},
            "delta": result.final_balance - capital,
        },
        "bets_count": 0 if result is None else len(result.bets),
    }


def experiment(saved):
    return {
        "id": saved.id,
        "status": saved.status,
        "created_at": saved.created_at,
        "request": saved.request.model_dump(mode="json"),
        "sources": {
            "history_id": saved.history_id,
            "history_sha256": saved.history_sha256,
            "rankings_id": saved.rankings_id,
            "rankings_sha256": saved.rankings_sha256,
            "code_version": saved.code_version,
        },
        "runs": [run_summary(run, saved.request.conditions.capital) for run in saved.runs],
    }


def configuration(saved):
    return {"id": saved.id, "name": saved.name, "strategy": saved.strategy.model_dump(mode="json")}
