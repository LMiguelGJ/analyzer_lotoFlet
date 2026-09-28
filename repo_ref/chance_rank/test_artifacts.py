"""Prediction artifacts export: row-id format, per-system/baseline winner ranks,
primary-target ranking100 recomputation, and the npz + schema.json export step.
"""

import json
import os
from datetime import date, timedelta

import numpy as np
import pytest

from chance_rank import artifacts, engine, pipeline, protocol, walkforward
from chance_rank.data import make_history


def _daily_history(n_days, rows_per_day, seed_label, host="premios.do"):
    generator = protocol.rng(seed_label)
    entries = []
    for d in range(n_days):
        iso = (date(2024, 1, 1) + timedelta(days=d)).isoformat()
        for r in range(rows_per_day):
            hour, minute = divmod(5 + r * 5, 60)
            nums = generator.integers(0, 100, size=5).tolist()
            entries.append((iso, f"{hour:02d}:{minute:02d}", nums, host))
    return make_history(entries)


def _explicit_folds(n_days, n_folds=2, test_block=6):
    folds = []
    start = n_days - n_folds * test_block
    for j in range(n_folds):
        a = start + j * test_block
        b = a + test_block
        inner = ((max(0, a - 12), max(0, a - 8)), (max(0, a - 8), max(0, a - 4)), (max(0, a - 4), a))
        folds.append(walkforward.Fold(index=j, test_days=(a, b), inner=inner))
    return folds


_SUBSET_CONFIGS = [
    "freq_hist:scope=position,window=none",
    "cold:scope=position",
    "decay:half_life=20",
    "transition:lam=100",
    "freq_recent:window=500",
]


# --- 1. row_id: stable "{date} {HH:MM} pos{p}" string, index into history -----------

def test_row_id_formats_date_time_and_position():
    h = _daily_history(3, 4, "test-artifacts-row-id")
    got = artifacts.row_id(h, 5, 1)
    expected = f"{h.dates[h.day[5]]} {h.hour[5]:02d}:{h.slot[5] % 60:02d} pos1"
    assert got == expected


def test_row_id_varies_by_position_only_in_suffix():
    h = _daily_history(3, 4, "test-artifacts-row-id-2")
    assert artifacts.row_id(h, 2, 3) == artifacts.row_id(h, 2, 1).rsplit(" ", 1)[0] + " pos3"


# --- 2. gather_rows: row ids + fold id concatenated in fold order, from test_rows ----

def _store_and_picks(tmp_path, seed_label):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, seed_label)
    folds = _explicit_folds(len(h.dates))
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path), "pos1")
    hits = pipeline.target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    config_ids, families_of = pipeline.candidate_entries(store["config_ids"].tolist())
    index_all = {cid: i for i, cid in enumerate(store["config_ids"].tolist())}
    candidate_hits = np.array([hits[index_all[cid]] for cid in config_ids])
    primary_rows = walkforward.primary_mask(h)
    picks, _scores, test_rows = pipeline.per_fold_choice(h, config_ids, families_of, candidate_hits,
                                                          folds, primary_rows)
    monkeypatch.undo()
    return h, folds, store, index_all, picks, test_rows, primary_rows


def test_gather_rows_concatenates_in_fold_order_matching_test_rows(tmp_path):
    _h, folds, _store, _index_all, _picks, test_rows, _primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-gather")

    row_idx, fold_id = artifacts.gather_rows(folds, test_rows)

    expected_row_idx = np.concatenate([test_rows[f.index]["row_idx"] for f in folds])
    assert np.array_equal(row_idx, expected_row_idx)
    assert row_idx.dtype == np.int64
    assert fold_id.dtype == np.int64
    offset = 0
    for f in folds:
        n = len(test_rows[f.index]["row_idx"])
        assert np.all(fold_id[offset:offset + n] == f.index)
        offset += n


# --- 3. system_winner_ranks: per-system gathered updated winner rank, or unavailable -

def test_system_winner_ranks_matches_chosen_config_ranks_for_present_family(tmp_path):
    h, folds, store, index_all, picks, test_rows, _primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-system-ranks")
    del h

    available, ranks = artifacts.system_winner_ranks(store, index_all, picks, folds, test_rows, "cold")

    assert available is True
    assert ranks.dtype == np.uint8
    expected = np.concatenate([
        store["ranks_updated"][index_all[picks[f.index]["cold"]]][test_rows[f.index]["row_idx"]]
        for f in folds])
    assert np.array_equal(ranks, expected)


