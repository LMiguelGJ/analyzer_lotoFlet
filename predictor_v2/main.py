"""Command-line entry point for backtest, forecast, and safe paper modes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .betting_economics import economics_for_probability
from .data_loader import DataLoadError, load_flat_json
from .data_validator import validate_numbers
from .decision_policy import PaperPolicyConfig, decide_paper
from .monte_carlo import run_monte_carlo
from .paper_trading import PaperTrader
from .report_generator import (
    render_data_quality,
    render_forecast,
    render_monte_carlo,
    render_paper,
    render_walk_forward,
)
from .risk_manager import RiskLimits
from .walk_forward import WalkForwardConfig, WalkForwardEngine


def default_data_path() -> Path:
    """Resolve the existing data file from datos/ under the repository root, not the cwd."""

    return Path(__file__).resolve().parents[1] / "datos" / "loteka_numbers.json"


def _add_data_and_walk_forward_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data",
        type=Path,
        default=default_data_path(),
        help="flat loteka_numbers.json path (default: datos/loteka_numbers.json)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1000,
        help="past observations before scoring (default: 1000)",
    )
    parser.add_argument(
        "--development-fraction",
        type=float,
        default=0.60,
        help="chronological development fraction",
    )
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.20,
        help="chronological validation fraction",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="predictor_v2",
        description=(
            "Transparent PAR/IMPAR walk-forward predictor with console-only paper simulation. "
            "No real-money execution is implemented."
        ),
    )
    subparsers = parser.add_subparsers(dest="mode")

    backtest = subparsers.add_parser(
        "backtest",
        help="run chronological development/validation/final-test evaluation",
        description="Run strict prequential backtesting and print metrics, calibration, and baselines.",
    )
    _add_data_and_walk_forward_options(backtest)

    forecast = subparsers.add_parser(
        "forecast",
        help="show the current next-target forecast and payout economics",
        description="Fit candidates chronologically, select before final test, then forecast the next target.",
    )
    _add_data_and_walk_forward_options(forecast)

    paper = subparsers.add_parser(
        "paper",
        help="settle an in-memory historical paper ledger under explicit limits",
        description=(
            "Simulate historical paper decisions only. Missing bankroll/stake/limit settings safely produce NO_BET. "
            "The >50%% trigger is exploratory and can have negative expected value."
        ),
    )
    _add_data_and_walk_forward_options(paper)
    paper.add_argument(
        "--bankroll", type=float, help="required explicit starting paper bankroll"
    )
    stake_group = paper.add_mutually_exclusive_group()
    stake_group.add_argument(
        "--stake", type=float, help="explicit fixed stake per paper bet"
    )
    stake_group.add_argument(
        "--stake-fraction",
        type=float,
        help="explicit fraction of current capital per paper bet",
    )
    paper.add_argument("--max-stake", type=float, help="manual absolute stake cap")
    paper.add_argument(
        "--max-stake-fraction",
        type=float,
        help="manual stake cap as fraction of starting bankroll",
    )
    paper.add_argument(
        "--max-daily-loss", type=float, help="manual session/day loss cap"
    )
    paper.add_argument(
        "--max-drawdown", type=float, help="manual peak-to-trough drawdown cap"
    )
    paper.add_argument(
        "--reserve",
        type=float,
        help="manual capital reserve that cannot be staked through",
    )

    monte_carlo = subparsers.add_parser(
        "monte_carlo",
        help="run fixed-risk console-only Monte Carlo scenarios",
        description=(
            "Run exploratory fixed-stake or fixed-fraction scenarios. Explicit bankroll, one stake setting, "
            "and at least one manual risk limit are required; no Kelly, martingale, or progression is used."
        ),
    )
    monte_carlo.add_argument(
        "--bankroll", type=float, required=True, help="explicit starting bankroll"
    )
    monte_carlo.add_argument(
        "--estimated-probability",
        type=float,
        required=True,
        help="estimated probability for the selected side",
    )
    stake_group = monte_carlo.add_mutually_exclusive_group(required=True)
    stake_group.add_argument(
        "--stake", type=float, help="explicit fixed stake per simulated bet"
    )
    stake_group.add_argument(
        "--stake-fraction",
        type=float,
        help="explicit fraction of current capital per simulated bet",
    )
    monte_carlo.add_argument(
        "--max-stake", type=float, help="manual absolute stake cap"
    )
    monte_carlo.add_argument(
        "--max-stake-fraction",
        type=float,
        help="manual stake cap as a fraction of starting bankroll",
    )
    monte_carlo.add_argument(
        "--max-daily-loss", type=float, help="manual daily loss cap"
    )
    monte_carlo.add_argument(
        "--max-drawdown", type=float, help="manual peak-to-trough drawdown cap"
    )
    monte_carlo.add_argument("--reserve", type=float, help="manual capital reserve")
    monte_carlo.add_argument(
        "--paths", type=int, default=1000, help="number of simulated paths"
    )
    monte_carlo.add_argument(
        "--horizon", type=int, default=100, help="periods per path"
    )
    monte_carlo.add_argument(
        "--seed", type=int, default=12345, help="deterministic random seed"
    )
    monte_carlo.add_argument(
        "--null-probability",
        type=float,
        default=0.5,
        help="null probability for comparison (default: 0.5)",
    )
    return parser


def _load_data(path: Path):
    loaded = load_flat_json(path)
    validation = validate_numbers(loaded.numbers)
    if not validation.ok:
        first = validation.issues[0] if validation.issues else None
        detail = f" ({first.code}: {first.message})" if first else ""
        raise ValueError(f"no usable normalized data{detail}")
    return loaded


def _run_walk_forward(args: argparse.Namespace, *, retain_test_predictions: bool):
    loaded = _load_data(args.data)
    config = WalkForwardConfig(
        warmup=args.warmup,
        development_fraction=args.development_fraction,
        validation_fraction=args.validation_fraction,
        retain_test_predictions=retain_test_predictions,
    )
    result = WalkForwardEngine(config=config).run(loaded.numbers)
    return loaded, result


def _paper_config(args: argparse.Namespace) -> PaperPolicyConfig:
    return PaperPolicyConfig(
        bankroll=args.bankroll,
        fixed_stake=args.stake,
        stake_fraction=args.stake_fraction,
        max_stake=args.max_stake,
        max_stake_fraction=args.max_stake_fraction,
        max_daily_loss=args.max_daily_loss,
        max_drawdown=args.max_drawdown,
        reserve=args.reserve,
    )


def run_monte_carlo_mode(args: argparse.Namespace) -> int:
    limits = RiskLimits(
        max_stake=args.max_stake,
        max_stake_fraction=args.max_stake_fraction,
        max_daily_loss=args.max_daily_loss,
        max_drawdown=args.max_drawdown,
        reserve=args.reserve,
    )
    if not limits.has_explicit_limit:
        print(
            "MONTE CARLO NO_BET: provide at least one explicit manual risk limit "
            "(max-stake, max-stake-fraction, max-daily-loss, max-drawdown, or reserve)."
        )
        return 0
    report = run_monte_carlo(
        initial_capital=args.bankroll,
        estimated_probability=args.estimated_probability,
        stake=args.stake,
        stake_fraction=args.stake_fraction,
        paths=args.paths,
        horizon=args.horizon,
        seed=args.seed,
        null_probability=args.null_probability,
        limits=limits,
    )
    print(render_monte_carlo(report))
    return 0


def run_backtest(args: argparse.Namespace) -> int:
    loaded, result = _run_walk_forward(args, retain_test_predictions=False)
    print(render_data_quality(loaded))
    print(render_walk_forward(result))
    return 0


def run_forecast(args: argparse.Namespace) -> int:
    loaded, result = _run_walk_forward(args, retain_test_predictions=False)
    economics = economics_for_probability(result.forecast.point_probability)
    print(render_data_quality(loaded))
    print(render_walk_forward(result))
    print(render_forecast(result.forecast, economics))
    return 0


def run_paper(args: argparse.Namespace) -> int:
    loaded, result = _run_walk_forward(args, retain_test_predictions=True)
    config = _paper_config(args)
    # Raw input quality is a safety input: any dropped/invalid record prevents bets.
    data_valid = loaded.summary.invalid_records == 0
    trader = PaperTrader(config, data_valid=data_valid, data_stale=False)
    ledger = trader.simulate(
        (
            (index, side, probability, actual_side)
            for index, _number, side, probability, actual_side, _support in result.test_predictions
        )
    )
    manager = trader.risk_manager
    current_decision = decide_paper(
        side=result.forecast.side,
        point_probability=result.forecast.point_probability,
        config=config,
        risk_manager=manager,
        data_available=True,
        data_stale=False,
        data_valid=data_valid,
    )
    print(render_data_quality(loaded))
    print(render_walk_forward(result))
    print(render_paper(ledger, manager, current_decision))
    print(
        render_forecast(
            result.forecast,
            economics_for_probability(result.forecast.point_probability),
        )
    )
    if current_decision.warnings:
        print("PAPER WARNING: " + ",".join(current_decision.warnings))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.mode is None:
        parser.print_help()
        return 0
    try:
        if args.mode == "backtest":
            return run_backtest(args)
        if args.mode == "forecast":
            return run_forecast(args)
        if args.mode == "paper":
            return run_paper(args)
        if args.mode == "monte_carlo":
            return run_monte_carlo_mode(args)
        parser.error(f"unknown mode: {args.mode}")
    except (DataLoadError, ValueError, OSError) as exc:
        print(f"predictor_v2 safely stopped: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
