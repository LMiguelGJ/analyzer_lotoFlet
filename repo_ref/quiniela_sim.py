"""Causal Quiniela Extraordinaria 80/8/4/2/1 simulation engine.

Chance Express history is a retrospective counterfactual, not verified Rapidita
outcomes. No number-selection method here predicts independent uniform draws.
"""

import argparse
import importlib
import os
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from math import ceil, isfinite, sqrt
from pathlib import Path

import numpy as np

from repo_ref.strategy_tests.rules import QUINIELA80, first_prize_ladder, payout_matrix

CAPITAL = 2000
GOAL = 2800
NUMBERS = 50
MC_SESSIONS = 20_000
SEED = 20260928
LADDER80 = first_prize_ladder(QUINIELA80)
BOLD_DIVISOR = QUINIELA80.prizes[0] - 1
EVENS = np.arange(100) % 2 == 0
ODDS = ~EVENS
_MODES = ("all", "best")
_STRATEGIES = ("flat", "ladder", "bold")


def load_validated_history(path):
    """Delegate chronology and SHA validation to repo_ref without editing it."""
    repo_ref = str(Path(__file__).resolve().parent.parent / "repo_ref")
    if repo_ref not in sys.path:
        sys.path.insert(0, repo_ref)
    data = importlib.import_module("chance_rank.data")
    return data.load_history(path)


class LegacyMarkov:
    """Port of MarkovPY.MarkovPredictor, including tie and back-off behavior."""

    def __init__(self, order=1):
        self.order = order
        self.history = deque(maxlen=order)
        self.counts_runs = {"Par": 0, "Impar": 0}
        self.transitions_by_key = {
            k: defaultdict(lambda: {"Par": 0, "Impar": 0})
            for k in range(1, order + 1)
        }
        self.after_runs = {
            "Par": {"Par": 0, "Impar": 0},
            "Impar": {"Par": 0, "Impar": 0},
        }

    def _state(self, number):
        return "Par" if number % 2 == 0 else "Impar"

    def update(self, number):
        current_state = self._state(number)
        for k in range(1, self.order + 1):
            if len(self.history) >= k:
                key = tuple(list(self.history)[-k:])
                self.transitions_by_key[k][key][current_state] += 1
        if len(self.history) == self.order and all(s == self.history[0] for s in self.history):
            self.after_runs[self.history[0]][current_state] += 1
        self.history.append(current_state)
        if len(self.history) == self.order and all(s == self.history[0] for s in self.history):
            self.counts_runs[self.history[0]] += 1

    def predict_global(self):
        total = sum(self.counts_runs.values())
        if total == 0:
            probs = {"Par": 0.5, "Impar": 0.5}
        else:
            probs = {state: self.counts_runs[state] / total for state in ("Par", "Impar")}
        return max(probs, key=lambda state: probs[state]), probs

    def predict_with_context(self):
        hist_list = list(self.history)
        for k in range(self.order, 0, -1):
            if len(hist_list) >= k:
                key = tuple(hist_list[-k:])
                counts = self.transitions_by_key[k].get(key)
                if counts:
                    total = counts["Par"] + counts["Impar"]
                    if total > 0:
                        probs = {"Par": counts["Par"] / total,
                                 "Impar": counts["Impar"] / total}
                        return k, key, max(probs, key=lambda state: probs[state]), probs
        predicted, probs = self.predict_global()
        return 0, (), predicted, probs

    def predict_combined(self, method="weighted", weight_context=0.7):
        pred_global, probs_global = self.predict_global()
        k_used, _, pred_ctx, probs_ctx = self.predict_with_context()
        if method == "weighted":
            combined = {
                state: weight_context * probs_ctx[state] +
                (1 - weight_context) * probs_global[state]
                for state in ("Par", "Impar")
            }
            return max(combined, key=lambda state: combined[state]), combined, "ponderada"
        if method == "conservative":
            if max(probs_ctx.values()) >= max(probs_global.values()):
                return pred_ctx, probs_ctx, "contexto (mayor confianza)"
            return pred_global, probs_global, "global (mayor confianza)"
        if method == "aggressive":
            if min(probs_ctx.values()) >= min(probs_global.values()):
                return pred_ctx, probs_ctx, "contexto (más segura)"
            return pred_global, probs_global, "global (más segura)"
        if k_used > 0:
            return pred_ctx, probs_ctx, "contexto (por defecto)"
        return pred_global, probs_global, "global (por defecto)"

    def combined_vote(self):
        predictions = [self.predict_combined(method) for method in
                       ("weighted", "conservative", "aggressive")]
        picks = [prediction[0] for prediction in predictions]
        if picks.count("Par") > picks.count("Impar"):
            return "Par"
        if picks.count("Impar") > picks.count("Par"):
            return "Impar"
        return ("Par" if sum(p[1]["Par"] for p in predictions) >
                sum(p[1]["Impar"] for p in predictions) else "Impar")


