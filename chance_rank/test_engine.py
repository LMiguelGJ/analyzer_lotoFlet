"""Persisted causal rank store: shapes, causal correctness, resume, and baselines."""

import os
from datetime import date, timedelta

import numpy as np
import pytest
from scipy.stats import rankdata

from chance_rank import engine, models, protocol, replay, walkforward
from chance_rank.data import make_history
from chance_rank.ranking import topk_mask, winner_rank


def _tiny_history(n_days=8, rows_per_day=10, seed_label="test-engine-tiny", n_rows=None):
    generator = protocol.rng(seed_label)
    entries = []
    for d in range(n_days):
        iso = (date(2024, 1, 1) + timedelta(days=d)).isoformat()
        for r in range(rows_per_day):
            if n_rows is not None and len(entries) >= n_rows:
                break
            hour, minute = divmod(5 + r * 5, 60)
            nums = generator.integers(0, 100, size=5).tolist()
            entries.append((iso, f"{hour:02d}:{minute:02d}", nums, "premios.do"))
    return make_history(entries)


_SUBSET_CONFIGS = [
    "freq_hist:scope=position,window=none",
    "cold:scope=position",
    "decay:half_life=20",
    "transition:lam=100",
]


def _explicit_fold(h):
    n_days = len(h.dates)
    return walkforward.Fold(index=0, test_days=(n_days - 2, n_days),
                             inner=((0, n_days - 6), (n_days - 6, n_days - 4), (n_days - 4, n_days - 2)))


# --- _AccumulatorFile: bounded random-access accumulator storage (CR-6) --------------

def test_accumulator_file_create_zero_has_exact_size_and_all_zero_content(tmp_path):
    path = tmp_path / "acc.dat"
    n_cfg, n = 3, 7
    store = engine._AccumulatorFile.create_zero(str(path), n_cfg, n)
    assert os.path.getsize(path) == n_cfg * n * 100 * 2
    for c in range(n_cfg):
        assert np.array_equal(store[c], np.zeros((n, 100), dtype=np.int16))


def test_accumulator_file_full_and_partial_slice_round_trip_matches_plain_ndarray(tmp_path):
    path = tmp_path / "acc.dat"
    n_cfg, n = 2, 50
    store = engine._AccumulatorFile.create_zero(str(path), n_cfg, n)
    reference = np.zeros((n_cfg, n, 100), dtype=np.int16)
    generator = np.random.default_rng(0)
    for c in range(n_cfg):
        for start in range(0, n, 17):
            end = min(start + 17, n)
            delta = generator.integers(-100, 100, size=(end - start, 100)).astype(np.int16)
            store[c, start:end] += delta
            reference[c, start:end] += delta
    for c in range(n_cfg):
        assert np.array_equal(store[c], reference[c])
        assert np.array_equal(store[c, 10:20], reference[c, 10:20])


def test_accumulator_file_shape_matches_declared_dimensions(tmp_path):
    store = engine._AccumulatorFile.create_zero(str(tmp_path / "acc.dat"), n_cfg=4, n=9)
    assert store.shape == (4, 9, 100)


# --- brier algebraic reformulation: pure-math equivalence proof (CR-6) ---------------

def test_brier_reformulation_matches_onehot_formula_within_tight_tolerance():
    """``sum(S**2) - 2*S[rows,Y] + 1`` must equal ``((S - onehot_y)**2).sum(axis=1)``
    to a much tighter tolerance than the 1e-6 float32 store tolerance, since this is
    the only formula CR-6 actually changes (everything else is a storage-layer swap).
    """
    generator = np.random.default_rng(1234)
    S = generator.random((500, 100))
    Y = generator.integers(0, 100, size=500)
    rows = np.arange(500)
    onehot_y = np.zeros((500, 100))
    onehot_y[rows, Y] = 1.0
    legacy = ((S - onehot_y) ** 2).sum(axis=1)
    reformulated = np.sum(S * S, axis=1) - 2.0 * S[rows, Y] + 1.0
    max_diff = np.max(np.abs(legacy - reformulated))
    assert max_diff <= 1e-12, f"brier reformulation diverged by {max_diff}"


# --- compute_target_store: shapes, dtypes, causal correctness ------------------------

