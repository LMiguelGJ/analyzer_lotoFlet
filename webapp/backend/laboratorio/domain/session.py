"""Pure Quiniela 80 session accounting over chronological, prepared draw rows.

No data access or persistence lives here. A missing ordering represents a draw
without ranking: its clock advances, but no bet is placed or settled.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from laboratorio.domain.contracts import (
    GAME,
    Conditions,
    Outcome,
    SettlementMode,
    StakingStyle,
    Strategy,
)


@dataclass(frozen=True, slots=True)
class Draw:
    label: str
    minute: int
    results: tuple[int, int, int, int, int]
    order: tuple[int, ...] | None


@dataclass(frozen=True, slots=True)
class Bet:
    label: str
    numbers: tuple[int, ...]
    per_number: int
    wagered: int
    results: tuple[int, int, int, int, int]
    paid: int
    balance: int


@dataclass(frozen=True, slots=True)
class SessionResult:
    outcome: Outcome
    bets_count: int
    wagered: int
    paid: int
    final_balance: int
    bets: tuple[Bet, ...]


def _ladder(coverage: int) -> tuple[int, ...]:
    """Ten recovery rounds: first-position prize covers earlier spend plus RD$10."""
    margin = GAME.prizes[0] - coverage
    if margin <= 0:
        raise ValueError("first prize must exceed coverage")
    invested = 0
    amounts = []
    for _ in range(10):
        amount = max(1, (invested + 10 + margin - 1) // margin)
        amounts.append(amount)
        invested += coverage * amount
    return tuple(amounts)


def _stake(
    balance: int, goal: int, strategy: Strategy, round_index: int, ladder: tuple[int, ...]
) -> int:
    if strategy.staking is StakingStyle.FLAT:
        return 1
    if strategy.staking is StakingStyle.LADDER:
        return ladder[round_index]
    margin = GAME.prizes[0] - strategy.coverage
    return min(balance // strategy.coverage, (goal - balance + margin - 1) // margin)


def preflight_initial_stake(conditions: Conditions, strategy: Strategy) -> int:
    """Validate the first wager using the same staking rule as session execution."""
    ladder = _ladder(strategy.coverage)
    stake = _stake(conditions.capital, conditions.goal, strategy, 0, ladder)
    if stake < 1 or conditions.capital < strategy.coverage * stake:
        raise ValueError("initial capital cannot afford the prescribed bet")
    return stake


def _payment(numbers: tuple[int, ...], results: tuple[int, ...], mode: SettlementMode) -> int:
    chosen = set(numbers)
    if mode is SettlementMode.ALL:
        return sum(
            prize for number, prize in zip(results, GAME.prizes, strict=True) if number in chosen
        )
    seen = set()
    total = 0
    for number, prize in zip(results, GAME.prizes, strict=True):
        if number in chosen and number not in seen:
            total += prize
            seen.add(number)
    return total


def run_session(conditions: Conditions, strategy: Strategy, draws: Iterable[Draw]) -> SessionResult:
    """Bet from the selected start until the first terminal event.

    Settlement happens before outcome checks. On the same settlement, financial
    outcomes (goal, then inability to finance the next bet) precede the bet cap;
    the clock cap excludes its boundary draw before any bet. A missing later
    ranking is not insolvency and never resets a ladder.
    """
    preflight_initial_stake(conditions, strategy)
    coverage = strategy.coverage
    ladder = _ladder(coverage)
    balance = conditions.capital
    wagered = paid = round_index = 0
    bets: list[Bet] = []
    start_minute = None
    outcome = Outcome.HISTORY_EXHAUSTED
    for row in draws:
        if start_minute is None:
            if row.label != conditions.start_draw or row.order is None:
                raise ValueError("start draw must have a ranking")
            start_minute = row.minute
        if (
            conditions.max_minutes is not None
            and row.minute - start_minute >= conditions.max_minutes
        ):
            outcome = Outcome.LIMIT
            break
        if row.order is None:
            continue
        per_number = _stake(balance, conditions.goal, strategy, round_index, ladder)
        cost = per_number * coverage
        if per_number < 1 or balance < cost:
            outcome = Outcome.RUIN
            break
        numbers = tuple(int(n) for n in row.order[:coverage])
        if len(numbers) != coverage or len(set(numbers)) != coverage:
            raise ValueError("draw ordering must contain the selected distinct numbers")
        winnings = per_number * _payment(numbers, row.results, conditions.settlement)
        balance += winnings - cost
        wagered += cost
        paid += winnings
        bets.append(Bet(row.label, numbers, per_number, cost, row.results, winnings, balance))
        if strategy.staking is StakingStyle.LADDER:
            round_index = 0 if row.results[0] in numbers else (round_index + 1) % len(ladder)
        if balance >= conditions.goal:
            outcome = Outcome.GOAL
            break
        next_stake = _stake(balance, conditions.goal, strategy, round_index, ladder)
        if next_stake < 1 or balance < coverage * next_stake:
            outcome = Outcome.RUIN
            break
        if conditions.max_bets is not None and len(bets) >= conditions.max_bets:
            outcome = Outcome.LIMIT
            break
    if start_minute is None:
        raise ValueError("start draw must exist")
    return SessionResult(outcome, len(bets), wagered, paid, balance, tuple(bets))
