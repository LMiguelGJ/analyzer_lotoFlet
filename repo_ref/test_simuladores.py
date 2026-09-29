"""Fast contracts for the 14 historical-only entry points; real replay is opt-in."""

import hashlib
import importlib.util
import os
import re
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import quiniela_compare as compare

ROOT = Path(__file__).resolve().parent.parent
SIMULATORS = ROOT / "simuladores"
# Frozen rows from docs/resumen_resultados_quiniela.md, not inputs to the runner.
EXPECTED = (
    ("transicion_1_audaz", "transition", 1, "bold", 681, 963, 282, 10.3),
    ("frios_1_audaz", "cold", 1, "bold", 684, 974, 290, -3.4),
    ("selector_1_audaz", "select_interpretable", 1, "bold", 663, 946, 283, -8.2),
    ("mezclas_1_audaz", "mix", 1, "bold", 676, 968, 292, -15.6),
    ("ensemble_5_audaz", "ensemble", 5, "bold", 3226, 4720, 1494, -51.2),
    ("ensemble_10_audaz", "ensemble", 10, "bold", 6140, 9061, 2921, -56.9),
    ("ensemble_20_audaz", "ensemble", 20, "bold", 10785, 16086, 5301, -59.2),
    ("frios_25_escalera", "cold", 25, "ladder", 677, 1105, 428, -162.2),
    ("mezclas_50_audaz", "mix", 50, "bold", 12845, 20605, 7760, -117.0),
    ("transicion_50_audaz", "transition", 50, "bold", 12890, 20682, 7792, -116.0),
    ("paridad_50_audaz", "parity", 50, "bold", 12698, 20404, 7706, -120.8),
    ("frios_50_escalera", "cold", 50, "ladder", 1429, 3502, 2073, -98.7),
    ("paridad_50_escalera", "parity", 50, "ladder", 1368, 3496, 2128, -124.4),
    ("paridad_50_plana", "parity", 50, "flat", 13, 91, 78, -1572.8),
)


def test_manifest_is_exact_and_imports_do_not_run(monkeypatch):
    from simuladores import runner

    assert len(EXPECTED) == len({row[0] for row in EXPECTED}) == 14
    assert {p.name for p in SIMULATORS.iterdir() if p.is_dir()} == {row[0] for row in EXPECTED}
    assert len(list(SIMULATORS.glob("*/ejecutar.py"))) == 14
    assert len(list(SIMULATORS.glob("*/README.md"))) == 14
    assert (SIMULATORS / "README.md").exists()

    def forbidden(*args, **kwargs):
        pytest.fail("import must not execute a scenario")

    monkeypatch.setattr(runner, "run", forbidden)
    for name, system, k, style, *_ in EXPECTED:
        script = SIMULATORS / name / "ejecutar.py"
        spec = importlib.util.spec_from_file_location(f"test_adapter_{name}", script)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert (system, k, style) == (module.SYSTEM, module.K, module.STYLE)


@pytest.mark.parametrize("name,system,k,style", [
    ("transicion_1_audaz", "transition", 1, "bold"),
    ("paridad_50_plana", "parity", 50, "flat"),
])
def test_launcher_works_from_own_directory_without_replay(monkeypatch, name, system,
                                                              k, style):
    from simuladores import runner

    calls = []
    monkeypatch.setattr(runner, "main", lambda *args: calls.append(args) or 0)
    script = SIMULATORS / name / "ejecutar.py"
    monkeypatch.chdir(script.parent)
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(script), run_name="__main__")
    assert exit_info.value.code == 0
    assert calls == [(system, k, style)]


def test_runner_one_scenario_and_null_output(monkeypatch, capsys):
    from simuladores import runner

    calls = []
    monkeypatch.setattr(runner, "verify_input", lambda path, digest: calls.append((path, digest)))
    monkeypatch.setattr(runner, "load_validated_history",
                        lambda path: calls.append(("load", path)) or SimpleNamespace(n=9))
    context = SimpleNamespace(row_ids=np.array([1, 3]), fold_id=np.array([0, 0]),
                              first="first", last="last", gaps=1)
    monkeypatch.setattr(runner, "ranking_context",
                        lambda history, path: calls.append(("context", path)) or context)
    record = {"completed": 0, "incomplete": 1, "sessions_total": 1, "goal_count": 0,
              "ruin_count": 0, "goal_rate": None, "ruin_rate": None, "goal_wilson95": None,
              "mean_net": None, "mean_final_balance": None, "median_steps": None,
              "p90_steps": None, "total_stake": 10, "total_paid": 0, "total_net": -10,
              "total_steps": 2}
    monkeypatch.setattr(runner, "historical_scenario",
                        lambda *args, **kwargs: calls.append((args, kwargs)) or record)
    assert runner.run("cold", 1, "bold", argv=[]) == 0
    text = capsys.readouterr().out
    assert calls[:2] == [(runner.HISTORY, runner.HISTORY_SHA256),
                         (runner.RANKINGS, runner.RANKINGS_SHA256)]
    assert calls[-1][0][2:] == ("cold", 1, "bold")
    assert calls[-1][1] == {"mode": "all", "context": context, "capital": 2000,
                             "goal": 2800}
    for fragment in ("Población común: 2", "Completas: 0", "Inconclusas: 1",
                     "Meta: 0/0 (—%)", "Quiebre: 0/0 (—%)", "Wilson", "Mediana",
                     "p90", "Neto medio: RD$—", "SHA-256", "contrafactual"):
        assert fragment.lower() in text.lower()


