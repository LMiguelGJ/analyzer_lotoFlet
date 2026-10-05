"""Pure multi-session historical replay over prepared, chronological draw rows."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from laboratorio.domain.contracts import StakingStyle
from laboratorio.domain.session import Bet, Draw


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    capital: int
    goal: int
    numbers: int
    positions: int
    prizes: tuple[int, ...]
    minimum_stake: int
    coverage: int
    staking: StakingStyle

    def __post_init__(self) -> None:
        if self.capital < 1 or self.goal <= self.capital:
            raise ValueError("goal must exceed positive capital")
        if self.numbers < 2 or self.positions < 1 or len(self.prizes) != self.positions:
            raise ValueError("game number/position/prize configuration is inconsistent")
        if any(type(prize) is not int or prize < 1 for prize in self.prizes):
            raise ValueError("prizes must be positive integers")
        if self.minimum_stake < 1 or not 1 <= self.coverage <= self.numbers:
            raise ValueError("minimum stake and coverage must fit the game")
        if type(self.staking) is not StakingStyle:
            raise ValueError("staking must be an explicit StakingStyle")
        if self.staking is StakingStyle.BOLD and self.coverage >= self.prizes[0]:
            raise ValueError("bold staking requires coverage below the first prize")


@dataclass(frozen=True, slots=True)
class BacktestSession:
    outcome: str
    final_balance: int
    bets: tuple[Bet, ...]


@dataclass(frozen=True, slots=True)
class WindowTotals:
    bets: int
    wagered: int
    paid: int


@dataclass(frozen=True, slots=True)
class BacktestResult:
    reached_goal: int
    quiebre: int
    completed: int
    goal_rate: float
    neto_medio: float
    incomplete: int
    sessions: tuple[BacktestSession, ...]
    window: WindowTotals


def _ladder(config: BacktestConfig) -> tuple[int, ...]:
    margin = config.prizes[0] - config.coverage
    if margin <= 0:
        raise ValueError("first prize must exceed coverage for ladder staking")
    invested = 0
    rounds = []
    for _ in range(10):
        stake = max(config.minimum_stake, (invested + 10 + margin - 1) // margin)
        rounds.append(stake)
        invested += config.coverage * stake
    return tuple(rounds)


def _stake(config: BacktestConfig, balance: int, round_index: int, ladder: tuple[int, ...]) -> int:
    if config.staking is StakingStyle.FLAT:
        return config.minimum_stake
    if config.staking is StakingStyle.LADDER:
        return ladder[round_index]
    margin = config.prizes[0] - config.coverage
    target = (config.goal - balance + margin - 1) // margin
    return min(target, balance // config.coverage)


def _paid(config: BacktestConfig, selected: tuple[int, ...], results: tuple[int, ...], stake: int):
    chosen = set(selected)
    return stake * sum(
        prize for number, prize in zip(results, config.prizes, strict=True) if number in chosen
    )


def _rounded(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def run_backtest(config: BacktestConfig, draws: Iterable[Draw]) -> BacktestResult:
    """Replay sessions sequentially; ranked rows are consumed once across sessions.

    Unranked rows are skipped without affecting balance or ladder progression. Each
    terminal session restarts at the next ranked draw; a tail still active at EOF is
    censored from completed metrics while its bets remain in window totals.
    """
    if type(config) is not BacktestConfig:
        raise TypeError("config must be BacktestConfig")
    rows = tuple(draws)
    if any(type(row) is not Draw for row in rows):
        raise TypeError("draws must contain Draw rows")
    previous_minute = None
    for row in rows:
        if previous_minute is not None and row.minute <= previous_minute:
            raise ValueError("draws must be strictly chronological")
        if len(row.results) != config.positions or any(
            type(number) is not int or not 0 <= number < config.numbers for number in row.results
        ):
            raise ValueError("draw results do not fit configured game")
        if row.order is not None and (
            len(row.order) < config.coverage
            or len(set(row.order)) != len(row.order)
            or any(
                type(number) is not int or not 0 <= number < config.numbers for number in row.order
            )
        ):
            raise ValueError("ranked draw must have a distinct valid coverage selection")
        previous_minute = row.minute

    ladder = _ladder(config) if config.staking is StakingStyle.LADDER else ()
    sessions: list[BacktestSession] = []
    window_bets = window_wagered = window_paid = 0
    cursor = 0
    while cursor < len(rows):
        while cursor < len(rows) and rows[cursor].order is None:
            cursor += 1
        if cursor == len(rows):
            break
        balance = config.capital
        round_index = 0
        bets = []
        outcome = None
        while cursor < len(rows):
            row = rows[cursor]
            cursor += 1
            if row.order is None:
                continue
            stake = _stake(config, balance, round_index, ladder)
            cost = stake * config.coverage
            if stake < config.minimum_stake or balance < cost:
                outcome = "quiebre"
                break
            selected = tuple(row.order[: config.coverage])
            paid = _paid(config, selected, row.results, stake)
            balance += paid - cost
            bet = Bet(row.label, selected, stake, cost, row.results, paid, balance)
            bets.append(bet)
            window_bets += 1
            window_wagered += cost
            window_paid += paid
            if config.staking is StakingStyle.LADDER:
                round_index = 0 if row.results[0] in selected else (round_index + 1) % len(ladder)
            if balance >= config.goal:
                outcome = "reached_goal"
                break
            next_stake = _stake(config, balance, round_index, ladder)
            if next_stake < config.minimum_stake or balance < next_stake * config.coverage:
                outcome = "quiebre"
                break
        sessions.append(BacktestSession(outcome or "incomplete", balance, tuple(bets)))
        if outcome is None:
            break
    reached = sum(session.outcome == "reached_goal" for session in sessions)
    ruined = sum(session.outcome == "quiebre" for session in sessions)
    completed = reached + ruined
    net = [
        session.final_balance - config.capital
        for session in sessions
        if session.outcome != "incomplete"
    ]
    return BacktestResult(
        reached_goal=reached,
        quiebre=ruined,
        completed=completed,
        goal_rate=_rounded(100 * reached / completed) if completed else 0.0,
        neto_medio=_rounded(sum(net) / len(net)) if net else 0.0,
        incomplete=len(sessions) - completed,
        sessions=tuple(sessions),
        window=WindowTotals(window_bets, window_wagered, window_paid),
    )
