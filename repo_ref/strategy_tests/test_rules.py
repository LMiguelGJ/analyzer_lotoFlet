"""Hand-computed checks for prize rules and experiment building blocks."""

import numpy as np
import pytest
from scipy.stats import binomtest, norm

from rng_audit.lottery_tests import Draws
from strategy_tests.experiments import (
    _binom,
    _ladder_arrays,
    ages_since,
    conditional_switch,
    e4_doubles,
    e9_next_first,
    money,
    replay_sessions,
    run_lengths,
)
from strategy_tests.rules import (
    LADDER,
    expected_return,
    ladder_table,
    payout,
    payout_matrix,
)
from strategy_tests.run_experiments import e9_section, idea_cell, n_summary


def test_binomial_zero_trials_is_descriptive_not_a_pass():
    result = _binom("E2 empty", "no bets", 0, 0, 0.01)
    assert result["p"] is None
    assert result["observed"] is None
    assert result["n"] == 0
    cell = idea_cell({"tests": [result]}, "E2")
    assert "0/0 pruebas válidas" in cell
    assert "1 N/A" in cell


def test_e9_exact_first_position_and_day_boundaries():
    nums = np.array([[0, 99, 0, 0, 0], [0, 2, 2, 2, 2],
                     [99, 0, 0, 0, 0], [99, 99, 99, 99, 99],
                     [99, 0, 0, 0, 0], [0, 99, 0, 0, 0]])
    d = Draws(nums, np.array([1, 1, 1, 2, 2, 2]), np.arange(6),
              np.zeros(6, dtype=int), np.ones(6, dtype=int))
    result = e9_next_first(d)
    rows, matrix = result["rows"], result["matrix"]
    assert len(rows) == len(matrix) == 100
    assert all(len(row) == 100 for row in matrix)
    assert rows[0] == {"x": "00", "count": 2, "repeats": 1, "rate": 0.5}
    assert rows[99] == {"x": "99", "count": 2, "repeats": 1, "rate": 0.5}
    assert rows[1] == {"x": "01", "count": 0, "repeats": 0, "rate": None}
    assert matrix[0][0] == matrix[0][99] == 1
    assert matrix[99][0] == matrix[99][99] == 1
    assert sum(map(sum, matrix)) == 4  # Not the 1→2 day boundary.
    assert sum(row["count"] for row in rows) == 4
    assert sum(row["repeats"] for row in rows) == sum(matrix[i][i] for i in range(100))
    assert result["expected_rate"] == 0.01
    assert "p" not in result


def test_e9_empty_days_and_report_formatting():
    nums = np.array([[0, 99, 99, 99, 99], [99, 0, 0, 0, 0]])
    d = Draws(nums, np.array([1, 2]), np.arange(2), np.zeros(2, dtype=int),
              np.ones(2, dtype=int))
    result = e9_next_first(d)
    assert sum(map(sum, result["matrix"])) == 0
    assert all(row["rate"] is None for row in result["rows"])
    section = e9_section(result)
    assert "| 00 | 0 | 0 | — | sin casos |" in section
    assert "| 99 | 0 | 0 | — | sin casos |" in section
    assert sum(line.startswith("| ") for line in section) == 101  # header + 100 values
    assert "1%" in "\n".join(section)
    assert "p Holm |" not in "\n".join(section)


def test_n_summary_lists_every_original_variant_and_threshold():
    e1 = [{"id": f"E1 {variant} N={n}", "n": 10, "observed": 0.5}
          for variant in ("par-g1", "par-5g", "alto-g1", "alto-5g")
          for n in range(1, 11)]
    e5 = [{"id": f"E5 {variant} N≥{n}", "n": 20, "observed": 0.4}
          for variant in ("par/impar", "bajo/alto") for n in range(3, 9)]
    section = n_summary({"tests": e1 + e5})
    assert len([line for line in section if line.startswith("| E1 ")]) == 40
    assert len([line for line in section if line.startswith("| E5 ")]) == 12
    assert "| E1 par-g1 N=1 | 10 | 50.00% |" in section
    assert "| E5 bajo/alto N≥8 | 20 | 40.00% |" in section


def test_payout_repeated_number_modes():
    assert payout([5, 5, 1, 2, 3], 5, "all") == 78
    assert payout([5, 5, 1, 2, 3], 5, "best") == 70


def test_payout_miss_and_lower_positions():
    assert payout([1, 2, 3, 4, 5], 9, "all") == 0
    assert payout([1, 2, 3, 4, 5], 4, "all") == 2
    assert payout([7, 1, 2, 3, 7], 7, "best") == 70


