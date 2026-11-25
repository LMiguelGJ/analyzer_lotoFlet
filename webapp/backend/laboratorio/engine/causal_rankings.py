"""Causal on-the-fly rankings for lists that ship no precomputed ``pos1.npz``.

The four simple families of the archived ``chance_rank`` models (cold, freq_hist,
freq_recent, decay) are reimplemented here with numpy only. Row ``t`` of every ranking
depends exclusively on the draws ``< t`` (row ``t`` itself is never read), so no future
information reaches a bet. The semantics mirror ``repo_ref/chance_rank/models.py`` and
``features.py``:

* ``freq_hist``   position scope: ``(count + 1) / (rows + 100)`` over the first-prize column;
  ``global`` (alias ``any``) scope counts every position. Rows in the denominator share one
  value, so ordering by the integer count is exactly equivalent to ordering by the score.
* ``freq_recent`` the same position-scope count over the last ``window`` rows.
* ``decay``       ``E[t] = sum_{s<t} a**(t-1-s) * onehot[s]`` with ``a = 0.5**(1/half_life)``.
* ``cold``        age since the last occurrence (exclusive of row ``t``); never seen -> ``t + 1``.

Rankings order the 100 numbers best first by (higher score, then lower ``TIE`` priority);
``TIE`` is the protocol's fixed random permutation, so ties never depend on observed data.

``DEFAULT_PARAMS`` are the fixed configurations used for lists without precomputed
rankings (Leidsa). The archived rankings picked a config per walk-forward fold; a short
history cannot support that selection, so one default per family is used: the position
scope, the 500-draw window and 500-draw half-life, which are the most frequently picked
values of the archived folds and the ones used by its ensemble. Chance Express never uses
this module for its results: it keeps the precomputed ``pos1.npz``; ``test_causal_rankings``
proves both implementations produce identical rows when given the archived per-fold config.
"""

import hashlib
import json
import threading
from collections import OrderedDict
from functools import lru_cache

import numpy as np

from laboratorio.engine.adapter import DataError

N_VALUES = 100
_PROTOCOL_TIE_LABEL = "chance-rank-v1/tie"

#: Families this module can rank, in the order they are offered.
FAMILIES = ("cold", "freq_hist", "freq_recent", "decay")

#: Extra families offered only by lists whose rankings are computed on the fly (Leidsa).
EXTRA_FAMILIES = ("transition", "overdue", "digits", "ensemble")

#: Every family this module can rank, in the order they are offered.
LEIDSA_FAMILIES = FAMILIES + EXTRA_FAMILIES

DEFAULT_PARAMS: dict[str, dict] = {
    "cold": {"scope": "position"},
    "freq_hist": {"scope": "position", "window": None},
    "freq_recent": {"window": 500},
    "decay": {"half_life": 500},
    "transition": {"fallback_window": 500},
    "overdue": {},
    "digits": {"window": 500},
    "ensemble": {
        "components": (
            "cold",
            "freq_hist",
            "freq_recent",
            "decay",
            "transition",
            "overdue",
            "digits",
        )
    },
}


#: Components the ensemble can vote with (never the ensemble itself).
ENSEMBLE_COMPONENTS = DEFAULT_PARAMS["ensemble"]["components"]
TIE_BREAKS = ("fixed", "seeded")
_SEEDED_TIE_LABEL = "chance-rank-v1/seeded-tie"
#: Most (system, params) rankings one list keeps at once; the oldest are dropped first.
_CACHE_LIMIT = 64
#: Most distinct parameter variants one list keeps at once.
_VARIANT_LIMIT = 16


