"""Row-wise ranking, percentile and tie-break utilities shared by every scoring family.

Every family orders values by (higher score, then lower ``TIE`` priority); ``TIE`` is
the protocol's fixed random permutation so ties never depend on observed data.
"""

import numpy as np
from scipy.stats import rankdata

from chance_rank.protocol import tie_priority

TIE = tie_priority()  # int64[100], lower wins ties


def percentile(scores):
    """Row-wise percentile in [0, 1]; higher score -> higher percentile, average-rank ties."""
    ranks = rankdata(scores, axis=1, method="average")
    return (ranks - 1) / (scores.shape[1] - 1)


def ranking(row_scores, tie=TIE):
    """Indices of the 100 values best first, ordered by (-score, tie[v])."""
    return np.lexsort((tie, -row_scores))


def rank_matrix(S, tie=TIE):
    """(M, 100) uint8 rankings best first, one row per row of ``S``."""
    tie_b = np.broadcast_to(tie, S.shape)
    order = np.lexsort((tie_b, -S), axis=-1)
    return order.astype(np.uint8)


def winner_rank(S, y):
    """0-based rank of value ``y[m]`` within row ``S[m]``; 0 is best.

    ``#{v: S[v] > S[y]} + #{v: S[v] == S[y] and tie[v] < tie[y]}``.
    """
    rows = np.arange(S.shape[0])
    s_y = S[rows, y]
    tie_y = TIE[y]
    greater = (S > s_y[:, None]).sum(axis=1)
    equal_better_tie = ((S == s_y[:, None]) & (TIE[None, :] < tie_y[:, None])).sum(axis=1)
    return greater + equal_better_tie


def topk_mask(S, k):
    """(M, 100) boolean mask of the top-``k`` values per row, consistent with ``ranking``."""
    order = rank_matrix(S)
    mask = np.zeros(S.shape, dtype=bool)
    rows = np.arange(S.shape[0])[:, None]
    mask[rows, order[:, :k]] = True
    return mask
