"""Contract for explicit Chance Express and counterfactual Quiniela prize profiles."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from strategy_tests.rules import (
    LADDER,
    ORIGINAL70,
    PRIZES,
    QUINIELA80,
    expected_return,
    first_prize_ladder,
    ladder_table,
    payout,
    payout_matrix,
)


def test_prize_profiles_are_explicit_and_immutable():
    assert ORIGINAL70.name == "original70"
    assert ORIGINAL70.prizes == (70, 8, 4, 2, 1)
    assert QUINIELA80.name == "quiniela80"
    assert QUINIELA80.prizes == (80, 8, 4, 2, 1)
    assert PRIZES.tolist() == [70, 8, 4, 2, 1]
    with pytest.raises(FrozenInstanceError):
        QUINIELA80.prizes = (70, 8, 4, 2, 1)
    with pytest.raises(TypeError):
        QUINIELA80.prizes[0] = 70


def test_counterfactual_payouts_and_legacy_default():
    repeated = [5, 5, 1, 2, 3]
    assert payout(repeated, 5, "all", QUINIELA80) == 88
    assert payout(repeated, 5, "best", QUINIELA80) == 80
    assert payout([5, 1, 2, 3, 4], 5, profile=QUINIELA80) == 80
    assert payout([1, 2, 3, 4, 5], 9, profile=QUINIELA80) == 0
    assert payout([1, 2, 3, 4, 5], 4, profile=QUINIELA80) == 2
    assert payout(repeated, 5) == payout(repeated, 5, profile=ORIGINAL70) == 78
    assert payout(repeated, 5, "best") == 70


def test_counterfactual_matrix_matches_scalar_for_every_number():
    nums = np.array([[5, 5, 1, 2, 3], [0, 1, 2, 3, 4], [9, 9, 9, 9, 9]])
    for mode in ("all", "best"):
        matrix = payout_matrix(nums, mode, QUINIELA80)
        assert matrix.shape == (3, 100)
        for i, row in enumerate(nums.tolist()):
            assert all(matrix[i, bet] == payout(row, bet, mode, QUINIELA80)
                       for bet in range(100))
        assert np.array_equal(payout_matrix(nums, mode),
                              payout_matrix(nums, mode, ORIGINAL70))
    assert payout_matrix(nums, "all", QUINIELA80).sum(axis=1).tolist() == [95] * 3
    assert payout_matrix(nums, "best", QUINIELA80)[0, 5] == 80


def test_counterfactual_expected_returns_and_legacy_default():
    assert expected_return("all", QUINIELA80) == pytest.approx(0.95)
    assert expected_return("best", QUINIELA80) == pytest.approx(0.9474159401)
    assert expected_return() == expected_return(profile=ORIGINAL70) == 0.85
    assert expected_return("best") == expected_return("best", ORIGINAL70)


def test_new_ladder_is_precomputed_for_ten_rounds_without_changing_original():
    ladder = first_prize_ladder(QUINIELA80)
    assert len(ladder) == 10
    assert ladder[:3] == (1, 2, 6)
    invested = 0
    for stake, (total, net) in zip(ladder, ladder_table(ladder, profile=QUINIELA80),
                                   strict=True):
        assert stake == max(1, -(-(invested + 10) // (80 - 50)))
        invested += 50 * stake
        assert total == invested
        assert net == 80 * stake - invested
        assert net >= 10
    assert LADDER == (1, 3, 10, 35, 123, 430, 1505, 5268, 18438, 64533)
    assert ladder_table(LADDER) == ladder_table(LADDER, profile=ORIGINAL70)
    assert ladder_table((1,), prize=90, profile=QUINIELA80) == [(50, 40)]


def test_ladder_rejects_unrecoverable_first_prize():
    with pytest.raises(ValueError, match="exceed"):
        first_prize_ladder(ORIGINAL70, numbers=70)
