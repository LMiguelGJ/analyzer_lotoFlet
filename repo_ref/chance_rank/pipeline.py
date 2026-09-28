"""Single-history analysis pipeline: fixed system order, per-fold selection, primary
contrasts, a scoped secondary check, control-stream contrasts, source-restart, and a
resumable step checkpoint.

``SYSTEMS`` is the fixed 16-entry order: the 12 interpretable families
(``protocol.INTERPRETABLE_FAMILIES``), the 2 supervised families, and the two automatic
selectors. ``PRIMARY_HOLM_FAMILY`` is that order crossed with the two primary baselines
(32 contrasts). A system whose family is absent from the store's candidates -- including
both supervised families before their store exists -- is reported ``available: False``
and contributes ``p=None`` (counted as ``p=1``) to Holm; this is the D-stage "partial".

Scope note: this module implements the checkpoint/resume mechanics and the primary/
control-contrast analysis in full, plus a scoped slice of the secondary analysis
(random-baseline nesting and H1 frozen-vs-updated agreement). The full descriptive
secondary suite (waits/Kaplan-Meier, prob_summary, breakdowns, ablation deltas,
hit_correlation/jaccard) and the full ``run_interpretable`` control-stream orchestration
are not implemented here; see the handoff report.
"""

import gc
import json
import os
import shutil
import time
from datetime import UTC, datetime

import numpy as np

from chance_rank import (
    controls,
    data,
    engine,
    inference,
    metrics,
    models,
    protocol,
    ranking,
    replay,
    supervised,
    walkforward,
)

FAMILIES_INTERP = protocol.INTERPRETABLE_FAMILIES
SUPERVISED_FAMILIES = protocol.SUPERVISED_FAMILIES
SYSTEMS = (*FAMILIES_INTERP, *SUPERVISED_FAMILIES, "select_interpretable", "select_all")
BASELINES_PRIMARY = protocol.BASELINES_PRIMARY
PRIMARY_HOLM_FAMILY = tuple((system, baseline) for system in SYSTEMS for baseline in BASELINES_PRIMARY)

RECENT500_ID = "freq_recent:window=500"

_FAMILY_OF_CONFIG = {cid: family for cid, family, _ in protocol.all_configs(include_supervised=True)}


def target_hits(ranks_updated, k=protocol.PRIMARY_K):
    """Boolean hit matrix aligned to ``ranks_updated``: any-target ranks (``ndim==3``,
    shape ``(n_cfg, n, 5)``) hit when the minimum of the 5 ranks is below ``k``."""
    ranks_updated = np.asarray(ranks_updated)
    if ranks_updated.ndim == 3:
        return (ranks_updated < k).any(axis=2)
    return ranks_updated < k


def candidate_entries(config_ids):
    """(ids, families) restricted to real model families, in the input order.

    Ablation ids are not candidates for family systems (D-decision in the parent task)
    and are dropped here; they are reported descriptively elsewhere.
    """
    ids, families = [], []
    for cid in config_ids:
        family = _FAMILY_OF_CONFIG.get(cid)
        if family is not None:
            ids.append(cid)
            families.append(family)
    return ids, families


def per_fold_choice(h, config_ids, families_of, hits, folds, primary_rows):
    """Per-fold winner per family/selector (inner rows only, via ``walkforward.selections``)
    and its hit vector on that fold's primary test-day rows, for one target's hit matrix.
    """
    picks, scores_table = walkforward.selections(h, config_ids, families_of, hits, folds, primary_rows)
    config_index = {cid: i for i, cid in enumerate(config_ids)}
    test_rows = {}
    for fold in folds:
        mask = primary_rows & walkforward.rows_in_days(h, *fold.test_days)
        row_idx = np.nonzero(mask)[0]
        system_hits = {}
        for system, cid in picks[fold.index].items():
            system_hits[system] = hits[config_index[cid]][row_idx] if cid is not None else None
        test_rows[fold.index] = {"row_idx": row_idx, "hits": system_hits}
    return picks, scores_table, test_rows


def _concat_test_rows(test_rows, folds):
    if not folds:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    row_idx = np.concatenate([test_rows[f.index]["row_idx"] for f in folds])
    fold_of_row = np.concatenate(
        [np.full(len(test_rows[f.index]["row_idx"]), f.index, dtype=np.int64) for f in folds])
    return row_idx, fold_of_row


def _system_hit_vector(test_rows, folds, system):
    """Concatenated hit vector for ``system`` across folds, or ``None`` if any fold is
    missing it (the family/selector was unavailable in at least one fold -> N/A overall).
    """
    parts = []
    for f in folds:
        v = test_rows[f.index]["hits"].get(system)
        if v is None:
            return None
        parts.append(v)
    return np.concatenate(parts) if parts else np.array([])


def _one_system_contrasts(hit_vec, recent500_vec, day, strata, fold_of_row, reps):
    n = len(hit_vec)
    all_true = np.ones(n, dtype=bool)
    diff_uniform = hit_vec.astype(np.float64) - 0.25
    diff_recent500 = hit_vec.astype(np.float64) - recent500_vec.astype(np.float64)

    uniform = inference.contrast(diff_uniform, all_true, day, strata, reps=reps)
    recent500 = inference.contrast(diff_recent500, all_true, day, strata, reps=reps)
    for entry, diff in ((uniform, diff_uniform), (recent500, diff_recent500)):
        # inference.contrast already reports a degenerate (zero-variance) bootstrap as
        # delta/p=1.0/point-mass CIs rather than N/A, so no fallback is needed here; a
        # None delta/p only ever means the true n==0 (unavailable) case.
        entry["delta"] = entry["delta_obs"]
        entry["p_raw"] = entry["p"]
        entry["fold_share"] = inference.fold_positive_share(diff, all_true, fold_of_row)["share"]

    sensitivity = {}
    for block_days, key in ((1, "L1"), (14, "L14")):
        s = inference.contrast(diff_uniform, all_true, day, strata, block_days=block_days, reps=reps)
        sensitivity[key] = {"delta": s["delta_obs"], "p": s["p"]}

    return {"available": True, "uniform": uniform, "recent500": recent500, "sensitivity": sensitivity}


