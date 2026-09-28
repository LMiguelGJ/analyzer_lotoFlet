"""Causal scoring families: hand-computed values, non-eligibility, causality, dispatch."""

from datetime import date, timedelta
from fractions import Fraction

import numpy as np
import pytest

from chance_rank import features as feat
from chance_rank import models, protocol, ranking
from chance_rank.data import make_history
from chance_rank.protocol import rng
from chance_rank.ranking import percentile


def _synthetic_history(n_rows=400, seed_label="test-models-synthetic"):
    """Multi-day synthetic history with occasional 10-minute gaps and two sources."""
    generator = rng(seed_label)
    nums = generator.integers(0, 100, size=(n_rows, 5))
    entries = []
    day_index = 0
    minute = 5
    rows_in_day = 0
    for i in range(n_rows):
        if rows_in_day >= 40 or (rows_in_day > 0 and generator.random() < 0.02):
            day_index += 1
            minute = 5
            rows_in_day = 0
        elif rows_in_day > 0:
            minute += 15 if generator.random() < 0.05 else 5
        hour, mm = divmod(minute, 60)
        hour += 5
        iso_date = (date(2025, 3, 5) + timedelta(days=day_index)).isoformat()
        host = "premios.do" if day_index < n_rows // 100 else "loteka.com.do"
        entries.append((iso_date, f"{hour:02d}:{mm:02d}", nums[i].tolist(), host))
        rows_in_day += 1
    return make_history(entries)


# --- freq_hist: expanding/window position scope, global scope denominator -----------

