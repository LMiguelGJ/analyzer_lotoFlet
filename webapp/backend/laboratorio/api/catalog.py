"""Small, cached catalog projection; never serialize ranking arrays."""

import json
from bisect import bisect_left
from datetime import date as calendar_date

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from laboratorio.api.experiments import bounded_profile_body
from laboratorio.domain.contracts import (
    COVERAGES,
    GAME,
    SYSTEMS,
    GameProfile,
    legacy_quiniela_80_profile,
)
from laboratorio.domain.profile_capabilities import audaz_compatible_coverage, supported
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_staking import q80_first_prize_ladder
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter()

# Reference scenarios, not valid/persisted GameProfile documents. Missing admission
# fields are deliberate: displaying a prize table must not enable execution.
PROFILE_TEMPLATES = (
    {
        "name": "Original70",
        "provenance": "repo_ref/strategy_tests/rules.py: ORIGINAL70 and payout_matrix",
        "known_fields": {
            "universe_size": 100,
            "positions": 5,
            "multipliers": [{"numerator": prize, "denominator": 1} for prize in (70, 8, 4, 2, 1)],
        },
        "missing_fields": [
            "schema_version",
            "profile_id",
            "revision",
            "allows_repeats",
            "currency",
            "scale",
            "stake_increment",
            "minimum_stake",
            "maximum_stake",
            "max_coverage",
            "max_exposure",
            "best_rule",
        ],
        "execution_supported": False,
    },
    {
        "name": "User example 60/10/5",
        "provenance": "docs/especificaciones-laboratorio-integral.md: E01",
        "known_fields": {
            "universe_size": 100,
            "positions": 3,
            "allows_repeats": True,
            "multipliers": [{"numerator": prize, "denominator": 1} for prize in (60, 10, 5)],
            "currency": "DOP",
            "minimum_stake": 1,
        },
        "missing_fields": [
            "schema_version",
            "profile_id",
            "revision",
            "scale",
            "stake_increment",
            "maximum_stake",
            "max_coverage",
            "max_exposure",
            "best_rule",
        ],
        "execution_supported": False,
    },
)


@router.get("/catalog")
def read_catalog(request: Request):
    data = request.app.state.data
    labels = data.history.labels
    return {
        "game": {
            "name": GAME.name,
            "numbers": GAME.numbers,
            "positions": GAME.positions,
            "prizes": GAME.prizes,
            "allows_repeats": GAME.allows_repeats,
        },
        "systems": SYSTEMS,
        "selectors": ["system", "blend", "random", "parity"],
        "coverages": COVERAGES,
        "parity_coverage": 50,
        "starting_draws": [labels[int(index)] for index in data.rankings.row_ids[:100]],
        "starting_draws_total": len(data.rankings.row_ids),
        "sources": {
            "history_sha256": HISTORY_SHA256,
            "rankings_sha256": RANKINGS_SHA256,
            "history_id": request.app.state.settings.history_path.name,
            "rankings_id": request.app.state.settings.rankings_path.name,
            "code_version": request.app.version,
            "first_draw": labels[0],
            "last_draw": labels[-1],
        },
    }