def _systems_contrast(h, candidate_ids, candidate_families, hits, folds, systems, *, reps,
                      baselines=BASELINES_PRIMARY):
    """Per-fold selection, paired contrasts vs uniform/recent500, and Holm over the
    ``systems`` x ``baselines`` family, including unavailable slots as p=1.
    """
    primary_rows = walkforward.primary_mask(h)
    picks, scores_table, test_rows = per_fold_choice(h, candidate_ids, candidate_families, hits,
                                                       folds, primary_rows)
    row_idx, fold_of_row = _concat_test_rows(test_rows, folds)
    day = h.day[row_idx]
    source = h.source[row_idx]
    strata = [(int(fold_of_row[i]), int(source[i])) for i in range(len(row_idx))]

    recent500_vec = None
    if RECENT500_ID in candidate_ids:
        recent500_vec = hits[candidate_ids.index(RECENT500_ID)][row_idx]

    systems_result, contrasts_in_order = {}, []
    for system in systems:
        hit_vec = _system_hit_vector(test_rows, folds, system)
        if hit_vec is None or recent500_vec is None:
            systems_result[system] = {"available": False,
                                       "classification": {"label": "no_disponible", "inestable": False}}
            contrasts_in_order += [(system, baseline, None) for baseline in baselines]
            continue
        entry = _one_system_contrasts(hit_vec, recent500_vec, day, strata, fold_of_row, reps)
        systems_result[system] = entry
        contrasts_in_order += [(system, baseline, entry[baseline]["p"]) for baseline in baselines]

    # a degenerate (zero-variance) contrast reports p=None from inference.contrast, but the
    # system itself is available (delta is a real number): treated as p_adj=1.0 (no evidence
    # against the null), not as the structurally-absent None that classify() cannot compare.
    p_adj = inference.holm([p for _, _, p in contrasts_in_order])
    for (system, baseline, _p), adj in zip(contrasts_in_order, p_adj, strict=True):
        if systems_result[system]["available"]:
            entry = systems_result[system][baseline]
            entry["p_adj"] = 1.0 if adj is None else adj
            entry["holm_reject"] = entry["p_adj"] < protocol.ALPHA

    for system in systems:
        entry = systems_result[system]
        if not entry["available"]:
            continue
        sens_holm = inference.holm([s["p"] for s in entry["sensitivity"].values()])
        for s, adj in zip(entry["sensitivity"].values(), sens_holm, strict=True):
            s["p_adj"] = 1.0 if adj is None else adj
            s["holm_reject"] = s["p_adj"] < protocol.ALPHA
        if baselines == BASELINES_PRIMARY:
            entry["classification"] = inference.classify(entry)

    return systems_result, len(row_idx), scores_table, picks


def analyze_primary(h, store, folds, *, reps=protocol.BOOT_REPS):
    """Primary Top-25/H1/pos1 analysis: fixed 32-family Holm, D10 classification.

    ``store``: ``engine.load_store(workdir, "pos1")`` result (positions=(0,) causal
    ranks). A family/selector not present among ``store["config_ids"]`` -- including
    both supervised families before their store exists -- is ``available: False``.
    """
    config_ids_all = store["config_ids"].tolist()
    hits_all = target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    candidate_ids, candidate_families = candidate_entries(config_ids_all)
    index_all = {cid: i for i, cid in enumerate(config_ids_all)}
    candidate_hits = np.array([hits_all[index_all[cid]] for cid in candidate_ids])

    systems_result, n_primary, _scores, _picks = _systems_contrast(
        h, candidate_ids, candidate_families, candidate_hits, folds, SYSTEMS, reps=reps)

    stage = "complete" if all(systems_result[s]["available"] for s in SYSTEMS) else "partial"
    mde = inference.mde_top25(n_primary, len(PRIMARY_HOLM_FAMILY))
    return {"systems": systems_result, "n_primary_targets": n_primary, "mde": mde,
            "holm_family_order": list(PRIMARY_HOLM_FAMILY), "stage": stage}


def random_baseline_nested(h, realization, k_values, rows, pos=0):
    """Top-K hit rates for one random realization; every K reuses the same ranking
    (frozen origin key per row), so hits at a smaller K imply hits at every larger K.
    """
    ranks = engine.random_ranks(h, realization, h.nums[:, pos], rows)
    n = len(rows)
    result = {k: {"n": n, "rate": float((ranks < k).mean()) if n else None} for k in k_values}
    return result, ranks


def horizon_frozen_vs_updated(h, store, fold, primary_rows):
    """H1 updated vs H1 frozen ranks for one fold's horizon blocks; must match exactly
    (both reuse the same causal score row at block origin), plus the dropped-target count.
    """
    blocks, dropped = replay.horizon_blocks(h, fold, primary_rows)
    if blocks.shape[0] == 0:
        return {"n_blocks": 0, "dropped": int(dropped), "h1_matches": True}
    updated_h1 = replay.updated_block_ranks(store["ranks_updated"][0], blocks)[:, 0]
    fold_blocks_mask = store["fold_id_per_block"] == fold.index
    frozen_h1 = store["ranks_frozen"][0][fold_blocks_mask][:, 0]
    return {"n_blocks": int(blocks.shape[0]), "dropped": int(dropped),
            "h1_matches": bool(np.array_equal(updated_h1, frozen_h1))}


def _system_gathered(arr_all, index_all, picks, folds, test_rows, system):
    """Concatenate ``arr_all[cfg]`` rows for whichever config ``system`` was picked in
    that row's fold (row order = fold order, via ``test_rows``); ``None`` if any fold
    lacks the system (family/selector unavailable in at least one fold -> N/A overall).
    """
    parts = []
    for fold in folds:
        cid = picks[fold.index].get(system)
        if cid is None:
            return None
        row_idx = test_rows[fold.index]["row_idx"]
        parts.append(arr_all[index_all[cid]][row_idx])
    return np.concatenate(parts, axis=0) if parts else arr_all[:0]


def _gathered_rows(values, folds, test_rows):
    """Concatenate raw (config-independent) row values across folds' test rows."""
    parts = [values[test_rows[fold.index]["row_idx"]] for fold in folds]
    return np.concatenate(parts, axis=0) if parts else values[:0]


def _full_hit_and_mask(h, hits_all, index_all, picks, folds, test_rows, system):
    """Full-length (segment-respecting) hit/mask vectors for ``waits``: masked at a
    row iff some fold picked ``system`` and that row is in that fold's test window.
    """
    hit_full = np.zeros(h.n, dtype=bool)
    mask_full = np.zeros(h.n, dtype=bool)
    for fold in folds:
        cid = picks[fold.index].get(system)
        if cid is None:
            return None, None
        row_idx = test_rows[fold.index]["row_idx"]
        hit_full[row_idx] = hits_all[index_all[cid]][row_idx]
        mask_full[row_idx] = True
    return hit_full, mask_full


def topk_all_systems(store, index_all, picks, folds, test_rows, systems, k_values, nums_gathered=None):
    """Top-K (all protocol K values, positional or any-variant) per system; ``None``
    entries for systems unavailable in at least one fold."""
    result = {}
    for system in systems:
        ranks_gathered = _system_gathered(store["ranks_updated"], index_all, picks, folds,
                                            test_rows, system)
        if ranks_gathered is None:
            result[system] = None
            continue
        n = len(ranks_gathered)
        all_true = np.ones(n, dtype=bool)
        if nums_gathered is not None:
            result[system] = {k: metrics.topk_summary(ranks_gathered, all_true, k, nums=nums_gathered)
                               for k in k_values}
        else:
            result[system] = {k: metrics.topk_summary(ranks_gathered, all_true, k) for k in k_values}
    return result