def test_formatted_completed_metrics_are_derived(capsys):
    from simuladores.runner import _show

    context = SimpleNamespace(row_ids=[1, 3], fold_id=[0, 1],
                              first="first", last="last", gaps=1)
    row = {"completed": 4, "incomplete": 1, "sessions_total": 5,
           "goal_count": 3, "ruin_count": 1, "goal_rate": 0.75, "ruin_rate": 0.25,
           "goal_wilson95": (0.33, 0.96), "mean_net": 10.3,
           "mean_final_balance": 2010.3, "median_steps": 5,
           "p90_steps": 9, "total_stake": 40, "total_paid": 50,
           "total_net": 10, "total_steps": 2}
    _show("cold", 1, "bold", context, SimpleNamespace(n=9), row)
    output = capsys.readouterr().out
    for fragment in ("Meta: 3/4 (75.0%)", "Quiebre: 1/4 (25.0%)",
                     "33.0%–96.0%", "Neto medio: RD$+10.3", "2010.3",
                     "5.0/9.0"):
        assert fragment in output


def test_missing_and_changed_input_fail_before_loading(monkeypatch):
    from simuladores import runner

    monkeypatch.setattr(runner, "load_validated_history",
                        lambda _: pytest.fail("must validate inputs before loading"))
    with pytest.raises(FileNotFoundError, match="Falta"):
        runner.verify_input(SIMULATORS / "nonexistent.json", "a" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        runner.verify_input(Path(__file__), "0" * 64)
    monkeypatch.setattr(runner, "verify_input",
                        lambda *args: (_ for _ in ()).throw(ValueError("SHA-256 mismatch")))
    assert runner.main("cold", 1, "bold", argv=[]) != 0


def test_help_is_side_effect_free(monkeypatch, capsys):
    from simuladores import runner

    monkeypatch.setattr(runner, "verify_input", lambda *args: pytest.fail("help loaded input"))
    with pytest.raises(SystemExit) as exit_info:
        runner.run("cold", 1, "bold", argv=["--help"])
    assert exit_info.value.code == 0
    assert "2000" in capsys.readouterr().out


def test_historical_scenario_equals_existing_grid_for_archived_and_parity(monkeypatch):
    """Bound the old grid, but retain its real selection, settlement and replay."""
    monkeypatch.setattr(compare, "SYSTEMS", ("cold",))
    monkeypatch.setattr(compare, "K_VALUES", (1,))
    history = SimpleNamespace(nums=np.asarray(
        [[61, 61, 61, 61, 61], [60, 60, 60, 60, 60]] * 4, dtype=np.uint8))
    ids = np.asarray([1, 3, 5, 7], dtype=np.int64)
    context = compare.RankingContext(ids, np.zeros(len(ids), dtype=np.int64),
                                     {}, "first", "last", 3)
    ranks = np.tile(np.arange(100, dtype=np.uint8), (len(ids), 1))
    monkeypatch.setattr(compare, "ranking_family", lambda *args: ranks)
    parity_calls = []

    def parity(full_history):
        parity_calls.append(full_history.copy())
        return np.arange(len(full_history), dtype=np.uint8) % 2

    monkeypatch.setattr(compare, "consensus_parity", parity)
    grid = compare.historical_rows(history, "archive.npz", context, capital=100, goal=180)
    for system, k, style in (("cold", 1, "flat"), ("parity", 50, "flat")):
        actual = compare.historical_scenario(history, "archive.npz", system, k, style,
                                             context=context, capital=100, goal=180)
        expected = next(row for row in grid if (row["system"], row["k"], row["style"],
                                               row["mode"]) == (system, k, style, "all"))
        assert actual == expected
    assert len(parity_calls) == 2
    for call in parity_calls:
        np.testing.assert_array_equal(call, history.nums[:, 0])


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.mark.skipif(os.environ.get("QUINIELA_RUN_INTEGRATION") != "1",
                    reason="opt-in real 14-scenario replay; parent runs in SI3")
def test_real_scenarios_from_each_directory_leave_inputs_and_reports_unchanged():
    from simuladores.runner import HISTORY, HISTORY_SHA256, RANKINGS, RANKINGS_SHA256

    protected = (HISTORY, RANKINGS, ROOT / "docs/resumen_resultados_quiniela.md",
                 ROOT / "docs/informe_quiniela_comparacion.md")
    before = {path: _sha256(path) for path in protected}
    assert before[HISTORY] == HISTORY_SHA256
    assert before[RANKINGS] == RANKINGS_SHA256
    try:
        for name, system, k, style, goals, completed, ruined, net in EXPECTED:
            script = SIMULATORS / name / "ejecutar.py"
            process = subprocess.run([sys.executable, "-B", str(script)],
                                     cwd=script.parent, capture_output=True, text=True,
                                     check=False)
            assert process.returncode == 0, (name, process.stderr)
            output = process.stdout
            assert f"Sistema: {system}; k: {k}; Apuesta: {style}; Modo: all" in output
            assert re.search(rf"Meta: {goals}/{completed} \({goals / completed * 100:.1f}%\)", output)
            assert re.search(rf"Quiebre: {ruined}/{completed} "
                             rf"\({ruined / completed * 100:.1f}%\)", output)
            assert f"Completas: {completed}" in output
            assert f"Neto medio: RD${net:+.1f}" in output
    finally:
        assert {path: _sha256(path) for path in protected} == before
