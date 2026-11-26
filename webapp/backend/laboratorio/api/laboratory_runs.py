"""Owner-scoped execution and historical results for managed laboratories."""

import copy
import logging
import sqlite3
import threading
import uuid
from collections import OrderedDict
from dataclasses import asdict
from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field

from laboratorio.api import StrictBody
from laboratorio.domain.laboratory_run_snapshots import OwnedLaboratoryRunSnapshot
from laboratorio.domain.laboratory_wallet import derive_wallet
from laboratorio.domain.number_lists import DEFAULT_LIST_ID, get_list
from laboratorio.engine.list_catalog import ListError
from laboratorio.engine.owned_laboratory_service import (
    OwnedLaboratoryServiceError,
    execute_owned_laboratory,
)
from laboratorio.engine.yearly_results import eligible_labels, results_by_year
from laboratorio.storage.laboratory_store import LaboratoryStoreError
from laboratorio.storage.owned_laboratory_run_store import (
    OwnedLaboratoryRunCapacityError,
    OwnedLaboratoryRunStoreError,
)
from laboratorio.storage.paging import MAX_PAGE_SIZE
from laboratorio.storage.quota import QuotaExceeded

router = APIRouter(prefix="/laboratories")
_MAX_I64 = 2**63 - 1
_CAPABILITIES = {"session_summary": True, "per_bet_trace": False}
_LOG = logging.getLogger(__name__)
_BY_YEAR_CACHE_LIMIT = 128
_by_year_cache: OrderedDict = OrderedDict()
_by_year_lock = threading.Lock()


class CreateLaboratoryRun(StrictBody):
    required_history_sha256: str = Field(
        strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )


