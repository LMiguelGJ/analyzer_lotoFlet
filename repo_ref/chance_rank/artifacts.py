"""Prediction artifacts: per-target npz export under ``outdir/predictions/`` plus the
documenting ``schema.json``, computed strictly from the already-persisted causal store
(``engine.load_store``) and one ``models.FeatureCache`` at a time for the primary
target's full ranking recomputation.
"""

import json
import os

import numpy as np

from chance_rank import engine, models, pipeline, protocol, ranking, walkforward

BASELINE_KINDS = ("recent500", "fixed", "trainfreq_frozen")
MODE_PRIMARY = 1  # bit0: row is in walkforward.primary_mask's population


def predictions_path(outdir, target):
    return os.path.join(outdir, "predictions", f"{target}.npz")


def results_path(outdir, target):
    return os.path.join(outdir, "predictions", f"results_{target}.npz")


def schema_path(outdir):
    return os.path.join(outdir, "predictions", "schema.json")


def _atomic_save_npz(path, **arrays):
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        np.savez_compressed(f, **arrays)
    os.replace(tmp_path, path)


def _atomic_write_json(path, obj):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp_path, path)


def row_id(h, i, p):
    """Stable row id: ``f"{date} {HH:MM} pos{p}"`` for history row ``i``, position ``p``."""
    return f"{h.label(i)} pos{p}"


def gather_rows(folds, test_rows):
    """(row_idx, fold_id) int64 arrays, concatenated across ``folds`` in fold order,
    aligned to ``test_rows[fold.index]["row_idx"]`` (same population/order the pipeline
    uses for per-fold selection and hit vectors)."""
    if not folds:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    row_idx = np.concatenate([test_rows[f.index]["row_idx"] for f in folds]).astype(np.int64)
    fold_id = np.concatenate(
        [np.full(len(test_rows[f.index]["row_idx"]), f.index, dtype=np.int64) for f in folds])
    return row_idx, fold_id


def system_winner_ranks(store, index_all, picks, folds, test_rows, system):
    """(available, ranks) for one system: the chosen config's updated winner rank on
    that fold's test rows, gathered in ``gather_rows`` order; unavailable (``None``
    ranks) if any fold lacks a pick for ``system``."""
    parts = []
    for fold in folds:
        cid = picks[fold.index].get(system)
        if cid is None:
            return False, None
        row_idx = test_rows[fold.index]["row_idx"]
        parts.append(store["ranks_updated"][index_all[cid]][row_idx])
    ranks = np.concatenate(parts).astype(np.uint8) if parts else np.empty(0, dtype=np.uint8)
    return True, ranks


def chosen_config_ids(picks, folds, system):
    """Per-fold chosen config id for ``system``, in fold order; ``""`` where unpicked."""
    return [picks[fold.index].get(system) or "" for fold in folds]


def baseline_winner_ranks(h, store, index_all, pos, folds, primary_rows, row_idx, kind):
    """Updated winner rank for one non-selected baseline, aligned to ``row_idx``
    (``gather_rows`` order): ``"recent500"`` reads the store's fixed recent500 config,
    ``"fixed"`` is a data-free constant ranking, ``"trainfreq_frozen"`` is per-fold
    train-prefix counts (same mask as ``row_idx``, so fold order lines up)."""
    if kind == "recent500":
        return store["ranks_updated"][index_all[pipeline.RECENT500_ID]][row_idx].astype(np.uint8)
    if kind == "fixed":
        return engine.fixed_ranks(h.nums[row_idx, pos]).astype(np.uint8)
    if kind == "trainfreq_frozen":
        trainfreq = engine.trainfreq_frozen(h, pos, folds, primary_rows)
        parts = [trainfreq[fold.index][1] for fold in folds]
        ranks = np.concatenate(parts) if parts else np.empty(0)
        return ranks.astype(np.uint8)
    raise ValueError(f"Unknown baseline kind: {kind!r}")


