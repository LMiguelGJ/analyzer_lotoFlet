from collections.abc import Mapping, MutableMapping
from operator import setitem
from typing import cast

import pytest

from laboratorio.domain.configurable_runs import QuinielaBet, QuinielaDraw, RunWindow
from laboratorio.domain.contracts import MAX_MONEY

PROFILE_SHA = "a" * 64
STRATEGY_SHA = "b" * 64
RULES = {
    "profile_sha256": PROFILE_SHA,
    "strategy_sha256": STRATEGY_SHA,
    "engine_version": "replay/v2",
}


def test_draw_round_trip_is_strict_immutable_and_preserves_repeated_results():
    source = {
        "schema_version": 2,
        "draw_id": "  draw-1  ",
        "timestamp": "2025-03-04T05:06:07Z",
        "results": [0, 7, 7],
    }
    draw = QuinielaDraw.from_mapping(source)

    assert draw.to_mapping() == {
        "schema_version": 2,
        "draw_id": "draw-1",
        "timestamp": "2025-03-04T05:06:07Z",
        "results": [0, 7, 7],
    }
    assert source["draw_id"] == "  draw-1  "
    assert isinstance(draw.results, tuple)
    original_results = draw.results
    with pytest.raises((AttributeError, TypeError)):
        draw.__setattr__("results", (*original_results, 8))
    assert draw.results == original_results
    assert QuinielaDraw.from_mapping(draw.to_mapping()) == draw


@pytest.mark.parametrize(
    "patch",
    [
        {"schema_version": True},
        {"schema_version": 1},
        {"draw_id": "   "},
        {"draw_id": "x" * 121},
        {"timestamp": "2025-03-04T05:06:07+00:00"},
        {"timestamp": "2025-02-30T05:06:07Z"},
        {"timestamp": "2025-03-04T05:06:07.000Z"},
        {"results": []},
        {"results": [1] * 17},
        {"results": [1.0]},
        {"results": [True]},
        {"results": [-1]},
        {"results": [2**53]},
        {"unexpected": 1},
    ],
)
def test_draw_rejects_invalid_and_extra_values(patch):
    mapping = {
        "schema_version": 2,
        "draw_id": "draw-1",
        "timestamp": "2025-03-04T05:06:07Z",
        "results": [1],
    }
    mapping.update(patch)

    with pytest.raises((TypeError, ValueError)):
        QuinielaDraw.from_mapping(mapping)


def test_window_round_trip_and_inclusive_order_boundary():
    window = RunWindow.from_mapping(
        {"schema_version": 2, "start": "2025-03-04T05:06:07Z", "end": "2025-03-04T05:06:07Z"}
    )

    assert window.to_mapping() == {
        "schema_version": 2,
        "start": "2025-03-04T05:06:07Z",
        "end": "2025-03-04T05:06:07Z",
    }
    assert RunWindow.from_mapping(window.to_mapping()) == window


@pytest.mark.parametrize(
    "mapping",
    [
        {"schema_version": 2, "start": "2025-03-04T05:06:08Z", "end": "2025-03-04T05:06:07Z"},
        {"schema_version": 2, "start": "2025-03-04T05:06:07+00:00", "end": "2025-03-04T05:06:07Z"},
        {
            "schema_version": 2,
            "start": "2025-03-04T05:06:07Z",
            "end": "2025-03-04T05:06:07Z",
            "extra": 1,
        },
        {"schema_version": 2, "start": "2025-03-04T05:06:07Z"},
        {"schema_version": False, "start": "2025-03-04T05:06:07Z", "end": "2025-03-04T05:06:07Z"},
    ],
)
def test_window_rejects_invalid_mappings(mapping):
    with pytest.raises((TypeError, ValueError)):
        RunWindow.from_mapping(mapping)


