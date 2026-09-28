"""Experiments E1-E8 on Chance Express draws.

Hypothesis tests return dicts ``{id, name, p, observed, expected, n, detail}`` (``p`` is None
for descriptive rows). Betting experiments also return candidates ``(label, stake, paid)``:
per-draw pesos staked and collected, used to pick a parameter on the training days and to
evaluate it on the held-out days.
"""

import math
from typing import Any

import numpy as np
from scipy.stats import binomtest, chi2_contingency, norm

from rng_audit import lottery_tests
from rng_audit.lottery_tests import Draws
from strategy_tests.rules import LADDER, ORIGINAL70, expected_return, payout_matrix

HALVES = {"par/impar": lambda x: x % 2, "bajo/alto": lambda x: (x >= 50).astype(np.int64)}
COLD_THRESHOLDS = (100, 150, 200, 300, 400, 500)
DOUBLE_WINDOWS = (1, 5, 20)
STREAKS = range(3, 9)
P_ANY = 1 - 0.99 ** 5
BOOTSTRAP_REPS = 2000


# --- building blocks -------------------------------------------------------------------------

def run_lengths(series, day):
    """Length of the same-value run ending at each draw; runs restart every day."""
    runs = np.ones(len(series), dtype=np.int64)
    same = (series[1:] == series[:-1]) & (day[1:] == day[:-1])
    for t in (np.flatnonzero(same) + 1).tolist():
        runs[t] = runs[t - 1] + 1
    return runs


def conditional_switch(series, day, n, runs=None):
    """(switches, cases): after a run of exactly ``n`` equal values, did the next draw differ?"""
    runs = run_lengths(series, day) if runs is None else runs
    idx = np.flatnonzero((runs[:-1] == n) & (day[1:] == day[:-1]))
    return int(np.count_nonzero(series[idx + 1] != series[idx])), int(idx.size)


def ages_since(values):
    """(N, 100) draws since each number last appeared in ``values`` (1-D or (N, k)).

    A number never seen yet counts as seen just before the first draw.
    """
    values = np.asarray(values).reshape(len(values), -1)
    ages = np.empty((len(values), 100), dtype=np.int32)
    last = np.full(100, -1)
    for t, row in enumerate(values):
        ages[t] = t - last
        last[row] = t
    return ages


def first_position_matrix(nums, profile=ORIGINAL70):
    """(N, 100) first-position-only pesos per number, independent of repeat mode."""
    matrix = np.zeros((len(nums), 100), dtype=np.int64)
    matrix[np.arange(len(nums)), nums[:, 0]] = profile.prizes[0]
    return matrix


