"""On-the-fly causal rankings for lists without precomputed rankings (S3, S5, S6)."""

import numpy as np
import pytest

from laboratorio.engine import causal_rankings as cr

SYSTEMS = cr.FAMILIES


def _random_nums(rows, width=3, seed=7):
    return np.random.default_rng(seed).integers(0, 100, size=(rows, width), dtype=np.int64)


def test_families_are_exactly_the_four_ranking_free_systems():
    assert set(cr.FAMILIES) == {"cold", "freq_hist", "freq_recent", "decay"}


@pytest.mark.parametrize("system", SYSTEMS)
def test_every_ranking_row_is_a_permutation_of_the_hundred_numbers(system):
    ranking = cr.causal_ranking(system, _random_nums(300))
    assert ranking.shape == (300, 100) and ranking.dtype == np.uint8
    assert (np.sort(ranking, axis=1) == np.arange(100)).all()


@pytest.mark.parametrize("system", SYSTEMS)
def test_ranking_at_t_depends_only_on_draws_before_t(system):
    nums = _random_nums(400)
    baseline = cr.causal_ranking(system, nums)
    cut = 250
    mutated = nums.copy()
    mutated[cut:] = _random_nums(400 - cut, seed=99)  # rewrite the future, including draw `cut`
    changed = cr.causal_ranking(system, mutated)
    assert np.array_equal(baseline[: cut + 1], changed[: cut + 1])
    # ...and the mutation is really visible afterwards (the test can fail).
    assert not np.array_equal(baseline[cut + 1 :], changed[cut + 1 :])


@pytest.mark.parametrize("system", SYSTEMS)
def test_first_row_has_no_information_and_follows_the_fixed_tie_order(system):
    ranking = cr.causal_ranking(system, _random_nums(5))
    assert tuple(ranking[0]) == tuple(np.argsort(cr.TIE))


def test_cold_puts_the_longest_unseen_number_first_and_decay_the_most_recent_first():
    nums = np.zeros((6, 3), dtype=np.int64)
    nums[:, 0] = [10, 11, 12, 10, 11, 12]
    cold = cr.causal_ranking("cold", nums)
    # Row 5 (past: 10 11 12 10 11): never-seen numbers are colder than any seen one; among the
    # seen ones 12 (age 3) is colder than 10 (age 2) and 11 (age 1), so they close the ranking.
    assert int(cold[5][0]) not in (10, 11, 12)
    assert list(cold[5][-3:]) == [12, 10, 11]
    decay = cr.causal_ranking("decay", nums, {"half_life": 2})
    assert int(decay[5][0]) == 11  # the most recent draw weighs most


def test_freq_recent_counts_only_the_window():
    nums = np.zeros((12, 3), dtype=np.int64)
    nums[:, 0] = [5, 5, 5, 5, 5, 5, 9, 9, 9, 9, 9, 9]
    wide = cr.causal_ranking("freq_recent", nums, {"window": 100})
    narrow = cr.causal_ranking("freq_recent", nums, {"window": 3})
    assert int(wide[11][0]) in (5, 9)  # tie 5 vs 9 resolved by the fixed priority
    assert int(narrow[11][0]) == 9


def test_causal_rankings_object_duck_types_the_frozen_rankings():
    nums = _random_nums(60)
    rankings = cr.CausalRankings(nums)
    assert np.array_equal(rankings.row_ids, np.arange(60))
    for system in SYSTEMS:
        assert np.array_equal(rankings.family(system), cr.causal_ranking(system, nums))
        assert rankings.family(system) is rankings.family(system)  # cached
    from laboratorio.engine.adapter import DataError

    with pytest.raises(DataError):
        rankings.family("notebook")


def _parse_config_id(config_id):
    family, rest = config_id.split(":")
    params = {}
    for pair in rest.split(","):
        key, value = pair.split("=")
        params[key] = None if value == "none" else int(value) if value.isdigit() else value
    return family, params


@pytest.mark.real_data
@pytest.mark.parametrize("system", SYSTEMS)
def test_on_the_fly_rankings_equal_the_precomputed_chance_rows(lab_data, system):
    """Given the archived per-fold config, every one of the 65,235 rows is identical."""
    with np.load(lab_data.rankings.path, allow_pickle=False) as archive:
        row_ids = archive["row_ids"]
        fold_id = archive["fold_id"]
        config_ids = [str(item) for item in archive[f"config_id__{system}"]]
    reference = lab_data.rankings.family(system)
    by_params = {}
    for fold, config_id in enumerate(config_ids):
        family, params = _parse_config_id(config_id)
        assert family == system
        by_params.setdefault(tuple(sorted(params.items(), key=str)), []).append(fold)
    checked = 0
    for key, folds in by_params.items():
        scores = cr.score_matrix(system, lab_data.history.nums, dict(key))
        mask = np.isin(fold_id, folds)
        rebuilt = cr.rank_rows(scores, row_ids[mask])
        assert np.array_equal(rebuilt, reference[mask]), (system, key)
        checked += int(mask.sum())
    assert checked == len(row_ids) == 65235


@pytest.mark.real_data
def test_default_params_are_among_the_archived_configs():
    # The Leidsa defaults are real configurations of the archived grid, not invented ones.
    assert cr.DEFAULT_PARAMS["freq_recent"]["window"] in (20, 100, 500, 2000)
    assert cr.DEFAULT_PARAMS["decay"]["half_life"] in (20, 100, 500, 2000)
    assert cr.DEFAULT_PARAMS["cold"]["scope"] in ("position", "any")
    assert cr.DEFAULT_PARAMS["freq_hist"] == {"scope": "position", "window": None}
