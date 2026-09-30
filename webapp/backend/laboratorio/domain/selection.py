"""Number selection for one draw: rankings, weighted blends, seeded random, parity.

Every selector produces a full ordering of the 100 numbers; a strategy with
coverage ``k`` bets on the first ``k``. Orderings never read the draw they are
used for, so no future information can leak into a bet.
"""

import hashlib
from collections.abc import Mapping, Sequence

import numpy as np

NUMBERS = 100
RANDOM_ALGORITHM = "blake2b64-sort-v1"
PARITY_ALGORITHM = "legacy-markov-27-votes-v1"
BLEND_ALGORITHM = "rank-points-100-to-1-weighted-v1"
_EVEN = np.arange(0, NUMBERS, 2, dtype=np.uint8)
_ODD = np.arange(1, NUMBERS, 2, dtype=np.uint8)


def top_k(order, k):
    """The first ``k`` numbers of a full ordering, keeping ranking order."""
    if not 1 <= k <= NUMBERS:
        raise ValueError(f"coverage must be between 1 and {NUMBERS}: {k}")
    return np.asarray(order[:k], dtype=np.uint8)


def blend_order(rankings: Mapping[str, np.ndarray], weights: Mapping[str, int]):
    """Order numbers by weighted rank points; ties go to the lower number.

    In each ranking the 1st number earns 100 points and the 100th earns 1. A
    number's score is the sum of weight% x points over the blended systems.
    Points are an ordering device, not probabilities.
    """
    if set(rankings) != set(weights) or sum(weights.values()) != 100:
        raise ValueError("blend weights must cover exactly the given rankings and add to 100")
    score = np.zeros(NUMBERS, dtype=np.int64)
    points = np.arange(NUMBERS, 0, -1, dtype=np.int64)  # position 0 -> 100 points
    for system, weight in weights.items():
        ranking = np.asarray(rankings[system], dtype=np.int64)
        score[ranking] += weight * points
    # lexsort sorts by the last key first: highest score, then lowest number.
    return np.lexsort((np.arange(NUMBERS), -score)).astype(np.uint8)


def random_order(seed: int, draw_label: str):
    """Seeded ordering keyed by (seed, draw), independent of evaluation order.

    Each number gets the 64-bit BLAKE2b digest of ``"{seed}|{draw}|{number}"``;
    numbers are sorted by digest (then number). Prefixes are nested by design.
    """
    keys = [
        int.from_bytes(
            hashlib.blake2b(f"{seed}|{draw_label}|{n:02d}".encode(), digest_size=8).digest(), "big"
        )
        for n in range(NUMBERS)
    ]
    return np.asarray(sorted(range(NUMBERS), key=lambda n: (keys[n], n)), dtype=np.uint8)


def parity_numbers(vote):
    """The 50 numbers bet by the parity consensus: 0 = even, 1 = odd."""
    if vote == 0:
        return _EVEN.copy()
    if vote == 1:
        return _ODD.copy()
    raise ValueError(f"parity vote must be 0 (even) or 1 (odd): {vote}")


_EVEN_STATE, _ODD_STATE = 0, 1
_CONTEXT_WEIGHT = 0.7
_GLOBAL_WEIGHT = 1 - _CONTEXT_WEIGHT  # kept as computed, to match the legacy float math


def _pick(probs):
    """Even wins ties, mirroring ``max`` over the legacy ("Par", "Impar") dict."""
    return _EVEN_STATE if probs[0] >= probs[1] else _ODD_STATE


class _ParityModel:
    """Order-``m`` parity model from the legacy Markov notebook, prediction side only."""

    __slots__ = ("history", "order", "runs", "transitions")

    def __init__(self, order):
        self.order = order
        self.history: list[int] = []
        self.runs = [0, 0]
        self.transitions: list[dict[tuple, list[int]]] = [{} for _ in range(order + 1)]

    def global_probs(self):
        total = self.runs[0] + self.runs[1]
        if total == 0:
            return (0.5, 0.5)
        return (self.runs[0] / total, self.runs[1] / total)

    def context_probs(self, global_probs):
        """Longest known context wins; falls back to the global estimate."""
        for k in range(min(self.order, len(self.history)), 0, -1):
            counts = self.transitions[k].get(tuple(self.history[-k:]))
            if counts is not None:
                total = counts[0] + counts[1]
                if total > 0:
                    return (counts[0] / total, counts[1] / total)
        return global_probs

    def ballot(self):
        """Three votes: global, context, and the majority of three combinations."""
        g = self.global_probs()
        c = self.context_probs(g)
        global_pick, context_pick = _pick(g), _pick(c)
        weighted = _pick(
            (
                _CONTEXT_WEIGHT * c[0] + _GLOBAL_WEIGHT * g[0],
                _CONTEXT_WEIGHT * c[1] + _GLOBAL_WEIGHT * g[1],
            )
        )
        conservative = context_pick if max(c) >= max(g) else global_pick
        aggressive = context_pick if min(c) >= min(g) else global_pick
        combined = _ODD_STATE if weighted + conservative + aggressive >= 2 else _EVEN_STATE
        return global_pick, context_pick, combined

    def update(self, state):
        for k in range(1, min(self.order, len(self.history)) + 1):
            key = tuple(self.history[-k:])
            counts = self.transitions[k].get(key)
            if counts is None:
                counts = self.transitions[k][key] = [0, 0]
            counts[state] += 1
        self.history.append(state)
        if len(self.history) > self.order:
            del self.history[0]
        if len(self.history) == self.order and all(s == self.history[0] for s in self.history):
            self.runs[self.history[0]] += 1


def parity_votes(first_numbers: Sequence[int] | np.ndarray):
    """Consensus of 27 votes (orders 1-9) per draw, cast before seeing that draw.

    Returns one int8 per draw: 0 = bet even numbers, 1 = bet odd numbers. The
    vote at position ``t`` only depends on ``first_numbers[:t]``.
    """
    models = [_ParityModel(order) for order in range(1, 10)]
    votes = np.empty(len(first_numbers), dtype=np.int8)
    for t, number in enumerate(first_numbers):
        odd_votes = sum(sum(model.ballot()) for model in models)
        votes[t] = 0 if 27 - odd_votes > odd_votes else 1
        state = int(number) % 2
        for model in models:
            model.update(state)
    return votes
