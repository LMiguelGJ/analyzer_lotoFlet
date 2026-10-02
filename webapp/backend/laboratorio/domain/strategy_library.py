"""Closed strategy-definition codec, compatibility projection and bootstrap presets."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from typing import cast

from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_capabilities import audaz_compatible_coverage
from laboratorio.domain.profile_request_v5 import _definition_dict, _load_definition
from laboratorio.domain.profile_staking import profile_recovery_ladder
from laboratorio.domain.profile_strategy import StrategyDefinition

PRESETS = (
    (
        "preset-paridad-50-plana",
        "Paridad plana: selección archivada de 50 números y apuesta unitaria.",
        StrategyDefinition.reference_parity_50,
    ),
    (
        "preset-transicion-1-audaz",
        "Transición: selección archivada y apuesta audaz de referencia.",
        StrategyDefinition.reference_transition_audaz,
    ),
    (
        "preset-frios-25-escalera",
        "Fríos: selección archivada de 25 números y escalera Q80 cíclica.",
        StrategyDefinition.reference_cold_25,
    ),
)
EXECUTION_UNAVAILABLE = (
    "Ejecución no disponible: falta el dispatch público de ProfileBatchRequestV5."
)


def strategy_payload(value: object) -> StrategyDefinition:
    """Decode exactly the existing v5 definition contract; never accept arbitrary DSL."""
    if not isinstance(value, Mapping):
        raise ValueError("definition must be a closed strategy object")
    try:
        raw = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
        definition = _load_definition(raw)
        definition.__post_init__()
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid closed strategy definition") from exc
    return definition


def definition_snapshot(definition: StrategyDefinition) -> tuple[str, str]:
    if type(definition) is not StrategyDefinition:
        raise TypeError("definition must be a StrategyDefinition")
    definition.__post_init__()
    serialized = json.dumps(
        _definition_dict(definition),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def registered_preset_definition(preset_id: str) -> tuple[str, StrategyDefinition]:
    """Return a trusted preset; user names never establish or erase this identity."""
    if type(preset_id) is str:
        for registered_id, explanation, constructor in PRESETS:
            if registered_id == preset_id:
                return explanation, constructor()
    raise ValueError("unknown reference preset identity")


def compatibility_projection(
    definition: StrategyDefinition,
    profile: GameProfile | None = None,
    *,
    reference_preset_id: str | None = None,
) -> dict:
    """Project generic profile math or a trusted preset identity.

    A supplied preset ID is an assertion of trusted identity: it must be registered
    and match the preset's full behavior, ignoring only its display name. Without an
    ID, even an exact copy is evaluated as an ordinary generic composition.
    """
    if type(definition) is not StrategyDefinition:
        raise TypeError("definition must be a StrategyDefinition")
    if reference_preset_id is not None:
        _, trusted_definition = registered_preset_definition(reference_preset_id)
        if replace(definition, name=trusted_definition.name) != trusted_definition:
            raise ValueError("definition does not match registered reference preset")
    requirements = {
        "definition_version": definition.definition_version,
        "coverage": definition.coverage,
        "selector": definition.selector,
        "staking": definition.staking,
        "profile_fields": [
            "universe_size",
            "max_coverage",
            "minimum_stake",
            "maximum_stake",
            "stake_increment",
            "max_exposure",
            "multipliers",
            "scale",
        ],
        "archived_context": "authenticated dataset binding required for archived selectors",
        "capital_admission": (
            "not evaluated: this projection has no starting capital, goal, or session conditions"
        ),
    }
    failures: list[str] = []
    if profile is not None:
        if type(profile) is not GameProfile:
            raise TypeError("profile must be a registered GameProfile snapshot")
        if definition.coverage > min(profile.universe_size, profile.max_coverage):
            failures.append("coverage exceeds profile universe or maximum coverage")
        parameters = dict(definition.selector_parameters)
        numbers = cast(tuple[int, ...], parameters.get("numbers", ()))
        if any(type(n) is not int or n >= profile.universe_size for n in numbers):
            failures.append("static selector number is outside profile universe")
        if definition.staking == "flat-per-number/v1":
            stake = cast(int, dict(definition.staking_parameters)["per_number_stake"])
            total = stake * definition.coverage
            if (
                stake < profile.minimum_stake
                or stake > profile.maximum_stake
                or stake % profile.stake_increment
                or total > profile.max_exposure
            ):
                failures.append("flat stake is incompatible with profile limits")
        if reference_preset_id in {
            preset_id for preset_id, _, _ in PRESETS
        } and not _reference_profile(profile):
            failures.append("reference preset requires its exact 100/5 repeat 80/8/4/2/1 profile")
        if (
            definition.staking == "profile-audaz/v1"
            and definition.coverage > audaz_compatible_coverage(profile)
        ):
            failures.append(
                "profile audaz requires positive first-position net gain at this coverage"
            )
        if definition.staking == "profile-recovery-ladder/v1":
            parameters = dict(definition.staking_parameters)
            try:
                profile_recovery_ladder(
                    profile,
                    definition.coverage,
                    cast(int, parameters["target_margin"]),
                    cast(int, parameters["rounds"]),
                )
            except ValueError as exc:
                failures.append(str(exc))
        if definition.staking in (
            "q80-first-prize-cycling/v1",
            "q80-reference-audaz/v1",
        ) and tuple((p.numerator, p.denominator) for p in profile.multipliers) != (
            (80, 1),
            (8, 1),
            (4, 1),
            (2, 1),
            (1, 1),
        ):
            failures.append("Q80 staking component requires its exact 80/8/4/2/1 payout profile")
    return {
        "definition_valid": True,
        "profile_context_provided": profile is not None,
        "profile_compatible": None if profile is None else not failures,
        "incompatibilities": failures,
        "requirements": requirements,
        "execution_available": False,
        "execution_unavailable_reason": EXECUTION_UNAVAILABLE,
    }


def _reference_profile(profile: GameProfile) -> bool:
    return (
        profile.universe_size == 100
        and profile.positions == 5
        and profile.allows_repeats
        and tuple((p.numerator, p.denominator) for p in profile.multipliers)
        == ((80, 1), (8, 1), (4, 1), (2, 1), (1, 1))
    )


def seed_presets(repository, **kwargs):
    """Explicit startup-only idempotent seed; never called at module import or on GET."""
    return repository.seed_strategy_presets(PRESETS, **kwargs)
