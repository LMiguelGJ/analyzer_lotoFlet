"""Healthy/signal/order-null control streams and their acceptance gates.

Healthy streams reuse the real calendar with a fully synthetic, reproducible draw
(sha256_drbg); signal streams start from the same synthetic draw and inject a known,
isolated pattern into column 0 only; the order-null permutes real numbers within
(day, source) groups. None of this reads or reasons about real draw content.
"""

import numpy as np

from chance_rank import protocol
from rng_audit import generators
from rng_audit.lottery_tests import Draws

RELEVANT_SYSTEM = {
    "repeat": ["transition"],
    "carry": ["carry"],
    "hour": ["time"],
    "shift": ["decay", "freq_recent"],
    "streak": ["category"],
}


def _months_template(h):
    months = np.array([int(h.dates[d][5:7]) for d in h.day.tolist()], dtype=np.int64)
    return Draws(nums=h.nums, day=h.day, slot=h.slot, weekday=h.weekday, month=months)


def healthy_history(h, i):
    """Fully synthetic sha256_drbg draw over the real calendar, seed .../healthy/{i:03d}."""
    seed = f"{protocol.PROTOCOL_ID}/healthy/{i:03d}"
    base = generators.sha256_drbg(_months_template(h), seed=seed)
    return h.with_nums(base.nums)


def signal_history(h, kind, q, i):
    """Synthetic draw with an isolated pattern injected into column 0 only.

    Every row always draws a Bernoulli coin and its kind-specific candidate value,
    whether or not the row is eligible, so the RNG consumption per row is fixed
    regardless of q or realized outcomes.
    """
    seed = f"{protocol.PROTOCOL_ID}/signal/{kind}/{q}/{i:03d}"
    base = generators.sha256_drbg(_months_template(h), seed=seed)
    first = base.nums[:, 0].copy()

    intervene = protocol.rng(f"{seed}/intervene")
    opportunities = 0
    applied = 0

    for t in range(h.n):
        coin = intervene.random()
        if kind == "repeat":
            intervene.integers(0, 10)
            eligible = bool(h.eligible[t])
            value = first[t - 1] if eligible else None
        elif kind == "carry":
            intervene.integers(0, 10)
            eligible = bool(h.eligible[t])
            value = base.nums[t - 1, 1] if eligible else None
        elif kind == "hour":
            digit = intervene.integers(0, 10)
            eligible = True
            value = 10 * (int(h.hour[t]) % 10) + int(digit)
        elif kind == "shift":
            digit = intervene.integers(0, 10)
            eligible = True
            value = int(digit) if h.day[t] >= protocol.SIGNAL_SHIFT_DAY else 90 + int(digit)
        elif kind == "streak":
            digit = intervene.integers(0, 50)
            eligible = (t >= 3
                        and h.segment[t] == h.segment[t - 1] == h.segment[t - 2] == h.segment[t - 3]
                        and first[t - 1] % 2 == first[t - 2] % 2 == first[t - 3] % 2)
            value = 2 * int(digit) + (1 - int(first[t - 1] % 2)) if eligible else None
        else:
            raise ValueError(f"Unknown signal kind: {kind}")

        if eligible:
            opportunities += 1
            if coin < q:
                first[t] = value
                applied += 1

    new_nums = base.nums.copy()
    new_nums[:, 0] = first
    history = h.with_nums(new_nums)
    rate = applied / opportunities if opportunities else None
    return history, {"opportunities": opportunities, "applied": applied, "rate": rate}


def order_null_history(h, i):
    """Permute full rows within each (day, source) group, seed .../order/{i:03d}."""
    generator = protocol.rng(f"{protocol.PROTOCOL_ID}/order/{i:03d}")
    new_nums = h.nums.copy()
    for day_idx in range(len(h.dates)):
        for source_idx in range(len(h.sources)):
            idx = np.flatnonzero((h.day == day_idx) & (h.source == source_idx))
            if len(idx) <= 1:
                continue
            perm = generator.permutation(len(idx))
            new_nums[idx] = h.nums[idx][perm]
    return h.with_nums(new_nums)


def healthy_gate(n_rejecting):
    return {"n_rejecting": n_rejecting, "ok": n_rejecting <= protocol.HEALTHY_MAX_REJECTING}


def signal_gate(decisions):
    """``decisions``: kind -> list of per-stream booleans (Holm-rejected at q=0.10)."""
    result = {}
    for kind, stream_decisions in decisions.items():
        n_rejecting = sum(1 for d in stream_decisions if d)
        result[kind] = {"n_rejecting": n_rejecting, "ok": n_rejecting >= 2}
    return result
