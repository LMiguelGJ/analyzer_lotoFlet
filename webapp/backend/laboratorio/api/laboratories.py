"""Manual laboratory-definition collection and detail resources."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field, StrictInt, StrictStr

from laboratorio.api import StrictBody, repo
from laboratorio.domain.laboratories import LaboratoryConfig
from laboratorio.storage.laboratory_store import (
    LaboratoryDefinitionConflict,
    LaboratoryStoreError,
    create_laboratory_definition,
    delete_laboratory_definition,
    get_laboratory_definition,
    get_laboratory_owned_counts,
    list_laboratory_definitions,
)
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


@router.post("", status_code=201)
def create_laboratory(body: CreateLaboratory, request: Request):
    try:
        config = LaboratoryConfig.from_mapping(body.config)
        settings = request.app.state.settings
        definition = create_laboratory_definition(
            repo(request),
            body.name,
            config,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
    except (LaboratoryDefinitionConflict, QuotaExceeded):
        raise HTTPException(
            409, "No se pudo crear el laboratorio por un conflicto o límite de cuota."
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
    limit: int = Query(20, ge=1, le=100),
):
    try:
        page = list_laboratory_definitions(repo(request), offset=offset, limit=limit)
    except LaboratoryStoreError:
        raise _corrupt() from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {**page, "items": [_snapshot(item) for item in page["items"]]}


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
