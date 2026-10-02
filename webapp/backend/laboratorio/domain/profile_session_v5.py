"""Private pure v5 adapter: authenticated source, closed definitions, shared session core."""

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Literal, cast

from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_archive import ArchivedBinding
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileDraw,
    ProfileSelector,
    ProfileSessionResult,
    ProfileStaking,
    Q80CyclingStaking,
    _selected,
    run_profile_session,
)
from laboratorio.domain.profile_staking import (
    ProfileAudazStaking,
    ProfileRecoveryLadderStaking,
    Q80ReferenceAudazStaking,
)
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.importing.datasets import SavedDataset

V5_SESSION_VERSION = 5


class StrategyCalculationFailure(ValueError):
    """A validated definition failed in the isolated financial session kernel."""


@dataclass(frozen=True, slots=True)
class ProfileStrategyResultV5:
    ordinal: int
    definition: StrategyDefinition
    session: ProfileSessionResult
    start_draw_index: int
    prior_cutoff: str | None
    dataset_sha256: str


@dataclass(frozen=True, slots=True)
class ProfileBatchResultV5:
    schema_version: int
    kind: str
    profile_id: str
    profile_revision: int
    profile_sha256: str
    dataset_sha256: str
    results: tuple[ProfileStrategyResultV5, ...]


