"""NIST SP 800-22 rev1a statistical tests, implemented with numpy/scipy.

Every test takes a 0/1 ``np.uint8`` array and returns a list of p-values.
An empty list means the test is not applicable to the given sequence length.
"""

import math

import numpy as np
from scipy.special import erfc, gammaincc
from scipy.stats import norm


def _pm1(bits):
    return bits.astype(np.int64) * 2 - 1


def _windows(bits, k, wrap):
    """Integer value of every overlapping k-bit window (MSB first)."""
    if k == 0:
        return np.zeros(len(bits), dtype=np.int64)
    seq = np.concatenate([bits, bits[: k - 1]]) if wrap else bits
    count = len(bits) if wrap else len(bits) - k + 1
    values = np.zeros(count, dtype=np.int64)
    for i in range(k):
        values = (values << 1) | seq[i : i + count]
    return values


def frequency(bits):
    s_obs = abs(_pm1(bits).sum()) / math.sqrt(len(bits))
    return [float(erfc(s_obs / math.sqrt(2)))]


def block_frequency(bits, m=128):
    blocks = len(bits) // m
    if blocks < 1:
        return []
    pi = bits[: blocks * m].reshape(blocks, m).mean(axis=1)
    chi2 = 4 * m * np.sum((pi - 0.5) ** 2)
    return [float(gammaincc(blocks / 2, chi2 / 2))]


def runs(bits):
    n = len(bits)
    pi = bits.mean()
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return [0.0]
    v_obs = 1 + int(np.count_nonzero(bits[1:] != bits[:-1]))
    num = abs(v_obs - 2 * n * pi * (1 - pi))
    den = 2 * math.sqrt(2 * n) * pi * (1 - pi)
    return [float(erfc(num / den))]


_LONGEST_RUN = [
    (750_000, 10_000, [10, 11, 12, 13, 14, 15, 16],
     [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]),
    (6_272, 128, [4, 5, 6, 7, 8, 9],
     [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]),
    (128, 8, [1, 2, 3, 4], [0.2148, 0.3672, 0.2305, 0.2188]),
]


def longest_run(bits):
    n = len(bits)
    params = next((p for p in _LONGEST_RUN if n >= p[0]), None)
    if params is None:
        return []
    _, m, edges, pis = params
    blocks = n // m
    matrix = bits[: blocks * m].reshape(blocks, m).astype(np.int64)
    current = np.zeros(blocks, dtype=np.int64)
    longest = np.zeros(blocks, dtype=np.int64)
    for col in range(m):
        current = (current + 1) * matrix[:, col]
        np.maximum(longest, current, out=longest)
    clipped = np.clip(longest, edges[0], edges[-1])
    counts = np.array([np.count_nonzero(clipped == e) for e in edges])
    expected = blocks * np.array(pis)
    chi2 = np.sum((counts - expected) ** 2 / expected)
    return [float(gammaincc((len(edges) - 1) / 2, chi2 / 2))]


