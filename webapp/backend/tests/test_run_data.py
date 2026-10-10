"""Tests for the run row builder: strategies, windows and equivalence with the selectors."""

import random
import time

import numpy as np
import pytest

from laboratorio.domain.contracts import SYSTEMS
from laboratorio.domain.runs import RunConfig, run_sessions
from laboratorio.domain.selection import blend_order, parity_numbers
from laboratorio.domain.session import Draw
from laboratorio.engine.run_data import (
    SYSTEM_LABELS,
    RunRows,
    RunSource,
    RunStrategy,
    RunWindow,
    build_run_rows,
    source_from_lab,
)

# --------------------------------------------------------------------------- synthetic data


class FakeRankings:
    """Duck-typed stand-in for ``Rankings``: seeded random families over the ranked rows."""

    def __init__(self, row_ids, seed=0):
        self.row_ids = np.asarray(row_ids, dtype=np.int64)
        self._rng = np.random.default_rng(seed)
        self._families = {}
        self.calls = 0

    def family(self, system):
        self.calls += 1
        if system not in self._families:
            n = len(self.row_ids)
            ranks = np.stack([self._rng.permutation(100) for _ in range(n)]).astype(np.uint8)
            self._families[system] = ranks
        return self._families[system]


LABELS = (
    "2024-01-01 10:00",
    "2024-01-01 15:00",
    "2024-01-02 10:00",
    "2024-01-03 10:00",
    "2024-01-04 10:00",
    "2024-01-05 10:00",
)
RANKED_ROWS = [1, 2, 4]  # rows 0, 3 and 5 have no ranking
UNRANKED_FLAGS = [True, False, False, True, False, True]
VOTES = np.array([0, 1, 0, 1, 0, 1], dtype=np.int8)


def make_source(labels=LABELS, ranked=RANKED_ROWS, sha="abc"):
    n = len(labels)
    results = (np.arange(n * 5, dtype=np.uint8) % 100).reshape(n, 5)
    rank_pos = np.full(n, -1, dtype=np.int32)
    for position, row in enumerate(ranked):
        rank_pos[row] = position
    minutes = np.arange(n, dtype=np.int64) * 10 + 1000
    return RunSource(tuple(labels), minutes, results, rank_pos, sha)


def make_rankings(ranked=RANKED_ROWS):
    return FakeRankings(ranked)


def mix(pairs, coverage=10):
    return RunStrategy("mix", tuple(pairs), coverage)


def parity(coverage=50):
    return RunStrategy("parity", (), coverage)


def ints(values):
    return tuple(int(v) for v in values)


# --------------------------------------------------------------------------- RunStrategy


def test_system_labels_reexport():
    assert SYSTEM_LABELS == dict(SYSTEMS)


def test_valid_strategies():
    assert mix([("transition", 100)], 1).kind == "mix"
    assert mix([("transition", 60), ("cold", 40)], 50).coverage == 50
    assert parity(25).components == ()
    names = list(SYSTEMS)
    every = [(name, 1) for name in names[:12]] + [(names[12], 88)]
    assert len(mix(every).components) == 13


@pytest.mark.parametrize("coverage", [0, 51, -1, 100])
def test_coverage_out_of_range(coverage):
    with pytest.raises(ValueError):
        mix([("cold", 100)], coverage)
    with pytest.raises(ValueError):
        parity(coverage)


@pytest.mark.parametrize("coverage", [10.0, True, "10", None])
def test_coverage_must_be_strict_int(coverage):
    with pytest.raises(ValueError):
        mix([("cold", 100)], coverage)
    with pytest.raises(ValueError):
        RunStrategy("parity", (), coverage)


def test_unknown_kind():
    with pytest.raises(ValueError):
        RunStrategy("random", (), 10)


def test_mix_requires_components():
    with pytest.raises(ValueError):
        mix([])


def test_mix_rejects_more_than_13_components():
    pairs = [(name, 1) for name in SYSTEMS] + [("extra", 1)]
    with pytest.raises(ValueError):
        mix(pairs)


def test_mix_rejects_unknown_system():
    with pytest.raises(ValueError):
        mix([("nonsense", 100)])


def test_mix_rejects_duplicate_system():
    with pytest.raises(ValueError):
        mix([("cold", 50), ("cold", 50)])


@pytest.mark.parametrize("percent", [0, -5, 101, 50.0, True, "50"])
def test_mix_rejects_bad_percent(percent):
    with pytest.raises(ValueError):
        mix([("cold", percent), ("decay", 50)])


