"""Counterfactual payout propagation without changing the original experiments."""

import numpy as np
import pytest

from rng_audit.lottery_tests import Draws
from strategy_tests import experiments as ex
from strategy_tests.rules import (
    LADDER,
    ORIGINAL70,
    QUINIELA80,
    first_prize_ladder,
    payout_matrix,
)


def draws(nums, days=None):
    nums = np.asarray(nums, dtype=np.int64)
    days = np.asarray(days if days is not None else np.ones(len(nums)), dtype=np.int64)
    return Draws(nums, days, np.arange(len(nums)), np.zeros(len(nums), dtype=int),
                 np.ones(len(nums), dtype=int))


def test_first_position_matrix_and_candidate_views_preserve_stakes_and_duplicates():
    d = draws([[5, 5, 1, 2, 3], [7, 5, 5, 2, 3]])
    first = ex.first_position_matrix(d.nums, QUINIELA80)
    assert first.shape == (2, 100)
    assert first[:, 5].tolist() == [80, 0]
    assert first[:, 7].tolist() == [0, 80]
    assert first.sum(axis=1).tolist() == [80, 80]
    assert ex.first_position_matrix(d.nums)[:, 5].tolist() == [70, 0]
    all_pay = payout_matrix(d.nums, "all", QUINIELA80)
    best_pay = payout_matrix(d.nums, "best", QUINIELA80)
    for experiment in (ex.e2_cold, ex.e3_carry, ex.e4_doubles, ex.e5_streak_entry):
        all_candidates = experiment(d, all_pay)[1]
        best_candidates = experiment(d, best_pay)[1]
        first_candidates = experiment(d, first)[1]
        assert [label for label, _, _ in all_candidates] == [label for label, _, _ in first_candidates]
        for (_, all_stake, _), (_, best_stake, _), (_, first_stake, first_paid) in zip(
                all_candidates, best_candidates, first_candidates, strict=True):
            np.testing.assert_array_equal(all_stake, first_stake)
            np.testing.assert_array_equal(best_stake, first_stake)
            assert np.all(first_paid >= 0)
    assert all_pay[0, 5] == 88 and best_pay[0, 5] == 80 and first[0, 5] == 80
    assert all_pay[1, 5] == 12 and best_pay[1, 5] == 8 and first[1, 5] == 0


def test_e5_explicit_ladders_and_first_outcome_at_tenth_day_end():
    d = draws([[1, 2, 3, 4, 5]] * 10, [1] * 10)
    hp = np.array([[75, 0]])
    original_stake, _, lost = ex._ladder_arrays(
        1, np.array([0]), np.array([0]), np.array([9]), hp,
        ladder=LADDER, profile=QUINIELA80, first_hits=np.array([False]))
    assert original_stake.tolist() == [50 * LADDER[9]]
    assert lost == 1  # Lower-position payouts cannot turn a first-position miss into a win.
    new_ladder = first_prize_ladder(QUINIELA80)
    new_stake, _, lost = ex._ladder_arrays(
        1, np.array([0]), np.array([0]), np.array([9]), hp,
        ladder=new_ladder, profile=QUINIELA80, first_hits=np.array([True]))
    assert new_stake.tolist() == [50 * new_ladder[9]]
    assert lost == 0
    _, _, old = ex.e5_streak_entry(d, payout_matrix(d.nums))
    _, _, explicit = ex.e5_streak_entry(d, payout_matrix(d.nums), ladder=LADDER,
                                       profile=ORIGINAL70)
    assert old.keys() == explicit.keys()
    for label in old:
        for a, b in zip(old[label][:2], explicit[label][:2], strict=True):
            np.testing.assert_array_equal(a, b)
        assert old[label][2] == explicit[label][2]
    _, _, alternative = ex.e5_streak_entry(d, payout_matrix(d.nums, profile=QUINIELA80),
                                           ladder=new_ladder, profile=QUINIELA80)
    assert alternative.keys() == old.keys()


