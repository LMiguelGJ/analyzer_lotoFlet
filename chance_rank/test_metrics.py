"""Descriptive metrics: Top-K summaries, waits/Kaplan-Meier, horizons, probabilistic
calibration, breakdowns and cross-model agreement."""

import numpy as np
import pytest

from chance_rank import protocol
from chance_rank.metrics import (
    breakdown,
    hit_correlation,
    horizon_summary,
    jaccard_topk,
    kaplan_meier,
    prob_summary,
    topk_summary,
    waits,
)

# --- topk_summary: positional -------------------------------------------------------


def test_topk_summary_positional_hand_example():
    ranks = np.array([0, 5, 24, 25, 99], dtype=np.uint8)
    mask = np.ones(5, dtype=bool)
    result = topk_summary(ranks, mask, k=25)
    assert result["n"] == 5
    assert result["hits"] == 3
    assert result["rate"] == pytest.approx(0.6)
    assert result["lift_pp"] == pytest.approx(0.35)
    assert result["relative"] == pytest.approx(1.4)
    assert result["mean_rank"] == pytest.approx(30.6)
    assert result["median_rank"] == pytest.approx(24.0)
    expected_mrr = np.mean([1 / 1, 1 / 6, 1 / 25, 1 / 26, 1 / 100])
    assert result["mrr"] == pytest.approx(expected_mrr)


def test_topk_summary_positional_respects_mask():
    ranks = np.array([0, 99, 0, 99], dtype=np.uint8)
    mask = np.array([True, False, True, False])
    result = topk_summary(ranks, mask, k=25)
    assert result["n"] == 2
    assert result["hits"] == 2
    assert result["rate"] == pytest.approx(1.0)


def test_topk_summary_positional_zero_targets_is_none():
    ranks = np.array([0, 1], dtype=np.uint8)
    mask = np.zeros(2, dtype=bool)
    result = topk_summary(ranks, mask, k=25)
    assert result["n"] == 0
    assert result["rate"] is None


# --- topk_summary: any-target with duplicate values ---------------------------------


def test_topk_summary_any_target_with_duplicate_values():
    ranks = np.array([[10, 10, 30, 5, 2], [26, 27, 28, 29, 30]], dtype=np.int64)
    nums = np.array([[3, 3, 7, 9, 11], [1, 2, 3, 4, 5]], dtype=np.int64)
    mask = np.ones(2, dtype=bool)
    result = topk_summary(ranks, mask, k=25, nums=nums)
    assert result["n"] == 2
    assert result["at_least_one_rate"] == pytest.approx(0.5)
    assert result["mean_positions_hit"] == pytest.approx(2.0)  # (4 + 0) / 2
    assert result["mean_distinct_values_hit"] == pytest.approx(1.5)  # (3 + 0) / 2
    assert result["reference_independent"] == pytest.approx(1 - 0.75 ** 5)


def test_topk_summary_any_target_requires_nums():
    ranks = np.zeros((1, 5), dtype=np.int64)
    mask = np.ones(1, dtype=bool)
    with pytest.raises(ValueError):
        topk_summary(ranks, mask, k=25)


# --- waits: spells restart at segment start or after a hit, censored at segment end --


def test_waits_hand_computed_with_censoring():
    hit_bool = np.array([False, False, True, False, True, False, False, False, True, False])
    mask = np.ones(10, dtype=bool)
    segment = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    durations, events = waits(hit_bool, mask, segment)
    assert durations.tolist() == [3, 2, 4, 1]
    assert events.tolist() == [True, True, True, False]


def test_waits_only_considers_masked_targets():
    hit_bool = np.array([False, True, False, True])
    mask = np.array([True, False, True, True])
    segment = np.array([0, 0, 0, 0])
    durations, events = waits(hit_bool, mask, segment)
    # row 1 is unmasked: it closes the spell open from row 0 as censored, row 2
    # starts a fresh spell that closes as an event at row 3
    assert durations.tolist() == [1, 2]
    assert events.tolist() == [False, True]


def test_waits_first_masked_row_of_a_segment_hit_is_an_event_of_duration_one():
    hit_bool = np.array([False, True])
    mask = np.array([False, True])
    segment = np.array([0, 0])
    durations, events = waits(hit_bool, mask, segment)
    assert durations.tolist() == [1]
    assert events.tolist() == [True]


def test_waits_hits_at_first_masked_row_of_each_segment_are_all_events_of_duration_one():
    hit_bool = np.array([False, True, False, True, False, True])
    mask = np.array([False, True, False, True, False, True])
    segment = np.array([0, 0, 1, 1, 2, 2])
    durations, events = waits(hit_bool, mask, segment)
    assert durations.tolist() == [1, 1, 1]
    assert events.tolist() == [True, True, True]


def test_kaplan_meier_hand_computed():
    durations = np.array([3, 2, 4, 1])
    events = np.array([True, True, True, False])
    result = kaplan_meier(durations, events, max_n=5)
    expected_survival = [1.0, 2 / 3, 1 / 3, 0.0, 0.0]
    assert result["survival"] == pytest.approx(expected_survival, abs=1e-9)
    assert result["median"] == 3
    assert result["n_censored"] == 1
    assert result["longest_miss_streak"] == 3


