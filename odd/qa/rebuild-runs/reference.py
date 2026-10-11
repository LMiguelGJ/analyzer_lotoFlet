"""Independent legacy-engine reference export for the rebuild acceptance harness.

Run from webapp/backend with py -3.14 and an isolated LABORATORIO_DATA_DIR.
Writes only into the caller-provided temporary output directory.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, cast

from laboratorio.api.backtests import _selection_rows
from laboratorio.domain.backtest import BacktestConfig, run_backtest
from laboratorio.domain.contracts import StakingStyle
from laboratorio.domain.selection import blend_order, parity_numbers, parity_votes
from laboratorio.domain.session import Draw
from laboratorio.engine.adapter import open_lab_data
from laboratorio.settings import Settings


def legacy_config(*, positions: int, prizes: tuple[int, ...], coverage: int) -> BacktestConfig:
    return BacktestConfig(
        capital=2000,
        goal=2800,
        numbers=100,
        positions=positions,
        prizes=prizes,
        minimum_stake=1,
        coverage=coverage,
        staking=StakingStyle.FLAT,
    )


def totals(result) -> dict:
    return {
        "sessions": len(result.sessions),
        "goal": result.reached_goal,
        "ruin": result.quiebre,
        "limit": 0,
        "incomplete": result.incomplete,
        "bets": result.window.bets,
        "wagered": result.window.wagered,
        "paid": result.window.paid,
        "net": result.window.paid - result.window.wagered,
        "return_pct": float(
            (Decimal(100 * (result.window.paid - result.window.wagered))
             / Decimal(result.window.wagered)).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        ) if result.window.wagered else None,
        "mean_net_closed": result.neto_medio,
    }


def aggregate_checks(result) -> dict:
    return {
        "session_bets": sum(len(session.bets) for session in result.sessions),
        "session_wagered": sum(bet.wagered for s in result.sessions for bet in s.bets),
        "session_paid": sum(bet.paid for s in result.sessions for bet in s.bets),
        "session_final_balances": sum(s.final_balance for s in result.sessions),
        "first_session": None if not result.sessions else {
            "outcome": result.sessions[0].outcome,
            "bets": len(result.sessions[0].bets),
            "final_balance": result.sessions[0].final_balance,
            "first_bet": {
                "label": result.sessions[0].bets[0].label,
                "numbers": list(result.sessions[0].bets[0].numbers),
                "results": list(result.sessions[0].bets[0].results),
                "wagered": result.sessions[0].bets[0].wagered,
                "paid": result.sessions[0].bets[0].paid,
                "balance": result.sessions[0].bets[0].balance,
            } if result.sessions[0].bets else None,
        },
    }


def parity_all_history_rows(data, *, coverage: int) -> list[Draw]:
    """Independent parity rows for every historical draw, including unranked draws."""
    history = data.history
    votes = parity_votes(history.nums[:, 0])
    if len(votes) != len(history.labels):
        raise RuntimeError("parity vote count is not aligned with historical labels")
    return [
        Draw(
            label,
            int(history.minutes[index]),
            cast(Any, tuple(int(number) for number in history.nums[index, :5])),
            tuple(int(number) for number in parity_numbers(int(votes[index]))[:coverage]),
        )
        for index, label in enumerate(history.labels)
    ]


def mixed_rows(data) -> list[Draw]:
    history, rankings = data.history, data.rankings
    row_pos = {int(row_id): position for position, row_id in enumerate(rankings.row_ids)}
    transition = rankings.family("transition")
    cold = rankings.family("cold")
    rows = []
    for index, numbers in enumerate(history.nums):
        position = row_pos.get(index)
        order = None
        if position is not None:
            blended = blend_order(
                {"transition": transition[position], "cold": cold[position]},
                {"transition": 60, "cold": 40},
            )
            order = tuple(int(number) for number in blended[:10])
        rows.append(Draw(
            history.labels[index], int(history.minutes[index]),
            cast(Any, tuple(int(number) for number in numbers[:3])), order,
        ))
    return rows


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: reference.py TEMP_OUTPUT_DIRECTORY")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_environment()
    data = open_lab_data(settings)

    mixed = run_backtest(
        legacy_config(positions=3, prizes=(60, 10, 5), coverage=10), mixed_rows(data)
    )
    parity_config = legacy_config(positions=5, prizes=(80, 8, 4, 2, 1), coverage=50)
    all_parity_rows = parity_all_history_rows(data, coverage=50)
    # Keep the established generation/selection path only for the ranked-row golden.
    golden = run_backtest(
        parity_config, _selection_rows(data, "parity", None, 50)
    )
    all_history_parity = run_backtest(parity_config, all_parity_rows)
    try:
        base = json.loads(settings.history_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot parse bundled history at {settings.history_path}: {exc}") from exc
    labels = sorted(
        f"{day} {record['hora']}"
        for day, draws in base["sorteos_por_fecha"].items()
        for record in draws
    )
    last_label = labels[-1]
    last_day = last_label[:10]
    existing_record = next(
        record for record in base["sorteos_por_fecha"][last_day]
        if f"{last_day} {record['hora']}" == last_label
    )
    new_day = (date.fromisoformat(last_day) + timedelta(days=1)).isoformat()
    synthetic = {
        "metadata": {"schema_version": 1, "juego": "Quiniela 80", "origen": "acceptance"},
        "sorteos_por_fecha": {new_day: [{
            "hora": "10:00", "numeros": ["01", "02", "03", "04", "05"]
        }]},
    }
    conflicting = {
        "metadata": {"schema_version": 1, "juego": "Quiniela 80", "origen": "acceptance"},
        "sorteos_por_fecha": {last_day: [{
            "hora": existing_record["hora"],
            "numeros": [f"{(int(value) + 1) % 100:02d}" for value in existing_record["numeros"]],
        }]},
    }
    (output / "synthetic-history.json").write_text(
        json.dumps(synthetic, ensure_ascii=False), encoding="utf-8"
    )
    (output / "conflicting-history.json").write_text(
        json.dumps(conflicting, ensure_ascii=False), encoding="utf-8"
    )

    report = {
        "frozen_history_sha256": data.history.sha256,
        "rankings_sha256": hashlib.sha256(settings.rankings_path.read_bytes()).hexdigest(),
        "draws": len(data.history.labels),
        "ranked_draws": len(data.rankings.row_ids),
        "last_label": last_label,
        "new_label": f"{new_day} 10:00",
        "legacy_mix_three_position_unlimited": {
            "totals": totals(mixed), "accounting": aggregate_checks(mixed),
        },
        "legacy_parity_five_position_flat_golden": {
            "scope": "ranked historical rows only; retained 65,235-row golden",
            "totals": totals(golden),
            "mean_net_closed_scope": {
                "closed_sessions": golden.reached_goal + golden.quiebre,
                "total_sessions": len(golden.sessions),
                "excludes_incomplete_sessions": golden.incomplete,
            },
            "accounting": aggregate_checks(golden),
        },
        "legacy_parity_five_position_flat_all_history_unlimited": {
            "scope": "all chronological history labels, including unranked rows",
            "draws": len(data.history.labels),
            "ranked_draws": len(data.rankings.row_ids),
            "totals": totals(all_history_parity),
            "mean_net_closed_scope": {
                "closed_sessions": all_history_parity.reached_goal + all_history_parity.quiebre,
                "total_sessions": len(all_history_parity.sessions),
                "excludes_incomplete_sessions": all_history_parity.incomplete,
            },
            "accounting": aggregate_checks(all_history_parity),
        },
        "claimed_limited_mix_fixture": {
            "totals": {
                "sessions": 5932, "limit": 5931, "bets": 65235,
            },
            "source": "prior worker report; API result must be checked against these exact claims",
        },
    }
    (output / "reference.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"output": str(output), "reference": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
