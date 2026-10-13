"""Local immutable quiniela profile creation and paginated reads (v2)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import StrictStr

from laboratorio.api import StrictBody, repo
from laboratorio.storage.game_profile_store import (
    MAX_SAFE_INTEGER,
    GameProfileConflict,
    GameProfileStoreError,
    create_game_profile,
    get_game_profile,
    list_game_profiles,
)
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/game-profiles")


class CreateGameProfile(StrictBody):
    name: StrictStr
    rules: dict[str, Any]


def _corrupt():
    return HTTPException(409, "Un perfil guardado está dañado y no se puede mostrar.")


@router.post("", status_code=201)
def create(body: CreateGameProfile, request: Request):
    settings = request.app.state.settings
    try:
        record = create_game_profile(
            repo(request),
            body.name,
            body.rules,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
    except (GameProfileConflict, QuotaExceeded):
        raise HTTPException(
            409, "No se pudo crear el perfil por un conflicto o límite de cuota."
        ) from None
    except GameProfileStoreError:
        raise _corrupt() from None
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise HTTPException(422, "El perfil no es válido: " + str(error)) from None
    return record.to_mapping()


@router.get("")
def collection(
    request: Request,
    offset: int = Query(0, ge=0, le=MAX_SAFE_INTEGER),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        page = list_game_profiles(repo(request), offset=offset, limit=limit)
    except GameProfileStoreError:
        raise _corrupt() from None
    return {**page, "items": [record.to_mapping() for record in page["items"]]}


@router.get("/{profile_id}")
def detail(profile_id: str, request: Request):
    try:
        record = get_game_profile(repo(request), profile_id)
    except GameProfileStoreError:
        raise _corrupt() from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    if record is None:
        raise HTTPException(404, "El perfil de quiniela no existe.")
    return record.to_mapping()
