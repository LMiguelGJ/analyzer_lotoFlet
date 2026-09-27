"""Contract tests for the isolated 80-prize counterfactual runner."""

import json

import numpy as np
import pytest

from rng_audit.lottery_tests import Draws
from strategy_tests import experiments as ex
from strategy_tests import run_quiniela80 as runner
from strategy_tests.rules import QUINIELA80, first_prize_ladder, payout_matrix


def draws(first, days):
    nums = np.column_stack((first, np.full((len(first), 4), 99)))
    days = np.asarray(days)
    return Draws(nums, days, np.arange(len(first)), np.zeros(len(first), dtype=int),
                 np.ones(len(first), dtype=int))


def test_training_first_return_selects_without_heldout_leakage():
    d = draws([1, 1, 1, 1], [1, 1, 2, 2])
    train = d.day == 1
    stakes = np.ones(4)
    views = {
        "first": [("A", stakes, np.array([80, 0, 0, 0])),
                  ("B", stakes, np.array([0, 0, 80, 80]))],
        "all": [("A", stakes, np.array([80, 0, 0, 0])),
                ("B", stakes, np.array([100, 100, 90, 90]))],
        "best": [("A", stakes, np.array([80, 0, 0, 0])),
                 ("B", stakes, np.array([10, 10, 80, 80]))],
    }
    result = runner.evaluate_views(d, views, train, np.random.default_rng(7))
    assert result["pick"] == "A"
    assert result["train_ret_first"] == 40
    assert result["held_out"]["first"]["net"] == -2
    assert result["held_out"]["all"]["stake"] == 2
    assert result["held_out"]["best"]["ret"] == 0
    assert result["sensitivity_total_pick"] == "B"
    assert result["sensitivity_total_held_out"]["all"]["ret"] == 90
    assert [r["label"] for r in result["grid"]] == ["A", "B"]
    assert result["grid"][1]["held_out"]["first"]["first_hits"] == 2
    assert result["grid"][1]["held_out"]["first"]["opportunities"] == 2
    assert result["grid"][1]["held_out"]["first"]["stake_units"] == 2
    assert result["grid"][1]["held_out"]["all"]["net"] == 178
    views["best"][0] = ("wrong label", stakes, np.zeros(4))
    with pytest.raises(ValueError, match="labels/stakes"):
        runner.evaluate_views(d, views, train, np.random.default_rng(7))


def test_zero_stakes_and_cost_of_ten_losses():
    d = draws([1, 1, 1, 1], [1, 1, 2, 2])
    zero = np.zeros(4)
    candidates = [("empty", zero, zero)]
    result = runner.evaluate_views(d, dict.fromkeys(runner.VIEWS, candidates),
                                   d.day == 1, np.random.default_rng(7))
    assert result["grid"][0]["held_out"]["all"] is None
    assert result["grid"][0]["held_out"]["first"] is None
    assert result["train_ret_first"] is None
    assert result["sensitivity_total_pick"] is None
    ladder = first_prize_ladder(QUINIELA80)
    assert runner.ladder_cost(ladder) == 50 * sum(ladder)


def test_raw_first_hits_ignore_lower_prizes_and_ladder_losses_are_split():
    d = draws([1] * 26, [1] * 13 + [2] * 13)
    train = d.day == 1
    stake = np.ones(26)
    first = np.zeros(26)
    all_paid = np.ones(26) * 8
    result = runner._money(d.day, stake, all_paid, np.random.default_rng(7),
                           first_paid=first)
    assert result is not None
    assert result["first_hits"] == 0
    assert result["stake_units"] == 26
    assert result["opportunities"] == 26
    pay = {"first": ex.first_position_matrix(d.nums, QUINIELA80),
           "all": payout_matrix(d.nums, "all", QUINIELA80),
           "best": payout_matrix(d.nums, "best", QUINIELA80)}
    ladders = runner.evaluate_ladders(d, pay, train, "par/impar tras ≥3",
                                      np.random.default_rng(7))
    for item in ladders.values():
        row = item["grid"][0]
        assert row["full_data"]["complete_losses"] == 2
        assert row["held_out"]["complete_losses"] == 1
        assert row["held_out"]["first"]["first_hits"] == 0
        assert row["held_out"]["first"]["stake_units"] == 10 * 50
        assert row["held_out"]["all"]["stake"] == row["held_out"]["best"]["stake"]


def test_healthy_e5_all_control_displays_upper_below_reference():
    data = json.loads((runner.REPORT_DIR / "strategy_tests_quiniela80.json").read_text(
        encoding="utf-8"))
    metric = data["results"]["sano (SHA-256)"]["money"]["E5"]["held_out"]["all"]
    reference = data["meta"]["reference"]["all"]
    assert metric["hi"] < reference

    report = runner._report(data["results"], data["meta"])
    line = next(line for line in report.splitlines()
                if line.startswith("- E5 all par/impar tras ≥3:"))
    assert f"IC [{metric['lo']:.6f}, {metric['hi']:.6f}] NO cubre {reference:.10f}" in line
    visible_upper = float(line.split("IC [", 1)[1].split(", ", 1)[1].split("]", 1)[0])
    assert visible_upper < reference


def test_report_structure_and_explicit_counterfactual_metadata(tmp_path, monkeypatch):
    meta = runner.metadata("chance_express_history.json", "abc", 10, 10, 6,
                           "2026-02-09", "2026-02-10", 6)
    assert meta["scenario"] == "hypothetical payout on Chance Express; not Rapidita observations"
    assert meta["prizes"] == [80, 8, 4, 2, 1]
    assert meta["split"]["heldout_from"] == "2026-02-10"
    assert meta["split"]["heldout_draws"] == 4
    assert meta["bootstrap"] == {"repetitions": 2000, "seed": 7, "unit": "day"}
    assert meta["reference"] == {"first": .8, "all": .95,
                                  "best": pytest.approx(.9474159401)}
    view = dict.fromkeys(runner.VIEWS)
    money = {key: {"pick": None, "train_ret_first": None, "held_out": view,
                   "grid": [], "sensitivity_total_pick": None,
                   "sensitivity_total_train_ret": None,
                   "sensitivity_total_held_out": view} for key in ("E2", "E3", "E4", "E5")}
    money["E5_ladders"] = {}
    empty = {"tests": [], "money": money, "sessions": {"all": [], "best": []},
             "repeat_rule": {"real_all": .95, "real_best": .9474, "theory_all": .95,
                             "theory_best": .9474159401, "draws_with_repeat": .1,
                             "theory_draws_with_repeat": .0965}, "sources": {}}
    results = {"Chance Express": {**empty, "e9": {"rows": [
        {"x": f"{i:02d}", "count": 0, "repeats": 0, "rate": None}
        for i in range(100)], "matrix": [[0] * 100 for _ in range(100)]}},
        "sano (SHA-256)": empty, "trampa (4 patrones sembrados)": empty}
    monkeypatch.setattr(runner, "controls_section", lambda _: [])
    runner.write_outputs(results, meta, tmp_path)
    data = json.loads((tmp_path / "strategy_tests_quiniela80.json").read_text(encoding="utf-8"))
    md = (tmp_path / "strategy_tests_quiniela80.md").read_text(encoding="utf-8")
    assert len(data["results"]["Chance Express"]["e9"]["rows"]) == 100
    assert len(data["results"]["Chance Express"]["e9"]["matrix"]) == 100
    assert "contrafactual" in md.lower() and "Rapidita" in md
    assert "0,80" in md and "0,95" in md and "0,9474159401" in md
    assert "E9" in md and "N/A" in md
