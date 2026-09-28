"""Frozen study protocol ``chance-rank-v1``: constants, model grid and derived seeds.

Nothing here reads real draws or computes predictive metrics. Every constant and
grid entry is fixed before any result is observed; changing this file changes
``protocol_hash()``, which is how downstream stages detect a different protocol.
"""

import hashlib
import json

import numpy as np

PROTOCOL_ID = "chance-rank-v1"
EXPECTED_SHA256 = "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711"

K_VALUES = (1, 5, 10, 20, 25, 30, 40, 50)
PRIMARY_K = 25
HORIZONS = (1, 5, 10, 20)
HORIZON_BLOCK = 20
STEP_MINUTES = 5
WARMUP = 2000

INITIAL_TRAIN_DAYS = 180
OUTER_BLOCK_DAYS = 28
INNER_BLOCKS = 3
SUPERVISED_REFIT_DAYS = 7

ALPHA = 0.01
BOOT_REPS = 10000
BOOT_BLOCK_DAYS = 7
SENSITIVITY_BLOCK_DAYS = (1, 14)
MIN_FOLD_TARGETS = 500
PRACTICAL_MIN_LIFT = 0.01
PRACTICAL_FOLD_SHARE = 0.70

RANDOM_REALIZATIONS = 100
HEALTHY_STREAMS = 20
HEALTHY_MAX_REJECTING = 2
SIGNAL_TYPES = ("repeat", "carry", "hour", "shift", "streak")
SIGNAL_Q = (0.02, 0.10)
SIGNAL_SEEDS = 3
SIGNAL_SHIFT_DAY = 283
ORDER_PERMUTATIONS = 20
CALIBRATION_BINS = 10

TARGETS = ("pos1", "pos2", "pos3", "pos4", "pos5", "any")
PRIMARY_TARGET = "pos1"

_MIX_STEPS = (0.0, 0.25, 0.5, 0.75, 1.0)
_MIX_WINDOWS = (20, 100, 500, 2000)


def _mix_configs():
    """15 (w_hist, w_recent, w_age) triples in ascending order; windows only matter
    when w_recent > 0, so a w_recent == 0 triple gets a single window=None config."""
    configs = []
    for w_hist in _MIX_STEPS:
        for w_recent in _MIX_STEPS:
            w_age = 1.0 - w_hist - w_recent
            if w_age not in _MIX_STEPS or w_age < 0:
                continue
            if w_recent == 0.0:
                configs.append({"w_hist": w_hist, "w_recent": w_recent, "w_age": w_age,
                                "window": None})
            else:
                for window in _MIX_WINDOWS:
                    configs.append({"w_hist": w_hist, "w_recent": w_recent, "w_age": w_age,
                                     "window": window})
    return configs


MODEL_GRID = {
    "freq_hist": [
        {"scope": "position", "window": None},
        {"scope": "position", "window": 20000},
        {"scope": "global", "window": None},
        {"scope": "global", "window": 20000},
    ],
    "freq_recent": [{"window": w} for w in _MIX_WINDOWS],
    "decay": [{"half_life": h} for h in _MIX_WINDOWS],
    "cold": [{"scope": "position"}, {"scope": "any"}],
    "notebook": [{"weights": [0.45, 0.45, 0.10], "window": w} for w in _MIX_WINDOWS],
    "mix": _mix_configs(),
    "transition": [{"lam": lam} for lam in (100, 1000)],
    "carry": [{"origin": j, "lam": lam} for j in range(1, 6) for lam in (100, 1000)],
    "doubles": [{"lam": lam} for lam in (100, 1000)],
    "category": [{"kind": kind, "lam": lam}
                 for kind in ("parity", "lowhigh", "decade", "ending") for lam in (100, 1000)],
    "time": [{"context": context, "lam": lam}
             for context in ("hour", "weekday", "daypos") for lam in (100, 1000)],
    "ensemble": [{"method": "borda"}, {"method": "vote"}],
}

SUPERVISED_GRID = {
    "logistic": [{"C": c, "window": w} for c in (0.01, 0.1, 1.0) for w in (10000, 30000)],
    "tree": [{"max_depth": d, "min_samples_leaf": m, "window": w}
             for d in (3, 5) for m in (200, 1000) for w in (10000, 30000)],
}