def consensus_parity(first_numbers):
    """27 votes per draw, before updating any model with that draw (0=even)."""
    models = [LegacyMarkov(order) for order in range(1, 10)]
    votes = np.empty(len(first_numbers), dtype=np.int8)
    for t, number in enumerate(first_numbers):
        ballot = []
        for model in models:
            ballot.extend((model.predict_global()[0], model.predict_with_context()[2],
                           model.combined_vote()))
        votes[t] = 0 if ballot.count("Par") > ballot.count("Impar") else 1
        for model in models:
            model.update(int(number))
    return votes


def historical_selections(nums, parity, seed=SEED):
    """One parity mask, fresh 50 distinct random numbers, and one bold number per draw."""
    if len(nums) != len(parity):
        raise ValueError("parity length must equal number of draws")
    rng_cover = np.random.default_rng(seed + 1)
    rng_bold = np.random.default_rng(seed + 2)
    cover = np.zeros((len(nums), 100), dtype=bool)
    for row in cover:
        row[rng_cover.choice(100, NUMBERS, replace=False)] = True
    return {
        "parity": np.where(np.asarray(parity)[:, None] == 0, EVENS, ODDS),
        "random50": cover,
        "bold_number": rng_bold.integers(0, 100, size=len(nums)),
    }


def draw_payments(nums, mode, mask=None, numbers=None):
    """Per-draw covered and single-number payments, pesos per peso on each number."""
    if mode not in _MODES:
        raise ValueError(f"unknown settlement mode: {mode}")
    matrix = payout_matrix(np.asarray(nums), mode, QUINIELA80)
    covered = None if mask is None else (matrix * mask).sum(axis=1)
    single = None if numbers is None else matrix[np.arange(len(nums)), numbers]
    return covered, single


@dataclass(frozen=True)
class BalanceState:
    balance: int
    round: int = 0


@dataclass(frozen=True)
class Session:
    reached: bool
    ruined: bool
    steps: int
    wagered: int
    paid: int
    final_balance: int


@dataclass(frozen=True)
class Metrics:
    sessions: int
    p_goal: float | None
    goal_wilson95: tuple[float, float] | None
    p_ruin: float | None
    mean_net: float | None
    mean_wagered: float | None
    return_per_peso: float | None
    median_steps: float | None
    p90_steps: float | None
    inconclusive: int


def _stake(strategy, state, goal):
    if strategy == "flat":
        return NUMBERS, 1
    if strategy == "ladder":
        per_number = LADDER80[state.round]
        return NUMBERS * per_number, per_number
    if strategy == "bold":
        return min(state.balance, max(0, ceil((goal - state.balance) / BOLD_DIVISOR))), 1
    raise ValueError(f"unknown strategy: {strategy}")


def _terminal(strategy, balance, round_index, goal):
    if balance >= goal:
        return "goal"
    if strategy == "bold":
        return "ruin" if balance <= 0 else None
    next_stake = NUMBERS if strategy == "flat" else NUMBERS * LADDER80[round_index]
    return "ruin" if balance < next_stake else None