def test_first_view_e3_and_e5_pays_only_first_hits_on_same_bets():
    nums = [[1, 1, 2, 3, 4]] * 9 + [[2, 2, 1, 3, 4]] * 5
    d = draws(nums)
    first = ex.first_position_matrix(d.nums, QUINIELA80)
    all_pay = payout_matrix(d.nums, "all", QUINIELA80)
    e3_all = ex.e3_carry(d, all_pay)[1]
    e3_first = ex.e3_carry(d, first)[1]
    np.testing.assert_array_equal(e3_all[0][1], e3_first[0][1])
    assert e3_all[0][2][9] == 4 and e3_first[0][2][9] == 0
    label = "par/impar tras ≥3"
    e5_all = {name: (stake, paid) for name, stake, paid in
              ex.e5_streak_entry(d, all_pay)[1]}
    e5_first = {name: (stake, paid) for name, stake, paid in
                ex.e5_streak_entry(d, first)[1]}
    np.testing.assert_array_equal(e5_all[label][0], e5_first[label][0])
    assert e5_first[label][1][9] == 80
    assert e5_all[label][1][9] >= e5_first[label][1][9]
    no_switch = draws([[1, 2, 3, 4, 5]] * 14)
    _, _, ladders = ex.e5_streak_entry(
        no_switch, payout_matrix(no_switch.nums, profile=QUINIELA80),
        ladder=first_prize_ladder(QUINIELA80), profile=QUINIELA80)
    assert ladders[label][2] == 1  # Last draw is the 10th bet with no first hit.


def test_audaz_uses_first_prize_minus_one_in_real_replay():
    assert ex._stake("bold", 1000, 2000) == 15
    assert ex._stake("bold", 1000, 2000, profile=QUINIELA80) == 13
    assert ex.replay_sessions(np.array([80]), [0], 1000, 2000, "bold",
                              profile=QUINIELA80)["bank"].tolist() == [2027]
    assert ex.back_to_back(np.array([80]), 1000, 2000, "bold",
                           profile=QUINIELA80).tolist() == [True]


class FixedDraw:
    def random(self, shape):
        out = np.ones(shape)
        out[:, :2] = 0
        return out


def test_monte_carlo_repeated_hits_all_and_best_and_legacy_default():
    all_result = ex.simulate_sessions(1, 1, 2, "bold", FixedDraw(), profile=QUINIELA80,
                                      mode="all")
    best_result = ex.simulate_sessions(1, 1, 2, "bold", FixedDraw(), profile=QUINIELA80,
                                       mode="best")
    original = ex.simulate_sessions(1, 1, 2, "bold", FixedDraw())
    assert all_result["bank"].tolist() == [88]
    assert best_result["bank"].tolist() == [80]
    assert original["bank"].tolist() == [78]
    assert all_result["steps"].tolist() == best_result["steps"].tolist() == [1]


def test_monte_carlo_cache_distinguishes_profile_and_mode(monkeypatch):
    seen = []

    def fake(count, bank, goal, style, rng, profile=ORIGINAL70, mode="all"):
        seen.append((count, profile, mode))
        return {"reached": np.ones(count, dtype=bool)}

    monkeypatch.setattr(ex, "_MC_CACHE", {})
    monkeypatch.setattr(ex, "simulate_sessions", fake)
    first = ex._fair_sessions(1000, 2000, "bold", QUINIELA80, "all")
    assert ex._fair_sessions(1000, 2000, "bold", QUINIELA80, "all") is first
    ex._fair_sessions(1000, 2000, "bold", QUINIELA80, "best")
    ex._fair_sessions(1000, 2000, "bold", ORIGINAL70, "all")
    assert seen == [(20_000, QUINIELA80, "all"), (20_000, QUINIELA80, "best"),
                    (20_000, ORIGINAL70, "all")]


def test_e6_and_e7_share_profile_and_mode(monkeypatch):
    d = draws([[5, 5, 1, 2, 3], [7, 5, 1, 2, 3]])
    all_pay = payout_matrix(d.nums, "all", QUINIELA80)
    best_pay = payout_matrix(d.nums, "best", QUINIELA80)
    seen = []

    def fake_sessions(bank, goal, style, profile=ORIGINAL70, mode="all"):
        seen.append((profile, mode))
        return {"reached": np.zeros(ex.MC_SESSIONS, dtype=bool),
                "steps": np.ones(ex.MC_SESSIONS)}

    monkeypatch.setattr(ex, "_fair_sessions", fake_sessions)
    _, rows = ex.e6_bold(d, best_pay, profile=QUINIELA80, mode="best")
    assert len(rows) == 4 and seen == [(QUINIELA80, "best")] * 4
    repeat = ex.e7_repeat_rule(d, all_pay, best_pay, profile=QUINIELA80)
    assert repeat["theory_all"] == pytest.approx(.95)
    assert repeat["theory_best"] == pytest.approx(.9474159401)
    assert ex.e7_repeat_rule(d, payout_matrix(d.nums), payout_matrix(d.nums, "best"))[
        "theory_all"] == .85
