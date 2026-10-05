"""Number selection: rankings, weighted blends, seeded random and causal parity."""

import hashlib

import numpy as np
import pytest

from laboratorio.domain.selection import (
    blend_order,
    parity_numbers,
    parity_votes,
    random_order,
    top_k,
)


def permutation(first):
    """A ranking whose leading entries are ``first`` followed by the rest ascending."""
    rest = [n for n in range(100) if n not in first]
    return np.asarray([*first, *rest], dtype=np.uint8)


def test_top_k_keeps_ranking_order_and_rejects_bad_k():
    """B-DOM-024: top_k preserves rank and rejects out-of-range k."""
    order = permutation([42, 7, 99])
    assert top_k(order, 3).tolist() == [42, 7, 99]
    for bad in (0, 101):
        with pytest.raises(ValueError):
            top_k(order, bad)


def test_blend_uses_rank_points_100_to_1_weighted_by_percent():
    """B-DOM-025: blend scores 100-to-1 rank points by component weight."""
    # transition ranks 10 first (100 pts), cold ranks 20 first (100 pts).
    rankings = {"transition": permutation([10, 20]), "cold": permutation([20, 10])}
    # 60/40: number 10 -> 60*100 + 40*99 = 9960; number 20 -> 60*99 + 40*100 = 9940.
    assert blend_order(rankings, {"transition": 60, "cold": 40})[:2].tolist() == [10, 20]
    assert blend_order(rankings, {"transition": 40, "cold": 60})[:2].tolist() == [20, 10]


def test_blend_ties_are_broken_by_ascending_number_not_by_method():
    """B-DOM-026: blend ties resolve by ascending number, independent of method order."""
    rankings = {"transition": permutation([30, 5]), "cold": permutation([5, 30])}
    # 50/50 gives 5 and 30 the same score; the lower number wins, whatever the order.
    assert blend_order(rankings, {"transition": 50, "cold": 50})[:2].tolist() == [5, 30]
    assert blend_order(rankings, {"cold": 50, "transition": 50})[:2].tolist() == [5, 30]


def test_blend_is_a_full_permutation():
    """B-DOM-027: blend produces a full permutation."""
    rng = np.random.default_rng(3)
    rankings = {name: rng.permutation(100).astype(np.uint8) for name in ("a", "b", "c")}
    order = blend_order(rankings, {"a": 20, "b": 30, "c": 50})
    assert sorted(order.tolist()) == list(range(100))


def test_blend_rejects_weights_that_do_not_match_rankings():
    """B-DOM-027: blend rejects invalid totals and ranking/weight key mismatch."""
    rankings = {"transition": permutation([1]), "cold": permutation([2])}
    with pytest.raises(ValueError):
        blend_order(rankings, {"transition": 60, "cold": 30})
    with pytest.raises(ValueError):
        blend_order(rankings, {"transition": 60, "time": 40})


def test_random_order_is_reproducible_nested_and_keyed_by_seed_and_draw():
    """B-DOM-028: seeded draw order is reproducible, nested, and key-bound."""
    first = random_order(7, "2025-09-02 05:10")
    assert sorted(first.tolist()) == list(range(100))
    assert np.array_equal(first, random_order(7, "2025-09-02 05:10"))
    # Coverage 5 is always the prefix of coverage 10 for the same draw.
    assert top_k(first, 10)[:5].tolist() == top_k(first, 5).tolist()
    assert not np.array_equal(first, random_order(8, "2025-09-02 05:10"))
    assert not np.array_equal(first, random_order(7, "2025-09-02 05:15"))


def test_random_order_does_not_depend_on_call_order():
    """B-DOM-029: seeded orders are independent of evaluation order."""
    labels = [f"2025-09-02 05:{m:02d}" for m in range(10, 60, 5)]
    forward = [random_order(11, label).tolist() for label in labels]
    backward = [random_order(11, label).tolist() for label in reversed(labels)]
    assert forward == backward[::-1]


def test_random_order_is_stable_across_releases():
    """B-DOM-030: seeded order retains its cross-release fingerprint."""
    # Frozen fingerprint of the documented algorithm (BLAKE2b-64 keys, ascending).
    digest = hashlib.sha256(random_order(20260928, "2025-09-02 05:10").tobytes()).hexdigest()
    assert random_order(20260928, "2025-09-02 05:10")[:5].tolist() == RANDOM_PREFIX
    assert digest == RANDOM_SHA


# Pinned once from the implementation; a change here means reproducibility broke.
RANDOM_PREFIX = [32, 12, 46, 74, 17]
RANDOM_SHA = "4c40b250ead564694479f36b2c1d800cc7c919e51869cf27bc518b5daabd8bb5"


def test_parity_numbers_are_the_50_even_or_odd_numbers():
    """B-DOM-031: parity selector returns exactly the even or odd half."""
    assert parity_numbers(0).tolist() == list(range(0, 100, 2))
    assert parity_numbers(1).tolist() == list(range(1, 100, 2))
    with pytest.raises(ValueError):
        parity_numbers(2)


def test_parity_first_vote_without_history_is_even():
    """B-DOM-031: first causal parity vote defaults to even."""
    assert parity_votes([37]).tolist() == [0]


def test_parity_votes_are_causal():
    """B-DOM-031: future draws cannot change earlier parity votes."""
    rng = np.random.default_rng(5)
    base = rng.integers(0, 100, size=400)
    votes = parity_votes(base)
    for cut in (1, 57, 250):
        changed = base.copy()
        changed[cut:] = (changed[cut:] + 1) % 100  # flip every parity from ``cut`` on
        # The vote for draw ``cut`` is cast before that draw is observed.
        assert np.array_equal(parity_votes(changed)[: cut + 1], votes[: cut + 1])


def test_parity_votes_follow_a_long_even_streak():
    """B-DOM-031: parity vote follows an extended even streak."""
    votes = parity_votes([2] * 60)
    assert votes[-1] == 0


def test_parity_votes_follow_a_long_odd_streak():
    """B-DOM-031: parity vote follows an extended odd streak."""
    votes = parity_votes([3] * 60)
    assert votes[-1] == 1