def test_compute_target_store_shapes_and_dtypes(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history()
    fold = _explicit_fold(h)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])
    store = engine.load_store(str(tmp_path), "pos1")
    n_cfg = len(_SUBSET_CONFIGS)
    assert store["config_ids"].tolist() == _SUBSET_CONFIGS
    assert store["ranks_updated"].shape == (n_cfg, h.n)
    assert store["ranks_updated"].dtype == np.uint8
    assert store["ranks_frozen"].dtype == np.uint8
    assert store["ranks_frozen"].shape[0] == n_cfg
    assert store["ranks_frozen"].shape[2] == 20
    assert store["p_true"].shape == (n_cfg, h.n)
    assert store["brier"].shape == (n_cfg, h.n)


def test_ranks_updated_matches_ranking_winner_rank(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history()
    fold = _explicit_fold(h)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])
    store = engine.load_store(str(tmp_path), "pos1")
    Y = h.nums[:, 0]
    for i, cid in enumerate(_SUBSET_CONFIGS):
        S = models.score_config(h, cid, 0)
        expected = winner_rank(S, Y)
        assert np.array_equal(store["ranks_updated"][i], expected)


def test_p_true_equals_score_at_realized_value_for_probabilistic_config(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history()
    fold = _explicit_fold(h)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])
    store = engine.load_store(str(tmp_path), "pos1")
    i = _SUBSET_CONFIGS.index("freq_hist:scope=position,window=none")
    S = models.score_config(h, _SUBSET_CONFIGS[i], 0)
    Y = h.nums[:, 0]
    expected = S[np.arange(h.n), Y].astype(np.float32)
    assert np.allclose(store["p_true"][i], expected)
    j = _SUBSET_CONFIGS.index("cold:scope=position")  # not probabilistic -> NaN
    assert np.all(np.isnan(store["p_true"][j]))


def test_any_target_ranks_match_independently_recomputed_integer_key(tmp_path, monkeypatch):
    """Recompute the doubled-average-rank-sum key by hand (an independent oracle).

    Not compared against ``models.any_scores`` directly: that path divides by 99 and
    averages in float64, so values that are *exactly* tied under the integer key can
    land a hair apart in float space and get ordered by value instead of by
    ``ranking.TIE`` -- precisely the ambiguity the exact integer key exists to avoid
    (ties are common here: e.g. every never-seen value shares the same freq_hist score).
    """
    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history(n_days=6, rows_per_day=8)
    fold = walkforward.Fold(index=0, test_days=(4, 6), inner=((0, 0), (0, 0), (0, 0)))
    subset = ["freq_hist:scope=position,window=none", "cold:scope=position"]
    engine.compute_target_store(h, subset, str(tmp_path), positions=(0, 1, 2, 3, 4),
                                 include_any=True, ablations=False, folds=[fold])
    store = engine.load_store(str(tmp_path), "any")
    assert store["ranks_updated"].shape == (2, h.n, 5)

    caches = [models.FeatureCache(h, pos) for pos in range(5)]
    for i, cid in enumerate(subset):
        key_total = np.zeros((h.n, 100))
        for pos in range(5):
            S = models.score_config(h, cid, pos, cache=caches[pos])
            key_total += rankdata(-S, axis=1, method="average") * 2
        S_any = -key_total
        for pos in range(5):
            expected = winner_rank(S_any, h.nums[:, pos])
            assert np.array_equal(store["ranks_updated"][i, :, pos], expected)


def test_any_checkpoint_resumes_without_recomputing_completed_position(tmp_path, monkeypatch):
    h = _tiny_history(n_days=3, rows_per_day=8)
    configs = [cid for cid, _, _ in protocol.all_configs(False)]
    folds = []
    checks = iter((False, True))
    assert not engine.compute_target_store(h, configs, str(tmp_path), positions=range(5),
                                           folds=folds, should_stop=lambda: next(checks))
    assert (tmp_path / "_any_checkpoint.json").exists()
    original = engine._compute_position

    def guard(history, pos, *args):
        assert pos != 0, "completed position was recomputed"
        return original(history, pos, *args)

    monkeypatch.setattr(engine, "_compute_position", guard)
    assert engine.compute_target_store(h, configs, str(tmp_path), positions=range(5), folds=folds)
    assert not (tmp_path / "_any_checkpoint.json").exists()
    store = engine.load_store(str(tmp_path), "any")
    assert len(store["config_ids"]) == len(configs) + len(models.ABLATIONS)
    for c, entry in enumerate(engine._entries(configs, True)):
        total = np.zeros((h.n, 100), dtype=np.int16)
        for pos in range(5):
            cache = models.FeatureCache(h, pos)
            scores = engine._score_for_entry(h, entry, pos, cache)
            if entry[1] == "interpretable":
                key = models.ranking_key_config(h, (entry[2], entry[3]), pos, cache=cache, scores=scores)
            else:
                key = models.ranking_key_ablation(h, entry[0], pos, cache=cache, scores=scores)
            total += (2 * rankdata(-key, axis=1, method="average")).astype(np.int16)
        for pos in range(5):
            assert np.array_equal(store["ranks_updated"][c, :, pos], winner_rank(-total, h.nums[:, pos]))