def horizon_all_systems(h, store, folds, picks, primary_rows, index_all, systems, k=protocol.PRIMARY_K):
    """Updated/frozen horizon summaries (mean hits, P(at least one)) for H in
    ``protocol.HORIZONS``, per system, plus dropped-target counts and block population.
    ``None`` entries for systems unavailable in at least one fold.
    """
    blocks_by_fold = {fold.index: replay.horizon_blocks(h, fold, primary_rows) for fold in folds}
    result = {}
    for system in systems:
        per_h = {}
        available = True
        updated_by_h = {H: [] for H in protocol.HORIZONS}
        frozen_by_h = {H: [] for H in protocol.HORIZONS}
        dropped_total, n_blocks_total = 0, 0
        for fold in folds:
            cid = picks[fold.index].get(system)
            if cid is None:
                available = False
                break
            blocks, dropped = blocks_by_fold[fold.index]
            dropped_total += dropped
            if blocks.shape[0] == 0:
                continue
            n_blocks_total += blocks.shape[0]
            c = index_all[cid]
            updated_block_ranks = replay.updated_block_ranks(store["ranks_updated"][c], blocks)
            fold_mask = store["fold_id_per_block"] == fold.index
            frozen_block_ranks = store["ranks_frozen"][c][fold_mask]
            for H in protocol.HORIZONS:
                hits_u, any_u = replay.horizon_hits(updated_block_ranks, k, H)
                hits_f, any_f = replay.horizon_hits(frozen_block_ranks, k, H)
                updated_by_h[H].append((hits_u, any_u))
                frozen_by_h[H].append((hits_f, any_f))
        if not available:
            result[system] = None
            continue
        for H in protocol.HORIZONS:
            def _summary(parts):
                if not parts:
                    return {"mean_hits": None, "p_at_least_one": None}
                hits = np.concatenate([p[0] for p in parts])
                anyv = np.concatenate([p[1] for p in parts])
                return {"mean_hits": float(hits.mean()), "p_at_least_one": float(anyv.mean())}
            per_h[H] = {
                "n_blocks": n_blocks_total, "dropped": int(dropped_total),
                "population": n_blocks_total * protocol.HORIZON_BLOCK + int(dropped_total),
                "updated": _summary(updated_by_h[H]), "frozen": _summary(frozen_by_h[H]),
            }
        result[system] = per_h
    return result


def baselines_secondary(h, pos, folds, primary_rows, k_values, realizations, index_all=None,
                          ranks_updated=None):
    """Uniform analytic, 100-realization random (mean/p2.5/p97.5), fixed permutation,
    per-fold trainfreq_frozen, and the fixed recent500 config -- all on primary rows.
    """
    rows = np.nonzero(primary_rows)[0]
    uniform = {k: k / 100 for k in k_values}

    random_rates = {k: [] for k in k_values}
    for realization in realizations:
        result, _ranks = random_baseline_nested(h, realization, k_values, rows, pos=pos)
        for k in k_values:
            random_rates[k].append(result[k]["rate"])
    random_result = {}
    for k in k_values:
        rates = np.array(random_rates[k])
        random_result[k] = {"mean": float(rates.mean()), "p2_5": float(np.percentile(rates, 2.5)),
                             "p97_5": float(np.percentile(rates, 97.5))}

    fixed_ranks_vec = engine.fixed_ranks(h.nums[rows, pos])
    fixed = {k: float((fixed_ranks_vec < k).mean()) for k in k_values}

    trainfreq = engine.trainfreq_frozen(h, pos, folds, primary_rows)
    trainfreq_result = {}
    for fold in folds:
        _row_idx, ranks = trainfreq[fold.index]
        trainfreq_result[fold.index] = {k: float((ranks < k).mean()) if len(ranks) else None
                                          for k in k_values}

    recent500 = None
    if index_all is not None and ranks_updated is not None and RECENT500_ID in index_all:
        r500_ranks = ranks_updated[index_all[RECENT500_ID]][rows]
        recent500 = {k: float((r500_ranks < k).mean()) for k in k_values}

    return {"uniform": uniform, "random": random_result, "fixed": fixed,
            "trainfreq_frozen": trainfreq_result, "recent500": recent500}


def prob_summary_for_system(store, index_all, picks, folds, test_rows, system):
    """``metrics.prob_summary`` over the fold-wise chosen config's rows, restricted to
    rows where that fold's pick is a probabilistic family; other rows are excluded and
    counted (D-scoped: probabilistic status is a per-family constant, params-independent).
    """
    p_true_parts, brier_parts, mass_parts, hits25_parts = [], [], [], []
    excluded = 0
    for fold in folds:
        cid = picks[fold.index].get(system)
        row_idx = test_rows[fold.index]["row_idx"]
        if cid is None:
            excluded += len(row_idx)
            continue
        family = _FAMILY_OF_CONFIG.get(cid)
        if not models.is_probabilistic(family, None):
            excluded += len(row_idx)
            continue
        c = index_all[cid]
        p_true_parts.append(store["p_true"][c][row_idx])
        brier_parts.append(store["brier"][c][row_idx])
        mass_parts.append(store["topk_mass"][c][row_idx])
        hits25_parts.append(store["ranks_updated"][c][row_idx] < protocol.PRIMARY_K)
    if not p_true_parts:
        return {"available": False, "excluded": excluded, "n": 0}
    p_true = np.concatenate(p_true_parts)
    brier = np.concatenate(brier_parts)
    mass = np.concatenate(mass_parts)
    hits25 = np.concatenate(hits25_parts)
    mask = np.ones(len(p_true), dtype=bool)
    summary = metrics.prob_summary(p_true, brier, mass, hits25, mask)
    summary["available"] = True
    summary["excluded"] = excluded
    summary["n"] = len(p_true)
    return summary


def breakdown_for_system(h, store, index_all, picks, folds, test_rows, system):
    """Primary Top-25 breakdown by fold, source and month (``YYYY-MM``) for the fold-wise
    chosen config; ``None`` if the system is unavailable in at least one fold."""
    hit_parts, fold_parts, source_parts, month_parts = [], [], [], []
    for fold in folds:
        cid = picks[fold.index].get(system)
        if cid is None:
            return None
        row_idx = test_rows[fold.index]["row_idx"]
        c = index_all[cid]
        hit_parts.append(store["ranks_updated"][c][row_idx] < protocol.PRIMARY_K)
        fold_parts.append(np.full(len(row_idx), fold.index))
        source_parts.append(h.source[row_idx])
        month_parts.append(np.array([h.dates[h.day[i]][:7] for i in row_idx]))
    hit = np.concatenate(hit_parts)
    fold_arr = np.concatenate(fold_parts)
    source_arr = np.concatenate(source_parts)
    month_arr = np.concatenate(month_parts)
    mask = np.ones(len(hit), dtype=bool)
    by_source = metrics.breakdown(hit, source_arr, mask)
    return {
        "by_fold": metrics.breakdown(hit, fold_arr, mask),
        "by_source": {h.sources[key]: value for key, value in by_source.items()},
        "by_month": metrics.breakdown(hit, month_arr, mask),
    }