def _stake(style, bank, goal, profile=ORIGINAL70):
    if style == "timid":
        return np.minimum(10, bank)
    return np.minimum(bank, -(-(goal - bank) // (profile.prizes[0] - 1)))


def replay_sessions(paycol, starts, bank, goal, style, profile=ORIGINAL70):
    """Play one number from each start index over a real payout sequence until goal or ruin."""
    starts = np.asarray(starts)
    banks = np.full(len(starts), bank, dtype=np.int64)
    alive = np.ones(len(starts), dtype=bool)
    reached, finished = np.zeros_like(alive), np.zeros_like(alive)
    steps = np.zeros(len(starts), dtype=np.int64)
    step = 0
    while alive.any():
        idx = starts + step
        alive &= idx < len(paycol)
        banks, steps, reached, finished, alive = _advance(
            banks, steps, reached, finished, alive, paycol[np.minimum(idx, len(paycol) - 1)],
            goal, style, profile)
        step += 1
    return {"reached": reached, "finished": finished, "steps": steps, "bank": banks}


def back_to_back(paycol, bank, goal, style, profile=ORIGINAL70):
    """Non-overlapping sessions over the real sequence: each starts where the previous ended."""
    reached, balance = [], bank
    for pay in paycol.tolist():
        balance += int(_stake(style, balance, goal, profile)) * (pay - 1)
        if balance >= goal or balance <= 0:
            reached.append(balance >= goal)
            balance = bank
    return np.array(reached, dtype=bool)


def simulate_sessions(count, bank, goal, style, rng, profile=ORIGINAL70, mode="all"):
    """Independent uniform positions paid by the same profile/mode as the real replay."""
    banks = np.full(count, bank, dtype=np.int64)
    alive = np.ones(count, dtype=bool)
    reached, finished = np.zeros_like(alive), np.zeros_like(alive)
    steps = np.zeros(count, dtype=np.int64)
    prizes = np.asarray(profile.prizes)
    while alive.any():
        hits = rng.random((count, 5)) < 0.01
        if mode == "all":
            pays = hits @ prizes
        elif mode == "best":
            pays = np.max(np.where(hits, prizes, 0), axis=1)
        else:
            raise ValueError(f"Unknown payout mode: {mode}")
        banks, steps, reached, finished, alive = _advance(
            banks, steps, reached, finished, alive, pays, goal, style, profile)
    return {"reached": reached, "finished": finished, "steps": steps, "bank": banks}


def _advance(banks, steps, reached, finished, alive, pays, goal, style,
             profile=ORIGINAL70):
    stake = np.where(alive, _stake(style, banks, goal, profile), 0)
    banks = banks + stake * (pays - 1)
    steps = steps + alive
    goal_hit = alive & (banks >= goal)
    ruined = alive & (banks <= 0)
    return (banks, steps, reached | goal_hit, finished | goal_hit | ruined,
            alive & ~(goal_hit | ruined))


def money(day, stake, paid, rng, reps=BOOTSTRAP_REPS):
    """Return per peso with a 95% day-block bootstrap interval, plus totals and drawdown."""
    total = float(stake.sum())
    if total == 0:
        return None
    _, idx = np.unique(day, return_inverse=True)
    s, p = np.bincount(idx, stake), np.bincount(idx, paid)
    boot = rng.integers(0, len(s), (reps, len(s)))
    ratios = p[boot].sum(axis=1) / np.maximum(s[boot].sum(axis=1), 1e-12)
    lo, hi = np.percentile(ratios, [2.5, 97.5])
    cum = np.cumsum(paid - stake)
    prior_net = np.concatenate(([0.0], cum[:-1]))
    min_bankroll = float(np.max(stake - prior_net))
    drawdown = float(np.max(np.maximum.accumulate(np.concatenate(([0.0], cum)))[1:] - cum))
    return {"ret": float(p.sum() / total), "lo": float(lo), "hi": float(hi),
            "stake": total, "net": float(p.sum() - total), "max_drawdown": drawdown,
            "min_bankroll": min_bankroll}


def subset(d, mask):
    return Draws(d.nums[mask], d.day[mask], d.slot[mask], d.weekday[mask], d.month[mask])


def _test(test_id, name, hits, n, expected, p, detail=""):
    return {"id": test_id, "name": name, "p": None if p is None else float(p),
            "observed": hits / n if n else None, "expected": expected, "n": int(n),
            "detail": detail}


def _binom(test_id, name, hits, n, expected, detail=""):
    p = binomtest(int(hits), int(n), expected).pvalue if n else None
    return _test(test_id, name, hits, n, expected, p, detail)


def _next_same_day(d):
    return np.flatnonzero(d.day[1:] == d.day[:-1])


# --- E9: exploratory next first position, Loteka only -------------------------------------------

def e9_next_first(d):
    """Count within-day first-position transitions; no per-value inference is attempted."""
    matrix = np.zeros((100, 100), dtype=np.int64)
    idx = _next_same_day(d)
    first = d.nums[:, 0]
    np.add.at(matrix, (first[idx], first[idx + 1]), 1)
    counts = matrix.sum(axis=1)
    return {"expected_rate": 0.01,
            "rows": [{"x": f"{x:02d}", "count": int(counts[x]),
                      "repeats": int(matrix[x, x]),
                      "rate": float(matrix[x, x] / counts[x]) if counts[x] else None}
                     for x in range(100)],
            "matrix": matrix.tolist()}


# --- E1: halves after a streak (#1) -------------------------------------------------------------

def e1_halves(d):
    tests = []
    for hname, half in HALVES.items():
        code = "par" if hname == "par/impar" else "alto"
        series = [half(d.nums[:, pos]) for pos in range(5)]
        runs = [run_lengths(s, d.day) for s in series]
        for scope, positions in (("globo 1", [0]), ("5 globos", range(5))):
            tag = "g1" if scope == "globo 1" else "5g"
            for n in range(1, 11):
                counts = [conditional_switch(series[i], d.day, n, runs[i]) for i in positions]
                sw, tot = sum(c[0] for c in counts), sum(c[1] for c in counts)
                tests.append(_binom(f"E1 {code}-{tag} N={n}",
                                    f"Cambia de mitad ({hname}, {scope}) tras {n} iguales",
                                    sw, tot, 0.5))
    return tests, []


# --- E2: cold numbers (#2) ----------------------------------------------------------------------

def e2_cold(d, pay):
    tests, candidates = [], []
    rows, first = np.arange(len(d.nums)), d.nums[:, 0]
    for variant, ages in (("1º", ages_since(first)), ("cualquier", ages_since(d.nums))):
        for x in COLD_THRESHOLDS:
            mask = ages >= x
            stake = mask.sum(axis=1)
            hits = int(np.count_nonzero(mask[rows, first]))
            tests.append(_binom(f"E2 {variant} X={x}",
                                f"Número frío (≥{x} sorteos sin salir en {variant}) sale 1º",
                                hits, int(stake.sum()), 0.01))
            candidates.append((f"frío en {variant} ≥{x}", stake, (mask * pay).sum(axis=1)))
    return tests, candidates


# --- E3: carry-over between positions (#6) -----------------------------------------------------

def _distinct_mask(rows):
    keep = np.ones(rows.shape, dtype=bool)
    for k in range(1, 5):
        keep[:, k] = ~(rows[:, :k] == rows[:, k:k + 1]).any(axis=1)
    return keep


def e3_carry(d, pay):
    tests, candidates = [], []
    idx = _next_same_day(d)
    prev, nxt_first = d.nums[idx], d.nums[idx + 1, 0]
    for k in range(5):
        hits = int(np.count_nonzero(nxt_first == prev[:, k]))
        tests.append(_binom(f"E3 {k + 1}º→1º", f"El {k + 1}º de un sorteo sale 1º en el siguiente",
                            hits, idx.size, 0.01))
        stake, paid = np.zeros(len(d.nums)), np.zeros(len(d.nums))
        stake[idx + 1] = 1
        paid[idx + 1] = pay[idx + 1, prev[:, k]]
        candidates.append((f"jugar el {k + 1}º anterior", stake, paid))
    keep = _distinct_mask(prev)
    expected = keep.sum(axis=1) / 100
    hits_any = (prev == nxt_first[:, None]).any(axis=1)
    z = (hits_any.sum() - expected.sum()) / math.sqrt(float((expected * (1 - expected)).sum()))
    tests.append(_test("E3 5→1º", "Algún número del sorteo anterior sale 1º",
                       int(hits_any.sum()), idx.size, float(expected.mean()), 2 * norm.sf(abs(z)),
                       f"z={z:+.2f}"))
    stake, paid = np.zeros(len(d.nums)), np.zeros(len(d.nums))
    stake[idx + 1] = keep.sum(axis=1)
    paid[idx + 1] = (np.take_along_axis(pay[idx + 1], prev, axis=1) * keep).sum(axis=1)
    candidates.append(("jugar los 5 anteriores", stake, paid))
    return tests, candidates


# --- E4: doubles (#12) --------------------------------------------------------------------------

def _double_events(d):
    events = []
    for t in np.flatnonzero(_has_repeat(d)).tolist():
        values, counts = np.unique(d.nums[t], return_counts=True)
        events.extend((t, int(v)) for v in values[counts >= 2].tolist())
    return np.array(events, dtype=np.int64).reshape(-1, 2)


def _day_cluster_p(hits, trials, expected):
    """Two-sided normal test of total excess hits, with days as independent clusters."""
    residual = hits - expected * trials
    days = len(residual)
    if days < 2:
        return 1.0
    se = math.sqrt(float(days / (days - 1) * np.square(residual - residual.mean()).sum()))
    return float(2 * norm.sf(abs(residual.sum() / se))) if se else 1.0


def e4_doubles(d, pay):
    tests, candidates = [], []
    events, n = _double_events(d), len(d.nums)
    days = np.unique(d.day)
    for w in DOUBLE_WINDOWS:
        trials = hits1 = hits_any = 0
        daily_trials = np.zeros(len(days))
        daily_hits1 = np.zeros(len(days))
        daily_hits_any = np.zeros(len(days))
        stake, paid = np.zeros(n), np.zeros(n)
        for j in range(1, w + 1):
            t = events[:, 0] + j
            ok = t < n
            t, x, src = t[ok], events[ok, 1], events[ok, 0]
            valid = d.day[t] == d.day[src]
            t, x = t[valid], x[valid]
            first_hit = d.nums[t, 0] == x
            any_hit = (d.nums[t] == x[:, None]).any(axis=1)
            trials += t.size
            hits1 += int(first_hit.sum())
            hits_any += int(any_hit.sum())
            cluster = np.searchsorted(days, d.day[t])
            np.add.at(daily_trials, cluster, 1)
            np.add.at(daily_hits1, cluster, first_hit)
            np.add.at(daily_hits_any, cluster, any_hit)
            np.add.at(stake, t, 1)
            np.add.at(paid, t, pay[t, x])
        tests.append(_test(f"E4 1º w={w}", f"Número doble sale 1º en los {w} sorteos siguientes",
                           hits1, trials, 0.01, _day_cluster_p(daily_hits1, daily_trials, 0.01),
                           f"{len(events)} dobles; inferencia agrupada por {len(days)} días"))
        tests.append(_test(f"E4 any w={w}",
                           f"Número doble sale en cualquier posición en los {w} siguientes",
                           hits_any, trials, P_ANY,
                           _day_cluster_p(daily_hits_any, daily_trials, P_ANY),
                           f"inferencia agrupada por {len(days)} días"))
        candidates.append((f"jugar el doble {w} sorteos", stake, paid))
    return tests, candidates


# --- E5: enter after N virtual misses (#21) ----------------------------------------------------

def _half_pay(pay, half):
    labels = half(np.arange(100))
    return np.stack([pay[:, labels == h].sum(axis=1) for h in (0, 1)], axis=1)


def _streak_bets(d, half, n):
    series = half(d.nums[:, 0])
    runs = run_lengths(series, d.day)
    idx = np.flatnonzero((runs[:-1] >= n) & (d.day[1:] == d.day[:-1]))
    return idx + 1, 1 - series[idx], runs[idx] - n, series


def e5_streak_entry(d, pay, ladder=LADDER, profile=ORIGINAL70):
    """Flat candidates and an explicitly labeled per-number stake ladder."""
    tests, candidates, ladders = [], [], {}
    for hname, half in HALVES.items():
        hp = _half_pay(pay, half)
        for n in STREAKS:
            bet_t, target, rnd, series = _streak_bets(d, half, n)
            wins = int(np.count_nonzero(series[bet_t] == target))
            tests.append(_binom(f"E5 {hname} N≥{n}",
                                f"Tras ≥{n} iguales ({hname}) sale la otra mitad en el 1º",
                                wins, bet_t.size, 0.5))
            stake, paid = np.zeros(len(d.nums)), np.zeros(len(d.nums))
            stake[bet_t], paid[bet_t] = 50, hp[bet_t, target]
            label = f"{hname} tras ≥{n}"
            candidates.append((label, stake, paid))
            first_hits = half(d.nums[bet_t, 0]) == target
            ladders[label] = _ladder_arrays(len(d.nums), bet_t, target, rnd, hp,
                                            ladder=ladder, profile=profile,
                                            first_hits=first_hits)
    return tests, candidates, ladders


def _ladder_arrays(n, bet_t, target, rnd, hp, ladder=LADDER, profile=ORIGINAL70,
                   first_hits=None):
    """Stake until the last round; count its first-position failures even at day end."""
    on = rnd < len(ladder)
    per_number = np.asarray(ladder)[rnd[on]]
    stake, paid = np.zeros(n), np.zeros(n)
    stake[bet_t[on]] = 50 * per_number
    paid[bet_t[on]] = per_number * hp[bet_t[on], target[on]]
    last = on & (rnd == len(ladder) - 1)
    if first_hits is None:
        # Legacy direct helper callers supply only payouts. E5 passes actual first hits.
        first_hits = hp[bet_t, target] >= profile.prizes[0]
    lost_ladders = int(np.count_nonzero(~first_hits[last]))
    return stake, paid, lost_ladders


# --- E6: bold vs timid play (#26) --------------------------------------------------------------

SCENARIOS = ((1000, 2000), (5000, 10000))
MC_SESSIONS = 20_000
_MC_CACHE = {}


def _fair_sessions(bank, goal, style, profile=ORIGINAL70, mode="all"):
    """Reuse Monte Carlo only within the same payout scenario and repeat mode."""
    key = (bank, goal, style, profile, mode)
    if key not in _MC_CACHE:
        rng = np.random.default_rng([bank, goal, 0 if style == "bold" else 1])
        _MC_CACHE[key] = simulate_sessions(MC_SESSIONS, bank, goal, style, rng, profile, mode)
    return _MC_CACHE[key]


def e6_bold(d, pay, profile=ORIGINAL70, mode="all"):
    tests, rows = [], []
    for bank, goal in SCENARIOS:
        for style in ("bold", "timid"):
            real = back_to_back(pay[:, 0], bank, goal, style, profile)
            mc = _fair_sessions(bank, goal, style, profile, mode)
            mc_rate = float(mc["reached"].mean())
            k, n = int(real.sum()), int(real.size)
            label = "audaz" if style == "bold" else "tímida (10 por sorteo)"
            tests.append(_binom(f"E6 {bank}→{goal} {style}",
                                f"Datos reales vs sorteos aleatorios con estos pagos: {label}, {bank}→{goal}",
                                k, n, min(max(mc_rate, 1e-9), 1 - 1e-9)))
            rows.append({"bank": bank, "goal": goal, "style": label,
                         "real_rate": k / n if n else None, "real_n": n,
                         "real_ci": _wilson(k, n), "mc_rate": mc_rate,
                         "mc_ci": _wilson(int(mc["reached"].sum()), MC_SESSIONS),
                         "mc_steps": float(np.median(mc["steps"])), "fair": bank / goal})
    return tests, rows


def _wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


# --- E7: repeated numbers rule (#27) -----------------------------------------------------------

def e7_repeat_rule(d, pay_all, pay_best, profile=ORIGINAL70):
    return {"theory_all": expected_return("all", profile),
            "theory_best": expected_return("best", profile),
            "real_all": float(pay_all.sum() / (100 * len(d.nums))),
            "real_best": float(pay_best.sum() / (100 * len(d.nums))),
            "draws_with_repeat": float(_has_repeat(d).mean()),
            "theory_draws_with_repeat": 1 - math.prod(range(96, 101)) / 100 ** 5}


def _has_repeat(d):
    ordered = np.sort(d.nums, axis=1)
    return (ordered[:, 1:] == ordered[:, :-1]).any(axis=1)


# --- E8: source regime change (#29) ------------------------------------------------------------

def e8_sources(d, source, profile=ORIGINAL70):
    tests = []
    labels = sorted(set(source.tolist()))
    codes = np.searchsorted(labels, source)
    for pos in range(5):
        table = np.zeros((len(labels), 100), dtype=np.int64)
        np.add.at(table, (codes, d.nums[:, pos]), 1)
        _, p, _, _ = chi2_contingency(table, correction=False)
        tests.append(_test(f"E8 globo {pos + 1}", f"Misma distribución por fuente, globo {pos + 1}",
                           0, len(d.nums), None, p))
    has_repeat = _has_repeat(d)
    table = np.array([[np.count_nonzero(has_repeat & (codes == c)),
                       np.count_nonzero(~has_repeat & (codes == c))] for c in range(len(labels))])
    _, p, _, _ = chi2_contingency(table, correction=False)
    rates = ", ".join(f"{lab}: {r[0] / r.sum():.4f}" for lab, r in zip(labels, table, strict=True))
    tests.append(_test("E8 repetidos", "Misma tasa de sorteos con repetidos por fuente",
                       0, len(d.nums), None, p, rates))
    per_source = {}
    for c, lab in enumerate(labels):
        part = subset(d, codes == c)
        audit: list[dict[str, Any]] = [dict(r, id=f"E8 {lab} {r['id']}", name=f"[{lab}] {r['name']}")
                 for r in lottery_tests.run_all(part)]
        # A 100×100 independence table needs ~50,000 observations for 5 expected/cell.
        if len(part.nums) < 50_000:
            for row in audit:
                test_id = row["id"].removeprefix(f"E8 {lab} ")
                if test_id == "B3a" or test_id.startswith("B4."):
                    row["p"] = None
                    row["detail"] += "; N/A: 100×100 expected count <5/cell; exploratory"

        part_pay = payout_matrix(part.nums, "all", profile)
        found = (e1_halves(part)[0] + e2_cold(part, part_pay)[0] + e3_carry(part, part_pay)[0]
                 + e4_doubles(part, part_pay)[0])
        found = [dict(r, id=f"E8 {lab} {r['id']}", name=f"[{lab}] {r['name']}") for r in found]
        tests.extend(audit + found)
        per_source[lab] = {"draws": len(part.nums),
                           "first_day": int(part.day.min()), "last_day": int(part.day.max())}
    return tests, per_source
