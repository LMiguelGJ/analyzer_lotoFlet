"""Private schema-2 Q80 result wire and trusted deterministic replay.

No persistent round state is needed: the complete authenticated chronological
rows, v2 request and profile deterministically recreate every round transition.
A result cannot prove dataset provenance: the caller MUST authenticate *all*
source rows (including pre-start rows) against request.dataset_sha256 using the
importer's digest convention, and verify job/request ownership before admission.
"""

import json
from dataclasses import dataclass

from laboratorio.domain.contracts import GameProfile
from laboratorio.domain.profile_capabilities import ENTRY_POLICY
from laboratorio.domain.profile_request import (
    _bad_constant,
    _canonical,
    _unique_pairs,
    profile_sha256,
)
from laboratorio.domain.profile_request_v2 import ProfileCyclingRequest
from laboratorio.domain.profile_result import (
    _RESULT_KEYS,
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

RESULT_VERSION = 2


@dataclass(frozen=True, slots=True)
class ProfileCyclingResult:
    """Explicit v2 envelope around a validated v1-shaped session calculation."""

    kind: str
    schema_version: int
    session: ProfileSessionResult

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind != "profile":
            raise ValueError("unsupported result kind")
        if type(self.schema_version) is not int or self.schema_version != RESULT_VERSION:
            raise ValueError("unsupported cycling result version")
        if type(self.session) is not ProfileSessionResult:
            raise ValueError("session must be a ProfileSessionResult")


def serialize_profile_cycling_result(result: ProfileCyclingResult) -> str:
    if type(result) is not ProfileCyclingResult:
        raise ValueError("result must be a ProfileCyclingResult")
    result.__post_init__()
    # v1 structural validation applies to the internal session only, not to
    # the externally dispatched v2 envelope. No v1 loader accepts these bytes.
    raw = json.loads(serialize_profile_result(result.session))
    raw["schema_version"] = RESULT_VERSION
    return _canonical(raw)


def load_profile_cycling_result(payload: str) -> ProfileCyclingResult:
    if type(payload) is not str:
        raise ValueError("result payload must be a JSON string")
    _utf8(payload)
    try:
        raw = json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid cycling result JSON") from exc
    _utf8(raw)
    raw = _keys(raw, _RESULT_KEYS, "result")
    if type(raw["kind"]) is not str or raw["kind"] != "profile":
        raise ValueError("unsupported result kind")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != RESULT_VERSION:
        raise ValueError("unsupported cycling result version")
    # Reuse exact v1 *field* validation after explicit version dispatch. The
    # session's schema version stays 1; only the outer wire has version 2.
    session = load_profile_result(_canonical({**raw, "schema_version": 1}))
    return ProfileCyclingResult("profile", RESULT_VERSION, session)


def validate_profile_cycling_result(
    result: ProfileCyclingResult,
    request: ProfileCyclingRequest,
    profile: GameProfile,
    trusted_draws: list[ProfileDraw] | tuple[ProfileDraw, ...],
    *,
    require_completed: bool = True,
) -> ProfileCyclingResult:
    """Admit only exact replay from caller-authenticated complete source rows."""
    if type(require_completed) is not bool:
        raise ValueError("require_completed must be a bool")
    result = load_profile_cycling_result(serialize_profile_cycling_result(result))
    if type(request) is not ProfileCyclingRequest:
        raise ValueError("request must be a ProfileCyclingRequest")
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
        raise ValueError("profile result/request/profile binding mismatch")
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
        profile,
        request.conditions,
        request.selector,
        request.staking,
        trusted_draws,
        cancel_after_elapsed_draws=(
            result.session.elapsed_draws
            if result.session.outcome is ProfileOutcome.CANCELLED
            else None
        ),
    )
    if result.session != expected:
        raise ValueError("cycling result differs from trusted deterministic replay")
    return result
