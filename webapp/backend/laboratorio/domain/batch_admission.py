"""Shared strict validation, source binding and persistence for v5 profile batches."""

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Any, cast

from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.execution_policy import ExecutionPolicy
from laboratorio.domain.profile_archive import ArchivedBinding, bind_archived_dataset
from laboratorio.domain.profile_request import profile_sha256
from laboratorio.domain.profile_request_v5 import ProfileBatchRequestV5
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileSelector,
    ProfileStaking,
    Q80CyclingStaking,
    _selected,
)
from laboratorio.domain.profile_session_v5 import _staking
from laboratorio.domain.profile_staking import (
    ProfileAudazStaking,
    ProfileRecoveryLadderStaking,
    Q80ReferenceAudazStaking,
    profile_audaz_stake,
    profile_recovery_ladder,
    q80_reference_audaz_stake,
)
from laboratorio.domain.profile_strategy import StrategyDefinition
from laboratorio.importing.datasets import SavedDataset
from laboratorio.settings import Settings

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ARCHIVED = frozenset(
    {
        "archived-cold/v1",
        "archived-transition/v1",
        "archived-topk/v1",
        "archived-parity50/v1",
    }
)


@dataclass(frozen=True, slots=True)
class StrategyReference:
    id: str
    revision: int
    definition_sha256: str

    def __post_init__(self) -> None:
        if type(self.id) is not str or not 1 <= len(self.id) <= 128:
            raise ValueError("strategy reference id is invalid")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("strategy reference revision must be positive")
        if type(self.definition_sha256) is not str or not _HEX64.fullmatch(self.definition_sha256):
            raise ValueError("strategy reference requires a lowercase definition SHA-256")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "revision": self.revision,
            "definition_sha256": self.definition_sha256,
        }


@dataclass(frozen=True, slots=True)
class ProfileBatchSubmission:
    """Validated, closed caller input. It contains references, never definitions or paths."""

    strategy_refs: tuple[StrategyReference, ...]
    profile_id: str
    profile_revision: int
    profile_sha256: str
    dataset_sha256: str
    conditions: ProfileConditions
    max_draws: int
    client_request_id: str

    def __post_init__(self) -> None:
        if type(self.strategy_refs) is not tuple or not 1 <= len(self.strategy_refs) <= 3:
            raise ValueError("one to three exact strategy revision references are required")
        if any(type(ref) is not StrategyReference for ref in self.strategy_refs):
            raise TypeError("strategy_refs must contain StrategyReference values")
        if type(self.profile_id) is not str or not self.profile_id:
            raise ValueError("profile_id is required")
        if type(self.profile_revision) is not int or self.profile_revision < 1:
            raise ValueError("profile_revision must be positive")
        for label, digest in (
            ("profile_sha256", self.profile_sha256),
            ("dataset_sha256", self.dataset_sha256),
        ):
            if type(digest) is not str or not _HEX64.fullmatch(digest):
                raise ValueError(f"{label} must be lowercase SHA-256")
        if type(self.conditions) is not ProfileConditions:
            raise TypeError("common conditions must be ProfileConditions")
        self.conditions.__post_init__()
        if type(self.max_draws) is not int or not 1 <= self.max_draws <= 10_000:
            raise ValueError("max_draws must be between 1 and 10000")
        if type(self.client_request_id) is not str or not 1 <= len(self.client_request_id) <= 128:
            raise ValueError("client_request_id must contain 1 to 128 characters")


@dataclass(frozen=True, slots=True)
class PreparedProfileBatch:
    """Pure validated projection shared by dry-run and transactional admission."""

    request: ProfileBatchRequestV5
    profile_snapshot: GameProfile
    strategy_refs: tuple[dict[str, Any], ...]
    client_request_id: str
    requested_constraints: dict[str, Any]
    effective_constraints: dict[str, Any]
    policy_revision: int
    policy: ExecutionPolicy
    source_identity: dict[str, Any]
    dataset_snapshot: SavedDataset
    archive_binding: ArchivedBinding | None