def resolve_params(system: str, params: dict | None = None) -> dict:
    """Family defaults with the partial override merged on top (nested dicts merge too)."""
    merged = dict(DEFAULT_PARAMS[system])
    for key, value in (params or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _canonical(params: dict) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"), default=list)


def _tie_priority() -> np.ndarray:
    """int64[100]: priority[v] = position of v in the protocol's fixed random permutation."""
    seed = int.from_bytes(hashlib.sha256(_PROTOCOL_TIE_LABEL.encode()).digest()[:8], "big")
    permutation = np.random.Generator(np.random.PCG64(seed)).permutation(N_VALUES)
    priority = np.empty(N_VALUES, dtype=np.int64)
    priority[permutation] = np.arange(N_VALUES, dtype=np.int64)
    return priority


TIE = _tie_priority()  # lower wins ties


def _check_nums(nums: np.ndarray) -> np.ndarray:
    nums = np.asarray(nums)
    if nums.ndim != 2 or nums.shape[1] < 1:
        raise DataError("draw numbers must be a (draws, positions) matrix")
    if nums.size and (int(nums.min()) < 0 or int(nums.max()) >= N_VALUES):
        raise DataError("draw numbers must be between 0 and 99")
    return nums.astype(np.int64, copy=False)


def _exclusive_counts(indicator: np.ndarray) -> np.ndarray:
    """(n + 1, width) cumulative counts: row t holds the counts over rows < t."""
    n = indicator.shape[0]
    cumulative = np.zeros((n + 1, indicator.shape[1]), dtype=np.int64)
    np.cumsum(indicator, axis=0, out=cumulative[1:])
    return cumulative


def _first_position_indicator(nums: np.ndarray) -> np.ndarray:
    indicator = np.zeros((nums.shape[0], N_VALUES), dtype=np.int8)
    indicator[np.arange(nums.shape[0]), nums[:, 0]] = 1
    return indicator


def _any_position_indicator(nums: np.ndarray) -> np.ndarray:
    """1 where a value appears at least once in the row (any position)."""
    indicator = np.zeros((nums.shape[0], N_VALUES), dtype=np.int8)
    rows = np.arange(nums.shape[0])
    for column in range(nums.shape[1]):
        indicator[rows, nums[:, column]] = 1
    return indicator


def _multiplicities(nums: np.ndarray) -> np.ndarray:
    counts = np.zeros((nums.shape[0], N_VALUES), dtype=np.int8)
    rows = np.arange(nums.shape[0])
    for column in range(nums.shape[1]):
        np.add.at(counts, (rows, nums[:, column]), 1)
    return counts


def _windowed(cumulative: np.ndarray, window: int | None) -> np.ndarray:
    """Counts over ``[max(0, t - window), t)`` for every t; ``None`` means ``[0, t)``."""
    n = cumulative.shape[0] - 1
    upto = cumulative[:n]
    if window is None:
        return upto
    lag = np.clip(np.arange(n) - window, 0, None)
    return upto - cumulative[lag]


def _freq_hist_key(nums: np.ndarray, params: dict) -> np.ndarray:
    scope, window = params["scope"], params["window"]
    if scope == "position":
        indicator = _first_position_indicator(nums)
    elif scope in ("global", "any"):
        indicator = _multiplicities(nums)
    else:
        raise ValueError(f"Unknown freq_hist scope: {scope}")
    return _windowed(_exclusive_counts(indicator), window)


def _freq_recent_key(nums: np.ndarray, params: dict) -> np.ndarray:
    return _windowed(_exclusive_counts(_first_position_indicator(nums)), params["window"])


def _decay_key(nums: np.ndarray, params: dict) -> np.ndarray:
    n = nums.shape[0]
    keep = 0.5 ** (1.0 / params["half_life"])
    onehot = np.zeros((n, N_VALUES), dtype=np.float64)
    onehot[np.arange(n), nums[:, 0]] = 1.0
    scores = np.zeros((n, N_VALUES), dtype=np.float64)
    state = np.zeros(N_VALUES, dtype=np.float64)
    for t in range(1, n):
        # Same float operations as ``scipy.signal.lfilter([0, 1], [1, -a], onehot)``.
        state = onehot[t - 1] + keep * state
        scores[t] = state
    return scores


def _cold_key(nums: np.ndarray, params: dict) -> np.ndarray:
    scope = params["scope"]
    if scope == "position":
        indicator = _first_position_indicator(nums)
    elif scope == "any":
        indicator = _any_position_indicator(nums)
    else:
        raise ValueError(f"Unknown cold scope: {scope}")
    n = nums.shape[0]
    index = np.arange(n, dtype=np.int64)
    occurrence = np.where(indicator > 0, index[:, None], -1)
    last_inclusive = np.maximum.accumulate(occurrence, axis=0)
    last_exclusive = np.vstack([np.full((1, N_VALUES), -1, dtype=np.int64), last_inclusive[:-1]])
    return index[:, None] - last_exclusive


def _transition_key(nums: np.ndarray, params: dict) -> np.ndarray:
    """Transition matrix of first-position pairs; row ``t`` counts only pairs with ``s <= t-1``.

    ``score[t] = M_t[a[t-1]] + f[t] / (1000 * (fallback_window + 1))``: the pair count from
    the score matrix dominates and the windowed frequency only breaks ties and covers states
    without history. Rows 0 and 1 have no pair yet, so they rank by ``f`` alone (row 0 by 0).
    """
    n = nums.shape[0]
    a = nums[:, 0]
    fallback_window = params["fallback_window"]
    fallback = _freq_recent_key(nums, {"window": fallback_window})
    scale = 1.0 / (1000 * (fallback_window + 1))
    scores = np.zeros((n, N_VALUES), dtype=np.float64)
    counts = np.zeros((N_VALUES, N_VALUES), dtype=np.int64)
    for t in range(n):
        scores[t] = fallback[t] * scale
        if t >= 2:
            scores[t] += counts[a[t - 1]]
        if t >= 1:
            # Pair ``s = t``: it becomes visible from row ``t + 1`` on.
            counts[a[t - 1], a[t]] += 1
    return scores


def _overdue_key(nums: np.ndarray, params: dict) -> np.ndarray:
    """``age / mean_gap`` over first-position appearances before the row.

    ``age = t - last_seen(v)`` (never seen -> ``t + 1``); ``mean_gap`` is the average gap
    between the first and the last sighting (``100`` until the number appears twice).
    """
    del params
    n = nums.shape[0]
    indicator = _first_position_indicator(nums)
    index = np.arange(n, dtype=np.int64)[:, None]
    occurrence = np.where(indicator > 0, index, -1)
    last_inclusive = np.maximum.accumulate(occurrence, axis=0)
    last = np.vstack([np.full((1, N_VALUES), -1, dtype=np.int64), last_inclusive[:-1]])
    first_occurrence = np.where(indicator > 0, index, n)
    first_inclusive = np.minimum.accumulate(first_occurrence, axis=0)
    first = np.vstack([np.full((1, N_VALUES), n, dtype=np.int64), first_inclusive[:-1]])
    counts = _exclusive_counts(indicator)[:n]
    age = np.where(last >= 0, index - last, index + 1)
    span = np.maximum(last - first, 0)
    mean_gap = np.where(counts >= 2, span / np.maximum(counts - 1, 1), 100.0)
    return age / mean_gap


def _digits_key(nums: np.ndarray, params: dict) -> np.ndarray:
    """``U[v % 10] + D[v // 10]``: unit and decade shares over the last ``window`` draws."""
    n = nums.shape[0]
    a = nums[:, 0]
    index = np.arange(n)
    units = np.zeros((n, 10), dtype=np.int8)
    units[index, a % 10] = 1
    decades = np.zeros((n, 10), dtype=np.int8)
    decades[index, a // 10] = 1
    window = params["window"]
    rows = np.minimum(np.arange(n, dtype=np.int64), window).astype(np.float64)
    denominator = np.maximum(rows, 1.0)[:, None]
    kept = rows[:, None] > 0
    unit_share = np.where(kept, _windowed(_exclusive_counts(units), window) / denominator, 0.0)
    decade_share = np.where(kept, _windowed(_exclusive_counts(decades), window) / denominator, 0.0)
    numbers = np.arange(N_VALUES, dtype=np.int64)
    return unit_share[:, numbers % 10] + decade_share[:, numbers // 10]


def _component_params(params: dict, component: str, base: dict | None = None) -> dict:
    """Params one ensemble component ranks with: defaults, overrides, then the vote's tie-break."""
    merged = resolve_params(component, base)
    overrides = (params.get("component_params") or {}).get(component)
    if overrides:
        merged = resolve_params(component, {**merged, **overrides})
    if params.get("tie_break", "fixed") != "fixed":
        merged["tie_break"] = params["tie_break"]
    return merged


def _borda(rankings: list[np.ndarray]) -> np.ndarray:
    """Minus the mean ranking position of every component (0 is the best)."""
    positions = [np.argsort(ranking, axis=1).astype(np.float64) for ranking in rankings]
    return -np.mean(positions, axis=0)


def _ensemble_key(nums: np.ndarray, params: dict) -> np.ndarray:
    """Borda score of the chosen components, each ranked with its own params."""
    params = resolve_params("ensemble", params)
    return _borda(
        [
            causal_ranking(component, nums, _component_params(params, component))
            for component in params["components"]
        ]
    )


_KEYS = {
    "cold": _cold_key,
    "freq_hist": _freq_hist_key,
    "freq_recent": _freq_recent_key,
    "decay": _decay_key,
    "transition": _transition_key,
    "overdue": _overdue_key,
    "digits": _digits_key,
    "ensemble": _ensemble_key,
}


def score_matrix(system: str, nums: np.ndarray, params: dict | None = None) -> np.ndarray:
    """(n, 100) causal scores, higher is better; ``params`` default to ``DEFAULT_PARAMS``."""
    if system not in _KEYS:
        raise DataError(f"ranking system unavailable: {system}")
    nums = _check_nums(nums)
    if nums.shape[0] == 0:
        return np.zeros((0, N_VALUES), dtype=np.int64)
    return _KEYS[system](nums, resolve_params(system, params))


@lru_cache(maxsize=65536)
def _seeded_priority(row: int) -> np.ndarray:
    """int64[100]: tie priority of draw ``row`` (lower wins); depends on the index alone."""
    digest = hashlib.sha256(f"{_SEEDED_TIE_LABEL}/{row}".encode()).digest()
    seed = int.from_bytes(digest[:8], "big")
    permutation = np.random.Generator(np.random.PCG64(seed)).permutation(N_VALUES)
    priority = np.empty(N_VALUES, dtype=np.int64)
    priority[permutation] = np.arange(N_VALUES, dtype=np.int64)
    priority.setflags(write=False)
    return priority


def rank_rows(
    scores: np.ndarray, rows: np.ndarray | None = None, tie_break: str = "fixed"
) -> np.ndarray:
    """uint8 rankings best first for the chosen score rows (all rows by default).

    Order is (higher score, then lower tie priority). ``fixed`` uses the protocol's ``TIE``
    (as ``chance_rank.ranking``); ``seeded`` uses a permutation derived from the draw index,
    so equal scores do not favour the same numbers row after row and stay reproducible.
    """
    if tie_break not in TIE_BREAKS:
        raise DataError(f"unknown tie break: {tie_break}")
    selected = scores if rows is None else scores[np.asarray(rows, dtype=np.int64)]
    indices = np.arange(len(scores)) if rows is None else np.asarray(rows, dtype=np.int64)
    result = np.empty(selected.shape, dtype=np.uint8)
    tie = np.broadcast_to(TIE, (min(len(selected), 8192), N_VALUES))
    for start in range(0, len(selected), 8192):
        chunk = selected[start : start + 8192]
        if tie_break == "seeded":
            priority = np.stack([_seeded_priority(int(i)) for i in indices[start : start + 8192]])
        else:
            priority = tie[: len(chunk)]
        order = np.lexsort((priority, -chunk), axis=-1)
        result[start : start + 8192] = order.astype(np.uint8)
    return result


def causal_ranking(
    system: str, nums: np.ndarray, params: dict | None = None, rows: np.ndarray | None = None
) -> np.ndarray:
    """Rankings of ``rows`` (all by default), each from the draws strictly before it."""
    tie_break = (params or {}).get("tie_break", "fixed")
    return rank_rows(score_matrix(system, nums, params), rows, tie_break)


class CausalRankings:
    """Duck-types the frozen ``Rankings`` for lists whose rankings are computed on the fly.

    Every draw is ranked (``row_ids`` is the whole history); ranking ``t`` is built from draws
    ``< t``. ``family`` returns the cached ``(n, 100)`` uint8 matrix of one system. ``params``
    may override only part of a family (the rest keeps its default). ``variant`` derives a
    sibling with other params that shares this object's ranking cache.
    """

    path = None

    def __init__(
        self,
        nums: np.ndarray,
        params: dict[str, dict] | None = None,
        *,
        _shared: "_SharedCache | None" = None,
    ):
        self._nums = _check_nums(nums)
        overrides = params or {}
        self._params = {system: resolve_params(system, overrides.get(system)) for system in _KEYS}
        self.row_ids = np.arange(self._nums.shape[0], dtype=np.int64)
        self._shared = _shared or _SharedCache()

    def variant(self, params: dict[str, dict] | None) -> "CausalRankings":
        """The rankings of this history under other params; one object per distinct params."""
        key = _canonical(params or {})
        shared = self._shared
        with shared.lock:
            found = shared.variants.get(key)
            if found is not None:
                shared.variants.move_to_end(key)
                return found
            found = CausalRankings(self._nums, params, _shared=shared)
            shared.variants[key] = found
            while len(shared.variants) > _VARIANT_LIMIT:
                shared.variants.popitem(last=False)
            return found

    def family(self, system: str) -> np.ndarray:
        if system not in _KEYS:
            raise DataError(f"ranking system unavailable: {system}")
        return self._ranking(system, self._params[system])

    def _ranking(self, system: str, params: dict) -> np.ndarray:
        """Ranking of ``system`` under exactly ``params``, cached by (system, params)."""
        key = (system, _canonical(params))
        shared = self._shared
        with shared.lock:
            cached = shared.rankings.get(key)
            if cached is not None:
                shared.rankings.move_to_end(key)
                return cached
        if system == "ensemble":
            votes = []
            for component in params["components"]:
                own = _component_params(params, component, self._params[component])
                votes.append(self._ranking(component, own))
            ranking = rank_rows(_borda(votes), None, params.get("tie_break", "fixed"))
        else:
            ranking = causal_ranking(system, self._nums, params)
        with shared.lock:
            shared.rankings[key] = ranking
            while len(shared.rankings) > _CACHE_LIMIT:
                shared.rankings.popitem(last=False)
        return ranking


class _SharedCache:
    """Ranking matrices and variants shared by one history's ``CausalRankings`` family."""

    def __init__(self):
        self.lock = threading.RLock()
        self.rankings: OrderedDict[tuple[str, str], np.ndarray] = OrderedDict()
        self.variants: OrderedDict[str, CausalRankings] = OrderedDict()