@pytest.mark.parametrize("pairs", [[("cold", 60), ("decay", 30)], [("cold", 60), ("decay", 50)]])
def test_mix_percents_must_sum_to_100(pairs):
    with pytest.raises(ValueError):
        mix(pairs)


def test_mix_rejects_malformed_component():
    with pytest.raises(ValueError):
        RunStrategy("mix", ("cold",), 10)
    with pytest.raises(ValueError):
        RunStrategy("mix", [("cold", 100)], 10)


def test_parity_rejects_components():
    with pytest.raises(ValueError):
        RunStrategy("parity", (("cold", 100),), 10)


# --------------------------------------------------------------------------- RunWindow


def test_window_defaults_and_valid():
    assert RunWindow(None, None).start_date is None
    assert RunWindow("2024-01-01", "2024-01-01").end_date == "2024-01-01"
    assert RunWindow("2024-01-01", None).end_date is None


@pytest.mark.parametrize("value", ["2024-13-01", "yesterday", "", "2024-1-1x"])
def test_window_rejects_bad_dates(value):
    with pytest.raises(ValueError):
        RunWindow(value, None)
    with pytest.raises(ValueError):
        RunWindow(None, value)


def test_window_rejects_non_string():
    with pytest.raises(ValueError):
        RunWindow(20240101, None)


def test_window_rejects_inverted_range():
    with pytest.raises(ValueError):
        RunWindow("2024-02-01", "2024-01-31")


# --------------------------------------------------------------------------- synthetic mix


def test_mix_orders_only_ranked_rows():
    result = build_run_rows(make_source(), make_rankings(), mix([("transition", 60), ("cold", 40)]))
    assert isinstance(result, RunRows)
    assert all(type(row) is Draw for row in result.rows)
    assert [row.order is None for row in result.rows] == UNRANKED_FLAGS
    assert [row.label for row in result.rows] == list(LABELS)


def test_mix_row_fields_are_python_values():
    source = make_source()
    result = build_run_rows(source, make_rankings(), mix([("cold", 100)], 7))
    row = result.rows[1]
    assert row.minute == 1010 and type(row.minute) is int
    assert row.results == ints(source.results[1])
    assert all(type(v) is int for v in row.results)
    assert len(row.order) == 7 and all(type(v) is int for v in row.order)


@pytest.mark.parametrize("coverage", [1, 10, 50])
def test_mix_matches_blend_order_synthetic(coverage):
    source = make_source()
    rankings = make_rankings()
    strategy = mix([("transition", 50), ("cold", 30), ("decay", 20)], coverage)
    result = build_run_rows(source, rankings, strategy)
    for index, row in enumerate(result.rows):
        position = int(source.rank_pos[index])
        if position < 0:
            continue
        expected = blend_order(
            {name: rankings.family(name)[position] for name, _ in strategy.components},
            dict(strategy.components),
        )
        assert row.order == ints(expected[:coverage])


def test_single_component_equals_raw_ranking():
    source = make_source()
    rankings = make_rankings()
    result = build_run_rows(source, rankings, mix([("cold", 100)], 20))
    family = rankings.family("cold")
    for index, row in enumerate(result.rows):
        position = int(source.rank_pos[index])
        if position >= 0:
            assert row.order == ints(family[position][:20])


def test_mix_ties_go_to_lower_number():
    # Two exactly reversed rankings tie on every number: the order must be 0, 1, 2...
    class Reversed:
        row_ids = np.array([0])

        @staticmethod
        def family(system):
            base = np.arange(100, dtype=np.uint8)
            return (base if system == "cold" else base[::-1]).reshape(1, 100).copy()

    source = make_source(LABELS[:1], [0])
    result = build_run_rows(source, Reversed(), mix([("cold", 50), ("decay", 50)], 5))
    assert result.rows[0].order == (0, 1, 2, 3, 4)


def test_cache_memoizes_families():
    source = make_source()
    rankings = make_rankings()
    cache = {}
    strategy = mix([("transition", 60), ("cold", 40)])
    first = build_run_rows(source, rankings, strategy, cache=cache)
    calls = rankings.calls
    assert set(cache) == {"transition", "cold"}
    second = build_run_rows(source, rankings, strategy, cache=cache)
    assert rankings.calls == calls
    assert first == second


def test_without_cache_still_works():
    result = build_run_rows(make_source(), make_rankings(), mix([("cold", 100)]))
    assert result.draws == 6