def prepare_profile_batch(
    repository,
    submission: ProfileBatchSubmission,
    *,
    settings: Settings | None = None,
) -> PreparedProfileBatch:
    """Resolve immutable inputs and limits without reserving identity or writing."""
    if type(submission) is not ProfileBatchSubmission:
        raise TypeError("submission must be a closed ProfileBatchSubmission")
    submission.__post_init__()
    requested_constraints = {
        **_conditions_dict(submission.conditions),
        "max_draws": submission.max_draws,
    }
    try:
        policy_revision, policy = repository.execution_policy()
    except ValueError as exc:
        raise ValueError("corrupt stored execution policy") from exc
    if len(submission.strategy_refs) > policy.max_strategies_per_batch:
        raise ValueError("batch exceeds current max_strategies_per_batch policy")

    try:
        profile = repository.get_game_profile(submission.profile_id, submission.profile_revision)
    except ValueError as exc:
        raise ValueError("corrupt stored profile snapshot") from exc
    if profile is None or profile_sha256(profile) != submission.profile_sha256:
        raise ValueError("profile identity or hash does not match a registered version")
    try:
        dataset = repository.get_dataset(submission.dataset_sha256)
    except ValueError as exc:
        raise ValueError("corrupt stored dataset snapshot") from exc
    if type(dataset) is not SavedDataset:
        raise ValueError("saved dataset not found")
    try:
        envelope = json.loads(dataset.canonical_json)
        dataset_profile = GameProfile.model_validate(envelope["profile"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("saved dataset has an invalid profile snapshot") from exc
    if dataset_profile != profile:
        raise ValueError("saved dataset profile differs from requested registered profile")
    start_matches = sum(
        f"{record.date} {record.time}" == submission.conditions.start_draw
        for record in dataset.preview.records
    )
    if start_matches != 1:
        raise ValueError("start draw must match exactly one canonical source draw")

    definitions = []
    for reference in submission.strategy_refs:
        try:
            snapshot = repository.get_strategy_revision(reference.id, reference.revision)
        except ValueError as exc:
            raise ValueError("corrupt stored strategy revision") from exc
        if snapshot is None:
            raise ValueError("exact strategy revision was not found")
        if snapshot["definition_sha256"] != reference.definition_sha256:
            raise ValueError("strategy revision SHA-256 does not match exact reference")
        definition = snapshot["definition"]
        if type(definition) is not StrategyDefinition:
            raise ValueError("strategy revision did not return a validated definition")
        definitions.append(definition)

    conditions = submission.conditions
    effective_bet_draws = min(
        policy.max_bet_draws,
        conditions.max_bet_draws if conditions.max_bet_draws is not None else policy.max_bet_draws,
    )
    effective_elapsed = min(
        policy.max_elapsed_draws,
        conditions.max_elapsed_draws
        if conditions.max_elapsed_draws is not None
        else policy.max_elapsed_draws,
    )
    effective_max_draws = min(submission.max_draws, effective_elapsed)
    if effective_max_draws < 1:
        raise ValueError("effective operation window is empty")
    effective_conditions = replace(
        conditions,
        max_bet_draws=effective_bet_draws,
        max_elapsed_draws=effective_elapsed,
    )
    effective_constraints = {
        **_conditions_dict(effective_conditions),
        "max_draws": effective_max_draws,
        "policy_revision": policy_revision,
        "policy": policy.as_dict(),
    }

    binding = None
    if any(definition.selector in _ARCHIVED for definition in definitions):
        if type(settings) is not Settings:
            raise ValueError("archived strategy admission requires trusted Settings context")
        binding = bind_archived_dataset(dataset, settings)
        if conditions.start_draw not in binding.history.labels:
            raise ValueError("start draw is outside authenticated archived history")
        start_index = binding.history.labels.index(conditions.start_draw)
        if start_index not in binding.rank_row_ids:
            raise ValueError("start draw has no authenticated archived ranking")

    for definition in definitions:
        _preflight_definition(profile, definition, effective_conditions)
        if definition.selector in _ARCHIVED and binding is None:
            raise ValueError("archived selector requires authenticated source binding")
        for key, value in definition.closing_defaults:
            shared = getattr(effective_conditions, key, None)
            if value is not None and shared != value:
                raise ValueError(
                    f"strategy {key} closing default conflicts with confirmed shared conditions"
                )

    request = ProfileBatchRequestV5(
        5,
        "profile_batch",
        profile.profile_id,
        profile.revision,
        submission.profile_sha256,
        dataset.dataset_sha256,
        effective_conditions,
        tuple(definitions),
        effective_max_draws,
    )
    source_identity = {
        "dataset_sha256": dataset.dataset_sha256,
        "source_sha256": dataset.source_sha256,
        "canonical_sha256": hashlib.sha256(dataset.canonical_json).hexdigest(),
        "row_count": len(dataset.preview.records),
        "profile_id": profile.profile_id,
        "profile_revision": profile.revision,
        "profile_sha256": submission.profile_sha256,
        "archive_bound": binding is not None,
        "archive_history_sha256": binding.history.sha256 if binding else None,
        "archive_rank_row_ids": list(binding.rank_row_ids) if binding else None,
    }
    return PreparedProfileBatch(
        request=request,
        profile_snapshot=profile,
        strategy_refs=tuple(ref.as_dict() for ref in submission.strategy_refs),
        client_request_id=submission.client_request_id,
        requested_constraints=requested_constraints,
        effective_constraints=effective_constraints,
        policy_revision=policy_revision,
        policy=policy,
        source_identity=source_identity,
        dataset_snapshot=dataset,
        archive_binding=binding,
    )


def admit_profile_batch(
    repository,
    submission: ProfileBatchSubmission,
    *,
    settings: Settings | None = None,
    quota_bytes: int | None = None,
    quota_explicit: bool | None = None,
    disk_usage=None,
) -> str:
    """Validate once, then atomically reserve capacity, identity, quota and snapshot."""
    if type(submission) is not ProfileBatchSubmission:
        raise TypeError("submission must be a closed ProfileBatchSubmission")
    submission.__post_init__()
    requested_constraints = {
        **_conditions_dict(submission.conditions),
        "max_draws": submission.max_draws,
    }
    duplicate_digest = hashlib.sha256(
        json.dumps(
            {
                "profile_id": submission.profile_id,
                "profile_revision": submission.profile_revision,
                "profile_sha256": submission.profile_sha256,
                "dataset_sha256": submission.dataset_sha256,
                "strategy_refs": tuple(ref.as_dict() for ref in submission.strategy_refs),
                "requested_constraints": requested_constraints,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    duplicate = repository.find_profile_batch_request(
        submission.client_request_id, duplicate_digest
    )
    if duplicate is not None:
        return duplicate
    prepared = prepare_profile_batch(repository, submission, settings=settings)
    return admit_prepared_profile_batch(
        repository,
        prepared,
        quota_bytes=quota_bytes,
        quota_explicit=quota_explicit,
        disk_usage=disk_usage,
    )


def admit_prepared_profile_batch(
    repository,
    prepared: PreparedProfileBatch,
    *,
    quota_bytes: int | None = None,
    quota_explicit: bool | None = None,
    disk_usage=None,
) -> str:
    """Consume a prepared projection in the repository's atomic admission transaction."""
    if type(prepared) is not PreparedProfileBatch:
        raise TypeError("prepared must be a closed PreparedProfileBatch")
    kwargs = {
        "strategy_refs": prepared.strategy_refs,
        "client_request_id": prepared.client_request_id,
        "requested_constraints": prepared.requested_constraints,
        "effective_constraints": prepared.effective_constraints,
        "policy_revision": prepared.policy_revision,
        "policy": prepared.policy,
        "source_identity": prepared.source_identity,
        "dataset_snapshot": prepared.dataset_snapshot,
        "quota_bytes": quota_bytes,
        "quota_explicit": quota_explicit,
    }
    if disk_usage is not None:
        kwargs["disk_usage"] = disk_usage
    return repository.create_profile_batch_experiment(prepared.request, **kwargs)


def _preflight_definition(
    profile: GameProfile, definition: StrategyDefinition, conditions: ProfileConditions
) -> None:
    if definition.coverage > min(profile.max_coverage, profile.universe_size):
        raise ValueError("strategy coverage exceeds registered profile limits")
    parameters = dict(definition.selector_parameters)
    if definition.selector == "static-numbers/v1" and any(
        number >= profile.universe_size for number in cast(tuple[int, ...], parameters["numbers"])
    ):
        raise ValueError("static strategy number exceeds registered profile universe")
    _selected(profile, _dummy_selector(definition), conditions.start_draw)
    staking = _staking(definition)
    if isinstance(staking, ProfileStaking):
        stake = staking.per_number_stake
    elif isinstance(staking, Q80CyclingStaking):
        from laboratorio.domain.profile_staking import q80_first_prize_ladder

        stake = q80_first_prize_ladder(profile, definition.coverage)[0]
    elif isinstance(staking, ProfileAudazStaking):
        stake = profile_audaz_stake(
            profile, definition.coverage, conditions.capital, conditions.goal
        )
    elif isinstance(staking, ProfileRecoveryLadderStaking):
        values = dict(definition.staking_parameters)
        stake = profile_recovery_ladder(
            profile,
            definition.coverage,
            cast(int, values["target_margin"]),
            cast(int, values["rounds"]),
        )[0]
    elif isinstance(staking, Q80ReferenceAudazStaking):
        stake = q80_reference_audaz_stake(conditions.capital, conditions.goal, profile=profile)
    else:
        raise ValueError("unsupported profile staking definition")
    if stake <= 0:
        raise ValueError("profile cannot fund the first prescribed bet")
    cost = stake * definition.coverage
    if (
        not profile.minimum_stake <= stake <= profile.maximum_stake
        or stake % profile.stake_increment
        or cost > profile.max_exposure
        or cost > conditions.capital
    ):
        raise ValueError("capital or profile bounds cannot fund the first prescribed bet")


def _dummy_selector(definition: StrategyDefinition):
    parameters = dict(definition.selector_parameters)
    if definition.selector == "static-numbers/v1":
        return ProfileSelector(
            1,
            definition.selector,
            definition.coverage,
            numbers=cast(tuple[int, ...], parameters["numbers"]),
        )
    if definition.selector == "seeded-random/hash-sha256-v1":
        return ProfileSelector(
            1,
            definition.selector,
            definition.coverage,
            seed=cast(int, parameters["seed"]),
            algorithm_version="hash-sha256-v1",
        )
    # Archived and parity definitions compile to the core's closed static callback selector.
    return ProfileSelector(
        1,
        "static-numbers/v1",
        definition.coverage,
        numbers=tuple(range(definition.coverage)),
    )


def _conditions_dict(conditions: ProfileConditions) -> dict:
    return {
        "schema_version": conditions.schema_version,
        "start_draw": conditions.start_draw,
        "capital": conditions.capital,
        "goal": conditions.goal,
        "settlement": conditions.settlement.value,
        "max_elapsed_draws": conditions.max_elapsed_draws,
        "max_bet_draws": conditions.max_bet_draws,
        "end_minute": conditions.end_minute,
        "duration_minutes": conditions.duration_minutes,
    }
