"""Small, cached catalog projection; never serialize ranking arrays."""

from fastapi import APIRouter, Query, Request

from laboratorio.domain.contracts import COVERAGES, GAME, SYSTEMS
from laboratorio.settings import HISTORY_SHA256, RANKINGS_SHA256

router = APIRouter()


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


@router.get("/catalog/starting-draws")
def starting_draws(
    request: Request, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    data = request.app.state.data
    rows = data.rankings.row_ids[offset : offset + limit]
    return {
        "total": len(data.rankings.row_ids),
        "offset": offset,
        "limit": limit,
        "items": [data.history.labels[int(index)] for index in rows],
    }
