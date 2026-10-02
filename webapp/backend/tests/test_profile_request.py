"""The v1 request is inert, strict JSON binding, not a legacy job."""

import hashlib
import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from pydantic import ValidationError

from laboratorio.domain.contracts import MAX_MONEY, ExperimentRequest, GameProfile, SettlementMode
from laboratorio.domain.profile_request import (
    ProfileExperimentRequest,
    load_profile_request,
    profile_sha256,
    serialize_profile_request,
)
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector, ProfileStaking

PROFILE = {
    "schema_version": 1,
    "profile_id": "test-profile",
    "revision": 2,
    "universe_size": 3,
    "positions": 1,
    "allows_repeats": False,
    "multipliers": [{"numerator": 3, "denominator": 2}],
    "currency": "DOP",
    "scale": 2,
    "stake_increment": 2,
    "minimum_stake": 2,
    "maximum_stake": 20,
    "max_coverage": 2,
    "max_exposure": 40,
    "best_rule": "maximum-payout/v1",
}


def request(**changes):
    p = GameProfile.model_validate(PROFILE)
    values: dict[str, Any] = dict(
        kind="profile",
        schema_version=1,
        name="Prueba",
        dataset_sha256="a" * 64,
        profile_id=p.profile_id,
        profile_revision=p.revision,
        profile_sha256=profile_sha256(p),
        conditions=ProfileConditions(
            1,
            "2025-01-01 05:10",
            20,
            100,
            SettlementMode.BEST,
            max_elapsed_draws=3,
            max_bet_draws=2,
            end_minute=30_000_000,
            duration_minutes=60,
        ),
        selector=ProfileSelector(
            1,
            "seeded-random/hash-sha256-v1",
            2,
            seed=0,
            algorithm_version="hash-sha256-v1",
        ),
        staking=ProfileStaking(1, "flat-per-number/v1", 2),
        entry_policy="all_rows/v1",
    )
    values.update(changes)
    return ProfileExperimentRequest(**values)


def wire(**changes):
    value = json.loads(serialize_profile_request(request()))
    value.update(changes)
    return json.dumps(value)


