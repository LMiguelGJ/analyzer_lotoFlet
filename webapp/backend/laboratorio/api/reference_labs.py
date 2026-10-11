"""Catalog, detail and persisted-run resources for the fixed reference laboratories."""

import logging
import uuid
from dataclasses import asdict
from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field

from laboratorio.api import StrictBody
from laboratorio.domain.reference_labs import REFERENCE_LABS, get_reference_lab
from laboratorio.engine.reference_lab_service import (
    ReferenceLabServiceError,
    execute_reference_lab,
)
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.reference_lab_store import (
    ReferenceLabStoreError,
    create_reference_lab_run,
    delete_reference_lab_run,
    get_reference_lab_run,
    list_reference_lab_runs,
)

router = APIRouter(prefix="/reference-labs")
_CONTRACT_VERSION = 1
_CAPABILITIES = {"session_summary": True, "per_bet_trace": False}
_MAX_I64 = 2**63 - 1
_LOG = logging.getLogger(__name__)


def _lab_contract(lab):
    return {
        "lab_id": lab.lab_id,
        "system": lab.system,
        "coverage": lab.coverage,
        "stake_style": lab.stake_style,
        "selection_kind": lab.selection_kind,
        "capital": lab.capital,
        "goal": lab.goal,
        "prizes": list(lab.prizes),
        "window": {"start": lab.window_start, "end": lab.window_end},
        "duration_cap": None,
        "editable": False,
    }


def _metadata(request: Request):
    data = request.app.state.data
    return {
        "sha256": data.history.sha256,
        "origin": "frozen_reference",
        "draws": len(data.history.labels),
        "ranked_draws": len(data.rankings.row_ids),
        "first_label": data.history.labels[0] if data.history.labels else None,
        "last_label": data.history.labels[-1] if data.history.labels else None,
    }


def _response(request: Request, lab):
    return {
        "contract_version": _CONTRACT_VERSION,
        "reference_history": _metadata(request),
        "capabilities": dict(_CAPABILITIES),
        "lab": _lab_contract(lab),
    }


@router.get("")
def reference_labs(request: Request):
    return {
        "contract_version": _CONTRACT_VERSION,
        "reference_history": _metadata(request),
        "capabilities": dict(_CAPABILITIES),
        "items": [_lab_contract(lab) for lab in REFERENCE_LABS],
    }


@router.get("/{lab_id}")
def reference_lab_detail(lab_id: str, request: Request):
    try:
        lab = get_reference_lab(lab_id)
    except ValueError:
        raise HTTPException(404, "El laboratorio de referencia no existe.") from None
    return _response(request, lab)


class CreateReferenceLabRun(StrictBody):
    required_history_sha256: str = Field(
        strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )


def _lab_or_404(lab_id: str):
    try:
        return get_reference_lab(lab_id)
    except ValueError:
        raise HTTPException(404, "El laboratorio de referencia no existe.") from None


def _run_not_found() -> NoReturn:
    raise HTTPException(404, "La corrida de referencia no existe.")


def _canonical_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _corrupt() -> NoReturn:
    raise HTTPException(
        409, "Una corrida de referencia guardada está dañada y no se puede mostrar."
    ) from None


def _stored_run(request: Request, lab, run_id: str):
    """Read one validated record scoped to ``lab``; caller must hold the reference-lab lock."""
    if not _canonical_uuid(run_id):
        _run_not_found()
    try:
        record = get_reference_lab_run(request.app.state.repo, run_id)
    except ReferenceLabStoreError:
        _corrupt()
    if record is None or record["lab_id"] != lab.lab_id:
        _run_not_found()
    return record


def _projection(record):
    result = record["result"]
    return {
        "id": record["id"],
        "lab_id": record["lab_id"],
        "contract_version": record["contract_version"],
        "created_at": record["created_at"],
        "config": record["config"],
        "provenance": record["provenance"],
        "summary": {
            "eligible_draws": result["eligible_draws"],
            "gaps": result["gaps"],
            "first": result["first"],
            "last": result["last"],
            "session_sha256": result["session_sha256"],
            "session_count": result["totals"]["sessions_total"],
            "totals": result["totals"],
        },
        "capabilities": dict(_CAPABILITIES),
    }


