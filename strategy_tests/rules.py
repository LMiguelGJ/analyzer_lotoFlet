"""Prize profiles and per-number payout helpers.

``ORIGINAL70`` is the Chance Express default; ``QUINIELA80`` is a counterfactual
prize table applied to the same draws, not evidence of Rapidita outcomes.
``mode="all"`` pays every matching position; ``mode="best"`` only the highest.
A peso bet on each of several numbers is a separate wager per number.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class PrizeProfile:
    """Immutable scenario identifier and prizes for positions 1st through 5th."""

    name: str
    prizes: tuple[int, int, int, int, int]


ORIGINAL70 = PrizeProfile("original70", (70, 8, 4, 2, 1))
QUINIELA80 = PrizeProfile("quiniela80", (80, 8, 4, 2, 1))
# Legacy NumPy interface used by the original experiments; never switch its values.
PRIZES = np.array(ORIGINAL70.prizes)
# Martingale ladder from lagacy_loto/Screenshot-2025-10-26.png (pesos per number, 50 numbers).
LADDER = (1, 3, 10, 35, 123, 430, 1505, 5268, 18438, 64533)
MODES = ("all", "best")


def payout(row, bet, mode="all", profile=ORIGINAL70):
    """Pesos per peso bet; ``profile`` selects the immutable prize scenario."""
    hits = [prize for prize, value in zip(profile.prizes, row, strict=True) if value == bet]
    if not hits:
        return 0
    return sum(hits) if mode == "all" else max(hits)


def payout_matrix(nums, mode="all", profile=ORIGINAL70):
    """(N, 100) payouts per number; ``profile`` follows the optional mode."""
    rows = np.arange(len(nums))
    matrix = np.zeros((len(nums), 100), dtype=np.int64)
    if mode == "all":
        for pos in range(5):
            np.add.at(matrix, (rows, nums[:, pos]), profile.prizes[pos])
    else:
        for pos in range(4, -1, -1):  # the 1st position is written last, so it wins
            matrix[rows, nums[:, pos]] = profile.prizes[pos]
    return matrix


def expected_return(mode="all", profile=ORIGINAL70):
    """Return per peso for five independent uniform positions under ``profile``."""
    if mode == "all":
        return float(sum(profile.prizes) / 100)
    return float(sum(prize * 0.01 * 0.99 ** pos
                     for pos, prize in enumerate(profile.prizes)))


def ladder_table(ladder, numbers=50, prize=None, profile=ORIGINAL70):
    """(total invested, net on first-position win); explicit ``prize`` overrides profile.

    With ``prize=None``, use ``profile.prizes[0]`` (70 by default). Existing
    positional ``ladder_table(ladder, numbers, prize)`` calls remain supported.
    """
    first_prize = profile.prizes[0] if prize is None else prize
    table, invested = [], 0
    for stake in ladder:
        invested += numbers * stake
        table.append((invested, first_prize * stake - invested))
    return table


def first_prize_ladder(profile=QUINIELA80, rounds=10, numbers=50, target_net=10):
    """Precompute stakes recovering prior costs plus ``target_net`` on a 1st win.

    Each round stakes ``numbers * stake``. This is a deterministic scenario,
    not a safe-betting recommendation; a complete miss loses all investments.
    """
    gain_per_stake = profile.prizes[0] - numbers
    if gain_per_stake <= 0:
        raise ValueError("first prize must exceed numbers bet for recovery")
    ladder, invested = [], 0
    for _ in range(rounds):
        stake = max(1, -(-(invested + target_net) // gain_per_stake))
        ladder.append(stake)
        invested += numbers * stake
    return tuple(ladder)
