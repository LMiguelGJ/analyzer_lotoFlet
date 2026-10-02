"""Private, strict canonical request codec for one session per strategy."""

import json
import re
from dataclasses import dataclass
from typing import Any

from laboratorio.domain.contracts import (
    MAX_PROFILE_REVISION,
    MAX_STRATEGIES,
    SettlementMode,
    normalize_strategy_name,
)
from laboratorio.domain.profile_request import _digest, _unique_pairs
from laboratorio.domain.profile_session import ProfileConditions
from laboratorio.domain.profile_strategy import StrategyDefinition

REQUEST_KIND = "profile_batch"
REQUEST_VERSION = 5
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PROFILE_ID = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")


@dataclass(frozen=True, slots=True)
class ProfileBatchRequestV5:
    schema_version: int
    kind: str
    profile_id: str
    profile_revision: int
    profile_sha256: str
    dataset_sha256: str
    conditions: ProfileConditions
    strategies: tuple[StrategyDefinition, ...]
    max_draws: int
    source_version: str = "canonical-history/v1"

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != REQUEST_VERSION:
            raise ValueError("unsupported profile batch request version")
        if type(self.kind) is not str or self.kind != REQUEST_KIND:
            raise ValueError("unsupported profile batch request kind")
        if type(self.profile_id) is not str or not _PROFILE_ID.fullmatch(self.profile_id):
            raise ValueError("invalid profile_id")
        if (
            type(self.profile_revision) is not int
            or not 1 <= self.profile_revision <= MAX_PROFILE_REVISION
        ):
            raise ValueError("invalid profile_revision")
        _digest(self.profile_sha256, "profile_sha256")
        _digest(self.dataset_sha256, "dataset_sha256")
        if type(self.conditions) is not ProfileConditions:
            raise TypeError("conditions must be ProfileConditions")
        self.conditions.__post_init__()
        if type(self.strategies) is not tuple or not 1 <= len(self.strategies) <= min(
            MAX_STRATEGIES, 3
        ):
            raise ValueError("strategies must contain one to three definitions")
        keys = []
        for definition in self.strategies:
            if type(definition) is not StrategyDefinition:
                raise TypeError("each strategy must be a StrategyDefinition snapshot")
            definition.__post_init__()
            keys.append(normalize_strategy_name(definition.name))
            for key, value in definition.closing_defaults:
                if key == "settlement" and value != self.conditions.settlement.value:
                    raise ValueError(
                        "strategy settlement recommendation conflicts with shared conditions"
                    )
        if len(keys) != len(set(keys)):
            raise ValueError("strategy names must be unique within a batch")
        if type(self.max_draws) is not int or not 1 <= self.max_draws <= 10_000:
            raise ValueError("max_draws must be an integer from 1 to 10000")
        if type(self.source_version) is not str or self.source_version != "canonical-history/v1":
            raise ValueError("unsupported source version")


def serialize_profile_batch_v5(request: ProfileBatchRequestV5) -> str:
    if type(request) is not ProfileBatchRequestV5:
        raise TypeError("request must be ProfileBatchRequestV5")
    request.__post_init__()
    c = request.conditions
    return _canonical(
        {
            "schema_version": 5,
            "kind": REQUEST_KIND,
            "profile_id": request.profile_id,
            "profile_revision": request.profile_revision,
            "profile_sha256": request.profile_sha256,
            "dataset_sha256": request.dataset_sha256,
            "conditions": {
                "schema_version": c.schema_version,
                "start_draw": c.start_draw,
                "capital": c.capital,
                "goal": c.goal,
                "settlement": c.settlement.value,
                "max_elapsed_draws": c.max_elapsed_draws,
                "max_bet_draws": c.max_bet_draws,
                "end_minute": c.end_minute,
                "duration_minutes": c.duration_minutes,
            },
            "strategies": [_definition_dict(d) for d in request.strategies],
            "max_draws": request.max_draws,
            "source_version": request.source_version,
        }
    )


def load_profile_batch_v5(payload: str) -> ProfileBatchRequestV5:
    if type(payload) is not str:
        raise TypeError("payload must be a JSON string")
    try:
        raw = json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid profile batch request JSON") from exc
    if type(raw) is dict and (
        type(raw.get("schema_version")) is not int or raw.get("schema_version") != 5
    ):
        raise ValueError("unsupported profile batch request version")
    raw = _exact_keys(
        raw,
        {
            "schema_version",
            "kind",
            "profile_id",
            "profile_revision",
            "profile_sha256",
            "dataset_sha256",
            "conditions",
            "strategies",
            "max_draws",
            "source_version",
        },
        "request",
    )
    c = raw["conditions"]
    c = _exact_keys(c, set(ProfileConditions.__dataclass_fields__), "conditions")
    if type(c["settlement"]) is not str or c["settlement"] not in ("all", "best"):
        raise ValueError("settlement must be all or best")
    conditions = ProfileConditions(**{**c, "settlement": SettlementMode(c["settlement"])})
    if type(raw["strategies"]) is not list:
        raise ValueError("strategies must be an array")
    return ProfileBatchRequestV5(
        5,
        raw["kind"],
        raw["profile_id"],
        raw["profile_revision"],
        raw["profile_sha256"],
        raw["dataset_sha256"],
        conditions,
        tuple(_load_definition(item) for item in raw["strategies"]),
        raw["max_draws"],
        raw["source_version"],
    )


def _definition_dict(d: StrategyDefinition) -> dict:
    return {
        "definition_version": d.definition_version,
        "name": d.name,
        "selector": d.selector,
        "coverage": d.coverage,
        "staking": d.staking,
        "selector_parameters": {
            key: list(value) if type(value) is tuple else value
            for key, value in d.selector_parameters
        },
        "staking_parameters": dict(d.staking_parameters),
        "closing_defaults": dict(d.closing_defaults),
    }


def _load_definition(raw: object) -> StrategyDefinition:
    raw = _exact_keys(
        raw,
        {
            "definition_version",
            "name",
            "selector",
            "coverage",
            "staking",
            "selector_parameters",
            "staking_parameters",
            "closing_defaults",
        },
        "strategy",
    )
    for key in ("selector_parameters", "staking_parameters", "closing_defaults"):
        if type(raw[key]) is not dict:
            raise ValueError(f"{key} must be an object")
    selector = dict(raw["selector_parameters"])
    if "numbers" in selector:
        if type(selector["numbers"]) is not list:
            raise ValueError("static numbers must be an array")
        selector["numbers"] = tuple(selector["numbers"])
    return StrategyDefinition(
        raw["definition_version"],
        raw["name"],
        raw["selector"],
        raw["coverage"],
        raw["staking"],
        tuple(sorted(selector.items())),
        tuple(sorted(raw["staking_parameters"].items())),
        tuple(sorted(raw["closing_defaults"].items())),
    )


def _exact_keys(value: object, expected: set[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or value.keys() != expected:
        raise ValueError(f"{name} must contain exactly {sorted(expected)}")
    return value


def _canonical(value: dict) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _bad_constant(value: str) -> None:
    raise ValueError(f"non-JSON number: {value}")