INTERPRETABLE_FAMILIES = tuple(MODEL_GRID)
SUPERVISED_FAMILIES = ("logistic", "tree")
SELECTORS = ("select_interpretable", "select_all")
BASELINES_PRIMARY = ("uniform", "recent500")

# Seed label templates, appended to f"{PROTOCOL_ID}/..." and consumed by ``rng()``.
SEED_LABELS = {
    "tie": "tie",
    "fixed": "fixed",
    "random": "random/{realization:03d}",
    "inference": "inference",
    "inference_l1": "inference/L1",
    "inference_l14": "inference/L14",
    "healthy": "healthy/{i:03d}",
    "signal": "signal/{kind}/{q}/{i:03d}",
    "order": "order/{i:03d}",
}

BUDGET = {
    "max_processes": 2,
    "ram_gb": 4,
    "artifacts_gb": 10,
    "block_hours": 2,
}

# (member name, family, params) triples scored by the "ensemble" family.
ENSEMBLE_MEMBERS = (
    ("hist", "freq_hist", {"scope": "position", "window": None}),
    ("recent", "freq_recent", {"window": 500}),
    ("age", "cold", {"scope": "position"}),
    ("transition", "transition", {"lam": 1000}),
    ("time", "time", {"context": "hour", "lam": 1000}),
)

ABLATION_RULE = {
    "notebook": "drop_one_component_renormalized",
    "ensemble": "borda_drop_one_member",
}

DAYPOS_BUCKETS = (0, 50, 100, 150)
RUN_LENGTH_CAP = 5
CATEGORY_KINDS = ("parity", "lowhigh", "decade", "ending")

SUPERVISED_SOLVER = "lbfgs"
SUPERVISED_MAX_ITER = 500
SUPERVISED_TOL = 1e-4
SUPERVISED_CLASS_WEIGHT = None
SUPERVISED_WINDOWS = (10000, 30000)

# One English one-liner per execution decision recorded in odd/tasks/chance-rank.md,
# frozen here so protocol_hash() also covers them.
DECISIONS = {
    "D1": "Observed day = a date with >=1 row (566); external folds use day indices.",
    "D2": "Segment = same-day chain of exact 5-minute-step rows; primary eligible "
          "target = a row with a predecessor in its segment; warmup 2000 rows.",
    "D3": "Ranking tie-break: tie = permutation of 0..99 from SHA-256('.../tie'); "
          "order by (-score, tie[v]); winner rank = #(score greater) + "
          "#(equal score with lower tie).",
    "D4": "Seeds: integer = first 8 bytes big-endian of SHA-256(label), used in "
          "numpy.random.Generator(PCG64).",
    "D5": "Category families use lambda in {100, 1000}, the same grid as the other "
          "conditional families (the plan did not fix lambda for this row).",
    "D6": "Supervised models train on min(window, available) prior eligible "
          "targets; marginal fallback only if fewer than 2000 are available.",
    "D7": "The practical criterion 'positive in >=70% of folds' is required "
          "against each baseline separately (uniform and recent500), counting "
          "external folds with >=500 targets.",
    "D8": "Supervised refit happens in 7-observed-day chunks aligned to the inner "
          "block grid (day 96 + 7k); causal predictions per chunk are reused "
          "across folds since they depend only on the prefix.",
    "D9": "Bootstrap uses a fresh generator per contrast with the same label "
          "('.../inference' for 7-day blocks; '.../L1' and '.../L14' for "
          "sensitivity), so all contrasts share the same paired day resamples.",
    "D10": "System classification (Top-25 H1 pos1): consistent-historical / "
           "exploratory-signal / inconclusive / no-improvement-detected, from the "
           "full practical criterion, unilateral raw p<0.05 vs both baselines, or "
           "the CI99 bound vs uniform; unstable flag if L1/L14 flips sign or the "
           "Holm decision.",
    "D11": "Distribution-shift control: the relevant family is the system "
           "internally selected among decay U freq_recent configs (the plan's "
           "'EWMA/recent'); repeat->transition, carry->carry, hour->time, "
           "streak->category.",
    "D12": "Ablations: 17 total (12 notebook + 5 ensemble); notebook-no_recent "
           "variants are identical across windows but kept by id.",
}


def _render_value(value):
    if value is None:
        return "none"
    if isinstance(value, (list, tuple)):
        return "/".join(_render_value(v) for v in value)
    return str(value)


