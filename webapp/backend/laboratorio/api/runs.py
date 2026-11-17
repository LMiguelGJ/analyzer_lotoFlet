"""Synchronous local API for creating and inspecting saved runs."""

import re
from typing import Annotated, Literal, NoReturn

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import Field, field_validator

from laboratorio.api import StrictBody, repo
from laboratorio.api.history import _meta
from laboratorio.domain.contracts import SYSTEMS
from laboratorio.domain.number_lists import (
    DEFAULT_LIST_ID,
    UNAVAILABLE_REASON,
    NumberList,
)
from laboratorio.engine.list_catalog import ListError
from laboratorio.engine.run_service import RunSpec, RunSpecError, _list_snapshot, execute_run

router = APIRouter(prefix="/runs")
_HISTORY_SHA256 = re.compile(r"\A[0-9a-fA-F]{64}\Z")


class RunRules(StrictBody):
    positions: int = Field(default=3, strict=True, ge=1, le=5)
    prizes: list[Annotated[int, Field(strict=True, ge=1)]] = Field(
        default_factory=lambda: [60, 10, 5]
    )
    minimum_stake: int = Field(default=1, strict=True, ge=1)


class RunComponent(StrictBody):
    system: str = Field(strict=True)
    percent: int = Field(strict=True, ge=1, le=100)


class RunStrategy(StrictBody):
    kind: Literal["mix", "parity"] = "mix"
    components: list[RunComponent] = Field(
        default_factory=lambda: [
            RunComponent(system="transition", percent=60),
            RunComponent(system="cold", percent=40),
        ]
    )
    coverage: int = Field(default=10, strict=True, ge=1, le=50)


class RunConditions(StrictBody):
    capital: int = Field(default=2000, strict=True, ge=1)
    goal: int = Field(default=2800, strict=True, ge=2)
    max_draws: int | None = Field(default=None, strict=True, ge=1)


class RunWindow(StrictBody):
    start_date: str | None = Field(default=None, strict=True)
    end_date: str | None = Field(default=None, strict=True)


class CreateRun(StrictBody):
    name: str | None = Field(default=None, strict=True, max_length=80)
    rules: RunRules = Field(default_factory=RunRules)
    strategy: RunStrategy = Field(default_factory=RunStrategy)
    conditions: RunConditions = Field(default_factory=RunConditions)
    window: RunWindow = Field(default_factory=RunWindow)
    history_sha256: str | None = Field(default=None, strict=True)

    @field_validator("history_sha256")
    @classmethod
    def valid_history_fingerprint(cls, value):
        if value is not None and not _HISTORY_SHA256.fullmatch(value):
            raise ValueError("history_sha256 debe ser una huella hexadecimal de 64 caracteres")
        return value


def _as_spec(body: CreateRun, list_id: str = DEFAULT_LIST_ID) -> RunSpec:
    return RunSpec(
        name=body.name,
        positions=body.rules.positions,
        prizes=tuple(body.rules.prizes),
        minimum_stake=body.rules.minimum_stake,
        kind=body.strategy.kind,
        components=tuple((item.system, item.percent) for item in body.strategy.components),
        coverage=body.strategy.coverage,
        capital=body.conditions.capital,
        goal=body.conditions.goal,
        max_draws=body.conditions.max_draws,
        start_date=body.window.start_date,
        end_date=body.window.end_date,
        history_sha256=body.history_sha256,
        list_id=list_id,
    )


def _storage_error(exc: ValueError) -> NoReturn:
    if str(exc) != "stored run is corrupt":
        raise exc
    raise HTTPException(409, "Una corrida guardada está dañada y no se puede mostrar.") from None


def system_entries(number_list: NumberList) -> list[dict]:
    """Ranking systems for the options payload.

    Chance Express keeps the plain ``{id, label}`` shape; any other list flags every system
    as available or not (with the Spanish reason).
    """
    if number_list.id == DEFAULT_LIST_ID:
        return [{"id": system, "label": label} for system, label in SYSTEMS.items()]
    entries = []
    for system, label in SYSTEMS.items():
        if system in number_list.available_systems:
            entries.append({"id": system, "label": label, "available": True})
        else:
            entries.append(
                {"id": system, "label": label, "available": False, "reason": UNAVAILABLE_REASON}
            )
    return entries


