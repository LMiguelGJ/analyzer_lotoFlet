"""Control datasets on the real timeline.

``healthy`` is the SHA-256 generator from the RNG audit. ``rigged`` starts from it and plants
the four patterns the experiments look for, so each experiment must be able to detect one.
"""

import numpy as np

from rng_audit.generators import sha256_drbg
from rng_audit.lottery_tests import Draws

COLD_AGE = 300


def healthy(template):
    return sha256_drbg(template)


def rigged(template, seed=2026):
    """Healthy draws plus four planted first-position patterns.

    1. After 5+ odd first numbers in a row (same day) the next first number is even 65% of the time.
    2. With 5% probability the first number repeats the previous draw's 2nd number (same day).
    3. With 5% probability a number doubled in the previous draw (same day) comes out first.
    4. A number absent from 1st place for 300+ draws comes out first ~3% of the time instead of 1%.
    """
    rng = np.random.default_rng(seed)
    nums = sha256_drbg(template, seed="rigged").nums.copy()
    last_first = np.full(100, -1)
    odd_run = 0
    for t in range(len(nums)):
        same_day = t > 0 and template.day[t] == template.day[t - 1]
        if not same_day:
            odd_run = 0
        cold = np.flatnonzero(t - last_first >= COLD_AGE)
        if cold.size and rng.random() < min(0.5, 0.02 * cold.size):
            nums[t, 0] = rng.choice(cold)
        if same_day:
            values, counts = np.unique(nums[t - 1], return_counts=True)
            doubled = values[counts >= 2]
            if doubled.size and rng.random() < 0.05:
                nums[t, 0] = rng.choice(doubled)
            if rng.random() < 0.05:
                nums[t, 0] = nums[t - 1, 1]
        if odd_run >= 5 and nums[t, 0] % 2 == 1 and rng.random() < 0.3:
            nums[t, 0] ^= 1
        odd_run = odd_run + 1 if nums[t, 0] % 2 == 1 else 0
        last_first[nums[t, 0]] = t
    return Draws(nums, template.day, template.slot, template.weekday, template.month)


CONTROLS = {"sano (SHA-256)": healthy, "trampa (4 patrones sembrados)": rigged}
