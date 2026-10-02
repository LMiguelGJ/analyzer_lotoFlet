"""Pure, versioned profile experiment request contract (no job or storage side effects).

Version 1 binds a dataset digest to a *reference* to one complete GameProfile.
``profile_sha256`` is SHA-256 of that profile's entire validated v1 JSON object,
UTF-8 encoded with sorted keys, compact separators and non-ASCII characters
unescaped. It is NOT the dataset digest convention: ``dataset_sha256`` is an
opaque, already-computed content digest supplied by the importer. Future versions
must dispatch by kind/schema_version, not reinterpret these v1 bytes or fields.
Money is exact integer units of 10**(-profile.scale), never a JSON float.
"""

import json
import re
from dataclasses import dataclass
from hashlib import sha256

from pydantic import TypeAdapter

from laboratorio.domain.contracts import (
    MAX_PROFILE_REVISION,
    GameProfile,
    Name,
    SettlementMode,
)
from laboratorio.domain.profile_capabilities import ENTRY_POLICY as ENTRY_POLICY
from laboratorio.domain.profile_capabilities import require_supported
from laboratorio.domain.profile_session import (
    ProfileConditions,
    ProfileSelector,
    ProfileStaking,
)

REQUEST_VERSION = 1
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PROFILE_ID = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
_NAME = TypeAdapter(Name)


def _canonical(value: dict) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def profile_sha256(profile: GameProfile) -> str:
    """Hash the *validated full profile*, not just its identity or revision.

    Revalidation protects against Pydantic model_copy(update=...) and forged
    nested frozen models. The canonical v1 input is the JSON-mode model_dump
    of GameProfile, not model_dump_json's unsorted wire representation.
    """
    if type(profile) is not GameProfile:
        raise TypeError("profile must be a GameProfile")
    validated = GameProfile.model_validate(profile.model_dump(mode="python", warnings="error"))
    canonical = _canonical(validated.model_dump(mode="json", warnings="error"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _digest(value: object, field: str) -> None:
    if type(value) is not str or not _HEX64.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")


def _keys(value: object, required: set[str], field: str) -> dict:
    if type(value) is not dict or value.keys() != required:
        raise ValueError(f"{field} must contain exactly {sorted(required)}")
    return value


@dataclass(frozen=True, slots=True)
class ProfileExperimentRequest:
    """One explicitly named strategy against one immutable dataset/profile binding."""

    kind: str
    schema_version: int
    name: str
    dataset_sha256: str
    profile_id: str
    profile_revision: int
    profile_sha256: str
    conditions: ProfileConditions
    selector: ProfileSelector
    staking: ProfileStaking
    entry_policy: str

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind != "profile":
            raise ValueError("unsupported request kind")
        if type(self.schema_version) is not int or self.schema_version != REQUEST_VERSION:
            raise ValueError("unsupported profile request version")
        if type(self.name) is not str:
            raise ValueError("name must be a string")
        object.__setattr__(self, "name", _NAME.validate_python(self.name))
        _digest(self.dataset_sha256, "dataset_sha256")
        _digest(self.profile_sha256, "profile_sha256")
        if type(self.profile_id) is not str or not _PROFILE_ID.fullmatch(self.profile_id):
            raise ValueError("invalid profile_id")
        if (
            type(self.profile_revision) is not int
            or not 1 <= self.profile_revision <= MAX_PROFILE_REVISION
        ):
            raise ValueError("invalid profile_revision")
        require_supported("entry", self.entry_policy, self.schema_version)
        for field, model in (
            ("conditions", ProfileConditions),
            ("selector", ProfileSelector),
            ("staking", ProfileStaking),
        ):
            value = getattr(self, field)
            if type(value) is not model:
                raise TypeError(f"{field} must be a {model.__name__}")
            value.__post_init__()  # frozen dataclasses can be forged via object.__setattr__


def serialize_profile_request(request: ProfileExperimentRequest) -> str:
    """Canonical v1 JSON, with all optional slots explicitly present as null."""
    if type(request) is not ProfileExperimentRequest:
        raise TypeError("request must be a ProfileExperimentRequest")
    request.__post_init__()
    c, s, t = request.conditions, request.selector, request.staking
    return _canonical(
        {
            "kind": request.kind,
            "schema_version": request.schema_version,
            "name": request.name,
            "dataset_sha256": request.dataset_sha256,
            "profile_id": request.profile_id,
            "profile_revision": request.profile_revision,
            "profile_sha256": request.profile_sha256,
            "entry_policy": request.entry_policy,
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
            "selector": {
                "schema_version": s.schema_version,
                "capability": s.capability,
                "coverage": s.coverage,
                "numbers": list(s.numbers) if s.numbers is not None else None,
                "seed": s.seed,
                "algorithm_version": s.algorithm_version,
            },
            "staking": {
                "schema_version": t.schema_version,
                "capability": t.capability,
                "per_number_stake": t.per_number_stake,
            },
        }
    )


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise ValueError(f"non-JSON number: {value}")


def load_profile_request(payload: str) -> ProfileExperimentRequest:
    """Parse only the exact v1 wire shape; never infer seed, stake or settlement."""
    if type(payload) is not str:
        raise TypeError("payload must be a JSON string")
    try:
        decoded = json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid profile request JSON") from exc
    raw = _keys(decoded, set(ProfileExperimentRequest.__dataclass_fields__), "request")
    c = _keys(raw["conditions"], set(ProfileConditions.__dataclass_fields__), "conditions")
    s = _keys(raw["selector"], set(ProfileSelector.__dataclass_fields__), "selector")
    t = _keys(raw["staking"], set(ProfileStaking.__dataclass_fields__), "staking")
    if type(c["settlement"]) is not str or c["settlement"] not in ("all", "best"):
        raise ValueError("settlement must explicitly be all or best")
    if s["numbers"] is not None and type(s["numbers"]) is not list:
        raise ValueError("numbers must be an explicit JSON array or null")
    return ProfileExperimentRequest(
        kind=raw["kind"],
        schema_version=raw["schema_version"],
        name=raw["name"],
        dataset_sha256=raw["dataset_sha256"],
        profile_id=raw["profile_id"],
        profile_revision=raw["profile_revision"],
        profile_sha256=raw["profile_sha256"],
        entry_policy=raw["entry_policy"],
        conditions=ProfileConditions(**{**c, "settlement": SettlementMode(c["settlement"])}),
        selector=ProfileSelector(
            **{**s, "numbers": tuple(s["numbers"]) if s["numbers"] is not None else None}
        ),
        staking=ProfileStaking(**t),
    )
