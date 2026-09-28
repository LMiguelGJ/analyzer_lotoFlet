"""Validate frozen inputs and replay exactly one historical scenario."""

import argparse
import hashlib
import sys
from pathlib import Path

from quiniela_compare import historical_scenario, ranking_context
from quiniela_sim import load_validated_history

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "chance_express_history.json"
RANKINGS = ROOT / "repo_ref/reports/chance_rank_v1/predictions/pos1.npz"
HISTORY_SHA256 = "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711"
RANKINGS_SHA256 = "b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d"
CAPITAL = 2000
GOAL = 2800


def verify_input(path, expected):
    """Reject missing or changed inputs before either is loaded."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Falta la entrada compartida: {path}") from exc
    if digest.hexdigest() != expected:
        raise ValueError(f"SHA-256 distinto en {path}: esperado {expected}, "
                         f"obtenido {digest.hexdigest()}")


def _number(value, digits=1):
    return "—" if value is None else f"{value:.{digits}f}"


def _percent(value):
    return "—" if value is None else _number(value * 100)


def _show(system, k, style, context, history, row):
    print(f"Sistema: {system}; k: {k}; Apuesta: {style}; Modo: all")
    print(f"Capital: RD${CAPITAL}; meta de saldo: RD${GOAL}")
    print(f"Historial: {HISTORY} | SHA-256: {HISTORY_SHA256}")
    print(f"Rankings: {RANKINGS} | SHA-256: {RANKINGS_SHA256}")
    print(f"Población común: {len(context.row_ids)} sorteos evaluables de "
          f"{history.n} históricos; {context.first} a {context.last}; "
          f"{int(context.fold_id[-1]) + 1} folds; {context.gaps} huecos sin apuesta")
    print(f"Completas: {row['completed']}; Inconclusas: {row['incomplete']}; "
          f"Sesiones iniciadas: {row['sessions_total']}")
    print(f"Meta: {row['goal_count']}/{row['completed']} ({_percent(row['goal_rate'])}%)")
    print(f"Quiebre: {row['ruin_count']}/{row['completed']} "
          f"({_percent(row['ruin_rate'])}%)")
    ci = row["goal_wilson95"]
    interval = "—" if ci is None else f"{_percent(ci[0])}%–{_percent(ci[1])}%"
    print(f"Wilson 95% descriptivo (meta, completas): {interval}")
    net = "—" if row["mean_net"] is None else f"{row['mean_net']:+.1f}"
    print(f"Neto medio: RD${net}; "
          f"Saldo final medio: RD${_number(row['mean_final_balance'])}")
    print(f"Mediana/p90 de sorteos apostados por sesión completa: "
          f"{_number(row['median_steps'])}/{_number(row['p90_steps'])}")
    print(f"Ventana completa incluida cola: apostado RD${row['total_stake']}; "
          f"cobrado RD${row['total_paid']}; neto RD${row['total_net']}; "
          f"sorteos apostados {row['total_steps']}")
    print("Contrafactual histórico con datos reutilizados: sesiones inconclusas "
          "excluidas de tasas y medias de completas, pero incluidas en totales "
          "de ventana. No garantiza resultados futuros.")


def run(system, k, style, argv=None):
    """No selectors or tunable parameters: a launcher fixes the exact row."""
    parser = argparse.ArgumentParser(description=(
        "Reproduce un escenario histórico de Quiniela: capital 2000, meta 2800, "
        "pagos acumulados. No escribe archivos."))
    parser.parse_args(argv)
    verify_input(HISTORY, HISTORY_SHA256)
    verify_input(RANKINGS, RANKINGS_SHA256)
    history = load_validated_history(HISTORY)
    context = ranking_context(history, RANKINGS)
    row = historical_scenario(history, RANKINGS, system, k, style, mode="all",
                              context=context, capital=CAPITAL, goal=GOAL)
    _show(system, k, style, context, history, row)
    return 0


def main(system, k, style, argv=None):
    try:
        return run(system, k, style, argv)
    except (OSError, ValueError) as exc:
        print(f"No se pudo reproducir el escenario: {exc}", file=sys.stderr)
        return 1
