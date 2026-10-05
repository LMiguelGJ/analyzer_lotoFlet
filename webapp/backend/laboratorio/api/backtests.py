"""Synchronous, bounded historical replay endpoints.

FastAPI runs these regular handlers in its worker thread pool; a 200,000-row
ceiling bounds each replay, so the single-run API needs no separate job queue.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field, model_validator

from laboratorio.api import StrictBody, repo
from laboratorio.domain.backtest import BacktestConfig, run_backtest
from laboratorio.domain.contracts import MAX_MONEY, StakingStyle, make_game
from laboratorio.domain.selection import parity_numbers
from laboratorio.domain.session import Draw
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256

router = APIRouter()
MAX_BACKTEST_DRAWS = 200_000
_SUPPORTED_SYSTEMS = ("transition", "cold", "select_interpretable", "mix", "ensemble")


class BacktestStrategy(StrictBody):
    name: str = Field(min_length=1, max_length=80)
    selector: Literal["system", "parity"]
    system: Literal["transition", "cold", "select_interpretable", "mix", "ensemble"] | None = None
    coverage: int = Field(strict=True, ge=1, le=1000)
    staking: StakingStyle

    @model_validator(mode="after")
    def selector_matches(self):
        if self.selector == "system" and self.system not in _SUPPORTED_SYSTEMS:
            raise ValueError("choose an available ranking method")
        if self.selector == "parity" and self.system is not None:
            raise ValueError("parity selection does not use a ranking method")
        return self


class BacktestGame(StrictBody):
    numbers: int = Field(strict=True, ge=2, le=1000)
    positions: int = Field(strict=True, ge=1, le=16)
    prizes: list[Annotated[int, Field(strict=True, ge=1, le=MAX_MONEY)]]
    min_stake: int = Field(strict=True, ge=1, le=MAX_MONEY)


class BacktestConditions(StrictBody):
    capital: int = Field(strict=True, ge=1, le=MAX_MONEY)
    goal: int = Field(strict=True, ge=2, le=MAX_MONEY)


class BacktestInputs(StrictBody):
    history_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rankings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateBacktest(StrictBody):
    name: str = Field(min_length=1, max_length=80)
    strategy: BacktestStrategy
    game: BacktestGame
    conditions: BacktestConditions
    inputs: BacktestInputs


def _selection_rows(data, selector, system, coverage):
    history = data.history
    ranked = {int(row_id): index for index, row_id in enumerate(data.rankings.row_ids)}
    family = None
    votes = None
    if selector == "system":
        family = data.rankings.family(system)
    else:
        votes = data.parity_votes()
    rows = []
    for index, numbers in enumerate(history.nums):
        rank_index = ranked.get(index)
        if rank_index is None:
            order = None
        elif family is not None:
            order = tuple(int(number) for number in family[rank_index][:coverage])
        else:
            assert votes is not None
            order = tuple(int(number) for number in parity_numbers(int(votes[index]))[:coverage])
        rows.append(
            Draw(
                history.labels[index],
                int(history.minutes[index]),
                (
                    int(numbers[0]),
                    int(numbers[1]),
                    int(numbers[2]),
                    int(numbers[3]),
                    int(numbers[4]),
                ),
                order,
            )
        )
    return rows


def _report(identifier, name, config, result, created_at):
    return {
        "id": identifier,
        "name": name,
        "created_at": created_at,
        "reached_goal": result.reached_goal,
        "completed": result.completed,
        "goal_rate": result.goal_rate,
        "quiebres": result.quiebre,
        "neto_medio": result.neto_medio,
        "incomplete": result.incomplete,
        "window": {
            "bets": result.window.bets,
            "wagered": result.window.wagered,
            "paid": result.window.paid,
            "sessions": len(result.sessions),
            "incomplete": result.incomplete,
        },
        "config": config,
    }


@router.post("", status_code=201)
def create_backtest(body: CreateBacktest, request: Request):
    if (body.inputs.history_sha256, body.inputs.rankings_sha256) != (
        HISTORY_SHA256,
        RANKINGS_SHA256,
    ):
        raise HTTPException(
            409, "The selected history or rankings do not match the available data."
        )
    data = request.app.state.data
    if data.history.sha256 != HISTORY_SHA256:
        raise HTTPException(409, "The available history does not match its saved fingerprint.")
    if len(data.history.labels) > MAX_BACKTEST_DRAWS:
        raise HTTPException(413, "This history is too large to replay in one request.")
    try:
        game = make_game(
            "Backtest game",
            body.game.numbers,
            body.game.positions,
            body.game.prizes,
            True,
            body.game.min_stake,
        )
        if body.conditions.goal <= body.conditions.capital:
            raise ValueError("the goal must be greater than the starting capital")
        if body.strategy.coverage > game.numbers:
            raise ValueError("coverage cannot exceed the number of possible numbers")
        if body.strategy.selector == "parity" and body.strategy.coverage > 50:
            raise ValueError("parity selection can cover at most 50 numbers")
        config = BacktestConfig(
            capital=body.conditions.capital,
            goal=body.conditions.goal,
            numbers=game.numbers,
            positions=game.positions,
            prizes=game.prizes,
            minimum_stake=game.minimum_stake,
            coverage=body.strategy.coverage,
            staking=body.strategy.staking,
        )
        rows = _selection_rows(data, body.strategy.selector, body.strategy.system, config.coverage)
        result = run_backtest(config, rows)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    config_echo = {
        "name": body.name,
        "strategy": body.strategy.model_dump(mode="json"),
        "game": body.game.model_dump(mode="json"),
        "conditions": body.conditions.model_dump(mode="json"),
        "inputs": body.inputs.model_dump(mode="json"),
    }
    try:
        identifier, created_at = repo(request).create_backtest(body.name, config_echo, result)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, "The backtest result could not be saved.") from exc
    report = _report(identifier, body.name, config_echo, result, created_at)
    return {"id": identifier, "status": "completed", "report": report}


@router.get("")
def list_backtests(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        total, rows = repo(request).search_backtests(offset, limit)
    except ValueError as exc:
        raise HTTPException(409, "A saved backtest is damaged and cannot be shown.") from exc
    return {"total": total, "offset": offset, "limit": limit, "items": rows}


@router.get("/{identifier}")
def get_backtest(identifier: str, request: Request):
    try:
        saved = repo(request).get_backtest(identifier)
    except ValueError as exc:
        raise HTTPException(409, "The saved backtest is damaged and cannot be shown.") from exc
    if saved is None:
        raise HTTPException(404, "Backtest not found.")
    return saved
