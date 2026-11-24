"""Manual laboratory-definition collection and detail resources."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field, StrictInt, StrictStr

from laboratorio.api import StrictBody, repo
from laboratorio.domain.laboratories import LaboratoryConfig, default_window
from laboratorio.domain.number_lists import (
    DEFAULT_LIST_ID,
    PARITY_SYSTEM,
    UNAVAILABLE_REASON,
    system_label,
)
from laboratorio.engine.list_catalog import ListError
from laboratorio.storage.laboratory_store import (
    LaboratoryDefinitionConflict,
    LaboratoryStoreError,
    create_laboratory_definition,
    delete_laboratory_definition,
    get_laboratory_definition,
    get_laboratory_last_runs,
    get_laboratory_owned_counts,
    list_laboratory_definitions,
)
from laboratorio.storage.paging import MAX_PAGE_SIZE
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/laboratories")
_MAX_I64 = 2**63 - 1


class CreateLaboratory(StrictBody):
    name: StrictStr
    config: dict[str, Any]


class DeleteLaboratory(StrictBody):
    confirmed_run_count: StrictInt = Field(ge=0, le=_MAX_I64)


def _corrupt() -> HTTPException:
    return HTTPException(409, "Un laboratorio guardado está dañado y no se puede mostrar.")


def _definition_or_404(definition):
    if definition is None:
        raise HTTPException(404, "El laboratorio no existe.")
    return definition


def _snapshot(definition):
    return definition.to_mapping()


def _config_for_active_list(request: Request, raw: dict) -> dict:
    """Stamp the active list on a new lab's config; a config naming another list is refused."""
    active = request.app.state.lists.active()
    mapping = dict(raw)
    if "list_id" in mapping:
        requested = mapping.pop("list_id")
        if requested != active.id:
            raise HTTPException(
                409,
                f"La lista activa es «{active.name}»: el laboratorio solo puede crearse "
                "para esa lista. Cambia la lista en Ajustes.",
            )
    if active.id != DEFAULT_LIST_ID:
        mapping["list_id"] = active.id
    return mapping


@router.get("/options")
def laboratory_options(request: Request):
    """What a new laboratory can use on the active list (systems, prizes, window, history)."""
    from laboratorio.domain.contracts import SYSTEMS

    lists = request.app.state.lists
    active = lists.active()
    try:
        history = lists.history(active.id)
    except ListError as exc:
        raise HTTPException(409, exc.message) from None
    first = history.labels[0] if history.labels else None
    last = history.labels[-1] if history.labels else None
    start, end = default_window(active.id, first, last)
    systems = []
    for system in (PARITY_SYSTEM, *SYSTEMS):
        entry: dict[str, object] = {"id": system, "label": system_label(system)}
        if system in active.available_systems:
            entry["available"] = True
        else:
            entry["available"] = False
            entry["reason"] = UNAVAILABLE_REASON
        systems.append(entry)
    return {
        "list": {"id": active.id, "name": active.name, "positions": active.positions},
        "systems": systems,
        "prizes": lists.prizes(active.id),
        "window": {"start": start, "end": end},
        "history_sha256": history.sha256,
    }


@router.post("", status_code=201)
def create_laboratory(body: CreateLaboratory, request: Request):
    try:
        config = LaboratoryConfig.from_mapping(_config_for_active_list(request, body.config))
        settings = request.app.state.settings
        definition = create_laboratory_definition(
            repo(request),
            body.name,
            config,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
    except LaboratoryDefinitionConflict:
        raise HTTPException(409, "Ya existe un laboratorio con ese nombre.") from None
    except QuotaExceeded:
        raise HTTPException(
            409,
            "No se pudo crear el laboratorio: no hay espacio libre suficiente en el disco "
            "o se alcanzó el límite de almacenamiento fijado en Ajustes.",
        ) from None
    except LaboratoryStoreError:
        raise _corrupt() from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return _snapshot(definition)


@router.get("")
def list_laboratories(
    request: Request,
    offset: int = Query(0, ge=0, le=_MAX_I64),
    limit: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    try:
        repository = repo(request)
        page = list_laboratory_definitions(repository, offset=offset, limit=limit)
        last_runs = get_laboratory_last_runs(repository, [item.id for item in page["items"]])
    except LaboratoryStoreError:
        raise _corrupt() from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    items = [{**_snapshot(item), "last_run": last_runs.get(item.id)} for item in page["items"]]
    return {**page, "items": items}


@router.get("/{laboratory_id}")
def get_laboratory(laboratory_id: str, request: Request):
    repository = repo(request)
    try:
        definition = get_laboratory_definition(repository, laboratory_id)
        _definition_or_404(definition)
        counts = get_laboratory_owned_counts(repository, laboratory_id)
    except LaboratoryStoreError:
        raise _corrupt() from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if counts is None:
        raise HTTPException(404, "El laboratorio no existe.")
    return {"definition": _snapshot(definition), **counts}


@router.delete("/{laboratory_id}")
def delete_laboratory(laboratory_id: str, body: DeleteLaboratory, request: Request):
    try:
        result = delete_laboratory_definition(
            repo(request),
            laboratory_id,
            confirmed_run_count=body.confirmed_run_count,
        )
    except LaboratoryDefinitionConflict:
        raise HTTPException(409, "El laboratorio cambió; recárgalo antes de eliminarlo.") from None
    except LaboratoryStoreError:
        raise _corrupt() from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if result is None:
        raise HTTPException(404, "El laboratorio no existe.")
    return result