def gf2_rank(rows, ncols):
    rows = list(rows)
    rank = 0
    for col in range(ncols - 1, -1, -1):
        bit = 1 << col
        pivot = next((i for i in range(rank, len(rows)) if rows[i] & bit), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and rows[i] & bit:
                rows[i] ^= rows[rank]
        rank += 1
    return rank


def binary_matrix_rank(bits, size=32):
    matrices = len(bits) // (size * size)
    if matrices < 38:
        return []
    rows = _windows(bits[: matrices * size * size], size, wrap=False)[:: size]
    rows = rows.reshape(matrices, size)
    ranks = np.array([gf2_rank(r.tolist(), size) for r in rows])
    full = np.count_nonzero(ranks == size)
    minus_one = np.count_nonzero(ranks == size - 1)
    rest = matrices - full - minus_one
    probs = (0.2888, 0.5776, 0.1336)
    chi2 = sum((obs - p * matrices) ** 2 / (p * matrices)
               for obs, p in zip((full, minus_one, rest), probs, strict=True))
    return [float(math.exp(-chi2 / 2))]


def dft(bits):
    n = len(bits)
    modulus = np.abs(np.fft.fft(_pm1(bits)))[: n // 2]
    threshold = math.sqrt(math.log(1 / 0.05) * n)
    n0 = 0.95 * n / 2
    n1 = np.count_nonzero(modulus < threshold)
    d = (n1 - n0) / math.sqrt(n * 0.95 * 0.05 / 4)
    return [float(erfc(abs(d) / math.sqrt(2)))]


def aperiodic_templates(m):
    templates = []
    for value in range(2 ** m):
        word = format(value, f"0{m}b")
        if all(word[:k] != word[-k:] for k in range(1, m)):
            templates.append(value)
    return templates


def non_overlapping_template(bits, m=9, blocks=8):
    block_len = len(bits) // blocks
    if block_len < m * 10:
        return []
    mu = (block_len - m + 1) / 2 ** m
    var = block_len * (1 / 2 ** m - (2 * m - 1) / 2 ** (2 * m))
    counts = np.zeros((blocks, 2 ** m), dtype=np.int64)
    for j in range(blocks):
        block = bits[j * block_len : (j + 1) * block_len]
        # Aperiodic templates cannot overlap themselves, so every match is non-overlapping.
        counts[j] = np.bincount(_windows(block, m, wrap=False), minlength=2 ** m)
    pvals = []
    for template in aperiodic_templates(m):
        chi2 = np.sum((counts[:, template] - mu) ** 2) / var
        pvals.append(float(gammaincc(blocks / 2, chi2 / 2)))
    return pvals


def overlapping_template(bits, m=9, block_len=1032):
    blocks = len(bits) // block_len
    if blocks < 50:
        return []
    pis = np.array([0.364091, 0.185659, 0.139381, 0.100571, 0.070432, 0.139865])
    matrix = bits[: blocks * block_len].reshape(blocks, block_len)
    hits = np.array([np.count_nonzero(_windows(row, m, wrap=False) == 2 ** m - 1)
                     for row in matrix])
    counts = np.bincount(np.minimum(hits, 5), minlength=6)
    expected = blocks * pis
    chi2 = np.sum((counts - expected) ** 2 / expected)
    return [float(gammaincc(5 / 2, chi2 / 2))]


def universal(bits, block_len=7, init_blocks=1280):
    n = len(bits)
    if n < 904_960:
        return []
    total_blocks = n // block_len
    k = total_blocks - init_blocks
    values = _windows(bits[: total_blocks * block_len], block_len, wrap=False)[:: block_len]
    last_seen = np.zeros(2 ** block_len, dtype=np.int64)
    for i in range(init_blocks):
        last_seen[values[i]] = i + 1
    total = 0.0
    for i in range(init_blocks, total_blocks):
        total += math.log2(i + 1 - last_seen[values[i]])
        last_seen[values[i]] = i + 1
    fn = total / k
    expected, variance = 6.1962507, 3.125
    c = 0.7 - 0.8 / block_len + (4 + 32 / block_len) * k ** (-3 / block_len) / 15
    sigma = c * math.sqrt(variance / k)
    return [float(erfc(abs(fn - expected) / (math.sqrt(2) * sigma)))]


def berlekamp_massey(bits):
    poly_c, poly_b, length, last = 1, 1, 0, -1
    window = 0
    for n, bit in enumerate(bits.tolist()):
        window = (window << 1) | bit
        if (poly_c & window).bit_count() & 1:
            previous = poly_c
            poly_c ^= poly_b << (n - last)
            if 2 * length <= n:
                length, last, poly_b = n + 1 - length, n, previous
    return length


def linear_complexity(bits, m=500):
    blocks = len(bits) // m
    if blocks < 200:
        return []
    mu = m / 2 + (9 + (-1) ** (m + 1)) / 36 - (m / 3 + 2 / 9) / 2 ** m
    t = np.array([(-1) ** m * (berlekamp_massey(bits[i * m : (i + 1) * m]) - mu) + 2 / 9
                  for i in range(blocks)])
    edges = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]
    counts = np.bincount(np.searchsorted(edges, t, side="left"), minlength=7)
    pis = np.array([0.010417, 0.03125, 0.125, 0.5, 0.25, 0.0625, 0.020833])
    chi2 = np.sum((counts - blocks * pis) ** 2 / (blocks * pis))
    return [float(gammaincc(3, chi2 / 2))]


def _psi2(bits, k):
    if k <= 0:
        return 0.0
    counts = np.bincount(_windows(bits, k, wrap=True), minlength=2 ** k)
    return 2 ** k / len(bits) * np.sum(counts.astype(np.float64) ** 2) - len(bits)


def serial(bits, m=16):
    psi_m, psi_m1, psi_m2 = (_psi2(bits, m - i) for i in range(3))
    delta1 = psi_m - psi_m1
    delta2 = psi_m - 2 * psi_m1 + psi_m2
    return [float(gammaincc(2 ** (m - 2), delta1 / 2)),
            float(gammaincc(2 ** (m - 3), delta2 / 2))]


def _phi(bits, k):
    if k <= 0:
        return 0.0
    counts = np.bincount(_windows(bits, k, wrap=True), minlength=2 ** k)
    probs = counts[counts > 0] / len(bits)
    return float(np.sum(probs * np.log(probs)))


def approximate_entropy(bits, m=10):
    n = len(bits)
    apen = _phi(bits, m) - _phi(bits, m + 1)
    chi2 = 2 * n * (math.log(2) - apen)
    return [float(gammaincc(2 ** (m - 1), chi2 / 2))]


def _cusum_p(x):
    n = len(x)
    z = int(np.max(np.abs(np.cumsum(x))))
    sqrt_n = math.sqrt(n)
    total = 1.0
    for k in range(int((-n / z + 1) / 4), int((n / z - 1) / 4) + 1):
        total -= norm.cdf((4 * k + 1) * z / sqrt_n) - norm.cdf((4 * k - 1) * z / sqrt_n)
    for k in range(int((-n / z - 3) / 4), int((n / z - 1) / 4) + 1):
        total += norm.cdf((4 * k + 3) * z / sqrt_n) - norm.cdf((4 * k + 1) * z / sqrt_n)
    return float(total)


def cumulative_sums(bits):
    x = _pm1(bits)
    return [_cusum_p(x), _cusum_p(x[::-1])]


def _excursion_walk(bits):
    walk = np.concatenate([[0], np.cumsum(_pm1(bits)), [0]])
    zeros = walk == 0
    cycles = int(zeros.sum()) - 1
    cycle_id = np.cumsum(zeros) - 1
    return walk, cycles, cycle_id


def random_excursions(bits):
    walk, cycles, cycle_id = _excursion_walk(bits)
    if cycles < max(0.005 * math.sqrt(len(bits)), 500):
        return []
    pvals = []
    for state in (-4, -3, -2, -1, 1, 2, 3, 4):
        a = abs(state)
        visits = np.bincount(cycle_id[walk == state], minlength=cycles)[:cycles]
        observed = np.bincount(np.minimum(visits, 5), minlength=6)
        pis = [1 - 1 / (2 * a)]
        pis += [1 / (4 * a * a) * (1 - 1 / (2 * a)) ** (k - 1) for k in range(1, 5)]
        pis.append(1 / (2 * a) * (1 - 1 / (2 * a)) ** 4)
        expected = cycles * np.array(pis)
        chi2 = np.sum((observed - expected) ** 2 / expected)
        pvals.append(float(gammaincc(5 / 2, chi2 / 2)))
    return pvals


def random_excursions_variant(bits):
    walk, cycles, _ = _excursion_walk(bits)
    if cycles < max(0.005 * math.sqrt(len(bits)), 500):
        return []
    pvals = []
    for state in [s for s in range(-9, 10) if s != 0]:
        visits = int(np.count_nonzero(walk == state))
        den = math.sqrt(2 * cycles * (4 * abs(state) - 2))
        pvals.append(float(erfc(abs(visits - cycles) / den)))
    return pvals


def run_suite(bits):
    """Run all 15 tests with SP 800-22 recommended parameters for ``len(bits)``."""
    n = len(bits)
    serial_m = min(16, max(2, int(math.log2(n)) - 3))
    apen_m = min(10, max(2, int(math.log2(n)) - 6))
    return {
        "frequency": frequency(bits),
        "block_frequency": block_frequency(bits),
        "runs": runs(bits),
        "longest_run": longest_run(bits),
        "binary_matrix_rank": binary_matrix_rank(bits),
        "dft": dft(bits),
        "non_overlapping_template": non_overlapping_template(bits),
        "overlapping_template": overlapping_template(bits),
        "universal": universal(bits),
        "linear_complexity": linear_complexity(bits),
        "serial": serial(bits, serial_m),
        "approximate_entropy": approximate_entropy(bits, apen_m),
        "cumulative_sums": cumulative_sums(bits),
        "random_excursions": random_excursions(bits),
        "random_excursions_variant": random_excursions_variant(bits),
    }