# Legacy execution_supported retains its original meaning. This separate capability
# describes only the profile engine's closed request subset; it is not a promise
# that any arbitrary strategy can execute or that a matching dataset exists.
def profile_execution(ready: bool, profile: GameProfile | None = None):
    """Offer cycling only for a profile whose complete minimum-coverage ladder fits."""
    staking = [
        name
        for name in supported("staking")
        if name
        not in (
            "q80-first-prize-cycling/v1",
            "profile-audaz/v1",
            "profile-recovery-ladder/v1",
        )
    ]
    audaz_coverage = 0
    recovery_coverage = 0
    if ready and profile is not None:
        try:
            q80_first_prize_ladder(profile, 1)
        except (ValueError, TypeError):
            pass
        else:
            staking.append("q80-first-prize-cycling/v1")
        audaz_coverage = audaz_compatible_coverage(profile)
        if audaz_coverage:
            staking.append("profile-audaz/v1")
        first = profile.multipliers[0]
        mathematical_limit = (first.numerator - 1) // first.denominator
        recovery_coverage = min(profile.max_coverage, profile.universe_size, mathematical_limit)
        if recovery_coverage:
            staking.append("profile-recovery-ladder/v1")
    return {
        "ready": ready,
        "selector_capabilities": list(supported("selector")),
        "staking_capabilities": staking,
        "entry_policies": list(supported("entry")),
        "settlements": list(supported("settlement")),
        "requires_compatible_dataset": True,
        "audaz_compatibility": {
            "available": audaz_coverage > 0,
            "maximum_compatible_coverage": audaz_coverage,
            "coverage_rule": "selected coverage must be strictly less than multiplier[0]",
        },
        "recovery_compatibility": {
            "available": recovery_coverage > 0,
            "maximum_compatible_coverage": recovery_coverage,
            "coverage_rule": "selected coverage must be strictly less than multiplier[0]",
            "parameters": ["target_margin", "rounds", "end_mode"],
        },
    }


def _profile_item(profile):
    return {
        "profile": profile.model_dump(mode="json"),
        "profile_sha256": profile_sha256(profile),
        "execution_supported": profile == legacy_quiniela_80_profile(),
        "profile_execution": profile_execution(True, profile),
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-standard JSON number")


@router.post("/catalog/profiles", status_code=201)
async def register_profile(request: Request):
    """Register one complete GameProfile; immutable same-content retries succeed."""
    try:
        raw = await bounded_profile_body(request)
        document = json.loads(
            raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        profile = GameProfile.model_validate(document)
    except (ValueError, ValidationError, TypeError, RecursionError) as exc:
        raise HTTPException(422, "invalid game profile") from exc
    settings = request.app.state.settings
    try:
        saved = await run_in_threadpool(
            request.app.state.repo.create_game_profile,
            profile,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
    except QuotaExceeded as exc:
        raise HTTPException(409, "profile quota has insufficient headroom") from exc
    except ValueError as exc:
        raise HTTPException(409, "profile version conflicts with registered content") from exc
    return _profile_item(saved)


@router.get("/catalog/profiles")
def profiles(request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    total, rows = request.app.state.repo.page_game_profiles(offset, limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_profile_item(profile) for profile in rows],
        "templates": PROFILE_TEMPLATES,
    }


def _date_bounds(data, draw_date: str) -> tuple[int, int, int, int]:
    try:
        calendar_date.fromisoformat(draw_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid ISO calendar date") from exc
    labels = data.history.labels
    first = bisect_left(labels, f"{draw_date} ")
    end = bisect_left(labels, f"{draw_date} 24:00")
    rows = data.rankings.row_ids
    return first, end, bisect_left(rows, first), bisect_left(rows, end)


@router.get("/catalog/starting-draws")
def starting_draws(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    draw_date: str | None = Query(None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    data = request.app.state.data
    rows = data.rankings.row_ids
    first, end = (0, len(rows))
    if draw_date is not None:
        _, _, first, end = _date_bounds(data, draw_date)
    return {
        "total": end - first,
        "offset": offset,
        "limit": limit,
        "items": [
            data.history.labels[int(index)]
            for index in rows[first + offset : min(first + offset + limit, end)]
        ],
    }


@router.get("/catalog/starting-draws/availability")
def starting_draw_availability(
    request: Request,
    draw_date: str = Query(alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    """One-day history count distinguishes missing draws from unranked history."""
    history_first, history_end, ranked_first, ranked_end = _date_bounds(
        request.app.state.data, draw_date
    )
    return {
        "date": draw_date,
        "history_total": history_end - history_first,
        "ranked_total": ranked_end - ranked_first,
    }
