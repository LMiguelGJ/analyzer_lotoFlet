"""Reusable k-number Quiniela 80 comparison engine (no experiment or reporting CLI).

Each draw has five independent positions; each of exactly k distinct selected numbers
receives the same integer-peso stake. Historical payments are pesos returned per
peso on each selected number, not already multiplied by the stake.
"""

import argparse
import hashlib
from dataclasses import dataclass
from functools import cache
from math import isfinite
from pathlib import Path

import numpy as np

from quiniela_sim import (
    Metrics,
    _report_destination,
    consensus_parity,
    load_validated_history,
    summarize,
)
from repo_ref.strategy_tests.rules import (
    QUINIELA80,
    expected_return,
    first_prize_ladder,
    payout_matrix,
)

CAPITAL = 2000
GOAL = 2800
K_VALUES = (1, 5, 10, 20, 25, 30, 40, 50)
MC_SESSIONS = 20_000
SEED = 20260928
_STRATEGIES = ("flat", "ladder", "bold")
_MODES = ("all", "best")
_FIRST_PRIZE = QUINIELA80.prizes[0]


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
class WindowAggregate:
    """Completed-only metrics plus fixed-window totals including the censored tail."""

    completed: Metrics
    sessions_total: int
    total_wagered: int
    total_paid: int
    total_net: int


def _validate(strategy, k, capital, goal):
    if strategy not in _STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    if isinstance(k, (bool, np.bool_)) or not isinstance(k, (int, np.integer)) or not 1 <= k < 80:
        raise ValueError("k must be an integer between 1 and 79")
    if capital <= 0 or goal <= capital:
        raise ValueError("capital must be positive and goal must exceed capital")


@cache
def _ladder(k):
    return first_prize_ladder(QUINIELA80, numbers=k, target_net=10, rounds=10)