def test_freq_hist_position_expanding_and_window():
    h = make_history([
        ("2025-03-05", "05:05", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:10", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:15", [1, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:20", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:25", [2, 9, 9, 9, 9], "premios.do"),
    ])
    cache = models.FeatureCache(h, 0)

    expanding = models.score_config(h, ("freq_hist", {"scope": "position", "window": None}), 0, cache=cache)
    assert expanding[4, 0] == pytest.approx((3 + 1) / 104)
    assert expanding[4, 1] == pytest.approx((1 + 1) / 104)
    assert expanding[4, 50] == pytest.approx(1 / 104)

    windowed = models.score_config(h, ("freq_hist", {"scope": "position", "window": 2}), 0, cache=cache)
    assert windowed[4, 0] == pytest.approx(2 / 102)
    assert windowed[4, 1] == pytest.approx(2 / 102)
    assert windowed[4, 50] == pytest.approx(1 / 102)


def test_freq_hist_global_scope_denominator():
    h = make_history([
        ("2025-03-05", "05:05", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:10", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:15", [1, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:20", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:25", [2, 9, 9, 9, 9], "premios.do"),
    ])
    cache = models.FeatureCache(h, 0)
    scores = models.score_config(h, ("freq_hist", {"scope": "global", "window": None}), 0, cache=cache)
    assert scores[4, 0] == pytest.approx((3 + 1) / 120)
    assert scores[4, 1] == pytest.approx((1 + 1) / 120)
    assert scores[4, 9] == pytest.approx((16 + 1) / 120)
    assert scores[4, 50] == pytest.approx(1 / 120)
    assert scores[4].sum() == pytest.approx(1.0)


# --- cold: ages including censoring, position vs any scope --------------------------

def test_cold_position_ages_including_censored():
    h = make_history([
        ("2025-03-05", "05:05", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:10", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:15", [1, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:20", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:25", [2, 9, 9, 9, 9], "premios.do"),
    ])
    cache = models.FeatureCache(h, 0)
    ages = models.score_config(h, ("cold", {"scope": "position"}), 0, cache=cache)
    assert ages[0, 0] == 1  # never seen before row 0 -> censored at t + 1
    assert ages[1, 0] == 1  # value 0 last seen at s=0
    assert ages[4, 0] == 1  # value 0 last seen at s=3
    assert ages[4, 1] == 2  # value 1 last seen at s=2
    assert ages[4, 2] == 5  # value 2 never seen before row 4 -> censored


def test_cold_any_scope_sees_other_positions():
    h = make_history([
        ("2025-03-05", "05:05", [0, 5, 5, 5, 5], "premios.do"),
        ("2025-03-05", "05:10", [9, 0, 5, 5, 5], "premios.do"),
        ("2025-03-05", "05:15", [9, 9, 5, 5, 5], "premios.do"),
    ])
    cache = models.FeatureCache(h, 0)
    ages_position = models.score_config(h, ("cold", {"scope": "position"}), 0, cache=cache)
    ages_any = models.score_config(h, ("cold", {"scope": "any"}), 0, cache=cache)
    assert ages_position[2, 0] == 2  # position scope: value 0 last seen at s=0
    assert ages_any[2, 0] == 1       # any scope: value 0 also appears at s=1 (position 1)


# --- decay: exponential recursion for a small half-life ------------------------------

def test_decay_recursion_small_half_life():
    h = make_history([
        ("2025-03-05", "05:05", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:10", [0, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:15", [1, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:20", [0, 9, 9, 9, 9], "premios.do"),
    ])
    cache = models.FeatureCache(h, 0)
    scores = models.score_config(h, ("decay", {"half_life": 1}), 0, cache=cache)
    assert scores[0, 0] == pytest.approx(0.0)
    assert scores[1, 0] == pytest.approx(1.0)
    assert scores[2, 0] == pytest.approx(1.5)
    assert scores[3, 0] == pytest.approx(0.75)
    assert scores[3, 1] == pytest.approx(1.0)
    assert scores[3, 50] == pytest.approx(0.0)


# --- transition: exact P(y|c) with lam on a tiny sequence -----------------------------

def test_transition_hand_computed_probability():
    h = make_history([
        ("2025-03-05", "05:05", [0, 1, 1, 1, 1], "premios.do"),
        ("2025-03-05", "05:10", [1, 1, 1, 1, 1], "premios.do"),
        ("2025-03-05", "05:15", [0, 1, 1, 1, 1], "premios.do"),
        ("2025-03-05", "05:20", [1, 1, 1, 1, 1], "premios.do"),
        ("2025-03-05", "05:25", [0, 1, 1, 1, 1], "premios.do"),
    ])
    cache = models.FeatureCache(h, 0)
    scores = models.score_config(h, ("transition", {"lam": 100}), 0, cache=cache)
    assert scores[4, 0] == pytest.approx(1 / 26)
    assert scores[4, 1] == pytest.approx(75 / 2626)
    assert scores[4, 50] == pytest.approx(25 / 2626)
    assert scores[0].tolist() == pytest.approx(cache.P0[0].tolist())  # row 0 never eligible


# --- time: hour context conditional probability, always valid ------------------------

def test_time_hour_hand_computed_probability_and_no_fallback_on_gap():
    h = make_history([
        ("2025-03-05", "05:05", [1, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:10", [1, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "06:05", [2, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "06:10", [1, 9, 9, 9, 9], "premios.do"),
    ])
    assert h.hour.tolist() == [5, 5, 6, 6]
    cache = models.FeatureCache(h, 0)
    scores = models.score_config(h, ("time", {"context": "hour", "lam": 100}), 0, cache=cache)
    assert scores[3, 2] == pytest.approx(303 / 10403)
    assert scores[3, 1] == pytest.approx(300 / 10403)
    assert scores[3, 50] == pytest.approx(100 / 10403)


def test_time_family_ignores_eligibility_unlike_transition():
    h = make_history([
        ("2025-03-05", "05:05", [3, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:15", [3, 9, 9, 9, 9], "premios.do"),  # 10-minute gap: not eligible
    ])
    assert h.eligible.tolist() == [False, False]
    assert h.hour.tolist() == [5, 5]
    cache = models.FeatureCache(h, 0)
    time_scores = models.score_config(h, ("time", {"context": "hour", "lam": 100}), 0, cache=cache)
    transition_scores = models.score_config(h, ("transition", {"lam": 100}), 0, cache=cache)
    # time uses the real hour=5 conditional count (n(c)=1) even though row 1 is not eligible
    assert time_scores[1, 3] == pytest.approx((1 + 100 * cache.P0[1, 3]) / 101)
    # transition falls back to the plain marginal because row 1 is not eligible
    assert transition_scores[1].tolist() == pytest.approx(cache.P0[1].tolist())


# --- non-eligible rows fall back to P0 for transition/carry/doubles/category ----------

def test_non_eligible_rows_equal_marginal_for_context_families():
    h = make_history([
        ("2025-03-05", "05:05", [3, 1, 1, 9, 9], "premios.do"),
        ("2025-03-05", "05:15", [5, 2, 2, 8, 8], "premios.do"),  # 10-minute gap: not eligible
    ])
    assert h.eligible.tolist() == [False, False]
    cache = models.FeatureCache(h, 0)
    # category's non-eligible fallback uses P0cat (value-split), covered separately in
    # test_category_p0_fallback_value_split_hand_computed
    for family, params in [("transition", {"lam": 100}),
                            ("carry", {"origin": 1, "lam": 100}),
                            ("doubles", {"lam": 100})]:
        scores = models.score_config(h, (family, params), 0, cache=cache)
        assert scores[1].tolist() == pytest.approx(cache.P0[1].tolist()), family


def test_category_p0_fallback_value_split_hand_computed():
    h = make_history([
        ("2025-03-05", "05:05", [3, 9, 9, 9, 9], "premios.do"),
        ("2025-03-05", "05:15", [5, 9, 9, 9, 9], "premios.do"),  # 10-minute gap: not eligible
    ])
    assert h.eligible.tolist() == [False, False]
    cache = models.FeatureCache(h, 0)
    scores = models.score_config(h, ("category", {"kind": "parity", "lam": 100}), 0, cache=cache)
    assert scores[1, 3] == pytest.approx(4 / 153)
    assert scores[1, 7] == pytest.approx(2 / 153)  # any other odd value
    assert scores[1, 4] == pytest.approx(1 / 150)  # any even value


# --- category run-length bucketing (unit-level, exact) --------------------------------

def test_category_run_lengths():
    categories = np.array([0, 0, 1, 1, 1, 0])
    eligible = np.array([False, True, True, True, True, True])
    assert feat.run_lengths(categories, eligible).tolist() == [1, 2, 1, 2, 3, 1]


def test_category_run_length_resets_on_non_eligible_gap():
    categories = np.array([0, 0, 0])
    eligible = np.array([False, True, False])  # a gap breaks the run even with same category
    assert feat.run_lengths(categories, eligible).tolist() == [1, 2, 1]


# --- doubles: hand-computed with Fraction arithmetic ----------------------------------

def test_doubles_hand_computed_with_a_hit_and_a_miss():
    h = make_history([
        ("2025-03-05", "05:05", [9, 1, 1, 20, 21], "premios.do"),   # not eligible
        ("2025-03-05", "05:10", [7, 7, 30, 40, 41], "premios.do"),  # eligible
        ("2025-03-05", "05:15", [7, 7, 60, 70, 71], "premios.do"),  # eligible
        ("2025-03-05", "05:20", [1, 60, 60, 70, 71], "premios.do"),  # eligible, scored row t=3
    ])
    lam = 100
    cache = models.FeatureCache(h, 0)
    p0 = {v: Fraction(int(cache.C[3, v]) + 1, 103) for v in (7, 1, 9)}
    p0_neutral = Fraction(1, 103)

    raw_7 = (Fraction(1) + lam * p0[7]) / (Fraction(1) + lam)   # n_c=1 (doubled+hit), s_c=1
    raw_1 = (Fraction(0) + lam * p0[1]) / (Fraction(1) + lam)   # n_c=1 (never doubled), s_c=0
    raw_9 = (Fraction(0) + lam * p0[9]) / (Fraction(2) + lam)   # n_c=2 (never doubled), s_c=0
    raw_neutral = (Fraction(0) + lam * p0_neutral) / (Fraction(2) + lam)
    total = raw_7 + raw_1 + raw_9 + 97 * raw_neutral

    scores = models.score_config(h, ("doubles", {"lam": lam}), 0, cache=cache)
    assert scores[3, 7] == pytest.approx(float(raw_7 / total))
    assert scores[3, 1] == pytest.approx(float(raw_1 / total))
    assert scores[3, 9] == pytest.approx(float(raw_9 / total))
    assert scores[3, 50] == pytest.approx(float(raw_neutral / total))
    assert scores[3].sum() == pytest.approx(1.0)


# --- notebook/mix: percentile combination, weights normalized to 1 -------------------

def test_notebook_weighted_percentile_combination():
    h = _synthetic_history(60, "test-notebook")
    cache = models.FeatureCache(h, 0)
    scores = models.score_config(h, ("notebook", {"weights": [0.45, 0.45, 0.10], "window": 20}), 0, cache=cache)
    expected = (0.45 * percentile(cache.freq_hist_position(None))
                + 0.45 * percentile(cache.freq_hist_position(20))
                + 0.10 * percentile(cache.cold("position")))
    assert np.allclose(scores, expected)


def test_mix_with_zero_recent_weight_skips_window():
    h = _synthetic_history(60, "test-mix")
    cache = models.FeatureCache(h, 0)
    scores = models.score_config(h, ("mix", {"w_hist": 0.5, "w_recent": 0.0, "w_age": 0.5, "window": None}),
                                  0, cache=cache)
    expected = 0.5 * percentile(cache.freq_hist_position(None)) + 0.5 * percentile(cache.cold("position"))
    assert np.allclose(scores, expected)


def test_exact_mixture_keys_match_fraction_oracle_and_preserve_distinct_scores():
    h = _synthetic_history(60, "test-exact-mixture")
    cache = models.FeatureCache(h, 0)
    cases = [
        (("mix", {"w_hist": 0.25, "w_recent": 0.5, "w_age": 0.25, "window": 20}),
         (Fraction(1, 4), Fraction(1, 2), Fraction(1, 4))),
        (("notebook", {"weights": [0.45, 0.45, 0.10], "window": 20}),
         (Fraction(9, 20), Fraction(9, 20), Fraction(2, 20))),
    ]
    from scipy.stats import rankdata

    components = [cache.freq_hist_position(None), cache.freq_hist_position(20), cache.cold("position")]
    doubled = [(2 * rankdata(s, axis=1, method="average")).astype(np.int64) for s in components]
    for config, weights in cases:
        scores = models.score_config(h, config, 0, cache=cache)
        key = models.ranking_key_config(h, config, 0, cache=cache, scores=scores)
        for row in (0, 20, 40, 59):
            oracle = [sum(w * int(r[row, v]) for w, r in zip(weights, doubled, strict=True))
                      for v in range(100)]
            expected = sorted(range(100), key=lambda v: (-oracle[v], int(ranking.TIE[v])))
            assert ranking.ranking(key[row]).tolist() == expected
            assert np.issubdtype(key.dtype, np.signedinteger)
            for a, b in ((0, 1), (1, 2)):
                if oracle[a] != oracle[b]:
                    assert key[row, a] != key[row, b]
        assert scores.shape == key.shape


def test_float_weighted_percentiles_can_split_exact_rank_ties():
    generator = rng("test-exact-rank-tie-arithmetic")
    ranks = np.stack([np.stack([generator.permutation(np.arange(1, 101)) for _ in range(3)])
                      for _ in range(60)])
    doubled = ranks * 2
    exact = 9 * doubled[:, 0] + 9 * doubled[:, 1] + 2 * doubled[:, 2]
    floating = (0.45 * ((ranks[:, 0] - 1) / 99)
                + 0.45 * ((ranks[:, 1] - 1) / 99)
                + 0.10 * ((ranks[:, 2] - 1) / 99))
    assert any(np.any((exact[row, :, None] == exact[row, None, :])
                      & (floating[row, :, None] != floating[row, None, :])) for row in range(60))


def test_exact_ensemble_and_ablation_keys_match_fraction_oracle():
    from scipy.stats import rankdata

    h = _synthetic_history(60, "test-exact-ensemble")
    cache = models.FeatureCache(h, 0)
    doubled = {}
    votes = {}
    for name, family, params in protocol.ENSEMBLE_MEMBERS:
        member = models.score_config(h, (family, params), 0, cache=cache)
        doubled[name] = (2 * rankdata(member, axis=1, method="average")).astype(np.int64)
        votes[name] = ranking.topk_mask(member, 25).astype(np.int64)
    for method in ("borda", "vote"):
        config = ("ensemble", {"method": method})
        key = models.ranking_key_config(h, config, 0, cache=cache)
        row = 59
        expected = sorted(range(100), key=lambda v: (
            -sum(int(votes[name][row, v]) for name in doubled) if method == "vote" else 0,
            -sum(int(r[row, v]) for r in doubled.values()), int(ranking.TIE[v])))
        assert ranking.ranking(key[row]).tolist() == expected
    for ablation_id, kind, params in models.ABLATIONS:
        key = models.ranking_key_ablation(h, ablation_id, 0, cache=cache)
        if kind == "ensemble_ablation":
            selected = [r for name, r in doubled.items() if name != params["drop"]]
            oracle = sum(selected)
        else:
            weights = {"hist": 9, "recent": 9, "age": 2}
            components = {"hist": cache.freq_hist_position(None),
                          "recent": cache.freq_hist_position(params["window"]),
                          "age": cache.cold("position")}
            oracle = sum(weights[name] * (2 * rankdata(matrix, axis=1, method="average")).astype(np.int64)
                         for name, matrix in components.items() if name != params["drop"])
        assert ranking.ranking(key[59]).tolist() == ranking.ranking(oracle[59]).tolist(), ablation_id


# --- probabilistic configs: positive, rows sum to 1 -----------------------------------

def test_probabilistic_configs_are_positive_and_sum_to_one():
    h = _synthetic_history(120, "test-probabilistic")
    for pos in (0, 3):
        cache = models.FeatureCache(h, pos)
        for config_id, family, params in protocol.all_configs(include_supervised=False):
            if not models.is_probabilistic(family, params):
                continue
            scores = models.score_config(h, (family, params), pos, cache=cache)
            assert np.all(scores > 0), config_id
            assert np.allclose(scores.sum(axis=1), 1.0, atol=1e-9), config_id


# --- _ENSEMBLE_MEMBERS: single source of truth is protocol.ENSEMBLE_MEMBERS -----------

def test_ensemble_members_derived_from_protocol():
    assert models._ENSEMBLE_MEMBERS is protocol.ENSEMBLE_MEMBERS
    assert models._ENSEMBLE_MEMBERS == protocol.ENSEMBLE_MEMBERS


# --- ensemble: vote tie-break by borda -------------------------------------------------

def test_ensemble_vote_score_decomposes_into_votes_and_borda():
    h = _synthetic_history(150, "test-ensemble")
    cache = models.FeatureCache(h, 0)
    vote_scores = models.score_config(h, ("ensemble", {"method": "vote"}), 0, cache=cache)
    borda_scores = models.score_config(h, ("ensemble", {"method": "borda"}), 0, cache=cache)
    votes = np.round(vote_scores // 10)
    remainder = vote_scores - votes * 10
    assert np.allclose(remainder, borda_scores, atol=1e-9)
    assert np.all((votes >= 0) & (votes <= 5))

    row = 140
    manual_order = np.lexsort((ranking.TIE, -borda_scores[row], -votes[row]))
    assert ranking.ranking(vote_scores[row]).tolist() == manual_order.tolist()


# --- any_scores: mean of percentiles of the five positional score matrices ------------

def test_any_scores_equals_mean_of_percentiles():
    h = _synthetic_history(80, "test-any-scores")
    positional = []
    for pos in range(5):
        cache = models.FeatureCache(h, pos)
        positional.append(models.score_config(h, ("freq_hist", {"scope": "position", "window": None}),
                                               pos, cache=cache))
    result = models.any_scores(positional)
    expected = np.mean([percentile(s) for s in positional], axis=0)
    assert np.allclose(result, expected)


# --- dispatch: every protocol config id is scorable; unknown ids raise ---------------

def test_every_grid_config_id_is_dispatchable():
    h = _synthetic_history(60, "test-dispatch")
    configs = protocol.all_configs(include_supervised=False)
    assert len(configs) == 93
    for pos in (0,):
        cache = models.FeatureCache(h, pos)
        for config_id, _, _ in configs:
            scores = models.score_config(h, config_id, pos, cache=cache)
            assert scores.shape == (h.n, 100), config_id


def test_every_ablation_id_is_dispatchable():
    h = _synthetic_history(60, "test-dispatch-ablation")
    cache = models.FeatureCache(h, 0)
    for ablation_id, _, _ in models.ABLATIONS:
        scores = models.score_ablation(h, ablation_id, 0, cache=cache)
        assert scores.shape == (h.n, 100), ablation_id


def test_unknown_config_id_raises():
    h = _synthetic_history(20, "test-unknown-config")
    with pytest.raises(ValueError):
        models.score_config(h, "not-a-real-config", 0)


def test_unknown_ablation_id_raises():
    h = _synthetic_history(20, "test-unknown-ablation")
    with pytest.raises(ValueError):
        models.score_ablation(h, "ablation:does-not-exist", 0)


def test_unknown_family_raises():
    h = _synthetic_history(20, "test-unknown-family")
    with pytest.raises(ValueError):
        models.score_config(h, ("not_a_family", {}), 0)


# --- causality: altering rows >= t0 never changes scores at rows <= t0 ----------------

def test_causality_for_every_config_and_ablation_at_two_positions():
    h = _synthetic_history(400, "test-causality-base")
    t0 = 150
    configs = protocol.all_configs(include_supervised=False)
    for pos in (0, 3):
        base_cache = models.FeatureCache(h, pos)
        altered_nums = h.nums.copy()
        generator = rng(f"test-causality-alter-pos{pos}")
        altered_nums[t0:] = generator.integers(0, 100, size=(h.n - t0, 5))
        altered_h = h.with_nums(altered_nums)
        altered_cache = models.FeatureCache(altered_h, pos)

        any_future_difference = False
        for config_id, family, params in configs:
            base_scores = models.score_config(h, (family, params), pos, cache=base_cache)
            altered_scores = models.score_config(altered_h, (family, params), pos, cache=altered_cache)
            assert np.array_equal(base_scores[:t0 + 1], altered_scores[:t0 + 1]), (config_id, pos)
            if not np.array_equal(base_scores[t0 + 1:], altered_scores[t0 + 1:]):
                any_future_difference = True
        assert any_future_difference

        for ablation_id, _, _ in models.ABLATIONS:
            base_scores = models.score_ablation(h, ablation_id, pos, cache=base_cache)
            altered_scores = models.score_ablation(altered_h, ablation_id, pos, cache=altered_cache)
            assert np.array_equal(base_scores[:t0 + 1], altered_scores[:t0 + 1]), (ablation_id, pos)


def test_exact_ranking_keys_remain_causal_under_future_mutation():
    h = _synthetic_history(60, "test-key-causality")
    altered = h.nums.copy()
    altered[30:] = rng("test-key-future").integers(0, 100, size=(30, 5))
    future = h.with_nums(altered)
    configs = [("mix", {"w_hist": 0.25, "w_recent": 0.5, "w_age": 0.25, "window": 20}),
               ("notebook", {"weights": [0.45, 0.45, 0.10], "window": 20}),
               ("ensemble", {"method": "vote"})]
    for config in configs:
        before = models.ranking_key_config(h, config, 0)
        after = models.ranking_key_config(future, config, 0)
        assert np.array_equal(before[:31], after[:31]), config
    ablation = models.ABLATIONS[0][0]
    assert np.array_equal(models.ranking_key_ablation(h, ablation, 0)[:31],
                          models.ranking_key_ablation(future, ablation, 0)[:31])


# --- load_history default sha (signature-level check; behavior covered in test_data.py) --

def test_load_history_defaults_to_protocol_expected_sha_signature():
    import inspect

    from chance_rank.data import load_history
    default = inspect.signature(load_history).parameters["expected_sha"].default
    assert default == protocol.EXPECTED_SHA256
