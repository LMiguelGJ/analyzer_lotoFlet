"""Experiment contracts: game, conditions, strategies, statuses and outcomes.

Everything here is data and validation. Rules that need the frozen history
(whether a start draw exists) or staking math (initial affordability) live in
the engine adapter and ``domain.session`` respectively.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

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
    prizes: tuple[int, int, int, int, int]
    allows_repeats: bool


GAME = Game("Quiniela 80", 100, 5, (80, 8, 4, 2, 1), True)

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