@pytest.mark.parametrize("damage", ["missing", "tampered", "identity", "partial"])
def test_any_checkpoint_rejects_incomplete_or_tampered_state(tmp_path, damage):
    import json

    h = _tiny_history(n_days=2, rows_per_day=5)
    configs = _SUBSET_CONFIGS
    assert not engine.compute_target_store(h, configs, str(tmp_path), positions=range(5),
                                           ablations=False, folds=[], should_stop=iter((False, True)).__next__)
    checkpoint = tmp_path / "_any_checkpoint.json"
    state = json.loads(checkpoint.read_text(encoding="utf-8"))
    if damage == "missing":
        (tmp_path / state["file"]).unlink()
    elif damage == "tampered":
        with (tmp_path / state["file"]).open("r+b") as f:
            f.write(b"bad")
    elif damage == "identity":
        state["identity"] = {"wrong": True}
        checkpoint.write_text(json.dumps(state), encoding="utf-8")
    else:
        checkpoint.unlink()
    with pytest.raises(ValueError, match="accumulator|checkpoint"):
        engine.compute_target_store(h, configs, str(tmp_path), positions=range(5),
                                    ablations=False, folds=[])


def test_any_resume_keeps_previous_durable_checkpoint_after_failed_position(tmp_path, monkeypatch):
    import json

    h = _tiny_history(n_days=2, rows_per_day=5)
    checks = iter((False, True))
    assert not engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=range(5),
                                           ablations=False, folds=[], should_stop=lambda: next(checks))
    before = json.loads((tmp_path / "_any_checkpoint.json").read_text(encoding="utf-8"))
    original = engine._compute_position

    def fail_second(history, pos, *args):
        if pos == 1:
            raise RuntimeError("interrupted")
        return original(history, pos, *args)

    monkeypatch.setattr(engine, "_compute_position", fail_second)
    with pytest.raises(RuntimeError, match="interrupted"):
        engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=range(5),
                                    ablations=False, folds=[])
    assert json.loads((tmp_path / "_any_checkpoint.json").read_text(encoding="utf-8")) == before
    monkeypatch.setattr(engine, "_compute_position", original)
    assert engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=range(5),
                                       ablations=False, folds=[])


def test_completed_any_rejects_orphaned_accumulator(tmp_path):
    h = _tiny_history(n_days=2, rows_per_day=5)
    assert engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=range(5),
                                       ablations=False, folds=[])
    (tmp_path / "_any_accumulator.0.int16.dat").write_bytes(b"bad")
    with pytest.raises(ValueError, match="accumulator checkpoint"):
        engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=range(5),
                                    ablations=False, folds=[])


def test_resume_skips_recompute_when_store_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history()
    fold = _explicit_fold(h)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])

    def _boom(*args, **kwargs):
        raise AssertionError("should not recompute a target that already matches")

    monkeypatch.setattr(models, "score_config", _boom)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])


def test_store_identity_rejects_config_fold_and_code_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history()
    fold = _explicit_fold(h)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])
    target = engine._target_path(str(tmp_path), "pos1")
    before = os.stat(target).st_mtime_ns
    alternate = walkforward.Fold(index=0, test_days=(5, 8), inner=fold.inner)
    for configs, folds in ((_SUBSET_CONFIGS[:-1], [fold]), (_SUBSET_CONFIGS, [alternate])):
        with pytest.raises(ValueError, match="identity"):
            engine.compute_target_store(h, configs, str(tmp_path), positions=(0,),
                                         include_any=False, ablations=False, folds=folds)
        assert os.stat(target).st_mtime_ns == before
    monkeypatch.setattr(engine, "code_hash", lambda: "changed-source")
    with pytest.raises(ValueError, match="identity"):
        engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                     include_any=False, ablations=False, folds=[fold])
    assert os.stat(target).st_mtime_ns == before


