"""Nested walk-forward folds: outer/inner day ranges, masks, and per-family selection."""

import json
from datetime import date, timedelta

import numpy as np
import pytest

from chance_rank import engine, protocol
from chance_rank.data import make_history
from chance_rank.walkforward import (
    Fold,
    fold_manifest,
    outer_folds,
    primary_mask,
    rows_in_days,
    secondary_mask,
    select,
    selections,
)


def _synthetic_history(n_days, rows_per_day=6, seed_label="test-walkforward", host="premios.do"):
    generator = protocol.rng(seed_label)
    entries = []
    for d in range(n_days):
        iso = (date(2024, 1, 1) + timedelta(days=d)).isoformat()
        for r in range(rows_per_day):
            hour, minute = divmod(5 + r * 5, 60)
            nums = generator.integers(0, 100, size=5).tolist()
            entries.append((iso, f"{hour:02d}:{minute:02d}", nums, host))
    return make_history(entries)


# --- outer_folds: exact bounds from the plan -----------------------------------------

def test_outer_folds_566_days_matches_plan():
    folds = outer_folds(566)
    assert len(folds) == 14
    assert folds[0].test_days == (180, 208)
    assert folds[-1].test_days == (544, 566)
    assert folds[-1].index == 13
    for j, fold in enumerate(folds):
        assert fold.index == j
        assert fold.test_days[0] == protocol.INITIAL_TRAIN_DAYS + protocol.OUTER_BLOCK_DAYS * j


def test_outer_folds_inner_ranges_are_84_days_before_start():
    folds = outer_folds(566)
    fold = folds[0]  # start = 180
    assert fold.inner == ((96, 124), (124, 152), (152, 180))


def test_outer_folds_small_n_days():
    assert outer_folds(180) == []
    folds = outer_folds(181)
    assert len(folds) == 1
    assert folds[0].test_days == (180, 181)
    assert folds[0].inner == ((96, 124), (124, 152), (152, 180))


# --- rows_in_days: half-open day mask -------------------------------------------------

def test_rows_in_days_half_open_mask():
    h = _synthetic_history(n_days=5, rows_per_day=3)
    mask = rows_in_days(h, 1, 3)
    assert mask.sum() == 3 * 2
    assert np.all(h.day[mask] >= 1)
    assert np.all(h.day[mask] < 3)


# --- primary/secondary masks -----------------------------------------------------------

def test_primary_mask_concrete_with_patched_warmup(monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 2)
    h = _synthetic_history(n_days=1, rows_per_day=4)
    mask = primary_mask(h)
    # row 0 has no predecessor (not eligible); rows 1-3 are eligible; warmup excludes idx<2
    assert mask.tolist() == [False, False, True, True]


def test_secondary_mask_is_next_available_record_not_consecutive(monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 0)
    # a 10-minute gap makes row 1 non-eligible while still being the "next available record"
    h = make_history([
        ("2025-01-01", "05:05", [1, 1, 1, 1, 1], "premios.do"),
        ("2025-01-01", "05:15", [2, 2, 2, 2, 2], "premios.do"),
        ("2025-01-01", "05:20", [3, 3, 3, 3, 3], "premios.do"),
    ])
    assert primary_mask(h).tolist() == [False, False, True]
    assert secondary_mask(h).tolist() == [False, True, False]


# --- select: masked-only aggregation with lexicographic tie-break --------------------

def test_select_never_reads_rows_outside_mask():
    hits = np.zeros((2, 3), dtype=bool)
    hits[0, :2] = [True, True]
    hits[1, :2] = [False, True]
    mask = np.array([True, True, False])
    # column 2 is set so that reading it would flip the winner if it leaked in
    hits[:, 2] = [False, True]
    best_id, scores = select(["a", "b"], hits, mask)
    assert best_id == "a"
    assert scores.tolist() == [1.0, 0.5]


def test_select_ties_break_by_lexicographically_smallest_id():
    hits = np.array([[True, False], [True, False]])
    mask = np.array([True, True])
    best_id, scores = select(["zebra", "alpha"], hits, mask)
    assert best_id == "alpha"
    assert scores.tolist() == [0.5, 0.5]


def test_select_keeps_loser_scores_for_audit():
    hits = np.array([[True, True], [False, True], [False, False]])
    mask = np.array([True, True])
    best_id, scores = select(["winner", "middle", "loser"], hits, mask)
    assert best_id == "winner"
    assert scores.tolist() == [1.0, 0.5, 0.0]


# --- selections: per-family winners plus the two automatic selectors ----------------

