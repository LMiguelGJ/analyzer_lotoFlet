"""Closed immutable composition snapshots used by the private v5 profile path."""

from dataclasses import dataclass

from pydantic import TypeAdapter

from laboratorio.domain.contracts import (
    MAX_MONEY,
    MAX_PROFILE_UNIVERSE,
    SYSTEMS,
    Name,
    normalize_strategy_name,
)

DEFINITION_VERSION = 1
_NAME = TypeAdapter(Name)
SELECTORS = frozenset(
    {
        "static-numbers/v1",
        "seeded-random/hash-sha256-v1",
        "archived-cold/v1",
        "archived-transition/v1",
        "archived-topk/v1",
        "archived-parity50/v1",
    }
)
STAKING = frozenset(
    {
        "flat-per-number/v1",
        "q80-first-prize-cycling/v1",
        "profile-audaz/v1",
        "profile-recovery-ladder/v1",
        "q80-reference-audaz/v1",
    }
)


def _exact_int(value: object, name: str, low: int, high: int) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    """A concrete, non-executable-DSL snapshot of one supported selector/stake pair."""

    definition_version: int
    name: str
    selector: str
    coverage: int
    staking: str
    selector_parameters: tuple[tuple[str, object], ...] = ()
    staking_parameters: tuple[tuple[str, object], ...] = ()
    closing_defaults: tuple[tuple[str, int | str | None], ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.definition_version) is not int
            or self.definition_version != DEFINITION_VERSION
        ):
            raise ValueError("unsupported strategy definition version")
        if type(self.name) is not str:
            raise ValueError("strategy name must be a string")
        object.__setattr__(self, "name", _NAME.validate_python(self.name))
        if type(self.selector) is not str or self.selector not in SELECTORS:
            raise ValueError("unsupported selector definition")
        _exact_int(self.coverage, "coverage", 1, MAX_PROFILE_UNIVERSE)
        if self.selector.startswith("archived-") and self.coverage > 100:
            raise ValueError("archived selector coverage must be 1 to 100")
        if type(self.staking) is not str or self.staking not in STAKING:
            raise ValueError("unsupported staking definition")
        parameter_sets = (
            ("selector", self.selector_parameters),
            ("staking", self.staking_parameters),
            ("closing", self.closing_defaults),
        )
        for label, pairs in parameter_sets:
            if type(pairs) is not tuple or any(
                type(pair) is not tuple or len(pair) != 2 for pair in pairs
            ):
                raise ValueError(f"{label} parameters must be immutable key/value tuples")
            keys = [pair[0] for pair in pairs]
            if (
                any(type(key) is not str for key in keys)
                or keys != sorted(keys)
                or len(keys) != len(set(keys))
            ):
                raise ValueError(f"{label} parameter keys must be unique and sorted")
        selector = dict(self.selector_parameters)
        stake = dict(self.staking_parameters)
        _only(
            selector,
            {
                "static-numbers/v1": {"numbers"},
                "seeded-random/hash-sha256-v1": {"seed"},
                "archived-cold/v1": {"system"},
                "archived-transition/v1": {"system"},
                "archived-topk/v1": {"system"},
                "archived-parity50/v1": set(),
            }[self.selector],
            "selector",
        )
        if self.selector == "static-numbers/v1":
            numbers = selector.get("numbers")
            if (
                type(numbers) is not tuple
                or len(numbers) != self.coverage
                or any(type(n) is not int or n < 0 for n in numbers)
                or len(set(numbers)) != len(numbers)
            ):
                raise ValueError("static selector requires distinct coverage-sized numbers")
        elif self.selector == "seeded-random/hash-sha256-v1":
            _exact_int(selector.get("seed"), "seed", 0, 2**53 - 1)
        elif self.selector in ("archived-cold/v1", "archived-transition/v1"):
            kind = self.selector.removeprefix("archived-").removesuffix("/v1")
            if selector.get("system", kind) != kind:
                raise ValueError("archived selector system must match its kind")
        elif self.selector == "archived-topk/v1":
            if selector.get("system") not in SYSTEMS:
                raise ValueError("topk selector requires a registered archived system")
        if self.selector == "archived-parity50/v1" and self.coverage != 50:
            raise ValueError("parity selector requires coverage 50")
        allowed_stake_keys = {
            "flat-per-number/v1": {"per_number_stake"},
            "q80-first-prize-cycling/v1": set(),
            "profile-audaz/v1": set(),
            "q80-reference-audaz/v1": set(),
            "profile-recovery-ladder/v1": {"target_margin", "rounds", "end_mode"},
        }[self.staking]
        _only(stake, allowed_stake_keys, "staking")
        if self.staking == "flat-per-number/v1":
            _exact_int(stake.get("per_number_stake"), "per_number_stake", 1, MAX_MONEY)
        if self.staking == "profile-recovery-ladder/v1":
            _exact_int(stake.get("target_margin"), "target_margin", 1, MAX_MONEY)
            _exact_int(stake.get("rounds"), "rounds", 1, 10_000)
            if stake.get("end_mode") not in ("cycle", "stop"):
                raise ValueError("end_mode must be cycle or stop")
        if self.staking == "q80-reference-audaz/v1" and self.coverage != 1:
            raise ValueError("reference audaz requires coverage one")
        if self.staking == "q80-first-prize-cycling/v1" and not 1 <= self.coverage <= 79:
            raise ValueError("Q80 cycling coverage must be 1 to 79")
        _only(
            dict(self.closing_defaults),
            {
                "max_elapsed_draws",
                "max_bet_draws",
                "end_minute",
                "duration_minutes",
                "settlement",
            },
            "closing",
        )
        for key, value in self.closing_defaults:
            if key == "settlement" and value not in ("all", "best"):
                raise ValueError("settlement closing default must be all or best")
            if value is not None and key in (
                "max_elapsed_draws",
                "max_bet_draws",
                "duration_minutes",
            ):
                _exact_int(value, key, 1, MAX_MONEY)
            if key == "end_minute" and value is not None:
                _exact_int(value, key, 1, 10**9)

    @classmethod
    def reference_parity_50(cls) -> "StrategyDefinition":
        return cls(
            1,
            "paridad_50_plana",
            "archived-parity50/v1",
            50,
            "flat-per-number/v1",
            (),
            (("per_number_stake", 1),),
            (("settlement", "all"),),
        )

    @classmethod
    def reference_transition_audaz(cls) -> "StrategyDefinition":
        return cls(
            1,
            "transicion_1_audaz",
            "archived-transition/v1",
            1,
            "q80-reference-audaz/v1",
            (("system", "transition"),),
            (),
            (("settlement", "all"),),
        )

    @classmethod
    def reference_cold_25(cls) -> "StrategyDefinition":
        return cls(
            1,
            "frios_25_escalera",
            "archived-cold/v1",
            25,
            "q80-first-prize-cycling/v1",
            (("system", "cold"),),
            (),
            (("settlement", "all"),),
        )

    @classmethod
    def static_numbers(
        cls, name: str, numbers: tuple[int, ...], *, stake: int = 1
    ) -> "StrategyDefinition":
        return cls(
            1,
            name,
            "static-numbers/v1",
            len(numbers),
            "flat-per-number/v1",
            (("numbers", tuple(numbers)),),
            (("per_number_stake", stake),),
        )


def normalize_definition_name(value: str) -> str:
    return normalize_strategy_name(value)


def _only(value: dict, allowed: set[str], field: str) -> None:
    if set(value) - allowed:
        raise ValueError(f"unknown {field} parameters")