def test_payout_matrix_matches_payout():
    nums = np.array([[5, 5, 1, 2, 3], [0, 1, 2, 3, 4], [9, 9, 9, 9, 9]])
    for mode in ("all", "best"):
        matrix = payout_matrix(nums, mode)
        assert matrix.shape == (3, 100)
        for i, row in enumerate(nums.tolist()):
            assert all(matrix[i, bet] == payout(row, bet, mode) for bet in range(100))
    assert payout_matrix(nums, "all").sum(axis=1).tolist() == [85, 85, 85]


def test_expected_return():
    assert expected_return("all") == pytest.approx(0.85)
    assert expected_return("best") == pytest.approx(
        0.70 + 0.08 * 0.99 + 0.04 * 0.99 ** 2 + 0.02 * 0.99 ** 3 + 0.01 * 0.99 ** 4)


def test_ladder_reproduces_screenshot():
    table = ladder_table(LADDER)
    assert [invested for invested, _ in table] == [
        50, 200, 700, 2450, 8600, 30100, 105350, 368750, 1290650, 4517300]
    assert [net for _, net in table] == [20, 10, 0, 0, 10, 0, 0, 10, 10, 10]


def test_ladder_counts_tenth_failure_at_day_end_without_eleventh_bet():
    hp = np.array([[0, 70], [70, 0]])
    stake, paid, lost = _ladder_arrays(
        2, np.array([0, 1]), np.array([0, 0]), np.array([9, 9]), hp)
    assert stake.tolist() == [50 * LADDER[9]] * 2
    assert paid.tolist() == [0, 70 * LADDER[9]]
    assert lost == 1


def test_money_minimum_bankroll_funds_each_wager_before_settlement():
    result = money(np.array([1, 1, 2, 2]), np.array([10, 30, 5, 0]),
                   np.array([20, 0, 0, 0]), np.random.default_rng(1), reps=20)
    assert result is not None
    assert result["min_bankroll"] == 25  # third stake 5 after cumulative net loss of 20
    assert result["max_drawdown"] == 35  # settled equity peak to trough, not starting cash


def test_money_minimum_bankroll_with_zero_stake_and_initial_loss():
    result = money(np.array([1, 1, 1]), np.array([0, 10, 20]),
                   np.array([0, 0, 0]), np.random.default_rng(1), reps=20)
    assert result is not None
    assert result["min_bankroll"] == 30


def test_e4_overlapping_windows_use_day_cluster_inference():
    firsts = ([7, 7, 7, 7], [1, 1, 1, 1], [1, 7, 1, 1])
    nums = np.array([[first, 7, 7, 2, 3] for day in firsts for first in day])
    d = Draws(nums, np.repeat([1, 2, 3], 4), np.tile(np.arange(4), 3),
              np.zeros(12, dtype=int), np.ones(12, dtype=int))
    tests, _ = e4_doubles(d, payout_matrix(nums, "all"))
    row = next(t for t in tests if t["id"] == "E4 1º w=5")
    residual = np.array([6, 0, 1]) - 6 * 0.01
    se = np.sqrt(3 / 2 * np.square(residual - residual.mean()).sum())
    assert row["n"] == 18
    assert row["observed"] == pytest.approx(7 / 18)
    assert row["p"] == pytest.approx(2 * norm.sf(abs(residual.sum() / se)))
    assert row["p"] != pytest.approx(binomtest(7, 18, 0.01).pvalue)


def test_run_lengths_and_switch_within_day():
    series = np.array([0, 0, 0, 1])
    day = np.array([1, 1, 1, 1])
    assert run_lengths(series, day).tolist() == [1, 2, 3, 1]
    assert conditional_switch(series, day, 1) == (0, 1)
    assert conditional_switch(series, day, 2) == (0, 1)
    assert conditional_switch(series, day, 3) == (1, 1)


def test_streaks_never_cross_days():
    series = np.array([0, 0, 0, 1])
    day = np.array([1, 1, 2, 2])
    assert run_lengths(series, day).tolist() == [1, 2, 1, 1]
    assert conditional_switch(series, day, 2) == (0, 0)
    assert conditional_switch(series, day, 1) == (1, 2)


def test_ages_since_last_first_position():
    ages = ages_since(np.array([3, 5, 3]))
    assert ages[0, 3] == 1 and ages[1, 3] == 1 and ages[2, 3] == 2
    assert ages[2, 5] == 1 and ages[2, 7] == 3


def test_bold_play_reaches_goal_on_third_draw():
    out = replay_sessions(np.array([0, 0, 70, 0]), np.array([0]), 1000, 2000, "bold")
    assert out["reached"].tolist() == [True]
    assert out["steps"].tolist() == [3]
    assert out["bank"].tolist() == [2005]


def test_timid_play_stops_when_data_ends():
    out = replay_sessions(np.array([0, 0]), np.array([0]), 1000, 2000, "timid")
    assert out["finished"].tolist() == [False]
    assert out["bank"].tolist() == [980]