def ablation_deltas(h, store, index_all, primary_rows, folds):
    """Each ablation's primary Top-25 rate and delta vs its full (non-ablated) parent
    config, aggregated over the union of all outer test-day rows (ablations are fixed,
    never selected per fold)."""
    mask = np.zeros(h.n, dtype=bool)
    for fold in folds:
        mask |= primary_rows & walkforward.rows_in_days(h, *fold.test_days)
    rows = np.nonzero(mask)[0]
    result = {}
    for aid, kind, params in models.ABLATIONS:
        if aid not in index_all or len(rows) == 0:
            continue
        ranks = store["ranks_updated"][index_all[aid]][rows]
        rate = float((ranks < protocol.PRIMARY_K).mean())
        if kind == "notebook_ablation":
            parent_id = protocol.config_id("notebook", {"weights": [0.45, 0.45, 0.10],
                                                          "window": params["window"]})
        else:
            parent_id = protocol.config_id("ensemble", {"method": "borda"})
        parent_rate = None
        if parent_id in index_all:
            parent_ranks = store["ranks_updated"][index_all[parent_id]][rows]
            parent_rate = float((parent_ranks < protocol.PRIMARY_K).mean())
        result[aid] = {"rate": rate, "parent": parent_id, "parent_rate": parent_rate,
                        "delta": (rate - parent_rate) if parent_rate is not None else None}
    return result


def hit_correlation_matrix(test_rows, folds, systems):
    vectors = {}
    for system in systems:
        v = _system_hit_vector(test_rows, folds, system)
        if v is not None:
            vectors[system] = v
    result = {}
    names = sorted(vectors)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            mask = np.ones(len(vectors[a]), dtype=bool)
            result[f"{a}|{b}"] = metrics.hit_correlation(vectors[a], vectors[b], mask)
    return result


def jaccard_and_hit_correlation(test_rows, folds, systems=protocol.INTERPRETABLE_FAMILIES):
    """Cross-system Top-25 hit-vector phi correlation (primary rows). Row-wise Jaccard
    between systems' chosen Top-25 lists is not computed (D13): recomputing scores per
    (fold, config) pair to build it measured ~6.5GB peak, over the plan's ~4GB budget.
    """
    hit_corr = hit_correlation_matrix(test_rows, folds, systems)
    return {"hit_correlation": hit_corr, "jaccard": "skipped: memory budget (D13)"}


def secondary_mask_topk(h, store, index_all, picks, folds):
    """Top-25 rate on the secondary (next-available-record, non-consecutive) mask for
    ``select_interpretable``'s per-fold winner; never the next real draw (D2/plan)."""
    sec_mask = walkforward.secondary_mask(h)
    result = {}
    for fold in folds:
        cid = picks[fold.index].get("select_interpretable")
        if cid is None:
            result[fold.index] = None
            continue
        mask = sec_mask & walkforward.rows_in_days(h, *fold.test_days)
        row_idx = np.nonzero(mask)[0]
        if len(row_idx) == 0:
            result[fold.index] = {"n": 0, "rate": None}
            continue
        ranks = store["ranks_updated"][index_all[cid]][row_idx]
        result[fold.index] = {"n": len(row_idx), "rate": float((ranks < protocol.PRIMARY_K).mean())}
    return result


def analyze_secondary(h, stores, folds, *, k_values=protocol.K_VALUES,
                       realizations=tuple(range(protocol.RANDOM_REALIZATIONS))):
    """Full descriptive secondary suite (no p-values): Top-K/any-variant, horizons,
    baselines, waits/Kaplan-Meier, prob_summary, breakdowns and ablation deltas for every
    target present in ``stores`` (keys from ``protocol.TARGETS``); plus one pos1
    cross-system hit_correlation/jaccard analysis and the secondary_mask
    (next-available-record) Top-25 report for ``select_interpretable``.

    ``stores``: ``{target_name: engine.load_store(...)}`` for whichever of
    ``protocol.TARGETS`` are available; a target absent from ``stores`` is simply not
    reported (caller's choice, e.g. a smoke run computing only pos1).
    """
    primary_rows = walkforward.primary_mask(h)
    targets_result = {}

    for target_name, store in stores.items():
        pos = None if target_name == "any" else int(target_name[3:]) - 1
        config_ids_all = store["config_ids"].tolist()
        index_all = {cid: i for i, cid in enumerate(config_ids_all)}
        hits25_all = target_hits(store["ranks_updated"], protocol.PRIMARY_K)
        candidate_ids, candidate_families = candidate_entries(config_ids_all)
        candidate_hits = np.array([hits25_all[index_all[cid]] for cid in candidate_ids])

        picks, _scores, test_rows = per_fold_choice(h, candidate_ids, candidate_families,
                                                     candidate_hits, folds, primary_rows)

        nums_gathered = _gathered_rows(h.nums, folds, test_rows) if pos is None else None
        topk = topk_all_systems(store, index_all, picks, folds, test_rows, SYSTEMS, k_values,
                                 nums_gathered)

        if pos is not None:
            horizon = horizon_all_systems(h, store, folds, picks, primary_rows, index_all, SYSTEMS)
            baselines = baselines_secondary(h, pos, folds, primary_rows, k_values, realizations,
                                             index_all=index_all, ranks_updated=store["ranks_updated"])

            waits = {}
            for system in SYSTEMS:
                hit_full, mask_full = _full_hit_and_mask(h, hits25_all, index_all, picks, folds,
                                                           test_rows, system)
                if hit_full is None:
                    waits[system] = None
                    continue
                durations, events = metrics.waits(hit_full, mask_full, h.segment)
                waits[system] = {"n_spells": len(durations),
                                  "km": metrics.kaplan_meier(durations, events, max_n=60)}
            if RECENT500_ID in index_all:
                hit_r500 = store["ranks_updated"][index_all[RECENT500_ID]] < protocol.PRIMARY_K
                durations, events = metrics.waits(hit_r500, primary_rows, h.segment)
                waits["recent500"] = {"n_spells": len(durations),
                                       "km": metrics.kaplan_meier(durations, events, max_n=60)}
            ranks0 = engine.random_ranks(h, 0, h.nums[:, pos], np.arange(h.n))
            hit_rand0 = ranks0 < protocol.PRIMARY_K
            durations, events = metrics.waits(hit_rand0, primary_rows, h.segment)
            waits["uniform_random_0"] = {"n_spells": len(durations),
                                          "km": metrics.kaplan_meier(durations, events, max_n=60)}

            prob = {system: prob_summary_for_system(store, index_all, picks, folds, test_rows, system)
                    for system in SYSTEMS}
            breakdown = {system: breakdown_for_system(h, store, index_all, picks, folds, test_rows,
                                                        system) for system in SYSTEMS}
            ablations = ablation_deltas(h, store, index_all, primary_rows, folds)
        else:
            horizon, baselines, waits, prob, breakdown, ablations = None, None, None, None, None, None

        targets_result[target_name] = {
            "topk": topk, "horizon": horizon, "baselines": baselines, "waits": waits,
            "prob_summary": prob, "breakdown": breakdown, "ablations": ablations,
        }

    cross_system, secondary_mask_result = None, None
    if "pos1" in stores:
        store = stores["pos1"]
        config_ids_all = store["config_ids"].tolist()
        index_all = {cid: i for i, cid in enumerate(config_ids_all)}
        hits25_all = target_hits(store["ranks_updated"], protocol.PRIMARY_K)
        candidate_ids, candidate_families = candidate_entries(config_ids_all)
        candidate_hits = np.array([hits25_all[index_all[cid]] for cid in candidate_ids])
        picks, _scores, test_rows = per_fold_choice(h, candidate_ids, candidate_families,
                                                     candidate_hits, folds, primary_rows)
        cross_system = jaccard_and_hit_correlation(test_rows, folds)
        secondary_mask_result = secondary_mask_topk(h, store, index_all, picks, folds)

    return {"targets": targets_result, "cross_system_pos1": cross_system,
            "secondary_mask_select_interpretable_next_available_record": secondary_mask_result}