# --------------------------------------------------------------------------- synthetic parity


def test_parity_orders_every_draw():
    result = build_run_rows(make_source(), make_rankings(), parity(10), parity_votes=VOTES)
    assert all(row.order is not None for row in result.rows)
    for index, row in enumerate(result.rows):
        assert row.order == ints(parity_numbers(int(VOTES[index]))[:10])
    assert result.rows[0].order[0] == 0 and result.rows[1].order[0] == 1


def test_parity_coverage_slice():
    result = build_run_rows(make_source(), make_rankings(), parity(3), parity_votes=VOTES)
    assert result.rows[0].order == (0, 2, 4)
    assert result.rows[1].order == (1, 3, 5)


def test_parity_ranked_only():
    result = build_run_rows(
        make_source(), make_rankings(), parity(5), ranked_only=True, parity_votes=VOTES
    )
    assert [row.order is None for row in result.rows] == UNRANKED_FLAGS
    assert result.draws == 6 and result.ranked_draws == 3


def test_parity_requires_votes():
    with pytest.raises(ValueError):
        build_run_rows(make_source(), make_rankings(), parity())


def test_parity_rejects_wrong_length_votes():
    with pytest.raises(ValueError):
        build_run_rows(
            make_source(), make_rankings(), parity(), parity_votes=np.zeros(5, dtype=np.int8)
        )


def test_parity_does_not_read_families():
    rankings = make_rankings()
    build_run_rows(make_source(), rankings, parity(), parity_votes=VOTES)
    assert rankings.calls == 0


# --------------------------------------------------------------------------- windows


def labels_of(result):
    return [row.label for row in result.rows]


def build_parity(window=None):
    window = window or RunWindow(None, None)
    return build_run_rows(make_source(), make_rankings(), parity(5), window, parity_votes=VOTES)


def test_default_window_covers_everything():
    result = build_parity()
    assert result.draws == 6
    assert result.ranked_draws == 3
    assert result.first_label == LABELS[0] and result.last_label == LABELS[-1]


def test_window_is_inclusive_on_both_ends():
    result = build_parity(RunWindow("2024-01-01", "2024-01-02"))
    assert labels_of(result) == list(LABELS[:3])
    assert result.first_label == LABELS[0] and result.last_label == LABELS[2]
    assert result.draws == 3 and result.ranked_draws == 2


def test_window_inside_history():
    result = build_parity(RunWindow("2024-01-02", "2024-01-04"))
    assert labels_of(result) == list(LABELS[2:5])
    assert result.ranked_draws == 2  # rows 2 and 4
    assert result.first_label == LABELS[2] and result.last_label == LABELS[4]


def test_window_start_only():
    result = build_parity(RunWindow("2024-01-04", None))
    assert labels_of(result) == list(LABELS[4:])
    assert result.ranked_draws == 1


def test_window_end_only():
    result = build_parity(RunWindow(None, "2024-01-01"))
    assert labels_of(result) == list(LABELS[:2])
    assert result.ranked_draws == 1


def test_window_single_day_covers_every_draw_of_that_day():
    assert build_parity(RunWindow("2024-01-01", "2024-01-01")).draws == 2


def test_empty_window_raises():
    with pytest.raises(ValueError, match="the selected window has no draws"):
        build_parity(RunWindow("2025-01-01", None))


def test_window_applies_to_mix():
    source = make_source()
    rankings = make_rankings()
    result = build_run_rows(
        source, rankings, mix([("cold", 100)], 4), RunWindow("2024-01-03", "2024-01-05")
    )
    assert labels_of(result) == list(LABELS[3:])
    assert [row.order is None for row in result.rows] == [True, False, True]
    assert result.ranked_draws == 1
    assert result.rows[1].order == ints(rankings.family("cold")[2][:4])


def test_window_parity_uses_source_aligned_votes():
    result = build_run_rows(
        make_source(),
        make_rankings(),
        parity(2),
        RunWindow("2024-01-02", None),
        parity_votes=VOTES,
    )
    # Source row 2 has vote 0 (even), row 3 vote 1 (odd).
    assert result.rows[0].order == (0, 2)
    assert result.rows[1].order == (1, 3)


