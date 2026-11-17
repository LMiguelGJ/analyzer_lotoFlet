"""Deterministic fixed-risk Monte Carlo scenarios; no Kelly or progression methods."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

from .risk_manager import RiskLimits


@dataclass(frozen=True)
class MonteCarloScenario:
    name: str
    true_probability: float
    paths: int
    horizon: int
    initial_capital: float
    mean_final_capital: float
    median_final_capital: float
    mean_per_period_growth: float
    mean_max_drawdown: float
    volatility_final_capital: float
    ruin_or_stop_rate: float
    mean_losing_streak: float
    worst_losing_streak: int
    note: str


@dataclass(frozen=True)
class MonteCarloReport:
    seed: int
    estimated_probability: float
    null_probability: float
    no_bet: MonteCarloScenario
    configured_under_null: MonteCarloScenario
    configured_under_estimated: MonteCarloScenario
    policy_note: str = "Configured scenarios use fixed stake/fraction only; no Kelly, martingale, or progression is simulated."


def _summary(
    name: str,
    true_probability: float,
    initial_capital: float,
    finals: list[float],
    drawdowns: list[float],
    growth_rates: list[float],
    stop_flags: list[bool],
    losing_streaks: list[int],
    paths: int,
    horizon: int,
    note: str,
) -> MonteCarloScenario:
    mean_final = sum(finals) / len(finals)
    variance = sum((value - mean_final) ** 2 for value in finals) / len(finals)
    return MonteCarloScenario(
        name=name,
        true_probability=true_probability,
        paths=paths,
        horizon=horizon,
        initial_capital=initial_capital,
        mean_final_capital=mean_final,
        median_final_capital=statistics.median(finals),
        mean_per_period_growth=sum(growth_rates) / len(growth_rates),
        mean_max_drawdown=sum(drawdowns) / len(drawdowns),
        volatility_final_capital=math.sqrt(variance),
        ruin_or_stop_rate=sum(1 for stopped in stop_flags if stopped) / len(stop_flags),
        mean_losing_streak=sum(losing_streaks) / len(losing_streaks),
        worst_losing_streak=max(losing_streaks),
        note=note,
    )


def _no_bet_scenario(
    initial_capital: float, paths: int, horizon: int, probability: float
) -> MonteCarloScenario:
    finals = [initial_capital] * paths
    zeros = [0.0] * paths
    return _summary(
        name="NO_BET",
        true_probability=probability,
        initial_capital=initial_capital,
        finals=finals,
        drawdowns=zeros,
        growth_rates=zeros,
        stop_flags=[False] * paths,
        losing_streaks=[0] * paths,
        paths=paths,
        horizon=horizon,
        note="No positions are opened; capital is unchanged.",
    )


def _simulate_configured(
    *,
    name: str,
    true_probability: float,
    estimated_probability: float,
    initial_capital: float,
    paths: int,
    horizon: int,
    stake: float | None,
    stake_fraction: float | None,
    limits: RiskLimits,
    rng: random.Random,
) -> MonteCarloScenario:
    finals: list[float] = []
    drawdowns: list[float] = []
    growth_rates: list[float] = []
    stop_flags: list[bool] = []
    losing_streaks: list[int] = []
    qualifying = estimated_probability > 0.5
    for _ in range(paths):
        capital = initial_capital
        peak = capital
        daily_loss = 0.0
        max_drawdown = 0.0
        current_losing = 0
        maximum_losing = 0
        stopped = False
        for _period in range(horizon):
            if not qualifying:
                continue
            current_stake = (
                stake if stake is not None else capital * (stake_fraction or 0.0)
            )
            if current_stake <= 0 or not math.isfinite(current_stake):
                stopped = True
                break
            allowed_limit = capital - (limits.reserve or 0.0)
            if limits.max_stake is not None:
                allowed_limit = min(allowed_limit, limits.max_stake)
            if limits.max_stake_fraction is not None:
                allowed_limit = min(
                    allowed_limit, initial_capital * limits.max_stake_fraction
                )
            if current_stake > allowed_limit + 1e-12:
                stopped = True
                break
            if (
                limits.max_daily_loss is not None
                and daily_loss + current_stake > limits.max_daily_loss + 1e-12
            ):
                stopped = True
                break
            if limits.max_drawdown is not None:
                prospective_drawdown = peak - (capital - current_stake)
                if prospective_drawdown > limits.max_drawdown + 1e-12:
                    stopped = True
                    break
            if rng.random() < true_probability:
                capital += current_stake * 0.4
                current_losing = 0
            else:
                capital -= current_stake
                daily_loss += current_stake
                current_losing += 1
                maximum_losing = max(maximum_losing, current_losing)
            peak = max(peak, capital)
            max_drawdown = max(max_drawdown, peak - capital)
            if capital <= 0 or (
                limits.reserve is not None and capital <= limits.reserve
            ):
                stopped = True
                break
            if (
                limits.max_daily_loss is not None
                and daily_loss >= limits.max_daily_loss
            ):
                stopped = True
                break
            if limits.max_drawdown is not None and max_drawdown >= limits.max_drawdown:
                stopped = True
                break
        finals.append(capital)
        drawdowns.append(max_drawdown)
        growth_rates.append(
            (capital / initial_capital) ** (1.0 / horizon) - 1.0
            if capital > 0 and horizon > 0
            else (0.0 if horizon == 0 else -1.0)
        )
        stop_flags.append(stopped)
        losing_streaks.append(maximum_losing)
    note = (
        "The >50% trigger was active. Results are exploratory and must not be read as an edge."
        if qualifying
        else "Estimated probability did not exceed 50%; configured policy stayed NO_BET."
    )
    return _summary(
        name=name,
        true_probability=true_probability,
        initial_capital=initial_capital,
        finals=finals,
        drawdowns=drawdowns,
        growth_rates=growth_rates,
        stop_flags=stop_flags,
        losing_streaks=losing_streaks,
        paths=paths,
        horizon=horizon,
        note=note,
    )


def run_monte_carlo(
    initial_capital: float,
    estimated_probability: float,
    *,
    stake: float | None = None,
    stake_fraction: float | None = None,
    paths: int = 1000,
    horizon: int = 100,
    seed: int = 12345,
    null_probability: float = 0.5,
    limits: RiskLimits | None = None,
) -> MonteCarloReport:
    """Compare no-bet and fixed-risk paths under null and estimated probabilities."""

    if initial_capital <= 0 or not math.isfinite(initial_capital):
        raise ValueError("initial_capital must be finite and positive")
    if not 0.0 <= estimated_probability <= 1.0 or not 0.0 <= null_probability <= 1.0:
        raise ValueError("probabilities must be between 0 and 1")
    if paths <= 0 or horizon < 0:
        raise ValueError("paths must be positive and horizon cannot be negative")
    if (stake is None) == (stake_fraction is None):
        raise ValueError("provide exactly one of stake or stake_fraction")
    if stake is not None and (stake <= 0 or not math.isfinite(stake)):
        raise ValueError("stake must be finite and positive")
    if stake_fraction is not None and not 0.0 < stake_fraction <= 1.0:
        raise ValueError("stake_fraction must be in (0, 1]")
    active_limits = limits
    if active_limits is None or not active_limits.has_explicit_limit:
        raise ValueError(
            "explicit manual risk limits are required: provide at least one of "
            "max_stake, max_stake_fraction, max_daily_loss, max_drawdown, or reserve"
        )
    active_limits.validate()
    no_bet = _no_bet_scenario(initial_capital, paths, horizon, null_probability)
    configured_under_null = _simulate_configured(
        name="CONFIGURED_FIXED_RISK_UNDER_NULL",
        true_probability=null_probability,
        estimated_probability=estimated_probability,
        initial_capital=initial_capital,
        paths=paths,
        horizon=horizon,
        stake=stake,
        stake_fraction=stake_fraction,
        limits=active_limits,
        rng=random.Random(seed),
    )
    configured_under_estimated = _simulate_configured(
        name="CONFIGURED_FIXED_RISK_UNDER_ESTIMATED",
        true_probability=estimated_probability,
        estimated_probability=estimated_probability,
        initial_capital=initial_capital,
        paths=paths,
        horizon=horizon,
        stake=stake,
        stake_fraction=stake_fraction,
        limits=active_limits,
        rng=random.Random(seed + 1),
    )
    return MonteCarloReport(
        seed=seed,
        estimated_probability=estimated_probability,
        null_probability=null_probability,
        no_bet=no_bet,
        configured_under_null=configured_under_null,
        configured_under_estimated=configured_under_estimated,
    )
