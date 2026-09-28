"""Causal feature-vector builder for the supervised stage (protocol section 3), plus the
CR-7 reduced exploratory fit/predict/aggregation subset.

Row t's feature vector reads only primitives from rows < t (row t is never
read), the same causality guarantee as ``chance_rank/features.py``. The full
supervised grid (``protocol.SUPERVISED_GRID``, 7-day refit) is out of scope here;
``fit_predict_fold``/``reduced_run`` implement only the pre-declared reduced subset:
one logistic config, one tree config, window=30000, refit once per outer fold.
"""

import time

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from chance_rank import features as feat
from chance_rank import protocol, walkforward
from chance_rank.models import FeatureCache
from chance_rank.ranking import winner_rank

CATEGORY_KINDS = ("parity", "lowhigh", "decade", "ending")
_CATEGORY_G = {"parity": 2, "lowhigh": 2, "decade": 10, "ending": 10}
FREQ_WINDOWS = (100, 500, 2000)
EWMA_HALF_LIFE = 500
STREAK_CAP = 5

# 3 * 100 (relative freq) + 100 (EWMA) + 2 * 100 (position age + censor mask)
# + 2 * 100 (global age + censor mask) + 5 * 100 (previous positions one-hot)
# + 100 (previous-draw duplicate indicator) + sum(g + STREAK_CAP for g in _CATEGORY_G)
# + 4 (cyclic hour/weekday)
N_FEATURES = (len(FREQ_WINDOWS) * 100 + 100 + 4 * 100 + 5 * 100 + 100
              + sum(g + STREAK_CAP for g in _CATEGORY_G.values()) + 4)


def _category_of(values, kind):
    if kind == "parity":
        return values % 2
    if kind == "lowhigh":
        return (values >= 50).astype(np.int64)
    if kind == "decade":
        return values // 10
    if kind == "ending":
        return values % 10
    raise ValueError(f"Unknown category kind: {kind}")


def _relative_freq(onehot, window):
    counts = feat.windowed_exclusive_sum(onehot, window)
    denom = feat.window_row_count(onehot.shape[0], window)
    return counts / np.maximum(denom, 1.0)[:, None]


def _shifted(x, fill=0):
    """Row t gets row t-1's value; row 0 gets ``fill`` (no predecessor)."""
    shifted = np.empty_like(x)
    shifted[0] = fill
    shifted[1:] = x[:-1]
    return shifted


def _cyclic(values, period):
    angle = 2.0 * np.pi * values.astype(np.float64) / period
    return np.stack([np.sin(angle), np.cos(angle)], axis=1)


def build_feature_matrix(h, pos):
    """(N, N_FEATURES) float64 causal feature matrix for target position ``pos``."""
    cache = FeatureCache(h, pos)
    onehot = cache.onehot

    freq_blocks = [_relative_freq(onehot, w) for w in FREQ_WINDOWS]
    ewma = feat.decay_scores(onehot, EWMA_HALF_LIFE)

    pos_ages = feat.ages_from_onehot(onehot).astype(np.float64)
    pos_never_seen = (pos_ages > cache.idx[:, None]).astype(np.float64)

    global_onehot = sum(feat.one_hot(h.nums[:, j]) for j in range(5))
    global_ages = feat.ages_from_onehot(global_onehot).astype(np.float64)
    global_never_seen = (global_ages > cache.idx[:, None]).astype(np.float64)

    prev_positions = _shifted(h.nums)
    prev_one_hot = np.concatenate(
        [feat.one_hot(prev_positions[:, j]) for j in range(5)], axis=1)
    prev_dup = (feat.row_multiplicities(prev_positions) >= 2).astype(np.float64)

    category_blocks = []
    for kind in CATEGORY_KINDS:
        g = _CATEGORY_G[kind]
        cat_all = _category_of(cache.Y, kind)
        run_len = feat.run_lengths(cat_all, h.eligible)
        prev_cat = _shifted(cat_all)
        prev_run = _shifted(run_len, fill=1)
        bucket = np.minimum(prev_run, STREAK_CAP) - 1
        category_blocks.append(feat.one_hot(prev_cat, width=g))
        category_blocks.append(feat.one_hot(bucket, width=STREAK_CAP))

    cyclic = np.concatenate([_cyclic(h.hour, 24), _cyclic(h.weekday, 7)], axis=1)

    return np.concatenate(
        freq_blocks + [ewma, pos_ages, pos_never_seen, global_ages, global_never_seen,
                       prev_one_hot, prev_dup] + category_blocks + [cyclic],
        axis=1,
    ).astype(np.float64)


# CR-7 pre-declared reduced grid, fixed before any result was observed: one logistic
# config, one tree config, per position, window=30000, refit once per outer fold.
REDUCED_LOGISTIC_CONFIG = {"C": 0.1, "solver": "lbfgs", "max_iter": 500, "tol": 1e-4}
REDUCED_TREE_CONFIG = {"max_depth": 5, "min_samples_leaf": 200}
REDUCED_WINDOW = 30000
REDUCED_FAMILIES = ("logistic", "tree")
REDUCED_SCHEDULE_NOTE = "reduced schedule, not the full plan's 7-day refit"
REDUCED_LABEL = "muestra reducida exploratoria"


