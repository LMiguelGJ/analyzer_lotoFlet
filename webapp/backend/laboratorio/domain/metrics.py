"""Pure exact financial metrics for one saved session/result."""

from decimal import ROUND_HALF_UP, Decimal

_QUANTUM = Decimal("0.000001")


def _rounded_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    value = (Decimal(numerator) / Decimal(denominator)).quantize(_QUANTUM, rounding=ROUND_HALF_UP)
    return float(value)


def financial_metrics(result, initial_capital: int) -> dict:
    """Report run-scoped net, ratios and absolute peak-to-trough drawdown.

    Monetary values remain integer units. Ratios use decimal division rounded to
    six places, ROUND_HALF_UP; zero wagers produce JSON null for both ratios.
    """
    balances = [initial_capital, *(bet.balance for bet in result.bets)]
    peak = balances[0]
    max_drawdown = 0
    for balance in balances[1:]:
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
    net = result.paid - result.wagered
    return {
        "net": net,
        "return_per_wagered": _rounded_ratio(result.paid, result.wagered),
        "roi": _rounded_ratio(net, result.wagered),
        "max_drawdown": max_drawdown,
        "metric_scope": "saved_individual_run",
        "ratio_rounding": "decimal-half-up-6",
    }