def test_build_is_pure_and_deterministic():
    source = make_source()
    rankings = make_rankings()
    votes = VOTES.copy()
    results_before = source.results.copy()
    rank_before = source.rank_pos.copy()
    strategy = mix([("transition", 60), ("cold", 40)], 10)
    first = build_run_rows(source, rankings, strategy)
    second = build_run_rows(source, rankings, strategy)
    assert first == second
    build_run_rows(source, rankings, parity(), parity_votes=votes)
    assert np.array_equal(votes, VOTES)
    assert np.array_equal(source.results, results_before)
    assert np.array_equal(source.rank_pos, rank_before)


# --------------------------------------------------------------------------- real data


def ranked_indexes(source):
    return [i for i in range(len(source.labels)) if source.rank_pos[i] >= 0]


@pytest.mark.real_data
def test_source_from_lab_rank_pos_consistency(lab_data):
    source = source_from_lab(lab_data)
    n = len(lab_data.history.labels)
    assert source.labels == lab_data.history.labels
    assert source.sha256 == lab_data.history.sha256
    assert source.rank_pos.shape == (n,) and source.rank_pos.dtype == np.int32
    assert source.minutes.dtype == np.int64 and source.results.dtype == np.uint8
    assert source.results.shape == (n, 5)
    row_ids = lab_data.rankings.row_ids
    for position in range(len(row_ids)):
        assert source.rank_pos[row_ids[position]] == position
    assert int((source.rank_pos >= 0).sum()) == len(row_ids)
    assert np.array_equal(source.results, lab_data.history.nums.astype(np.uint8))


@pytest.mark.real_data
@pytest.mark.parametrize(
    "pairs",
    [
        [("transition", 60), ("cold", 40)],
        [("transition", 50), ("cold", 30), ("decay", 20)],
    ],
)
@pytest.mark.parametrize("coverage", [1, 10, 50])
def test_real_mix_matches_blend_order(lab_data, pairs, coverage):
    source = source_from_lab(lab_data)
    cache = {}
    result = build_run_rows(source, lab_data.rankings, mix(pairs, coverage), cache=cache)
    sample = random.Random(1234).sample(ranked_indexes(source), 300)
    for index in sample:
        position = int(source.rank_pos[index])
        expected = blend_order({name: cache[name][position] for name, _ in pairs}, dict(pairs))
        assert result.rows[index].order == ints(expected[:coverage])


@pytest.mark.real_data
def test_real_single_component_equals_family_prefix(lab_data):
    source = source_from_lab(lab_data)
    result = build_run_rows(source, lab_data.rankings, mix([("transition", 100)], 30))
    family = lab_data.rankings.family("transition")
    for index in random.Random(7).sample(ranked_indexes(source), 300):
        assert result.rows[index].order == ints(family[source.rank_pos[index]][:30])


@pytest.mark.real_data
def test_real_order_none_exactly_on_unranked_rows(lab_data):
    source = source_from_lab(lab_data)
    result = build_run_rows(source, lab_data.rankings, mix([("cold", 100)], 5))
    assert len(result.rows) == len(source.labels) == result.draws
    for index, row in enumerate(result.rows):
        assert (row.order is None) == (source.rank_pos[index] < 0)
    assert result.ranked_draws == len(lab_data.rankings.row_ids)


@pytest.mark.real_data
@pytest.mark.golden
def test_real_parity_golden(lab_data):
    result = build_run_rows(
        source_from_lab(lab_data),
        lab_data.rankings,
        RunStrategy("parity", (), 50),
        ranked_only=True,
        parity_votes=lab_data.parity_votes(),
    )
    run = run_sessions(
        RunConfig(
            capital=2000,
            goal=2800,
            coverage=50,
            positions=5,
            prizes=(80, 8, 4, 2, 1),
            minimum_stake=1,
        ),
        result.rows,
    )
    totals = run.totals
    assert totals.goal == 13
    assert totals.ruin == 78
    assert totals.goal + totals.ruin == 91
    assert totals.mean_net_closed == -1572.8


@pytest.mark.real_data
def test_real_mix_performance_with_warm_cache(lab_data):
    source = source_from_lab(lab_data)
    strategy = mix([("transition", 60), ("cold", 40)], 10)
    cache = {}
    build_run_rows(source, lab_data.rankings, strategy, cache=cache)  # warm the cache
    started = time.perf_counter()
    result = build_run_rows(source, lab_data.rankings, strategy, cache=cache)
    elapsed = time.perf_counter() - started
    print(f"\nPERF mix 60/40 coverage 10: {elapsed:.3f}s for {result.draws} rows")
    assert elapsed < 2.0
