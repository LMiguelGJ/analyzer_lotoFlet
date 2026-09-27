"""Control generators that reuse the real timeline (dates and draw times).

``sha256_drbg`` is a deterministic cryptographic generator (healthy baseline). The other
three carry one known implementation defect each, to prove the tests can detect it.
"""

import hashlib
import random

import numpy as np

from rng_audit.lottery_tests import Draws


def _sha256_bytes(seed, count):
    out = bytearray()
    counter = 0
    while len(out) < count:
        out += hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        counter += 1
    return np.frombuffer(bytes(out[:count]), dtype=np.uint8)


def _with_nums(template, nums):
    return Draws(nums.reshape(-1, 5).astype(np.int64), template.day, template.slot,
                 template.weekday, template.month)


def sha256_drbg(template, seed="healthy"):
    needed = template.nums.size
    raw = _sha256_bytes(seed, needed * 3)
    values = raw[raw < 200][:needed] % 100  # 200 = 2 x 100, so rejection keeps it unbiased
    return _with_nums(template, values)


def lcg_low_bits(template, seed=12345):
    state, values = seed, np.empty(template.nums.size, dtype=np.int64)
    for i in range(values.size):
        state = (1103515245 * state + 12345) % 2 ** 31
        values[i] = state % 100
    return _with_nums(template, values)


def modulo_bias_8bit(template, seed="biased"):
    return _with_nums(template, _sha256_bytes(seed, template.nums.size) % 100)


def seeded_by_time(template):
    values = []
    for slot in template.slot.tolist():
        draw_rng = random.Random(slot)  # the same time of day always produces the same draw
        values.extend(draw_rng.randrange(100) for _ in range(5))
    return _with_nums(template, np.array(values))


CONTROLS = {
    "sano (SHA-256)": sha256_drbg,
    "LCG bits bajos": lcg_low_bits,
    "sesgo módulo 8 bits": modulo_bias_8bit,
    "semilla por hora": seeded_by_time,
}