def test_system_winner_ranks_unavailable_for_absent_family(tmp_path):
    _h, folds, store, index_all, picks, test_rows, _primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-system-ranks-absent")

    available, ranks = artifacts.system_winner_ranks(store, index_all, picks, folds, test_rows, "logistic")

    assert available is False
    assert ranks is None


# --- 4. chosen_config_ids: per-fold winner id for one system, "" when unpicked -------

def test_chosen_config_ids_matches_picks_per_fold(tmp_path):
    _h, folds, _store, _index_all, picks, _test_rows, _primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-chosen-config")

    ids = artifacts.chosen_config_ids(picks, folds, "cold")

    assert ids == [picks[f.index]["cold"] for f in folds]


def test_chosen_config_ids_empty_string_when_system_unpicked(tmp_path):
    _h, folds, _store, _index_all, picks, _test_rows, _primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-chosen-config-absent")

    ids = artifacts.chosen_config_ids(picks, folds, "logistic")

    assert ids == [""] * len(folds)


# --- 5. baseline_winner_ranks: recent500 / fixed / trainfreq_frozen, aligned to row_idx

def test_baseline_winner_ranks_recent500_matches_store(tmp_path):
    h, folds, store, index_all, _picks, test_rows, primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-baseline-recent500")
    row_idx, _fold_id = artifacts.gather_rows(folds, test_rows)

    ranks = artifacts.baseline_winner_ranks(h, store, index_all, 0, folds, primary_rows, row_idx,
                                             "recent500")

    expected = store["ranks_updated"][index_all[pipeline.RECENT500_ID]][row_idx]
    assert np.array_equal(ranks, expected)
    assert ranks.dtype == np.uint8


def test_baseline_winner_ranks_fixed_matches_engine_fixed_ranks(tmp_path):
    h, folds, store, index_all, _picks, test_rows, primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-baseline-fixed")
    row_idx, _fold_id = artifacts.gather_rows(folds, test_rows)

    ranks = artifacts.baseline_winner_ranks(h, store, index_all, 0, folds, primary_rows, row_idx,
                                             "fixed")

    expected = engine.fixed_ranks(h.nums[row_idx, 0])
    assert np.array_equal(ranks, expected)
    assert ranks.dtype == np.uint8


def test_baseline_winner_ranks_trainfreq_frozen_matches_engine_per_fold(tmp_path):
    h, folds, store, index_all, _picks, test_rows, primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-baseline-trainfreq")
    row_idx, _fold_id = artifacts.gather_rows(folds, test_rows)

    ranks = artifacts.baseline_winner_ranks(h, store, index_all, 0, folds, primary_rows, row_idx,
                                             "trainfreq_frozen")

    trainfreq = engine.trainfreq_frozen(h, 0, folds, primary_rows)
    expected = np.concatenate([trainfreq[f.index][1] for f in folds])
    assert np.array_equal(ranks, expected)
    assert ranks.dtype == np.uint8


def test_baseline_winner_ranks_rejects_unknown_kind(tmp_path):
    h, folds, store, index_all, _picks, test_rows, primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-baseline-unknown")
    row_idx, _fold_id = artifacts.gather_rows(folds, test_rows)

    with pytest.raises(ValueError):
        artifacts.baseline_winner_ranks(h, store, index_all, 0, folds, primary_rows, row_idx, "bogus")


# --- 6. ranking100_for_system / _recent500: primary-target full rank recomputation --

def test_ranking100_for_system_rows_are_permutations_and_match_winner_rank(tmp_path):
    from chance_rank import models

    h, folds, store, index_all, picks, test_rows, _primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-ranking100")
    cache = models.FeatureCache(h, 0)

    available, ranking100 = artifacts.ranking100_for_system(h, picks, folds, test_rows, "cold", 0, cache)

    assert available is True
    for row in ranking100:
        assert sorted(row.tolist()) == list(range(100))

    _sys_available, winner_ranks = artifacts.system_winner_ranks(store, index_all, picks, folds,
                                                                  test_rows, "cold")
    row_idx, _fold_id = artifacts.gather_rows(folds, test_rows)
    y_true = h.nums[row_idx, 0]
    for m in range(len(row_idx)):
        position = int(np.where(ranking100[m] == y_true[m])[0][0])
        assert position == int(winner_ranks[m])