def run_profile_batch_v5(
    request: ProfileBatchRequestV5,
    profile: GameProfile,
    dataset: SavedDataset,
    binding: ArchivedBinding | None,
    *,
    operation_budget: int,
) -> ProfileBatchResultV5:
    """Run one bounded session per definition over a checked full source snapshot.

    The caller supplies a SavedDataset checked by the importer and a binding made
    from that dataset by bind_archived_dataset. Their complete canonical rows are
    compared here; no result hash is treated as proof of selection authenticity.
    """
    if type(request) is not ProfileBatchRequestV5:
        raise TypeError("request must be ProfileBatchRequestV5")
    request.__post_init__()
    if type(profile) is not GameProfile or type(dataset) is not SavedDataset:
        raise TypeError("profile and dataset must be checked typed snapshots")
    if type(operation_budget) is not int or not 1 <= operation_budget <= 10_000:
        raise ValueError("operation budget must be an integer from 1 to 10000")
    if request.max_draws > operation_budget:
        raise ValueError("request exceeds operation budget")
    profile = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
    if (
        profile.profile_id != request.profile_id
        or profile.revision != request.profile_revision
        or profile_sha256(profile) != request.profile_sha256
    ):
        raise ValueError("batch request/profile binding mismatch")
    if hashlib.sha256(dataset.canonical_json).hexdigest() != dataset.dataset_sha256:
        raise ValueError("dataset canonical hash mismatch")
    if dataset.dataset_sha256 != request.dataset_sha256:
        raise ValueError("batch request/dataset binding mismatch")
    if (
        not dataset.preview.promotable
        or hashlib.sha256(dataset.raw_bytes).hexdigest() != dataset.source_sha256
    ):
        raise ValueError("dataset source is not a checked promotable snapshot")
    try:
        envelope = json.loads(dataset.canonical_json)
        saved_profile = GameProfile.model_validate(envelope["profile"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("dataset profile snapshot is invalid") from exc
    if profile_sha256(saved_profile) != request.profile_sha256:
        raise ValueError("dataset profile differs from request profile")
    records = dataset.preview.records
    if not records:
        raise ValueError("dataset history is empty")
    source_labels = tuple(f"{record.date} {record.time}" for record in records)
    previous_minute = None
    for label, record in zip(source_labels, records, strict=True):
        draw = _record_draw(label, record.numbers)
        if (
            len(draw.results) != profile.positions
            or any(number < 0 or number >= profile.universe_size for number in draw.results)
            or (not profile.allows_repeats and len(set(draw.results)) != len(draw.results))
            or (previous_minute is not None and draw.minute <= previous_minute)
        ):
            raise ValueError("dataset draw rows violate the checked profile source contract")
        previous_minute = draw.minute
    if binding is not None:
        if type(binding) is not ArchivedBinding:
            raise TypeError("binding must be an authenticated ArchivedBinding")
        if (
            dataset.source_sha256 != binding.history.sha256
            or len(records) != binding.canonical_draw_count
        ):
            raise ValueError("dataset source does not match verified archive binding")
        for i, (record, label, numbers) in enumerate(
            zip(records, binding.history.labels, binding.history.nums, strict=True)
        ):
            if source_labels[i] != label or record.numbers != tuple(int(n) for n in numbers):
                raise ValueError(f"dataset row differs from verified binding at {i}")
    elif any(
        d.selector
        in (
            "archived-cold/v1",
            "archived-transition/v1",
            "archived-topk/v1",
            "archived-parity50/v1",
        )
        for d in request.strategies
    ):
        raise ValueError("archived selectors require authenticated binding context")

    start_indices = [
        i for i, label in enumerate(source_labels) if label == request.conditions.start_draw
    ]
    if len(start_indices) != 1:
        raise ValueError("start draw must exist exactly once in the full source")
    start = start_indices[0]
    window = records[start : start + request.max_draws]
    strategy_results = []
    for ordinal, definition in enumerate(request.strategies):
        definition.__post_init__()
        if definition.selector in (
            "archived-cold/v1",
            "archived-transition/v1",
            "archived-topk/v1",
            "archived-parity50/v1",
        ):
            if binding is None:
                raise ValueError("archived selector requires verified binding")
            if start not in binding.rank_row_ids:
                raise ValueError("selected ranked start draw has no archived ranking")
            evaluator_ids = set(binding.rank_row_ids)
        else:
            evaluator_ids = None
        window_draws = []
        for offset, record in enumerate(window):
            index = start + offset
            label = source_labels[index]
            source_row = _record_draw(label, record.numbers)
            enters = evaluator_ids is None or index in evaluator_ids
            window_draws.append(replace(source_row, enter=enters))
        # The session kernel retains ownership of timing, funding, settlement and
        # outcomes. A v5 callback only supplies causal selector output.
        selector = ProfileSelector(
            1,
            "static-numbers/v1",
            definition.coverage,
            numbers=tuple(range(definition.coverage)),
        )
        staking = _staking(definition)
        conditions = _resolved_conditions(request.conditions, definition)

        row_indices = {source_labels[start + i]: start + i for i in range(len(window))}

        select = _selector_for(profile, definition, binding, row_indices)
        selected_by_label = {}
        for row in window_draws:
            if row.enter:
                selected = select(row)
                if (
                    type(selected) is not tuple
                    or len(selected) != definition.coverage
                    or len(set(selected)) != len(selected)
                    or any(
                        type(number) is not int or not 0 <= number < profile.universe_size
                        for number in selected
                    )
                ):
                    raise ValueError("selector output violates the profile selection contract")
                selected_by_label[row.label] = selected

        try:
            session = run_profile_session(
                profile,
                conditions,
                selector,
                staking,
                window_draws,
                row_budget=len(window_draws),
                selected_numbers=lambda row, selections=selected_by_label: selections[row.label],
            )
        except ValueError as exc:
            raise StrategyCalculationFailure(str(exc)) from exc
        strategy_results.append(
            ProfileStrategyResultV5(
                ordinal,
                definition,
                session,
                start,
                binding.prior_cutoff(start)
                if binding
                else source_labels[start - 1]
                if start
                else None,
                dataset.dataset_sha256,
            )
        )
    return ProfileBatchResultV5(
        5,
        "profile_batch_result",
        profile.profile_id,
        profile.revision,
        request.profile_sha256,
        dataset.dataset_sha256,
        tuple(strategy_results),
    )


def _record_draw(label: str, numbers: tuple[int, ...]) -> ProfileDraw:
    from laboratorio.domain.profile_session import _minute

    return ProfileDraw(1, label, _minute(label), tuple(numbers), True)


def _selector_for(
    profile: GameProfile,
    definition: StrategyDefinition,
    binding: ArchivedBinding | None,
    row_indices: dict[str, int],
):
    parameters = dict(definition.selector_parameters)

    def select(row: ProfileDraw) -> tuple[int, ...]:
        index = row_indices[row.label]
        if definition.selector == "static-numbers/v1":
            return cast(tuple[int, ...], parameters["numbers"])
        if definition.selector == "seeded-random/hash-sha256-v1":
            random = ProfileSelector(
                1,
                "seeded-random/hash-sha256-v1",
                definition.coverage,
                seed=cast(int, parameters["seed"]),
                algorithm_version="hash-sha256-v1",
            )
            return _selected(profile, random, row.label)
        if binding is None:
            raise ValueError("archived selector requires verified binding")
        kind = {
            "archived-cold/v1": "cold",
            "archived-transition/v1": "transition",
            "archived-topk/v1": "topk",
            "archived-parity50/v1": "parity",
        }[definition.selector]
        system = cast(str | None, parameters.get("system", kind))
        return binding.select(kind, index, definition.coverage, system=system)

    return select


def _staking(
    definition: StrategyDefinition,
) -> (
    ProfileStaking
    | Q80CyclingStaking
    | ProfileAudazStaking
    | ProfileRecoveryLadderStaking
    | Q80ReferenceAudazStaking
):
    parameters = dict(definition.staking_parameters)
    if definition.staking == "flat-per-number/v1":
        return ProfileStaking(1, "flat-per-number/v1", cast(int, parameters["per_number_stake"]))
    if definition.staking == "q80-first-prize-cycling/v1":
        return Q80CyclingStaking()
    if definition.staking == "profile-audaz/v1":
        return ProfileAudazStaking()
    if definition.staking == "profile-recovery-ladder/v1":
        return ProfileRecoveryLadderStaking(
            cast(int, parameters["target_margin"]),
            cast(int, parameters["rounds"]),
            cast(Literal["cycle", "stop"], parameters["end_mode"]),
        )
    if definition.staking == "q80-reference-audaz/v1":
        return Q80ReferenceAudazStaking()
    raise ValueError("unsupported staking definition")


def _resolved_conditions(
    conditions: ProfileConditions, definition: StrategyDefinition
) -> ProfileConditions:
    settlement_recommendation = dict(definition.closing_defaults).get("settlement")
    if (
        settlement_recommendation is not None
        and settlement_recommendation != conditions.settlement.value
    ):
        raise ValueError("strategy settlement recommendation conflicts with shared conditions")
    return conditions