def test_profile_hash_is_full_validated_sorted_compact_utf8_json_not_dataset_digest():
    p = GameProfile.model_validate(PROFILE)
    reference = hashlib.sha256(
        json.dumps(PROFILE, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    assert profile_sha256(p) == reference
    assert profile_sha256(p) != "a" * 64
    assert profile_sha256(GameProfile.model_validate({**PROFILE, "revision": 3})) != reference
    assert profile_sha256(GameProfile.model_validate({**PROFILE, "currency": "USD"})) != reference
    reordered = dict(reversed(list(PROFILE.items())))
    assert profile_sha256(GameProfile.model_validate(reordered)) == reference
    with pytest.raises(ValidationError):
        profile_sha256(p.model_copy(update={"positions": 2}))
    with pytest.raises(ValidationError):
        forged = p.multipliers[0].model_copy(update={"numerator": True})
        profile_sha256(p.model_copy(update={"multipliers": (forged,)}))
    with pytest.raises(TypeError):
        profile_sha256(PROFILE)  # type: ignore[arg-type]


def test_full_roundtrip_frozen_typed_nested_objects_and_explicit_null_slots():
    source = request()
    text = serialize_profile_request(source)
    canonical = json.dumps(
        json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert text == canonical
    assert load_profile_request(text) == source
    loaded = load_profile_request(text)
    assert type(loaded.conditions) is ProfileConditions
    assert type(loaded.selector) is ProfileSelector
    assert type(loaded.staking) is ProfileStaking
    assert loaded.conditions.settlement is SettlementMode.BEST
    assert loaded.selector.seed == 0
    assert loaded.staking.per_number_stake == 2  # exact 0.02 DOP at profile scale 2
    assert request(name="\tPrueba\t").name == "Prueba"
    assert load_profile_request(wire(name="\tPrueba\t")).name == "Prueba"
    assert json.loads(text)["selector"]["numbers"] is None
    with pytest.raises(FrozenInstanceError):
        loaded.name = "Other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        loaded.staking.per_number_stake = 3  # type: ignore[misc]
    static = request(selector=ProfileSelector(1, "static-numbers/v1", 2, numbers=(0, 2)))
    assert load_profile_request(serialize_profile_request(static)) == static
    assert json.loads(serialize_profile_request(static))["selector"]["seed"] is None
    assert (
        load_profile_request(
            serialize_profile_request(
                request(
                    conditions=ProfileConditions(
                        1, "2025-01-01 05:10", 20, 100, SettlementMode.ALL
                    ),
                )
            )
        ).conditions.max_bet_draws
        is None
    )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("kind", "legacy"),
        ("kind", True),
        ("schema_version", 2),
        ("schema_version", True),
        ("dataset_sha256", "A" * 64),
        ("dataset_sha256", "a" * 63),
        ("profile_sha256", "z" * 64),
        ("profile_id", "Bad ID"),
        ("profile_revision", True),
        ("profile_revision", 0),
        ("entry_policy", "conditional-entry/v1"),
        ("entry_policy", "all_rows"),
        ("name", " "),
    ],
)
def test_malformed_envelope_rejected(field, bad):
    with pytest.raises((ValueError, ValidationError)):
        load_profile_request(wire(**{field: bad}))


def test_no_hidden_seed_stake_settlement_or_version_and_no_extra_fields():
    base = json.loads(wire())
    for path, field in (
        ((), "kind"),
        ((), "entry_policy"),
        ((), "profile_sha256"),
        (("conditions",), "settlement"),
        (("selector",), "seed"),
        (("selector",), "algorithm_version"),
        (("staking",), "per_number_stake"),
    ):
        value = json.loads(json.dumps(base))
        target = value
        for key in path:
            target = target[key]
        target.pop(field)
        with pytest.raises((ValueError, TypeError)):
            load_profile_request(json.dumps(value))
    for field in ("conditions", "selector", "staking"):
        value = json.loads(json.dumps(base))
        value[field]["surprise"] = 1
        with pytest.raises(ValueError):
            load_profile_request(json.dumps(value))
    with pytest.raises(ValueError):
        load_profile_request(wire(surprise=1))
    with pytest.raises(ValueError, match="duplicate"):
        load_profile_request(wire()[:-1] + ',"kind":"profile"}')


@pytest.mark.parametrize(
    "section,field,bad",
    [
        ("conditions", "capital", 1.0),
        ("conditions", "goal", True),
        ("conditions", "capital", MAX_MONEY + 1),
        ("conditions", "settlement", 1),
        ("conditions", "settlement", "other"),
        ("conditions", "schema_version", 2),
        ("selector", "coverage", True),
        ("selector", "seed", 0.0),
        ("selector", "seed", None),
        ("selector", "capability", "freq_hist"),
        ("selector", "algorithm_version", "hash-sha256-v2"),
        ("selector", "schema_version", 2),
        ("staking", "per_number_stake", 2.0),
        ("staking", "per_number_stake", True),
        ("staking", "per_number_stake", MAX_MONEY + 1),
        ("staking", "capability", "ladder"),
    ],
)
def test_nested_invalid_exact_types_capabilities_and_money(section, field, bad):
    value = json.loads(wire())
    value[section][field] = bad
    with pytest.raises((ValueError, TypeError)):
        load_profile_request(json.dumps(value))


def test_static_numbers_are_exact_integers_and_unknown_entry_or_numbers_shape_rejected():
    value = json.loads(
        serialize_profile_request(
            request(
                selector=ProfileSelector(1, "static-numbers/v1", 2, numbers=(0, 2)),
            )
        )
    )
    for numbers in ([0, True], [0, 2.0], [0, 0], "0,2"):
        bad = {**value, "selector": {**value["selector"], "numbers": numbers}}
        with pytest.raises(ValueError):
            load_profile_request(json.dumps(bad))
    with pytest.raises(ValueError):
        load_profile_request(wire(entry_policy="conditional-entry/v1"))
    with pytest.raises(ValueError):
        load_profile_request("{invalid")
    with pytest.raises(ValueError):
        load_profile_request(wire()[:-1] + ',"staking":{"capability":"ladder"}}')


def test_forged_frozen_nested_objects_are_revalidated_before_serialization():
    source = request()
    object.__setattr__(source.selector, "algorithm_version", "other")
    with pytest.raises(ValueError, match="algorithm"):
        serialize_profile_request(source)
    with pytest.raises(ValueError):
        ProfileSelector(1, "parity", 2)


def test_legacy_experiment_contract_is_unchanged_and_separate():
    legacy = ExperimentRequest.model_validate(
        {
            "name": "Old",
            "conditions": {
                "start_draw": "2025-01-01 05:10",
                "capital": 10,
                "goal": 20,
                "settlement": "all",
                "seed": 0,
            },
            "strategies": [
                {
                    "name": "Legacy",
                    "selector": "random",
                    "coverage": 1,
                    "staking": "flat",
                }
            ],
        }
    )
    assert legacy.conditions.seed == 0
    assert "kind" not in legacy.model_dump()
    with pytest.raises(ValidationError):
        ExperimentRequest.model_validate({**legacy.model_dump(), "kind": "profile"})