def test_legacy_float_rank_store_is_rejected_without_overwrite(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history()
    fold = _explicit_fold(h)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                 include_any=False, ablations=False, folds=[fold])
    meta_path = engine._meta_path(str(tmp_path), "pos1")
    with open(meta_path, encoding="utf-8") as f:
        legacy = json.load(f)
    legacy.pop("ranking_key_version", None)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(legacy, f)
    before = engine._target_path(str(tmp_path), "pos1")
    mtime = os.stat(before).st_mtime_ns
    with pytest.raises(ValueError, match="identity"):
        engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=(0,),
                                     include_any=False, ablations=False, folds=[fold])
    assert os.stat(before).st_mtime_ns == mtime


def test_no_leftover_tmp_or_memmap_files_after_successful_write(tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 5)
    h = _tiny_history()
    fold = _explicit_fold(h)
    engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path), positions=range(5),
                                 include_any=True, ablations=False, folds=[fold])
    leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp") or "accumulator" in p]
    assert leftovers == []


def test_mixture_store_updated_frozen_and_any_accumulator_use_exact_order(monkeypatch):
    monkeypatch.setattr(protocol, "WARMUP", 0)
    h = _tiny_history(n_days=3, rows_per_day=20, seed_label="test-exact-store")
    cid = next(cid for cid, family, _ in protocol.all_configs(False) if family == "notebook")
    fold = walkforward.Fold(index=0, test_days=(2, 3), inner=((0, 0), (0, 0), (0, 0)))
    entries = engine._entries([cid], False)
    accumulator = np.zeros((1, h.n, 100), dtype=np.int16)
    result = engine._compute_position(h, 0, entries, [cid], [fold], np.ones(h.n, dtype=bool), accumulator)
    key = models.ranking_key_config(h, cid, 0)
    expected = winner_rank(key, h.nums[:, 0])
    assert np.array_equal(result["ranks_updated"][0], expected)
    assert result["blocks"].shape == (1, 20)
    origin = result["blocks"][0, 0]
    frozen = winner_rank(np.repeat(key[origin:origin + 1], 20, axis=0),
                         np.asarray(h.nums)[result["blocks"][0], 0])
    assert np.array_equal(result["ranks_frozen"][0, 0], frozen)
    assert np.array_equal(accumulator[0], (2 * rankdata(-key, axis=1, method="average")).astype(np.int16))


def test_store_stops_between_targets_and_resumes(tmp_path):
    h = _tiny_history()
    fold = _explicit_fold(h)
    checks = iter((False, True))
    completed = engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path),
                                             positions=(0, 1), include_any=False,
                                             ablations=False, folds=[fold],
                                             should_stop=lambda: next(checks))
    assert completed is False
    assert os.path.exists(engine._target_path(str(tmp_path), "pos1"))
    assert not os.path.exists(engine._target_path(str(tmp_path), "pos2"))
    assert engine.compute_target_store(h, _SUBSET_CONFIGS, str(tmp_path),
                                       positions=(0, 1), include_any=False,
                                       ablations=False, folds=[fold]) is True


def test_position_scoring_releases_derived_cache_between_entries(monkeypatch):
    h = _tiny_history(n_days=4, rows_per_day=8)
    cid = "transition:lam=100"
    entries = engine._entries([cid, cid], False)
    fold = _explicit_fold(h)
    original = engine._score_for_entry
    snapshots = []

    def capture(history, entry, pos, cache):
        snapshots.append(len(cache._cond_cache))
        return original(history, entry, pos, cache)

    monkeypatch.setattr(engine, "_score_for_entry", capture)
    result = engine._compute_position(h, 0, entries, [cid, cid], [fold],
                                      np.ones(h.n, dtype=bool), None)
    assert np.array_equal(result["ranks_updated"][0], result["ranks_updated"][1])
    assert snapshots == [0, 0]


# --- CR-6 equivalence: new file-backed accumulator + reformulated brier vs frozen path -

