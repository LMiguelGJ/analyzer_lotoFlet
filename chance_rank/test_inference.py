"""Block bootstrap inference, Holm correction, fold agreement, D10 classification."""

import numpy as np
import pytest

from chance_rank import inference, protocol
from chance_rank.inference import (
    block_bootstrap,
    classify,
    contrast,
    day_totals,
    fold_positive_share,
    holm,
    mde_top25,
)

# --- day_totals: per-day sum/count, strata must not mix within a day ------------------


def test_day_totals_hand_computed():
    diff = np.array([1.0, 2.0, 3.0, 100.0, 5.0, 6.0])
    mask = np.array([True, True, True, False, True, True])
    day = np.array([0, 0, 1, 1, 2, 2])
    strata = [(0, "a"), (0, "a"), (0, "a"), (0, "a"), (1, "b"), (1, "b")]

    day_sum, day_n, strata_of_day = day_totals(diff, mask, day, strata)

    assert day_sum == {0: pytest.approx(3.0), 1: pytest.approx(3.0), 2: pytest.approx(11.0)}
    assert day_n == {0: 2, 1: 1, 2: 2}
    assert strata_of_day == {0: (0, "a"), 1: (0, "a"), 2: (1, "b")}


def test_mixed_source_day_is_partitioned_and_bootstrapped_without_cross_stratum_leakage():
    diff = np.array([1.0, 100.0, 3.0, 200.0, 999.0])
    mask = np.array([True, True, True, True, False])
    day = np.array([5, 5, 6, 6, 6])
    strata = [(0, "a"), (0, "b"), (0, "a"), (0, "b"), (0, "b")]
    sums, counts, assignments = day_totals(diff, mask, day, strata)
    assert sums == {(5, (0, "a")): 1.0, (5, (0, "b")): 100.0,
                    (6, (0, "a")): 3.0, (6, (0, "b")): 200.0}
    assert counts == dict.fromkeys(sums, 1)
    assert assignments == {key: key[1] for key in sums}

    label = "mixed-source-oracle"
    generator = protocol.rng(label)
    expected = np.zeros(12)
    for stratum, values in (((0, "a"), [1.0, 3.0]), ((0, "b"), [100.0, 200.0])):
        del stratum
        starts = generator.integers(0, 2, size=(12, 2))
        expected += np.asarray(values)[starts].sum(axis=1)
    expected /= 4
    actual = block_bootstrap(sums, counts, assignments, 1, 12, label)
    assert actual == pytest.approx(expected)
    assert np.array_equal(actual, block_bootstrap(sums, counts, assignments, 1, 12, label))


# --- block_bootstrap: determinism, circular wrap, truncation, strata separation ------


def test_block_bootstrap_same_label_same_draws():
    day_sum = {10: 1.0, 11: 2.0, 12: 3.0}
    day_n = {10: 1, 11: 1, 12: 1}
    strata_of_day = {10: "s1", 11: "s1", 12: "s1"}
    boot_a = block_bootstrap(day_sum, day_n, strata_of_day, block_days=2, reps=50,
                              label="test-bb-determinism")
    boot_b = block_bootstrap(day_sum, day_n, strata_of_day, block_days=2, reps=50,
                              label="test-bb-determinism")
    assert boot_a.tolist() == boot_b.tolist()


def test_block_bootstrap_different_label_differs():
    day_sum = {10: 1.0, 11: 2.0, 12: 3.0, 13: 4.0, 14: 5.0}
    day_n = {10: 1, 11: 1, 12: 1, 13: 1, 14: 1}
    strata_of_day = dict.fromkeys(day_sum, "s1")
    boot_a = block_bootstrap(day_sum, day_n, strata_of_day, block_days=2, reps=50, label="label-a")
    boot_b = block_bootstrap(day_sum, day_n, strata_of_day, block_days=2, reps=50, label="label-b")
    assert boot_a.tolist() != boot_b.tolist()


