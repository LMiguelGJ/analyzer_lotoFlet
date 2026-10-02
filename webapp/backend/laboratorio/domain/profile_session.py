"""Pure bounded session execution for the explicit, supported profile subset.

No adapter, storage, ranking, or legacy engine is changed here. Inputs are complete
prepared draw rows; skipped entries still advance the elapsed-draw clock. The
registry names pending families rather than silently treating them as supported.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from laboratorio.domain.contracts import (
    DRAW_FORMAT,
    MAX_MONEY,
    MAX_SEED,
    GameProfile,
    SettlementMode,
)
from laboratorio.domain.profile_capabilities import legacy_capabilities, require_supported
from laboratorio.domain.profile_engine import settle_profile_bet
from laboratorio.domain.profile_staking import (
    ProfileAudazStaking,
    ProfileRecoveryLadderStaking,
    ProfileRecoveryState,
    Q80LadderState,
    Q80ReferenceAudazStaking,
    Q80ReferenceAudazState,
    profile_audaz_stake,
    profile_recovery_ladder,
    q80_first_prize_ladder,
    q80_reference_audaz_stake,
    step_profile_recovery,
    step_q80_first_prize_cycle,
    step_q80_reference_audaz,
)

SESSION_VERSION = 1
MAX_SESSION_ROWS = 10_000  # Admission ceiling including pre-start rows and skipped entries.


class ProfileOutcome(StrEnum):
    GOAL = "goal"
    RUIN = "ruin"
    LIMIT = "limit"
    HISTORY_EXHAUSTED = "history_exhausted"
    CANCELLED = "cancelled"


# Compatibility projection only; admission and API lists come from the registry.
CAPABILITIES = legacy_capabilities()


def _exact_int(value: object, name: str, lower: int, upper: int) -> None:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer between {lower} and {upper}")


def _minute(label: str) -> int:
    if type(label) is not str:
        raise ValueError("draw label must be a canonical YYYY-MM-DD HH:MM string")
    try:
        moment = datetime.strptime(label, DRAW_FORMAT)
    except ValueError as exc:
        raise ValueError("draw label must be a valid YYYY-MM-DD HH:MM date") from exc
    if moment.strftime(DRAW_FORMAT) != label:
        raise ValueError("draw label must be canonical YYYY-MM-DD HH:MM")
    return (moment - datetime(1970, 1, 1)).days * 1440 + moment.hour * 60 + moment.minute


@dataclass(frozen=True, slots=True)
class ProfileConditions:
    schema_version: int
    start_draw: str
    capital: int
    goal: int
    settlement: SettlementMode
    max_elapsed_draws: int | None = None
    max_bet_draws: int | None = None
    end_minute: int | None = None
    duration_minutes: int | None = None

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SESSION_VERSION:
            raise ValueError("unsupported session conditions version")
        _minute(self.start_draw)
        _exact_int(self.capital, "capital", 1, MAX_MONEY)
        _exact_int(self.goal, "goal", 1, MAX_MONEY)
        if self.goal <= self.capital:
            raise ValueError("goal must exceed initial capital")
        if type(self.settlement) is not SettlementMode:
            raise ValueError("settlement must explicitly be all or best")
        require_supported("settlement", self.settlement.value, self.schema_version)
        for name in ("max_elapsed_draws", "max_bet_draws", "duration_minutes"):
            value = getattr(self, name)
            if value is not None:
                ceiling = 10**9 if name == "duration_minutes" else MAX_SESSION_ROWS
                _exact_int(value, name, 1, ceiling)
        if self.end_minute is not None:
            _exact_int(self.end_minute, "end_minute", 1, 10**9)
            if self.end_minute <= _minute(self.start_draw):
                raise ValueError("end_minute must be after start_draw")


@dataclass(frozen=True, slots=True)
class ProfileSelector:
    schema_version: int
    capability: str
    coverage: int
    numbers: tuple[int, ...] | None = None
    seed: int | None = None
    algorithm_version: str | None = None

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SESSION_VERSION:
            raise ValueError("unsupported selector version")
        _exact_int(self.coverage, "coverage", 1, 1_000)
        capability = require_supported("selector", self.capability, self.schema_version)
        if self.capability == "static-numbers/v1":
            if type(self.numbers) is not tuple or len(self.numbers) != self.coverage:
                raise ValueError("static selector requires explicit coverage-sized numbers")
            if any(type(n) is not int or n < 0 for n in self.numbers) or len(
                set(self.numbers)
            ) != len(self.numbers):
                raise ValueError("static numbers must be distinct non-negative integers")
            if self.seed is not None or self.algorithm_version is not None:
                raise ValueError("static selector cannot carry random parameters")
        elif self.capability == "seeded-random/hash-sha256-v1":
            if self.numbers is not None or self.algorithm_version != capability.version:
                raise ValueError("random selector requires explicit hash-sha256-v1 algorithm")
            _exact_int(self.seed, "seed", 0, MAX_SEED)
        else:
            raise ValueError(f"unsupported selector capability: {self.capability!r}")


@dataclass(frozen=True, slots=True)
class ProfileStaking:
    schema_version: int
    capability: str
    per_number_stake: int

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SESSION_VERSION:
            raise ValueError("unsupported staking version")
        require_supported("staking", self.capability, self.schema_version)
        _exact_int(self.per_number_stake, "per_number_stake", 1, MAX_MONEY)


@dataclass(frozen=True, slots=True)
class Q80CyclingStaking:
    """Private Q80 ten-round cycling policy; not a v1 request capability."""

    schema_version: int = SESSION_VERSION
    capability: str = "q80-first-prize-cycling/v1"

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SESSION_VERSION:
            raise ValueError("unsupported Q80 cycling staking version")
        if type(self.capability) is not str or self.capability != "q80-first-prize-cycling/v1":
            raise ValueError("unsupported Q80 cycling staking policy")


@dataclass(frozen=True, slots=True)
class ProfileDraw:
    schema_version: int
    label: str
    minute: int
    results: tuple[int, ...]
    enter: bool

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SESSION_VERSION:
            raise ValueError("unsupported draw version")
        if type(self.minute) is not int or self.minute != _minute(self.label):
            raise ValueError("draw minute must agree with canonical label")
        if type(self.results) is not tuple or any(type(n) is not int for n in self.results):
            raise ValueError("results must be a tuple of exact integers")
        if type(self.enter) is not bool:
            raise ValueError("enter must explicitly be a bool")


@dataclass(frozen=True, slots=True)
class ProfileBet:
    label: str
    stakes: tuple[tuple[int, int], ...]
    results: tuple[int, ...]
    wagered: int
    paid: int
    balance: int


@dataclass(frozen=True, slots=True)
class ProfileSessionResult:
    schema_version: int
    profile_id: str
    profile_revision: int
    outcome: ProfileOutcome
    collisions: tuple[str, ...]
    elapsed_draws: int
    bet_draws: int
    wagered: int
    paid: int
    final_balance: int
    bets: tuple[ProfileBet, ...]


def _selected(profile: GameProfile, selector: ProfileSelector, label: str) -> tuple[int, ...]:
    if selector.capability == "static-numbers/v1":
        if selector.numbers is None:
            raise ValueError("static selector has no numbers")
        return selector.numbers
    # Hash each number independently. No mutable PRNG state, modulo bias, or
    # coverage in the key: prefixes are stable for every k on the same draw.
    if selector.seed is None:
        raise ValueError("random selector has no seed")
    return tuple(
        sorted(
            range(profile.universe_size),
            key=lambda n: (
                sha256(f"hash-sha256-v1:{selector.seed}:{label}:{n}".encode("ascii")).digest(),
                n,
            ),
        )[: selector.coverage]
    )


def run_profile_session(
    profile: GameProfile,
    conditions: ProfileConditions,
    selector: ProfileSelector,
    staking: (
        ProfileStaking
        | Q80CyclingStaking
        | ProfileAudazStaking
        | ProfileRecoveryLadderStaking
        | Q80ReferenceAudazStaking
    ),
    draws: Sequence[ProfileDraw],
    *,
    row_budget: int = MAX_SESSION_ROWS,
    cancel_after_elapsed_draws: int | None = None,
    selected_numbers: Callable[[ProfileDraw], tuple[int, ...]] | None = None,
) -> ProfileSessionResult:
    """Validate and admit at most ``row_budget`` rows, then run without external IO.

    ``cancel_after_elapsed_draws`` is an explicit deterministic cancellation signal:
    stop before the next row once that many in-window rows have elapsed. No callback
    or hidden clock is consulted. The source must be a bounded, chronological
    prepared dataset; no future result
    value participates in selecting a bet. Pre-start rows count toward admission.
    Lists/tuples only: the importer must enforce this budget before materialization;
    arbitrary iterables are rejected rather than expanded without validation.
    """
    if not isinstance(profile, GameProfile):
        raise TypeError("profile must be a GameProfile")
    profile = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
    if (
        type(conditions) is not ProfileConditions
        or type(selector) is not ProfileSelector
        or type(staking)
        not in (
            ProfileStaking,
            Q80CyclingStaking,
            ProfileAudazStaking,
            ProfileRecoveryLadderStaking,
            Q80ReferenceAudazStaking,
        )
    ):
        raise TypeError("conditions, selector and staking must be typed session models")
    # Frozen dataclasses are shallow: revalidate even object.__setattr__-tampered
    # instances, and reject forged nested tuples before allocation or settlement.
    for config in (conditions, selector, staking):
        config.__post_init__()
    _exact_int(row_budget, "row_budget", 1, MAX_SESSION_ROWS)
    if cancel_after_elapsed_draws is not None:
        _exact_int(cancel_after_elapsed_draws, "cancel_after_elapsed_draws", 0, row_budget)
    if selected_numbers is not None and not callable(selected_numbers):
        raise TypeError("selected_numbers must be a callable selector")
    if type(draws) not in (tuple, list):
        raise TypeError("draws must be a bounded materialized list or tuple of imported rows")
    if len(draws) > row_budget:
        raise ValueError("draw row budget exceeded")
    if selector.coverage > profile.max_coverage or selector.coverage > profile.universe_size:
        raise ValueError("selector coverage exceeds profile")
    if selector.numbers is not None and any(n >= profile.universe_size for n in selector.numbers):
        raise ValueError("static number exceeds profile universe")
    ladder = ()
    ladder_state = Q80LadderState(conditions.capital)
    recovery_state = ProfileRecoveryState(conditions.capital)
    reference_state = Q80ReferenceAudazState(conditions.capital)
    stake = 0
    if isinstance(staking, Q80CyclingStaking):
        ladder = q80_first_prize_ladder(profile, selector.coverage)
        cost = ladder[0] * selector.coverage
    elif isinstance(staking, ProfileRecoveryLadderStaking):
        staking.__post_init__()
        ladder = profile_recovery_ladder(
            profile, selector.coverage, staking.target_margin, staking.rounds
        )
        cost = ladder[0] * selector.coverage
    elif isinstance(staking, Q80ReferenceAudazStaking):
        stake = q80_reference_audaz_stake(conditions.capital, conditions.goal, profile=profile)
        if stake == 0:
            raise ValueError("initial capital cannot afford the minimum reference audaz stake")
        cost = stake * selector.coverage
        if cost > conditions.capital:
            raise ValueError("initial reference audaz stake exceeds capital")
    elif isinstance(staking, ProfileAudazStaking):
        # Validate exact policy compatibility and initial affordability before any row.
        stake = profile_audaz_stake(profile, selector.coverage, conditions.capital, conditions.goal)
        if stake == 0:
            raise ValueError("initial capital cannot afford the minimum audaz stake")
        cost = stake * selector.coverage
        if cost > conditions.capital or cost > profile.max_exposure or cost > MAX_MONEY:
            raise ValueError("initial audaz stake exceeds capital or profile exposure")
    else:
        stake = staking.per_number_stake
        if (
            not profile.minimum_stake <= stake <= profile.maximum_stake
            or stake % profile.stake_increment
        ):
            raise ValueError("stake is incompatible with profile bounds or increment")
        cost = stake * selector.coverage
        if cost > profile.max_exposure or cost > MAX_MONEY:
            raise ValueError("stake cost exceeds profile exposure")
    if cost > conditions.capital and not isinstance(staking, ProfileAudazStaking):
        raise ValueError("initial capital cannot afford the prescribed bet")

    start_index = None
    previous_minute = None
    for index, row in enumerate(draws):
        if type(row) is not ProfileDraw:
            raise TypeError("each row must be a ProfileDraw")
        row.__post_init__()
        if len(row.results) != profile.positions or any(
            n < 0 or n >= profile.universe_size for n in row.results
        ):
            raise ValueError("draw results positions/range incompatible with profile")
        if not profile.allows_repeats and len(set(row.results)) != len(row.results):
            raise ValueError("draw results repeat numbers in a no-repeats profile")
        if previous_minute is not None and row.minute <= previous_minute:
            raise ValueError("draws must be strictly chronological without duplicate minutes")
        previous_minute = row.minute
        if row.label == conditions.start_draw:
            start_index = index
    if start_index is None:
        raise ValueError("start draw must exist")
    rows = draws[start_index:]
    start_minute = _minute(conditions.start_draw)
    balance = conditions.capital
    wagered = paid = elapsed = 0
    bets: list[ProfileBet] = []
    outcome = ProfileOutcome.HISTORY_EXHAUSTED
    collisions: tuple[str, ...] = ()
    for row in rows:
        if cancel_after_elapsed_draws is not None and elapsed >= cancel_after_elapsed_draws:
            outcome = ProfileOutcome.CANCELLED
            break
        boundaries = tuple(
            name
            for name, reached in (
                (
                    "end_minute",
                    conditions.end_minute is not None and row.minute >= conditions.end_minute,
                ),
                (
                    "duration_minutes",
                    conditions.duration_minutes is not None
                    and row.minute - start_minute >= conditions.duration_minutes,
                ),
            )
            if reached
        )
        if boundaries:
            outcome, collisions = ProfileOutcome.LIMIT, boundaries
            break
        elapsed += 1
        ladder_outcome = None
        audaz_outcome = None
        if row.enter:
            numbers = (
                selected_numbers(row)
                if selected_numbers is not None
                else _selected(profile, selector, row.label)
            )
            if (
                type(numbers) is not tuple
                or len(numbers) != selector.coverage
                or len(set(numbers)) != len(numbers)
                or any(
                    type(number) is not int or not 0 <= number < profile.universe_size
                    for number in numbers
                )
            ):
                raise ValueError(
                    "selected numbers must be a distinct coverage-sized profile selection"
                )
            if isinstance(staking, Q80CyclingStaking):
                stake = ladder[ladder_state.round_index]
            elif isinstance(staking, ProfileRecoveryLadderStaking):
                stake = ladder[recovery_state.round_index]
            elif isinstance(staking, Q80ReferenceAudazStaking):
                stake = q80_reference_audaz_stake(balance, conditions.goal, profile=profile)
                if stake == 0:
                    audaz_outcome = "ruin"
            elif isinstance(staking, ProfileAudazStaking):
                stake = profile_audaz_stake(profile, selector.coverage, balance, conditions.goal)
                if stake == 0:
                    audaz_outcome = "ruin"
            if stake > 0:
                stakes = tuple((number, stake) for number in numbers)
                payout = settle_profile_bet(
                    profile, row.results, dict(stakes), conditions.settlement, capital=balance
                )
                if isinstance(staking, Q80CyclingStaking):
                    # One authoritative settlement binds payout and first-position hit
                    # to this validated draw and selection. The kernel owns transitions.
                    unit_paid, remainder = divmod(payout.paid, stake)
                    if remainder:
                        raise AssertionError("Q80 settlement is not divisible by its unit stake")
                    ladder_step = step_q80_first_prize_cycle(
                        profile,
                        selector.coverage,
                        ladder_state,
                        unit_paid,
                        row.results[0] in numbers,
                        conditions.goal,
                    )
                    if (
                        ladder_step.cost != payout.cost
                        or ladder_step.paid != payout.paid
                        or ladder_step.state.balance != balance + payout.delta
                    ):
                        raise AssertionError("Q80 kernel and authoritative settlement disagree")
                    if wagered + payout.cost > MAX_MONEY or paid + payout.paid > MAX_MONEY:
                        raise ValueError("session totals exceed the safe money ceiling")
                    ladder_state = ladder_step.state
                    ladder_outcome = ladder_step.outcome
                    balance = ladder_state.balance
                elif isinstance(staking, Q80ReferenceAudazStaking):
                    unit_paid, remainder = divmod(payout.paid, stake)
                    if remainder:
                        raise AssertionError(
                            "Q80 reference settlement is not divisible by unit stake"
                        )
                    reference_step = step_q80_reference_audaz(
                        profile, reference_state, selector.coverage, unit_paid, conditions.goal
                    )
                    if reference_step.cost != payout.cost or reference_step.paid != payout.paid:
                        raise AssertionError(
                            "reference audaz kernel and authoritative settlement disagree"
                        )
                    reference_state = reference_step.state
                    audaz_outcome = "ruin" if reference_step.outcome == "quiebre" else None
                    balance = reference_state.balance
                elif isinstance(staking, ProfileRecoveryLadderStaking):
                    recovery_step = step_profile_recovery(
                        ladder,
                        selector.coverage,
                        recovery_state,
                        payout.paid,
                        row.results[0] in numbers,
                        conditions.goal,
                        staking.end_mode,
                    )
                    if (
                        recovery_step.cost != payout.cost
                        or recovery_step.paid != payout.paid
                        or recovery_step.state.balance != balance + payout.delta
                    ):
                        raise AssertionError(
                            "recovery kernel and authoritative settlement disagree"
                        )
                    recovery_state = recovery_step.state
                    ladder_outcome = recovery_step.outcome
                    balance = recovery_state.balance
                else:
                    balance += payout.delta
                    if isinstance(staking, ProfileAudazStaking):
                        next_stake = profile_audaz_stake(
                            profile, selector.coverage, balance, conditions.goal
                        )
                        if balance < conditions.goal and next_stake == 0:
                            audaz_outcome = "ruin"
                wagered += payout.cost
                paid += payout.paid
                if not 0 <= balance <= MAX_MONEY or wagered > MAX_MONEY or paid > MAX_MONEY:
                    raise ValueError("session totals exceed the safe money ceiling")
                bets.append(
                    ProfileBet(row.label, stakes, row.results, payout.cost, payout.paid, balance)
                )
        reasons = tuple(
            name
            for name, reached in (
                ("goal", bool(row.enter and balance >= conditions.goal)),
                (
                    "ruin",
                    bool(
                        row.enter
                        and (
                            ladder_outcome == "ruin"
                            if isinstance(
                                staking,
                                (Q80CyclingStaking, ProfileRecoveryLadderStaking),
                            )
                            else audaz_outcome == "ruin"
                            if isinstance(staking, (ProfileAudazStaking, Q80ReferenceAudazStaking))
                            else balance < cost
                        )
                    ),
                ),
                (
                    "recovery_round_limit",
                    bool(
                        row.enter
                        and isinstance(staking, ProfileRecoveryLadderStaking)
                        and ladder_outcome == "round_limit"
                    ),
                ),
                (
                    "max_bet_draws",
                    conditions.max_bet_draws is not None and len(bets) >= conditions.max_bet_draws,
                ),
                (
                    "max_elapsed_draws",
                    conditions.max_elapsed_draws is not None
                    and elapsed >= conditions.max_elapsed_draws,
                ),
            )
            if reached
        )
        if reasons:
            collisions = reasons
            outcome = (
                ProfileOutcome.GOAL
                if reasons[0] == "goal"
                else ProfileOutcome.RUIN
                if reasons[0] == "ruin"
                else ProfileOutcome.LIMIT
            )
            break
    return ProfileSessionResult(
        SESSION_VERSION,
        profile.profile_id,
        profile.revision,
        outcome,
        collisions,
        elapsed,
        len(bets),
        wagered,
        paid,
        balance,
        tuple(bets),
    )