def _legacy_compute_position(h, pos, entries, config_ids, folds, primary_rows, accumulator):
    """Verbatim pre-CR-6 ``engine._compute_position`` body (onehot-based Brier, plain
    array-or-memmap accumulator writes), kept only to prove the CR-6 refactor changes
    no output. Delegates every unchanged helper to the real ``engine`` module.
    """
    n_cfg, n = len(entries), h.n
    cache = models.FeatureCache(h, pos)
    Y = h.nums[:, pos]

    blocks_by_fold = {fold.index: replay.horizon_blocks(h, fold, primary_rows) for fold in folds}
    ranks_updated = np.empty((n_cfg, n), dtype=np.uint8)
    p_true = np.full((n_cfg, n), np.nan, dtype=np.float32)
    topk_mass = np.full((n_cfg, n), np.nan, dtype=np.float32)
    brier = np.full((n_cfg, n), np.nan, dtype=np.float32)
    frozen_by_fold = {fold.index: np.zeros((n_cfg, blocks_by_fold[fold.index][0].shape[0], 20), dtype=np.uint8)
                       for fold in folds}

    rows = np.arange(n)
    onehot_y = None

    for c, entry in enumerate(entries):
        S = engine._score_for_entry(h, entry, pos, cache)
        cid, kind, family, params = entry
        key = (models.ranking_key_config(h, (family, params), pos, cache=cache, scores=S)
               if kind == "interpretable" else models.ranking_key_ablation(h, cid, pos, cache=cache, scores=S))
        ranks_updated[c] = winner_rank(key, Y)
        if engine._is_probabilistic_entry(entry):
            if onehot_y is None:
                onehot_y = np.zeros((n, 100))
                onehot_y[rows, Y] = 1.0
            p_true[c] = S[rows, Y].astype(np.float32)
            mask25 = topk_mask(S, protocol.PRIMARY_K)
            topk_mass[c] = (S * mask25).sum(axis=1).astype(np.float32)
            brier[c] = ((S - onehot_y) ** 2).sum(axis=1).astype(np.float32)
        if accumulator is not None:
            for start in range(0, n, 4096):
                end = min(start + 4096, n)
                doubled = (rankdata(-key[start:end], axis=1, method="average") * 2).astype(np.int16)
                accumulator[c, start:end] += doubled
        for fold in folds:
            blocks, _dropped = blocks_by_fold[fold.index]
            if blocks.shape[0]:
                frozen_by_fold[fold.index][c] = replay.frozen_block_ranks(key, Y, blocks)
        del S, key
        engine.release_derived_cache(cache)

    blocks_concat, fold_id_per_block, dropped_per_fold = engine._concat_fold_blocks(blocks_by_fold, folds)
    frozen_concat = (np.concatenate([frozen_by_fold[fold.index] for fold in folds], axis=1)
                      if blocks_concat.shape[0] else np.empty((n_cfg, 0, 20), dtype=np.uint8))

    return {
        "config_ids": np.array(config_ids),
        "ranks_updated": ranks_updated,
        "blocks": blocks_concat,
        "fold_id_per_block": fold_id_per_block,
        "ranks_frozen": frozen_concat,
        "dropped_per_fold": dropped_per_fold,
        "p_true": p_true,
        "topk_mass": topk_mass,
        "brier": brier,
    }


def test_full_grid_five_positions_match_frozen_pre_cr6_implementation(tmp_path):
    """110-entry, 5-position, 5,000-row equivalence check for CR-6 (memory blocker):
    the new file-backed accumulator plus reformulated Brier must reproduce the frozen
    pre-refactor path exactly for ranks_updated/ranks_frozen/blocks/p_true/topk_mass,
    and within a tight float32 tolerance for brier.
    """
    n_rows = 5000
    h = _tiny_history(n_days=(n_rows + 186) // 187, rows_per_day=187,
                       seed_label="cr6-equivalence-5000", n_rows=n_rows)
    configs = [cid for cid, _, _ in protocol.all_configs(False)]
    entries = engine._entries(configs, True)
    config_ids = [e[0] for e in entries]
    n_cfg = len(entries)
    assert n_cfg == 110
    n_days = len(h.dates)
    fold = walkforward.Fold(index=0, test_days=(n_days - 3, n_days), inner=((0, 0), (0, 0), (0, 0)))
    primary_rows = walkforward.primary_mask(h)

    legacy_acc = np.zeros((n_cfg, h.n, 100), dtype=np.int16)
    new_acc = engine._AccumulatorFile.create_zero(str(tmp_path / "acc.dat"), n_cfg, h.n)

    max_brier_diff = 0.0
    for pos in range(5):
        legacy = _legacy_compute_position(h, pos, entries, config_ids, [fold], primary_rows, legacy_acc)
        new = engine._compute_position(h, pos, entries, config_ids, [fold], primary_rows, new_acc)
        assert np.array_equal(legacy["ranks_updated"], new["ranks_updated"])
        assert np.array_equal(legacy["blocks"], new["blocks"])
        assert np.array_equal(legacy["ranks_frozen"], new["ranks_frozen"])
        assert np.array_equal(legacy["p_true"], new["p_true"], equal_nan=True)
        assert np.array_equal(legacy["topk_mass"], new["topk_mass"], equal_nan=True)
        diff = np.nanmax(np.abs(legacy["brier"] - new["brier"]))
        max_brier_diff = max(max_brier_diff, float(diff))

    for c in range(n_cfg):
        assert np.array_equal(legacy_acc[c], new_acc[c])

    assert max_brier_diff <= 1e-6, f"brier max diff {max_brier_diff}"


