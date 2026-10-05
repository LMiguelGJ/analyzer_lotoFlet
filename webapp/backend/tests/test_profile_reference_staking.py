import pytest

from laboratorio.domain.contracts import legacy_quiniela_80_profile
from laboratorio.domain.profile_staking import (
    ProfileAudazStaking,
    Q80ReferenceAudazStaking,
    Q80ReferenceAudazState,
    q80_reference_audaz_stake,
    step_q80_reference_audaz,
)


def test_reference_audaz_identity_is_distinct_from_profile_audaz():
    """B-DOM-115: reference Audaz capability is distinct from profile Audaz."""
    assert Q80ReferenceAudazStaking().capability == "transition-1-audaz-reference/v1"
    assert Q80ReferenceAudazStaking().capability != ProfileAudazStaking().capability


def test_reference_audaz_uses_ceiling_over_79_and_balance_cap():
    """B-DOM-116: reference Audaz uses ceiling division and balance cap."""
    assert q80_reference_audaz_stake(2000, 2800) == 11
    assert q80_reference_audaz_stake(1, 2800) == 1
    assert q80_reference_audaz_stake(100, 101) == 1


def test_reference_audaz_initial_zero_is_quiebre_not_goal():
    """B-DOM-117: zero initial balance is quiebre, not goal."""
    assert q80_reference_audaz_stake(0, 2800) == 0
    result = step_q80_reference_audaz(
        legacy_quiniela_80_profile(), Q80ReferenceAudazState(0), 1, 0, 2800
    )
    assert result.outcome == "quiebre"
    assert result.state.balance == 0


def test_reference_audaz_steps_exact_money_and_recomputes_without_goal_outcome():
    """B-DOM-118: reference Audaz settles exact money and recomputes without goal outcome."""
    profile = legacy_quiniela_80_profile()
    state = Q80ReferenceAudazState(2000)
    result = step_q80_reference_audaz(profile, state, 1, 80, 2800)
    assert (result.cost, result.paid, result.state.balance, result.next_stake) == (11, 880, 2869, 0)
    assert result.reset is True
    assert result.outcome is None


def test_reference_audaz_checks_increment_and_exposure_not_generic_audaz_clipping():
    """B-DOM-119: reference Audaz enforces increment and exposure without generic clipping."""
    profile = legacy_quiniela_80_profile().model_copy(
        update={"maximum_stake": 100, "max_coverage": 1, "max_exposure": 10}
    )
    with pytest.raises(ValueError, match="exposure"):
        q80_reference_audaz_stake(2000, 2800, profile=profile)
    assert q80_reference_audaz_stake(10, 100_000) == 10
    with pytest.raises(ValueError, match="exact integer"):
        q80_reference_audaz_stake(True, 2800)


def test_reference_audaz_secondary_payment_does_not_reset_and_reports_cap():
    """B-DOM-120: secondary payout preserves cycle and capped stake reports quiebre."""
    profile = legacy_quiniela_80_profile()
    result = step_q80_reference_audaz(profile, Q80ReferenceAudazState(2000), 1, 8, 2800)
    assert (result.cost, result.paid, result.state.balance, result.next_stake) == (11, 88, 2077, 10)
    assert result.reset is False
    assert result.outcome is None
    capped = step_q80_reference_audaz(profile, Q80ReferenceAudazState(10), 1, 0, 100_000)
    assert (capped.cost, capped.next_stake, capped.capped, capped.outcome) == (
        10,
        0,
        True,
        "quiebre",
    )
