"""Pure Q80 cycle policy contract against the frozen local laboratory rules."""

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from laboratorio.domain.contracts import GameProfile, legacy_quiniela_80_profile
from laboratorio.domain.profile_staking import (
    ProfileAudazStaking,
    ProfileRecoveryLadderStaking,
    Q80LadderState,
    profile_audaz_stake,
    profile_recovery_ladder,
    q80_first_prize_ladder,
    step_q80_first_prize_cycle,
)


def profile(**changes: Any) -> GameProfile:
    values = legacy_quiniela_80_profile().model_dump(mode="python")
    values.update(profile_id="another-q80", best_rule="maximum-payout/v1")
    values.update(changes)
    if "multipliers" in changes:
        values["multipliers"] = [
            {"numerator": numerator, "denominator": denominator}
            for numerator, denominator in changes["multipliers"]
        ]
    return GameProfile.model_validate(values)


def test_profile_audaz_generalizes_q80_reference_for_coverage_one_and_fifty():
    """B-DOM-099: profile Audaz generalizes Q80 stake math across coverage."""
    p = profile()
    assert profile_audaz_stake(p, 1, 2000, 2800) == (800 + 79 - 1) // 79
    assert profile_audaz_stake(p, 50, 2000, 2800) == min((800 + 30 - 1) // 30, 2000 // 50)
    assert profile_audaz_stake(p, 50, 1000, 2000) == min((1000 + 30 - 1) // 30, 1000 // 50)
    assert profile_audaz_stake(p, 1, 200, 200) == 0


def test_profile_audaz_supports_custom_universe_positions_rational_payouts_and_grid():
    """B-DOM-100: profile Audaz supports custom universes, payouts, and stake grids."""
    p = profile(
        universe_size=37,
        positions=3,
        multipliers=[(25, 2), (7, 1), (3, 1)],
        scale=1,
        stake_increment=2,
        minimum_stake=2,
        maximum_stake=200,
        max_coverage=10,
        max_exposure=500,
    )
    # m1=12.5, k=3, goal gap=100: ceil(100/9.5) on the 2-unit grid is 12.
    assert profile_audaz_stake(p, 3, 100, 200) == 12


def test_profile_audaz_caps_by_balance_maximum_and_exposure():
    """B-DOM-101: profile Audaz respects balance, maximum-stake, and exposure caps."""
    p = profile(maximum_stake=10)
    assert profile_audaz_stake(p, 1, 2000, 2800) == 10
    exposed = profile(max_coverage=10, max_exposure=20, maximum_stake=20)
    assert profile_audaz_stake(exposed, 3, 2000, 2800) == 6
    assert profile_audaz_stake(profile(), 50, 49, 500) == 0


@pytest.mark.parametrize(
    "positions,multipliers",
    [
        (1, [(30, 1)]),
        (3, [(40, 1), (6, 1), (2, 1)]),
        (5, [(50, 1), (8, 1), (4, 1), (2, 1), (1, 1)]),
    ],
)
def test_profile_audaz_uses_configured_positions_on_non_100_universes(positions, multipliers):
    """B-DOM-100: profile Audaz uses configured positions for alternate universes."""
    p = profile(
        universe_size=23,
        positions=positions,
        multipliers=multipliers,
        max_coverage=10,
        maximum_stake=1000,
        max_exposure=10_000,
    )
    first_multiplier = multipliers[0][0]
    assert profile_audaz_stake(p, 1, 100, 200) == (100 + first_multiplier - 2) // (
        first_multiplier - 1
    )


def test_profile_audaz_rejects_nonpositive_first_hit_margin():
    """B-DOM-102: profile Audaz requires a positive first-hit margin."""
    p = profile(positions=1, multipliers=[(2, 1)])
    with pytest.raises(ValueError, match="greater than coverage"):
        profile_audaz_stake(p, 2, 100, 200)


def test_recovery_ladder_generalizes_universe_positions_rationals_and_increment_grid():
    """B-DOM-103: recovery ladder generalizes exact math over profiles and stake grids."""
    for positions, multipliers in (
        (1, [(25, 2)]),
        (3, [(40, 1), (6, 1), (2, 1)]),
        (5, [(50, 1), (8, 1), (4, 1), (2, 1), (1, 1)]),
    ):
        p = profile(
            universe_size=37,
            positions=positions,
            multipliers=multipliers,
            scale=1,
            stake_increment=2,
            minimum_stake=2,
            maximum_stake=100_000,
            max_coverage=10,
            max_exposure=1_000_000,
        )
        ladder = profile_recovery_ladder(p, 3, 10, 4)
        prior_cost = 0
        first_num, first_den = multipliers[0]
        for stake in ladder:
            assert stake % 2 == 0 and stake >= 2
            assert stake * (first_num - 3 * first_den) >= (prior_cost + 10) * first_den
            if stake > 2:
                assert (stake - 2) * (first_num - 3 * first_den) < (prior_cost + 10) * first_den
            prior_cost += 3 * stake


def test_recovery_ladder_matches_q80_reference_and_separates_original70():
    """B-DOM-104: generalized recovery matches Q80 and distinguishes Original70."""
    p = profile()
    assert profile_recovery_ladder(p, 50, 10, 10) == (1, 2, 6, 16, 42, 112, 299, 797, 2126, 5669)
    # Same formula as rules.py for the compatible Original70 prize table; its
    # historical fixed screenshot LADDER is intentionally a different preset.
    p70 = profile(
        multipliers=[(70, 1), (8, 1), (4, 1), (2, 1), (1, 1)],
        max_coverage=50,
        maximum_stake=1_000_000,
        max_exposure=1_000_000,
    )
    assert profile_recovery_ladder(p70, 50, 10, 3) == (1, 3, 11)


def test_recovery_ladder_rejects_nonpositive_margin_bad_gain_and_full_ladder_caps():
    """B-DOM-105: recovery rejects invalid parameters and caps clipping its full ladder."""
    with pytest.raises(ValueError, match="target_margin"):
        ProfileRecoveryLadderStaking(0, 10, "cycle")
    with pytest.raises(ValueError, match="rounds"):
        ProfileRecoveryLadderStaking(10, 0, "cycle")
    with pytest.raises(ValueError, match="end_mode"):
        ProfileRecoveryLadderStaking(10, 2, "terminal")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="first-position multiplier"):
        profile_recovery_ladder(profile(positions=1, multipliers=[(3, 1)]), 3, 1, 2)
    with pytest.raises(ValueError, match="maximum stake"):
        profile_recovery_ladder(profile(maximum_stake=100), 50, 10, 10)
    with pytest.raises(ValueError, match="exposure"):
        profile_recovery_ladder(profile(maximum_stake=5669, max_exposure=5669), 50, 10, 10)


