"""Strict schema-4 generic recovery-ladder request wire."""

import json
from dataclasses import dataclass

from laboratorio.domain.contracts import MAX_PROFILE_REVISION, SettlementMode
from laboratorio.domain.profile_request import (
    _NAME,
    _PROFILE_ID,
    _bad_constant,
    _canonical,
    _digest,
    _keys,
    _unique_pairs,
)
from laboratorio.domain.profile_result import _utf8
from laboratorio.domain.profile_session import ProfileConditions, ProfileSelector
from laboratorio.domain.profile_staking import ProfileRecoveryLadderStaking

REQUEST_VERSION = 4


@dataclass(frozen=True, slots=True)
class ProfileRecoveryRequest:
    kind: str
    schema_version: int
    name: str
    dataset_sha256: str
    profile_id: str
    profile_revision: int
    profile_sha256: str
    conditions: ProfileConditions
    selector: ProfileSelector
    staking: ProfileRecoveryLadderStaking
    entry_policy: str

    def __post_init__(self):
        if type(self.kind) is not str or self.kind != "profile":
            raise ValueError("unsupported request kind")
        if type(self.schema_version) is not int or self.schema_version != REQUEST_VERSION:
            raise ValueError("unsupported recovery request version")
        if type(self.name) is not str:
            raise ValueError("name must be a string")
        _utf8(self.name)
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
        if type(self.entry_policy) is not str or self.entry_policy != "all_rows/v1":
            raise ValueError("unsupported entry policy")
        for field, model in (
            ("conditions", ProfileConditions),
            ("selector", ProfileSelector),
            ("staking", ProfileRecoveryLadderStaking),
        ):
            value = getattr(self, field)
            if type(value) is not model:
                raise TypeError(f"{field} must be a {model.__name__}")
            value.__post_init__()


def serialize_profile_recovery_request(request: ProfileRecoveryRequest) -> str:
    if type(request) is not ProfileRecoveryRequest:
        raise TypeError("request must be a ProfileRecoveryRequest")
    request.__post_init__()
    c, s, t = request.conditions, request.selector, request.staking
    return _canonical(
        {
            "kind": request.kind,
            "schema_version": 4,
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
                "schema_version": 1,
                "target_margin": t.target_margin,
                "rounds": t.rounds,
                "end_mode": t.end_mode,
            },
        }
    )


def load_profile_recovery_request(payload: str) -> ProfileRecoveryRequest:
    if type(payload) is not str:
        raise TypeError("payload must be a JSON string")
    _utf8(payload)
    try:
        raw = json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid recovery request JSON") from exc
    _utf8(raw)
    raw = _keys(raw, set(ProfileRecoveryRequest.__dataclass_fields__), "request")
    if (
        type(raw["kind"]) is not str
        or raw["kind"] != "profile"
        or type(raw["schema_version"]) is not int
        or raw["schema_version"] != 4
    ):
        raise ValueError("unsupported recovery request version")
    c = _keys(raw["conditions"], set(ProfileConditions.__dataclass_fields__), "conditions")
    s = _keys(raw["selector"], set(ProfileSelector.__dataclass_fields__), "selector")
    t = _keys(
        raw["staking"],
        {"schema_version", "target_margin", "rounds", "end_mode"},
        "staking",
    )
    if type(t["schema_version"]) is not int or t["schema_version"] != 1:
        raise ValueError("unsupported recovery staking version")
    if type(c["settlement"]) is not str or c["settlement"] not in ("all", "best"):
        raise ValueError("settlement must explicitly be all or best")
    if s["numbers"] is not None and type(s["numbers"]) is not list:
        raise ValueError("numbers must be an explicit JSON array or null")
    return ProfileRecoveryRequest(
        raw["kind"],
        raw["schema_version"],
        raw["name"],
        raw["dataset_sha256"],
        raw["profile_id"],
        raw["profile_revision"],
        raw["profile_sha256"],
        ProfileConditions(**{**c, "settlement": SettlementMode(c["settlement"])}),
        ProfileSelector(
            **{**s, "numbers": tuple(s["numbers"]) if s["numbers"] is not None else None}
        ),
        ProfileRecoveryLadderStaking(t["target_margin"], t["rounds"], t["end_mode"]),
        raw["entry_policy"],
    )
