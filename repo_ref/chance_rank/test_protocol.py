"""Fixed-point checks for the frozen chance-rank-v1 protocol data."""

import hashlib

import numpy as np
import pytest

from chance_rank import protocol
from chance_rank.protocol import (
    INTERPRETABLE_FAMILIES,
    MODEL_GRID,
    all_configs,
    canonical_json,
    config_id,
    fixed_ranking,
    protocol_dict,
    protocol_hash,
    rng,
    seed_int,
    tie_priority,
)


def test_config_ids_are_unique_and_total_count_is_107():
    configs = all_configs()
    ids = [config_id for config_id, _family, _params in configs]
    assert len(ids) == len(set(ids))
    assert len(configs) == 107


def test_interpretable_configs_count_is_93_and_supervised_is_14():
    configs = all_configs()
    interpretable = [c for c in configs if c[1] in INTERPRETABLE_FAMILIES]
    supervised = [c for c in configs if c[1] not in INTERPRETABLE_FAMILIES]
    assert len(interpretable) == 93
    assert len(supervised) == 14


def test_all_configs_without_supervised_only_has_interpretable_families():
    configs = all_configs(include_supervised=False)
    assert len(configs) == 93
    assert all(family in INTERPRETABLE_FAMILIES for _cid, family, _params in configs)


def test_mix_has_45_configs_with_single_entry_when_recent_weight_is_zero():
    mix_configs = MODEL_GRID["mix"]
    assert len(mix_configs) == 45
    zero_recent = [c for c in mix_configs if c["w_recent"] == 0]
    assert len(zero_recent) == 5
    assert all(c["window"] is None for c in zero_recent)
    ids = {config_id("mix", c) for c in mix_configs}
    assert len(ids) == 45
    for c in mix_configs:
        assert abs(c["w_hist"] + c["w_recent"] + c["w_age"] - 1.0) < 1e-9


def test_seed_int_matches_manual_sha256_prefix():
    label = "chance-rank-v1/tie"
    expected = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")
    assert seed_int(label) == expected
    assert seed_int(label) == seed_int(label)


def test_rng_is_deterministic_for_the_same_label():
    a = rng("chance-rank-v1/example").random(5)
    b = rng("chance-rank-v1/example").random(5)
    assert np.array_equal(a, b)


def test_tie_priority_is_a_stable_permutation_of_0_to_99():
    first = tie_priority()
    second = tie_priority()
    assert np.array_equal(first, second)
    assert sorted(first.tolist()) == list(range(100))
    assert first.dtype == np.int64


def test_fixed_ranking_is_a_stable_permutation_of_0_to_99():
    first = fixed_ranking()
    second = fixed_ranking()
    assert np.array_equal(first, second)
    assert sorted(first.tolist()) == list(range(100))


def test_protocol_hash_is_stable_and_changes_with_protocol_dict():
    first = protocol_hash()
    second = protocol_hash()
    assert first == second
    modified = protocol_dict()
    modified["alpha"] = modified["alpha"] * 2
    changed_hash = hashlib.sha256(canonical_json(modified).encode("utf-8")).hexdigest()
    assert changed_hash != first


# --- CR-1 fix round: protocol_dict must also freeze budget/seed/model constants -----


def test_protocol_dict_contains_the_newly_frozen_keys():
    d = protocol_dict()
    for key in ("seed_labels", "budget", "ensemble_members", "ablation_rule",
                "daypos_buckets", "run_length_cap", "category_kinds",
                "supervised_settings", "decisions"):
        assert key in d


def test_decisions_cover_d1_through_d12_with_english_one_liners():
    decisions = protocol_dict()["decisions"]
    expected_ids = {f"D{i}" for i in range(1, 13)}
    assert set(decisions) == expected_ids
    for one_liner in decisions.values():
        assert isinstance(one_liner, str) and one_liner


@pytest.mark.parametrize("attr,mutate", [
    ("SEED_LABELS", lambda v: {**v, "tie": "tie-changed"}),
    ("BUDGET", lambda v: {**v, "max_processes": v["max_processes"] + 1}),
    ("ENSEMBLE_MEMBERS", lambda v: v[:-1]),
    ("ABLATION_RULE", lambda v: {**v, "notebook": "changed"}),
    ("DAYPOS_BUCKETS", lambda v: (0, 25, 100, 150)),
    ("RUN_LENGTH_CAP", lambda v: v + 1),
    ("CATEGORY_KINDS", lambda v: (*v, "extra")),
    ("SUPERVISED_SOLVER", lambda v: "newton-cg"),
    ("SUPERVISED_MAX_ITER", lambda v: v + 1),
    ("SUPERVISED_TOL", lambda v: v * 2),
    ("SUPERVISED_WINDOWS", lambda v: (*v, 50000)),
    ("DECISIONS", lambda v: {**v, "D1": "changed"}),
])
def test_protocol_hash_changes_when_a_newly_frozen_constant_changes(monkeypatch, attr, mutate):
    baseline = protocol_hash()
    current = getattr(protocol, attr)
    monkeypatch.setattr(protocol, attr, mutate(current))
    assert protocol_hash() != baseline