def test_profile_audaz_policy_identity_is_private_and_immutable():
    """B-DOM-106: profile Audaz policy identity is private and immutable."""
    assert ProfileAudazStaking() == ProfileAudazStaking(1, "profile-audaz/v1")
    with pytest.raises(FrozenInstanceError):
        ProfileAudazStaking().__setattr__("capability", "other")


def test_exact_ten_round_q80_recovery_and_distinct_lower_coverage():
    """B-DOM-107: Q80 recovery ladder matches exact ten-round reference values."""
    # repo_ref/strategy_tests/rules.py:first_prize_ladder (lines 72-87),
    # repo_ref/quiniela_compare.py:_ladder (lines 80-82); not ORIGINAL70.LADDER.
    p = profile()
    assert p.profile_id != legacy_quiniela_80_profile().profile_id
    assert q80_first_prize_ladder(p, 50) == (1, 2, 6, 16, 42, 112, 299, 797, 2126, 5669)
    ladder = q80_first_prize_ladder(p, 20)
    invested = 0
    for amount in ladder:
        assert amount == max(1, (invested + 10 + (80 - 20) - 1) // (80 - 20))
        invested += 20 * amount
        assert 80 * amount - invested >= 10
    assert ladder[:3] == (1, 1, 1)
    assert q80_first_prize_ladder(p, 1)[:3] == (1, 1, 1)


def test_secondary_only_pays_without_resetting_and_first_position_resets():
    """B-DOM-108: secondary payout advances while first prize resets the cycle."""
    # repo_ref/quiniela_compare.py:step (lines 101-124) resets ONLY on first_hit.
    p = profile()
    initial = Q80LadderState(2000, 0)
    secondary = step_q80_first_prize_cycle(p, 50, initial, 8, False, 2800)
    assert (secondary.cost, secondary.paid, secondary.state, secondary.outcome) == (
        50,
        8,
        Q80LadderState(1958, 1),
        None,
    )
    first = step_q80_first_prize_cycle(p, 50, secondary.state, 80, True, 2800)
    assert (first.cost, first.paid, first.state, first.outcome) == (
        100,
        160,
        Q80LadderState(2018, 0),
        None,
    )
    assert initial == Q80LadderState(2000, 0)
    with pytest.raises(FrozenInstanceError):
        initial.__setattr__("balance", 0)


def test_ten_misses_cycle_in_compare_variant_not_e5_terminal_loss():
    """B-DOM-109: ten failed Q80 rungs cycle instead of terminal E5 loss."""
    # repo_ref/quiniela_compare.py:step (lines 117-123) cycles modulo ten;
    # repo_ref/strategy_tests/test_quiniela80_experiments.py E5 counts a
    # complete loss after its tenth bet instead. This is the compare variant.
    p = profile()
    state = Q80LadderState(1_000_000, 0)
    costs = []
    for _ in range(10):
        result = step_q80_first_prize_cycle(p, 50, state, 0, False, 2_000_000)
        costs.append(result.cost)
        state = result.state
    assert costs == [50, 100, 300, 800, 2100, 5600, 14950, 39850, 106300, 283450]
    assert state == Q80LadderState(546_500, 0)
    assert step_q80_first_prize_cycle(p, 50, state, 0, False, 2_000_000).cost == 50


def test_exact_funds_boundary_and_unaffordable_current_or_next_rung():
    """B-DOM-110: current/next rung funding obeys exact balance boundaries."""
    p = profile()
    exact = step_q80_first_prize_cycle(p, 50, Q80LadderState(50), 0, False, 500)
    assert (exact.cost, exact.paid, exact.state, exact.outcome) == (
        50,
        0,
        Q80LadderState(0, 1),
        "ruin",
    )
    insufficient = Q80LadderState(49)
    no_draw = step_q80_first_prize_cycle(p, 50, insufficient, 0, False, 500)
    assert (no_draw.cost, no_draw.paid, no_draw.state, no_draw.outcome) == (
        0,
        0,
        insufficient,
        "ruin",
    )
    next_unaffordable = step_q80_first_prize_cycle(p, 50, Q80LadderState(99), 0, False, 500)
    assert (next_unaffordable.cost, next_unaffordable.state, next_unaffordable.outcome) == (
        50,
        Q80LadderState(49, 1),
        "ruin",
    )
    goal = step_q80_first_prize_cycle(p, 50, Q80LadderState(50), 80, True, 80)
    assert (goal.state, goal.outcome) == (Q80LadderState(80, 0), "goal")
    already = step_q80_first_prize_cycle(p, 50, Q80LadderState(80), 0, False, 80)
    assert (already.cost, already.state, already.outcome) == (0, Q80LadderState(80), "goal")


@pytest.mark.parametrize(
    "changes, error",
    [
        ({"multipliers": [(70, 1), (8, 1), (4, 1), (2, 1), (1, 1)]}, "Q80 payouts"),
        ({"multipliers": [(160, 2), (8, 1), (4, 1), (2, 1), (1, 1)]}, "Q80 payouts"),
        ({"positions": 3, "multipliers": [(80, 1), (8, 1), (4, 1)]}, "Q80 positions"),
        ({"universe_size": 101}, "Q80 universe"),
        ({"allows_repeats": False}, "Q80 repeats"),
        ({"currency": "USD"}, "DOP"),
        ({"scale": 1}, "scale"),
        ({"stake_increment": 2, "minimum_stake": 2}, "increment"),
        ({"minimum_stake": 2}, "minimum"),
        ({"max_coverage": 20}, "coverage"),
    ],
)
def test_incompatible_profiles_or_coverage_are_rejected(changes, error):
    """B-DOM-111: Q80 cycling rejects profiles/capabilities incompatible with reference."""
    with pytest.raises(ValueError, match=error):
        q80_first_prize_ladder(profile(**changes), 50)


def test_profile_caps_reject_whole_ladder_not_clip_a_later_rung():
    """B-DOM-112: profile caps validate the entire Q80 ladder, not clipped rungs."""
    with pytest.raises(ValueError, match="maximum stake"):
        q80_first_prize_ladder(profile(maximum_stake=100), 50)
    with pytest.raises(ValueError, match="exposure"):
        q80_first_prize_ladder(profile(maximum_stake=5669, max_exposure=10_000), 50)
    with pytest.raises(ValueError, match="maximum stake"):
        q80_first_prize_ladder(profile(maximum_stake=5668), 50)
    assert q80_first_prize_ladder(profile(maximum_stake=5669, max_exposure=283450), 50)[-1] == 5669
    with pytest.raises(ValueError, match="maximum stake"):
        step_q80_first_prize_cycle(
            profile(maximum_stake=5668), 50, Q80LadderState(10_000), 0, False, 20_000
        )


@pytest.mark.parametrize("coverage", [True, 0, 80, 100, 1.0])
def test_invalid_reference_coverage_is_rejected(coverage):
    """B-DOM-113: Q80 reference coverage rejects bool, invalid, and non-integer values."""
    with pytest.raises(ValueError, match="coverage"):
        q80_first_prize_ladder(profile(), coverage)


@pytest.mark.parametrize(
    "state,unit,first,goal",
    [
        (Q80LadderState(100), True, False, 200),
        (Q80LadderState(100), -1, False, 200),
        (Q80LadderState(100), 0, 1, 200),
        (Q80LadderState(100), 0, False, 0),
    ],
)
def test_invalid_step_inputs_fail_explicitly(state, unit, first, goal):
    """B-DOM-113: cycle step validates exact state, unit, hit, and goal inputs."""
    with pytest.raises(ValueError):
        step_q80_first_prize_cycle(profile(), 50, state, unit, first, goal)


@pytest.mark.parametrize("balance, round_index", [(-1, 0), (100, 10), (True, 0)])
def test_invalid_state_fails_explicitly(balance, round_index):
    """B-DOM-113: Q80 ladder state rejects invalid balance, round, and bool values."""
    with pytest.raises(ValueError):
        Q80LadderState(balance, round_index)


def test_legacy_descriptor_has_same_q80_financial_ladder():
    """B-DOM-107: legacy descriptor shares the exact Q80 financial ladder."""
    assert q80_first_prize_ladder(legacy_quiniela_80_profile(), 50) == (
        q80_first_prize_ladder(profile(), 50)
    )


def test_forged_profile_cannot_bypass_financial_gate():
    """B-DOM-114: forged profile copies cannot bypass Q80 financial validation."""
    forged = profile().model_copy(update={"scale": 1})
    with pytest.raises(ValueError, match="scale"):
        q80_first_prize_ladder(forged, 50)
