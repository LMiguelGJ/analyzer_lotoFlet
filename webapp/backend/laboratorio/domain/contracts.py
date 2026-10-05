"""Experiment contracts: game, conditions, strategies, statuses and outcomes.

Everything here is data and validation. Rules that need the frozen history
(whether a start draw exists) or staking math (initial affordability) live in
the engine adapter and ``domain.session`` respectively.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError
from pydantic_core import ValidationError as CoreValidationError


@dataclass(frozen=True)
class Game:
    name: str
    numbers: int
    positions: int
    prizes: tuple[int, ...]
    allows_repeats: bool
    minimum_stake: int = 1


def make_game(
    name: str,
    numbers: int,
    positions: int,
    prizes: Sequence[int],
    allows_repeats: bool,
    minimum_stake: int = 1,
) -> Game:
    """Build a validated Game; raises ValueError on an inconsistent rule set."""
    prizes = tuple(prizes)
    if numbers < 2:
        raise ValueError("numbers must be at least 2")
    if numbers > MAX_GAME_NUMBERS:
        raise ValueError(f"numbers must be at most {MAX_GAME_NUMBERS}")
    if positions < 1:
        raise ValueError("positions must be at least 1")
    if positions > MAX_GAME_POSITIONS:
        raise ValueError(f"positions must be at most {MAX_GAME_POSITIONS}")
    if not allows_repeats and positions > numbers:
        raise ValueError("positions exceed numbers when repeats are not allowed")
    if len(prizes) != positions:
        raise ValueError("exactly one prize is required per position")
    if any(prize < 1 for prize in prizes):
        raise ValueError("every prize must be at least 1")
    if minimum_stake < 1:
        raise ValueError("minimum_stake must be at least 1")
    return Game(name, numbers, positions, prizes, allows_repeats, minimum_stake)


GAME = Game("Quiniela 80", 100, 5, (80, 8, 4, 2, 1), True)


def configure_game(game: Game) -> None:
    """Replace the active game rules (the value held by ``GAME``).

    Modules that did ``from ... import GAME`` keep a reference to the same object, so
    the rules are swapped in place (the frozen dataclass is rebound field by field)
    instead of rebinding the module attribute, which those importers would never see.
    """
    for field in fields(Game):
        object.__setattr__(GAME, field.name, getattr(game, field.name))


# Admission ceilings for inert profile documents, NOT execution budgets. The old
# game has 100 numbers, 5 positions and up to 50 selected numbers. Ten times its
# universe and roughly three times its positions keep validation/allocation bounded;
# execution still needs draw-count, work, memory and data-compatibility admission.
MAX_PROFILE_UNIVERSE = 1_000
MAX_PROFILE_POSITIONS = 16

# Ceilings for the ACTIVE game rules (the editable ones). They mirror the profile
# admission ceilings on purpose: a configured game must stay bounded so the
# catalog payload and the rules editor never explode (e.g. 5000 prize inputs).
MAX_GAME_NUMBERS = 1_000
MAX_GAME_POSITIONS = 16
MAX_PROFILE_SCALE = 6  # integer micro-units are the finest accepted money unit
MAX_PROFILE_REVISION = 1_000_000
LEGACY_PROFILE_ID = "legacy-quiniela-80"

# The 13 archived pos1 ranking systems, in the order of the frozen export.
SYSTEMS: dict[str, str] = {
    "freq_hist": "Frecuencia histórica",
    "freq_recent": "Frecuencia reciente",
    "decay": "Decaimiento",
    "cold": "Fríos",
    "notebook": "Cuaderno",
    "mix": "Mezclas",
    "transition": "Transición",
    "carry": "Arrastre",
    "doubles": "Dobles",
    "category": "Categoría",
    "time": "Horario",
    "ensemble": "Ensemble",
    "select_interpretable": "Selector interpretable",
}
COVERAGES = (1, 5, 10, 20, 25, 30, 40, 50)
PARITY_COVERAGE = 50
MAX_STRATEGIES = 5
MAX_MONEY = 1_000_000_000_000
# 2**53 - 1 (Number.MAX_SAFE_INTEGER): the largest integer JavaScript's `JSON.parse`/
# `response.json()` round-trips exactly. A 64-bit seed was silently rounded on the way
# back from the API; see [F16] in especificaciones-laboratorio-web.md.
MAX_SEED = 2**53 - 1
DRAW_FORMAT = "%Y-%m-%d %H:%M"
_DRAW_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")

# Unicode category Zs (space separators) plus ASCII control whitespace, spelled out
# explicitly because Python's str.strip() and JS's String.prototype.trim() disagree on
# some format characters (e.g. U+FEFF): relying on each language's built-in whitespace
# definition would let the two sides drift apart again.
_NAME_TRIM_CHARS = " \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000"
_NAME_TRIM_RE = re.compile(rf"^[{_NAME_TRIM_CHARS}]+|[{_NAME_TRIM_CHARS}]+$")


def _trim_name(value: str) -> str:
    """The same explicit trim used by normalize_strategy_name, applied before storage.

    Replaces Pydantic's built-in ``strip_whitespace=True``, which strips whatever Python's
    str.strip() considers whitespace (including U+0085) while JS's trim() disagrees
    (it strips U+0085 too, but strips U+FEFF where Python doesn't): using each side's
    default definition let the stored name and the duplicate-detection key drift apart.
    """
    return _NAME_TRIM_RE.sub("", value)


Name = Annotated[str, BeforeValidator(_trim_name), StringConstraints(min_length=1, max_length=80)]


def normalize_strategy_name(name: str) -> str:
    """Canonical form used only to detect duplicate strategy names, never to store a name.

    NFKC normalization folds compatibility variants (ligatures, fullwidth letters,
    combining sequences) to their canonical form; the explicit trim charset removes
    leading/trailing spaces without depending on strip()'s built-in definition;
    upper() then lower() folds case including special mappings (e.g. german eszett)
    that str.casefold()/toLocaleLowerCase() fold asymmetrically. Mirrored exactly by
    normalizeStrategyName in webapp/frontend/src/pages/new-experiment/model.ts.
    """
    trimmed = _NAME_TRIM_RE.sub("", unicodedata.normalize("NFKC", name))
    return trimmed.upper().lower()


class SelectorKind(StrEnum):
    SYSTEM = "system"
    BLEND = "blend"
    RANDOM = "random"
    PARITY = "parity"


class StakingStyle(StrEnum):
    FLAT = "flat"
    LADDER = "ladder"
    BOLD = "bold"


class SettlementMode(StrEnum):
    ALL = "all"
    BEST = "best"


class ExperimentStatus(StrEnum):
    PENDING = "pending"  # queued; runs while the server is alive
    HELD = "held"  # was pending at restart; needs an explicit start
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"  # server stopped while running; never resumed
    FAILED = "failed"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"  # was calculating when cancelled; result discarded
    NOT_RUN = "not_run"  # never started because the experiment stopped
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class Outcome(StrEnum):
    GOAL = "goal"
    RUIN = "ruin"
    LIMIT = "limit"
    HISTORY_EXHAUSTED = "history_exhausted"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PayoutMultiplier(_Frozen):
    """Exact non-negative rational total payout per unit staked (no extra refund)."""

    numerator: int = Field(strict=True, ge=0, le=MAX_MONEY)
    denominator: int = Field(strict=True, ge=1, le=MAX_MONEY)


class GameProfile(_Frozen):
    """Inert versioned game contract; it does not change GAME or enable execution.

    Money is integer units of 10**(-scale) currency. A stake is min + n *
    stake_increment for n >= 0. The minimum and maximum are multiples of the
    increment, so every valid stake has an integral exact payout. Per-draw
    max_exposure and max_coverage are declared separately; execution must enforce
    both, plus independent workload admission. JSON emits bounded integers, never
    floats or numeric strings. A first-match best rule is reserved for the frozen
    legacy profile; new profiles select the maximum payout at each repeated number.
    """

    schema_version: int = Field(strict=True, ge=1, le=1)
    profile_id: str = Field(strict=True, pattern=r"^[a-z][a-z0-9-]{0,79}$")
    revision: int = Field(strict=True, ge=1, le=MAX_PROFILE_REVISION)
    universe_size: int = Field(strict=True, ge=1, le=MAX_PROFILE_UNIVERSE)
    positions: int = Field(strict=True, ge=1, le=MAX_PROFILE_POSITIONS)
    allows_repeats: bool = Field(strict=True)
    multipliers: tuple[PayoutMultiplier, ...] = Field(
        min_length=1, max_length=MAX_PROFILE_POSITIONS
    )
    currency: str = Field(strict=True, pattern=r"^[A-Z]{3}$")
    scale: int = Field(strict=True, ge=0, le=MAX_PROFILE_SCALE)
    stake_increment: int = Field(strict=True, ge=1, le=MAX_MONEY)
    minimum_stake: int = Field(strict=True, ge=1, le=MAX_MONEY)
    maximum_stake: int = Field(strict=True, ge=1, le=MAX_MONEY)
    max_coverage: int = Field(strict=True, ge=1, le=MAX_PROFILE_UNIVERSE)
    max_exposure: int = Field(strict=True, ge=1, le=MAX_MONEY)
    best_rule: Literal["maximum-payout/v1", "first-match/v0"]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.allows_repeats and self.positions > self.universe_size:
            raise ValueError("positions exceed universe without replacement")
        if len(self.multipliers) != self.positions:
            raise ValueError("one exact multiplier is required per position")
        if self.max_coverage > self.universe_size:
            raise ValueError("coverage exceeds universe")
        if self.minimum_stake > self.maximum_stake:
            raise ValueError("minimum stake exceeds maximum stake")
        if self.minimum_stake % self.stake_increment or self.maximum_stake % self.stake_increment:
            raise ValueError("stake bounds must be multiples of the increment")
        if self.maximum_stake > self.max_exposure:
            raise ValueError("maximum stake exceeds per-draw exposure")
        if self.max_coverage * self.minimum_stake > self.max_exposure:
            raise ValueError("the declared coverage cannot be funded at minimum stake")
        # Every stake is a multiple of increment. Reject fractional payouts rather
        # than silently rounding in a future engine, even at the smallest stake.
        if any(
            (self.stake_increment * prize.numerator) % prize.denominator
            for prize in self.multipliers
        ):
            raise ValueError("all payouts must be integral in the declared scale")
        # A conservative all-mode ceiling includes repeated draws: any selected
        # stake can match at every position. This also protects future JSON results
        # from integers beyond the existing MAX_MONEY / JS-safe API boundary.
        from fractions import Fraction

        all_mode_bound = self.max_exposure * sum(
            (Fraction(p.numerator, p.denominator) for p in self.multipliers),
            Fraction(0),
        )
        if all_mode_bound > MAX_MONEY:
            raise ValueError("worst-case total payout exceeds the safe money ceiling")
        legacy_terms = (
            self.universe_size == GAME.numbers
            and self.positions == GAME.positions
            and self.allows_repeats == GAME.allows_repeats
            and tuple((p.numerator, p.denominator) for p in self.multipliers)
            == tuple((prize, 1) for prize in GAME.prizes)
            and self.currency == "DOP"
            and self.scale == 0
            and self.stake_increment == 1
            and self.minimum_stake == 1
            and self.max_coverage == max(COVERAGES)
            and self.maximum_stake == 1_000_000_000
            and self.max_exposure == 1_000_000_000
        )
        if self.profile_id == LEGACY_PROFILE_ID:
            if self.revision != 1 or self.best_rule != "first-match/v0" or not legacy_terms:
                raise ValueError("the legacy identity is reserved for its frozen v0 semantics")
        elif self.best_rule != "maximum-payout/v1":
            raise ValueError("first-match best is reserved for the legacy profile")
        return self


def legacy_quiniela_80_profile() -> GameProfile:
    """Explicit migration descriptor, not a replacement for executable GAME.

    Historical best returns the FIRST matching position, even when a later
    position pays more; new profiles take the maximum. Monetary caps here admit
    only new uses of this descriptor; never revalidate or recalculate old results
    against them. Old snapshots remain RD$1 integer units and unchanged.
    """
    return GameProfile(
        schema_version=1,
        profile_id=LEGACY_PROFILE_ID,
        revision=1,
        universe_size=GAME.numbers,
        positions=GAME.positions,
        allows_repeats=GAME.allows_repeats,
        multipliers=tuple(
            PayoutMultiplier(numerator=prize, denominator=1) for prize in GAME.prizes
        ),
        currency="DOP",
        scale=0,
        stake_increment=1,
        minimum_stake=1,
        maximum_stake=1_000_000_000,
        max_coverage=max(COVERAGES),
        max_exposure=1_000_000_000,
        best_rule="first-match/v0",
    )


class BlendComponent(_Frozen):
    system: str
    weight: int = Field(strict=True, ge=1, le=99)

    @model_validator(mode="after")
    def _known_system(self) -> Self:
        if self.system not in SYSTEMS:
            raise ValueError(f"unknown ranking system: {self.system}")
        return self


class Strategy(_Frozen):
    name: Name
    selector: SelectorKind
    system: str | None = None
    components: tuple[BlendComponent, ...] | None = None
    coverage: int = Field(strict=True)
    staking: StakingStyle

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.selector is SelectorKind.SYSTEM:
            if self.system not in SYSTEMS:
                raise ValueError("an individual strategy needs one of the 13 systems")
            if self.components is not None:
                raise ValueError("an individual strategy has no blend components")
        elif self.system is not None:
            raise ValueError("only individual strategies name a single system")

        if self.selector is SelectorKind.BLEND:
            components = self.components or ()
            names = [c.system for c in components]
            if len(components) < 2 or len(set(names)) != len(names):
                raise ValueError("a blend needs at least two distinct systems")
            if sum(c.weight for c in components) != 100:
                raise ValueError("blend weights must add up to 100")
        elif self.components is not None:
            raise ValueError("only blends have components")

        if self.selector is SelectorKind.PARITY:
            if self.coverage != PARITY_COVERAGE:
                raise ValueError("parity always covers 50 numbers")
        elif self.coverage not in COVERAGES:
            raise ValueError(f"coverage must be one of {COVERAGES}")
        return self


class Conditions(_Frozen):
    start_draw: str
    capital: int = Field(strict=True, ge=1, le=MAX_MONEY)
    goal: int = Field(strict=True, ge=2, le=MAX_MONEY)
    settlement: SettlementMode = SettlementMode.ALL
    max_bets: int | None = Field(default=None, strict=True, ge=1, le=10_000_000)
    max_minutes: int | None = Field(default=None, strict=True, ge=1, le=100_000_000)
    seed: int = Field(strict=True, ge=0, le=MAX_SEED)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not _DRAW_RE.fullmatch(self.start_draw):
            raise ValueError("start_draw must look like 'YYYY-MM-DD HH:MM'")
        datetime.strptime(self.start_draw, DRAW_FORMAT)  # rejects impossible dates
        if self.goal <= self.capital:
            raise ValueError("goal is the final balance and must exceed capital")
        return self


class ExperimentRequest(_Frozen):
    name: Name
    conditions: Conditions
    strategies: tuple[Strategy, ...] = Field(min_length=1, max_length=MAX_STRATEGIES)

    @model_validator(mode="after")
    def _unique_names(self) -> Self:
        seen: set[str] = set()
        for index, item in enumerate(self.strategies):
            key = normalize_strategy_name(item.name)
            if key in seen:
                raise CoreValidationError.from_exception_data(
                    title=self.__class__.__name__,
                    line_errors=[
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                "strategy names must be unique within an experiment",
                            ),
                            loc=("strategies", index, "name"),
                            input=item.name,
                        )
                    ],
                )
            seen.add(key)
        return self


def parse_draw_time(label):
    return datetime.strptime(label, DRAW_FORMAT)
