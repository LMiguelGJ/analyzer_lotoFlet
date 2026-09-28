"""Causal, vectorized primitives shared by every scoring family in ``models.py``.

Every primitive at row t reads only rows < t (row t itself is never read), so a
change to ``h.nums`` at row t or later cannot change any primitive value at rows < t.
"""

import numpy as np
from scipy.signal import lfilter

N_VALUES = 100


def one_hot(values, width=N_VALUES):
    onehot = np.zeros((len(values), width), dtype=np.float64)
    onehot[np.arange(len(values)), values] = 1.0
    return onehot


def exclusive_cumsum(x, axis=0):
    """Sum over rows < t along ``axis``; row 0 is zero."""
    cum = np.cumsum(x, axis=axis)
    return cum - x


def windowed_exclusive_sum(x, window):
    """Sum over rows in ``[max(0, t - window), t)``; ``window=None`` means ``[0, t)``."""
    excl = exclusive_cumsum(x, axis=0)
    if window is None:
        return excl
    n = x.shape[0]
    lag_idx = np.clip(np.arange(n) - window, 0, None)
    return excl - excl[lag_idx]


def window_row_count(n, window):
    """Number of rows counted by ``windowed_exclusive_sum`` at each t: min(t, window) or t."""
    idx = np.arange(n)
    if window is None:
        return idx.astype(np.float64)
    return np.minimum(idx, window).astype(np.float64)


def row_multiplicities(nums, width=N_VALUES):
    """(N, width) int: count of each value within each row's entries (e.g. 0..5)."""
    n = nums.shape[0]
    counts = np.zeros((n, width), dtype=np.int64)
    for j in range(nums.shape[1]):
        np.add.at(counts, (np.arange(n), nums[:, j]), 1)
    return counts


def ages_from_onehot(onehot):
    """(N, width) age since last occurrence, exclusive of row t; never seen -> t + 1."""
    n, width = onehot.shape
    idx = np.arange(n)
    occ_idx = np.where(onehot > 0, idx[:, None], -1)
    last_inclusive = np.maximum.accumulate(occ_idx, axis=0)
    last_exclusive = np.vstack([np.full((1, width), -1, dtype=np.int64), last_inclusive[:-1]])
    return idx[:, None] - last_exclusive


def decay_scores(onehot, half_life):
    """E[t] = sum_{s<t} a**(t-1-s) * onehot[s], a = 0.5**(1/half_life), E[0] = 0."""
    a = 0.5 ** (1.0 / half_life)
    return lfilter([0.0, 1.0], [1.0, -a], onehot, axis=0)


def run_lengths(categories, eligible):
    """Length of the consecutive run of equal ``categories`` ending at each row.

    A run resets when ``eligible`` is False (segment start) or the category changes
    from the immediate predecessor.
    """
    n = len(categories)
    break_point = np.ones(n, dtype=bool)
    break_point[1:] = (~eligible[1:]) | (categories[1:] != categories[:-1])
    idx = np.arange(n)
    last_break = np.maximum.accumulate(np.where(break_point, idx, -1))
    return idx - last_break + 1


def conditional_counts(context, outcome, valid, n_ctx, n_out):
    """(N, n_out) counts of past valid events sharing row t's context.

    ``counts[t, o]`` is the number of ``s < t`` with ``valid[s]`` and
    ``context[s] == context[t]`` and ``outcome[s] == o``. Rows where ``valid[t]``
    is False still get a (unused by convention) lookup for whatever ``context[t]``
    holds; callers fall back to a marginal for those rows.
    """
    n = len(context)
    onehot = np.zeros((n, n_out), dtype=np.float64)
    valid_idx = np.flatnonzero(valid)
    onehot[valid_idx, outcome[valid_idx]] = 1.0

    order = np.argsort(context, kind="stable")
    ctx_sorted = context[order]
    onehot_sorted = onehot[order]
    cum_exclusive = exclusive_cumsum(onehot_sorted, axis=0)

    uniq_vals, first_positions = np.unique(ctx_sorted, return_index=True)
    baseline = np.zeros((n_ctx, n_out), dtype=np.float64)
    baseline[uniq_vals] = cum_exclusive[first_positions]
    result_sorted = cum_exclusive - baseline[ctx_sorted]

    counts = np.empty((n, n_out), dtype=np.float64)
    counts[order] = result_sorted
    return counts