def test_bet_round_trip_reconciles_money_and_copies_rules_immutably():
    source = {
        "schema_version": 2,
        "ordinal": 0,
        "session_ordinal": 0,
        "draw_ordinal": 0,
        "draw_id": " draw-1 ",
        "timestamp": "2025-03-04T05:06:07Z",
        "numbers": [2, 8],
        "per_number": 3,
        "wagered": 6,
        "results": [8, 8],
        "paid": MAX_MONEY,
        "balance_before": 6,
        "balance_after": MAX_MONEY,
        "rules_used": dict(RULES),
    }
    bet = QuinielaBet.from_mapping(source)

    assert bet.to_mapping() == source | {"draw_id": "draw-1"}
    assert source["draw_id"] == " draw-1 "
    assert bet.numbers == (2, 8)
    assert bet.results == (8, 8)
    assert isinstance(bet.rules_used, Mapping)
    original_rules = dict(bet.rules_used)
    # The cast deliberately attempts a forbidden write; MappingProxyType rejects it at runtime.
    writable_view = cast(MutableMapping[str, str], bet.rules_used)
    with pytest.raises(TypeError):
        setitem(writable_view, "engine_version", "changed")
    assert dict(bet.rules_used) == original_rules
    original_numbers = bet.numbers
    with pytest.raises((AttributeError, TypeError)):
        bet.__setattr__("numbers", (*original_numbers, 9))
    assert bet.numbers == original_numbers
    assert QuinielaBet.from_mapping(bet.to_mapping()) == bet


def _valid_bet_mapping():
    return {
        "schema_version": 2,
        "ordinal": 0,
        "session_ordinal": 0,
        "draw_ordinal": 0,
        "draw_id": "draw-1",
        "timestamp": "2025-03-04T05:06:07Z",
        "numbers": [2, 8],
        "per_number": 3,
        "wagered": 6,
        "results": [8],
        "paid": 9,
        "balance_before": 10,
        "balance_after": 13,
        "rules_used": dict(RULES),
    }


@pytest.mark.parametrize(
    "patch",
    [
        {"schema_version": 1},
        {"ordinal": True},
        {"session_ordinal": -1},
        {"draw_ordinal": 2**53},
        {"draw_id": " "},
        {"timestamp": "2025-03-04T05:06:07+00:00"},
        {"numbers": []},
        {"numbers": [2, 2]},
        {"numbers": [True]},
        {"numbers": [1.5]},
        {"numbers": [2**53]},
        {"numbers": [1] * 1001},
        {"per_number": 0},
        {"per_number": MAX_MONEY + 1},
        {"wagered": 5},
        {"wagered": MAX_MONEY + 1},
        {"results": []},
        {"results": [1] * 17},
        {"results": [True]},
        {"paid": -1},
        {"paid": MAX_MONEY + 1},
        {"balance_before": 5},
        {"balance_before": MAX_MONEY + 1},
        {"balance_after": MAX_MONEY + 1},
        {"balance_after": 14},
        {"rules_used": {**RULES, "profile_sha256": "A" * 64}},
        {"rules_used": {**RULES, "strategy_sha256": "short"}},
        {"rules_used": {**RULES, "engine_version": " "}},
        {"rules_used": {**RULES, "other": "x"}},
        {"rules_used": {"profile_sha256": PROFILE_SHA}},
        {"unexpected": "x"},
    ],
)
def test_bet_rejects_invalid_mappings_without_mutating_input(patch):
    mapping = _valid_bet_mapping()
    mapping.update(patch)
    before = repr(mapping)

    with pytest.raises((TypeError, ValueError)):
        QuinielaBet.from_mapping(mapping)

    assert repr(mapping) == before


def test_bet_rejects_money_overflow_and_non_integral_types():
    for patch in (
        {"per_number": True},
        {"wagered": 6.0},
        {"paid": "9"},
        {"balance_after": True},
        {"rules_used": {**RULES, "engine_version": "x" * 81}},
    ):
        mapping = _valid_bet_mapping()
        mapping.update(patch)
        with pytest.raises((TypeError, ValueError)):
            QuinielaBet.from_mapping(mapping)
