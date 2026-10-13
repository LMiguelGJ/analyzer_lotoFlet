"""Strict, inert v2 contracts for configurable quiniela profiles."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from fractions import Fraction
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from laboratorio.domain.contracts import (
    MAX_MONEY,
    MAX_PROFILE_POSITIONS,
    MAX_PROFILE_SCALE,
    MAX_PROFILE_UNIVERSE,
    PayoutMultiplier,
)

MAX_SAFE_INTEGER = 9_007_199_254_740_991
_RULE_FIELDS = frozenset(
    {
        "schema_version",
        "universe",
        "display_width",
        "positions",
        "played_positions",
        "order_matters",
        "allows_repeats",
        "multipliers",
        "payout_mode",
        "currency",
        "scale",
        "minimum_stake",
        "stake_increment",
        "maximum_stake",
        "max_coverage",
        "max_exposure",
    }
)
_PROFILE_FIELDS = frozenset({"schema_version", "id", "name", "rules"})


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class QuinielaRules(_FrozenModel):
    """Immutable rules data; money values are integer units at ``scale``."""

    schema_version: int = Field(strict=True, ge=2, le=2)
    universe: tuple[int, ...] = Field(min_length=2, max_length=MAX_PROFILE_UNIVERSE)
    display_width: int = Field(strict=True, ge=1, le=MAX_PROFILE_POSITIONS)
    positions: int = Field(strict=True, ge=1, le=MAX_PROFILE_POSITIONS)
    played_positions: tuple[int, ...] = Field(min_length=1, max_length=MAX_PROFILE_POSITIONS)
    order_matters: bool = Field(strict=True)
    allows_repeats: bool = Field(strict=True)
    multipliers: tuple[PayoutMultiplier, ...] = Field(
        min_length=1, max_length=MAX_PROFILE_POSITIONS
    )
    payout_mode: Literal["all", "best"]
    currency: str = Field(strict=True, pattern=r"^[A-Z]{3}$")
    scale: int = Field(strict=True, ge=0, le=MAX_PROFILE_SCALE)
    minimum_stake: int = Field(strict=True, ge=1, le=MAX_MONEY)
    stake_increment: int = Field(strict=True, ge=1, le=MAX_MONEY)
    maximum_stake: int = Field(strict=True, ge=1, le=MAX_MONEY)
    max_coverage: int = Field(strict=True, ge=1, le=MAX_PROFILE_UNIVERSE)
    max_exposure: int = Field(strict=True, ge=1, le=MAX_MONEY)

    @model_validator(mode="before")
    @classmethod
    def _strict_integer_arrays(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        for key in ("universe", "played_positions"):
            items = value.get(key)
            if isinstance(items, (tuple, list)) and any(type(item) is not int for item in items):
                raise ValueError(f"{key} must contain strict integers")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if any(number < 0 or number > MAX_SAFE_INTEGER for number in self.universe):
            raise ValueError("universe values must be nonnegative JavaScript-safe integers")
        if tuple(sorted(set(self.universe))) != self.universe:
            raise ValueError("universe must be distinct and in canonical ascending order")
        if self.display_width < len(str(self.universe[-1])):
            raise ValueError("display_width cannot represent every universe number")
        if any(position < 0 or position >= self.positions for position in self.played_positions):
            raise ValueError("played_positions must be zero-based positions within the game")
        if tuple(sorted(set(self.played_positions))) != self.played_positions:
            raise ValueError("played_positions must be distinct and in canonical ascending order")
        if not self.allows_repeats and self.positions > len(self.universe):
            raise ValueError("positions exceed universe when repeats are not allowed")
        if len(self.multipliers) != self.positions:
            raise ValueError("one exact multiplier is required per result position")
        if self.max_coverage > len(self.universe):
            raise ValueError("max_coverage exceeds universe")
        if self.minimum_stake > self.maximum_stake:
            raise ValueError("minimum_stake exceeds maximum_stake")
        if self.minimum_stake % self.stake_increment or self.maximum_stake % self.stake_increment:
            raise ValueError("stake bounds must be multiples of stake_increment")
        if self.maximum_stake > self.max_exposure:
            raise ValueError("maximum_stake exceeds max_exposure")
        if self.max_coverage * self.minimum_stake > self.max_exposure:
            raise ValueError("max_coverage cannot be funded at minimum_stake within max_exposure")

        for multiplier in self.multipliers:
            if (self.stake_increment * multiplier.numerator) % multiplier.denominator:
                raise ValueError("payout is not exactly representable at stake_increment")

        active = tuple(self.multipliers[index] for index in self.played_positions)
        if not self.order_matters and any(
            Fraction(item.numerator, item.denominator)
            != Fraction(active[0].numerator, active[0].denominator)
            for item in active[1:]
        ):
            raise ValueError("unordered played positions require equal rational payouts")

        multipliers = (
            active
            if self.payout_mode == "all"
            else (
                max(
                    active,
                    key=lambda item: Fraction(item.numerator, item.denominator),
                ),
            )
        )
        worst_case = Fraction(self.max_exposure) * sum(
            (Fraction(item.numerator, item.denominator) for item in multipliers),
            Fraction(0),
        )
        if worst_case > MAX_MONEY:
            raise ValueError("worst-case payout exceeds the safe money ceiling")
        return self

    @classmethod
    def from_mapping(cls, mapping: object) -> QuinielaRules:
        if not isinstance(mapping, Mapping) or frozenset(mapping) != _RULE_FIELDS:
            raise ValueError("rules mapping must contain exactly the v2 fields")
        for key in ("universe", "played_positions", "multipliers"):
            if not isinstance(mapping[key], list):
                raise ValueError(f"{key} must be a JSON array")
        copied = dict(mapping)
        copied["multipliers"] = [
            PayoutMultiplier.model_validate(item) for item in mapping["multipliers"]
        ]
        return cls.model_validate(copied)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "universe": list(self.universe),
            "display_width": self.display_width,
            "positions": self.positions,
            "played_positions": list(self.played_positions),
            "order_matters": self.order_matters,
            "allows_repeats": self.allows_repeats,
            "multipliers": [item.model_dump(mode="python") for item in self.multipliers],
            "payout_mode": self.payout_mode,
            "currency": self.currency,
            "scale": self.scale,
            "minimum_stake": self.minimum_stake,
            "stake_increment": self.stake_increment,
            "maximum_stake": self.maximum_stake,
            "max_coverage": self.max_coverage,
            "max_exposure": self.max_exposure,
        }


class QuinielaProfile(_FrozenModel):
    """Immutable named v2 profile with canonical lowercase UUID identity."""

    schema_version: int = Field(strict=True, ge=2, le=2)
    id: str = Field(strict=True)
    name: str = Field(strict=True)
    rules: QuinielaRules

    @model_validator(mode="after")
    def _canonical_identity_and_name(self) -> Self:
        try:
            canonical_id = str(uuid.UUID(self.id))
        except (ValueError, AttributeError) as error:
            raise ValueError("id must be a canonical lowercase UUID") from error
        if self.id != canonical_id:
            raise ValueError("id must be a canonical lowercase UUID")
        if not self.name or self.name != self.name.strip():
            raise ValueError("name must be nonempty and already trimmed")
        if len(self.name.encode("utf-8")) > 120:
            raise ValueError("name must be at most 120 UTF-8 bytes")
        return self

    @classmethod
    def from_mapping(cls, mapping: object) -> QuinielaProfile:
        if not isinstance(mapping, Mapping) or frozenset(mapping) != _PROFILE_FIELDS:
            raise ValueError("profile mapping must contain exactly the v2 fields")
        copied = dict(mapping)
        copied["rules"] = QuinielaRules.from_mapping(mapping["rules"])
        return cls.model_validate(copied)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "rules": self.rules.to_mapping(),
        }


def create_profile(name: str, rules: QuinielaRules | Mapping[str, object]) -> QuinielaProfile:
    """Create a fresh profile identity after normalizing its display name."""
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    if isinstance(rules, Mapping):
        rules = QuinielaRules.from_mapping(rules)
    if not isinstance(rules, QuinielaRules):
        raise TypeError("rules must be QuinielaRules or a rules mapping")
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name.encode("utf-8")) > 120:
        raise ValueError("name must be nonempty and at most 120 UTF-8 bytes")
    return QuinielaProfile(
        schema_version=2,
        id=str(uuid.uuid4()),
        name=normalized_name,
        rules=rules,
    )