_SERVICE_ERRORS = {
    "invalid": (422, "La solicitud del laboratorio de referencia no es válida."),
    "not_found": (404, "El laboratorio de referencia no existe."),
    "conflict": (409, "La historia requerida no coincide con la fuente de referencia cargada."),
}


@router.post("/{lab_id}/runs", status_code=201)
def create_lab_run(lab_id: str, body: CreateReferenceLabRun, request: Request):
    lab = _lab_or_404(lab_id)
    state = request.app.state
    # Lock order is fixed: reference-lab lock, then the shared rankings/parity-cache lock.
    with state.reference_lab_lock, state.rankings_lock:
        try:
            execution = execute_reference_lab(lab.lab_id, body.required_history_sha256, state.data)
        except ReferenceLabServiceError as exc:
            status, message = _SERVICE_ERRORS[exc.kind]
            raise HTTPException(status, message) from None
        run_id = str(uuid.uuid4())
        try:
            create_reference_lab_run(
                state.repo,
                run_id,
                lab.lab_id,
                _lab_contract(lab),
                asdict(execution.provenance),
                asdict(execution.result),
                quota_bytes=state.settings.quota_bytes,
                quota_explicit=state.settings.is_quota_explicit,
            )
            record = get_reference_lab_run(state.repo, run_id)
        except QuotaExceeded:
            raise HTTPException(
                409, "No hay espacio suficiente en la cuota para guardar esta corrida."
            ) from None
        except ReferenceLabStoreError as exc:
            _LOG.error("reference-lab run could not be persisted (%s)", type(exc).__name__)
            raise HTTPException(500, "No se pudo guardar la corrida de referencia.") from None
        if record is None:
            _LOG.error("reference-lab run vanished after persistence")
            raise HTTPException(500, "No se pudo guardar la corrida de referencia.")
    return _projection(record)


@router.get("/{lab_id}/runs")
def list_lab_runs(
    lab_id: str,
    request: Request,
    offset: int = Query(0, ge=0, le=_MAX_I64),
    limit: int = Query(20, ge=1, le=100),
):
    lab = _lab_or_404(lab_id)
    with request.app.state.reference_lab_lock:
        try:
            return list_reference_lab_runs(
                request.app.state.repo, lab_id=lab.lab_id, offset=offset, limit=limit
            )
        except ReferenceLabStoreError:
            _corrupt()


@router.get("/{lab_id}/runs/{run_id}/sessions")
def lab_run_sessions(
    lab_id: str,
    run_id: str,
    request: Request,
    offset: int = Query(0, ge=0, le=_MAX_I64),
    limit: int = Query(50, ge=1, le=100),
):
    lab = _lab_or_404(lab_id)
    with request.app.state.reference_lab_lock:
        record = _stored_run(request, lab, run_id)
    sessions = record["sessions"]
    return {
        "run_id": record["id"],
        "total": len(sessions),
        "offset": offset,
        "limit": limit,
        "items": [
            {"ordinal": ordinal, "summary": summary}
            for ordinal, summary in enumerate(sessions[offset : offset + limit], start=offset)
        ],
    }


@router.get("/{lab_id}/runs/{run_id}")
def get_lab_run(lab_id: str, run_id: str, request: Request):
    lab = _lab_or_404(lab_id)
    with request.app.state.reference_lab_lock:
        record = _stored_run(request, lab, run_id)
    return _projection(record)


@router.delete("/{lab_id}/runs/{run_id}", status_code=204)
def delete_lab_run(lab_id: str, run_id: str, request: Request):
    lab = _lab_or_404(lab_id)
    with request.app.state.reference_lab_lock:
        _stored_run(request, lab, run_id)  # scope + integrity check before any deletion
        if not delete_reference_lab_run(request.app.state.repo, run_id):
            _run_not_found()
