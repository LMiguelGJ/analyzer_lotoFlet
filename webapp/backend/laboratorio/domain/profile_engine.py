"""Pure, exact per-draw accounting for a validated versioned game profile.

This is not session execution: selection, draw scheduling, budget allocation and
termination remain the caller's responsibility. No public execution flag is set.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from laboratorio.domain.contracts import MAX_MONEY, GameProfile, SettlementMode


@dataclass(frozen=True, slots=True)
class ProfilePayout:
    """Integer amounts in the profile's declared smallest currency unit."""

    cost: int
    paid: int
    delta: int


def _bounded_units(value: int, name: str) -> None:
    if type(value) is not int or not 0 <= value <= MAX_MONEY:
        raise ValueError(f"{name} must be an integer between 0 and {MAX_MONEY}")


def settle_profile_bet(
    profile: GameProfile,
    results: Sequence[int],
    per_number_stakes: Mapping[int, int],
    settlement: SettlementMode,
    *,
    budget: int | None = None,
    capital: int | None = None,
) -> ProfilePayout:
    """Charge all stakes and pay matching positions, without a separate stake refund.

    ``all`` sums each matching position; ``best`` pays once per selected number,
    using the maximum position payout in new profiles and the first match only
    for the reserved legacy descriptor. Optional budget and capital each bound
    the *entire* wager, not individual stakes. There is no implicit rounding.
    An empty stake map is not a bet and is rejected.
    """
    if not isinstance(profile, GameProfile):
        raise TypeError("profile must be a GameProfile")
    # Frozen Pydantic instances can still be changed via model_copy(update=...).
    # Reconstruct through the standard validator, including its after validators.
    profile = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
    if type(settlement) is not SettlementMode:
        raise ValueError("settlement must explicitly be all or best")
    if not isinstance(results, (tuple, list)) or len(results) != profile.positions:
        raise ValueError("results must have exactly the profile's positions")
    if any(
        type(number) is not int or not 0 <= number < profile.universe_size for number in results
    ):
        raise ValueError("results must contain in-range integer numbers")
    if not profile.allows_repeats and len(set(results)) != len(results):
        raise ValueError("results repeat numbers in a no-repeats profile")
    if not isinstance(per_number_stakes, Mapping):
        raise TypeError("per_number_stakes must map distinct numbers to stakes")
    if not 1 <= len(per_number_stakes) <= profile.max_coverage:
        raise ValueError("stake coverage is outside the profile limit")

    cost = 0
    for number, stake in per_number_stakes.items():
        if type(number) is not int or not 0 <= number < profile.universe_size:
            raise ValueError("stake keys must be distinct in-range integers")
        if (
            type(stake) is not int
            or not profile.minimum_stake <= stake <= profile.maximum_stake
            or stake % profile.stake_increment
        ):
            raise ValueError("stakes must meet the profile's minimum, maximum and increment")
        cost += stake
    if cost > profile.max_exposure or cost > MAX_MONEY:
        raise ValueError("total stake exceeds per-draw exposure")
    for name, available in (("budget", budget), ("capital", capital)):
        if available is not None:
            _bounded_units(available, name)
            if cost > available:
                raise ValueError(f"total stake exceeds {name}")

    paid = 0
    matched: set[int] = set()
    best_by_number: dict[int, int] = {}
    for number, multiplier in zip(results, profile.multipliers, strict=True):
        if number not in per_number_stakes:
            continue
        dividend = per_number_stakes[number] * multiplier.numerator
        if dividend % multiplier.denominator:
            raise ValueError("payout is not integral in the declared currency units")
        payout = dividend // multiplier.denominator
        if settlement is SettlementMode.ALL:
            paid += payout
        elif profile.best_rule == "first-match/v0":
            if number not in matched:
                paid += payout
                matched.add(number)
        else:
            best_by_number[number] = max(best_by_number.get(number, 0), payout)
    if settlement is SettlementMode.BEST and profile.best_rule == "maximum-payout/v1":
        paid = sum(best_by_number.values())
    if paid > MAX_MONEY:
        raise ValueError("total payout exceeds the safe money ceiling")
    return ProfilePayout(cost=cost, paid=paid, delta=paid - cost)
