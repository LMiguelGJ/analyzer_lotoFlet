"""Deterministic, declared point reduction for a saved run's balance trajectory."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrajectoryPoint:
    source_index: int
    label: str
    balance: int


def reduce_trajectory(initial_capital: int, bets: Sequence, max_points: int = 500) -> dict:
    """Return selected bet points while preserving endpoints and global extrema.

    Index zero refers to replay ``offset=0``; initial capital is a separate
    baseline (and participates in extrema/drawdown calculations), not a bet row.
    Ties choose the earliest point, with initial capital preceding all bets.
    """
    if type(initial_capital) is not int or initial_capital < 0:
        raise ValueError("initial_capital must be a non-negative integer")
    if type(max_points) is not int or not 4 <= max_points <= 2000:
        raise ValueError("max_points must be between 4 and 2000")

    total = len(bets)
    balances = [initial_capital, *(bet.balance for bet in bets)]
    min_position = min(range(len(balances)), key=lambda index: balances[index])
    max_position = max(range(len(balances)), key=lambda index: balances[index])
    minimum = {
        "balance": balances[min_position],
        "source_index": None if min_position == 0 else min_position - 1,
    }
    maximum = {
        "balance": balances[max_position],
        "source_index": None if max_position == 0 else max_position - 1,
    }

    mandatory = set()
    if total:
        mandatory.update((0, total - 1))
    if min_position:
        mandatory.add(min_position - 1)
    if max_position:
        mandatory.add(max_position - 1)

    limit = min(max_points, total)
    selected = set(range(total)) if total <= max_points else set(mandatory)
    if len(selected) > limit:
        # Four is the minimum limit; this can only happen if a future contract
        # changes the mandatory set, so fail rather than silently drop extrema.
        raise ValueError("point limit cannot preserve mandatory trajectory points")
    if total > limit:
        # Fill remaining capacity using evenly spaced source indices, then the
        # lowest remaining indices. This is stable across runs and Python versions.
        slots = limit - len(selected)
        candidates = (
            [round(index * (total - 1) / max(1, slots - 1)) for index in range(slots)]
            if slots
            else []
        )
        selected.update(candidates)
        if len(selected) < limit:
            for index in range(total):
                selected.add(index)
                if len(selected) == limit:
                    break

    points = [
        {
            "source_index": index,
            "label": bets[index].label,
            "balance": bets[index].balance,
            "replay": f"replay?offset={index}&limit=1",
        }
        for index in sorted(selected)
    ]
    return {
        "initial_capital": initial_capital,
        "total": total,
        "max_points": max_points,
        "reduction_method": "none" if len(points) == total else "minmax-even-v1",
        "minimum": minimum,
        "maximum": maximum,
        "points": points,
    }
