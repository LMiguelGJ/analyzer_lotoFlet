"""The intentionally exploratory >50% paper-decision policy and safety gate."""

from __future__ import annotations

from dataclasses import dataclass

from .betting_economics import BetEconomics, economics_for_probability
from .risk_manager import RiskCheck, RiskLimits, RiskManager


@dataclass(frozen=True)
class PaperPolicyConfig:
    """Explicit paper settings; no bankroll, stake, or limits are invented."""

    bankroll: float | None = None
    fixed_stake: float | None = None
    stake_fraction: float | None = None
    max_stake: float | None = None
    max_stake_fraction: float | None = None
    max_daily_loss: float | None = None
    max_drawdown: float | None = None
    reserve: float | None = None

    @property
    def has_stake_setting(self) -> bool:
        return (self.fixed_stake is not None) ^ (self.stake_fraction is not None)

    @property
    def limits(self) -> RiskLimits:
        return RiskLimits(
            max_stake=self.max_stake,
            max_stake_fraction=self.max_stake_fraction,
            max_daily_loss=self.max_daily_loss,
            max_drawdown=self.max_drawdown,
            reserve=self.reserve,
        )

    @property
    def explicit(self) -> bool:
        """Require bankroll, exactly one stake setting, and one capital limit."""

        return (
            self.bankroll is not None
            and self.has_stake_setting
            and self.limits.has_explicit_limit
        )

    def validate(self) -> None:
        if self.fixed_stake is not None and self.fixed_stake <= 0:
            raise ValueError("fixed_stake must be positive")
        if self.stake_fraction is not None and not 0.0 < self.stake_fraction <= 1.0:
            raise ValueError("stake_fraction must be in (0, 1]")
        if self.bankroll is not None and self.bankroll <= 0:
            raise ValueError("bankroll must be positive")
        self.limits.validate()


def qualifies_by_point_probability(
    point_probability: float, threshold: float = 0.5
) -> bool:
    """F3 trigger: strictly greater than 50%, never greater-than-or-equal."""

    probability = float(point_probability)
    if not 0.0 <= probability <= 1.0:
        raise ValueError("point_probability must be between 0 and 1")
    if threshold != 0.5:
        raise ValueError("the approved exploratory policy threshold is fixed at 0.5")
    return probability > 0.5


@dataclass(frozen=True)
class PaperDecision:
    action: str
    side: str
    point_probability: float
    stake: float | None
    economics: BetEconomics | None
    reason: str
    warnings: tuple[str, ...]
    risk_check: RiskCheck | None

    @property
    def is_bet(self) -> bool:
        return self.action == "BET"


def build_risk_manager(config: PaperPolicyConfig) -> RiskManager | None:
    """Build only from explicit CLI-equivalent inputs; return ``None`` safely otherwise."""

    config.validate()
    if config.bankroll is None:
        return None
    return RiskManager(initial_capital=config.bankroll, limits=config.limits)


def decide_paper(
    side: str,
    point_probability: float,
    config: PaperPolicyConfig,
    risk_manager: RiskManager | None = None,
    *,
    data_available: bool = True,
    data_stale: bool = False,
    data_valid: bool = True,
) -> PaperDecision:
    """Return BET/NO_BET without ever executing or settling a real transaction."""

    probability = float(point_probability)
    if side not in {"PAR", "IMPAR"}:
        raise ValueError("side must be PAR or IMPAR")
    config.validate()
    warnings: list[str] = []
    if not qualifies_by_point_probability(probability):
        return PaperDecision(
            action="NO_BET",
            side=side,
            point_probability=probability,
            stake=None,
            economics=None,
            reason="POINT_PROBABILITY_NOT_GREATER_THAN_50_PERCENT",
            warnings=tuple(warnings),
            risk_check=None,
        )
    if not config.explicit or risk_manager is None:
        return PaperDecision(
            action="NO_BET",
            side=side,
            point_probability=probability,
            stake=None,
            economics=None,
            reason="MISSING_EXPLICIT_RISK_CONFIGURATION",
            warnings=tuple(warnings),
            risk_check=None,
        )

    stake = risk_manager.proposed_stake(
        fixed_stake=config.fixed_stake,
        stake_fraction=config.stake_fraction,
    )
    if stake is None:
        return PaperDecision(
            action="NO_BET",
            side=side,
            point_probability=probability,
            stake=None,
            economics=None,
            reason="MISSING_EXPLICIT_STAKE",
            warnings=tuple(warnings),
            risk_check=None,
        )
    economics = economics_for_probability(probability, stake=stake)
    if economics.negative_expected_value:
        warnings.append("NEGATIVE_EXPECTED_VALUE")
    risk_check = risk_manager.check_stake(
        stake,
        data_available=data_available,
        data_stale=data_stale,
        data_valid=data_valid,
    )
    if not risk_check.allowed:
        return PaperDecision(
            action="NO_BET",
            side=side,
            point_probability=probability,
            stake=stake,
            economics=economics,
            reason=risk_check.reason,
            warnings=tuple(warnings),
            risk_check=risk_check,
        )
    return PaperDecision(
        action="BET",
        side=side,
        point_probability=probability,
        stake=stake,
        economics=economics,
        reason="POINT_PROBABILITY_GT_50_AND_RISK_OK",
        warnings=tuple(warnings),
        risk_check=risk_check,
    )