def source_restart(h, folds, picks):
    """Re-score select_interpretable's per-fold winners from the first row of the second
    source, so no state from before the switch leaks into post-switch predictions.
    Warmup applies fresh inside the sub-history (D-decision in the parent task).
    """
    if len(h.sources) < 2:
        return {"n": 0, "rate": None, "na_folds": 0, "note": "single source, no restart boundary"}

    switch_row = int(np.argmax(h.source == 1))
    entries = [(h.dates[h.day[i]], f"{h.hour[i]:02d}:{h.slot[i] % 60:02d}", h.nums[i].tolist(),
                h.sources[h.source[i]]) for i in range(switch_row, h.n)]
    sub_h = data.make_history(entries, sources=h.sources)
    sub_primary = walkforward.primary_mask(sub_h)

    cache = models.FeatureCache(sub_h, 0)
    hit_count, opp_count, na_folds = 0, 0, 0
    for fold in folds:
        cid = picks.get(fold.index, {}).get("select_interpretable")
        if cid is None:
            na_folds += 1
            continue
        orig_mask = (h.day >= fold.test_days[0]) & (h.day < fold.test_days[1]) & (h.source == 1)
        orig_idx = np.nonzero(orig_mask)[0]
        sub_idx = orig_idx - switch_row
        clipped = np.clip(sub_idx, 0, sub_h.n - 1)
        keep = (sub_idx >= 0) & (sub_idx < sub_h.n) & sub_primary[clipped]
        sub_idx = sub_idx[keep]
        if len(sub_idx) == 0:
            continue
        key = models.ranking_key_config(sub_h, cid, 0, cache=cache)
        ranks = ranking.winner_rank(key[sub_idx], sub_h.nums[sub_idx, 0])
        hit_count += int((ranks < protocol.PRIMARY_K).sum())
        opp_count += len(sub_idx)

    rate = hit_count / opp_count if opp_count else None
    return {"n": opp_count, "rate": rate, "na_folds": na_folds}


def run_control(h_ctrl, workdir, folds, configs, *, reps=protocol.BOOT_REPS, run_identity=None):
    """Position-0-only causal store for a control history; contrasts for every present
    interpretable family plus the auxiliary ``recent_decay`` system (D11: best internal
    selection among ``decay`` U ``freq_recent`` configs) vs uniform/recent500. The store
    is deleted after analysis so only the JSON result is kept on disk.
    """
    os.makedirs(workdir, exist_ok=True)
    engine.compute_target_store(h_ctrl, configs, workdir, positions=(0,), include_any=False,
                                 ablations=False, folds=folds,
                                 run_identity=run_identity if run_identity is not None else {"reps": reps})
    store = engine.load_store(workdir, "pos1")
    config_ids_all = store["config_ids"].tolist()
    hits_all = target_hits(store["ranks_updated"], protocol.PRIMARY_K)
    families_of_all = [_FAMILY_OF_CONFIG.get(cid) for cid in config_ids_all]

    interp_index = [i for i, f in enumerate(families_of_all) if f in FAMILIES_INTERP]
    interp_ids = [config_ids_all[i] for i in interp_index]
    interp_families = [families_of_all[i] for i in interp_index]
    interp_hits = hits_all[interp_index]
    systems_result, n_primary, _scores, _picks = _systems_contrast(
        h_ctrl, interp_ids, interp_families, interp_hits, folds, SYSTEMS, reps=reps)

    decay_index = [i for i, f in enumerate(families_of_all) if f in ("decay", "freq_recent")]
    signal_systems = ("transition", "carry", "time", "recent_decay", "category")
    signal_ids = [*interp_ids, *[f"recent_decay/{config_ids_all[i]}" for i in decay_index]]
    signal_families = [*interp_families, *(["recent_decay"] * len(decay_index))]
    signal_hits = np.concatenate((interp_hits, hits_all[decay_index]), axis=0)
    signal_result, _n, _s, _p = _systems_contrast(
        h_ctrl, signal_ids, signal_families, signal_hits, folds, signal_systems,
        reps=reps, baselines=("uniform",))
    systems_result["recent_decay"] = signal_result["recent_decay"]

    for path in (engine._target_path(workdir, "pos1"), engine._meta_path(workdir, "pos1")):
        if os.path.exists(path):
            os.remove(path)

    return {"systems": systems_result, "n_primary_targets": n_primary,
            "holm_family_order": list(PRIMARY_HOLM_FAMILY),
            "signal_holm_family_order": [(s, "uniform") for s in signal_systems],
            "signal_systems": signal_result}


def stream_rejects(control_result):
    """True if any available system in a control result rejects Holm vs uniform or
    recent500 (healthy-stream gate input, D: max 2/20 rejecting streams)."""
    for system in SYSTEMS:
        entry = control_result["systems"].get(system, {})
        if not entry.get("available"):
            continue
        if entry["uniform"]["holm_reject"] or entry["recent500"]["holm_reject"]:
            return True
    return False


def _atomic_write_json(path, obj):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp_path, path)


def _step_path(outdir, step):
    return os.path.join(outdir, "steps", f"{step}.json")


def _step_done(outdir, step, data_sha, identity=None):
    path = _step_path(outdir, step)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    if record.get("protocol_hash") != protocol.protocol_hash():
        raise ValueError(f"run_interpretable: protocol hash changed for step {step!r} "
                          f"(existing {record.get('protocol_hash')}, current {protocol.protocol_hash()})")
    if record.get("data_sha") != data_sha:
        raise ValueError(f"run_interpretable: data sha changed for step {step!r}")
    if identity is not None and record.get("identity") != identity:
        raise ValueError(f"run identity mismatch for step {step!r}")
    return record["result"]


def _mark_step_done(outdir, step, data_sha, result, identity=None):
    path = _step_path(outdir, step)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"protocol_hash": protocol.protocol_hash(), "data_sha": data_sha,
                   "identity": identity, "result": result}, f)
    os.replace(tmp_path, path)


def _candidate_inventory(h, configs):
    """All candidate ids (interpretable + ablations), supervised marked ``"pending"``,
    and a dedup report: config/ablation ids whose primary-target (pos0) winner-rank
    sequence exactly matches an earlier id are listed as duplicates but kept as
    candidates (never dropped -- D-decision, parent task).
    """
    interp_ids = list(configs)
    ablation_ids = [aid for aid, _kind, _params in models.ABLATIONS]
    supervised_ids = [cid for cid, family, _params in protocol.all_configs(include_supervised=True)
                       if family in protocol.SUPERVISED_FAMILIES]

    cache = models.FeatureCache(h, 0)
    seen, duplicates = {}, {}
    for cid in (*interp_ids, *ablation_ids):
        S = (models.score_config(h, cid, 0, cache=cache) if cid in interp_ids
             else models.score_ablation(h, cid, 0, cache=cache))
        key = ranking.winner_rank(S, h.nums[:, 0]).tobytes()
        if key in seen:
            duplicates[cid] = seen[key]
        else:
            seen[key] = cid
        del S
        engine.release_derived_cache(cache)

    return {"interpretable": interp_ids, "ablations": ablation_ids,
            "supervised": dict.fromkeys(supervised_ids, "pending"),
            "n_candidates": len(interp_ids) + len(ablation_ids), "duplicates": duplicates}


