"""Causal scoring for the ``chance-rank-v1`` interpretable model grid.

Every ``score_*`` function returns an ``(N, 100)`` float64 array where row t is the
score of each candidate value as the prediction of ``h.nums[t, pos]``, computed only
from rows < t. Higher score is better; ties are broken by ``ranking.TIE``.
"""

from fractions import Fraction
from math import lcm

import numpy as np
from scipy.stats import rankdata

from chance_rank import features as feat
from chance_rank import protocol
from chance_rank.ranking import percentile, topk_mask

N_VALUES = 100


class FeatureCache:
    """Shared per-(history, pos) primitives so scoring many configs computes them once."""

    def __init__(self, h, pos):
        self.h = h
        self.pos = pos
        self.n = h.n
        self.idx = np.arange(self.n, dtype=np.float64)
        self.Y = h.nums[:, pos]
        self.onehot = feat.one_hot(self.Y)
        self.C = feat.exclusive_cumsum(self.onehot)
        self.P0 = (self.C + 1.0) / (self.idx[:, None] + 100.0)
        self._window_cache = {}
        self._global_cache = {}
        self._decay_cache = {}
        self._age_cache = {}
        self._cond_cache = {}
        self._percentile_cache = {}
        self._doubled_rank_cache = {}
        self._mult = None

    @property
    def multiplicities(self):
        if self._mult is None:
            self._mult = feat.row_multiplicities(self.h.nums)
        return self._mult

    def _window_count(self, window):
        return feat.window_row_count(self.n, window)

    def freq_hist_position(self, window):
        if window not in self._window_cache:
            windowed = feat.windowed_exclusive_sum(self.onehot, window)
            count = self._window_count(window)
            self._window_cache[window] = (windowed + 1.0) / (count[:, None] + 100.0)
        return self._window_cache[window]

    def freq_hist_global(self, window):
        key = ("global", window)
        if key not in self._global_cache:
            windowed = feat.windowed_exclusive_sum(self.multiplicities, window)
            count = self._window_count(window)
            self._global_cache[key] = (windowed + 1.0) / (5.0 * count[:, None] + 100.0)
        return self._global_cache[key]

    def decay(self, half_life):
        if half_life not in self._decay_cache:
            self._decay_cache[half_life] = feat.decay_scores(self.onehot, half_life)
        return self._decay_cache[half_life]

    def cold(self, scope):
        if scope not in self._age_cache:
            if scope == "position":
                source = self.onehot
            elif scope == "any":
                source = (self.multiplicities > 0).astype(np.float64)
            else:
                raise ValueError(f"Unknown cold scope: {scope}")
            self._age_cache[scope] = feat.ages_from_onehot(source).astype(np.float64)
        return self._age_cache[scope]

    def conditional(self, key, context, outcome, valid, n_ctx, n_out):
        if key not in self._cond_cache:
            self._cond_cache[key] = feat.conditional_counts(context, outcome, valid, n_ctx, n_out)
        return self._cond_cache[key]

    def percentile_of(self, key, matrix):
        """Percentile transform cached by ``key``; avoids repeating rankdata across configs."""
        if key not in self._percentile_cache:
            self._percentile_cache[key] = percentile(matrix)
        return self._percentile_cache[key]

    def doubled_rank_of(self, key, matrix):
        """Exact integer 2 * average rank, including half-integer tied ranks."""
        if key not in self._doubled_rank_cache:
            self._doubled_rank_cache[key] = (2 * rankdata(matrix, axis=1, method="average")).astype(np.int16)
        return self._doubled_rank_cache[key]


def score_freq_hist(cache, params):
    if params["scope"] == "position":
        return cache.freq_hist_position(params["window"])
    return cache.freq_hist_global(params["window"])


def score_freq_recent(cache, params):
    return cache.freq_hist_position(params["window"])


def score_decay(cache, params):
    return cache.decay(params["half_life"])


def score_cold(cache, params):
    return cache.cold(params["scope"])


def _percentile_freq_hist_position(cache, window):
    return cache.percentile_of(("pct_freq_hist_position", window), cache.freq_hist_position(window))


def _percentile_cold(cache, scope):
    return cache.percentile_of(("pct_cold", scope), cache.cold(scope))


def _mix_score(cache, w_hist, w_recent, w_age, window):
    total = w_hist * _percentile_freq_hist_position(cache, None)
    if w_recent:
        total = total + w_recent * _percentile_freq_hist_position(cache, window)
    total = total + w_age * _percentile_cold(cache, "position")
    return total


