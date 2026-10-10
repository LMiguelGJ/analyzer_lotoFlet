"""Active history catalog and raw JSON import endpoints."""

from typing import cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from laboratorio.api import history
from laboratorio.engine.active_history import HistoryImportError, HistorySnapshot
from laboratorio.engine.adapter import History

router = APIRouter(prefix="/history")


def _meta(snapshot: HistorySnapshot, *, active: bool) -> dict:
    source_history = cast(History, snapshot.history)
    return {
        "sha256": snapshot.sha256,
        "origin": snapshot.origin,
        "draws": len(source_history.labels),
        "ranked_draws": snapshot.ranked_draws,
        "first_label": source_history.labels[0],
        "last_label": source_history.labels[-1],
        "added_draws": snapshot.added_draws,
        "created_at": snapshot.created_at,
        "active": active,
    }


@router.get("")
def list_history(request: Request):
    catalog = history(request)
    active_snapshot = catalog.active()
    active_sha = active_snapshot.sha256
    sources = []
    for source in catalog.list_sources():
        snapshot = catalog.snapshot(source["sha256"])
        if snapshot is not None:
            sources.append(_meta(snapshot, active=source["sha256"] == active_sha))
    return {"active": _meta(active_snapshot, active=True), "sources": sources}


@router.post("")
async def import_history(request: Request):
    raw = await request.body()
    if not raw:
        raise HTTPException(422, "El archivo no tiene el formato de historial esperado.")
    try:
        outcome = await run_in_threadpool(history(request).import_history, raw)
    except HistoryImportError as exc:
        status = {"invalid": 422, "conflict": 409, "quota": 409}[exc.kind]
        raise HTTPException(status, exc.message) from None
    status_code = 201 if outcome.added else 200
    return JSONResponse(
        {
            "created": bool(outcome.added),
            "added": outcome.added,
            "active": _meta(outcome.snapshot, active=True),
        },
        status_code=status_code,
    )
