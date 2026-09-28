"""Horizon-block replay: consecutive-target partitioning and updated/frozen ranks.

Each fold's target rows are partitioned per segment into complete blocks of
``HORIZON_BLOCK`` (20) consecutive targets, dropping any remainder; blocks never cross a
segment, day or fold boundary because segments already stop at every 10-minute gap and
day change (``chance_rank.data``), and targets are pre-restricted to the fold's test
days. "Updated" ranks reuse each target's own causal score row; "frozen" ranks re-score
every target in a block under the first target's score row only, i.e. the state already
available before that block started (``score_config`` rows are causal by construction).
"""

import numpy as np

from chance_rank import protocol
from chance_rank.ranking import winner_rank
from chance_rank.walkforward import rows_in_days


def horizon_blocks(h, fold, mask):
    """Row indices of complete 20-target blocks within ``fold``'s test days, per segment.

    Returns ``(blocks, dropped)``: ``blocks`` is an int64 ``(n_blocks, HORIZON_BLOCK)``
    array, ``dropped`` is the count of targets left over after the last full block.
    """
    target_rows = mask & rows_in_days(h, *fold.test_days)
    idx = np.nonzero(target_rows)[0]
    block_size = protocol.HORIZON_BLOCK
    blocks, dropped = [], 0
    for seg_id in np.unique(h.segment[idx]):
        seg_idx = idx[h.segment[idx] == seg_id]
        n_blocks = len(seg_idx) // block_size
        dropped += len(seg_idx) - n_blocks * block_size
        for b in range(n_blocks):
            blocks.append(seg_idx[b * block_size:(b + 1) * block_size])
    result = np.array(blocks, dtype=np.int64) if blocks else np.empty((0, block_size), dtype=np.int64)
    return result, dropped


def updated_block_ranks(ranks, blocks):
    """Each target's own rank, grouped into blocks: ``ranks[blocks]``."""
    return ranks[blocks]


def frozen_block_ranks(S, targets_values, blocks):
    """Rank every target in each block under the score row of the block's first target.

    ``targets_values``: ``(N,)`` for a single position or ``(N, 5)`` for the any-target.
    Column 0 of the result always equals column 0 of ``updated_block_ranks``, since the
    first target's own causal score row *is* the state before it.
    """
    origin_rows = blocks[:, 0]
    n_blocks, block_len = blocks.shape
    S_origin = S[origin_rows]

    if targets_values.ndim == 1:
        y = targets_values[blocks]  # (n_blocks, block_len)
        S_rep = np.repeat(S_origin, block_len, axis=0)
        ranks = winner_rank(S_rep, y.reshape(-1))
        return ranks.reshape(n_blocks, block_len).astype(np.uint8)

    n_pos = targets_values.shape[1]
    y = targets_values[blocks]  # (n_blocks, block_len, n_pos)
    S_rep = np.repeat(S_origin, block_len * n_pos, axis=0)
    ranks = winner_rank(S_rep, y.reshape(-1))
    return ranks.reshape(n_blocks, block_len, n_pos).astype(np.uint8)


def horizon_hits(block_ranks, k, H):
    """Hits within the first ``H`` targets of each block: ``(count_hits, any_hit)``.

    For any-target ranks (shape ``(n_blocks, HORIZON_BLOCK, 5)``), a target hits when the
    minimum rank over its 5 drawn values is below ``k``.
    """
    prefix = block_ranks[:, :H, ...]
    hit = prefix.min(axis=2) < k if prefix.ndim == 3 else prefix < k
    return hit.sum(axis=1), hit.any(axis=1)