def test_selections_tie_between_families_and_supervised_absent_is_none():
    h = _synthetic_history(n_days=10, rows_per_day=4)
    fold = Fold(index=0, test_days=(8, 10), inner=((2, 4), (4, 6), (6, 8)))
    n = h.n
    config_ids = ["freq_hist:a", "freq_hist:b", "cold:x"]
    families_of = ["freq_hist", "freq_hist", "cold"]
    inner_mask = rows_in_days(h, 2, 4) | rows_in_days(h, 4, 6) | rows_in_days(h, 6, 8)
    idx = np.nonzero(inner_mask)[0]
    hits = np.zeros((3, n), dtype=bool)
    hits[0, idx] = True
    hits[1, idx[:1]] = True
    hits[2, idx] = True
    primary_rows = np.ones(n, dtype=bool)

    picks, scores_table = selections(h, config_ids, families_of, hits, [fold], primary_rows)

    assert picks[0]["freq_hist"] == "freq_hist:a"
    assert picks[0]["cold"] == "cold:x"
    assert picks[0]["select_interpretable"] == "cold:x"  # tie a vs cold:x -> smaller id wins
    assert picks[0]["select_all"] is None  # no supervised family present -> N/A
    assert set(scores_table[0].keys()) == set(config_ids)
    assert scores_table[0]["freq_hist:b"] == pytest.approx(1 / len(idx))


def test_selections_select_all_present_when_both_supervised_families_present():
    h = _synthetic_history(n_days=10, rows_per_day=4)
    fold = Fold(index=0, test_days=(8, 10), inner=((2, 4), (4, 6), (6, 8)))
    n = h.n
    config_ids = ["freq_hist:a", "logistic:a", "tree:a"]
    families_of = ["freq_hist", "logistic", "tree"]
    inner_mask = rows_in_days(h, 2, 4) | rows_in_days(h, 4, 6) | rows_in_days(h, 6, 8)
    idx = np.nonzero(inner_mask)[0]
    hits = np.zeros((3, n), dtype=bool)
    hits[1, idx] = True
    primary_rows = np.ones(n, dtype=bool)

    picks, _ = selections(h, config_ids, families_of, hits, [fold], primary_rows)
    assert picks[0]["select_all"] == "logistic:a"


# --- fold_manifest: dates and counts only, JSON-serializable, no metrics -------------

def test_fold_manifest_has_dates_and_counts_no_metrics():
    h = _synthetic_history(n_days=200, rows_per_day=4)
    folds = outer_folds(len(h.dates))
    manifest = fold_manifest(h, folds[:1])
    entry = manifest[0]
    assert entry["index"] == 0
    assert entry["test_days"]["start_date"] == h.dates[folds[0].test_days[0]]
    assert isinstance(entry["test_rows"], int)
    assert len(entry["inner"]) == 3
    json.dumps(manifest)  # must be JSON-serializable


# --- leakage: altering days at/after a fold's start must not change that fold's picks --

def test_leakage_altering_future_days_does_not_change_earlier_fold_selections(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 2000)
    # 260 observed days x 12 rows/day: row 2000 falls around day 166, well before the
    # first outer fold's start (day 180), so every outer fold has primary targets.
    h = _synthetic_history(n_days=260, rows_per_day=12, seed_label="test-leakage-base")
    folds = outer_folds(len(h.dates))
    assert len(folds) == 3
    subset = ["freq_hist:scope=position,window=none", "cold:scope=position"]

    threshold_day = folds[1].test_days[0]  # 208
    altered_nums = h.nums.copy()
    future_rows = h.day >= threshold_day
    generator = protocol.rng("test-leakage-future-alteration")
    altered_nums[future_rows] = generator.integers(0, 100, size=(future_rows.sum(), 5))
    h_altered = h.with_nums(altered_nums)

    def _run(history, workdir):
        engine.compute_target_store(history, subset, workdir, positions=(0,),
                                     include_any=False, ablations=False, folds=folds)
        store = engine.load_store(workdir, "pos1")
        hits = store["ranks_updated"] < protocol.PRIMARY_K
        primary_rows = primary_mask(history)
        families_of = ["freq_hist", "cold"]
        return selections(history, subset, families_of, hits, folds, primary_rows)

    picks_base, scores_base = _run(h, str(tmp_path / "base"))
    picks_altered, scores_altered = _run(h_altered, str(tmp_path / "altered"))

    # fold 0 and fold 1's inner windows end at/before day 208 -> untouched by the alteration
    for j in (0, 1):
        assert picks_base[j] == picks_altered[j]
        assert scores_base[j] == pytest.approx(scores_altered[j])