# --- baselines: random, fixed ---------------------------------------------------------

def test_random_ranks_matches_manual_key_computation():
    h = _tiny_history(n_days=3, rows_per_day=5)
    values = h.nums[:, 0]
    rows = np.arange(h.n)
    ranks = engine.random_ranks(h, 7, values, rows)

    keys = protocol.rng("chance-rank-v1/random/007").random((h.n, 100))
    expected = np.array([int((keys[t] < keys[t, values[t]]).sum()) for t in range(h.n)])
    assert np.array_equal(ranks, expected)

    all_ranks_row0 = np.array([int((keys[0] < keys[0, v]).sum()) for v in range(100)])
    assert sorted(all_ranks_row0.tolist()) == list(range(100))  # a permutation, ties improbable


def test_random_ranks_is_deterministic_per_realization_and_varies_across_realizations():
    h = _tiny_history(n_days=3, rows_per_day=5)
    values = h.nums[:, 0]
    rows = np.arange(h.n)
    ranks_a = engine.random_ranks(h, 0, values, rows)
    ranks_b = engine.random_ranks(h, 0, values, rows)
    assert np.array_equal(ranks_a, ranks_b)
    ranks_other_seed = engine.random_ranks(h, 1, values, rows)
    assert not np.array_equal(ranks_a, ranks_other_seed)


def test_fixed_ranks_is_constant_regardless_of_row_and_a_permutation():
    ranks_a = engine.fixed_ranks(np.array([5, 5, 5]))
    assert ranks_a[0] == ranks_a[1] == ranks_a[2]
    full = engine.fixed_ranks(np.arange(100))
    assert sorted(full.tolist()) == list(range(100))


