"""Synchronous run orchestration and persistence boundary."""

import threading
import time
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import uuid4

from laboratorio.domain.contracts import SYSTEMS
from laboratorio.domain.runs import RunConfig, run_sessions
from laboratorio.engine.active_history import HistoryCatalog
from laboratorio.engine.run_data import (
    SYSTEM_LABELS,
    RunStrategy,
    RunWindow,
    build_run_rows,
)
from laboratorio.settings import Settings
from laboratorio.storage.quota import QuotaExceeded
from laboratorio.storage.repository import Repository
from laboratorio.storage.run_trace import pack_run


class RunSpecError(ValueError):
    """Invalid run request with a user-facing Spanish message and stable error kind."""

    def __init__(self, message: str, kind: Literal["invalid", "not_found", "quota"] = "invalid"):
        super().__init__(message)
        self.message = message
        self.kind = kind


@dataclass(frozen=True)
class RunSpec:
    name: str | None
    positions: int
    prizes: tuple[int, ...]
    minimum_stake: int
    kind: str
    components: tuple[tuple[str, int], ...]
    coverage: int
    capital: int
    goal: int
    max_draws: int | None
    start_date: str | None
    end_date: str | None
    history_sha256: str | None


def _fail_validation(spec):
    if type(spec.goal) is int and type(spec.capital) is int and spec.goal <= spec.capital:
        return "La meta debe ser mayor que el capital."
    if (
        type(spec.coverage) is int
        and type(spec.minimum_stake) is int
        and type(spec.capital) is int
        and spec.capital < spec.coverage * spec.minimum_stake
    ):
        return "El capital no alcanza para la primera apuesta (cobertura \u00d7 apuesta mínima)."
    if type(spec.coverage) is not int or not 1 <= spec.coverage <= 50:
        return "La cobertura debe estar entre 1 y 50 números."
    if (
        type(spec.positions) is not int
        or not isinstance(spec.prizes, tuple)
        or len(spec.prizes) != spec.positions
        or any(type(prize) is not int or prize < 1 for prize in spec.prizes)
    ):
        return "Cada posición necesita un premio entero de al menos 1."
    if spec.kind not in ("mix", "parity"):
        return "La estrategia elegida no es válida."
    if spec.kind == "parity" and spec.components != ():
        return "La estrategia de paridad no admite sistemas de mezcla."
    if spec.kind == "mix":
        if not isinstance(spec.components, tuple) or not spec.components:
            return "Cada sistema de la mezcla debe ser distinto y existir en el catálogo."
        if any(not isinstance(item, tuple) or len(item) != 2 for item in spec.components):
            return "Cada sistema de la mezcla debe ser distinto y existir en el catálogo."
        names = [item[0] for item in spec.components]
        if len(names) != len(set(names)) or any(name not in SYSTEMS for name in names):
            return "Cada sistema de la mezcla debe ser distinto y existir en el catálogo."
        percentages = [item[1] for item in spec.components]
        if any(type(percent) is not int or not 1 <= percent <= 100 for percent in percentages):
            return "Los porcentajes de la mezcla deben sumar 100."
        if sum(percentages) != 100:
            return "Los porcentajes de la mezcla deben sumar 100."
    return None


def _default_name(spec):
    if spec.kind == "parity":
        strategy = "Paridad"
    elif len(spec.components) == 1:
        strategy = SYSTEM_LABELS[spec.components[0][0]]
    else:
        strategy = " + ".join(
            f"{SYSTEM_LABELS[system]} {percent} %" for system, percent in spec.components
        )
    return f"{strategy} · {spec.coverage} números"