def _control_stream_names():
    names = [("healthy", i) for i in range(1, protocol.HEALTHY_STREAMS + 1)]
    for kind in protocol.SIGNAL_TYPES:
        for q in protocol.SIGNAL_Q:
            for i in range(1, protocol.SIGNAL_SEEDS + 1):
                names.append(("signal", kind, q, i))
    names += [("order", i) for i in range(1, protocol.ORDER_PERMUTATIONS + 1)]
    return names


def _control_stream_id(entry):
    if entry[0] == "healthy":
        return f"healthy_{entry[1]:03d}"
    if entry[0] == "signal":
        _kind_tag, kind, q, i = entry
        return f"signal_{kind}_{q}_{i:03d}"
    return f"order_{entry[1]:03d}"


def _build_control_history(h, entry):
    if entry[0] == "healthy":
        return controls.healthy_history(h, entry[1])
    if entry[0] == "signal":
        _kind_tag, kind, q, i = entry
        history, _info = controls.signal_history(h, kind, q, i)
        return history
    return controls.order_null_history(h, entry[1])


def _control_path(outdir, name):
    return os.path.join(outdir, "controls", f"{name}.json")


def _control_done(outdir, name, data_sha, identity=None):
    path = _control_path(outdir, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    if record.get("protocol_hash") != protocol.protocol_hash():
        raise ValueError(f"run_interpretable: protocol hash changed for control {name!r} "
                          f"(existing {record.get('protocol_hash')}, current {protocol.protocol_hash()})")
    if record.get("data_sha") != data_sha:
        raise ValueError(f"run_interpretable: data sha changed for control {name!r}")
    if identity is not None and record.get("identity") != identity:
        raise ValueError(f"run identity mismatch for control {name!r}")
    return record["result"]


def _mark_control_done(outdir, name, data_sha, result, identity=None):
    path = _control_path(outdir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"protocol_hash": protocol.protocol_hash(), "data_sha": data_sha,
                   "identity": identity, "result": result}, f)
    os.replace(tmp_path, path)


def _write_status(outdir, state, reason, next_step, identity=None):
    path = os.path.join(outdir, "status.json")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"state": state, "reason": reason, "next_step": next_step,
                   "identity": identity}, f)
    os.replace(tmp_path, path)