def test_block_bootstrap_circular_wrap_truncation_and_strata_pooling_matches_manual_oracle():
    day_sum = {10: 1.0, 11: 2.0, 12: 3.0, 20: 10.0, 21: 20.0, 22: 30.0, 23: 40.0}
    day_n = {10: 1, 11: 1, 12: 1, 20: 2, 21: 2, 22: 2, 23: 2}
    strata_of_day = {10: "s1", 11: "s1", 12: "s1", 20: "s2", 21: "s2", 22: "s2", 23: "s2"}
    block_days, reps, label = 2, 4, "test-bb-oracle"

    # independent oracle: replicate the documented draw order (sorted stratum keys,
    # one `generator.integers(0, m, size=(reps, n_blocks))` call per stratum) by hand.
    generator = protocol.rng(label)
    days_by_stratum = {"s1": [10, 11, 12], "s2": [20, 21, 22, 23]}
    total_diff = np.zeros(reps)
    total_count = np.zeros(reps)
    for stratum in sorted(days_by_stratum):
        days = days_by_stratum[stratum]
        m = len(days)
        n_blocks = -(-m // block_days)
        starts = generator.integers(0, m, size=(reps, n_blocks))
        for r in range(reps):
            resampled_days = []
            for start in starts[r].tolist():
                for off in range(block_days):
                    resampled_days.append(days[(start + off) % m])
            resampled_days = resampled_days[:m]
            total_diff[r] += sum(day_sum[d] for d in resampled_days)
            total_count[r] += sum(day_n[d] for d in resampled_days)
    expected = total_diff / total_count

    actual = block_bootstrap(day_sum, day_n, strata_of_day, block_days, reps, label)
    assert actual == pytest.approx(expected)


# --- contrast: p formula, CI order, N/A on empty mask, degenerate bootstrap ----------


def test_contrast_empty_mask_is_na():
    diff = np.array([1.0, 1.0])
    mask = np.zeros(2, dtype=bool)
    result = contrast(diff, mask, np.array([0, 1]), [("f", "s"), ("f", "s")])
    assert result["n"] == 0
    assert result["p"] is None
    assert result["delta_obs"] is None


def test_contrast_p_formula_and_ci_on_constructed_boot(monkeypatch):
    fixed_boot = np.array([-1.0, 0.0, 1.0, 2.0, 3.0, 10.0])
    captured = {}

    def _fake_block_bootstrap(day_sum, day_n, strata_of_day, block_days, reps, label):
        captured["label"] = label
        return fixed_boot

    monkeypatch.setattr(inference, "block_bootstrap", _fake_block_bootstrap)

    diff = np.array([1.0, 1.0])
    mask = np.array([True, True])
    day = np.array([100, 101])
    strata = [("f0", "src"), ("f0", "src")]

    result = contrast(diff, mask, day, strata, block_days=7)

    assert result["delta_obs"] == pytest.approx(1.0)
    # boot - delta_obs >= delta_obs  <=>  boot >= 2.0  ->  {2.0, 3.0, 10.0} = 3 of 6
    assert result["p"] == pytest.approx((1 + 3) / (6 + 1))
    assert result["ci95"] == pytest.approx((np.percentile(fixed_boot, 2.5),
                                             np.percentile(fixed_boot, 97.5)))
    assert result["ci99"] == pytest.approx((np.percentile(fixed_boot, 0.5),
                                             np.percentile(fixed_boot, 99.5)))
    assert captured["label"] == f"{protocol.PROTOCOL_ID}/inference"


@pytest.mark.parametrize("block_days,expected_suffix", [
    (7, ""), (1, "/L1"), (14, "/L14"),
])
def test_contrast_label_follows_d9(monkeypatch, block_days, expected_suffix):
    captured = {}

    def _fake_block_bootstrap(day_sum, day_n, strata_of_day, block_days, reps, label):
        captured["label"] = label
        return np.array([0.0, 1.0, 2.0])

    monkeypatch.setattr(inference, "block_bootstrap", _fake_block_bootstrap)
    diff = np.array([1.0, 1.0])
    mask = np.array([True, True])
    day = np.array([100, 101])
    strata = [("f0", "src"), ("f0", "src")]

    contrast(diff, mask, day, strata, block_days=block_days)
    assert captured["label"] == f"{protocol.PROTOCOL_ID}/inference{expected_suffix}"


def test_contrast_degenerate_bootstrap_reports_point_mass_not_na(monkeypatch):
    monkeypatch.setattr(inference, "block_bootstrap",
                         lambda *a, **k: np.full(5, 2.0))
    diff = np.array([1.0, 1.0])
    mask = np.array([True, True])
    day = np.array([100, 101])
    strata = [("f0", "src"), ("f0", "src")]

    result = contrast(diff, mask, day, strata, block_days=7)
    assert result["delta_obs"] == pytest.approx(1.0)
    assert result["p"] == pytest.approx(1.0)
    assert result["ci95"] == pytest.approx((1.0, 1.0))
    assert result["ci99"] == pytest.approx((1.0, 1.0))
    assert result["degenerate"] is True


def test_contrast_empty_mask_is_na_and_not_degenerate():
    diff = np.array([1.0, 1.0])
    mask = np.zeros(2, dtype=bool)
    result = contrast(diff, mask, np.array([0, 1]), [("f", "s"), ("f", "s")])
    assert result["n"] == 0
    assert result["p"] is None
    assert result["degenerate"] is False


def test_contrast_normal_bootstrap_reports_degenerate_false(monkeypatch):
    monkeypatch.setattr(inference, "block_bootstrap",
                         lambda *a, **k: np.array([-1.0, 0.0, 1.0, 2.0, 3.0, 10.0]))
    diff = np.array([1.0, 1.0])
    mask = np.array([True, True])
    day = np.array([100, 101])
    strata = [("f0", "src"), ("f0", "src")]

    result = contrast(diff, mask, day, strata, block_days=7)
    assert result["degenerate"] is False


# --- holm: N/A treated as p=1 in ordering, reported back as None --------------------


def test_holm_hand_example_with_na():
    pvals = [0.01, 0.02, None, 0.20]
    adjusted = holm(pvals)
    assert adjusted[0] == pytest.approx(0.04)
    assert adjusted[1] == pytest.approx(0.06)
    assert adjusted[2] is None
    assert adjusted[3] == pytest.approx(0.40)


def test_holm_is_monotonic_non_decreasing_in_sorted_order():
    pvals = [0.5, 0.001, 0.3, None, 0.001]
    adjusted = holm(pvals)
    effective = [1.0 if p is None else p for p in pvals]
    order = sorted(range(len(pvals)), key=lambda i: effective[i])
    sorted_adjusted = [float(1.0 if adjusted[i] is None else adjusted[i]) for i in order]
    assert sorted_adjusted == sorted(sorted_adjusted)


# --- fold_positive_share -------------------------------------------------------------


def test_fold_positive_share_hand_computed():
    diff = np.array([1.0, 1.0, 1.0, -1.0, -1.0, 5.0])
    mask = np.ones(6, dtype=bool)
    fold_of_row = np.array([0, 0, 0, 1, 1, 2])
    result = fold_positive_share(diff, mask, fold_of_row, min_targets=2)
    assert result["per_fold_delta"][0] == pytest.approx(1.0)
    assert result["per_fold_delta"][1] == pytest.approx(-1.0)
    assert result["eligible_folds"] == [0, 1]
    assert result["share"] == pytest.approx(0.5)


# --- classify: every D10 branch, plus the inestable flag ------------------------------


def _system(uniform, recent500, sensitivity=None):
    return {"uniform": uniform, "recent500": recent500, "sensitivity": sensitivity or {}}


def test_classify_consistente_historico():
    uniform = {"delta": 0.02, "p_adj": 0.001, "p_raw": 0.001, "fold_share": 0.8,
               "ci99": (0.005, 0.03)}
    recent500 = {"delta": 0.015, "p_adj": 0.005, "p_raw": 0.005, "fold_share": 0.75,
                 "ci99": (0.002, 0.025)}
    sensitivity = {"L1": {"delta": 0.02, "holm_reject": True},
                   "L14": {"delta": 0.018, "holm_reject": True}}
    result = classify(_system(uniform, recent500, sensitivity))
    assert result["label"] == "consistente_historico"
    assert result["inestable"] is False


def test_classify_senal_exploratoria():
    uniform = {"delta": 0.02, "p_adj": 0.05, "p_raw": 0.03, "fold_share": 0.5,
               "ci99": (-0.005, 0.03)}
    recent500 = {"delta": 0.015, "p_adj": 0.06, "p_raw": 0.04, "fold_share": 0.5,
                 "ci99": (-0.01, 0.025)}
    result = classify(_system(uniform, recent500))
    assert result["label"] == "senal_exploratoria"


def test_classify_inconcluso():
    uniform = {"delta": 0.005, "p_adj": 0.3, "p_raw": 0.2, "fold_share": 0.4,
               "ci99": (-0.01, 0.015)}
    recent500 = {"delta": 0.005, "p_adj": 0.3, "p_raw": 0.2, "fold_share": 0.4,
                 "ci99": (-0.01, 0.02)}
    result = classify(_system(uniform, recent500))
    assert result["label"] == "inconcluso"


def test_classify_sin_mejora_detectada():
    uniform = {"delta": -0.005, "p_adj": 0.9, "p_raw": 0.8, "fold_share": 0.2,
               "ci99": (-0.02, -0.005)}
    recent500 = {"delta": -0.005, "p_adj": 0.9, "p_raw": 0.8, "fold_share": 0.2,
                 "ci99": (-0.02, -0.003)}
    result = classify(_system(uniform, recent500))
    assert result["label"] == "sin_mejora_detectada"


def test_classify_no_disponible_when_delta_missing():
    uniform = {"delta": None}
    recent500 = {"delta": 0.01}
    result = classify(_system(uniform, recent500))
    assert result["label"] == "no_disponible"
    assert result["inestable"] is False


def test_classify_inestable_on_sign_flip():
    uniform = {"delta": 0.02, "p_adj": 0.001, "p_raw": 0.001, "fold_share": 0.8,
               "ci99": (0.005, 0.03)}
    recent500 = {"delta": 0.015, "p_adj": 0.005, "p_raw": 0.005, "fold_share": 0.75,
                 "ci99": (0.002, 0.025)}
    sensitivity = {"L1": {"delta": -0.01, "holm_reject": True},
                   "L14": {"delta": 0.018, "holm_reject": True}}
    result = classify(_system(uniform, recent500, sensitivity))
    assert result["label"] == "consistente_historico"
    assert result["inestable"] is True


def test_classify_inestable_on_holm_decision_change():
    uniform = {"delta": 0.02, "p_adj": 0.001, "p_raw": 0.001, "fold_share": 0.8,
               "ci99": (0.005, 0.03)}
    recent500 = {"delta": 0.015, "p_adj": 0.005, "p_raw": 0.005, "fold_share": 0.75,
                 "ci99": (0.002, 0.025)}
    sensitivity = {"L1": {"delta": 0.02, "holm_reject": False},
                   "L14": {"delta": 0.018, "holm_reject": True}}
    result = classify(_system(uniform, recent500, sensitivity))
    assert result["inestable"] is True


def test_classify_propagates_degenerate_flag_without_crashing():
    uniform = {"delta": 0.0, "p_adj": 1.0, "p_raw": 1.0, "fold_share": 0.0,
               "ci99": (0.0, 0.0), "degenerate": True}
    recent500 = {"delta": 0.0, "p_adj": 1.0, "p_raw": 1.0, "fold_share": 0.0,
                 "ci99": (0.0, 0.0), "degenerate": True}
    result = classify(_system(uniform, recent500))
    assert result["label"] == "sin_mejora_detectada"
    assert result["degenerate"] is True


def test_classify_degenerate_defaults_false_when_absent():
    uniform = {"delta": -0.005, "p_adj": 0.9, "p_raw": 0.8, "fold_share": 0.2,
               "ci99": (-0.02, -0.005)}
    recent500 = {"delta": -0.005, "p_adj": 0.9, "p_raw": 0.8, "fold_share": 0.2,
                 "ci99": (-0.02, -0.003)}
    result = classify(_system(uniform, recent500))
    assert result["degenerate"] is False


# --- mde_top25 -------------------------------------------------------------------------


def test_mde_top25_formula():
    from scipy.stats import norm

    n, m_tests = 1000, 93
    result = mde_top25(n, m_tests, alpha=0.01, power=0.8)
    expected = (norm.ppf(1 - 0.01 / m_tests) + norm.ppf(0.8)) * np.sqrt(0.25 * 0.75 / n)
    assert result["mde"] == pytest.approx(expected)
    assert result["label"] == "optimistic binomial approximation"