def _per_number(strategy, k, balance, round_index, goal):
    if strategy == "flat":
        return 1
    if strategy == "ladder":
        return _ladder(k)[round_index]
    return min((goal - balance + _FIRST_PRIZE - k - 1) // (_FIRST_PRIZE - k),
               balance // k)


def _next_unaffordable(strategy, k, balance, round_index, goal):
    return balance < k or balance < k * _per_number(strategy, k, balance, round_index, goal)


def step(strategy, k, state, cover_pay=0, first_hit=False, goal=GOAL):
    """Settle one affordable draw, then test goal before next-stake affordability.

    An unaffordable call consumes no draw and returns the original state. The
    caller must not turn an initially unaffordable replay into zero-step sessions.
    """
    _validate(strategy, k, 1, goal)
    if state.balance >= goal:
        return 0, 0, state, "goal"
    if state.balance < k:
        return 0, 0, state, "ruin"
    per_number = _per_number(strategy, k, state.balance, state.round, goal)
    stake = k * per_number
    if state.balance < stake:
        return 0, 0, state, "ruin"
    winnings = per_number * cover_pay
    balance = int(state.balance + winnings - stake)
    round_index = state.round
    if strategy == "ladder":
        round_index = 0 if first_hit else (round_index + 1) % len(_ladder(k))
    next_state = BalanceState(balance, round_index)
    outcome = ("goal" if balance >= goal else
               "ruin" if _next_unaffordable(strategy, k, balance, round_index, goal) else None)
    return stake, int(winnings), next_state, outcome


def replay(strategy, k, cover_pay, first_hits, capital=CAPITAL, goal=GOAL):
    """Partition aligned chronological outcomes; retain the trailing censored session.

    A terminal draw belongs to its ending session. The following draw starts the
    next session immediately, without losing a draw to an affordability check.
    """
    _validate(strategy, k, capital, goal)
    if len(cover_pay) != len(first_hits):
        raise ValueError("cover_pay and first_hits must align")
    if _next_unaffordable(strategy, k, capital, 0, goal):
        raise ValueError("initial stake is unaffordable")
    sessions = []
    state = BalanceState(capital)
    steps = wagered = paid = 0
    for payment, first_hit in zip(cover_pay, first_hits, strict=True):
        stake, winnings, state, outcome = step(
            strategy, k, state, payment, first_hit, goal
        )
        steps += 1
        wagered += stake
        paid += winnings
        if outcome:
            sessions.append(Session(outcome == "goal", outcome == "ruin", steps,
                                    wagered, paid, state.balance))
            state = BalanceState(capital)
            steps = wagered = paid = 0
    if steps:
        sessions.append(Session(False, False, steps, wagered, paid, state.balance))
    return sessions


def aggregate(sessions, capital=CAPITAL):
    """Fixed-window stake, payout and net include completed and censored sessions."""
    return WindowAggregate(
        completed=summarize(sessions, capital),
        sessions_total=len(sessions),
        total_wagered=sum(s.wagered for s in sessions),
        total_paid=sum(s.paid for s in sessions),
        total_net=sum(s.final_balance - capital for s in sessions),
    )


def sample_payments(draws, k, mode="all"):
    """Vectorized pesos per peso for the fixed selected set range(k)."""
    if isinstance(k, (bool, np.bool_)) or not isinstance(k, (int, np.integer)) or not 1 <= k < 80:
        raise ValueError("k must be an integer between 1 and 79")
    if mode not in _MODES:
        raise ValueError(f"unknown settlement mode: {mode}")
    draws = np.asarray(draws)
    if draws.ndim != 2 or draws.shape[1] != 5:
        raise ValueError("draws must have shape (n, 5)")
    selected = draws < k
    if mode == "best":
        for pos in range(1, 5):
            selected[:, pos] &= ~np.any(draws[:, :pos] == draws[:, pos, None], axis=1)
    return (selected * np.asarray(QUINIELA80.prizes)).sum(axis=1)


def simulate(strategy, k, mode="all", sessions=MC_SESSIONS, seed=SEED,
             capital=CAPITAL, goal=GOAL, max_steps=2_000_000):
    """Seeded vectorized sessions; fail rather than misclassify a safety-cap tail."""
    _validate(strategy, k, capital, goal)
    if mode not in _MODES:
        raise ValueError(f"unknown settlement mode: {mode}")
    if sessions <= 0 or max_steps <= 0:
        raise ValueError("sessions and max_steps must be positive")
    if _next_unaffordable(strategy, k, capital, 0, goal):
        raise ValueError("initial stake is unaffordable")
    rng = np.random.default_rng(seed)
    balance = np.full(sessions, capital, dtype=np.int64)
    rounds = np.zeros(sessions, dtype=np.int64)
    steps = np.zeros(sessions, dtype=np.int64)
    wagered = np.zeros(sessions, dtype=np.int64)
    paid = np.zeros(sessions, dtype=np.int64)
    reached = np.zeros(sessions, dtype=bool)
    ruined = np.zeros(sessions, dtype=bool)
    ladder = np.asarray(_ladder(k))
    for _ in range(max_steps):
        active = np.flatnonzero(~(reached | ruined))
        if not len(active):
            break
        if strategy == "flat":
            per_number = np.ones(len(active), dtype=np.int64)
        elif strategy == "ladder":
            per_number = ladder[rounds[active]]
        else:
            per_number = np.minimum(
                (goal - balance[active] + _FIRST_PRIZE - k - 1) // (_FIRST_PRIZE - k),
                balance[active] // k,
            )
        stake = k * per_number
        affordable = (per_number >= 1) & (balance[active] >= stake)
        ruined[active[~affordable]] = True
        active, stake, per_number = (active[affordable], stake[affordable],
                                     per_number[affordable])
        if not len(active):
            continue
        draws = rng.integers(0, 100, size=(len(active), 5))
        winnings = per_number * sample_payments(draws, k, mode)
        balance[active] += winnings - stake
        steps[active] += 1
        wagered[active] += stake
        paid[active] += winnings
        if strategy == "ladder":
            rounds[active] = np.where(draws[:, 0] < k, 0,
                                      (rounds[active] + 1) % len(ladder))
        reached[active] = balance[active] >= goal
        if strategy == "ladder":
            next_stake = k * ladder[rounds[active]]
            ruined[active] = (balance[active] < next_stake) & ~reached[active]
        else:
            ruined[active] = (balance[active] < k) & ~reached[active]
    if np.any(~(reached | ruined)):
        raise RuntimeError(f"Monte Carlo did not terminate within {max_steps} rounds")
    return [Session(bool(reached[i]), bool(ruined[i]), int(steps[i]),
                    int(wagered[i]), int(paid[i]), int(balance[i]))
            for i in range(sessions)]


# These are the available, archived pos1 selectors; supervised/unavailable systems
# and the recent500 auxiliary baseline are deliberately not inferred or imputed.
SYSTEMS = ("freq_hist", "freq_recent", "decay", "cold", "notebook", "mix",
           "transition", "carry", "doubles", "category", "time", "ensemble",
           "select_interpretable")
EXCLUDED = ("logistic", "tree", "select_all")
RANKINGS = Path(__file__).resolve().parent.parent / (
    "repo_ref/reports/chance_rank_v1/predictions/pos1.npz"
)
INPUT = Path(__file__).resolve().parent.parent / "chance_express_history.json"


@dataclass(frozen=True)
class RankingContext:
    row_ids: np.ndarray
    fold_id: np.ndarray
    configs: dict
    first: str
    last: str
    gaps: int


def _array(archive, key, shape=None, dtype=None):
    if key not in archive.files:
        raise ValueError(f"missing ranking metadata: {key}")
    value = archive[key]
    if shape is not None and value.shape != shape:
        raise ValueError(f"invalid {key} shape: {value.shape}, expected {shape}")
    if dtype is not None and value.dtype != dtype:
        raise ValueError(f"invalid {key} dtype: {value.dtype}")
    return value


def ranking_context(history, path):
    """Validate archive chronology and availability without loading ranking families."""
    with np.load(path, allow_pickle=False) as archive:
        rows = _array(archive, "row_ids", dtype=np.dtype("int64"))
        n = len(rows)
        if rows.shape != (n,) or not n or np.any(rows < 1) or np.any(rows >= history.n) or (
            np.any(np.diff(rows) <= 0)
        ):
            raise ValueError("row_ids must be distinct increasing in-bounds history indices")
        folds = _array(archive, "fold_id", (n,), np.dtype("int64"))
        if np.any(folds < 0) or np.any(np.diff(folds) < 0) or not np.array_equal(
            np.unique(folds), np.arange(folds[-1] + 1)
        ):
            raise ValueError("fold_id must be contiguous ordered folds")
        count = int(folds[-1]) + 1
        timestamps = _array(archive, "timestamps", (n,))
        cutoff = _array(archive, "cutoff", (n,))
        labels = [history.label(i) for i in range(history.n)]
        label_indices = {label: i for i, label in enumerate(labels)}
        for index, stamp, before in zip(rows, timestamps, cutoff, strict=True):
            if stamp != labels[index]:
                raise ValueError("timestamps do not align with history row_ids")
            if before not in label_indices or label_indices[before] >= index:
                raise ValueError("cutoff must identify an actual earlier history draw")
        names = _array(archive, "systems")
        if names.ndim != 1 or len(names) != len(SYSTEMS) + len(EXCLUDED) or (
            set(names.tolist()) != set(SYSTEMS) | set(EXCLUDED)
        ):
            raise ValueError("systems metadata differs from frozen selection")
        _array(archive, "baselines")  # The auxiliary baselines are not selected.
        configs = {}
        for system in (*SYSTEMS, *EXCLUDED):
            available = _array(archive, f"available__{system}", (1,), np.dtype("bool"))
            if bool(available[0]) != (system in SYSTEMS):
                raise ValueError(f"available__{system} differs from frozen selection")
            config = _array(archive, f"config_id__{system}", (count,))
            if config.dtype.kind != "U" or (system in SYSTEMS and np.any(config == "")):
                raise ValueError(f"config_id__{system} missing or invalid")
            if system in EXCLUDED and np.any(config != ""):
                raise ValueError(f"config_id__{system} should be unavailable")
            configs[system] = config.tolist()
        return RankingContext(rows.copy(), folds.copy(), configs,
                              str(timestamps[0]), str(timestamps[-1]),
                              int(rows[-1] - rows[0] + 1 - n))


def ranking_family(path, system, context):
    """Load and verify exactly one exported tie-ordered full permutation family."""
    if system not in SYSTEMS:
        raise ValueError(f"unavailable ranking system: {system}")
    with np.load(path, allow_pickle=False) as archive:
        ranks = _array(archive, f"ranking100__{system}",
                       (len(context.row_ids), 100), np.dtype("uint8"))
    expected = np.arange(100, dtype=np.uint8)
    for start in range(0, len(ranks), 4096):
        if not np.all(np.sort(ranks[start:start + 4096], axis=1) == expected):
            raise ValueError(f"ranking100__{system} contains a non-permutation")
    return ranks


def selected_payments(nums, ranks, k, mode):
    """One top-k pos1 set, settled against all five actual positions."""
    if mode not in _MODES or not 1 <= k <= 100 or ranks.shape != (len(nums), 100):
        raise ValueError("invalid mode, k, or ranking alignment")
    payments = np.empty(len(nums), dtype=np.int64)
    first = np.empty(len(nums), dtype=bool)
    for start in range(0, len(nums), 4096):
        end = min(start + 4096, len(nums))
        chosen = ranks[start:end, :k]
        matrix = payout_matrix(nums[start:end], mode, QUINIELA80)
        payments[start:end] = np.take_along_axis(matrix, chosen, axis=1).sum(axis=1)
        first[start:end] = np.any(chosen == nums[start:end, 0, None], axis=1)
    return payments, first


def _record(source, system, k, style, mode, sessions, capital, seed=None):
    aggregate_stats = aggregate(sessions, capital)
    complete = aggregate_stats.completed
    draws = sum(s.steps for s in sessions)
    return {
        "source": source, "system": system, "k": k, "style": style, "mode": mode,
        "completed": complete.sessions, "incomplete": complete.inconclusive,
        "goal_count": sum(s.reached for s in sessions if s.reached or s.ruined),
        "ruin_count": sum(s.ruined for s in sessions if s.reached or s.ruined),
        "sessions_total": aggregate_stats.sessions_total, "goal_rate": complete.p_goal,
        "goal_wilson95": complete.goal_wilson95, "ruin_rate": complete.p_ruin,
        "mean_net": complete.mean_net,
        "mean_final_balance": capital + complete.mean_net if complete.sessions else None,
        "mean_stake": complete.mean_wagered,
        "completed_return_per_peso": complete.return_per_peso,
        "median_steps": complete.median_steps, "p90_steps": complete.p90_steps,
        "total_stake": aggregate_stats.total_wagered,
        "total_paid": aggregate_stats.total_paid, "total_net": aggregate_stats.total_net,
        "total_steps": draws,
        "net_per_draw": aggregate_stats.total_net / draws if draws else None,
        "seed": seed,
    }


def historical_rows(history, path, context, capital=CAPITAL, goal=GOAL):
    """Shared selected timestamps, with no bet in gaps; no fold/day reset."""
    row_ids = context.row_ids
    nums = history.nums[row_ids]
    records = []

    def evaluate(system, ranks, ks):
        for mode in _MODES:
            # One mode's matrix per family; never keep multiple ranking families.
            matrix = payout_matrix(nums, mode, QUINIELA80)
            by_rank = np.take_along_axis(matrix, ranks, axis=1)
            del matrix
            cumulative = np.cumsum(by_rank, axis=1)
            del by_rank
            first_rank = np.argmax(ranks == nums[:, 0, None], axis=1)
            for k in ks:
                pay = cumulative[:, k - 1]
                first_hit = first_rank < k
                for style in _STRATEGIES:
                    sessions = replay(style, k, pay, first_hit, capital, goal)
                    records.append(_record("history", system, k, style, mode,
                                           sessions, capital))

    for system in SYSTEMS:
        ranks = ranking_family(path, system, context)
        evaluate(system, ranks, K_VALUES)
        del ranks
    rng = np.random.default_rng(SEED + 100)
    ranks = np.stack([rng.permutation(100) for _ in row_ids]).astype(np.uint8)
    evaluate("random", ranks, K_VALUES)
    del ranks
    # Causal consensus sees ALL earlier draws, including draws without archived ranks.
    parity = consensus_parity(history.nums[:, 0])[row_ids]
    even = np.arange(0, 100, 2, dtype=np.uint8)
    odd = np.arange(1, 100, 2, dtype=np.uint8)
    ranks = np.where(parity[:, None] == 0, np.r_[even, odd], np.r_[odd, even])
    evaluate("parity", ranks, (50,))
    return records


def historical_scenario(history, path, system, k, style, mode="all", context=None,
                        capital=CAPITAL, goal=GOAL):
    """Replay one archived selector (or parity at k=50) on selected history rows.

    A supplied context is expected to come from ranking_context. Gaps and folds
    consume no bets; parity still observes every earlier history draw.
    """
    _validate(style, k, capital, goal)
    if system not in SYSTEMS and system != "parity":
        raise ValueError(f"unavailable ranking system: {system}")
    if k not in ((50,) if system == "parity" else K_VALUES):
        raise ValueError(f"unsupported k for {system}: {k}")
    if mode not in _MODES:
        raise ValueError(f"unknown settlement mode: {mode}")
    if _next_unaffordable(style, k, capital, 0, goal):
        raise ValueError("initial stake is unaffordable")

    if context is None:
        context = ranking_context(history, path)
    row_ids = context.row_ids
    nums = history.nums[row_ids]
    if system == "parity":
        parity = consensus_parity(history.nums[:, 0])[row_ids]
        even = np.arange(0, 100, 2, dtype=np.uint8)
        odd = np.arange(1, 100, 2, dtype=np.uint8)
        ranks = np.where(parity[:, None] == 0, np.r_[even, odd], np.r_[odd, even])
    else:
        ranks = ranking_family(path, system, context)
    payments, first_hits = selected_payments(nums, ranks, k, mode)
    sessions = replay(style, k, payments, first_hits, capital, goal)
    return _record("history", system, k, style, mode, sessions, capital)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_experiment(input_path=INPUT, rankings_path=RANKINGS, capital=CAPITAL, goal=GOAL,
                   mc_sessions=MC_SESSIONS):
    """Historical descriptive comparison plus 48 independent uniform MC rows."""
    history = load_validated_history(input_path)
    ranking_sha = _sha256(rankings_path)
    context = ranking_context(history, rankings_path)
    results = historical_rows(history, rankings_path, context, capital, goal)
    if _sha256(rankings_path) != ranking_sha:
        raise ValueError("ranking archive changed during evaluation")
    for mode_index, mode in enumerate(_MODES):
        for k in K_VALUES:
            for style_index, style in enumerate(_STRATEGIES):
                seed = SEED + 1000 + 100 * k + 10 * style_index + mode_index
                sessions = simulate(style, k, mode, mc_sessions, seed, capital, goal)
                results.append(_record("mc", "uniform", k, style, mode,
                                       sessions, capital, seed))
    provenance = {
        "history_sha256": history.sha256, "ranking_sha256": ranking_sha,
        "rows": len(context.row_ids), "first": context.first, "last": context.last,
        "gaps": context.gaps, "fold_count": int(context.fold_id[-1]) + 1,
        "capital": capital, "goal": goal, "mc_sessions": mc_sessions,
    }
    return results, provenance


def _metric(value, digits=1):
    if value is None:
        return "—"
    if not isfinite(value):
        raise ValueError("non-finite metric")
    return f"{value:.{digits}f}"


def _table(rows):
    header = ("| Fuente | Sistema | k | Estilo | Completas | Inconclusas | "
              "Meta (n) | Meta % | Wilson 95 % | Quiebre (n) | Quiebre % | "
              "Neto medio | Saldo final medio | Apostado medio | "
              "Apostado total ventana | Pagado total ventana | Neto total ventana | "
              "Sorteos apostados | Neto/sorteo apostado | Retorno/peso completas | "
              "Mediana/p90 sorteos | Semilla MC |")
    lines = [header, "|" + "---|" * (header.count("|") - 1)]
    for row in rows:
        ci = row["goal_wilson95"]
        interval = "—" if ci is None else f"{_metric(ci[0] * 100)}–{_metric(ci[1] * 100)}"
        duration = ("—" if row["median_steps"] is None else
                    f"{_metric(row['median_steps'])}/{_metric(row['p90_steps'])}")
        lines.append(
            f"| {row['source']} | {row['system']} | {row['k']} | {row['style']} | "
            f"{row['completed']} | {row['incomplete']} | {row['goal_count']} | "
            f"{_metric(None if row['goal_rate'] is None else row['goal_rate'] * 100)} | "
            f"{interval} | {row['ruin_count']} | "
            f"{_metric(None if row['ruin_rate'] is None else row['ruin_rate'] * 100)} | "
            f"{_metric(row['mean_net'])} | {_metric(row['mean_final_balance'])} | "
            f"{_metric(row['mean_stake'])} | "
            f"{_metric(row['total_stake'])} | {_metric(row['total_paid'])} | "
            f"{_metric(row['total_net'])} | {row['total_steps']} | "
            f"{_metric(row['net_per_draw'], 3)} | "
            f"{_metric(row['completed_return_per_peso'], 4)} | {duration} | "
            f"{row['seed'] if row['seed'] is not None else '—'} |"
        )
    return "\n".join(lines)


def leaders(rows, limit=10):
    eligible = [row for row in rows if row["source"] == "history" and
                row["mode"] == "all" and row["completed"]]
    return sorted(eligible, key=lambda r: (-r["goal_rate"], -r["mean_net"],
                                         r["median_steps"], r["system"], r["k"],
                                         r["style"]))[:limit]


def render_comparison(rows, provenance):
    """Complete tables and provenance, not a claim of independent validation."""
    top = leaders(rows)
    lines = ["# Quiniela Q80: comparación exploratoria de rankings", "",
             (f"Capital RD${provenance['capital']}; meta RD${provenance['goal']}; "
              f"sesiones MC por k/estilo/modo: {provenance['mc_sessions']}."),
             (f"Historial SHA-256 `{provenance['history_sha256']}`; archivo de rankings "
              f"SHA-256 `{provenance['ranking_sha256']}`."),
             (f"Sorteos comunes seleccionados: {provenance['rows']}, desde "
              f"{provenance['first']} hasta {provenance['last']}; faltantes dentro "
              f"del tramo: {provenance['gaps']}; folds: "
              f"{provenance.get('fold_count', '—')}. No se apuesta en sorteos sin "
              "ranking; sesiones y saldo continúan entre huecos, días y folds."), "",
             ("La evaluación histórica reutiliza datos ya explorados para los "
              "rankings: NO es un holdout intacto ni confirmación independiente. "
              "Chance Express bajo Q80 es contrafactual, no resultados verificados "
              "de Rapidita. No implica recomendación ni ganador universal o "
              "rentable. Los rankings son de pos1: el mismo conjunto top-k se "
              "liquida en las cinco posiciones, conservando el orden exportado "
              "de los empates. Azar usa permutaciones completas por sorteo, con "
              "prefijos anidados. Paridad usa todo el historial causal y luego "
              "se restringe a los mismos sorteos."), "",
             ("Grilla k=1,5,10,20,25,30,40,50; flat/ladder/bold; all/best. "
              "13 sistemas archivados + azar en cada k; paridad legada solo k=50. "
              "logistic/tree/select_all no disponibles, excluidos; recent500 "
              "auxiliar no seleccionado. No se lee winner_rank/results_pos1."),
             (f"Semillas: base {SEED}; permutaciones azar {SEED + 100}; "
              "MC base+1000+100*k+10*índice_estilo+índice_modo "
              "(flat/ladder/bold = 0/1/2; all/best = 0/1)."), "",
             ("Conteos exactos de meta y quiebre, tasas, IC Wilson descriptivo "
              "95 % y medias sobre sesiones completas: excluyen la cola "
              "inconclusa. Saldo final medio es capital más neto medio; "
              "— indica no disponible, "
              "no cero. Quiebre es no poder financiar la próxima apuesta y puede "
              "dejar saldo. Sorteos de duración cuentan apuestas realizadas, no "
              "tiempo calendario. Totales de ventana incluyen colas inconclusas "
              "y suman sesiones que reinician en el capital inicial, NO una sola "
              "cartera ininterrumpida. Neto/sorteo apostado incluye toda apuesta "
              "de la ventana."), "",
             ("MC con posiciones independientes uniformes mide apuesta/cobertura, "
              "no ventaja del selector. Retorno teórico uniforme por peso: "
              f"all {expected_return('all', QUINIELA80):.4f} (EV -0,05/peso), "
              f"best {expected_return('best', QUINIELA80):.4f}; el neto medio "
              "de sesiones MC completas es estimación finita, no EV teórica. "
              "Esto no descarta diferencias empíricas entre selectores."), "",
             "## Líderes descriptivos (solo historial all)", "",
             (f"{len(top)} líderes; orden por tasa de meta descendente, luego "
              "neto medio descendente, mediana de sorteos ascendente e "
              "ID sistema/k/estilo estable."),
             _table(top), "", "## Historial completo — all", "",
             _table([r for r in rows if r['source'] == 'history' and r['mode'] == 'all']),
             "", "## Sensibilidad histórica — best", "",
             _table([r for r in rows if r['source'] == 'history' and r['mode'] == 'best']),
             "", "## Montecarlo uniforme — all", "",
             _table([r for r in rows if r['source'] == 'mc' and r['mode'] == 'all']),
             "", "## Montecarlo uniforme — best", "",
             _table([r for r in rows if r['source'] == 'mc' and r['mode'] == 'best']), ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Exploratory causal Quiniela ranking comparison")
    parser.add_argument("--capital", type=int, default=CAPITAL)
    parser.add_argument("--meta", type=int, default=GOAL)
    parser.add_argument("--mc-sessions", type=int, default=MC_SESSIONS)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--rankings", type=Path, default=RANKINGS)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.capital <= 0 or args.meta <= args.capital or args.mc_sessions <= 0:
        parser.error("capital and mc-sessions must be positive; meta must exceed capital")
    if args.capital < max(K_VALUES):
        parser.error(f"capital must be at least {max(K_VALUES)} to fund every grid k")
    try:
        destination = _report_destination(args.report, args.input)
        if destination == args.rankings.resolve():
            raise ValueError("--report coincides with --rankings")
    except ValueError as exc:
        parser.error(str(exc))
    rows, provenance = run_experiment(args.input, args.rankings, args.capital,
                                      args.meta, args.mc_sessions)
    report = render_comparison(rows, provenance)
    try:
        with destination.open("x", encoding="utf-8") as output:
            output.write(report)
    except OSError as exc:
        parser.error(f"--report cannot be created exclusively: {exc}")
    top = leaders(rows)
    print(f"Quiniela Q80 all: {len(top)} líderes; {len(rows)} rows total")
    print(_table(top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
