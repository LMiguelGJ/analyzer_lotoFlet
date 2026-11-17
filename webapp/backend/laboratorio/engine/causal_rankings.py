"""Causal on-the-fly rankings for lists that ship no precomputed ``pos1.npz``.

The four simple families of the archived ``chance_rank`` models (cold, freq_hist,
freq_recent, decay) are reimplemented here with numpy only. Row ``t`` of every ranking
depends exclusively on the draws ``< t`` (row ``t`` itself is never read), so no future
information reaches a bet. The semantics mirror ``repo_ref/chance_rank/models.py`` and
``features.py``:

* ``freq_hist``   position scope: ``(count + 1) / (rows + 100)`` over the first-prize column;
  ``global`` scope counts every position. Rows in the denominator share one value, so
  ordering by the integer count is exactly equivalent to ordering by the score.
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

import numpy as np

from laboratorio.engine.adapter import DataError

N_VALUES = 100
_PROTOCOL_TIE_LABEL = "chance-rank-v1/tie"

#: Families this module can rank, in the order they are offered.
FAMILIES = ("cold", "freq_hist", "freq_recent", "decay")

DEFAULT_PARAMS: dict[str, dict] = {
    "cold": {"scope": "position"},
    "freq_hist": {"scope": "position", "window": None},
    "freq_recent": {"window": 500},
    "decay": {"half_life": 500},
}


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
    """(n + 1, 100) cumulative counts: row t holds the counts over rows < t."""
    n = indicator.shape[0]
    cumulative = np.zeros((n + 1, N_VALUES), dtype=np.int64)
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
    elif scope == "global":
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


_KEYS = {
    "cold": _cold_key,
    "freq_hist": _freq_hist_key,
    "freq_recent": _freq_recent_key,
    "decay": _decay_key,
}


def score_matrix(system: str, nums: np.ndarray, params: dict | None = None) -> np.ndarray:
    """(n, 100) causal scores, higher is better; ``params`` default to ``DEFAULT_PARAMS``."""
    if system not in _KEYS:
        raise DataError(f"ranking system unavailable: {system}")
    nums = _check_nums(nums)
    if nums.shape[0] == 0:
        return np.zeros((0, N_VALUES), dtype=np.int64)
    return _KEYS[system](nums, DEFAULT_PARAMS[system] if params is None else params)


def rank_rows(scores: np.ndarray, rows: np.ndarray | None = None) -> np.ndarray:
    """uint8 rankings best first for the chosen score rows (all rows by default).

    Order is (higher score, then lower ``TIE`` priority), as ``chance_rank.ranking``.
    """
    selected = scores if rows is None else scores[np.asarray(rows, dtype=np.int64)]
    result = np.empty(selected.shape, dtype=np.uint8)
    tie = np.broadcast_to(TIE, (min(len(selected), 8192), N_VALUES))
    for start in range(0, len(selected), 8192):
        chunk = selected[start : start + 8192]
        order = np.lexsort((tie[: len(chunk)], -chunk), axis=-1)
        result[start : start + 8192] = order.astype(np.uint8)
    return result


def causal_ranking(
    system: str, nums: np.ndarray, params: dict | None = None, rows: np.ndarray | None = None
) -> np.ndarray:
    """Rankings of ``rows`` (all by default), each from the draws strictly before it."""
    return rank_rows(score_matrix(system, nums, params), rows)


class CausalRankings:
    """Duck-types the frozen ``Rankings`` for lists whose rankings are computed on the fly.

    Every draw is ranked (``row_ids`` is the whole history); ranking ``t`` is built from draws
    ``< t``. ``family`` returns the cached ``(n, 100)`` uint8 matrix of one system.
    """

    path = None

    def __init__(self, nums: np.ndarray, params: dict[str, dict] | None = None):
        self._nums = _check_nums(nums)
        self._params = {**DEFAULT_PARAMS, **(params or {})}
        self.row_ids = np.arange(self._nums.shape[0], dtype=np.int64)
        self._cache: dict[str, np.ndarray] = {}

    def family(self, system: str) -> np.ndarray:
        if system not in _KEYS:
            raise DataError(f"ranking system unavailable: {system}")
        if system not in self._cache:
            self._cache[system] = causal_ranking(system, self._nums, self._params[system])
        return self._cache[system]