def _log_jsonl(outdir, record):
    path = os.path.join(outdir, "run_log.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _summarize_controls(control_results, primary_result=None):
    """Healthy/signal gates, plus the order-null per-system delta distribution with the
    real (unpermuted) primary delta's rank among the 20 permutation deltas, labelled
    'conditional on exchangeability' (never mixed with the primary inference).
    """
    healthy_names = [n for n in control_results if n.startswith("healthy_")]
    n_rejecting = sum(1 for n in healthy_names if stream_rejects(control_results[n]))
    healthy_gate = controls.healthy_gate(n_rejecting)

    signal_decisions = {kind: [] for kind in protocol.SIGNAL_TYPES}
    for kind in protocol.SIGNAL_TYPES:
        for i in range(1, protocol.SIGNAL_SEEDS + 1):
            name = f"signal_{kind}_0.1_{i:03d}"
            if name not in control_results:
                continue
            relevant = controls.RELEVANT_SYSTEM[kind]
            systems = control_results[name].get("signal_systems", {})
            rejected = any(systems.get(fam, {}).get("available") and systems[fam]["uniform"]["holm_reject"]
                           for fam in relevant if fam in systems)
            signal_decisions[kind].append(rejected)
    signal_gate = controls.signal_gate(signal_decisions)

    order_names = sorted(n for n in control_results if n.startswith("order_"))
    order_distribution = {}
    systems_seen = set()
    for name in order_names:
        systems_seen.update(control_results[name]["systems"].keys())
    for system in systems_seen:
        deltas_uniform, deltas_recent500 = [], []
        for name in order_names:
            entry = control_results[name]["systems"].get(system)
            if entry and entry.get("available"):
                deltas_uniform.append(entry["uniform"]["delta"])
                deltas_recent500.append(entry["recent500"]["delta"])
        entry = {"deltas_uniform": deltas_uniform, "deltas_recent500": deltas_recent500,
                 "note": "conditional on exchangeability"}
        real = (primary_result or {}).get("systems", {}).get(system)
        if real and real.get("available"):
            real_u, real_r = real["uniform"]["delta"], real["recent500"]["delta"]
            entry["real_delta_uniform"] = real_u
            entry["real_delta_recent500"] = real_r
            entry["rank_among_permutations_uniform"] = (
                1 + sum(1 for d in deltas_uniform if d >= real_u)) if deltas_uniform else None
            entry["rank_among_permutations_recent500"] = (
                1 + sum(1 for d in deltas_recent500 if d >= real_r)) if deltas_recent500 else None
        order_distribution[system] = entry

    return {"healthy_gate": healthy_gate, "signal_gate": signal_gate,
            "order_null_distribution": order_distribution}


def _code_hash():
    return engine.code_hash()


_MAIN_STEPS = ("validation", "protocol", "fold_manifest", "inventory", "mde", "store",
               "primary", "secondary", "export", "source_restart")

_SUPERVISED_REDUCED_LABEL = (
    "muestra reducida exploratoria, no criterio completo, ventana fija de 30000, "
    "refit una vez por fold externo (no cada 7 dias)"
)


def _supervised_reduced_path(outdir):
    return os.path.join(outdir, "supervised_reduced.json")


def _supervised_reduced_partial_dir(outdir):
    return os.path.join(outdir, "supervised_reduced_partial")


def _supervised_reduced_partial_path(outdir, family, pos, fold_index):
    return os.path.join(_supervised_reduced_partial_dir(outdir), f"{family}_pos{pos + 1}_fold{fold_index}.json")


def _supervised_reduced_identity(h, folds):
    return {"protocol_hash": protocol.protocol_hash(), "data_sha": h.sha256,
            "code_hash": _code_hash(),
            "folds_hash": engine._hash_json([{"index": f.index, "test_days": f.test_days,
                                              "inner": f.inner} for f in folds]),
            "grid": {"logistic": supervised.REDUCED_LOGISTIC_CONFIG,
                     "tree": supervised.REDUCED_TREE_CONFIG, "window": supervised.REDUCED_WINDOW}}


def _supervised_reduced_fit(h, outdir, identity, family, pos, fold_index, fold, matrix):
    """Compute (or load) one (family, pos, fold) fit and checkpoint it atomically under
    ``outdir/supervised_reduced_partial/`` before returning it, so a mid-run kill loses
    at most the one fit in flight rather than the whole 140-fit run.
    """
    part_path = _supervised_reduced_partial_path(outdir, family, pos, fold_index)
    fit_identity = {**identity, "family": family, "pos": pos, "fold_index": fold_index}
    if os.path.exists(part_path):
        with open(part_path, encoding="utf-8") as f:
            part = json.load(f)
        if part.get("identity") != fit_identity:
            raise ValueError("run identity mismatch for supervised_reduced partial fit "
                              f"{family}/pos{pos + 1}/fold{fold_index}")
        return part["result"]
    fit_result = supervised.reduced_fit_one(h, pos, fold, family, matrix=matrix)
    _atomic_write_json(part_path, {"identity": fit_identity, "result": fit_result})
    return fit_result


def run_supervised_reduced(h, outdir, folds=None, positions=(0, 1, 2, 3, 4)):
    """CR-7 opt-in reduced exploratory subset: one logistic config, one tree config,
    per position, window=30000, refit once per outer fold (not the full plan's 7-day
    refit schedule). Separate from ``_MAIN_STEPS``/``run_interpretable``; never called
    by that orchestrator.

    Checkpoints after every individual (family, position, fold) fit under
    ``outdir/supervised_reduced_partial/<family>_pos<p>_fold<j>.json`` (each guarded by
    the same protocol/data/code identity as the final file), so a mid-run kill loses at
    most the fit in flight. Once every fit is present the final ``supervised_reduced.json``
    is assembled with the same schema/label as before; partial files are left on disk
    (cheap, and useful for inspecting/resuming a still-in-progress run).
    """
    os.makedirs(outdir, exist_ok=True)
    if folds is None:
        folds = walkforward.outer_folds(len(h.dates))
    identity = _supervised_reduced_identity(h, folds)
    path = _supervised_reduced_path(outdir)

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        if record.get("identity") != identity:
            raise ValueError("run identity mismatch for supervised_reduced")
        return record["result"]

    os.makedirs(_supervised_reduced_partial_dir(outdir), exist_ok=True)
    families_result = {family: {"positions": {}, "wall_time_seconds": 0.0}
                       for family in supervised.REDUCED_CONFIGS}
    total_time = 0.0

    for pos in positions:
        matrix = None
        for family in supervised.REDUCED_CONFIGS:
            hits, targets, fold_times = 0, 0, []
            for fold_index, fold in enumerate(folds):
                part_path = _supervised_reduced_partial_path(outdir, family, pos, fold_index)
                if matrix is None and not os.path.exists(part_path):
                    matrix = supervised.build_feature_matrix(h, pos)
                fit_result = _supervised_reduced_fit(h, outdir, identity, family, pos, fold_index, fold, matrix)
                hits += fit_result["hits"]
                targets += fit_result["targets"]
                fold_times.append(fit_result["elapsed_seconds"])
                families_result[family]["wall_time_seconds"] += fit_result["elapsed_seconds"]
                total_time += fit_result["elapsed_seconds"]
            families_result[family]["positions"][f"pos{pos + 1}"] = {
                "hit_rate_top25": (hits / targets) if targets else None,
                "hits": hits, "targets": targets, "fold_wall_time_seconds": fold_times,
            }
        del matrix

    result = {
        "label": _SUPERVISED_REDUCED_LABEL,
        "schedule_note": supervised.REDUCED_SCHEDULE_NOTE,
        "window": supervised.REDUCED_WINDOW,
        "grid": {"logistic": supervised.REDUCED_LOGISTIC_CONFIG, "tree": supervised.REDUCED_TREE_CONFIG},
        "families": families_result,
        "primary_pos1": {family: families_result[family]["positions"]["pos1"]["hit_rate_top25"]
                          for family in supervised.REDUCED_CONFIGS
                          if "pos1" in families_result[family]["positions"]},
        "total_wall_time_seconds": total_time,
    }
    _atomic_write_json(path, {"protocol_hash": protocol.protocol_hash(), "data_sha": h.sha256,
                              "identity": identity, "result": result})
    return result


def run_interpretable(h, outdir, *, folds=None, configs=None, max_seconds=7200,
                       reps=protocol.BOOT_REPS, run_controls=True):
    """Full resumable orchestrator for the plan's interpretable phase: validation,
    protocol, fold_manifest, candidate inventory, mde (before store/primary), the full
    causal store (positions 0..4 + any + ablations), primary, secondary, source_restart,
    and (when ``run_controls``) the 70 control streams (20 healthy + 30 signal + 20
    order) with their gate summary, ending in one assembled ``metrics.json``.

    Every step and control stream is bound to a complete run identity; a
    mismatch raises rather than silently overwriting. When ``max_seconds`` elapses, the
    run stops before the next unit of work and writes ``outdir/status.json``; a later
    call with the same protocol/data resumes from the first incomplete step or stream.
    ``run_controls=False`` stops right after ``source_restart`` (test-only escape hatch:
    no metrics.json is written in that case). Supervised families are out of scope here
    (CR-7); ``metrics.json`` is always marked ``"partial: supervised pending"``.
    """
    if max_seconds is None:
        max_seconds = 7200
    if not 0 <= max_seconds <= 7200:
        raise ValueError("max_seconds must be within 0..7200 seconds")
    start = time.monotonic()
    data_sha = h.sha256
    if folds is None:
        folds = walkforward.outer_folds(len(h.dates))
    if configs is None:
        configs = [cid for cid, _family, _params in protocol.all_configs(include_supervised=False)]
    identity = engine.store_identity(h, configs + [aid for aid, _, _ in models.ABLATIONS], folds,
                                     run_identity={"reps": reps})
    identity["code_hash"] = _code_hash()
    identity["reps"] = reps
    # Check every checkpoint and collateral artifact before any write, even if a prior
    # step would be skipped or a time budget would stop this invocation immediately.
    from pathlib import Path
    root = Path(outdir)
    status_path = root / "status.json"
    manifest_path = root / "identity.json"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            if json.load(f) != identity:
                raise ValueError("run identity mismatch for manifest")
    if status_path.exists():
        with open(status_path, encoding="utf-8") as f:
            if json.load(f).get("identity") != identity:
                raise ValueError("run identity mismatch for status")
    for path in (root / "protocol.json", root / "metrics.json"):
        if path.exists():
            with open(path, encoding="utf-8") as f:
                if json.load(f).get("identity") != identity:
                    raise ValueError(f"run identity mismatch for {path.name}")
    for step_path in (root / "steps").glob("*.json"):
        _step_done(outdir, step_path.stem, data_sha, identity)
    for control_path in (root / "controls").glob("*.json"):
        _control_done(outdir, control_path.stem, data_sha, identity)
    store_dir = root / "store"
    store_identity = engine.store_identity(h, configs + [aid for aid, _, _ in models.ABLATIONS], folds,
                                           run_identity={"reps": reps})
    for meta_path in store_dir.glob("target_*.meta.json"):
        engine._already_computed(str(store_dir), meta_path.name[7:-10], store_identity)
    for target_path in store_dir.glob("target_*.npz"):
        engine._already_computed(str(store_dir), target_path.stem[7:], store_identity)
    engine._checkpoint_state(str(store_dir), store_identity,
                             (len(configs) + len(models.ABLATIONS), h.n, 100), tuple(range(5)))
    for control_dir in (root / "controls_store").glob("*"):
        meta = control_dir / "target_pos1.meta.json"
        target = control_dir / "target_pos1.npz"
        if meta.exists() != target.exists():
            raise ValueError(f"run identity incomplete for control store {control_dir.name}")
        if meta.exists():
            with open(meta, encoding="utf-8") as f:
                cached_identity = json.load(f).get("identity", {})
            if (cached_identity.get("run_identity") != identity
                    or cached_identity.get("config_hash") != engine._hash_json(configs)
                    or cached_identity.get("folds_hash") != identity["folds_hash"]
                    or cached_identity.get("ranking_key_version") != identity["ranking_key_version"]):
                raise ValueError(f"run identity mismatch for control store {control_dir.name}")
    os.makedirs(outdir, exist_ok=True)
    if not manifest_path.exists():
        _atomic_write_json(str(manifest_path), identity)

    def _budget_exceeded():
        return max_seconds is not None and (time.monotonic() - start) > max_seconds

    def _stop(next_step, reason="time budget"):
        _write_status(outdir, "partial", reason, next_step, identity)
        return {"status": "partial", "reason": reason, "next_step": next_step}

    results = {}
    for step in _MAIN_STEPS:
        cached = _step_done(outdir, step, data_sha, identity)
        if cached is not None:
            results[step] = cached
            continue
        if _budget_exceeded():
            return _stop(step)
        if step == "store" and shutil.disk_usage(outdir).free < protocol.BUDGET["artifacts_gb"] * (1024 ** 3):
            return _stop("store", reason="insufficient disk")

        step_start_iso = datetime.now(UTC).isoformat()
        t0 = time.monotonic()
        primary_rows = walkforward.primary_mask(h)

        if step == "validation":
            result = data.validation_report(h)
        elif step == "protocol":
            result = protocol.protocol_dict()
            _atomic_write_json(os.path.join(outdir, "protocol.json"),
                                {"protocol_hash": protocol.protocol_hash(), "protocol": result,
                                 "identity": identity})
        elif step == "fold_manifest":
            result = walkforward.fold_manifest(h, folds)
        elif step == "inventory":
            result = _candidate_inventory(h, configs)
        elif step == "mde":
            result = inference.mde_top25(int(primary_rows.sum()), len(PRIMARY_HOLM_FAMILY))
        elif step == "store":
            store_dir = os.path.join(outdir, "store")
            complete = engine.compute_target_store(h, configs, store_dir, positions=(0, 1, 2, 3, 4),
                                                   include_any=True, ablations=True, folds=folds,
                                                   run_identity={"reps": reps},
                                                   should_stop=_budget_exceeded)
            if not complete:
                return _stop("store")
            result = {"store_dir": store_dir}
        elif step == "primary":
            store = engine.load_store(os.path.join(outdir, "store"), "pos1")
            result = analyze_primary(h, store, folds, reps=reps)
        elif step == "secondary":
            stores = {t: engine.load_store(os.path.join(outdir, "store"), t) for t in protocol.TARGETS}
            result = analyze_secondary(h, stores, folds)
        elif step == "export":
            from chance_rank import artifacts

            manifest = {}
            for target in protocol.TARGETS:
                sub_step = f"export_{target}"
                cached_target = _step_done(outdir, sub_step, data_sha, identity)
                if cached_target is not None:
                    manifest[target] = cached_target
                    continue
                if _budget_exceeded():
                    return _stop(step)
                store = engine.load_store(os.path.join(outdir, "store"), target)
                target_result = artifacts.export_one_target(h, outdir, target, store, folds,
                                                             primary_rows=primary_rows)
                del store
                gc.collect()
                _mark_step_done(outdir, sub_step, data_sha, target_result, identity)
                manifest[target] = target_result
            artifacts.write_schema(outdir, manifest, SYSTEMS)
            result = manifest
        elif step == "source_restart":
            store = engine.load_store(os.path.join(outdir, "store"), "pos1")
            config_ids_all = store["config_ids"].tolist()
            hits_all = target_hits(store["ranks_updated"], protocol.PRIMARY_K)
            candidate_ids, candidate_families = candidate_entries(config_ids_all)
            index_all = {cid: i for i, cid in enumerate(config_ids_all)}
            candidate_hits = np.array([hits_all[index_all[cid]] for cid in candidate_ids])
            picks, _s, _t = per_fold_choice(h, candidate_ids, candidate_families, candidate_hits,
                                             folds, primary_rows)
            result = source_restart(h, folds, picks)
        else:
            raise ValueError(f"Unknown step: {step}")

        _mark_step_done(outdir, step, data_sha, result, identity)
        results[step] = result
        _log_jsonl(outdir, {"step": step, "start": step_start_iso, "end": datetime.now(UTC).isoformat(),
                             "seconds": time.monotonic() - t0, "status": "completed"})

    if not run_controls:
        return {"status": "completed", "steps": results}

    control_results = {}
    for entry in _control_stream_names():
        name = _control_stream_id(entry)
        cached = _control_done(outdir, name, data_sha, identity)
        if cached is not None:
            control_results[name] = cached
            continue
        if _budget_exceeded():
            return _stop(f"controls/{name}")

        stream_start_iso = datetime.now(UTC).isoformat()
        t0 = time.monotonic()
        h_ctrl = _build_control_history(h, entry)
        workdir = os.path.join(outdir, "controls_store", name)
        result = run_control(h_ctrl, workdir, folds, configs, reps=reps,
                             run_identity=identity)
        _mark_control_done(outdir, name, data_sha, result, identity)
        control_results[name] = result
        _log_jsonl(outdir, {"step": f"controls/{name}", "start": stream_start_iso,
                             "end": datetime.now(UTC).isoformat(), "seconds": time.monotonic() - t0,
                             "status": "completed"})

    cached = _step_done(outdir, "controls_summary", data_sha, identity)
    if cached is not None:
        results["controls_summary"] = cached
    else:
        if _budget_exceeded():
            return _stop("controls_summary")
        result = _summarize_controls(control_results, results.get("primary"))
        _mark_step_done(outdir, "controls_summary", data_sha, result, identity)
        results["controls_summary"] = result

    cached = _step_done(outdir, "metrics", data_sha, identity)
    if cached is not None:
        results["metrics"] = cached
    else:
        if _budget_exceeded():
            return _stop("metrics")
        result = {
            "protocol_hash": protocol.protocol_hash(), "data_sha": data_sha, "identity": identity,
            "validation": results["validation"], "fold_manifest": results["fold_manifest"],
            "inventory": results["inventory"], "mde": results["mde"], "primary": results["primary"],
            "secondary": results["secondary"], "source_restart": results["source_restart"],
            "controls": control_results, "controls_summary": results["controls_summary"],
            "status": "partial: supervised pending",
        }
        _atomic_write_json(os.path.join(outdir, "metrics.json"), result)
        _mark_step_done(outdir, "metrics", data_sha, result, identity)
        results["metrics"] = result

    _write_status(outdir, "partial", "supervised pending (CR-7)", "supervised", identity)
    return {"status": "completed", "steps": results, "controls": control_results}


def main_run(input_path, outdir, max_seconds=7200):
    """Entry point: load the real history with the default protocol SHA check, then run
    ``run_interpretable``. Never called on the real JSON in this unit's tests."""
    h = data.load_history(input_path)
    return run_interpretable(h, outdir, max_seconds=max_seconds)
