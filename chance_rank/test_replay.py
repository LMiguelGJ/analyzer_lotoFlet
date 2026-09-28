"""Horizon block partitioning and updated/frozen rank replay."""

from datetime import date, timedelta

import numpy as np
import pytest

from chance_rank import protocol
from chance_rank.data import make_history
from chance_rank.ranking import winner_rank
from chance_rank.replay import (
    frozen_block_ranks,
    horizon_blocks,
    horizon_hits,
    updated_block_ranks,
)
from chance_rank.walkforward import Fold


def _daily_history(n_days, rows_per_day, gap_at=None, seed_label="test-replay-history"):
    generator = protocol.rng(seed_label)
    entries = []
    for d in range(n_days):
        iso = (date(2024, 1, 1) + timedelta(days=d)).isoformat()
        minute = 5
        for r in range(rows_per_day):
            if gap_at is not None and (d, r) == gap_at:
                minute += 10  # break eligibility with a 10-minute gap
            hour, mm = divmod(minute, 60)
            nums = generator.integers(0, 100, size=5).tolist()
            entries.append((iso, f"{hour:02d}:{mm:02d}", nums, "premios.do"))
            minute += 5
    return make_history(entries)


# --- horizon_blocks: partition into complete blocks of 20, dropping remainders -------

def test_horizon_blocks_partitions_into_20_and_drops_remainder():
    h = _daily_history(n_days=3, rows_per_day=25)  # 25/day -> 1 block of 20 + 5 dropped/day
    fold = Fold(index=0, test_days=(0, 3), inner=((0, 0), (0, 0), (0, 0)))
    mask = np.ones(h.n, dtype=bool)
    blocks, dropped = horizon_blocks(h, fold, mask)
    assert blocks.shape == (3, 20)
    assert blocks.dtype == np.int64
    assert dropped == 3 * 5
    assert np.all(h.day[blocks[0]] == h.day[blocks[0, 0]])


def test_horizon_blocks_respects_fold_test_days():
    h = _daily_history(n_days=4, rows_per_day=20)
    fold = Fold(index=0, test_days=(1, 3), inner=((0, 0), (0, 0), (0, 0)))
    mask = np.ones(h.n, dtype=bool)
    blocks, dropped = horizon_blocks(h, fold, mask)
    assert blocks.shape == (2, 20)
    assert set(np.unique(h.day[blocks]).tolist()) == {1, 2}
    assert dropped == 0


def test_horizon_blocks_never_crosses_a_10_minute_gap_segment():
    h = _daily_history(n_days=1, rows_per_day=41, gap_at=(0, 20))
    fold = Fold(index=0, test_days=(0, 1), inner=((0, 0), (0, 0), (0, 0)))
    mask = np.ones(h.n, dtype=bool)
    blocks, dropped = horizon_blocks(h, fold, mask)
    assert blocks.shape == (2, 20)
    for block in blocks:
        assert len(set(h.segment[block].tolist())) == 1
    assert dropped == 1


def test_horizon_blocks_applies_the_given_mask():
    h = _daily_history(n_days=1, rows_per_day=40)
    fold = Fold(index=0, test_days=(0, 1), inner=((0, 0), (0, 0), (0, 0)))
    mask = np.ones(h.n, dtype=bool)
    mask[0] = False  # drop the first row -> only 39 eligible-for-target rows remain
    blocks, dropped = horizon_blocks(h, fold, mask)
    assert blocks.shape == (1, 20)
    assert dropped == 19
    assert 0 not in blocks


# --- updated_block_ranks: fancy indexing wrapper --------------------------------------

def test_updated_block_ranks_matches_fancy_indexing():
    ranks = np.arange(50)
    blocks = np.arange(40).reshape(2, 20)
    result = updated_block_ranks(ranks, blocks)
    assert result.shape == (2, 20)
    assert np.array_equal(result, ranks[blocks])