def config_id(family, params):
    """Stable string identifier, unique per (family, params) across the whole grid."""
    parts = [f"{key}={_render_value(params[key])}" for key in sorted(params)]
    return f"{family}:" + ",".join(parts)


def all_configs(include_supervised=True):
    """(config_id, family, params) triples, families in ``MODEL_GRID`` order."""
    configs = [(config_id(family, params), family, params)
               for family, variants in MODEL_GRID.items() for params in variants]
    if include_supervised:
        configs += [(config_id(family, params), family, params)
                    for family, variants in SUPERVISED_GRID.items() for params in variants]
    return configs


def seed_int(label):
    """Integer seed: first 8 bytes big-endian of sha256(label)."""
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")


def rng(label):
    return np.random.Generator(np.random.PCG64(seed_int(label)))


def tie_priority():
    """int64[100]: priority[v] = position of value v in a fixed random permutation.

    Lower priority wins ties, common to every family (protocol section on
    normalization/tie-breaking).
    """
    permutation = rng(f"{PROTOCOL_ID}/tie").permutation(100)
    priority = np.empty(100, dtype=np.int64)
    priority[permutation] = np.arange(100, dtype=np.int64)
    return priority


def fixed_ranking():
    """A fixed ranking (best first), independent of any observed data."""
    return rng(f"{PROTOCOL_ID}/fixed").permutation(100).astype(np.int64)


def protocol_dict():
    return {
        "protocol_id": PROTOCOL_ID,
        "expected_sha256": EXPECTED_SHA256,
        "k_values": list(K_VALUES),
        "primary_k": PRIMARY_K,
        "horizons": list(HORIZONS),
        "horizon_block": HORIZON_BLOCK,
        "step_minutes": STEP_MINUTES,
        "warmup": WARMUP,
        "initial_train_days": INITIAL_TRAIN_DAYS,
        "outer_block_days": OUTER_BLOCK_DAYS,
        "inner_blocks": INNER_BLOCKS,
        "supervised_refit_days": SUPERVISED_REFIT_DAYS,
        "alpha": ALPHA,
        "boot_reps": BOOT_REPS,
        "boot_block_days": BOOT_BLOCK_DAYS,
        "sensitivity_block_days": list(SENSITIVITY_BLOCK_DAYS),
        "min_fold_targets": MIN_FOLD_TARGETS,
        "practical_min_lift": PRACTICAL_MIN_LIFT,
        "practical_fold_share": PRACTICAL_FOLD_SHARE,
        "random_realizations": RANDOM_REALIZATIONS,
        "healthy_streams": HEALTHY_STREAMS,
        "healthy_max_rejecting": HEALTHY_MAX_REJECTING,
        "signal_types": list(SIGNAL_TYPES),
        "signal_q": list(SIGNAL_Q),
        "signal_seeds": SIGNAL_SEEDS,
        "signal_shift_day": SIGNAL_SHIFT_DAY,
        "order_permutations": ORDER_PERMUTATIONS,
        "calibration_bins": CALIBRATION_BINS,
        "targets": list(TARGETS),
        "primary_target": PRIMARY_TARGET,
        "interpretable_families": list(INTERPRETABLE_FAMILIES),
        "supervised_families": list(SUPERVISED_FAMILIES),
        "selectors": list(SELECTORS),
        "baselines_primary": list(BASELINES_PRIMARY),
        "model_grid": MODEL_GRID,
        "supervised_grid": SUPERVISED_GRID,
        "seed_labels": SEED_LABELS,
        "budget": BUDGET,
        "ensemble_members": [list(member) for member in ENSEMBLE_MEMBERS],
        "ablation_rule": ABLATION_RULE,
        "daypos_buckets": list(DAYPOS_BUCKETS),
        "run_length_cap": RUN_LENGTH_CAP,
        "category_kinds": list(CATEGORY_KINDS),
        "supervised_settings": {
            "solver": SUPERVISED_SOLVER,
            "max_iter": SUPERVISED_MAX_ITER,
            "tol": SUPERVISED_TOL,
            "class_weight": SUPERVISED_CLASS_WEIGHT,
            "windows": list(SUPERVISED_WINDOWS),
            "refit_days": SUPERVISED_REFIT_DAYS,
        },
        "decisions": DECISIONS,
    }


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def protocol_hash():
    return hashlib.sha256(canonical_json(protocol_dict()).encode("utf-8")).hexdigest()
