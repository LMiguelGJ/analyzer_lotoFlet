"""Independent, hand-computed per-draw fixtures for the inert profile engine."""

from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from laboratorio.domain.contracts import (
    MAX_MONEY,
    GameProfile,
    PayoutMultiplier,
    SettlementMode,
    legacy_quiniela_80_profile,
)
from laboratorio.domain.profile_engine import ProfilePayout, settle_profile_bet


def profile(**changes):
    data = {
        "schema_version": 1,
        "profile_id": "example-three",
        "revision": 1,
        "universe_size": 100,
        "positions": 3,
        "allows_repeats": True,
        "multipliers": [{"numerator": prize, "denominator": 1} for prize in (60, 10, 5)],
        "currency": "DOP",
        "scale": 0,
        "stake_increment": 1,
        "minimum_stake": 1,
        "maximum_stake": 100,
        "max_coverage": 10,
        "max_exposure": 1_000,
        "best_rule": "maximum-payout/v1",
    }
    data.update(changes)
    return GameProfile.model_validate(data)


def settle(p, results, stakes, mode=SettlementMode.ALL, **limits):
    return settle_profile_bet(p, results, stakes, mode, **limits)


@pytest.mark.parametrize(
    ("results", "stakes", "expected"),
    [
        ((7, 8, 9), {7: 1}, (1, 60, 59)),
        ((7, 8, 9), {9: 1}, (1, 5, 4)),
        ((7, 8, 9), {8: 2}, (2, 20, 18)),
        ((7, 8, 9), {10: 1}, (1, 0, -1)),
        ((7, 8, 9), {7: 2, 8: 3, 9: 1}, (6, 155, 149)),
    ],
)
def test_example_three_position_payouts_in_integer_units(results, stakes, expected):
    """B-DOM-125: three-position profile payouts use exact integer units."""
    assert settle(profile(), results, stakes) == ProfilePayout(*expected)


def test_repeats_all_sum_each_position_best_only_once_per_number():
    """B-DOM-126: ALL pays each repeated position; BEST pays each number once."""
    p = profile()
    assert settle(p, (7, 7, 8), {7: 2, 8: 3}) == ProfilePayout(5, 155, 150)
    assert settle(p, (7, 7, 8), {7: 2, 8: 3}, SettlementMode.BEST) == ProfilePayout(5, 135, 130)
    assert settle(p, (7, 7, 7), {7: 1}, SettlementMode.BEST) == ProfilePayout(1, 60, 59)


def test_new_best_uses_maximum_not_first_even_with_nonmonotonic_payout():
    """B-DOM-127: maximum-payout selects maximum multiplier, not first match."""
    p = profile(multipliers=[{"numerator": n, "denominator": 1} for n in (1, 9, 2)])
    assert settle(p, (7, 7, 7), {7: 2}) == ProfilePayout(2, 24, 22)
    assert settle(p, (7, 7, 7), {7: 2}, SettlementMode.BEST) == ProfilePayout(2, 18, 16)


def test_reserved_legacy_best_preserves_first_match_not_maximum():
    """B-DOM-128: reserved legacy best rule keeps first-match semantics."""
    p = legacy_quiniela_80_profile()
    assert settle(p, (7, 7, 8, 7, 8), {7: 1, 8: 1}) == ProfilePayout(2, 95, 93)
    assert settle(p, (7, 7, 8, 7, 8), {7: 1, 8: 1}, SettlementMode.BEST) == ProfilePayout(2, 84, 82)
    assert p.best_rule == "first-match/v0"


def test_scaled_rational_payout_is_exact_and_zero_prize_has_no_refund():
    """B-DOM-129: scaled rational payouts are exact and zero prizes do not refund."""
    p = profile(
        scale=2,
        stake_increment=2,
        minimum_stake=2,
        maximum_stake=100,
        multipliers=[
            {"numerator": 3, "denominator": 2},
            {"numerator": 0, "denominator": 1},
            {"numerator": 1, "denominator": 2},
        ],
    )
    assert settle(p, (1, 2, 3), {1: 4, 2: 2, 3: 6}) == ProfilePayout(12, 9, -3)
    assert settle(p, (1, 2, 3), {2: 2}) == ProfilePayout(2, 0, -2)


