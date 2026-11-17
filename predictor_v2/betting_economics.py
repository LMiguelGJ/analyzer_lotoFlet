"""Exact payout arithmetic for the approved 50-number paper contract."""

from __future__ import annotations

from dataclasses import dataclass

TOTAL_STAKE = 50.0
GROSS_PAYOUT = 70.0
NET_WIN = 20.0
NET_LOSS = -50.0
B = 0.4
BREAK_EVEN_PROBABILITY = 1.0 / (1.0 + B)


@dataclass(frozen=True)
class BetEconomics:
    point_probability: float
    stake: float
    gross_payout: float
    net_win: float
    net_loss: float
    odds_b: float
    break_even_probability: float
    expected_value: float
    negative_expected_value: bool
    warning: str | None


def economics_for_probability(
    point_probability: float,
    stake: float = TOTAL_STAKE,
    gross_multiple: float = 1.4,
) -> BetEconomics:
    """Calculate EV for a fixed-risk paper stake; no staking progression is used."""

    probability = float(point_probability)
    if not 0.0 <= probability <= 1.0:
        raise ValueError("point_probability must be between 0 and 1")
    if stake <= 0 or gross_multiple <= 1.0:
        raise ValueError("stake must be positive and gross_multiple must exceed 1")
    gross_payout = stake * gross_multiple
    net_win = gross_payout - stake
    net_loss = -stake
    odds_b = net_win / stake
    break_even = 1.0 / (1.0 + odds_b)
    expected_value = probability * net_win + (1.0 - probability) * net_loss
    negative = expected_value < 0.0
    warning = "NEGATIVE_EXPECTED_VALUE" if negative else None
    return BetEconomics(
        point_probability=probability,
        stake=stake,
        gross_payout=gross_payout,
        net_win=net_win,
        net_loss=net_loss,
        odds_b=odds_b,
        break_even_probability=break_even,
        expected_value=expected_value,
        negative_expected_value=negative,
        warning=warning,
    )


def expected_value(point_probability: float, stake: float = TOTAL_STAKE) -> float:
    """Convenience wrapper for the approved 70 gross / 50 stake contract."""

    return economics_for_probability(point_probability, stake=stake).expected_value
