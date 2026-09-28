"""Row-wise ranking, percentile and tie-break utilities."""

import numpy as np
import pytest

from chance_rank.protocol import rng, tie_priority
from chance_rank.ranking import percentile, rank_matrix, ranking, topk_mask, winner_rank


def test_tie_priority_is_a_permutation_of_100():
    tie = tie_priority()
    assert sorted(tie.tolist()) == list(range(100))


def test_percentile_average_ties_and_range():
    S = np.array([[0.0, 1.0, 1.0, 3.0]])
    pct = percentile(S)
    assert pct.shape == (1, 4)
    assert pct.min() == 0.0
    assert pct.max() == pytest.approx(3 / 3)
    # the two tied middle values share the average rank (2+3)/2 = 2.5 -> (2.5-1)/3
    assert pct[0, 1] == pytest.approx(pct[0, 2])
    assert pct[0, 1] == pytest.approx(1.5 / 3)


def test_percentile_is_between_zero_and_one_for_random_rows():
    S = rng("test-percentile-range").normal(size=(50, 100))
    pct = percentile(S)
    assert pct.min() >= 0.0
    assert pct.max() <= 1.0


def test_ranking_orders_by_score_then_tie_break():
    tie = np.array([2, 0, 1, 3])
    row = np.array([5.0, 5.0, 1.0, 9.0])
    order = ranking(row, tie=tie)
    # v=3 has the highest score alone; v=0 and v=1 tie at 5.0, tie[1]=0 < tie[0]=2 -> v=1 first
    assert order.tolist() == [3, 1, 0, 2]


def test_ranking_matches_default_tie_priority_length():
    row = rng("test-ranking-default").normal(size=100)
    order = ranking(row)
    assert sorted(order.tolist()) == list(range(100))


def test_winner_rank_matches_position_in_ranking_with_random_ties():
    generator = rng("test-winner-rank")
    S = generator.integers(0, 5, size=(30, 100)).astype(np.float64)  # many exact ties
    y = generator.integers(0, 100, size=30)
    ranks = winner_rank(S, y)
    for m in range(30):
        order = ranking(S[m])
        expected = int(np.where(order == y[m])[0][0])
        assert ranks[m] == expected


def test_winner_rank_zero_for_uncontested_best():
    S = np.zeros((1, 100))
    S[0, 7] = 10.0
    y = np.array([7])
    assert winner_rank(S, y).tolist() == [0]


def test_rank_matrix_rows_are_permutations_of_100():
    generator = rng("test-rank-matrix")
    S = generator.normal(size=(10, 100))
    order = rank_matrix(S)
    assert order.dtype == np.uint8
    for row in order:
        assert sorted(row.tolist()) == list(range(100))


def test_rank_matrix_row_matches_single_row_ranking():
    generator = rng("test-rank-matrix-consistency")
    S = generator.normal(size=(5, 100))
    order = rank_matrix(S)
    for m in range(5):
        assert order[m].tolist() == ranking(S[m]).tolist()


def test_topk_mask_matches_ranking_prefix():
    generator = rng("test-topk-mask")
    S = generator.integers(0, 3, size=(8, 100)).astype(np.float64)
    for k in (1, 25, 50):
        mask = topk_mask(S, k)
        assert mask.shape == (8, 100)
        assert mask.sum(axis=1).tolist() == [k] * 8
        for m in range(8):
            top_values = set(ranking(S[m])[:k].tolist())
            assert set(np.where(mask[m])[0].tolist()) == top_values


def test_topk_mask_is_nested_for_increasing_k():
    generator = rng("test-topk-nested")
    S = generator.normal(size=(4, 100))
    mask25 = topk_mask(S, 25)
    mask50 = topk_mask(S, 50)
    assert np.all(mask50 | ~mask25)  # everything in top-25 is also in top-50