@pytest.mark.skipif(os.environ.get("CHANCE_RANK_BENCH") != "1", reason="explicit synthetic benchmark only")
def test_synthetic_full_grid_budget_benchmark():
    """Opt-in synthetic-only throughput/RSS check; no historical target values."""
    import tempfile
    import threading
    import time

    import psutil

    configs = [cid for cid, _, _ in protocol.all_configs(False)]
    process = psutil.Process()
    peak = [process.memory_info().rss]
    done = threading.Event()

    def sample():
        while not done.wait(0.02):
            peak[0] = max(peak[0], process.memory_info().rss)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        cases = ((5000, "full"), (20000, "mem_bench_20k"), (105426, "one_position"))
        mode = os.environ.get("CHANCE_RANK_BENCH_MODE")
        for n, label in cases:
            if label != mode:
                continue
            if label == "mem_bench_20k":
                import dataclasses
                from pathlib import Path

                from chance_rank.data import load_history

                real_path = Path(__file__).resolve().parent.parent / "chance_express_history.json"
                if not real_path.exists():
                    pytest.skip("chance_express_history.json not present")
                real_h = load_history(real_path, expected_sha=None)
                n_rows = min(n, real_h.n)
                prefix = dataclasses.replace(
                    real_h, nums=real_h.nums[:n_rows], day=real_h.day[:n_rows], slot=real_h.slot[:n_rows],
                    hour=real_h.hour[:n_rows], weekday=real_h.weekday[:n_rows], day_pos=real_h.day_pos[:n_rows],
                    source=real_h.source[:n_rows], eligible=real_h.eligible[:n_rows],
                    segment=real_h.segment[:n_rows], sha256="synthetic-calendar-prefix", provenance={})
                synthetic_nums = protocol.rng("chance-rank-v1/mem-bench").integers(0, 100, size=(n_rows, 5))
                h = prefix.with_nums(synthetic_nums)
                with tempfile.TemporaryDirectory(prefix="chance-rank-bench-") as workdir:
                    start = time.monotonic()
                    assert engine.compute_target_store(h, configs, workdir, folds=[],
                                                       positions=range(5), ablations=True)
                    elapsed = time.monotonic() - start
                    peak[0] = max(peak[0], process.memory_info().rss)
                    peak_gib = peak[0] / 1024 ** 3
                    extrapolated_gib = peak_gib * (105426 / h.n)  # linear estimate, documented as such
                    print(f"synthetic {label}: rows={h.n} (real calendar prefix, synthetic numbers) "
                          f"seconds={elapsed:.1f} peak_rss_gib={peak_gib:.3f} "
                          f"extrapolated_105426_rows_peak_rss_gib_estimate={extrapolated_gib:.3f}")
                del h
                continue
            h = _tiny_history(n_days=(n + 186) // 187, rows_per_day=187,
                              seed_label=f"budget-synthetic-{n}", n_rows=n)
            if n == 5000:
                with tempfile.TemporaryDirectory(prefix="chance-rank-bench-") as workdir:
                    start = time.monotonic()
                    assert engine.compute_target_store(h, configs, workdir, folds=[],
                                                       positions=range(5), ablations=True)
                    elapsed = time.monotonic() - start
                    any_store = engine.load_store(workdir, "any")
                    pos_store = engine.load_store(workdir, "pos1")
                    assert any_store["ranks_updated"].shape == (110, h.n, 5)
                    # Independent positional-key oracle for every grid id and ablation.
                    cache = models.FeatureCache(h, 0)
                    for c, entry in enumerate(engine._entries(configs, True)):
                        scores = engine._score_for_entry(h, entry, 0, cache)
                        if entry[1] == "interpretable":
                            key = models.ranking_key_config(h, (entry[2], entry[3]), 0,
                                                            cache=cache, scores=scores)
                        else:
                            key = models.ranking_key_ablation(h, entry[0], 0, cache=cache, scores=scores)
                        assert np.array_equal(pos_store["ranks_updated"][c],
                                              winner_rank(key, h.nums[:, 0])), entry[0]
                        engine.release_derived_cache(cache)
                    del cache, any_store, pos_store
                    peak[0] = max(peak[0], process.memory_info().rss)
                    print(f"synthetic {label}: rows={h.n} seconds={elapsed:.1f} "
                          f"peak_rss_gib={peak[0] / 1024**3:.3f}")
            else:
                with tempfile.TemporaryDirectory(prefix="chance-rank-bench-") as workdir:
                    accumulator = engine._AccumulatorFile.create_zero(
                        os.path.join(workdir, "accumulator.dat"), 110, h.n)
                    start = time.monotonic()
                    engine._compute_position(h, 0, engine._entries(configs, True),
                                             configs + [aid for aid, _, _ in models.ABLATIONS],
                                             [], np.zeros(h.n, dtype=bool), accumulator)
                    elapsed = time.monotonic() - start
                    print(f"synthetic {label}: rows={h.n} seconds={elapsed:.1f} "
                          f"peak_rss_gib={peak[0] / 1024**3:.3f} "
                          f"five_position_compute_extrapolated_seconds={elapsed * 5:.1f}")
                    del accumulator
            del h
    finally:
        done.set()
        sampler.join()


def test_trainfreq_frozen_is_constant_within_a_fold():
    h = _tiny_history(n_days=8, rows_per_day=10)
    fold = _explicit_fold(h)
    primary_rows = np.ones(h.n, dtype=bool)
    result = engine.trainfreq_frozen(h, 0, [fold], primary_rows)
    row_idx, ranks = result[0]
    assert row_idx.tolist() == list(np.nonzero(walkforward.rows_in_days(h, *fold.test_days))[0])
    Y = h.nums[:, 0]
    train_mask = h.day < fold.test_days[0]
    counts = np.bincount(Y[train_mask], minlength=100).astype(np.float64)
    expected = winner_rank(np.broadcast_to(counts, (len(row_idx), 100)), Y[row_idx])
    assert np.array_equal(ranks, expected)
