from types import SimpleNamespace

import pytest

from laboratorio.domain.trajectory import reduce_trajectory


def bets(balances):
    return tuple(
        SimpleNamespace(label=f"draw-{index}", balance=value)
        for index, value in enumerate(balances)
    )


def test_empty_and_short_trajectories_are_not_fabricated():
    assert reduce_trajectory(10, (), 4) == {
        "initial_capital": 10,
        "total": 0,
        "max_points": 4,
        "reduction_method": "none",
        "minimum": {"balance": 10, "source_index": None},
        "maximum": {"balance": 10, "source_index": None},
        "points": [],
    }
    short = reduce_trajectory(10, bets([9, 11]), 4)
    assert [point["source_index"] for point in short["points"]] == [0, 1]
    assert short["reduction_method"] == "none"
    full = reduce_trajectory(10, bets([10, 9, 11, 10, 10]), 500)
    assert [point["source_index"] for point in full["points"]] == list(range(5))
    assert full["reduction_method"] == "none"


def test_reduction_keeps_endpoints_extrema_earliest_ties_and_replay_indices():
    result = reduce_trajectory(10, bets([8, 3, 3, 15, 9, 15, 11]), 4)
    points = result["points"]
    assert [point["source_index"] for point in points] == sorted(
        point["source_index"] for point in points
    )
    assert {point["source_index"] for point in points} == {0, 1, 3, 6}
    assert result["minimum"] == {"balance": 3, "source_index": 1}
    assert result["maximum"] == {"balance": 15, "source_index": 3}
    assert points[1]["replay"] == "replay?offset=1&limit=1"
    assert result["total"] == 7
    assert result["reduction_method"] == "minmax-even-v1"


def test_initial_capital_participates_in_extrema_with_earliest_tie():
    result = reduce_trajectory(10, bets([10, 12, 8]), 4)
    assert result["minimum"] == {"balance": 8, "source_index": 2}
    assert result["maximum"] == {"balance": 12, "source_index": 1}
    initial_tie = reduce_trajectory(10, bets([10]), 4)
    assert initial_tie["minimum"] == {"balance": 10, "source_index": None}


@pytest.mark.parametrize("limit", [3, 2001, True])
def test_point_limit_is_explicitly_bounded(limit):
    with pytest.raises(ValueError):
        reduce_trajectory(10, (), limit)
