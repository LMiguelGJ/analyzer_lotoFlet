"""Process queue status and explicit held/cancel actions."""

from fastapi import APIRouter, HTTPException, Query, Request

from laboratorio.api import jobs, missing, repo
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/queue")


@router.get("")
def status(request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    queue = jobs(request)
    failure = queue.last_failure
    pending_total, pending_ids = queue.page_pending_ids(offset, limit)
    held_total, held_ids = repo(request).page_held_ids(offset, limit)
    return {
        "active_id": queue.active_id,
        "pending": {
            "total": pending_total,
            "offset": offset,
            "limit": limit,
            "count": len(pending_ids),
            "items": pending_ids,
        },
        "held": {
            "total": held_total,
            "offset": offset,
            "limit": limit,
            "count": len(held_ids),
            "items": held_ids,
        },
        "last_failure": None
        if failure is None
        else {
            "experiment_id": failure.experiment_id,
            "persisted": failure.persisted,
            "reason": type(failure.error).__name__,
            "persistence_error": None
            if failure.persistence_error is None
            else type(failure.persistence_error).__name__,
        },
    }


@router.post("/{identifier}/start")
def start(identifier: str, request: Request):
    missing(repo(request).get_experiment(identifier))
    try:
        jobs(request).start_held(identifier)
    except QuotaExceeded as exc:
        raise HTTPException(507, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, "queue is unavailable") from exc
    return {"id": identifier, "status": "queued"}


@router.post("/{identifier}/cancel")
def cancel(identifier: str, request: Request):
    missing(repo(request).get_experiment(identifier))
    try:
        jobs(request).cancel(identifier)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, "queue is unavailable") from exc
    return {"id": identifier, "status": "cancellation_requested"}