def _definition(request, identifier):
    try:
        definition = request.app.state.repo.get_laboratory_definition(identifier)
    except LaboratoryStoreError:
        raise HTTPException(409, "Un laboratorio guardado está dañado.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if definition is None:
        raise HTTPException(404, "El laboratorio no existe.")
    return definition


def _corrupt() -> NoReturn:
    raise HTTPException(409, "Una corrida guardada está dañada y no se puede mostrar.") from None


def _stored(request, owner_id, run_id):
    try:
        record = request.app.state.repo.get_owned_laboratory_run(owner_id, run_id)
    except OwnedLaboratoryRunStoreError as exc:
        try:
            canonical = str(uuid.UUID(run_id)) == run_id
        except ValueError:
            canonical = False
        if not canonical:
            raise HTTPException(404, "La corrida no existe.") from None
        _corrupt()
        raise AssertionError("unreachable") from exc
    if record is None:
        raise HTTPException(404, "La corrida no existe.")
    return record


def _by_year(request, snapshot, summary, sessions=None, *, owner_id=None, run_id=None):
    """Per-year result of a saved run, computed on read; ``None`` when it cannot be certified.

    Nothing is stored: the draw labels come from the list's current history. Only the labels are
    used (each session keeps its own stored balance), so the file fingerprint may differ (a
    re-download rewrites its metadata, or appends later draws); the labels up to the run's last
    draw must still match it exactly (same eligible draws, first and last label).
    """
    config = snapshot.definition.config
    try:
        data = request.app.state.lists.lab_data(config.list_id)
    except ListError:
        return None
    labels = eligible_labels(data.history, data.rankings, config.window_start, config.window_end)
    labels = [label for label in labels if label <= summary["last"]]
    if len(labels) != summary["eligible_draws"]:
        return None
    # Keyed by the resolved labels themselves, not the file fingerprint: the fingerprint can
    # change while the labels stay the same, and the labels can change under the same key.
    key = (summary["session_sha256"], hash(tuple(labels)), config.capital)
    with _by_year_lock:
        if key in _by_year_cache:
            _by_year_cache.move_to_end(key)
            return copy.deepcopy(_by_year_cache[key])
    if sessions is None:
        try:
            record = request.app.state.repo.get_owned_laboratory_run(owner_id, run_id)
        except OwnedLaboratoryRunStoreError:
            return None
        if record is None:
            return None
        sessions = record["sessions"]
    rows = results_by_year(
        sessions,
        labels,
        capital=config.capital,
        eligible_draws=summary["eligible_draws"],
        first=summary["first"],
        last=summary["last"],
    )
    if rows is not None:
        with _by_year_lock:
            _by_year_cache[key] = rows
            while len(_by_year_cache) > _BY_YEAR_CACHE_LIMIT:
                _by_year_cache.popitem(last=False)
        rows = copy.deepcopy(rows)
    return rows


def _projection(request, record):
    result = record["result"]
    snapshot = OwnedLaboratoryRunSnapshot.from_mapping(record["snapshot"])
    wallet = derive_wallet(
        record["sessions"], snapshot.definition.config.capital, result["totals"]["total_net"]
    )
    projection = {
        **{
            key: record[key]
            for key in ("id", "owner_laboratory_id", "lab_id", "contract_version", "created_at")
        },
        "snapshot": record["snapshot"],
        "summary": {
            **{
                key: result[key]
                for key in ("eligible_draws", "gaps", "first", "last", "session_sha256")
            },
            "session_count": result["totals"]["sessions_total"],
            "totals": result["totals"],
            "wallet": wallet,
        },
        "capabilities": dict(_CAPABILITIES),
    }
    projection["summary"]["by_year"] = _by_year(
        request, snapshot, projection["summary"], record["sessions"]
    )
    return projection


def _compact_projection(request, record):
    snapshot = OwnedLaboratoryRunSnapshot.from_mapping(record["snapshot"])
    summary = dict(record["summary"])
    summary["by_year"] = _by_year(
        request, snapshot, summary, owner_id=record["owner_laboratory_id"], run_id=record["id"]
    )
    return {
        **{
            key: record[key]
            for key in ("id", "owner_laboratory_id", "lab_id", "contract_version", "created_at")
        },
        "snapshot": record["snapshot"],
        "summary": summary,
        "capabilities": dict(_CAPABILITIES),
    }


def _stored_compact(request, owner_id, run_id):
    try:
        record = request.app.state.repo.get_owned_laboratory_run_summary(owner_id, run_id)
    except OwnedLaboratoryRunStoreError:
        try:
            canonical = str(uuid.UUID(run_id)) == run_id
        except ValueError:
            canonical = False
        if not canonical:
            raise HTTPException(404, "La corrida no existe.") from None
        _corrupt()
    if record is None:
        raise HTTPException(404, "La corrida no existe.")
    return record


@router.post("/{laboratory_id}/runs", status_code=201)
def create_laboratory_run(laboratory_id: str, body: CreateLaboratoryRun, request: Request):
    definition = _definition(request, laboratory_id)
    state = request.app.state
    lab_list = get_list(definition.config.list_id)
    active = state.lists.active()
    if lab_list is None or lab_list.id != active.id:
        name = lab_list.name if lab_list else definition.config.list_id
        raise HTTPException(
            409,
            f"Este laboratorio es de la lista «{name}» y la lista activa es «{active.name}». "
            "Cambia la lista en Ajustes para ejecutarlo.",
        )
    if active.id == DEFAULT_LIST_ID:
        data = state.data  # the frozen Chance Express inputs, exactly as before
    else:
        try:
            data = state.lists.lab_data(active.id)
        except ListError as exc:
            raise HTTPException(409, exc.message) from None
    with state.reference_lab_lock, state.rankings_lock:
        try:
            execution = execute_owned_laboratory(definition, body.required_history_sha256, data)
        except OwnedLaboratoryServiceError as exc:
            if exc.kind == "conflict":
                raise HTTPException(
                    409, "La historia requerida no coincide con la referencia fija."
                ) from None
            if exc.kind == "empty_window":
                raise HTTPException(422, "La ventana elegida no tiene sorteos.") from None
            raise HTTPException(422, "La solicitud del laboratorio no es válida.") from None
        identifier = str(uuid.uuid4())
        try:
            state.repo.create_owned_laboratory_run(
                identifier,
                laboratory_id,
                execution.snapshot,
                asdict(execution.result),
                quota_bytes=state.settings.quota_bytes,
                quota_explicit=state.settings.is_quota_explicit,
            )
            record = state.repo.get_owned_laboratory_run(laboratory_id, identifier)
        except QuotaExceeded:
            raise HTTPException(
                409, "No hay espacio suficiente en la cuota para guardar esta corrida."
            ) from None
        except OwnedLaboratoryRunCapacityError:
            raise HTTPException(
                409, "El resultado completo supera el límite de almacenamiento de una corrida."
            ) from None
        except OwnedLaboratoryRunStoreError:
            raise HTTPException(
                409, "El laboratorio cambió o la corrida no es válida; no se guardó."
            ) from None
        except sqlite3.Error as exc:
            _LOG.error("owned run storage failure (%s)", type(exc).__name__)
            raise HTTPException(500, "No se pudo guardar la corrida.") from None
        if record is None:
            raise HTTPException(500, "La corrida ya no está disponible después de guardarla.")
    return _projection(request, record)


@router.get("/{laboratory_id}/runs")
def list_laboratory_runs(
    laboratory_id: str,
    request: Request,
    offset: int = Query(0, ge=0, le=_MAX_I64),
    limit: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    _definition(request, laboratory_id)
    with request.app.state.reference_lab_lock:
        try:
            return request.app.state.repo.list_owned_laboratory_run_summaries(
                laboratory_id, offset=offset, limit=limit
            )
        except OwnedLaboratoryRunStoreError:
            _corrupt()


@router.get("/{laboratory_id}/runs/{run_id}/sessions")
def laboratory_run_sessions(
    laboratory_id: str,
    run_id: str,
    request: Request,
    offset: int = Query(0, ge=0, le=_MAX_I64),
    limit: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
):
    _definition(request, laboratory_id)
    with request.app.state.reference_lab_lock:
        try:
            page = request.app.state.repo.list_owned_laboratory_run_sessions(
                laboratory_id, run_id, offset=offset, limit=limit
            )
        except OwnedLaboratoryRunStoreError:
            try:
                canonical = str(uuid.UUID(run_id)) == run_id
            except ValueError:
                canonical = False
            if not canonical:
                raise HTTPException(404, "La corrida no existe.") from None
            _corrupt()
    if page is None:
        raise HTTPException(404, "La corrida no existe.")
    return page


@router.get("/{laboratory_id}/runs/{run_id}")
def get_laboratory_run(laboratory_id: str, run_id: str, request: Request):
    _definition(request, laboratory_id)
    with request.app.state.reference_lab_lock:
        record = _stored_compact(request, laboratory_id, run_id)
    return _compact_projection(request, record)