def test_one_and_five_position_profiles_and_no_repeat_policy():
    """B-DOM-130: engine supports one/five positions and enforces no-repeat profiles."""
    one = profile(positions=1, multipliers=[{"numerator": 3, "denominator": 1}])
    assert settle(one, (7,), {7: 2}) == ProfilePayout(2, 6, 4)
    five = profile(
        positions=5,
        allows_repeats=False,
        multipliers=[{"numerator": n, "denominator": 1} for n in (5, 4, 3, 2, 1)],
    )
    assert settle(five, (0, 1, 2, 3, 4), {2: 1, 4: 2}, SettlementMode.BEST) == (
        ProfilePayout(3, 5, 2)
    )
    with pytest.raises(ValueError, match="repeat"):
        settle(five, (0, 0, 2, 3, 4), {0: 1})


def test_full_cost_must_fit_exposure_budget_and_available_capital():
    """B-DOM-131: full stake cost fits exposure, budget, and available capital."""
    p = profile(max_exposure=10, maximum_stake=10)
    assert settle(p, (1, 2, 3), {1: 6, 2: 4}, budget=10, capital=10).cost == 10
    with pytest.raises(ValueError, match="total stake exceeds budget"):
        settle(p, (1, 2, 3), {1: 6, 2: 4}, budget=9)
    with pytest.raises(ValueError, match="total stake exceeds capital"):
        settle(p, (1, 2, 3), {1: 6, 2: 4}, capital=9)
    with pytest.raises(ValueError, match="exposure"):
        settle(p, (1, 2, 3), {1: 6, 2: 5})
    for bad in (True, 10.0, "10", -1, MAX_MONEY + 1):
        with pytest.raises(ValueError, match="budget"):
            settle(p, (1, 2, 3), {1: 1}, budget=bad)


@pytest.mark.parametrize(
    ("results", "stakes", "mode"),
    [
        ((1, 2), {1: 1}, SettlementMode.ALL),
        ((1, 2, 3, 4), {1: 1}, SettlementMode.ALL),
        ((1, True, 3), {1: 1}, SettlementMode.ALL),
        ((1, 2.0, 3), {1: 1}, SettlementMode.ALL),
        ((-1, 2, 3), {1: 1}, SettlementMode.ALL),
        ((100, 2, 3), {1: 1}, SettlementMode.ALL),
        ((1, 2, 3), {}, SettlementMode.ALL),
        ((1, 2, 3), {True: 1}, SettlementMode.ALL),
        ((1, 2, 3), {100: 1}, SettlementMode.ALL),
        ((1, 2, 3), {1: False}, SettlementMode.ALL),
        ((1, 2, 3), {1: 1.0}, SettlementMode.ALL),
        ((1, 2, 3), {1: 0}, SettlementMode.ALL),
        ((1, 2, 3), {1: 101}, SettlementMode.ALL),
        ((1, 2, 3), {1: 1}, "all"),
        ((1, 2, 3), {1: 1}, None),
    ],
)
def test_rejects_malformed_draw_stakes_or_implicit_settlement(results, stakes, mode):
    """B-DOM-132: engine rejects malformed draws/stakes and implicit settlement."""
    with pytest.raises(ValueError):
        settle(profile(), results, stakes, mode)


def test_coverage_increment_and_input_mapping_enforced():
    """B-DOM-133: engine enforces coverage, stake increments, and mapping input."""
    p = profile(max_coverage=2, stake_increment=2, minimum_stake=2)
    with pytest.raises(ValueError, match="coverage"):
        settle(p, (1, 2, 3), {1: 2, 2: 2, 3: 2})
    with pytest.raises(ValueError, match="increment"):
        settle(p, (1, 2, 3), {1: 3})
    with pytest.raises(TypeError, match="map"):
        settle(p, (1, 2, 3), [(1, 2), (1, 2)])


def test_model_copy_cannot_bypass_profile_validation():
    """B-DOM-134: model_copy cannot bypass profile validation at settlement."""
    p = profile()
    malformed = (
        p.model_copy(update={"positions": 4}),
        p.model_copy(update={"best_rule": "first-match/v0"}),
        p.model_copy(
            update={
                "multipliers": (
                    PayoutMultiplier.model_construct(numerator=1, denominator=0),
                    *p.multipliers[1:],
                )
            }
        ),
        p.model_copy(
            update={
                "multipliers": (PayoutMultiplier(numerator=1, denominator=2), *p.multipliers[1:])
            }
        ),
        p.model_copy(update={"max_exposure": 1}),
    )
    for invalid in malformed:
        with pytest.raises(ValidationError):
            settle(invalid, (1, 2, 3), {1: 1})


def test_payout_result_is_frozen():
    """B-DOM-135: profile payout result is immutable."""
    outcome = settle(profile(), (1, 2, 3), {1: 1})
    with pytest.raises(FrozenInstanceError):
        outcome.__setattr__("paid", 0)
