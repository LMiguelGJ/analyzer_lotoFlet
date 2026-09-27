"""Tests specific to five independent 00-99 draws taken every five minutes.

Each test returns a dict with ``id``, ``name``, ``p`` (two-sided or upper-tail p-value)
and ``detail``. Serial tests never pair draws from different days.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.stats import binom, chi2, chi2_contingency, chisquare, norm, poisson

LAGS = 187  # one full day of draws


@dataclass
class Draws:
    nums: np.ndarray      # (N, 5) values 0-99 in time order
    day: np.ndarray       # (N,) day ordinal
    slot: np.ndarray      # (N,) minutes since midnight
    weekday: np.ndarray   # (N,) 0 = Monday
    month: np.ndarray     # (N,) 1-12


def _result(test_id, name, p, detail):
    return {"id": test_id, "name": name, "p": float(min(max(p, 0.0), 1.0)), "detail": detail}


def _proportion_test(hits, total, expected):
    z = (hits / total - expected) / math.sqrt(expected * (1 - expected) / total)
    return 2 * norm.sf(abs(z)), z


def _contingency(a, b, size_a, size_b):
    table = np.zeros((size_a, size_b), dtype=np.int64)
    np.add.at(table, (a, b), 1)
    table = table[table.sum(axis=1) > 0][:, table.sum(axis=0) > 0]
    stat, p, dof, _ = chi2_contingency(table, correction=False)
    return p, stat, dof


def _same_day_pairs(d, lag):
    left = np.arange(len(d.day) - lag)
    return left[d.day[left] == d.day[left + lag]]


def modulo_bias(d):
    flat = d.nums.ravel()
    out = []
    for test_id, bits, cut in (("B1a", 8, 56), ("B1b", 16, 36)):
        hits = int(np.count_nonzero(flat < cut))
        p, z = _proportion_test(hits, flat.size, cut / 100)
        biased = cut * math.ceil(2 ** bits / 100) / 2 ** bits
        out.append(_result(
            test_id, f"Sesgo de módulo, fuente de {bits} bits (00-{cut - 1:02d})", p,
            f"observado {hits / flat.size:.5f}, justo {cut / 100:.5f}, "
            f"con sesgo sería {biased:.5f} (z={z:+.2f})"))
    return out


def uniformity(d):
    out = []
    for pos in range(5):
        counts = np.bincount(d.nums[:, pos], minlength=100)
        stat, p = chisquare(counts)
        out.append(_result(f"B2.{pos + 1}", f"Uniformidad globo {pos + 1}", p,
                           f"chi²={stat:.1f} (gl=99)"))
    stat, p = chisquare(np.bincount(d.nums.ravel(), minlength=100))
    out.append(_result("B2.g", "Uniformidad global", p, f"chi²={stat:.1f} (gl=99)"))
    return out


def serial_transitions(d):
    idx = _same_day_pairs(d, 1)
    out = []
    p, stat, dof = _contingency(d.nums[idx, 0], d.nums[idx + 1, 0], 100, 100)
    out.append(_result("B3a", "Sorteo N → N+1, globo 1 (100×100)", p,
                       f"chi²={stat:.0f} (gl={dof}), {len(idx)} pares"))
    a = np.concatenate([d.nums[idx, k] for k in range(5)])
    b = np.concatenate([d.nums[idx + 1, k] for k in range(5)])
    p, stat, dof = _contingency(a, b, 100, 100)
    out.append(_result("B3b", "Sorteo N → N+1, 5 globos juntos", p,
                       f"chi²={stat:.0f} (gl={dof}), {len(a)} pares"))
    p, stat, dof = _contingency(d.nums[idx, 0] % 2, d.nums[idx + 1, 0] % 2, 2, 2)
    out.append(_result("B3c", "Paridad N → N+1, globo 1 (tu Markov orden 1)", p,
                       f"chi²={stat:.2f} (gl={dof})"))
    return out


def position_independence(d):
    out = []
    for i in range(5):
        for j in range(i + 1, 5):
            p, stat, dof = _contingency(d.nums[:, i], d.nums[:, j], 100, 100)
            out.append(_result(f"B4.{i + 1}{j + 1}", f"Globo {i + 1} vs globo {j + 1}", p,
                               f"chi²={stat:.0f} (gl={dof})"))
    return out


def digits(d):
    out = []
    for pos in range(5):
        tens, units = d.nums[:, pos] // 10, d.nums[:, pos] % 10
        stat_t, p_t = chisquare(np.bincount(tens, minlength=10))
        stat_u, p_u = chisquare(np.bincount(units, minlength=10))
        p_i, stat_i, _ = _contingency(tens, units, 10, 10)
        out.append(_result(f"B5.{pos + 1}d", f"Decenas globo {pos + 1}", p_t, f"chi²={stat_t:.1f}"))
        out.append(_result(f"B5.{pos + 1}u", f"Unidades globo {pos + 1}", p_u, f"chi²={stat_u:.1f}"))
        out.append(_result(f"B5.{pos + 1}i", f"Decena vs unidad globo {pos + 1}", p_i,
                           f"chi²={stat_i:.1f}"))
    return out


def gaps(d):
    all_gaps = []
    for pos in range(5):
        series = d.nums[:, pos]
        order = np.lexsort((np.arange(len(series)), series))
        values, index = series[order], order
        same = values[1:] == values[:-1]
        all_gaps.append((index[1:] - index[:-1])[same])
    g = np.concatenate(all_gaps)
    # 20 equiprobable bins of the geometric(p=0.01) distribution.
    edges = np.unique(np.ceil(np.log(1 - np.arange(1, 20) / 20) / np.log(0.99)).astype(int))
    bins = np.searchsorted(edges, g, side="left")
    observed = np.bincount(bins, minlength=len(edges) + 1)
    cdf = 1 - 0.99 ** np.concatenate([edges, [np.inf]])
    probs = np.diff(np.concatenate([[0.0], cdf]))
    stat, p = chisquare(observed, probs * observed.sum())
    return [_result("B6", "Tiempo de retorno de cada número (gaps)", p,
                    f"chi²={stat:.1f} (gl={len(probs) - 1}), {len(g)} gaps, "
                    f"media {g.mean():.2f} (justa 100)")]


def _ljung_box(series, d):
    z = (series - series.mean()) / series.std()
    q, worst, used = 0.0, (0, 0.0), 0
    for lag in range(1, LAGS + 1):
        idx = _same_day_pairs(d, lag)
        if len(idx) < 1000:
            continue
        used += 1
        r = float(np.mean(z[idx] * z[idx + lag]))
        score = r * math.sqrt(len(idx))
        q += score ** 2
        if abs(score) > abs(worst[1]):
            worst = (lag, score)
    return chi2.sf(q, used), q, worst, used


def autocorrelation(d):
    out = []
    for pos in range(5):
        p, q, (lag, score), used = _ljung_box(d.nums[:, pos].astype(float), d)
        out.append(_result(f"B7.{pos + 1}", f"Memoria a 1-{used} sorteos, globo {pos + 1}", p,
                           f"Q={q:.1f} (gl={used}); lag más extremo {lag} (z={score:+.2f})"))
    p, q, (lag, score), used = _ljung_box((d.nums[:, 0] % 2).astype(float), d)
    out.append(_result("B7.p", f"Memoria de la paridad a 1-{used} sorteos, globo 1", p,
                       f"Q={q:.1f} (gl={used}); lag más extremo {lag} (z={score:+.2f})"))
    return out


def time_seeding(d):
    key = {(day, slot): i for i, (day, slot) in enumerate(zip(d.day, d.slot, strict=True))}
    pairs = [(i, key[(day + 1, slot)]) for (day, slot), i in key.items()
             if (day + 1, slot) in key]
    left, right = np.array(pairs).T
    matches = np.count_nonzero(d.nums[left] == d.nums[right], axis=0)
    total = int(matches.sum())
    trials = 5 * len(left)
    p = 2 * min(binom.cdf(total, trials, 0.01), binom.sf(total - 1, trials, 0.01))
    out = [_result("B8a", "Misma hora, días consecutivos (coincidencias)", p,
                   f"{total} coincidencias en {trials} comparaciones, "
                   f"esperadas {trials * 0.01:.0f}")]
    slot_codes = np.unique(d.slot, return_inverse=True)[1]
    p, stat, dof = _contingency(np.repeat(slot_codes, 5), d.nums.ravel(),
                                slot_codes.max() + 1, 100)
    out.append(_result("B8b", "¿Cada horario tiene números propios? (horario × número)", p,
                       f"chi²={stat:.0f} (gl={dof})"))
    return out


def repeats(d):
    n = len(d.nums)
    codes = d.nums.astype(np.int64) @ (100 ** np.arange(5))
    duplicates = n - len(np.unique(codes))
    expected = n * (n - 1) / 2 / 1e10
    out = [_result("B9a", "Sorteos completos repetidos (5 números iguales)",
                   poisson.sf(duplicates - 1, expected),
                   f"{duplicates} repetidos, esperados {expected:.2f}")]
    series = np.ascontiguousarray(d.nums[:, 0], dtype=np.uint8)
    longest = 1
    for length in range(2, 200):
        windows = np.ascontiguousarray(sliding_window_view(series, length))
        exact = windows.view(np.dtype((np.void, length))).ravel()
        if len(np.unique(exact)) == len(exact):
            break
        longest = length
    log_rate = math.log((n - longest + 1) ** 2 / 2) - longest * math.log(100)
    p = -math.expm1(-math.exp(log_rate))
    out.append(_result("B9b", "Secuencia repetida más larga (globo 1)", p,
                       f"la más larga mide {longest} sorteos; "
                       f"con azar lo típico es {math.log(n * n / 2, 100):.1f}"))
    return out


def _linear_relation(x, y):
    worst_p, worst_a = 1.0, 0
    for a in range(100):
        _, p = chisquare(np.bincount((y - a * x) % 100, minlength=100))
        if p < worst_p:
            worst_p, worst_a = p, a
    return min(1.0, worst_p * 100), worst_a


def linear_relations(d):
    idx = _same_day_pairs(d, 1)
    x, y = d.nums[idx, 0].astype(np.int64), d.nums[idx + 1, 0].astype(np.int64)
    p1, a1 = _linear_relation(x, y)
    x2 = d.nums[:, :4].ravel().astype(np.int64)
    y2 = d.nums[:, 1:].ravel().astype(np.int64)
    p2, a2 = _linear_relation(x2, y2)
    return [
        _result("B10a", "Fórmula lineal entre sorteos (x' = a·x + c mod 100)", p1,
                f"peor a={a1}, p corregido por 100 pruebas"),
        _result("B10b", "Fórmula lineal entre globos del mismo sorteo", p2,
                f"peor a={a2}, p corregido por 100 pruebas"),
    ]


def calendar_effects(d):
    flat = d.nums.ravel()
    out = []
    for test_id, name, labels in (
            ("B11a", "Hora del día × número", d.slot // 60),
            ("B11b", "Día de la semana × número", d.weekday),
            ("B11c", "Mes × número", d.month)):
        codes = np.unique(labels, return_inverse=True)[1]
        p, stat, dof = _contingency(np.repeat(codes, 5), flat, codes.max() + 1, 100)
        out.append(_result(test_id, name, p, f"chi²={stat:.0f} (gl={dof})"))
    return out


ALL_TESTS = (modulo_bias, uniformity, serial_transitions, position_independence, digits,
             gaps, autocorrelation, time_seeding, repeats, linear_relations, calendar_effects)


def run_all(d):
    results = []
    for test in ALL_TESTS:
        results.extend(test(d))
    return results
