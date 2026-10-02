"""Explicit schema-3 audaz result wire and deterministic trusted replay."""

import json
from dataclasses import dataclass

from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_capabilities import ENTRY_POLICY
from laboratorio.domain.profile_request import _canonical, _unique_pairs, profile_sha256
from laboratorio.domain.profile_request_v3 import ProfileAudazRequest
from laboratorio.domain.profile_result import (
    _RESULT_KEYS,
    _bad_constant,
    _keys,
    _utf8,
    load_profile_result,
    serialize_profile_result,
)
from laboratorio.domain.profile_session import (
    MAX_SESSION_ROWS,
    ProfileDraw,
    ProfileOutcome,
    ProfileSessionResult,
    run_profile_session,
)

RESULT_VERSION = 3


@dataclass(frozen=True, slots=True)
class ProfileAudazResult:
    kind: str
    schema_version: int
    session: ProfileSessionResult

    def __post_init__(self):
        if type(self.kind) is not str or self.kind != "profile":
            raise ValueError("unsupported result kind")
        if type(self.schema_version) is not int or self.schema_version != RESULT_VERSION:
            raise ValueError("unsupported audaz result version")
        if type(self.session) is not ProfileSessionResult:
            raise ValueError("session must be a ProfileSessionResult")


def serialize_profile_audaz_result(result: ProfileAudazResult) -> str:
    if type(result) is not ProfileAudazResult:
        raise ValueError("result must be a ProfileAudazResult")
    result.__post_init__()
    try:
        raw = json.loads(serialize_profile_result(result.session))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid typed audaz result") from exc
    raw["schema_version"] = RESULT_VERSION
    return _canonical(raw)


def load_profile_audaz_result(payload: str) -> ProfileAudazResult:
    if type(payload) is not str:
        raise ValueError("result payload must be a JSON string")
    _utf8(payload)
    try:
        raw = json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid audaz result JSON") from exc
    _utf8(raw)
    raw = _keys(raw, _RESULT_KEYS, "result")
    if type(raw["kind"]) is not str or raw["kind"] != "profile":
        raise ValueError("unsupported result kind")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != RESULT_VERSION:
        raise ValueError("unsupported audaz result version")
    session = load_profile_result(_canonical({**raw, "schema_version": 1}))
    return ProfileAudazResult("profile", RESULT_VERSION, session)


def validate_profile_audaz_result(
    result: ProfileAudazResult,
    request: ProfileAudazRequest,
    profile: GameProfile,
    trusted_draws: list[ProfileDraw] | tuple[ProfileDraw, ...],
    *,
    require_completed: bool = True,
) -> ProfileAudazResult:
    if type(require_completed) is not bool:
        raise ValueError("require_completed must be a bool")
    result = load_profile_audaz_result(serialize_profile_audaz_result(result))
    if type(request) is not ProfileAudazRequest:
        raise ValueError("request must be a ProfileAudazRequest")
    request.__post_init__()
    if type(profile) is not GameProfile:
        raise ValueError("profile must be a GameProfile")
    if (
        request.profile_id != profile.profile_id
        or request.profile_revision != profile.revision
        or request.profile_sha256 != profile_sha256(profile)
        or result.session.profile_id != request.profile_id
        or result.session.profile_revision != request.profile_revision
        or request.entry_policy != ENTRY_POLICY
    ):
        raise ValueError("audaz result/request/profile binding mismatch")
    if type(trusted_draws) not in (list, tuple) or len(trusted_draws) > MAX_SESSION_ROWS:
        raise ValueError("trusted draws must be a bounded materialized sequence")
    if any(
        type(row) is not ProfileDraw or type(row.enter) is not bool or not row.enter
        for row in trusted_draws
    ):
        raise ValueError("all_rows/v1 requires every trusted source row to enter")
    if require_completed and result.session.outcome is ProfileOutcome.CANCELLED:
        raise ValueError("cancelled result cannot complete a job")
    expected = run_profile_session(
        profile, request.conditions, request.selector, request.staking, trusted_draws
    )
    if result.session != expected:
        raise ValueError("audaz result differs from trusted deterministic replay")
    return result
