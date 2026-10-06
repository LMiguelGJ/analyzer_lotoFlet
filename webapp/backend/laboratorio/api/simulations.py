"""Unified, bounded listing of stored classic, profile and historical simulations."""

import sqlite3
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from laboratorio.api import experiment
from laboratorio.domain.contracts import ExperimentStatus

router = APIRouter(prefix="/simulations")


def _validate_public_experiment(saved):
    try:
        experiment(saved)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc


@router.get("")
def list_simulations(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    scope: Literal["classic", "profile", "historical"] | None = None,
    name_contains: str | None = Query(None, max_length=80),
    status: ExperimentStatus | None = None,
    sort: Literal["created_at", "name", "status"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
):
    try:
        total, rows = request.app.state.repo.search_simulations(
            offset,
            limit,
            scope=scope,
            name_contains=name_contains,
            status=None if status is None else status.value,
            sort=sort,
            order=order,
            validate_experiment=_validate_public_experiment,
            settings=request.app.state.settings,
        )
        items = []
        for source_kind, item_scope, saved in rows:
            if source_kind == "experiment":
                detail = experiment(saved)
                items.append(
                    {
                        "source_kind": "experiment",
                        "scope": item_scope,
                        "id": saved.id,
                        "name": (
                            detail["display"]["name"]
                            if "display" in detail
                            else detail["request"]["name"]
                        ),
                        "status": saved.status.value,
                        "created_at": saved.created_at,
                        "detail": detail,
                    }
                )
            else:
                items.append(
                    {
                        "source_kind": "backtest",
                        "scope": item_scope,
                        "id": saved["id"],
                        "name": saved["name"],
                        "status": "completed",
                        "created_at": saved["created_at"],
                        "report": saved,
                    }
                )
    except ValueError as exc:
        raise HTTPException(409, "A stored simulation is damaged and cannot be shown.") from exc
    except (sqlite3.Error, OSError) as exc:
        raise HTTPException(503, "A simulation source is unavailable.") from exc
    return {"total": total, "offset": offset, "limit": limit, "items": items}