def _build_model(family, config):
    if family == "logistic":
        return LogisticRegression(C=config["C"], solver=config["solver"],
                                   max_iter=config["max_iter"], tol=config["tol"])
    if family == "tree":
        return DecisionTreeClassifier(max_depth=config["max_depth"],
                                       min_samples_leaf=config["min_samples_leaf"])
    raise ValueError(f"Unknown supervised family: {family}")


def fit_predict_fold(h, pos, fold, window, config, family, matrix=None):
    """Causal probabilities over the 100 classes for ``fold``'s primary-mask test rows.

    Trained once on up to ``window`` prior eligible targets strictly before
    ``fold.test_days[0]``; fold test rows are never read during fit. Missing classes
    in the training window keep their vector position via ``model.classes_`` --
    :class:`~sklearn.tree.DecisionTreeClassifier` and
    :class:`~sklearn.linear_model.LogisticRegression` both drop classes absent from
    the training labels from ``classes_``, so the raw ``predict_proba`` column order
    would otherwise silently depend on which digits happened to appear.

    ``matrix``, when given, must equal ``build_feature_matrix(h, pos)``; callers
    fitting many folds/families for the same position pass it in to build the causal
    feature matrix once instead of once per fit.

    Returns ``(row_idx, S)``: ``row_idx`` are the test rows in ascending order, ``S``
    is ``(len(row_idx), 100)`` float64.
    """
    if matrix is None:
        matrix = build_feature_matrix(h, pos)
    Y = h.nums[:, pos]
    primary_rows = walkforward.primary_mask(h)

    train_mask = primary_rows & (h.day < fold.test_days[0])
    train_idx = np.nonzero(train_mask)[0]
    if train_idx.size > window:
        train_idx = train_idx[-window:]

    test_mask = primary_rows & walkforward.rows_in_days(h, *fold.test_days)
    test_idx = np.nonzero(test_mask)[0]

    model = _build_model(family, config)
    model.fit(matrix[train_idx], Y[train_idx])

    proba = model.predict_proba(matrix[test_idx]) if test_idx.size else np.empty((0, model.classes_.size))
    S = np.zeros((test_idx.size, 100), dtype=np.float64)
    S[:, model.classes_] = proba
    return test_idx, S


REDUCED_CONFIGS = {"logistic": REDUCED_LOGISTIC_CONFIG, "tree": REDUCED_TREE_CONFIG}


def reduced_fit_one(h, pos, fold, family, matrix=None):
    """Single (family, position, fold) fit of the CR-7 reduced grid: hits/targets/elapsed
    for that one fit only. Building block for both ``reduced_run`` (in-memory aggregate
    over every position/family/fold) and per-fit-checkpointing callers that need to
    persist and resume one (family, pos, fold) at a time.
    """
    if family not in REDUCED_CONFIGS:
        raise ValueError(f"Unknown supervised family: {family}")
    config = REDUCED_CONFIGS[family]
    start = time.perf_counter()
    row_idx, S = fit_predict_fold(h, pos, fold, REDUCED_WINDOW, config, family, matrix=matrix)
    elapsed = time.perf_counter() - start

    hits, targets = 0, 0
    if row_idx.size:
        Y = h.nums[row_idx, pos]
        ranks = winner_rank(S, Y)
        hits = int((ranks < protocol.PRIMARY_K).sum())
        targets = int(row_idx.size)

    return {"hits": hits, "targets": targets, "elapsed_seconds": elapsed}


def reduced_run(h, folds, positions=(0, 1, 2, 3, 4)):
    """Aggregate the pre-declared reduced grid: 2 families x len(positions) x len(folds)
    fits, primary Top-25 hit rate (pos1) plus descriptive rates for the other positions.

    Never labelled 'logistic'/'tree' full-grid result on its own -- callers must keep
    ``REDUCED_LABEL``/``REDUCED_SCHEDULE_NOTE`` attached wherever this is reported.
    """
    families_result = {family: {"positions": {}, "wall_time_seconds": 0.0} for family in REDUCED_CONFIGS}
    total_time = 0.0

    # One causal feature matrix per position, reused across both families and every
    # fold (matches the codebase's "one FeatureCache per position at a time" bound).
    for pos in positions:
        matrix = build_feature_matrix(h, pos)
        for family in REDUCED_CONFIGS:
            hits, targets, fold_times = 0, 0, []
            for fold in folds:
                fit = reduced_fit_one(h, pos, fold, family, matrix=matrix)
                fold_times.append(fit["elapsed_seconds"])
                families_result[family]["wall_time_seconds"] += fit["elapsed_seconds"]
                total_time += fit["elapsed_seconds"]
                hits += fit["hits"]
                targets += fit["targets"]

            families_result[family]["positions"][f"pos{pos + 1}"] = {
                "hit_rate_top25": (hits / targets) if targets else None,
                "hits": hits, "targets": targets, "fold_wall_time_seconds": fold_times,
            }
        del matrix

    return {
        "label": REDUCED_LABEL,
        "schedule_note": REDUCED_SCHEDULE_NOTE,
        "window": REDUCED_WINDOW,
        "grid": {"logistic": REDUCED_LOGISTIC_CONFIG, "tree": REDUCED_TREE_CONFIG},
        "families": families_result,
        "primary_pos1": {family: families_result[family]["positions"]["pos1"]["hit_rate_top25"]
                          for family in REDUCED_CONFIGS if "pos1" in families_result[family]["positions"]},
        "total_wall_time_seconds": total_time,
    }