def test_ranking100_for_system_unavailable_for_absent_family(tmp_path):
    from chance_rank import models

    h, folds, _store, _index_all, picks, test_rows, _primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-ranking100-absent")
    cache = models.FeatureCache(h, 0)

    available, ranking100 = artifacts.ranking100_for_system(h, picks, folds, test_rows, "logistic", 0,
                                                              cache)

    assert available is False
    assert ranking100 is None


def test_ranking100_for_recent500_matches_winner_rank(tmp_path):
    from chance_rank import models

    h, folds, store, index_all, _picks, test_rows, primary_rows = _store_and_picks(
        tmp_path, "test-artifacts-ranking100-recent500")
    cache = models.FeatureCache(h, 0)
    row_idx, _fold_id = artifacts.gather_rows(folds, test_rows)

    ranking100 = artifacts.ranking100_for_recent500(h, folds, test_rows, 0, cache)
    baseline_ranks = artifacts.baseline_winner_ranks(h, store, index_all, 0, folds, primary_rows,
                                                       row_idx, "recent500")

    y_true = h.nums[row_idx, 0]
    for row in ranking100:
        assert sorted(row.tolist()) == list(range(100))
    for m in range(len(row_idx)):
        position = int(np.where(ranking100[m] == y_true[m])[0][0])
        assert position == int(baseline_ranks[m])


def test_notebook_artifact_full_order_matches_exact_stored_winner_ranks(tmp_path, monkeypatch):
    from chance_rank import models, ranking

    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _daily_history(3, 20, "test-artifacts-exact-notebook")
    fold = walkforward.Fold(index=0, test_days=(2, 3), inner=((0, 0), (0, 0), (0, 0)))
    cid = next(cid for cid, family, _ in protocol.all_configs(False) if family == "notebook")
    engine.compute_target_store(h, [cid], str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])
    store = engine.load_store(str(tmp_path), "pos1")
    rows = np.arange(40, 60)
    picks = {0: {"notebook": cid}}
    test_rows = {0: {"row_idx": rows}}
    available, order = artifacts.ranking100_for_system(h, picks, [fold], test_rows,
                                                        "notebook", 0, models.FeatureCache(h, 0))
    assert available and order is not None
    assert np.array_equal(order, ranking.rank_matrix(models.ranking_key_config(h, cid, 0)[rows]))
    for m, row in enumerate(rows):
        assert int(np.where(order[m] == h.nums[row, 0])[0][0]) == int(store["ranks_updated"][0, row])


# --- 6b. export_target releases the shared FeatureCache between systems (memory) ----

def test_export_target_releases_derived_cache_between_systems(tmp_path):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-artifacts-export-cache-release")
    folds = _explicit_folds(len(h.dates), n_folds=1, test_block=6)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path / "store"), positions=(0,),
                                 include_any=False, ablations=False, folds=folds)
    store = engine.load_store(str(tmp_path / "store"), "pos1")
    hits = pipeline.target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    config_ids, families_of = pipeline.candidate_entries(store["config_ids"].tolist())
    index_all = {cid: i for i, cid in enumerate(store["config_ids"].tolist())}
    candidate_hits = np.array([hits[index_all[cid]] for cid in config_ids])
    primary_rows = walkforward.primary_mask(h)
    picks, _scores, test_rows = pipeline.per_fold_choice(h, config_ids, families_of, candidate_hits,
                                                          folds, primary_rows)
    monkeypatch.undo()

    outdir = tmp_path / "run"
    snapshots = []
    original = pipeline.models.score_config

    def capture(history, config, pos, cache=None):
        assert cache is not None
        snapshots.append(len(cache._cond_cache) + len(cache._window_cache))
        return original(history, config, pos, cache=cache)

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(pipeline.models, "score_config", capture)
        artifacts.export_target(h, str(outdir), "pos1", store, folds, picks, test_rows, index_all,
                                 primary_rows, systems=("cold", "decay", "freq_hist"))

    assert snapshots, "expected score_config to be called for the primary target's ranking100"
    assert all(snapshot == 0 for snapshot in snapshots), (
        f"FeatureCache derived state was not released between systems: {snapshots}")


# --- 7. export_target: predictions_<target>.npz + results_<target>.npz on disk ------

