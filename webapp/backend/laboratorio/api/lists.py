"""Selectable number lists: catalog listing and the persisted active list."""

from fastapi import APIRouter, HTTPException, Request

from laboratorio.api import StrictBody
from laboratorio.engine.list_catalog import ListError

router = APIRouter(prefix="/lists")


class ActiveList(StrictBody):
    id: str


def _listing(request: Request) -> list[dict]:
    catalog = request.app.state.lists
    active = catalog.active_id()
    return [
        {
            "id": item.definition.id,
            "name": item.definition.name,
            "positions": item.definition.positions,
            "draws": item.draws,
            "first_label": item.first_label,
            "last_label": item.last_label,
            "active": item.definition.id == active,
            "available": item.available,
        }
        for item in catalog.summaries()
    ]


@router.get("")
def list_lists(request: Request):
    return _listing(request)


@router.put("/active")
def set_active_list(body: ActiveList, request: Request):
    try:
        request.app.state.lists.set_active(body.id)
    except ListError as exc:
        raise HTTPException(422 if exc.kind == "unknown" else 409, exc.message) from None
    return _listing(request)
