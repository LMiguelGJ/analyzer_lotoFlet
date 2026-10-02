"""Pure Q80 first-prize recovery ladder; not an admitted profile capability.

This is the cycling session variant in repo_ref/quiniela_compare.py:_ladder,
_per_number, _next_unaffordable, step (lines 80-124), also used by
repo_ref/quiniela_sim.py:step (lines 211-230) at coverage 50. In contrast,
strategy_tests/experiments.py E5 closes a complete loss after ten bets; it is
not this policy. The original 70-prize screenshot LADDER is not Q80.
"""

from dataclasses import dataclass
from typing import Literal

from laboratorio.domain.contracts import MAX_MONEY, GameProfile

_ROUNDS = 10
_MARGIN = 10
_PRIZES = (80, 8, 4, 2, 1)
MAX_RECOVERY_ROUNDS = 10_000  # One possible rung per admitted session row.


@dataclass(frozen=True, slots=True)
class ProfileAudazStaking:
    """Private profile-generic goal-seeking stake policy; not a wire capability."""

    schema_version: int = 1
    capability: str = "profile-audaz/v1"

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported profile audaz staking version")
        if type(self.capability) is not str or self.capability != "profile-audaz/v1":
            raise ValueError("unsupported profile audaz staking policy")


def profile_audaz_stake(profile: GameProfile, coverage: int, balance: int, goal: int) -> int:
    """Choose an increment-aligned stake using only first-position net gain.

    The exact conservative gain per unit stake is ``m1 - coverage``. The result
    is rounded upward to the profile increment to target the gap, then bounded by
    available balance and the profile's stake/exposure limits. Zero means no
    admissible minimum stake can be financed (or the goal is already reached).
    """
    if type(profile) is not GameProfile:
        raise TypeError("profile must be a GameProfile")
    profile = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
    if type(coverage) is not int or not 1 <= coverage <= profile.max_coverage:
        raise ValueError("coverage exceeds profile limit")
    if type(balance) is not int or not 0 <= balance <= MAX_MONEY:
        raise ValueError("balance must be an exact bounded integer")
    if type(goal) is not int or not 1 <= goal <= MAX_MONEY:
        raise ValueError("goal must be an exact positive bounded integer")

    first = profile.multipliers[0]
    gain_numerator = first.numerator - coverage * first.denominator
    if gain_numerator <= 0:
        raise ValueError("profile audaz requires first-position multiplier greater than coverage")
    if balance >= goal:
        return 0

    gap = goal - balance
    required_numerator = gap * first.denominator
    required_increment_count = (
        required_numerator + gain_numerator * profile.stake_increment - 1
    ) // (gain_numerator * profile.stake_increment)
    required = max(
        profile.minimum_stake,
        required_increment_count * profile.stake_increment,
    )
    max_affordable = min(
        balance // coverage,
        profile.maximum_stake,
        profile.max_exposure // coverage,
    )
    max_affordable -= max_affordable % profile.stake_increment
    if max_affordable < profile.minimum_stake:
        return 0
    return min(required, max_affordable)


@dataclass(frozen=True, slots=True)
class ProfileRecoveryLadderStaking:
    """Private generic recovery ladder; every financial/horizon parameter is explicit."""

    target_margin: int
    rounds: int
    end_mode: Literal["cycle", "stop"]

    def __post_init__(self) -> None:
        if type(self.target_margin) is not int or not 1 <= self.target_margin <= MAX_MONEY:
            raise ValueError("target_margin must be a positive bounded profile-money integer")
        if type(self.rounds) is not int or not 1 <= self.rounds <= MAX_RECOVERY_ROUNDS:
            raise ValueError(f"rounds must be an integer from 1 to {MAX_RECOVERY_ROUNDS}")
        if self.end_mode not in ("cycle", "stop") or type(self.end_mode) is not str:
            raise ValueError("end_mode must explicitly be cycle or stop")


