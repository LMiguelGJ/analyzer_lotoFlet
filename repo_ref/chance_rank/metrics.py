"""Descriptive metrics: Top-K summaries, waits/Kaplan-Meier, horizons, probabilistic
calibration, breakdowns and cross-model agreement.

Nothing here decides significance; ``inference.py`` does. These are plain descriptive
statistics over already-computed rankings/predictions.
"""

import numpy as np

from chance_rank import protocol, ranking


def topk_summary(ranks, mask, k, nums=None):
    """Positional (``ranks`` 1D) or any-target (``ranks`` (N, 5), needs ``nums``)."""
    ranks = np.asarray(ranks)
    mask = np.asarray(mask, dtype=bool)
    n = int(mask.sum())

    if ranks.ndim == 2:
        if nums is None:
            raise ValueError("any-target topk_summary requires nums")
        result = {"n": n, "reference_independent": 1 - (1 - k / 100) ** 5}
        if n == 0:
            result.update(at_least_one_rate=None, mean_positions_hit=None,
                           mean_distinct_values_hit=None)
            return result
        hits_mask = ranks[mask] < k
        nums_m = np.asarray(nums)[mask]
        distinct = np.array([len(set(nums_m[i, hits_mask[i]].tolist())) for i in range(n)])
        result.update(
            at_least_one_rate=float(hits_mask.any(axis=1).mean()),
            mean_positions_hit=float(hits_mask.sum(axis=1).mean()),
            mean_distinct_values_hit=float(distinct.mean()),
        )
        return result

    if n == 0:
        return {"n": 0, "hits": None, "rate": None, "lift_pp": None, "relative": None,
                "mean_rank": None, "median_rank": None, "mrr": None}
    r = ranks[mask].astype(np.float64)
    hits = int((r < k).sum())
    rate = hits / n
    return {
        "n": n,
        "hits": hits,
        "rate": rate,
        "lift_pp": rate - k / 100,
        "relative": rate / (k / 100) - 1,
        "mean_rank": float(r.mean()),
        "median_rank": float(np.median(r)),
        "mrr": float(np.mean(1 / (r + 1))),
    }


def waits(hit, mask, segment):
    """Waiting-time spells over masked targets, restarting at segment starts.

    Spells are built over masked rows only, in time order. The current spell
    breaks -- closing it as censored (if it had accumulated at least one row)
    and starting a fresh spell at the current row -- when the current masked
    row's segment differs from the previous masked row's segment, or when an
    unmasked row sits between them (a mask gap). A hit closes its spell as an
    event, including the hit row itself. Any spell still open after the last
    masked row overall is closed as censored.
    """
    hit = np.asarray(hit, dtype=bool)
    mask = np.asarray(mask, dtype=bool)
    segment = np.asarray(segment)

    durations, events = [], []
    elapsed = 0
    prev_i = None
    prev_seg = None
    for i in np.flatnonzero(mask):
        if prev_i is not None and (segment[i] != prev_seg or i != prev_i + 1):
            if elapsed >= 1:
                durations.append(elapsed)
                events.append(False)
            elapsed = 0
        elapsed += 1
        if hit[i]:
            durations.append(elapsed)
            events.append(True)
            elapsed = 0
        prev_i = i
        prev_seg = segment[i]

    if elapsed >= 1:
        durations.append(elapsed)
        events.append(False)

    return np.array(durations, dtype=np.int64), np.array(events, dtype=bool)


def kaplan_meier(durations, events, max_n=60):
    durations = np.asarray(durations)
    events = np.asarray(events, dtype=bool)

    survival = []
    s = 1.0
    for t in range(1, max_n + 1):
        at_risk = int((durations >= t).sum())
        if at_risk > 0:
            d = int(((durations == t) & events).sum())
            if d > 0:
                s *= 1 - d / at_risk
        survival.append(s)

    median = next((n for n, sv in enumerate(survival, start=1) if sv <= 0.5), None)
    n_censored = int((~events).sum())
    if len(durations):
        streaks = np.where(events, durations - 1, durations)
        longest_miss_streak = int(streaks.max())
    else:
        longest_miss_streak = 0

    return {"survival": survival, "median": median, "n_censored": n_censored,
            "longest_miss_streak": longest_miss_streak}


def horizon_summary(block_ranks, k, H):
    block_ranks = np.asarray(block_ranks)
    n_blocks = block_ranks.shape[0]
    if n_blocks == 0:
        return {"n_blocks": 0, "mean_hits": None, "p_at_least_one": None}

    window = block_ranks[:, :H]
    hit_per_draw = (window < k).any(axis=2) if window.ndim == 3 else window < k
    return {
        "n_blocks": int(n_blocks),
        "mean_hits": float(hit_per_draw.sum(axis=1).mean()),
        "p_at_least_one": float(hit_per_draw.any(axis=1).mean()),
    }


def prob_summary(p_true, brier, top25_mass, hits25, mask):
    mask = np.asarray(mask, dtype=bool)
    p_true = np.asarray(p_true)[mask]
    brier = np.asarray(brier)[mask]
    top25_mass = np.asarray(top25_mass)[mask]
    hits25 = np.asarray(hits25, dtype=bool)[mask]

    bins = np.clip(np.floor(top25_mass * protocol.CALIBRATION_BINS), 1,
                    protocol.CALIBRATION_BINS).astype(int)
    calibration = []
    for b in range(1, protocol.CALIBRATION_BINS + 1):
        in_bin = bins == b
        count = int(in_bin.sum())
        calibration.append({
            "bin": b,
            "count": count,
            "mean_mass": float(top25_mass[in_bin].mean()) if count else None,
            "hit_rate": float(hits25[in_bin].mean()) if count else None,
        })

    return {
        "mean_log_loss": float(np.mean(-np.log(np.maximum(p_true, 1e-12)))),
        "uniform_log_loss": float(np.log(100)),
        "mean_brier": float(np.mean(brier)),
        "uniform_brier": 0.99,
        "calibration": calibration,
    }


def breakdown(values, groups, mask):
    """Per-group n/rate of a boolean indicator, restricted to masked rows."""
    values = np.asarray(values, dtype=bool)
    groups = np.asarray(groups)
    mask = np.asarray(mask, dtype=bool)
    result = {}
    for g in np.unique(groups):
        gm = mask & (groups == g)
        n = int(gm.sum())
        result[g.item()] = {"n": n, "rate": float(values[gm].mean()) if n else None}
    return result


def hit_correlation(a, b, mask):
    """Phi coefficient (Pearson correlation of two boolean indicators); None if degenerate."""
    mask = np.asarray(mask, dtype=bool)
    a = np.asarray(a, dtype=np.float64)[mask]
    b = np.asarray(b, dtype=np.float64)[mask]
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def jaccard_topk(S_a, S_b, k, mask):
    """Row-wise Jaccard overlap of top-``k`` sets, keyed by row index for masked rows."""
    mask = np.asarray(mask, dtype=bool)
    mask_a = ranking.topk_mask(np.asarray(S_a), k)
    mask_b = ranking.topk_mask(np.asarray(S_b), k)
    inter = (mask_a & mask_b).sum(axis=1)
    union = (mask_a | mask_b).sum(axis=1)
    return {i: float(inter[i] / union[i]) for i in range(len(mask)) if mask[i]}
