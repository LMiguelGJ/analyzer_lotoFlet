"""Block bootstrap inference, Holm correction, fold agreement, D10 classification.

``contrast`` compares one system against one baseline on paired targets; callers run
it twice (uniform, recent500) per system per K/horizon and feed both into ``classify``.
"""

import numpy as np
from scipy.stats import norm

from chance_rank import protocol


def day_totals(diff, mask, day, strata):
    """Sum/count within day-source units; retain day keys for single-stratum histories."""
    diff = np.asarray(diff, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    day = np.asarray(day)

    mixed = len({int(d): None for d in day}) < len({(int(d), strata[i])
                                                        for i, d in enumerate(day)})
    day_sum, day_n, strata_of_day = {}, {}, {}
    for i in range(len(day)):
        d = int(day[i])
        s = strata[i]
        unit = (d, s) if mixed else d
        strata_of_day[unit] = s
        if mask[i]:
            day_sum[unit] = day_sum.get(unit, 0.0) + float(diff[i])
            day_n[unit] = day_n.get(unit, 0) + 1
    return day_sum, day_n, strata_of_day


def block_bootstrap(day_sum, day_n, strata_of_day, block_days, reps, label):
    """Circular block bootstrap of the ratio sum(diff)/n, stratified and pooled.

    One fresh ``protocol.rng(label)`` draws all strata's starts, in sorted-stratum
    order, so every contrast sharing a label resamples the same days (paired, D9).
    """
    generator = protocol.rng(label)
    days_by_stratum = {}
    for d, s in strata_of_day.items():
        days_by_stratum.setdefault(s, []).append(d)

    total_diff = np.zeros(reps)
    total_count = np.zeros(reps)
    offsets = np.arange(block_days)
    for stratum in sorted(days_by_stratum):
        days = sorted(days_by_stratum[stratum])
        m = len(days)
        day_sum_arr = np.array([day_sum[d] for d in days])
        day_n_arr = np.array([day_n[d] for d in days])
        n_blocks = -(-m // block_days)
        starts = generator.integers(0, m, size=(reps, n_blocks))
        idx = (starts[:, :, None] + offsets[None, None, :]) % m
        idx = idx.reshape(reps, -1)[:, :m]
        total_diff += day_sum_arr[idx].sum(axis=1)
        total_count += day_n_arr[idx].sum(axis=1)

    return total_diff / total_count


def contrast(diff, mask, day, strata, block_days=protocol.BOOT_BLOCK_DAYS,
             reps=protocol.BOOT_REPS):
    """One-sided bootstrap contrast: mean(diff) on masked targets vs the block-bootstrap
    null centered at zero drift, paired via the fixed inference seed (D9)."""
    diff = np.asarray(diff, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    n = int(mask.sum())
    if n == 0:
        return {"n": 0, "delta_obs": None, "p": None, "ci95": None, "ci99": None, "degenerate": False}

    delta_obs = float(diff[mask].mean())
    day_sum, day_n, strata_of_day = day_totals(diff, mask, day, strata)
    suffix = {1: "/L1", 14: "/L14"}.get(block_days, "" if block_days == protocol.BOOT_BLOCK_DAYS
                                         else f"/L{block_days}")
    label = f"{protocol.PROTOCOL_ID}/inference{suffix}"
    boot = block_bootstrap(day_sum, day_n, strata_of_day, block_days, reps, label)

    if np.std(boot) == 0:
        # a degenerate (zero-variance) bootstrap is a point mass at delta_obs: p=1.0
        # (no evidence against the null) and both CIs collapse to that point, rather
        # than being reported as an unavailable (N/A) contrast.
        return {"n": n, "delta_obs": delta_obs, "p": 1.0, "ci95": (delta_obs, delta_obs),
                "ci99": (delta_obs, delta_obs), "degenerate": True}

    p = (1 + int(np.count_nonzero(boot - delta_obs >= delta_obs))) / (len(boot) + 1)
    ci95 = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))
    ci99 = (float(np.percentile(boot, 0.5)), float(np.percentile(boot, 99.5)))
    return {"n": n, "delta_obs": delta_obs, "p": p, "ci95": ci95, "ci99": ci99, "degenerate": False}


def holm(pvals):
    """Holm step-down adjustment; ``None`` entries count as p=1 in ordering/family size
    but are reported back as ``None``."""
    m = len(pvals)
    effective = [1.0 if p is None else p for p in pvals]
    order = sorted(range(m), key=lambda i: effective[i])
    adjusted: list[float | None] = [None] * m
    running_max = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * effective[i])
        running_max = max(running_max, adj)
        adjusted[i] = running_max
    for i, p in enumerate(pvals):
        if p is None:
            adjusted[i] = None
    return adjusted