def _ranking100_per_fold(h, folds, test_rows, config_id_of_fold, pos, cache):
    parts = []
    for fold in folds:
        cid = config_id_of_fold(fold)
        if cid is None:
            return None
        row_idx = test_rows[fold.index]["row_idx"]
        S = models.score_config(h, cid, pos, cache=cache)
        key = models.ranking_key_config(h, cid, pos, cache=cache, scores=S)
        parts.append(ranking.rank_matrix(key[row_idx]))
        del S, key
    return (np.concatenate(parts).astype(np.uint8) if parts
            else np.empty((0, 100), dtype=np.uint8))


def ranking100_for_system(h, picks, folds, test_rows, system, pos, cache):
    """(available, ranking100 uint8 (n_rows, 100)) for one system on the primary
    target: per fold, scores the chosen config once via ``models.score_config`` and
    takes ``ranking.rank_matrix`` of its ordering key on that fold's rows only; ``cache`` is one shared
    ``models.FeatureCache(h, pos)`` (D-scoped: primary target, per-fold winners only).
    """
    result = _ranking100_per_fold(h, folds, test_rows, lambda f: picks[f.index].get(system), pos, cache)
    return (result is not None), result


def ranking100_for_recent500(h, folds, test_rows, pos, cache):
    """Full ranking100 for the fixed ``recent500`` baseline (same config every fold)."""
    return _ranking100_per_fold(h, folds, test_rows, lambda _f: pipeline.RECENT500_ID, pos, cache)


def export_target(h, outdir, target_name, store, folds, picks, test_rows, index_all, primary_rows,
                   systems=pipeline.SYSTEMS, cache=None):
    """Export pre-outcome metadata/rankings separately from outcome-derived results.

    ``results_<target>.npz`` contains y_true and every winner_rank; never expose it
    to a non-reveal inspection. ``pos`` is None for the any-target.
    """
    pos = None if target_name == "any" else int(target_name[3:]) - 1
    row_idx, fold_id = gather_rows(folds, test_rows)
    mode_flags = np.full(len(row_idx), MODE_PRIMARY, dtype=np.uint8)

    results: dict[str, np.ndarray] = {"row_ids": row_idx}
    arrays = {"row_ids": row_idx, "fold_id": fold_id, "mode_flags": mode_flags,
              "timestamps": np.array([h.label(int(i)) for i in row_idx]),
              "cutoff": np.array([h.label(int(i) - 1) for i in row_idx]),
              "systems": np.array(systems), "baselines": np.array(BASELINE_KINDS)}

    for system in systems:
        available, ranks = system_winner_ranks(store, index_all, picks, folds, test_rows, system)
        arrays[f"available__{system}"] = np.array([available])
        results[f"winner_rank__{system}"] = ranks if ranks is not None else np.empty(0, dtype=np.uint8)
        arrays[f"config_id__{system}"] = np.array(chosen_config_ids(picks, folds, system))

    if pos is not None:
        for kind in BASELINE_KINDS:
            results[f"winner_rank__{kind}"] = baseline_winner_ranks(h, store, index_all, pos, folds,
                                                                      primary_rows, row_idx, kind)

    if pos is not None and target_name == protocol.PRIMARY_TARGET:
        owns_cache = cache is None
        cache = cache if cache is not None else models.FeatureCache(h, pos)
        for system in systems:
            available, ranking100 = ranking100_for_system(h, picks, folds, test_rows, system, pos, cache)
            if available:
                arrays[f"ranking100__{system}"] = ranking100
            engine.release_derived_cache(cache)
        arrays["ranking100__recent500"] = ranking100_for_recent500(h, folds, test_rows, pos, cache)
        if owns_cache:
            engine.release_derived_cache(cache)
            del cache

    os.makedirs(os.path.dirname(predictions_path(outdir, target_name)), exist_ok=True)
    _atomic_save_npz(predictions_path(outdir, target_name), **arrays)

    y_true = h.nums[row_idx, pos] if pos is not None else h.nums[row_idx]
    _atomic_save_npz(results_path(outdir, target_name), **results, y_true=y_true)