def profile_recovery_ladder(
    profile: GameProfile, coverage: int, target_margin: int, rounds: int
) -> tuple[int, ...]:
    """Build all validated rungs using exact rational first-position recovery.

    For each rung choose the smallest stake on the profile increment grid such
    that stake * (first_multiplier - coverage) covers prior *wagered costs* plus
    target_margin. Payouts from earlier rounds do not reduce that accumulated cost.
    """
    if type(profile) is not GameProfile:
        raise TypeError("profile must be a GameProfile")
    profile = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
    if type(coverage) is not int or not 1 <= coverage <= min(
        profile.max_coverage, profile.universe_size
    ):
        raise ValueError("coverage exceeds profile or universe limit")
    if type(target_margin) is not int or not 1 <= target_margin <= MAX_MONEY:
        raise ValueError("target_margin must be a positive bounded profile-money integer")
    if type(rounds) is not int or not 1 <= rounds <= MAX_RECOVERY_ROUNDS:
        raise ValueError(f"rounds must be an integer from 1 to {MAX_RECOVERY_ROUNDS}")

    first = profile.multipliers[0]
    gain_numerator = first.numerator - coverage * first.denominator
    if gain_numerator <= 0:
        raise ValueError("first-position multiplier must exceed coverage")

    accumulated_cost = 0
    ladder: list[int] = []
    increment = profile.stake_increment
    for _ in range(rounds):
        required_numerator = (accumulated_cost + target_margin) * first.denominator
        denominator = gain_numerator * increment
        stake = max(
            profile.minimum_stake,
            ((required_numerator + denominator - 1) // denominator) * increment,
        )
        if stake > profile.maximum_stake:
            raise ValueError("recovery ladder exceeds profile maximum stake")
        cost = coverage * stake
        if cost > profile.max_exposure or cost > MAX_MONEY:
            raise ValueError("recovery ladder exceeds profile exposure")
        accumulated_cost += cost
        if accumulated_cost > MAX_MONEY:
            raise ValueError("recovery ladder exceeds safe accumulated money ceiling")
        ladder.append(stake)
    return tuple(ladder)


@dataclass(frozen=True, slots=True)
class ProfileRecoveryState:
    balance: int
    round_index: int = 0

    def __post_init__(self) -> None:
        if type(self.balance) is not int or not 0 <= self.balance <= MAX_MONEY:
            raise ValueError("balance must be an exact bounded integer")
        if type(self.round_index) is not int or self.round_index < 0:
            raise ValueError("round_index must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ProfileRecoveryStep:
    cost: int
    paid: int
    state: ProfileRecoveryState
    outcome: Literal["goal", "ruin", "round_limit"] | None


def step_profile_recovery(
    ladder: tuple[int, ...],
    coverage: int,
    state: ProfileRecoveryState,
    paid: int,
    first_hit: bool,
    goal: int,
    end_mode: Literal["cycle", "stop"],
) -> ProfileRecoveryStep:
    """Advance after authoritative settlement; first-position wins alone reset."""
    if type(ladder) is not tuple or not ladder or len(ladder) > MAX_RECOVERY_ROUNDS:
        raise ValueError("ladder must be a non-empty bounded tuple")
    if any(type(stake) is not int or stake < 1 for stake in ladder):
        raise ValueError("ladder stakes must be positive exact integers")
    if type(coverage) is not int or coverage < 1:
        raise ValueError("coverage must be a positive integer")
    if type(state) is not ProfileRecoveryState:
        raise TypeError("state must be a ProfileRecoveryState")
    state.__post_init__()
    if state.round_index >= len(ladder):
        raise ValueError("round_index exceeds configured recovery ladder")
    if type(paid) is not int or not 0 <= paid <= MAX_MONEY:
        raise ValueError("paid must be a bounded exact integer")
    if type(first_hit) is not bool:
        raise ValueError("first_hit must be an explicit bool")
    if type(goal) is not int or not 1 <= goal <= MAX_MONEY:
        raise ValueError("goal must be an exact positive bounded integer")
    if type(end_mode) is not str or end_mode not in ("cycle", "stop"):
        raise ValueError("end_mode must explicitly be cycle or stop")
    if state.balance >= goal:
        return ProfileRecoveryStep(0, 0, state, "goal")
    cost = coverage * ladder[state.round_index]
    if cost > MAX_MONEY:
        raise ValueError("recovery bet exceeds safe money ceiling")
    if state.balance < cost:
        return ProfileRecoveryStep(0, 0, state, "ruin")
    balance = state.balance + paid - cost
    if balance < 0 or balance > MAX_MONEY:
        raise ValueError("recovery settlement exceeds safe money ceiling")
    if first_hit:
        next_round = 0
        limit_reached = False
    elif state.round_index + 1 == len(ladder):
        limit_reached = end_mode == "stop"
        next_round = 0 if end_mode == "cycle" else state.round_index
    else:
        limit_reached = False
        next_round = state.round_index + 1
    next_state = ProfileRecoveryState(balance, next_round)
    outcome = (
        "goal"
        if balance >= goal
        else "ruin"
        if balance < coverage * ladder[next_round]
        else "round_limit"
        if limit_reached
        else None
    )
    return ProfileRecoveryStep(cost, paid, next_state, outcome)


@dataclass(frozen=True, slots=True)
class Q80LadderState:
    balance: int
    round_index: int = 0

    def __post_init__(self) -> None:
        if type(self.balance) is not int or not 0 <= self.balance <= MAX_MONEY:
            raise ValueError("balance must be an exact bounded integer")
        if type(self.round_index) is not int or not 0 <= self.round_index < _ROUNDS:
            raise ValueError("round_index must be an integer from 0 to 9")


@dataclass(frozen=True, slots=True)
class Q80LadderStep:
    cost: int
    paid: int
    state: Q80LadderState
    outcome: Literal["goal", "ruin"] | None


def _validate_q80_profile(profile: GameProfile, coverage: int) -> GameProfile:
    if type(profile) is not GameProfile:
        raise TypeError("profile must be a GameProfile")
    profile = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
    if profile.universe_size != 100:
        raise ValueError("Q80 universe must contain 100 numbers")
    if profile.positions != 5:
        raise ValueError("Q80 positions must contain five draws")
    if not profile.allows_repeats:
        raise ValueError("Q80 repeats must be allowed")
    if tuple((p.numerator, p.denominator) for p in profile.multipliers) != tuple(
        (prize, 1) for prize in _PRIZES
    ):
        raise ValueError("Q80 payouts must be exact 80/8/4/2/1 integers")
    if profile.currency != "DOP":
        raise ValueError("Q80 policy requires DOP currency")
    if profile.scale != 0:
        raise ValueError("Q80 policy requires scale zero")
    if profile.stake_increment != 1:
        raise ValueError("Q80 policy requires increment one")
    if profile.minimum_stake != 1:
        raise ValueError("Q80 policy requires minimum stake one")
    if type(coverage) is not int or not 1 <= coverage < _PRIZES[0]:
        raise ValueError("Q80 coverage must be an integer from 1 to 79")
    if coverage > profile.max_coverage:
        raise ValueError("Q80 coverage exceeds profile coverage")
    return profile


def q80_audaz_stake(profile: GameProfile, coverage: int, balance: int, goal: int) -> int:
    """Reference audaz stake: goal-gap first-prize stake, capped only by funds.

    A positive reference stake is never clipped to profile stake/exposure caps;
    incompatible caps fail explicitly. Zero means the bankroll cannot fund even
    one unit per selected number, or the goal was already reached.
    """
    profile = _validate_q80_profile(profile, coverage)
    if type(balance) is not int or not 0 <= balance <= MAX_MONEY:
        raise ValueError("balance must be an exact bounded integer")
    if type(goal) is not int or not 1 <= goal <= MAX_MONEY:
        raise ValueError("goal must be an exact positive bounded integer")
    if balance >= goal:
        return 0
    gain = _PRIZES[0] - coverage
    stake = min((goal - balance + gain - 1) // gain, balance // coverage)
    if stake == 0:
        return 0
    if stake < profile.minimum_stake or stake % profile.stake_increment:
        return 0
    if stake > profile.maximum_stake:
        raise ValueError("Q80 audaz stake exceeds profile maximum stake")
    if stake * coverage > profile.max_exposure or stake * coverage > MAX_MONEY:
        raise ValueError("Q80 audaz stake exceeds profile exposure")
    return stake


def q80_first_prize_ladder(profile: GameProfile, coverage: int) -> tuple[int, ...]:
    """Ten full, unclipped stakes per number for first-hit recovery plus ten.

    Formula from repo_ref/strategy_tests/rules.py:first_prize_ladder (lines
    72-87): ceil((prior investments + 10) / (80 - coverage)), min 1.
    repo_ref/quiniela_compare.py:_validate (lines 69-75) admits 1..79.
    Check *all* rungs against this profile's stake and exposure limits before
    offering the policy, even if the current bankroll funds only round zero.
    """
    profile = _validate_q80_profile(profile, coverage)

    invested = 0
    ladder = []
    gain = _PRIZES[0] - coverage
    for _ in range(_ROUNDS):
        amount = max(1, (invested + _MARGIN + gain - 1) // gain)
        if amount > profile.maximum_stake:
            raise ValueError("Q80 ladder exceeds profile maximum stake")
        cost = coverage * amount
        if cost > profile.max_exposure or cost > MAX_MONEY:
            raise ValueError("Q80 ladder exceeds profile exposure")
        ladder.append(amount)
        invested += cost
    return tuple(ladder)


def step_q80_first_prize_cycle(
    profile: GameProfile,
    coverage: int,
    state: Q80LadderState,
    paid_per_unit: int,
    first_hit: bool,
    goal: int,
) -> Q80LadderStep:
    """Settle one draw or return unchanged on no funding; test the NEXT stake.

    The caller supplies the already-settled covered payout per unit and the
    independent first-position hit flag. Secondary payouts affect balance, not
    the round. No draw/selection/settlement IO occurs here. A tenth miss cycles
    back to round zero (compare/sim variant), not E5's terminal loss.
    """
    ladder = q80_first_prize_ladder(profile, coverage)
    if type(state) is not Q80LadderState:
        raise TypeError("state must be a Q80LadderState")
    state.__post_init__()
    if type(paid_per_unit) is not int or not 0 <= paid_per_unit <= sum(_PRIZES):
        raise ValueError("paid_per_unit must be an exact Q80 covered payout")
    if type(first_hit) is not bool:
        raise ValueError("first_hit must be an explicit bool")
    if type(goal) is not int or not 1 <= goal <= MAX_MONEY:
        raise ValueError("goal must be an exact positive bounded integer")
    if state.balance >= goal:
        return Q80LadderStep(0, 0, state, "goal")
    cost = coverage * ladder[state.round_index]
    if state.balance < cost:
        return Q80LadderStep(0, 0, state, "ruin")
    paid = ladder[state.round_index] * paid_per_unit
    balance = state.balance + paid - cost
    if paid > MAX_MONEY or balance > MAX_MONEY:
        raise ValueError("Q80 ladder settlement exceeds safe money ceiling")
    next_round = 0 if first_hit else (state.round_index + 1) % _ROUNDS
    next_state = Q80LadderState(balance, next_round)
    next_cost = coverage * ladder[next_round]
    outcome = "goal" if balance >= goal else "ruin" if balance < next_cost else None
    return Q80LadderStep(cost, paid, next_state, outcome)