def fold_positive_share(diff, mask, fold_of_row, min_targets=protocol.MIN_FOLD_TARGETS):
    diff = np.asarray(diff, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    fold_of_row = np.asarray(fold_of_row)

    per_fold_delta, per_fold_n = {}, {}
    for f in np.unique(fold_of_row):
        fm = mask & (fold_of_row == f)
        n = int(fm.sum())
        per_fold_n[f.item()] = n
        if n:
            per_fold_delta[f.item()] = float(diff[fm].mean())

    eligible_folds = sorted(f for f, n in per_fold_n.items() if n >= min_targets)
    positive = sum(1 for f in eligible_folds if per_fold_delta[f] > 0)
    share = positive / len(eligible_folds) if eligible_folds else None
    return {"per_fold_delta": per_fold_delta, "eligible_folds": eligible_folds, "share": share}


def _full_criterion(baseline):
    return (baseline["delta"] >= protocol.PRACTICAL_MIN_LIFT
            and baseline["p_adj"] < protocol.ALPHA
            and baseline["fold_share"] >= protocol.PRACTICAL_FOLD_SHARE)


def _exploratory(baseline):
    return baseline["delta"] > 0 and baseline["p_raw"] < 0.05


def classify(system):
    """D10 label for one system's primary contrast (Top-25/H1/pos1), plus the
    ``inestable`` flag from the 1/14-day block sensitivity of the uniform contrast.

    ``degenerate`` (either baseline had a zero-variance bootstrap) is passed through
    for reporting; it does not change the classification logic, since a degenerate
    contrast's p=1.0/point-mass CI already fails the full and exploratory criteria.
    """
    uniform = system["uniform"]
    recent500 = system["recent500"]
    sensitivity = system.get("sensitivity") or {}
    degenerate = bool(uniform.get("degenerate") or recent500.get("degenerate"))

    if uniform.get("delta") is None or recent500.get("delta") is None:
        return {"label": "no_disponible", "inestable": False, "degenerate": False}

    if _full_criterion(uniform) and _full_criterion(recent500):
        label = "consistente_historico"
    elif _exploratory(uniform) and _exploratory(recent500):
        label = "senal_exploratoria"
    elif uniform["ci99"][1] >= protocol.PRACTICAL_MIN_LIFT:
        label = "inconcluso"
    else:
        label = "sin_mejora_detectada"

    primary_sign = uniform["delta"] > 0
    primary_holm_reject = uniform["p_adj"] < protocol.ALPHA
    inestable = any((entry["delta"] > 0) != primary_sign
                     or entry["holm_reject"] != primary_holm_reject
                     for entry in sensitivity.values())

    return {"label": label, "inestable": inestable, "degenerate": degenerate}


def mde_top25(n, m_tests, alpha=protocol.ALPHA, power=0.8):
    """Optimistic binomial-approximation minimum detectable effect for one proportion
    test, Holm-corrected for ``m_tests`` simultaneous families."""
    mde = (norm.ppf(1 - alpha / m_tests) + norm.ppf(power)) * np.sqrt(0.25 * 0.75 / n)
    return {"mde": float(mde), "label": "optimistic binomial approximation"}