def test_kaplan_meier_no_events_median_is_none():
    durations = np.array([5, 6])
    events = np.array([False, False])
    result = kaplan_meier(durations, events, max_n=3)
    assert result["median"] is None
    assert result["n_censored"] == 2


# --- horizon_summary ------------------------------------------------------------------


def test_horizon_summary_hand_computed():
    block_ranks = np.array([[0, 10, 3, 50], [30, 2, 40, 1], [50, 60, 70, 80]], dtype=np.int64)
    result = horizon_summary(block_ranks, k=5, H=2)
    assert result["n_blocks"] == 3
    assert result["mean_hits"] == pytest.approx(2 / 3)
    assert result["p_at_least_one"] == pytest.approx(2 / 3)


def test_horizon_summary_no_blocks_is_none():
    block_ranks = np.empty((0, 4), dtype=np.int64)
    result = horizon_summary(block_ranks, k=5, H=2)
    assert result["n_blocks"] == 0
    assert result["mean_hits"] is None
    assert result["p_at_least_one"] is None


# --- prob_summary: log-loss/Brier vs uniform reference, calibration bins ------------


def test_prob_summary_hand_computed():
    p_true = np.array([0.5, 0.02, 0.9, 0.01])
    brier = np.array([0.1, 0.5, 0.05, 0.6])
    top25_mass = np.array([0.1, 0.35, 0.62, 0.95])
    hits25 = np.array([True, False, True, False])
    mask = np.ones(4, dtype=bool)

    result = prob_summary(p_true, brier, top25_mass, hits25, mask)

    expected_log_loss = np.mean(-np.log(np.maximum(p_true, 1e-12)))
    assert result["mean_log_loss"] == pytest.approx(expected_log_loss)
    assert result["uniform_log_loss"] == pytest.approx(np.log(100))
    assert result["mean_brier"] == pytest.approx(np.mean(brier))
    assert result["uniform_brier"] == pytest.approx(0.99)

    assert len(result["calibration"]) == protocol.CALIBRATION_BINS
    by_bin = {b["bin"]: b for b in result["calibration"]}
    assert by_bin[1]["count"] == 1
    assert by_bin[1]["mean_mass"] == pytest.approx(0.1)
    assert by_bin[1]["hit_rate"] == pytest.approx(1.0)
    assert by_bin[3]["count"] == 1
    assert by_bin[3]["hit_rate"] == pytest.approx(0.0)
    assert by_bin[6]["count"] == 1
    assert by_bin[6]["hit_rate"] == pytest.approx(1.0)
    assert by_bin[9]["count"] == 1
    assert by_bin[9]["hit_rate"] == pytest.approx(0.0)
    empty_bins = [b for b in result["calibration"] if b["bin"] not in (1, 3, 6, 9)]
    for b in empty_bins:
        assert b["count"] == 0
        assert b["mean_mass"] is None
        assert b["hit_rate"] is None


# --- breakdown: generic per-group n/rate -----------------------------------------------


def test_breakdown_hand_computed():
    values = np.array([True, False, True, True, False, True])
    groups = np.array([0, 0, 1, 1, 2, 2])
    mask = np.array([True, True, True, True, True, False])
    result = breakdown(values, groups, mask)
    assert result[0] == {"n": 2, "rate": pytest.approx(0.5)}
    assert result[1] == {"n": 2, "rate": pytest.approx(1.0)}
    assert result[2] == {"n": 1, "rate": pytest.approx(0.0)}


# --- hit_correlation: phi coefficient of two hit indicators --------------------------


def test_hit_correlation_perfect_and_zero():
    mask = np.ones(4, dtype=bool)
    identical = np.array([True, True, False, False])
    assert hit_correlation(identical, identical, mask) == pytest.approx(1.0)

    a = np.array([True, True, False, False])
    b = np.array([True, False, True, False])
    assert hit_correlation(a, b, mask) == pytest.approx(0.0, abs=1e-9)


def test_hit_correlation_zero_variance_is_none():
    mask = np.ones(4, dtype=bool)
    constant = np.array([True, True, True, True])
    other = np.array([True, False, True, False])
    assert hit_correlation(constant, other, mask) is None


# --- jaccard_topk: overlap of top-k sets between two score matrices ------------------


def test_jaccard_topk_hand_computed():
    S_a = np.zeros((2, 100))
    S_b = np.zeros((2, 100))
    S_a[0] = 100 - np.arange(100)  # top3 best-first: 0, 1, 2
    S_b[0] = np.arange(100, dtype=np.float64)
    S_b[0, [2, 3, 4]] = [200, 199, 198]  # top3 best-first: 2, 3, 4
    same_row = 100 - np.arange(100)
    S_a[1] = same_row
    S_b[1] = same_row
    mask = np.ones(2, dtype=bool)

    result = jaccard_topk(S_a, S_b, k=3, mask=mask)
    assert result[0] == pytest.approx(1 / 5)  # {0,1,2} vs {2,3,4} -> 1/5
    assert result[1] == pytest.approx(1.0)
