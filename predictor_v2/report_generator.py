"""Console-only report rendering for the independent predictor_v2 CLI."""

from __future__ import annotations

from .betting_economics import BetEconomics
from .data_loader import NormalizationResult, format_quality_warnings
from .monte_carlo import MonteCarloReport, MonteCarloScenario
from .paper_trading import PaperLedger
from .risk_manager import RiskManager
from .walk_forward import WalkForwardResult


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.3f}%"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def render_data_quality(result: NormalizationResult) -> str:
    return "DATA QUALITY\n" + format_quality_warnings(result)


def render_economics(economics: BetEconomics) -> str:
    warning = economics.warning or "none"
    return "\n".join(
        (
            "ECONOMICS",
            f"stake={economics.stake:.2f} gross_payout={economics.gross_payout:.2f} "
            f"net_win={economics.net_win:.2f} net_loss={economics.net_loss:.2f}",
            f"b={economics.odds_b:.6f} break_even={_percent(economics.break_even_probability)} "
            f"p={_percent(economics.point_probability)} EV={economics.expected_value:.4f}",
            f"warning={warning}",
        )
    )


def render_forecast(prediction, economics: BetEconomics | None = None) -> str:
    lines = [
        "FORECAST (exploratory; not a real-money instruction)",
        f"model={prediction.model_name} side={prediction.side} "
        f"p(PAR)={_percent(prediction.probability_par)} "
        f"p(IMPAR)={_percent(prediction.probability_impar)}",
        f"point_probability={_percent(prediction.point_probability)} support={prediction.support} "
        f"context={prediction.context}",
    ]
    raw_probability_par = prediction.metadata.get("raw_probability_par")
    raw_probability_impar = prediction.metadata.get("raw_probability_impar")
    raw_point_probability = prediction.metadata.get("raw_point_probability")
    if (
        isinstance(raw_probability_par, (int, float))
        and isinstance(raw_probability_impar, (int, float))
        and isinstance(raw_point_probability, (int, float))
    ):
        lines.append(
            f"raw_p(PAR)={_percent(raw_probability_par)} "
            f"raw_p(IMPAR)={_percent(raw_probability_impar)} "
            f"raw_point_probability={_percent(raw_point_probability)}"
        )
    if economics is not None:
        lines.append(render_economics(economics))
    return "\n".join(lines)


def _render_metric_line(name: str, metrics) -> str:
    p_value = metrics.binomial_test.p_value
    p_value_text = "n/a" if p_value is None else f"{p_value:.4g}"
    return (
        f"{name}: n={metrics.count} acc={_percent(metrics.accuracy)} "
        f"precision_PAR={_percent(metrics.precision_par)} recall_PAR={_percent(metrics.recall_par)} "
        f"F1_PAR={_percent(metrics.f1_par)} Brier={_number(metrics.brier_score)} "
        f"logloss={_number(metrics.log_loss)} p_one_sided={p_value_text}"
    )


def render_walk_forward(result: WalkForwardResult) -> str:
    lines = [
        "WALK-FORWARD BACKTEST",
        f"observations={result.observations} warmup={result.warmup} selected_model={result.selected_model}",
        f"selection={result.selection_reason}",
        "partitions: "
        + ", ".join(f"{part.name}={part.count}" for part in result.partitions),
        "MODEL METRICS (development/validation are exploratory; test is frozen final evaluation)",
    ]
    for split in ("development", "validation", "test"):
        lines.append(f"[{split}]")
        for name, metrics in result.split_metrics[split].items():
            lines.append(_render_metric_line(name, metrics))
    lines.append("BASELINES")
    for split in ("development", "validation", "test"):
        for name, metrics in result.baseline_metrics[split].items():
            lines.append(_render_metric_line(f"{split}/{name}", metrics))
    lines.append(
        f"calibration: fitted={result.calibration_fit.fitted} "
        f"source={result.calibration_fit.source} n={result.calibration_fit.sample_count} "
        f"blocks={result.calibration_fit.block_count}"
    )
    for curve_name, curve in result.calibration_curves.items():
        populated = sum(1 for item in curve if item.count)
        lines.append(
            f"calibration_curve={curve_name} populated_bins={populated}/{len(curve)}"
        )
    lines.append(
        "multiple-comparison note: "
        + result.split_metrics["test"][result.selected_model].multiple_comparison_note
    )
    lines.append(
        "uncertainty note: dependency-free block_bootstrap_accuracy is available; "
        "it is not run by default on the full data stream."
    )
    lines.append(
        "NOTE: no claim of an edge; compare the final test with null and baseline results."
    )
    lines.extend(f"warning: {warning}" for warning in result.warnings)
    return "\n".join(lines)