def score_notebook(cache, params):
    w_hist, w_recent, w_age = params["weights"]
    return _mix_score(cache, w_hist, w_recent, w_age, params["window"])


def score_mix(cache, params):
    return _mix_score(cache, params["w_hist"], params["w_recent"], params["w_age"], params["window"])


def _shifted(values, fill=0):
    shifted = np.full_like(values, fill)
    shifted[1:] = values[:-1]
    return shifted


def score_transition(cache, params):
    lam = params["lam"]
    eligible = cache.h.eligible
    context = _shifted(cache.Y)
    counts = cache.conditional("transition", context, cache.Y, eligible, N_VALUES, N_VALUES)
    n_c = counts.sum(axis=1, keepdims=True)
    score = (counts + lam * cache.P0) / (n_c + lam)
    return np.where(eligible[:, None], score, cache.P0)


def score_carry(cache, params):
    lam = params["lam"]
    j = params["origin"]
    eligible = cache.h.eligible
    context = _shifted(cache.h.nums[:, j - 1])
    counts = cache.conditional(f"carry:{j}", context, cache.Y, eligible, N_VALUES, N_VALUES)
    n_c = counts.sum(axis=1, keepdims=True)
    score = (counts + lam * cache.P0) / (n_c + lam)
    return np.where(eligible[:, None], score, cache.P0)


_TIME_N_CTX = {"hour": 24, "weekday": 7, "daypos": 4}


