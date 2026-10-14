"""Profile-bound preview, confirmation and bounded reads for v2 histories."""

import hashlib

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import StrictBool, StrictStr

from laboratorio.api import StrictBody, repo
from laboratorio.engine.quiniela_import import (
    HistoryImportError,
    preview_history,
    preview_included_history,
)
from laboratorio.settings import HISTORY_SHA256
from laboratorio.storage.game_profile_store import (
    GameProfileStoreError,
    get_game_profile,
)
from laboratorio.storage.quiniela_history_store import (
    HistorySourceConflict,
    HistorySourceStoreError,
    confirm_history_source,
    get_history_source,
    list_history_sources,
)
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/history-sources")
MAX_SAFE_INTEGER = 2**53 - 1


class PreviewHistoryBody(StrictBody):
    profile_id: StrictStr
    name: StrictStr
    raw_json: StrictStr
    timezone: StrictStr | None = None
    timezone_confirmed: StrictBool = False


class ConfirmHistoryBody(PreviewHistoryBody):
    expected_preview_sha256: StrictStr


class IncludedHistoryBody(StrictBody):
    profile_id: StrictStr
    name: StrictStr = "Historial incluido"


class ConfirmIncludedHistoryBody(IncludedHistoryBody):
    expected_preview_sha256: StrictStr


def _missing_profile():
    return HTTPException(404, "El perfil de quiniela no existe.")


def _corrupt_source():
    return HTTPException(409, "Una fuente de historial guardada está dañada.")


def _get_profile(repository, profile_id):
    try:
        record = get_game_profile(repository, profile_id)
    except (GameProfileStoreError, ValueError):
        raise HTTPException(409, "El perfil seleccionado está dañado.") from None
    if record is None:
        raise _missing_profile()
    return record


def _read_included(request):
    settings = request.app.state.settings
    try:
        raw = settings.history_path.read_bytes()
    except OSError:
        raise HTTPException(409, "El historial incluido no está disponible.") from None
    if hashlib.sha256(raw).hexdigest() != HISTORY_SHA256:
        raise HTTPException(409, "El historial incluido no coincide con la fuente congelada.")
    return raw


def _preview_import(body, request):
    record = _get_profile(repo(request), body.profile_id)
    return preview_history(
        body.raw_json.encode("utf-8"),
        record.profile,
        name=body.name,
        origin="imported",
        timezone=body.timezone,
        timezone_confirmed=body.timezone_confirmed,
    )


def _preview_included(body, request):
    record = _get_profile(repo(request), body.profile_id)
    return preview_included_history(_read_included(request), record.profile, name=body.name)


def _confirm(preview, expected, request):
    if type(expected) is not str or len(expected) != 64:
        raise HTTPException(422, "expected_preview_sha256 debe ser SHA-256 hexadecimal.")
    if preview.preview_sha256 != expected:
        raise HTTPException(409, "La previsualización cambió; no se guardó la fuente.")
    settings = request.app.state.settings
    try:
        record, created = confirm_history_source(
            repo(request),
            preview,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
        if record is None:
            raise HistorySourceStoreError("confirmed source could not be read back")
    except (HistorySourceConflict, HistorySourceStoreError):
        raise HTTPException(409, "No se pudo confirmar la fuente inmutable.") from None
    except QuotaExceeded:
        raise HTTPException(409, "La cuota no permite guardar esta fuente.") from None
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise HTTPException(422, "La fuente no es válida.") from None
    response = record.to_mapping()
    response["created"] = created
    response["source_reference"] = record.reference.to_mapping()
    return response


@router.post("/preview")
def preview_import(body: PreviewHistoryBody, request: Request):
    try:
        return _preview_import(body, request).to_mapping()
    except HistoryImportError as error:
        raise HTTPException(422, "El historial no es compatible: " + str(error)) from None
    except (UnicodeError, TypeError, ValueError, OverflowError, RecursionError) as error:
        raise HTTPException(422, "El historial no es válido: " + str(error)) from None


@router.post("")
def confirm_import(body: ConfirmHistoryBody, request: Request):
    try:
        preview = _preview_import(body, request)
        return _confirm(preview, body.expected_preview_sha256, request)
    except HistoryImportError as error:
        raise HTTPException(422, "El historial no es compatible: " + str(error)) from None
    except (UnicodeError, TypeError, ValueError, OverflowError, RecursionError) as error:
        raise HTTPException(422, "El historial no es válido: " + str(error)) from None


@router.get("")
def collection(
    request: Request,
    offset: int = Query(0, ge=0, le=MAX_SAFE_INTEGER),
    limit: int = Query(20, ge=1, le=100),
    profile_id: str | None = None,
):
    try:
        page = list_history_sources(
            repo(request), offset=offset, limit=limit, profile_id=profile_id
        )
    except HistorySourceStoreError:
        raise _corrupt_source() from None
    return page


@router.get("/{source_id}")
def detail(source_id: str, request: Request):
    try:
        record = get_history_source(repo(request), source_id)
    except HistorySourceStoreError:
        raise _corrupt_source() from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    if record is None:
        raise HTTPException(404, "La fuente de historial no existe.")
    return record.to_mapping()


@router.post("/included/preview")
def preview_included(body: IncludedHistoryBody, request: Request):
    try:
        return _preview_included(body, request).to_mapping()
    except HistoryImportError as error:
        raise HTTPException(422, "El historial incluido no es compatible: " + str(error)) from None
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise HTTPException(422, "El historial incluido no es válido: " + str(error)) from None


@router.post("/included/confirm")
def confirm_included(body: ConfirmIncludedHistoryBody, request: Request):
    try:
        preview = _preview_included(body, request)
        return _confirm(preview, body.expected_preview_sha256, request)
    except HistoryImportError as error:
        raise HTTPException(422, "El historial incluido no es compatible: " + str(error)) from None
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise HTTPException(422, "El historial incluido no es válido: " + str(error)) from None
