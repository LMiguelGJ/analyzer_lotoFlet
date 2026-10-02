"""Closed profile-engine capability catalog; pending entries never admit requests.

Schema versions govern admission separately from selector algorithm versions.
Settlement wire values remain ``all`` and ``best``; their v1 meaning is bound
to the profile's own best_rule. This is not a plugin loader or a claim that legacy
ranking exports work with arbitrary profiles.
"""

from dataclasses import dataclass
from typing import Literal

CapabilityKind = Literal["selector", "staking", "entry", "settlement"]
CapabilityStatus = Literal["supported", "pending"]
ENTRY_POLICY = "all_rows/v1"  # Kept as the v1 result/request compatibility identifier.


@dataclass(frozen=True, slots=True)
class ProfileCapability:
    kind: CapabilityKind
    identifier: str  # Exact request value, not a family to resolve by prefix.
    version: str  # Capability/algorithm version; never used as a schema-version suffix.
    status: CapabilityStatus
    schema_version: int | None  # Pending entries have no admitted request schema.
    parameters: tuple[str, ...] = ()
    compatibility: tuple[str, ...] = ()


PROFILE_CAPABILITIES = (
    ProfileCapability(
        "selector",
        "static-numbers/v1",
        "v1",
        "supported",
        1,
        ("coverage", "numbers"),
        ("distinct-in-profile-universe", "profile-coverage"),
    ),
    ProfileCapability(
        "selector",
        "seeded-random/hash-sha256-v1",
        "hash-sha256-v1",
        "supported",
        1,
        ("coverage", "seed", "algorithm_version"),
        ("profile-universe", "profile-coverage", "explicit-hash-sha256-v1"),
    ),
    ProfileCapability(
        "staking",
        "flat-per-number/v1",
        "v1",
        "supported",
        1,
        ("per_number_stake",),
        ("profile-stake-bounds", "profile-increment", "profile-exposure", "initial-capital"),
    ),
    ProfileCapability(
        "staking",
        "q80-first-prize-cycling/v1",
        "v1",
        "supported",
        2,
        (),
        ("q80-80/8/4/2/1", "full-ten-round-ladder", "initial-capital", "first-hit-reset"),
    ),
    ProfileCapability(
        "staking",
        "profile-audaz/v1",
        "v1",
        "supported",
        3,
        (),
        (
            "selected-coverage-below-first-multiplier",
            "profile-stake-bounds",
            "profile-increment",
            "profile-exposure",
            "initial-capital",
        ),
    ),
    ProfileCapability(
        "staking",
        "profile-recovery-ladder/v1",
        "v1",
        "supported",
        4,
        ("target_margin", "rounds", "end_mode"),
        (
            "profile-rational-first-multiplier",
            "profile-stake-bounds",
            "profile-exposure",
            "initial-capital",
        ),
    ),
    ProfileCapability("entry", ENTRY_POLICY, "v1", "supported", 1, (), ("prepared-draw-enter",)),
    ProfileCapability("settlement", "all", "v1", "supported", 1, (), ("profile-multipliers",)),
    ProfileCapability("settlement", "best", "v1", "supported", 1, (), ("profile-best-rule",)),
    *(
        ProfileCapability("selector", name, "unassigned", "pending", None)
        for name in (
            "freq_hist",
            "freq_recent",
            "decay",
            "cold",
            "notebook",
            "mix",
            "transition",
            "carry",
            "doubles",
            "category",
            "time",
            "ensemble",
            "select_interpretable",
            "blend",
            "parity",
        )
    ),
    *(
        ProfileCapability("staking", name, "unassigned", "pending", None)
        for name in (
            "ladder",
            "bold",
            "timid",
        )
    ),
    ProfileCapability("entry", "conditional-entry", "unassigned", "pending", None),
    *(
        ProfileCapability("staking", name, "unassigned", "pending", None)
        for name in (
            "fractional-flat",
            "kelly-binary",
            "fractional-kelly",
        )
    ),
    ProfileCapability("settlement", "custom-settlement", "unassigned", "pending", None),
)


def _validate_registry(entries: tuple[ProfileCapability, ...]) -> None:
    """Reject ambiguous identifiers or accidentally executable pending families."""
    seen: set[tuple[str, str]] = set()
    for item in entries:
        key = (item.kind, item.identifier)
        if key in seen or (item.status == "supported") != (type(item.schema_version) is int):
            raise ValueError(f"invalid profile capability: {key!r}")
        seen.add(key)


_validate_registry(PROFILE_CAPABILITIES)


def supported(kind: CapabilityKind) -> tuple[str, ...]:
    """Ordered, closed API projection for a single profile strategy axis."""
    return tuple(
        item.identifier
        for item in PROFILE_CAPABILITIES
        if item.kind == kind and item.status == "supported"
    )


def require_supported(
    kind: CapabilityKind, identifier: object, schema_version: object
) -> ProfileCapability:
    """Exact kind/ID/schema admission, independent of the algorithm version."""
    if type(identifier) is str and type(schema_version) is int:
        for item in PROFILE_CAPABILITIES:
            if (
                item.kind == kind
                and item.identifier == identifier
                and item.status == "supported"
                and item.schema_version == schema_version
            ):
                return item
    raise ValueError(f"unsupported {kind} capability: {identifier!r}")


def audaz_compatible_coverage(profile) -> int:
    """Highest selectable integer k with exact first multiplier strictly greater than k."""
    first = profile.multipliers[0]
    mathematical_limit = (first.numerator - 1) // first.denominator
    return max(0, min(profile.max_coverage, profile.universe_size, mathematical_limit))


def legacy_capabilities() -> tuple[tuple[str, str], ...]:
    """Preserve the historical CAPABILITIES spelling/order for existing consumers."""
    return tuple(
        (
            f"settlement-{item.identifier}"
            if item.kind == "settlement"
            else "entry-explicit/v1"
            if item.kind == "entry" and item.status == "supported"
            else item.identifier,
            item.status,
        )
        for item in PROFILE_CAPABILITIES
        if item.identifier
        not in (
            "q80-first-prize-cycling/v1",
            "profile-audaz/v1",
            "profile-recovery-ladder/v1",
        )
    )