def export_one_target(h, outdir, target_name, store, folds, primary_rows=None, systems=pipeline.SYSTEMS):
    """Export predictions/results for a single target and return its manifest entry.

    Self-contained: recomputes this target's per-fold picks the same way
    ``pipeline.analyze_secondary`` does, from ``store`` alone, so callers only need to
    hold one target's store array set in memory at a time.
    """
    if primary_rows is None:
        primary_rows = walkforward.primary_mask(h)
    config_ids_all = store["config_ids"].tolist()
    index_all = {cid: i for i, cid in enumerate(config_ids_all)}
    hits_all = pipeline.target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    candidate_ids, candidate_families = pipeline.candidate_entries(config_ids_all)
    candidate_hits = np.array([hits_all[index_all[cid]] for cid in candidate_ids])
    picks, _scores, test_rows = pipeline.per_fold_choice(h, candidate_ids, candidate_families,
                                                           candidate_hits, folds, primary_rows)
    export_target(h, outdir, target_name, store, folds, picks, test_rows, index_all,
                   primary_rows, systems=systems)
    row_idx, _fold_id = gather_rows(folds, test_rows)
    return {
        "n_rows": len(row_idx),
        "predictions_file": os.path.basename(predictions_path(outdir, target_name)),
        "results_file": os.path.basename(results_path(outdir, target_name)),
    }


def export_all(h, outdir, stores, folds, systems=pipeline.SYSTEMS):
    """Export predictions/results for every target present in ``stores`` (keys from
    ``protocol.TARGETS``), then write the documenting ``schema.json``. Self-contained:
    recomputes each target's per-fold picks the same way ``pipeline.analyze_secondary``
    does, so this step can run (and be checkpointed) independently of that one.
    """
    primary_rows = walkforward.primary_mask(h)
    manifest = {target_name: export_one_target(h, outdir, target_name, store, folds, primary_rows,
                                                systems=systems)
                for target_name, store in stores.items()}
    write_schema(outdir, manifest, systems)
    return manifest


def write_schema(outdir, manifest, systems=pipeline.SYSTEMS):
    """Document every array/dtype/meaning under ``outdir/predictions/`` in one
    ``schema.json``, covering both the predictions and the separate results files."""
    schema = {
        "predictions_file_pattern": "predictions/<target>.npz",
        "results_file_pattern": "predictions/results_<target>.npz",
        "row_id_format": 'f"{date} {HH:MM} pos{p}" via artifacts.row_id(h, i, p)',
        "systems": list(systems),
        "baselines": list(BASELINE_KINDS),
        "targets": manifest,
        "arrays": {
            "row_ids": "int64, row index into the history array (h.nums/h.day/...)",
            "timestamps": "ISO local date and HH:MM for each evaluated target",
            "cutoff": "last observed timestamp before target; no target values",
            "fold_id": "int64, outer fold index owning that row's test window",
            "mode_flags": "uint8 bitmask; bit0 (value 1) = primary "
                          "(walkforward.primary_mask population)",
            "systems": "array of the exported system names (unicode strings)",
            "baselines": "array of the exported baseline names for position targets: "
                         "recent500, fixed, trainfreq_frozen",
            "available__<system>": "bool[1], whether that system had a pick in every fold",
            "config_id__<system>": 'unicode string per fold, the chosen config id ("" if '
                                   "unpicked that fold)",
            "ranking100__<system|recent500>": "uint8 (n_rows, 100), primary target only: "
                                              "full best-first ranking of value indices",
        },
        "results_arrays": {
            "row_ids": "int64, matches predictions row_ids for the same target",
            "y_true": "int64, the true value(s): shape (n_rows,) for pos1..pos5, "
                      "(n_rows, 5) for any",
            "winner_rank__<system|baseline>": "uint8, outcome-derived 0-based rank of the "
                                              "true value under the selected config (updated mode); "
                                              "empty when a system is unavailable",
        },
    }
    os.makedirs(os.path.dirname(schema_path(outdir)), exist_ok=True)
    _atomic_write_json(schema_path(outdir), schema)
