"""Reusable strategies; experiments keep their immutable request snapshots."""

from fastapi import APIRouter, HTTPException, Query, Request

from laboratorio.api import StrictBody, configuration, missing, repo
from laboratorio.domain.contracts import Name, Strategy

router = APIRouter(prefix="/configurations")


class ConfigurationBody(StrictBody):
    name: Name
    strategy: Strategy


class ConfirmDelete(StrictBody):
    confirm_id: str


@router.post("", status_code=201)
def create(body: ConfigurationBody, request: Request):
    identifier = repo(request).create_configuration(body.name, body.strategy)
    return configuration(repo(request).get_configuration(identifier))


@router.get("")
def list_all(request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    total, rows = repo(request).page_configurations(offset, limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [configuration(row) for row in rows],
    }


@router.get("/{identifier}")
def detail(identifier: str, request: Request):
    return configuration(missing(repo(request).get_configuration(identifier)))


@router.put("/{identifier}")
def update(identifier: str, body: ConfigurationBody, request: Request):
    if not repo(request).update_configuration(identifier, body.name, body.strategy):
        raise HTTPException(404, "resource not found")
    return detail(identifier, request)


@router.delete("/{identifier}", status_code=204)
def delete(identifier: str, body: ConfirmDelete, request: Request):
    if body.confirm_id != identifier:
        raise HTTPException(400, "confirmation must match configuration id")
    if not repo(request).delete_configuration(identifier):
        raise HTTPException(404, "resource not found")
