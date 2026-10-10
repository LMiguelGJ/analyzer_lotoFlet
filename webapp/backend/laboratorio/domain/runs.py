"""Pure consecutive-session run engine over prepared, chronological draw rows.

Every session starts with the initial capital, bets the minimum stake on each covered number
and ends on goal, ruin or an optional draw limit. The next session opens right after the draw
that closed the previous one; a session still open when the rows run out is ``incomplete``.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from laboratorio.domain.session import Bet, Draw

OUTCOME_GOAL = "goal"
OUTCOME_RUIN = "ruin"
OUTCOME_LIMIT = "limit"
OUTCOME_INCOMPLETE = "incomplete"

NUMBERS = 100
MAX_POSITIONS = 5
MAX_COVERAGE = 50
RESULTS_PER_DRAW = 5


def _is_int(value: object) -> bool:
    return type(value) is int


@dataclass(frozen=True, slots=True)
class RunConfig:
    capital: int
    goal: int
    coverage: int
    positions: int
    prizes: tuple[int, ...]
    minimum_stake: int
    max_draws: int | None = None

    def __post_init__(self) -> None:
        integers = (self.capital, self.goal, self.coverage, self.positions, self.minimum_stake)
        if not all(_is_int(value) for value in integers):
            raise ValueError("capital, goal, coverage, positions and stake must be integers")
        if not isinstance(self.prizes, tuple) or not all(_is_int(prize) for prize in self.prizes):
            raise ValueError("prizes must be a tuple of integers")
        if self.max_draws is not None and not _is_int(self.max_draws):
            raise ValueError("max_draws must be an integer or None")
        if self.capital < 1 or self.goal <= self.capital:
            raise ValueError("goal must exceed a positive capital")
        if not 1 <= self.coverage <= MAX_COVERAGE:
            raise ValueError(f"coverage must be between 1 and {MAX_COVERAGE}")
        if not 1 <= self.positions <= MAX_POSITIONS:
            raise ValueError(f"positions must be between 1 and {MAX_POSITIONS}")
        if len(self.prizes) != self.positions or any(prize < 1 for prize in self.prizes):
            raise ValueError("exactly one positive prize per position is required")
        if self.minimum_stake < 1:
            raise ValueError("minimum stake must be positive")
        if self.capital < self.coverage * self.minimum_stake:
            raise ValueError("capital must afford the first bet")
        if self.max_draws is not None and self.max_draws < 1:
            raise ValueError("max_draws must be at least 1")


@dataclass(frozen=True, slots=True)
class RunSession:
    ordinal: int
    outcome: str
    start_index: int
    end_index: int
    draws: int
    final_balance: int
    wagered: int
    paid: int
    bets: tuple[Bet, ...]


@dataclass(frozen=True, slots=True)
class RunTotals:
    sessions: int
    goal: int
    ruin: int
    limit: int
    incomplete: int
    bets: int
    wagered: int
    paid: int
    net: int
    return_pct: float | None
    mean_net_closed: float | None


@dataclass(frozen=True, slots=True)
class RunResult:
    sessions: tuple[RunSession, ...]
    totals: RunTotals
    draws: int
    ranked_draws: int


def _ratio(numerator: int, denominator: int) -> float:
    """Exact ``numerator / denominator`` rounded to one decimal, halves away from zero."""
    value = Decimal(numerator) / Decimal(denominator)
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _validate_rows(rows: tuple[Draw, ...], coverage: int) -> int:
    """Check every row and return how many are ranked."""
    ranked = 0
    previous_minute = None
    for row in rows:
        if type(row) is not Draw:
            raise TypeError("rows must contain Draw instances")
        if previous_minute is not None and row.minute <= previous_minute:
            raise ValueError("draws must be strictly chronological")
        previous_minute = row.minute
        results = row.results
        if len(results) != RESULTS_PER_DRAW or any(
            type(number) is not int or not 0 <= number < NUMBERS for number in results
        ):
            raise ValueError("draw results must be five integers between 0 and 99")
        order = row.order
        if order is not None:
            if (
                len(order) < coverage
                or len(set(order)) != len(order)
                or any(type(number) is not int or not 0 <= number < NUMBERS for number in order)
            ):
                raise ValueError("ranked draw must have distinct valid numbers covering the bet")
            ranked += 1
    return ranked


def _totals(sessions: list[RunSession], capital: int) -> RunTotals:
    counts = {OUTCOME_GOAL: 0, OUTCOME_RUIN: 0, OUTCOME_LIMIT: 0, OUTCOME_INCOMPLETE: 0}
    bets = wagered = paid = closed_net = closed = 0
    for session in sessions:
        counts[session.outcome] += 1
        bets += len(session.bets)
        wagered += session.wagered
        paid += session.paid
        if session.outcome != OUTCOME_INCOMPLETE:
            closed += 1
            closed_net += session.final_balance - capital
    net = paid - wagered
    return RunTotals(
        sessions=len(sessions),
        goal=counts[OUTCOME_GOAL],
        ruin=counts[OUTCOME_RUIN],
        limit=counts[OUTCOME_LIMIT],
        incomplete=counts[OUTCOME_INCOMPLETE],
        bets=bets,
        wagered=wagered,
        paid=paid,
        net=net,
        return_pct=_ratio(100 * net, wagered) if wagered else None,
        mean_net_closed=_ratio(closed_net, closed) if closed else None,
    )


def run_sessions(config: RunConfig, rows: Iterable[Draw]) -> RunResult:
    """Chain sessions over ``rows`` and report each one plus window totals.

    Unranked rows never bet. Before a session they are skipped; inside one they still advance
    the elapsed-draw clock used by ``max_draws``. After each settled bet the session closes
    on goal first, then ruin (the next bet is unaffordable), then limit.
    """
    if type(config) is not RunConfig:
        raise TypeError("config must be RunConfig")
    draws = tuple(rows)
    ranked_draws = _validate_rows(draws, config.coverage)

    capital = config.capital
    goal = config.goal
    coverage = config.coverage
    positions = config.positions
    prizes = config.prizes
    stake = config.minimum_stake
    max_draws = config.max_draws
    cost = coverage * stake
    prize_amounts = tuple(prize * stake for prize in prizes)
    position_range = range(positions)

    sessions: list[RunSession] = []
    total = len(draws)
    cursor = 0
    while cursor < total:
        while cursor < total and draws[cursor].order is None:
            cursor += 1
        if cursor == total:
            break
        start = cursor
        balance = capital
        elapsed = 0
        wagered = paid_total = 0
        bets: list[Bet] = []
        outcome = OUTCOME_INCOMPLETE
        while cursor < total:
            row = draws[cursor]
            cursor += 1
            elapsed += 1
            order = row.order
            if order is not None:
                selected = order[:coverage]
                chosen = set(selected)
                # A Bet keeps only the positions in play, so the slice is shorter than five.
                results = cast("Any", row.results[:positions])
                paid = 0
                for position in position_range:
                    if results[position] in chosen:
                        paid += prize_amounts[position]
                balance += paid - cost
                wagered += cost
                paid_total += paid
                bets.append(Bet(row.label, selected, stake, cost, results, paid, balance))
                if balance >= goal:
                    outcome = OUTCOME_GOAL
                elif balance < cost:
                    outcome = OUTCOME_RUIN
            if outcome == OUTCOME_INCOMPLETE and max_draws is not None and elapsed >= max_draws:
                outcome = OUTCOME_LIMIT
            if outcome != OUTCOME_INCOMPLETE:
                break
        sessions.append(
            RunSession(
                ordinal=len(sessions) + 1,
                outcome=outcome,
                start_index=start,
                end_index=cursor - 1,
                draws=elapsed,
                final_balance=balance,
                wagered=wagered,
                paid=paid_total,
                bets=tuple(bets),
            )
        )
        if outcome == OUTCOME_INCOMPLETE:
            break

    return RunResult(
        sessions=tuple(sessions),
        totals=_totals(sessions, capital),
        draws=total,
        ranked_draws=ranked_draws,
    )