def _daypos_bucket(day_pos):
    return np.minimum(day_pos // 50, 3)


def score_time(cache, params):
    lam = params["lam"]
    kind = params["context"]
    h = cache.h
    if kind == "hour":
        context = h.hour
    elif kind == "weekday":
        context = h.weekday
    elif kind == "daypos":
        context = _daypos_bucket(h.day_pos)
    else:
        raise ValueError(f"Unknown time context: {kind}")
    valid = np.ones(cache.n, dtype=bool)
    counts = cache.conditional(f"time:{kind}", context, cache.Y, valid, _TIME_N_CTX[kind], N_VALUES)
    n_c = counts.sum(axis=1, keepdims=True)
    return (counts + lam * cache.P0) / (n_c + lam)


def score_doubles(cache, params):
    lam = params["lam"]
    eligible = cache.h.eligible
    mult_prev = _shifted(cache.multiplicities)
    doubled = eligible[:, None] & (mult_prev >= 2)
    doubled_f = doubled.astype(np.float64)

    n1 = feat.exclusive_cumsum(doubled_f)
    s1 = feat.exclusive_cumsum(doubled_f * cache.onehot)
    eligible_f = eligible.astype(np.float64)[:, None]
    total_eligible = feat.exclusive_cumsum(eligible_f)
    eligible_hits = feat.exclusive_cumsum(eligible_f * cache.onehot)
    n0 = total_eligible - n1
    s0 = eligible_hits - s1

    n_c = np.where(doubled, n1, n0)
    s_c = np.where(doubled, s1, s0)
    raw = (s_c + lam * cache.P0) / (n_c + lam)
    normalized = raw / raw.sum(axis=1, keepdims=True)
    return np.where(eligible[:, None], normalized, cache.P0)


_CATEGORY_G = {"parity": 2, "lowhigh": 2, "decade": 10, "ending": 10}


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


def score_category(cache, params):
    lam = params["lam"]
    kind = params["kind"]
    group_count = _CATEGORY_G[kind]
    eligible = cache.h.eligible
    cat_all = _category_of(cache.Y, kind)

    run_len = feat.run_lengths(cat_all, eligible)
    prevcat = _shifted(cat_all)
    prev_run_len = _shifted(run_len, fill=1)
    bucket = np.minimum(prev_run_len, 5)
    context = prevcat * 5 + (bucket - 1)

    counts = cache.conditional(f"category:{kind}", context, cat_all, eligible,
                                group_count * 5, group_count)
    n_c = counts.sum(axis=1, keepdims=True)

    cat_onehot = feat.one_hot(cat_all, width=group_count)
    cat_c = feat.exclusive_cumsum(cat_onehot)
    p0_cat = (cat_c + 1.0) / (cache.idx[:, None] + group_count)
    p_cat = (counts + lam * p0_cat) / (n_c + lam)
    p_cat_used = np.where(eligible[:, None], p_cat, p0_cat)

    values = np.arange(N_VALUES)
    value_category = _category_of(values, kind)
    smoothed = cache.C + 1.0
    category_totals = np.zeros((cache.n, group_count))
    for k in range(group_count):
        category_totals[:, k] = smoothed[:, value_category == k].sum(axis=1)
    value_share = smoothed / category_totals[:, value_category]
    return p_cat_used[:, value_category] * value_share


_ENSEMBLE_MEMBERS = protocol.ENSEMBLE_MEMBERS  # single source of truth


def _percentile_of_family(cache, family, params):
    key = ("pct_family", family, tuple(sorted(params.items())))
    return cache.percentile_of(key, _score_family(cache, family, params))


def score_ensemble(cache, params):
    percentiles = [_percentile_of_family(cache, family, p) for _, family, p in _ENSEMBLE_MEMBERS]
    borda = np.mean(percentiles, axis=0)
    if params["method"] == "borda":
        return borda
    if params["method"] == "vote":
        scores = [_score_family(cache, family, p) for _, family, p in _ENSEMBLE_MEMBERS]
        votes = np.sum([topk_mask(s, 25) for s in scores], axis=0)
        return votes * 10 + borda
    raise ValueError(f"Unknown ensemble method: {params['method']}")


_FAMILY_FUNCS = {
    "freq_hist": score_freq_hist,
    "freq_recent": score_freq_recent,
    "decay": score_decay,
    "cold": score_cold,
    "notebook": score_notebook,
    "mix": score_mix,
    "transition": score_transition,
    "carry": score_carry,
    "doubles": score_doubles,
    "category": score_category,
    "time": score_time,
    "ensemble": score_ensemble,
}

_PROBABILISTIC_FAMILIES = {
    "freq_hist", "freq_recent", "transition", "carry", "time", "category", "doubles",
}


def is_probabilistic(family, params):
    del params
    return family in _PROBABILISTIC_FAMILIES


def _score_family(cache, family, params):
    func = _FAMILY_FUNCS.get(family)
    if func is None:
        raise ValueError(f"Unknown model family: {family}")
    return func(cache, params)


_CONFIG_INDEX = {cid: (family, params)
                  for cid, family, params in protocol.all_configs(include_supervised=False)}


def score_config(h, config, pos, cache=None):
    """Score a config given either its protocol ``config_id`` or a ``(family, params)`` pair."""
    if cache is None:
        cache = FeatureCache(h, pos)
    if isinstance(config, str):
        if config not in _CONFIG_INDEX:
            raise ValueError(f"Unknown config id: {config}")
        family, params = _CONFIG_INDEX[config]
    else:
        family, params = config
    return _score_family(cache, family, params)


def _weighted_rank_key(components, weights) -> np.ndarray:
    """Common-denominator integer numerator of a weighted mean of average ranks.

    A component is a doubled average rank; the shared percentile divisor (2 * 99)
    and the positive weight denominator cannot affect ordering. No float score is
    rounded, and the returned integer keys preserve genuine one-rank differences.
    """
    rational = [Fraction(str(weight)) for weight in weights]
    denominator = lcm(*(weight.denominator for weight in rational))
    coefficients = [int(weight * denominator) for weight in rational]
    dtype = np.int32 if 200 * sum(abs(c) for c in coefficients) < np.iinfo(np.int32).max else np.int64
    result = np.zeros_like(components[0], dtype=dtype)
    for coefficient, ranks in zip(coefficients, components, strict=True):
        result += coefficient * ranks.astype(dtype)
    return result


def _mix_rank_key(cache, weights, window) -> np.ndarray:
    components = [cache.doubled_rank_of(("hist", None), cache.freq_hist_position(None)),
                  cache.doubled_rank_of(("hist", window), cache.freq_hist_position(window))
                  if weights[1] else None,
                  cache.doubled_rank_of(("cold", "position"), cache.cold("position"))]
    return _weighted_rank_key([r for r in components if r is not None],
                              [w for w, r in zip(weights, components, strict=True) if r is not None])


def _ensemble_rank_key(cache, members, method="borda") -> np.ndarray:
    borda = np.zeros((cache.n, N_VALUES), dtype=np.int32)
    for _, family, p in members:
        borda += cache.doubled_rank_of(("family", family, tuple(sorted(p.items()))),
                                      _score_family(cache, family, p))
    if method == "borda":
        return borda
    if method == "vote":
        votes = np.zeros((cache.n, N_VALUES), dtype=np.int32)
        for _, family, p in members:
            votes += topk_mask(_score_family(cache, family, p), 25)
        # Borda spans at most 198 * n_members; one vote always dominates it.
        return votes * (198 * len(members) + 1) + borda
    raise ValueError(f"Unknown ensemble method: {method}")


def ranking_key_config(h, config, pos, cache=None, scores=None) -> np.ndarray:
    """Ordering key for a config (higher wins); exact for percentile mixtures.

    Non-mixtures return their unmodified scores: conditional probabilities are not
    quantized, since no exact-tie equivalence proof exists for their float arithmetic.
    """
    if cache is None:
        cache = FeatureCache(h, pos)
    if isinstance(config, str):
        family, params = _CONFIG_INDEX[config]
    else:
        family, params = config
    if family == "mix":
        return _mix_rank_key(cache, (params["w_hist"], params["w_recent"], params["w_age"]), params["window"])
    if family == "notebook":
        return _mix_rank_key(cache, params["weights"], params["window"])
    if family == "ensemble":
        return _ensemble_rank_key(cache, _ENSEMBLE_MEMBERS, params["method"])
    return scores if scores is not None else _score_family(cache, family, params)


def ranking_key_ablation(h, ablation_id, pos, cache=None, scores=None) -> np.ndarray:
    """Ordering key for a notebook/ensemble ablation; renormalization is order-neutral."""
    if cache is None:
        cache = FeatureCache(h, pos)
    kind, params = _ABLATION_INDEX[ablation_id]
    if kind == "notebook_ablation":
        weights = {"hist": 9, "recent": 9, "age": 2}
        weights[params["drop"]] = 0
        return _mix_rank_key(cache, (weights["hist"], weights["recent"], weights["age"]), params["window"])
    if kind == "ensemble_ablation":
        return _ensemble_rank_key(cache, [m for m in _ENSEMBLE_MEMBERS if m[0] != params["drop"]])
    raise ValueError(f"Unknown ablation kind: {kind}")


def any_scores(positional_scores):
    """Mean of the percentile of each of the five positional score matrices."""
    return np.mean([percentile(s) for s in positional_scores], axis=0)


def _renormalized_notebook_weights(drop):
    base = {"hist": 0.45, "recent": 0.45, "age": 0.10}
    del base[drop]
    total = sum(base.values())
    return {key: value / total for key, value in base.items()}


def _build_ablations():
    ablations = []
    for drop in ("hist", "recent", "age"):
        weights = _renormalized_notebook_weights(drop)
        for window in (20, 100, 500, 2000):
            ablation_id = f"ablation:notebook-no_{drop},window={window}"
            ablations.append((ablation_id, "notebook_ablation",
                               {"drop": drop, "window": window, "weights": weights}))
    for name, _, _ in _ENSEMBLE_MEMBERS:
        ablation_id = f"ablation:ensemble-no_{name}"
        ablations.append((ablation_id, "ensemble_ablation", {"drop": name}))
    return tuple(ablations)


ABLATIONS = _build_ablations()
_ABLATION_INDEX = {aid: (kind, params) for aid, kind, params in ABLATIONS}


def _notebook_ablation_score(cache, params):
    drop = params["drop"]
    weights = params["weights"]
    window = params["window"]
    total = np.zeros((cache.n, N_VALUES))
    if drop != "hist":
        total = total + weights["hist"] * _percentile_freq_hist_position(cache, None)
    if drop != "recent":
        total = total + weights["recent"] * _percentile_freq_hist_position(cache, window)
    if drop != "age":
        total = total + weights["age"] * _percentile_cold(cache, "position")
    return total


def _ensemble_ablation_score(cache, params):
    drop = params["drop"]
    members = [(family, p) for name, family, p in _ENSEMBLE_MEMBERS if name != drop]
    percentiles = [_percentile_of_family(cache, family, p) for family, p in members]
    return np.mean(percentiles, axis=0)


def score_ablation(h, ablation_id, pos, cache=None):
    if cache is None:
        cache = FeatureCache(h, pos)
    if ablation_id not in _ABLATION_INDEX:
        raise ValueError(f"Unknown ablation id: {ablation_id}")
    kind, params = _ABLATION_INDEX[ablation_id]
    if kind == "notebook_ablation":
        return _notebook_ablation_score(cache, params)
    if kind == "ensemble_ablation":
        return _ensemble_ablation_score(cache, params)
    raise ValueError(f"Unknown ablation kind: {kind}")
