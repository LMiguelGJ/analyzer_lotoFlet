"""Manual capital limits for a fixed-risk paper-only ledger."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    """All limits are explicit inputs; ``None`` means the caller did not set it."""

    max_stake: float | None = None
    max_stake_fraction: float | None = None
    max_daily_loss: float | None = None
    max_drawdown: float | None = None
    reserve: float | None = None

    @property
    def has_explicit_limit(self) -> bool:
        return any(
            value is not None
            for value in (
                self.max_stake,
                self.max_stake_fraction,
                self.max_daily_loss,
                self.max_drawdown,
                self.reserve,
            )
        )

    def validate(self) -> None:
        for name, value in (
            ("max_stake", self.max_stake),
            ("max_daily_loss", self.max_daily_loss),
            ("max_drawdown", self.max_drawdown),
            ("reserve", self.reserve),
        ):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and non-negative")
        if self.max_stake_fraction is not None and (
            not math.isfinite(self.max_stake_fraction)
            or not 0.0 < self.max_stake_fraction <= 1.0
        ):
            raise ValueError("max_stake_fraction must be in (0, 1]")


@dataclass(frozen=True)
class RiskCheck:
    allowed: bool
    reason: str
    stake: float
    current_capital: float
    maximum_allowed_stake: float | None


class RiskManager:
    """Stateful risk gate that never increases stake after a loss."""

    def __init__(self, initial_capital: float, limits: RiskLimits) -> None:
        if not math.isfinite(initial_capital) or initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive")
        limits.validate()
        self.initial_capital = float(initial_capital)
        self.limits = limits
        self.current_capital = float(initial_capital)
        self.peak_capital = float(initial_capital)
        self.daily_loss = 0.0
        self.last_stake = 0.0
        self.last_result: float | None = None
        self.stopped_reason: str | None = None

    @property
    def drawdown(self) -> float:
        return max(0.0, self.peak_capital - self.current_capital)

    @property
    def is_stopped(self) -> bool:
        return self.stopped_reason is not None

    @property
    def maximum_allowed_stake(self) -> float | None:
        candidates = [self.current_capital - (self.limits.reserve or 0.0)]
        if self.limits.max_stake is not None:
            candidates.append(self.limits.max_stake)
        if self.limits.max_stake_fraction is not None:
            candidates.append(self.initial_capital * self.limits.max_stake_fraction)
        return max(0.0, min(candidates)) if candidates else None

    def check_data(
        self, data_available: bool, data_stale: bool, data_valid: bool
    ) -> RiskCheck:
        if not data_available:
            return RiskCheck(
                False,
                "MISSING_DATA",
                0.0,
                self.current_capital,
                self.maximum_allowed_stake,
            )
        if data_stale:
            return RiskCheck(
                False,
                "STALE_DATA",
                0.0,
                self.current_capital,
                self.maximum_allowed_stake,
            )
        if not data_valid:
            return RiskCheck(
                False,
                "INVALID_DATA",
                0.0,
                self.current_capital,
                self.maximum_allowed_stake,
            )
        return RiskCheck(
            True, "DATA_OK", 0.0, self.current_capital, self.maximum_allowed_stake
        )

    def check_stake(
        self,
        stake: float,
        *,
        data_available: bool = True,
        data_stale: bool = False,
        data_valid: bool = True,
    ) -> RiskCheck:
        """Check a prospective fixed stake, including worst-case loss limits."""

        data_check = self.check_data(data_available, data_stale, data_valid)
        if not data_check.allowed:
            return data_check
        if not self.limits.has_explicit_limit:
            return RiskCheck(
                False, "MISSING_EXPLICIT_RISK_LIMITS", stake, self.current_capital, None
            )
        if self.is_stopped:
            return RiskCheck(
                False,
                self.stopped_reason or "RISK_STOPPED",
                stake,
                self.current_capital,
                self.maximum_allowed_stake,
            )
        if not math.isfinite(stake) or stake <= 0:
            return RiskCheck(
                False,
                "INVALID_STAKE",
                stake,
                self.current_capital,
                self.maximum_allowed_stake,
            )

        maximum = self.maximum_allowed_stake
        if maximum is not None and stake > maximum + 1e-12:
            return RiskCheck(
                False, "STAKE_LIMIT_EXCEEDED", stake, self.current_capital, maximum
            )
        if (
            self.last_result is not None
            and self.last_result < 0
            and stake > self.last_stake + 1e-12
        ):
            return RiskCheck(
                False, "STAKE_INCREASE_AFTER_LOSS", stake, self.current_capital, maximum
            )
        if (
            self.limits.max_daily_loss is not None
            and self.daily_loss + stake > self.limits.max_daily_loss + 1e-12
        ):
            return RiskCheck(
                False, "MAX_DAILY_LOSS_EXCEEDED", stake, self.current_capital, maximum
            )
        if (
            self.limits.max_drawdown is not None
            and self.drawdown + stake > self.limits.max_drawdown + 1e-12
        ):
            return RiskCheck(
                False, "MAX_DRAWDOWN_EXCEEDED", stake, self.current_capital, maximum
            )
        if (
            self.limits.reserve is not None
            and self.current_capital - stake < self.limits.reserve - 1e-12
        ):
            return RiskCheck(
                False, "RESERVE_VIOLATION", stake, self.current_capital, maximum
            )
        return RiskCheck(True, "RISK_LIMITS_OK", stake, self.current_capital, maximum)

    def proposed_stake(
        self, fixed_stake: float | None = None, stake_fraction: float | None = None
    ) -> float | None:
        """Resolve fixed or current-capital fraction without progression or Kelly sizing."""

        if (fixed_stake is None) == (stake_fraction is None):
            raise ValueError("provide exactly one of fixed_stake or stake_fraction")
        if fixed_stake is not None:
            stake = fixed_stake
        else:
            if stake_fraction is None or not 0.0 < stake_fraction <= 1.0:
                raise ValueError("stake_fraction must be in (0, 1]")
            stake = self.current_capital * stake_fraction
        if self.last_result is not None and self.last_result < 0:
            stake = min(stake, self.last_stake)
        return stake

    def record_settlement(self, net_result: float, stake: float) -> None:
        """Settle an already-placed paper bet after its outcome is known."""

        if not math.isfinite(net_result) or not math.isfinite(stake) or stake <= 0:
            raise ValueError(
                "settlement result and stake must be finite; stake must be positive"
            )
        self.current_capital += net_result
        self.peak_capital = max(self.peak_capital, self.current_capital)
        self.daily_loss += max(0.0, -net_result)
        self.last_stake = stake
        self.last_result = net_result
        if self.current_capital <= 0:
            self.stopped_reason = "BANKROLL_EXHAUSTED"
        elif (
            self.limits.reserve is not None
            and self.current_capital <= self.limits.reserve
        ):
            self.stopped_reason = "RESERVE_REACHED"
        elif (
            self.limits.max_daily_loss is not None
            and self.daily_loss >= self.limits.max_daily_loss
        ):
            self.stopped_reason = "MAX_DAILY_LOSS_REACHED"
        elif (
            self.limits.max_drawdown is not None
            and self.drawdown >= self.limits.max_drawdown
        ):
            self.stopped_reason = "MAX_DRAWDOWN_REACHED"

    def summary(self) -> dict[str, float | str | None]:
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "peak_capital": self.peak_capital,
            "daily_loss": self.daily_loss,
            "drawdown": self.drawdown,
            "last_stake": self.last_stake,
            "stopped_reason": self.stopped_reason,
        }