def test_export_target_primary_writes_ranking100_and_separate_results(tmp_path):
    h, folds, store, index_all, picks, test_rows, primary_rows = _store_and_picks(
        tmp_path / "store", "test-artifacts-export-primary")
    row_idx, fold_id = artifacts.gather_rows(folds, test_rows)
    outdir = tmp_path / "run"

    artifacts.export_target(h, str(outdir), "pos1", store, folds, picks, test_rows, index_all,
                             primary_rows, systems=("cold", "decay"))

    pred_path = artifacts.predictions_path(str(outdir), "pos1")
    res_path = artifacts.results_path(str(outdir), "pos1")
    assert os.path.exists(pred_path)
    assert os.path.exists(res_path)

    with np.load(pred_path) as pred:
        assert np.array_equal(pred["row_ids"], row_idx)
        assert np.array_equal(pred["fold_id"], fold_id)
        assert np.all(pred["mode_flags"] == 1)
        avail_cold, ranks_cold = artifacts.system_winner_ranks(store, index_all, picks, folds,
                                                                test_rows, "cold")
        assert bool(pred["available__cold"][0]) == avail_cold
        assert not any(key.startswith("winner_rank__") for key in pred.files)
        assert list(pred["config_id__cold"]) == artifacts.chosen_config_ids(picks, folds, "cold")
        assert "winner_rank__recent500" not in pred.files
        assert "winner_rank__fixed" not in pred.files
        assert "winner_rank__trainfreq_frozen" not in pred.files

        y_true = h.nums[row_idx, 0]
        ranking100_cold = pred["ranking100__cold"]
        for m in range(len(row_idx)):
            assert sorted(ranking100_cold[m].tolist()) == list(range(100))
            position = int(np.where(ranking100_cold[m] == y_true[m])[0][0])
            assert position == int(ranks_cold[m])
        assert "ranking100__recent500" in pred.files
        assert "winner_rank__cold" not in pred.files
        assert "y_true" not in pred.files

    with np.load(res_path) as res:
        assert np.array_equal(res["row_ids"], row_idx)
        assert np.array_equal(res["y_true"], y_true)
        assert np.array_equal(res["winner_rank__cold"], ranks_cold)
        assert "winner_rank__recent500" in res.files


def test_export_target_non_primary_position_has_no_ranking100(tmp_path):
    h, folds, store, index_all, picks, test_rows, primary_rows = _store_and_picks(
        tmp_path / "store", "test-artifacts-export-secondary")
    outdir = tmp_path / "run"

    artifacts.export_target(h, str(outdir), "pos2", store, folds, picks, test_rows, index_all,
                             primary_rows, systems=("cold", "decay"))

    with np.load(artifacts.predictions_path(str(outdir), "pos2")) as pred:
        assert "ranking100__cold" not in pred.files
        assert not any(key.startswith("winner_rank__") for key in pred.files)


def test_export_target_any_has_no_positional_baselines(tmp_path):
    h, folds, store, index_all, picks, test_rows, primary_rows = _store_and_picks(
        tmp_path / "store", "test-artifacts-export-any")
    outdir = tmp_path / "run"

    artifacts.export_target(h, str(outdir), "any", store, folds, picks, test_rows, index_all,
                             primary_rows, systems=("cold", "decay"))

    with np.load(artifacts.predictions_path(str(outdir), "any")) as pred:
        assert "winner_rank__fixed" not in pred.files
        assert "winner_rank__cold" not in pred.files
    with np.load(artifacts.results_path(str(outdir), "any")) as res:
        assert res["y_true"].shape == (len(res["row_ids"]), 5)
        assert "winner_rank__cold" in res.files


def test_prediction_is_invariant_to_current_target_outcome(tmp_path):
    h, folds, store, index_all, picks, test_rows, primary_rows = _store_and_picks(
        tmp_path / "store", "test-artifacts-no-current-outcome")
    row_idx, _ = artifacts.gather_rows(folds, test_rows)
    target = int(row_idx[0])
    original = tmp_path / "original"
    changed = tmp_path / "changed"
    artifacts.export_target(h, str(original), "pos1", store, folds, picks, test_rows,
                            index_all, primary_rows, systems=("cold",))
    nums = h.nums.copy()
    nums[target, 0] = (int(nums[target, 0]) + 1) % 100
    altered = h.with_nums(nums)
    # Recompute the store, but retain the same inner-row selection (only this target changed).
    engine.compute_target_store(altered, _SUBSET_CONFIGS, str(tmp_path / "altered_store"),
                                positions=(0,), include_any=False, ablations=False, folds=folds)
    altered_store = engine.load_store(str(tmp_path / "altered_store"), "pos1")
    artifacts.export_target(altered, str(changed), "pos1", altered_store, folds, picks,
                            test_rows, index_all, primary_rows, systems=("cold",))
    with np.load(artifacts.predictions_path(str(original), "pos1")) as before, \
            np.load(artifacts.predictions_path(str(changed), "pos1")) as after:
        assert not any("winner_rank" in key or "y_true" in key for key in before.files)
        assert before.files == after.files
        for key in before.files:
            np.testing.assert_array_equal(before[key][0] if before[key].ndim else before[key],
                                          after[key][0] if after[key].ndim else after[key])
    with np.load(artifacts.results_path(str(original), "pos1")) as before, \
            np.load(artifacts.results_path(str(changed), "pos1")) as after:
        assert before["y_true"][0] != after["y_true"][0]
        assert before["winner_rank__cold"][0] != after["winner_rank__cold"][0]