def step(strategy, state, cover_pay=0, single_pay=0, first_hit=False, goal=GOAL):
    """Settle one draw; ruin is inability to finance the *next* stake."""
    if goal <= 0:
        raise ValueError("goal must be positive")
    if state.balance >= goal:
        return 0, 0, state, "goal"
    stake, per_number = _stake(strategy, state, goal)
    if stake == 0 or state.balance < stake:
        return 0, 0, state, "ruin"
    paid = stake * single_pay if strategy == "bold" else per_number * cover_pay
    balance = state.balance + paid - stake
    round_index = state.round
    if strategy == "ladder":
        round_index = 0 if first_hit else (round_index + 1) % len(LADDER80)
    new_state = BalanceState(int(balance), round_index)
    return stake, paid, new_state, _terminal(strategy, balance, round_index, goal)


def replay_back_to_back(strategy, cover_pay, single_pay=None, first_hits=None,
                        capital=CAPITAL, goal=GOAL):
    """Partition chronological draws into nonoverlapping terminal sessions.

    The trailing unfinished session is retained as neither reached nor ruined.
    """
    if capital <= 0 or goal <= capital:
        raise ValueError("capital must be positive and goal must exceed capital")
    n = len(cover_pay)
    if single_pay is None:
        single_pay = np.zeros(n, dtype=np.int64)
    if first_hits is None:
        first_hits = np.zeros(n, dtype=bool)
    if len(single_pay) != n or len(first_hits) != n:
        raise ValueError("payment and first-hit arrays must match")
    sessions = []
    state = BalanceState(capital)
    steps = wagered = paid = 0
    for t in range(n):
        stake, winnings, state, outcome = step(
            strategy, state, cover_pay[t], single_pay[t], first_hits[t], goal
        )
        if stake:
            steps += 1
            wagered += stake
            paid += winnings
        if outcome:
            sessions.append(Session(outcome == "goal", outcome == "ruin", steps,
                                    wagered, paid, state.balance))
            if not steps:
                return sessions  # initial stake unaffordable: no draw can change this
            state = BalanceState(capital)
            steps = wagered = paid = 0
    if steps:
        sessions.append(Session(False, False, steps, wagered, paid, state.balance))
    return sessions


def _sample_payments(draws, mode, strategy):
    """Match payout_matrix without allocating a (sessions, 100) matrix per step."""
    selected = draws == 0 if strategy == "bold" else (draws % 2 == 0)
    if mode == "best":
        # Earlier positions have higher prizes. Each distinct number pays once.
        for pos in range(1, 5):
            selected[:, pos] &= ~np.any(draws[:, :pos] == draws[:, pos, None], axis=1)
    return (selected * np.asarray(QUINIELA80.prizes)).sum(axis=1)


