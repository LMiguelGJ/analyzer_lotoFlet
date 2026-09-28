"""Nested walk-forward folds, primary/secondary target masks and per-family selection.

Outer folds are contiguous 28-day test blocks over observed days, expanding-window
trained; each outer origin ``d`` has three consecutive inner validation blocks
``[d-84,d-56)``, ``[d-56,d-28)``, ``[d-28,d)`` used to pick one winner per family
before that block is ever scored (decisions D1/D2 in ``odd/tasks/chance-rank.md``).
"""

from dataclasses import dataclass

import numpy as np

from chance_rank import protocol


@dataclass(frozen=True, slots=True)
class Fold:
    index: int
    test_days: tuple[int, int]
    inner: tuple[tuple[int, int], tuple[int, int], tuple[int, int]]


def outer_folds(n_days):
    """Expanding-window outer folds: 28-day test blocks starting at day 180, 208, ..."""
    folds = []
    j = 0
    while True:
        start = protocol.INITIAL_TRAIN_DAYS + protocol.OUTER_BLOCK_DAYS * j
        if start >= n_days:
            break
        end = min(start + protocol.OUTER_BLOCK_DAYS, n_days)
        inner = ((start - 84, start - 56), (start - 56, start - 28), (start - 28, start))
        folds.append(Fold(index=j, test_days=(start, end), inner=inner))
        j += 1
    return folds


def rows_in_days(h, a, b):
    """Boolean mask of rows whose observed day index is in the half-open range [a, b)."""
    return (h.day >= a) & (h.day < b)


def primary_mask(h):
    """Eligible targets past warmup: main analysis population."""
    idx = np.arange(h.n)
    return h.eligible & (idx >= protocol.WARMUP)


def secondary_mask(h):
    """Non-eligible targets past warmup: the 'next available record' population."""
    idx = np.arange(h.n)
    return (~h.eligible) & (idx >= protocol.WARMUP) & (idx > 0)


def select(config_ids, hits, mask):
    """Best config by mean hit rate over ``mask`` rows only; ties -> smallest id.

    Returns ``(best_id, scores)`` with ``scores`` aligned to ``config_ids``, including
    losers, for audit. Never reads ``hits`` columns outside ``mask``.
    """
    hits = np.asarray(hits)
    denom = int(mask.sum())
    if denom == 0:
        raise ValueError("select: mask has zero opportunities")
    scores = hits[:, mask].sum(axis=1) / denom
    order = sorted(range(len(config_ids)), key=lambda i: (-scores[i], config_ids[i]))
    return config_ids[order[0]], scores


def _inner_rows_mask(h, fold, primary_rows):
    a1, b1 = fold.inner[0]
    a2, b2 = fold.inner[1]
    a3, b3 = fold.inner[2]
    union = rows_in_days(h, a1, b1) | rows_in_days(h, a2, b2) | rows_in_days(h, a3, b3)
    return union & primary_rows


def _pick_best(candidate_ids, config_index, scores):
    order = sorted(candidate_ids, key=lambda cid: (-scores[config_index[cid]], cid))
    return order[0]


def selections(h, config_ids, families_of, hits, folds, primary_rows):
    """Per-fold winner per family plus the two automatic selectors.

    Returns ``(picks, scores_table)``: ``picks[fold.index]`` maps each family present to
    its chosen config id, plus ``"select_interpretable"`` (best among interpretable
    families) and ``"select_all"`` (best among all families, or ``None`` when a required
    supervised family is absent). ``scores_table[fold.index]`` holds every candidate's
    inner score, including losers, for audit.
    """
    config_ids = list(config_ids)
    families_of = list(families_of)
    hits = np.asarray(hits)
    config_index = {cid: i for i, cid in enumerate(config_ids)}
    families_present = sorted(set(families_of))

    picks, scores_table = {}, {}
    for fold in folds:
        mask = _inner_rows_mask(h, fold, primary_rows)
        denom = int(mask.sum())
        if denom == 0:
            raise ValueError(f"selections: fold {fold.index} has zero inner opportunities")
        scores = hits[:, mask].sum(axis=1) / denom

        by_family = {}
        for family in families_present:
            candidate_ids = [cid for cid, f in zip(config_ids, families_of, strict=True) if f == family]
            by_family[family] = _pick_best(candidate_ids, config_index, scores)

        interpretable_ids = [by_family[f] for f in protocol.INTERPRETABLE_FAMILIES if f in by_family]
        select_interpretable = (_pick_best(interpretable_ids, config_index, scores)
                                 if interpretable_ids else None)

        if set(protocol.SUPERVISED_FAMILIES) <= set(families_present):
            select_all = _pick_best(list(by_family.values()), config_index, scores)
        else:
            select_all = None

        by_family["select_interpretable"] = select_interpretable
        by_family["select_all"] = select_all
        picks[fold.index] = by_family
        scores_table[fold.index] = {cid: float(scores[i]) for i, cid in enumerate(config_ids)}

    return picks, scores_table


def _day_range_dates(h, day_range):
    a, b = day_range
    start_date = h.dates[a] if 0 <= a < len(h.dates) else None
    end_date = h.dates[b - 1] if 0 <= b - 1 < len(h.dates) else None
    return {"start_day": a, "end_day": b, "start_date": start_date, "end_date": end_date}


def fold_manifest(h, folds):
    """JSON-serializable fold dates and row/target counts, declared before any metric."""
    manifest = []
    primary_rows = primary_mask(h)
    for fold in folds:
        manifest.append({
            "index": fold.index,
            "test_days": _day_range_dates(h, fold.test_days),
            "inner": [_day_range_dates(h, r) for r in fold.inner],
            "test_rows": int(rows_in_days(h, *fold.test_days).sum()),
            "inner_rows": [int(rows_in_days(h, *r).sum()) for r in fold.inner],
            "primary_targets": int((primary_rows & rows_in_days(h, *fold.test_days)).sum()),
        })
    return manifest
