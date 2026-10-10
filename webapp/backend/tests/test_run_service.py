import threading
import time

import pytest

from laboratorio.domain.runs import RunConfig, run_sessions
from laboratorio.engine.run_data import RunStrategy, RunWindow, build_run_rows, source_from_lab
from laboratorio.engine.run_service import RunSpec, RunSpecError, execute_run


def _spec(**changes):
    values = {
        "name": None,
        "positions": 3,
        "prizes": (60, 10, 5),
        "minimum_stake": 1,
        "kind": "mix",
        "components": (("transition", 60), ("cold", 40)),
        "coverage": 10,
        "capital": 2000,
        "goal": 2800,
        "max_draws": None,
        "start_date": None,
        "end_date": None,
        "history_sha256": None,
    }
    return RunSpec(**(values | changes))


def test_service_example_matches_independent_engine_and_persists(repo, lab_data, run_environment):
    catalog, settings = run_environment
    report = execute_run(_spec(), catalog=catalog, repo=repo, settings=settings, rankings_cache={})
    rows = build_run_rows(
        source_from_lab(lab_data),
        lab_data.rankings,
        RunStrategy("mix", (("transition", 60), ("cold", 40)), 10),
        RunWindow(None, None),
    )
    result = run_sessions(RunConfig(2000, 2800, 10, 3, (60, 10, 5), 1), rows.rows)
    assert report["name"] == "Transición 60 % + Fríos 40 % · 10 números"
    totals = report["summary"]["totals"]
    assert totals["sessions"] == result.totals.sessions
    assert totals["bets"] == result.totals.bets
    assert totals["net"] == result.totals.net
    assert totals["return_pct"] == result.totals.return_pct
    assert report["summary"]["window"]["first_label"] == rows.first_label
    assert report["summary"]["window"]["last_label"] == rows.last_label
    saved = repo.page_run_sessions(report["id"], 0, 1)[1][0]
    assert saved["ordinal"] == result.sessions[0].ordinal
    assert saved["outcome"] == result.sessions[0].outcome
    assert saved["final_balance"] == result.sessions[0].final_balance
    assert repo.get_run(report["id"]) == report


def test_service_limit_window_parity_and_repeat(repo, lab_data, run_environment):
    catalog, settings = run_environment
    limited = execute_run(
        _spec(max_draws=12),
        catalog=catalog,
        repo=repo,
        settings=settings,
        rankings_cache={},
    )
    sessions, first_page = repo.page_run_sessions(limited["id"], 0, 100)
    assert sessions > 100
    items = list(first_page)
    for offset in range(100, sessions, 100):
        items.extend(repo.page_run_sessions(limited["id"], offset, 100)[1])
    limit_sessions = [item for item in items if item["outcome"] == "limit"]
    assert limit_sessions and all(item["draws"] == 12 for item in limit_sessions)
    assert limited["summary"]["detail"]["status"] in ("complete", "partial")
    windowed = execute_run(
        _spec(kind="parity", components=(), start_date="2025-09-02", end_date="2025-09-10"),
        catalog=catalog,
        repo=repo,
        settings=settings,
        rankings_cache={},
    )
    assert windowed["name"] == "Paridad · 10 números"
    assert windowed["summary"]["window"]["draws"] > 0
    repeat = execute_run(
        _spec(),
        catalog=catalog,
        repo=repo,
        settings=settings,
        rankings_cache={},
    )
    assert repeat["id"] != limited["id"]
    repeat_again = execute_run(
        _spec(),
        catalog=catalog,
        repo=repo,
        settings=settings,
        rankings_cache={},
    )
    assert repeat_again["id"] != repeat["id"]
    assert repeat["summary"]["totals"] == repeat_again["summary"]["totals"]
    assert repeat["summary"]["totals"] == repo.get_run(repeat["id"])["summary"]["totals"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"goal": 2000}, "La meta debe ser mayor que el capital."),
        (
            {"capital": 9},
            "El capital no alcanza para la primera apuesta (cobertura \u00d7 apuesta mínima).",
        ),
        (
            {"components": (("transition", 50), ("cold", 40))},
            "Los porcentajes de la mezcla deben sumar 100.",
        ),
        (
            {"components": (("transition", 50), ("transition", 50))},
            "Cada sistema de la mezcla debe ser distinto y existir en el catálogo.",
        ),
        (
            {"components": (("bogus", 100),)},
            "Cada sistema de la mezcla debe ser distinto y existir en el catálogo.",
        ),
        ({"coverage": 0}, "La cobertura debe estar entre 1 y 50 números."),
        ({"positions": 2}, "Cada posición necesita un premio entero de al menos 1."),
        (
            {"start_date": "2025-02-30"},
            "Las fechas deben tener el formato AAAA-MM-DD y el inicio "
            "no puede ser posterior al fin.",
        ),
        (
            {"start_date": "2024-01-01", "end_date": "2024-01-02"},
            "La ventana elegida no tiene sorteos.",
        ),
        (
            {"start_date": "2025-03-05", "end_date": "2025-09-01"},
            "En esa ventana ningún sorteo tiene ranking para esta estrategia. "
            "Probá con paridad o una ventana desde 2025-09-02.",
        ),
    ],
)
def test_service_validation_errors(repo, run_environment, changes, message):
    catalog, settings = run_environment
    with pytest.raises(RunSpecError) as error:
        execute_run(
            _spec(**changes), catalog=catalog, repo=repo, settings=settings, rankings_cache={}
        )
    assert error.value.message == message


def test_service_schema_determinism(repo, run_environment):
    catalog, settings = run_environment
    first = execute_run(
        _spec(name="Deterministic"),
        catalog=catalog,
        repo=repo,
        settings=settings,
        rankings_cache={},
    )
    second = execute_run(
        _spec(name="Deterministic"),
        catalog=catalog,
        repo=repo,
        settings=settings,
        rankings_cache={},
    )
    assert first["id"] != second["id"]
    assert first["summary"]["totals"] == second["summary"]["totals"]
    assert first["schema_version"] == 1
    fresh = type(repo)(repo.path)
    assert fresh.get_run(first["id"]) == first


def test_service_lock_serializes_execution(repo, run_environment, monkeypatch):
    from laboratorio.engine import run_service

    catalog, settings = run_environment
    guard = threading.Lock()
    active = 0
    maximum = 0

    def fake_execute(*args, **kwargs):
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.02)
        with guard:
            active -= 1
        return {"ok": True}

    monkeypatch.setattr(run_service, "_execute", fake_execute)
    lock = threading.Lock()
    barrier = threading.Barrier(3)

    def invoke():
        barrier.wait()
        return run_service.execute_run(
            _spec(),
            catalog=catalog,
            repo=repo,
            settings=settings,
            rankings_cache={},
            lock=lock,
        )

    threads = [threading.Thread(target=invoke) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert maximum == 1


def test_service_pin_uses_older_snapshot_after_import(repo, run_environment):
    from laboratorio.engine.history_merge import canonical_history_bytes

    catalog, settings = run_environment
    original = catalog.active()
    imported = catalog.import_history(
        canonical_history_bytes(["2026-09-26 00:00"], [[1, 2, 3, 4, 5]])
    ).snapshot
    assert imported.sha256 != original.sha256
    pinned = execute_run(
        _spec(history_sha256=original.sha256),
        catalog=catalog,
        repo=repo,
        settings=settings,
        rankings_cache={},
    )
    assert pinned["config"]["history"]["sha256"] == original.sha256
    assert pinned["config"]["history"]["sha256"] != catalog.active().sha256