def _execute(spec, *, catalog, repo, settings, rankings_cache):
    started = time.perf_counter()
    message = _fail_validation(spec)
    if message:
        raise RunSpecError(message)
    name = _default_name(spec) if spec.name is None or spec.name == "" else spec.name
    if not isinstance(name, str) or len(name) > 80:
        raise RunSpecError("El nombre de la corrida no puede superar 80 caracteres.")
    if spec.history_sha256 is None:
        snapshot = catalog.active()
    else:
        snapshot = catalog.snapshot(spec.history_sha256)
        if snapshot is None:
            raise RunSpecError("El historial indicado no existe.", "not_found")
    try:
        config = RunConfig(
            spec.capital,
            spec.goal,
            spec.coverage,
            spec.positions,
            spec.prizes,
            spec.minimum_stake,
            spec.max_draws,
        )
    except (TypeError, ValueError):
        raise RunSpecError("Las reglas y condiciones de la corrida no son válidas.") from None
    try:
        strategy = RunStrategy(spec.kind, spec.components, spec.coverage)
    except (TypeError, ValueError):
        raise RunSpecError("La estrategia elegida no es válida.") from None
    try:
        window = RunWindow(spec.start_date, spec.end_date)
    except (TypeError, ValueError):
        raise RunSpecError(
            "Las fechas deben tener el formato AAAA-MM-DD y el inicio "
            "no puede ser posterior al fin."
        ) from None
    try:
        run_rows = build_run_rows(
            snapshot.source,
            catalog._lab.rankings,
            strategy,
            window,
            parity_votes=catalog.parity_votes(snapshot) if strategy.kind == "parity" else None,
            ranked_only=False,
            cache=rankings_cache,
        )
    except (TypeError, ValueError) as exc:
        if "no draws" in str(exc):
            raise RunSpecError("La ventana elegida no tiene sorteos.") from None
        raise RunSpecError("No se pudieron preparar los sorteos de la ventana elegida.") from None
    if strategy.kind == "mix" and run_rows.ranked_draws == 0:
        raise RunSpecError(
            "En esa ventana ningún sorteo tiene ranking para esta estrategia. "
            "Probá con paridad o una ventana desde 2025-09-02."
        )
    result = run_sessions(config, run_rows.rows)
    elapsed = time.perf_counter() - started
    if result.totals.sessions == 0 and strategy.kind == "mix":
        raise RunSpecError(
            "En esa ventana ningún sorteo tiene ranking para esta estrategia. "
            "Probá con paridad o una ventana desde 2025-09-02."
        )
    packed = pack_run(result, run_rows.rows, config)
    config_payload = {
        "name": name,
        "rules": {
            "positions": spec.positions,
            "prizes": list(spec.prizes),
            "minimum_stake": spec.minimum_stake,
        },
        "strategy": {
            "kind": strategy.kind,
            "components": [
                {"system": system, "percent": percent} for system, percent in spec.components
            ],
            "coverage": spec.coverage,
        },
        "conditions": {"capital": spec.capital, "goal": spec.goal, "max_draws": spec.max_draws},
        "window": {"start_date": spec.start_date, "end_date": spec.end_date},
        "history": {"sha256": snapshot.sha256, "origin": snapshot.origin},
    }
    totals = asdict(result.totals)
    summary = {
        "totals": totals,
        "window": {
            "draws": run_rows.draws,
            "ranked_draws": run_rows.ranked_draws,
            "first_label": run_rows.first_label,
            "last_label": run_rows.last_label,
        },
        "detail": packed.detail,
        "engine_version": 1,
        "elapsed_seconds": elapsed,
    }
    identifier = str(uuid4())
    try:
        created_at = repo.create_run(
            identifier,
            name,
            config_payload,
            summary,
            packed.session_rows,
            quota_bytes=settings.quota_bytes,
            quota_explicit=settings.is_quota_explicit,
        )
    except QuotaExceeded:
        raise RunSpecError(
            "No hay espacio suficiente en la cuota para guardar esta corrida.", "quota"
        ) from None
    return {
        "id": identifier,
        "name": name,
        "created_at": created_at,
        "schema_version": 1,
        "config": config_payload,
        "summary": summary,
    }


def execute_run(
    spec: RunSpec,
    *,
    catalog: HistoryCatalog,
    repo: Repository,
    settings: Settings,
    rankings_cache: dict,
    lock: threading.Lock | None = None,
) -> dict:
    if lock is None:
        return _execute(
            spec, catalog=catalog, repo=repo, settings=settings, rankings_cache=rankings_cache
        )
    with lock:
        return _execute(
            spec, catalog=catalog, repo=repo, settings=settings, rankings_cache=rankings_cache
        )