def simulate(strategy, mode="all", sessions=MC_SESSIONS, seed=SEED,
             capital=CAPITAL, goal=GOAL, max_steps=2_000_000):
    """Independent uniform 5-position draws; fixed choices by distributional symmetry."""
    if strategy not in _STRATEGIES or mode not in _MODES:
        raise ValueError("unknown strategy or settlement mode")
    if sessions <= 0 or capital <= 0 or goal <= capital or max_steps <= 0:
        raise ValueError("sessions, capital and max_steps must be positive; goal > capital")
    rng = np.random.default_rng(seed + _STRATEGIES.index(strategy) * 2 + _MODES.index(mode))
    balance = np.full(sessions, capital, dtype=np.int64)
    rounds = np.zeros(sessions, dtype=np.int64)
    steps = np.zeros(sessions, dtype=np.int64)
    wagered = np.zeros(sessions, dtype=np.int64)
    paid = np.zeros(sessions, dtype=np.int64)
    reached = np.zeros(sessions, dtype=bool)
    ruined = np.zeros(sessions, dtype=bool)
    for _ in range(max_steps):
        active = np.flatnonzero(~(reached | ruined))
        if not len(active):
            break
        if strategy == "flat":
            stake = np.full(len(active), NUMBERS, dtype=np.int64)
        elif strategy == "ladder":
            stake = NUMBERS * np.asarray(LADDER80)[rounds[active]]
        else:
            stake = np.minimum(balance[active],
                               (goal - balance[active] + BOLD_DIVISOR - 1) // BOLD_DIVISOR)
        affordable = balance[active] >= stake
        ruined[active[~affordable]] = True
        active, stake = active[affordable], stake[affordable]
        if not len(active):
            continue
        draws = rng.integers(0, 100, size=(len(active), 5))
        if strategy == "ladder":
            per_number = np.asarray(LADDER80)[rounds[active]]
        else:
            per_number = stake if strategy == "bold" else 1
        winnings = per_number * _sample_payments(draws, mode, strategy)
        balance[active] += winnings - stake
        steps[active] += 1
        wagered[active] += stake
        paid[active] += winnings
        if strategy == "ladder":
            rounds[active] = np.where(draws[:, 0] % 2 == 0, 0,
                                      (rounds[active] + 1) % len(LADDER80))
        reached[active] = balance[active] >= goal
        if strategy == "bold":
            ruined[active] = balance[active] <= 0
        else:
            next_stake = (NUMBERS if strategy == "flat" else
                          NUMBERS * np.asarray(LADDER80)[rounds[active]])
            ruined[active] = (balance[active] < next_stake) & ~reached[active]
    if np.any(~(reached | ruined)):
        raise RuntimeError(f"Monte Carlo did not terminate within {max_steps} rounds")
    return [Session(bool(reached[i]), bool(ruined[i]), int(steps[i]),
                    int(wagered[i]), int(paid[i]), int(balance[i]))
            for i in range(sessions)]


def _wilson(successes, n):
    z = 1.959963984540054
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    spread = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - spread, center + spread


def summarize(sessions, capital=CAPITAL):
    """Rates and means use terminal sessions only; incomplete tail is explicit."""
    completed = [s for s in sessions if s.reached or s.ruined]
    n = len(completed)
    inconclusive = len(sessions) - n
    if not n:
        return Metrics(0, None, None, None, None, None, None, None, None, inconclusive)
    successes = sum(s.reached for s in completed)
    wagered = sum(s.wagered for s in completed)
    return Metrics(
        sessions=n,
        p_goal=successes / n,
        goal_wilson95=_wilson(successes, n),
        p_ruin=sum(s.ruined for s in completed) / n,
        mean_net=sum(s.final_balance - capital for s in completed) / n,
        mean_wagered=wagered / n,
        return_per_peso=sum(s.paid for s in completed) / wagered if wagered else None,
        median_steps=float(np.median([s.steps for s in completed])),
        p90_steps=float(np.percentile([s.steps for s in completed], 90)),
        inconclusive=inconclusive,
    )


_HISTORICAL = {
    "parity": "Paridad Markov (50)",
    "random50": "Azar 50",
    "ladder": "Escalera paridad",
    "bold": "Audaz aleatoria",
}
_MC = {"flat": "Plana (50)", "ladder": "Escalera (50)", "bold": "Audaz (1)"}


def _number(value, decimals=1, signed=False):
    if value is None:
        return "—"
    if not isfinite(value):
        raise ValueError("non-finite metric cannot be reported")
    return f"{value:+,.{decimals}f}" if signed else f"{value:,.{decimals}f}"


def _percent(value):
    return "—" if value is None else f"{_number(value * 100)} %"


def _table(results, mode):
    header = ("| Fuente | Estrategia | Sesiones completas | Meta | IC Wilson 95 % | "
              "Quiebre | Neto medio (RD$) | Apostado medio (RD$) | Apostado total (RD$) | "
              "Retorno/peso | Sorteos mediana / p90 | Inconclusas |")
    lines = [header, "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for source, names in (("Historial", _HISTORICAL), ("Montecarlo", _MC)):
        for strategy, label in names.items():
            stats = results[(source, strategy, mode)]
            ci = ("—" if stats.goal_wilson95 is None else
                  f"{_percent(stats.goal_wilson95[0])} – {_percent(stats.goal_wilson95[1])}")
            duration = ("—" if stats.median_steps is None else
                        f"{_number(stats.median_steps)} / {_number(stats.p90_steps)}")
            lines.append(
                f"| {source} | {label} | {stats.sessions} | {_percent(stats.p_goal)} | "
                f"{ci} | {_percent(stats.p_ruin)} | {_number(stats.mean_net, signed=True)} | "
                f"{_number(stats.mean_wagered)} | "
                f"{_number(stats.mean_wagered * stats.sessions if stats.mean_wagered is not None else None)} | "
                f"{_number(stats.return_per_peso, 4)} | "
                f"{duration} | {stats.inconclusive} |"
            )
    return "\n".join(lines)


def render_report(results, capital=CAPITAL, goal=GOAL, history_count=0):
    """Render computed metrics; absent denominators are explicitly unavailable."""
    all_table = _table(results, "all")
    best_table = _table(results, "best")
    incomplete = sum(results[("Historial", key, mode)].inconclusive
                     for mode in _MODES for key in _HISTORICAL)
    completed = sum(results[(source, key, mode)].sessions
                    for mode in _MODES
                    for source, names in (("Historial", _HISTORICAL), ("Montecarlo", _MC))
                    for key in names)
    completion_note = ("Sin sesiones completas en al menos una fila; sus tasas, "
                       "intervalos y promedios aparecen como —, no como cero.\n\n"
                       if any(stats.sessions == 0 for stats in results.values()) else "")
    return (
        "# Quiniela Extraordinaria 80/8/4/2/1 — simulación retrospectiva\n\n"
        "## 1. Alcance y advertencias\n\n"
        f"Capital RD${capital:,}; meta RD${goal:,}; historial de {history_count:,} sorteos. "
        "El historial es Chance Express: contrafactual para Q80, no datos verificados "
        "de Rapidita. No es una predicción ni una recomendación de juego. "
        "Se suponen premios 80/8/4/2/1 por peso, sin comisiones ni impuestos.\n\n"
        "## 2. Tabla principal (modo all)\n\n" + all_table + "\n\n"
        "## 3. Sensibilidad (modo best)\n\n" + best_table + "\n\n"
        "## 4. Glosario\n\n"
        "Sesiones completas: meta o quiebre; la última sesión histórica sin desenlace "
        "queda inconclusa y se excluye de tasas y promedios. Meta y quiebre: "
        "fracciones de sesiones completas. IC Wilson 95 %: intervalo descriptivo "
        "de la fracción de meta; en historial usa una aproximación de independencia, "
        "sin garantizar que los sorteos sean IID. Neto medio: saldo final menos capital, "
        "con signo. Apostado medio: promedio por sesión completa; apostado total: "
        "suma sobre sesiones completas. Retorno/peso: "
        "pagos totales divididos por apuestas totales, no beneficio neto. Sorteos "
        "mediana/p90: duración de sesiones completas. Quiebre significa no poder "
        "financiar la próxima apuesta prescrita (en audaz, saldo agotado); puede "
        "quedar saldo, no necesariamente bancarrota total.\n\n"
        "## 5. Lectura de los resultados\n\n"
        f"Se computaron {completed} sesiones completas entre todas las filas y modos "
        f"(no son sesiones únicas entre estrategias), y {incomplete} colas "
        "históricas inconclusas entre las filas y modos. "
        + completion_note +
        "Las tasas y los importes de cada fila están arriba; las colas censuradas "
        "pueden sesgar la comparación histórica. No extrapolar la muestra histórica "
        "como garantía de resultados futuros.\n\n"
        "## 6. Supuestos y trazabilidad [A1]–[T2]\n\n"
        "- [A1] Q80 usa premios 80/8/4/2/1 para posiciones 1–5; all suma "
        "posiciones repetidas y best paga solo la mejor posición por número.\n"
        "- [A2] Plana y control apuestan un peso a 50 números; escalera usa "
        "1, 2, 6, 16… por número y reinicia al cubrir el primer premio. "
        "Cuatro rondas financiables describen solo la trayectoria de pérdidas "
        "totales desde RD$2.000, no un límite universal con premios secundarios.\n"
        "- [A3] Audaz elige un número y apuesta el mínimo entre saldo y "
        "ceil((meta − saldo)/79). La meta se evalúa después de cada sorteo.\n"
        "- [T1] Historial cronológico validado; Markov arranca vacío, emite "
        "27 votos antes de actualizar con el sorteo actual. No se mezcla JSON "
        "legado sin fecha. Paridad y selecciones azar 50/audaz se generan una "
        f"vez con semillas {SEED + 1}/{SEED + 2} y se reutilizan entre all/best.\n"
        "- [T2] MC genera cinco posiciones uniformes independientes (se admiten "
        "repeticiones). Cobertura fija par o número 0: bajo sorteos IID uniformes "
        "la cobertura fija tiene la misma distribución que otra cobertura igual, "
        "no los mismos resultados en una muestra. Semilla base "
        f"{SEED}; flat all/best usa +0/+1, ladder +2/+3, bold +4/+5. "
        "Sin ajuste de semillas según los resultados.\n"
    )


def _report_destination(path, input_path):
    """Validate an unused destination before running expensive computations."""
    root = Path(__file__).resolve().parent.parent
    protected = tuple(root / name for name in ("lagacy_loto", "repo_ref", ".pi", "odd", ".git"))
    try:
        # Check the entry itself before resolve: dangling symlinks have exists() == False.
        if path.is_symlink() or path.exists():
            raise ValueError("--report ya existe o es un enlace simbólico")
        destination = path.resolve()
        lexical = Path(os.path.abspath(path))
        if destination == input_path.resolve():
            raise ValueError("--report coincide con --input")
        if any(directory == candidate or directory in candidate.parents
               for candidate in (destination, lexical) for directory in protected):
            raise ValueError("--report apunta a una ubicación protegida")
        if not destination.parent.is_dir():
            raise ValueError("--report requiere un directorio padre existente")
    except (OSError, RuntimeError) as exc:
        raise ValueError("--report no se pudo validar") from exc
    return destination


def main(argv=None):
    """Run historical and seeded MC comparisons without changing input files."""
    parser = argparse.ArgumentParser(description="Simulador de Quiniela Extraordinaria Q80")
    parser.add_argument("--capital", type=int, default=CAPITAL)
    parser.add_argument("--meta", type=int, default=GOAL)
    parser.add_argument("--mc-sessions", type=int, default=MC_SESSIONS)
    parser.add_argument("--input", type=Path,
                        default=Path(__file__).resolve().parent.parent / "chance_express_history.json")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.capital <= 0 or args.mc_sessions <= 0 or args.meta <= args.capital:
        parser.error("capital y mc-sessions deben ser positivos; meta debe superar capital")
    destination = None
    if args.report is not None:
        try:
            destination = _report_destination(args.report, args.input)
        except ValueError as exc:
            parser.error(str(exc))

    history = load_validated_history(args.input)
    nums = history.nums
    selections = historical_selections(nums, consensus_parity(nums[:, 0]))
    results = {}
    for mode in _MODES:
        matrix = payout_matrix(nums, mode, QUINIELA80)
        parity = selections["parity"]
        random50 = selections["random50"]
        bold_numbers = selections["bold_number"]
        payments = {
            "parity": (matrix * parity).sum(axis=1),
            "random50": (matrix * random50).sum(axis=1),
        }
        single = matrix[np.arange(len(nums)), bold_numbers]
        first_hits = parity[np.arange(len(nums)), nums[:, 0]]
        for key in _HISTORICAL:
            covered = payments["random50" if key == "random50" else "parity"]
            strategy = "flat" if key in ("parity", "random50") else key
            sessions = replay_back_to_back(
                strategy, covered, single_pay=single, first_hits=first_hits,
                capital=args.capital, goal=args.meta,
            )
            results[("Historial", key, mode)] = summarize(sessions, args.capital)
        for strategy in _MC:
            sessions = simulate(strategy, mode, sessions=args.mc_sessions, seed=SEED,
                                capital=args.capital, goal=args.meta)
            results[("Montecarlo", strategy, mode)] = summarize(sessions, args.capital)
    print("Quiniela Extraordinaria — modo all (sesiones completas)")
    print(_table(results, "all"))
    if destination is not None:
        report = render_report(results, args.capital, args.meta, len(nums))
        try:
            with destination.open("x", encoding="utf-8") as output:
                output.write(report)
        except OSError as exc:
            parser.error(f"--report no se pudo crear exclusivamente: {exc.strerror}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
