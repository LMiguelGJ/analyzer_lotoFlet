"""Deterministic contract checks for the frozen E5 healthy-control calibration."""

from unittest.mock import patch

import numpy as np

from rng_audit.lottery_tests import Draws
from strategy_tests import calibrate_e5 as cal


def tiny_draws():
    nums = np.zeros((4, 5), dtype=np.int64)
    day = np.array([1, 1, 2, 2])
    return Draws(nums, day, np.arange(4), day, day)


def test_frozen_seeds_split_and_policy_order():
    expected = tuple(f"E5-healthy-cal-v1-{i:03d}" for i in range(1, 21))
    assert expected == cal.SEEDS
    assert len(set(cal.SEEDS)) == 20
    days = np.arange(10)
    assert cal.split_day(days) == 6
    assert cal.split_day(np.arange(566)) == 339


def test_pick_uses_training_only_and_first_tie():
    train = np.array([True, True, False, False])
    candidates = [
        ("first", np.array([1., 1., 1., 1.]), np.array([1., 1., 0., 0.])),
        ("second", np.array([1., 1., 1., 1.]), np.array([1., 1., 100., 100.])),
        ("third", np.array([1., 1., 1., 1.]), np.array([0., 0., 100., 100.])),
    ]
    assert cal.pick_training(candidates, train) == (0, 1.0)
    assert cal.pick_training(candidates, np.array([False, False, True, True])) == (1, 100.0)
    assert cal.pick_training([("empty", np.zeros(4), np.zeros(4)), *candidates], train) == (1, 1.0)


def test_evaluate_one_uses_original_e5_money_on_held_days_and_inclusive_ci():
    d = tiny_draws()
    candidates = [(f"policy {i}", np.ones(4), np.array([1., 1., 0., 0.]))
                  for i in range(12)]
    candidates[1] = ("chosen", np.ones(4), np.array([2., 2., 0., 0.]))
    metric = {"ret": 0.85, "lo": 0.85, "hi": 0.85, "stake": 2.0}
    with (patch.object(cal, "sha256_drbg", return_value=d) as generator,
          patch.object(cal, "payout_matrix", return_value=np.zeros((4, 100))),
          patch.object(cal.ex, "e5_streak_entry", return_value=([], candidates, {})),
          patch.object(cal.ex, "money", return_value=metric) as money):
        row = cal.evaluate_one(d, "E5-healthy-cal-v1-001", 2)
    generator.assert_called_once_with(d, seed="E5-healthy-cal-v1-001")
    assert row == {"seed": "E5-healthy-cal-v1-001", "policy": "chosen",
                   "train_ret": 2.0, "ret": 0.85, "lo": 0.85, "hi": 0.85,
                   "covered": True}
    args, kwargs = money.call_args
    np.testing.assert_array_equal(args[0], [2, 2])
    np.testing.assert_array_equal(args[1], [1., 1.])
    np.testing.assert_array_equal(args[2], [0., 0.])
    assert kwargs == {}
    assert args[3].bit_generator.state == np.random.default_rng(7).bit_generator.state
    assert cal.ex.BOOTSTRAP_REPS == 2000
    with (patch.object(cal, "sha256_drbg", return_value=d),
          patch.object(cal, "payout_matrix", return_value=np.zeros((4, 100))),
          patch.object(cal.ex, "e5_streak_entry", return_value=([], candidates, {})),
          patch.object(cal.ex, "money", return_value=dict(metric, hi=0.849))):
        assert cal.evaluate_one(d, "E5-healthy-cal-v1-001", 2)["covered"] is False


def test_aggregate_threshold_and_report_shape():
    rows = [{"seed": seed, "policy": "par/impar tras ≥3", "train_ret": .85,
             "ret": .85, "lo": .8, "hi": .9, "covered": i < 18}
            for i, seed in enumerate(cal.SEEDS)]
    original = {"pick": "par/impar tras ≥3", "held_out": {"lo": .824, "hi": .849}}
    report = cal.make_report(rows, original, {"days": 566, "test_from": "2026-02-10"}, 1.25)
    assert len(report["records"]) == 20
    assert report["aggregate"] == {"covered": 18, "total": 20, "threshold": 18, "pass": True}
    assert report["original_e5"]["criterion_met"] is False
    assert report["elapsed_seconds"] == 1.25
    assert cal.make_report([dict(r, covered=i < 17) for i, r in enumerate(rows)],
                           original, {}, 1)["aggregate"]["pass"] is False
    text = cal.markdown(report)
    assert text.count("E5-healthy-cal-v1-") == 20
    assert "INCUMPLIDO" in text and "rentabilidad" in text
