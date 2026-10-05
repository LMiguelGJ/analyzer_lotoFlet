from types import SimpleNamespace

from laboratorio.domain.metrics import financial_metrics


def test_metrics_are_run_scoped_exact_and_round_half_up():
    """B-DOM-032: financial metrics are run-scoped and use half-up rounding."""
    result = SimpleNamespace(
        wagered=3,
        paid=1,
        bets=(
            SimpleNamespace(balance=12),
            SimpleNamespace(balance=7),
            SimpleNamespace(balance=10),
        ),
    )
    assert financial_metrics(result, 10) == {
        "net": -2,
        "return_per_wagered": 0.333333,
        "roi": -0.666667,
        "max_drawdown": 5,
        "metric_scope": "saved_individual_run",
        "ratio_rounding": "decimal-half-up-6",
    }


def test_zero_wagers_have_null_ratios_and_no_nonfinite_values():
    """B-DOM-033: zero wagers yield null ratios and finite metrics."""
    result = SimpleNamespace(wagered=0, paid=0, bets=())
    metrics = financial_metrics(result, 100)
    assert metrics["return_per_wagered"] is None
    assert metrics["roi"] is None
    assert metrics["max_drawdown"] == 0