# --- 8. export_all + schema.json: self-contained per-target export -------------------

def test_export_one_target_matches_export_all_reference_computation(tmp_path):
    """Regression guard for the per-target resumable export step: exporting targets
    one at a time (only ever loading one target's store) must be byte-identical to
    the frozen ``export_all`` reference that loads every target's store at once.
    """
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-artifacts-export-equivalence")
    folds = _explicit_folds(len(h.dates))
    store_dir = tmp_path / "store"
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(store_dir), positions=(0, 1),
                                 include_any=False, ablations=False, folds=folds)

    reference_outdir = tmp_path / "reference"
    stores = {"pos1": engine.load_store(str(store_dir), "pos1"),
              "pos2": engine.load_store(str(store_dir), "pos2")}
    reference_manifest = artifacts.export_all(h, str(reference_outdir), stores, folds,
                                              systems=("cold", "decay"))

    per_target_outdir = tmp_path / "per_target"
    primary_rows = walkforward.primary_mask(h)
    per_target_manifest = {}
    for target in ("pos1", "pos2"):
        store = engine.load_store(str(store_dir), target)
        per_target_manifest[target] = artifacts.export_one_target(
            h, str(per_target_outdir), target, store, folds, primary_rows=primary_rows,
            systems=("cold", "decay"))
        del store
    monkeypatch.undo()

    assert per_target_manifest == reference_manifest
    for target in ("pos1", "pos2"):
        with np.load(artifacts.predictions_path(str(reference_outdir), target)) as before, \
                np.load(artifacts.predictions_path(str(per_target_outdir), target)) as after:
            assert before.files == after.files
            for key in before.files:
                np.testing.assert_array_equal(before[key], after[key])
        with np.load(artifacts.results_path(str(reference_outdir), target)) as before, \
                np.load(artifacts.results_path(str(per_target_outdir), target)) as after:
            assert before.files == after.files
            for key in before.files:
                np.testing.assert_array_equal(before[key], after[key])


def test_export_all_writes_every_target_and_a_schema_covering_all_files(tmp_path):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(protocol, "WARMUP", 20)
    h = _daily_history(60, 10, "test-artifacts-export-all")
    folds = _explicit_folds(len(h.dates))
    store_dir = tmp_path / "store"
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(store_dir), positions=(0, 1),
                                 include_any=False, ablations=False, folds=folds)
    stores = {"pos1": engine.load_store(str(store_dir), "pos1"),
              "pos2": engine.load_store(str(store_dir), "pos2")}
    outdir = tmp_path / "run"

    manifest = artifacts.export_all(h, str(outdir), stores, folds,
                                     systems=("cold", "decay"))
    monkeypatch.undo()

    assert set(manifest) == {"pos1", "pos2"}
    for target in ("pos1", "pos2"):
        assert os.path.exists(artifacts.predictions_path(str(outdir), target))
        assert os.path.exists(artifacts.results_path(str(outdir), target))

    with open(artifacts.schema_path(str(outdir)), encoding="utf-8") as f:
        schema = json.load(f)
    assert set(schema["targets"]) == {"pos1", "pos2"}
    assert "row_ids" in schema["arrays"]
    assert "ranking100__<system|recent500>" in schema["arrays"]

    with np.load(artifacts.predictions_path(str(outdir), "pos1")) as pred:
        assert "ranking100__cold" in pred.files
    with np.load(artifacts.predictions_path(str(outdir), "pos2")) as pred:
        assert "ranking100__cold" not in pred.files