def render_paper(
    ledger: PaperLedger,
    risk_manager: RiskManager | None,
    current_decision=None,
) -> str:
    lines = [
        "PAPER TRADING ONLY (NO REAL EXECUTION)",
        f"bets={len(ledger.bets)} settled={ledger.settled_count} no_bet={ledger.no_bet_count} "
        f"wins={ledger.win_count} losses={ledger.loss_count} net={ledger.net_result:.2f}",
    ]
    if risk_manager is not None:
        summary = risk_manager.summary()
        current_capital_value = summary.get("current_capital")
        drawdown_value = summary.get("drawdown")
        current_capital = (
            float(current_capital_value)
            if isinstance(current_capital_value, (int, float))
            else 0.0
        )
        drawdown = (
            float(drawdown_value) if isinstance(drawdown_value, (int, float)) else 0.0
        )
        stopped_reason = summary.get("stopped_reason")
        stop_text = stopped_reason if isinstance(stopped_reason, str) else "none"
        lines.append(
            f"capital={current_capital:.2f} drawdown={drawdown:.2f} "
            f"stop_reason={stop_text or 'none'}"
        )
    if current_decision is not None:
        lines.append(
            f"current_decision={current_decision.action} reason={current_decision.reason} "
            f"point_probability={_percent(current_decision.point_probability)}"
        )
        if current_decision.warnings:
            lines.append("current_warnings=" + ",".join(current_decision.warnings))
    if ledger.no_bet_reasons:
        lines.append("no_bet_reasons=" + repr(dict(ledger.no_bet_reasons)))
    historical_warnings: dict[str, int] = {}
    for bet in ledger.bets:
        for warning in bet.warnings:
            historical_warnings[warning] = historical_warnings.get(warning, 0) + 1
    if historical_warnings:
        lines.append("historical_bet_warnings=" + repr(historical_warnings))
    lines.append(
        "Every historical BET was settled only after its recorded outcome was revealed."
    )
    return "\n".join(lines)


def _render_scenario(scenario: MonteCarloScenario) -> str:
    return (
        f"{scenario.name}: p_true={_percent(scenario.true_probability)} paths={scenario.paths} "
        f"horizon={scenario.horizon} mean_final={scenario.mean_final_capital:.2f} "
        f"median_final={scenario.median_final_capital:.2f} "
        f"growth/period={_percent(scenario.mean_per_period_growth)} "
        f"mean_max_drawdown={scenario.mean_max_drawdown:.2f} "
        f"volatility={scenario.volatility_final_capital:.2f} "
        f"stop_rate={_percent(scenario.ruin_or_stop_rate)} "
        f"mean_losing_streak={scenario.mean_losing_streak:.2f} "
        f"worst_losing_streak={scenario.worst_losing_streak}\n"
        f"  note: {scenario.note}"
    )


def render_monte_carlo(report: MonteCarloReport) -> str:
    return "\n".join(
        (
            "MONTE CARLO (fixed-risk exploratory scenarios)",
            f"seed={report.seed} estimated_p={_percent(report.estimated_probability)} "
            f"null_p={_percent(report.null_probability)}",
            _render_scenario(report.no_bet),
            _render_scenario(report.configured_under_null),
            _render_scenario(report.configured_under_estimated),
            f"note: {report.policy_note}",
        )
    )