def test_updated_block_ranks_supports_any_target_5_columns():
    ranks5 = np.arange(50 * 5).reshape(50, 5)
    blocks = np.arange(40).reshape(2, 20)
    result = updated_block_ranks(ranks5, blocks)
    assert result.shape == (2, 20, 5)
    assert np.array_equal(result, ranks5[blocks])


# --- frozen_block_ranks: rank under the origin row's score only -----------------------

def test_frozen_block_ranks_uses_origin_row_score_for_whole_block():
    generator = protocol.rng("test-frozen")
    n = 40
    S = generator.normal(size=(n, 100))
    Y = generator.integers(0, 100, size=n)
    blocks = np.arange(n).reshape(2, 20)
    frozen = frozen_block_ranks(S, Y, blocks)
    assert frozen.shape == (2, 20)
    assert frozen.dtype in (np.uint8, np.int64, np.int32)
    origin = blocks[:, 0]
    for b in range(2):
        expected = winner_rank(np.broadcast_to(S[origin[b]], (20, 100)), Y[blocks[b]])
        assert np.array_equal(frozen[b], expected)


def test_frozen_updated_column_zero_invariant():
    generator = protocol.rng("test-frozen-invariant")
    n = 40
    S = generator.normal(size=(n, 100))
    Y = generator.integers(0, 100, size=n)
    ranks = winner_rank(S, Y)
    blocks = np.arange(n).reshape(2, 20)
    updated = updated_block_ranks(ranks, blocks)
    frozen = frozen_block_ranks(S, Y, blocks)
    assert np.array_equal(frozen[:, 0], updated[:, 0])


def test_frozen_block_ranks_ignores_non_origin_rows_of_s():
    generator = protocol.rng("test-frozen-immutable")
    n = 20
    S = generator.normal(size=(n, 100))
    Y = generator.integers(0, 100, size=n)
    blocks = np.arange(n).reshape(1, 20)
    frozen_before = frozen_block_ranks(S, Y, blocks)
    S_altered = S.copy()
    S_altered[1:] = generator.normal(size=(n - 1, 100))  # keep origin row 0 fixed
    frozen_after = frozen_block_ranks(S_altered, Y, blocks)
    assert np.array_equal(frozen_before, frozen_after)


def test_frozen_block_ranks_for_any_target_5_values():
    generator = protocol.rng("test-frozen-any")
    n = 40
    S = generator.normal(size=(n, 100))
    values = generator.integers(0, 100, size=(n, 5))
    blocks = np.arange(n).reshape(2, 20)
    frozen = frozen_block_ranks(S, values, blocks)
    assert frozen.shape == (2, 20, 5)
    origin = blocks[:, 0]
    for b in range(2):
        for p in range(5):
            expected = winner_rank(np.broadcast_to(S[origin[b]], (20, 100)), values[blocks[b], p])
            assert np.array_equal(frozen[b, :, p], expected)


# --- horizon_hits: prefix hit count and any-hit, positional and any-target -----------

@pytest.mark.parametrize("H", [1, 5, 10, 20])
def test_horizon_hits_counts_prefix_and_any_positional(H):
    block_ranks = np.full((3, 20), 99, dtype=np.uint8)
    block_ranks[0, :H] = 0
    block_ranks[2, H - 1] = 0
    count_hits, any_hit = horizon_hits(block_ranks, k=1, H=H)
    assert count_hits[0] == H
    assert any_hit[0]
    assert count_hits[1] == 0
    assert not any_hit[1]
    assert any_hit[2]


def test_horizon_hits_any_target_uses_min_over_5_ranks():
    block_ranks = np.full((1, 20, 5), 99, dtype=np.uint8)
    block_ranks[0, 3, 2] = 0  # a hit only at target index 3, one of the 5 slots
    count_hits, any_hit = horizon_hits(block_ranks, k=1, H=5)
    assert count_hits[0] == 1
    assert any_hit[0]
    count_hits2, any_hit2 = horizon_hits(block_ranks, k=1, H=3)
    assert count_hits2[0] == 0
    assert not any_hit2[0]
