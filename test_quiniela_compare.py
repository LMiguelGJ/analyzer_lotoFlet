"""Small synthetic contracts for a single historical Quiniela scenario."""

from types import SimpleNamespace

import numpy as np
import pytest

import quiniela_compare as compare


def history_and_context(numbers, row_ids):
    history = SimpleNamespace(nums=np.asarray(numbers, dtype=np.uint8))
    rows = np.asarray(row_ids, dtype=np.int64)
    context = compare.RankingContext(rows, np.zeros(len(rows), dtype=np.int64),
                                     {}, "first", "last", 0)
    return history, context


def test_single_archived_family_matches_existing_record_for_both_settlements(monkeypatch):
    history, context = history_and_context(
        [[20, 21, 22, 23, 24], [7, 7, 7, 7, 7],
         [20, 21, 22, 23, 24], [7, 7, 7, 7, 7],
         [20, 21, 22, 23, 24], [7, 7, 7, 7, 7]], [1, 3, 5]
    )
    ranks = np.tile(np.r_[7, np.arange(100)[np.arange(100) != 7]], (3, 1)).astype(np.uint8)
    calls = []

    def one_family(path, system, supplied_context):
        calls.append((path, system, supplied_context))
        return ranks

    monkeypatch.setattr(compare, "ranking_family", one_family)
    for mode in ("all", "best"):
        payments, first = compare.selected_payments(history.nums[context.row_ids],
                                                     ranks, 1, mode)
        expected = compare._record("history", "cold", 1, "flat", mode,
                                   compare.replay("flat", 1, payments, first,
                                                  capital=50, goal=60), 50)
        actual = compare.historical_scenario(history, "archive.npz", "cold", 1,
                                             "flat", mode, context, 50, 60)
        assert actual == expected
    assert calls == [("archive.npz", "cold", context)] * 2
    assert actual["source"] == "history"
    assert actual["seed"] is None
    assert actual["total_steps"] == 3


def test_context_is_loaded_only_when_not_supplied(monkeypatch):
    history, context = history_and_context([[1, 2, 3, 4, 5], [7, 7, 7, 7, 7]], [1])
    calls = []
    monkeypatch.setattr(compare, "ranking_context",
                        lambda h, p: calls.append((h, p)) or context)
    monkeypatch.setattr(compare, "ranking_family",
                        lambda *args: np.tile(np.arange(100, dtype=np.uint8), (1, 1)))
    row = compare.historical_scenario(history, "archive.npz", "mix", 1, "flat",
                                      capital=50, goal=60)
    assert calls == [(history, "archive.npz")]
    assert row["total_steps"] == 1


@pytest.mark.parametrize("system,k,style,mode,capital,goal", [
    ("random", 1, "flat", "all", 50, 60),
    ("logistic", 1, "flat", "all", 50, 60),
    ("parity", 1, "flat", "all", 50, 60),
    ("parity", 50, "flat", "all", 49, 60),
    ("cold", 2, "flat", "all", 50, 60),
    ("cold", True, "flat", "all", 50, 60),
    ("cold", 1, "unknown", "all", 50, 60),
    ("cold", 1, "flat", "other", 50, 60),
    ("cold", 1, "flat", "all", 0, 60),
    ("cold", 1, "flat", "all", 50, 50),
    ("cold", 50, "ladder", "all", 49, 100),
])
def test_invalid_inputs_rejected_before_archive_or_consensus(
        monkeypatch, system, k, style, mode, capital, goal):
    history, _ = history_and_context([[1, 2, 3, 4, 5]], [0])

    def forbidden(*args):
        pytest.fail("invalid input reached expensive work")

    monkeypatch.setattr(compare, "ranking_context", forbidden)
    monkeypatch.setattr(compare, "ranking_family", forbidden)
    monkeypatch.setattr(compare, "consensus_parity", forbidden)
    with pytest.raises(ValueError):
        compare.historical_scenario(history, "archive.npz", system, k, style,
                                    mode, capital=capital, goal=goal)


def test_parity_uses_full_history_before_row_selection_and_skips_gaps(monkeypatch):
    history, context = history_and_context(
        [[61, 61, 61, 61, 61], [61, 61, 61, 61, 61],
         [60, 60, 60, 60, 60], [61, 61, 61, 61, 61],
         [60, 60, 60, 60, 60], [60, 60, 60, 60, 60],
         [61, 61, 61, 61, 61]], [3, 6]
    )
    observed = []

    def consensus(first_numbers):
        observed.append(first_numbers.copy())
        return np.asarray([0, 0, 0, 1, 0, 0, 0], dtype=np.int8)

    monkeypatch.setattr(compare, "consensus_parity", consensus)
    monkeypatch.setattr(compare, "ranking_family",
                        lambda *args: pytest.fail("parity must not read ranking families"))
    even = np.arange(0, 100, 2, dtype=np.uint8)
    odd = np.arange(1, 100, 2, dtype=np.uint8)
    ranks = np.stack([np.r_[odd, even], np.r_[even, odd]])
    payments, first = compare.selected_payments(history.nums[context.row_ids],
                                                 ranks, 50, "all")
    expected = compare._record("history", "parity", 50, "flat", "all",
                               compare.replay("flat", 50, payments, first,
                                              capital=100, goal=180), 100)
    actual = compare.historical_scenario(history, "archive.npz", "parity", 50,
                                         "flat", context=context, capital=100, goal=180)
    assert len(observed) == 1
    np.testing.assert_array_equal(observed[0], history.nums[:, 0])
    assert actual == expected
    assert actual["total_steps"] == 2  # Not seven calendar draws.


def test_parity_predictor_replays_unselected_prior_draws():
    history, context = history_and_context(
        [[61, 61, 61, 61, 61]] * 5 + [[60, 60, 60, 60, 60]] * 2,
        [3, 6],
    )
    full_votes = compare.consensus_parity(history.nums[:, 0])[context.row_ids]
    isolated_votes = compare.consensus_parity(history.nums[context.row_ids, 0])
    assert full_votes[0] != isolated_votes[0]
    even = np.arange(0, 100, 2, dtype=np.uint8)
    odd = np.arange(1, 100, 2, dtype=np.uint8)
    ranks = np.where(full_votes[:, None] == 0, np.r_[even, odd], np.r_[odd, even])
    payments, first = compare.selected_payments(history.nums[context.row_ids],
                                                 ranks, 50, "all")
    expected = compare._record("history", "parity", 50, "flat", "all",
                               compare.replay("flat", 50, payments, first,
                                              capital=100, goal=180), 100)
    assert compare.historical_scenario(history, "unused.npz", "parity", 50,
                                       "flat", context=context, capital=100,
                                       goal=180) == expected


def test_incomplete_tail_is_in_window_totals_not_completed_means(monkeypatch):
    history, context = history_and_context(
        [[60, 60, 60, 60, 60]] * 7, [1, 3, 6]
    )
    monkeypatch.setattr(compare, "ranking_family",
                        lambda *args: np.tile(np.arange(100, dtype=np.uint8), (3, 1)))
    row = compare.historical_scenario(history, "archive.npz", "transition", 50,
                                      "flat", context=context, capital=100, goal=180)
    assert (row["completed"], row["incomplete"], row["sessions_total"]) == (1, 1, 2)
    assert (row["goal_count"], row["ruin_count"]) == (0, 1)
    assert row["mean_net"] == -100
    assert row["total_steps"] == 3
    assert (row["total_stake"], row["total_paid"], row["total_net"]) == (150, 0, -150)
    assert row["net_per_draw"] == -50