def list_summary(number_list: NumberList) -> dict:
    return {"id": number_list.id, "name": number_list.name, "positions": number_list.positions}


def _leidsa_history_meta(request: Request, number_list: NumberList) -> dict:
    lists = request.app.state.lists
    try:
        lab = lists.lab_data(number_list.id)
    except ListError as exc:
        raise HTTPException(409, exc.message) from None
    snapshot = _list_snapshot(lab)
    meta = _meta(snapshot, active=True)
    meta["list_id"] = number_list.id
    return meta


@router.get("/options")
def run_options(request: Request):
    number_list = request.app.state.lists.active()
    on_chance = number_list.id == DEFAULT_LIST_ID
    saved = request.app.state.lists.prizes(number_list.id)
    if on_chance:
        # Runs play 3 positions by default: Loteka keeps its own 60/10/5 table until the user
        # saves one, then the first three saved prizes are offered.
        custom = saved != list(number_list.default_prizes)
        prizes = saved[:3] if custom else [60, 10, 5]
    else:
        prizes = saved
    components = (
        [{"system": "transition", "percent": 60}, {"system": "cold", "percent": 40}]
        if on_chance
        else [{"system": "cold", "percent": 60}, {"system": "freq_recent", "percent": 40}]
    )
    if on_chance:
        catalog = request.app.state.history
        history = _meta(catalog.active(), active=True)
    else:
        history = _leidsa_history_meta(request, number_list)
    return {
        "list": list_summary(number_list),
        "systems": system_entries(number_list),
        "systems_available": list(number_list.available_systems),
        "defaults": {
            "name": None,
            "rules": {"positions": 3, "prizes": prizes, "minimum_stake": 1},
            "strategy": {"kind": "mix", "components": components, "coverage": 10},
            "conditions": {"capital": 2000, "goal": 2800, "max_draws": None},
            "window": {"start_date": None, "end_date": None},
            "history_sha256": None,
        },
        "limits": {
            "coverage": {"min": 1, "max": 50},
            "positions": {"min": 1, "max": 5 if on_chance else number_list.positions},
            "name": 80,
            "detail": {"sessions": 50000, "bets": 250000, "bytes": 33554432},
        },
        "history": history,
    }


@router.post("", status_code=201)
def create_run(body: CreateRun, request: Request):
    lists = request.app.state.lists
    try:
        return execute_run(
            _as_spec(body, lists.active_id()),
            catalog=request.app.state.history,
            repo=repo(request),
            settings=request.app.state.settings,
            rankings_cache=request.app.state.rankings_cache,
            lock=request.app.state.rankings_lock,
            lists=lists,
        )
    except RunSpecError as exc:
        status = {"invalid": 422, "not_found": 404, "quota": 409}[exc.kind]
        raise HTTPException(status, exc.message) from None


@router.get("")
def list_runs(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        total, items = repo(request).search_runs(offset, limit)
    except ValueError as exc:
        _storage_error(exc)
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@router.get("/{run_id}/sessions")
def run_sessions(
    run_id: str,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    outcome: Literal["goal", "ruin", "limit", "incomplete"] | None = None,
):
    try:
        page = repo(request).page_run_sessions(run_id, offset, limit, outcome)
    except ValueError as exc:
        _storage_error(exc)
    if page is None:
        raise HTTPException(404, "La corrida no existe.")
    total, items = page
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@router.get("/{run_id}/sessions/{ordinal}/bets")
def run_session_bets(
    run_id: str,
    ordinal: Annotated[int, Path(ge=1)],
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        page = repo(request).page_run_bets(run_id, ordinal, offset, limit)
    except ValueError as exc:
        _storage_error(exc)
    if page is None:
        raise HTTPException(404, "La corrida o sesión no existe.")
    return page


@router.get("/{run_id}")
def get_run(run_id: str, request: Request):
    try:
        report = repo(request).get_run(run_id)
    except ValueError as exc:
        _storage_error(exc)
    if report is None:
        raise HTTPException(404, "La corrida no existe.")
    return report


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: str, request: Request):
    if not repo(request).delete_run(run_id):
        raise HTTPException(404, "La corrida no existe.")
    return None
