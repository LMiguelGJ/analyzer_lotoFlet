"""Read-only catalog and detail resources for the fixed reference laboratories."""

from fastapi import APIRouter, HTTPException, Request

from laboratorio.domain.reference_labs import REFERENCE_LABS, get_reference_lab

router = APIRouter(prefix="/reference-labs")
_CONTRACT_VERSION = 1
_CAPABILITIES = {"session_summary": True, "per_bet_trace": False}


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
