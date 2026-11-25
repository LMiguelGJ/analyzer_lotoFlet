"""Validated definitions for mutable user laboratories (not persistence or execution)."""

import copy
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from laboratorio.domain.number_lists import DEFAULT_LIST_ID, get_list, unavailable_message
from laboratorio.domain.ranking_params import validate_ranking_params
from laboratorio.domain.reference_labs import (
    REFERENCE_LABS,
    STAKE_STYLE_LABELS,
    ReferenceLab,
    StakeStyle,
)

SNAPSHOT_VERSION = 1
# This draw-count bound is valid only for the history digest pinned by the service.
FROZEN_HISTORY_SHA256 = "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711"
MAX_FROZEN_DRAWS = 105_426
MAX_SAFE_INTEGER = min(2**53 - 1, 2**63 - 1)
MAX_SESSION_DRAWS_LIMIT = 10_000
# Draws a list without precomputed rankings needs before its rankings carry information.
WARMUP_DRAWS = 500
MAX_STAKE_PER_NUMBER_LIMIT = 1_000_000
_REFERENCE_NAMESPACE = uuid.UUID("5531ba2c-7735-5a3c-a97f-8358244c0fb4")
_SUPPORTED_SYSTEMS = frozenset(lab.system for lab in REFERENCE_LABS)  # Chance Express labs
_REFERENCE_START = min(lab.window_start for lab in REFERENCE_LABS)
_REFERENCE_END = max(lab.window_end for lab in REFERENCE_LABS)


def supported_systems(list_id):
    """Systems a user laboratory may use on a list (Chance keeps its archived family)."""
    if list_id == DEFAULT_LIST_ID:
        return _SUPPORTED_SYSTEMS
    number_list = get_list(list_id)
    return frozenset(number_list.available_systems) if number_list else frozenset()


def default_window(list_id, first_label=None, last_label=None):
    """Default laboratory window: Chance keeps its archived bounds, others use the list's labels."""
    if list_id == DEFAULT_LIST_ID:
        return _REFERENCE_START, _REFERENCE_END
    return first_label, last_label


def _strict_int(value, field):
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


def _validate_max_session_draws(value):
    if value is None:
        return
    if type(value) is not int or not 1 <= value <= MAX_SESSION_DRAWS_LIMIT:
        raise ValueError(
            "El máximo de días por sesión debe ser un número entero entre 1 y "
            f"{MAX_SESSION_DRAWS_LIMIT}, o quedar vacío para no poner límite."
        )


def _validate_max_stake_per_number(value):
    if value is None:
        return
    if type(value) is not int or not 1 <= value <= MAX_STAKE_PER_NUMBER_LIMIT:
        raise ValueError(
            "La apuesta máxima por número debe ser un número entero entre 1 y "
            f"{MAX_STAKE_PER_NUMBER_LIMIT}, o quedar vacía para no poner tope."
        )


def _validate_name(name):
    if type(name) is not str or not name or name != name.strip():
        raise ValueError("name must be non-empty and trimmed")
    try:
        byte_length = len(name.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("name must contain valid UTF-8 text") from exc
    if byte_length > 120 or any(unicodedata.category(char) == "Cc" for char in name):
        raise ValueError("name must be at most 120 UTF-8 bytes and contain no controls")


def _validate_window_label(value):
    if type(value) is not str:
        raise ValueError("window labels must be strings")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError("window labels must use YYYY-MM-DD HH:MM") from exc
    if parsed.strftime("%Y-%m-%d %H:%M") != value:
        raise ValueError("window labels must be canonical YYYY-MM-DD HH:MM")
    return value


def _financial_bounds(config):
    """Prove aggregate replay totals stay in both browser-safe and SQLite integers.

    Replay draws are capped by the pinned 105,426-row history. Before each draw,
    balance is below goal; therefore wagered per draw is below goal and payout is
    below goal * sum(prizes). The largest transient balance is bounded by starting
    capital plus all possible payments. Ladder arithmetic is separately bounded
    by computing its ten integer rounds exactly.
    """
    prize_sum = sum(config.prizes)
    max_wagered = MAX_FROZEN_DRAWS * config.goal
    max_paid = MAX_FROZEN_DRAWS * config.goal * prize_sum
    max_balance = config.capital + max_paid
    totals = max(max_wagered, max_paid, max_balance, abs(max_paid - max_wagered))
    if totals > MAX_SAFE_INTEGER:
        raise ValueError("financial replay bound exceeds safe SQLite/browser integer range")
    if config.stake_style == "ladder":
        gain = config.prizes[0] - config.coverage
        invested = 0
        for _ in range(10):
            stake = max(1, (invested + 10 + gain - 1) // gain)
            invested += config.coverage * stake
            if max(stake, invested) > MAX_SAFE_INTEGER:
                raise ValueError("ladder arithmetic exceeds safe SQLite/browser integer range")


@dataclass(frozen=True, slots=True)
class LaboratoryConfig:
    """Immutable, versioned-config-compatible user inputs; selection kind is derived."""

    system: str
    coverage: int
    stake_style: StakeStyle
    capital: int
    goal: int
    prizes: tuple[int, ...]
    window_start: str
    window_end: str
    # Chance Express keeps its exact historical shape: the id is not serialized for it.
    list_id: str = DEFAULT_LIST_ID
    # Optional per-session deadline in draws (one draw per day on Leidsa). ``None`` = unlimited.
    max_session_draws: int | None = None
    # Optional bank cap: no number receives more than this per draw. ``None`` = no cap.
    max_stake_per_number: int | None = None
    # Optional overrides of the ranking system (window, half-life, scope, components, tie-break).
    # ``None`` keeps today's fixed defaults and is never serialized (see ``ranking_params``).
    ranking_params: dict | None = field(default=None, hash=False)

    def __post_init__(self):
        number_list = get_list(self.list_id)
        if number_list is None:
            raise ValueError("list_id must identify a known number list")
        if type(self.system) is not str:
            raise ValueError("system is not supported by the archived reference family")
        if self.list_id == DEFAULT_LIST_ID:
            if self.system not in _SUPPORTED_SYSTEMS:
                raise ValueError("system is not supported by the archived reference family")
        elif self.system not in number_list.available_systems:
            raise ValueError(unavailable_message(self.system))
        _validate_max_session_draws(self.max_session_draws)
        _validate_max_stake_per_number(self.max_stake_per_number)
        object.__setattr__(
            self,
            "ranking_params",
            validate_ranking_params(self.system, self.list_id, self.ranking_params),
        )
        _strict_int(self.coverage, "coverage")
        if self.coverage > 50:
            raise ValueError("coverage must be between 1 and 50")
        if self.system == "parity" and self.coverage != 50:
            raise ValueError("parity selection requires all 50 numbers")
        if type(self.stake_style) is not str or self.stake_style not in STAKE_STYLE_LABELS:
            raise ValueError(
                "El estilo de apuesta no es válido. Estilos disponibles: "
                + ", ".join(STAKE_STYLE_LABELS)
                + "."
            )
        _strict_int(self.capital, "capital")
        if self.capital < self.coverage:
            raise ValueError("capital must fund at least one unit on every selected number")
        _strict_int(self.goal, "goal")
        if self.goal <= self.capital:
            raise ValueError("goal must exceed initial capital")
        positions = number_list.positions
        if type(self.prizes) is not tuple or len(self.prizes) != positions:
            words = {3: "three", 5: "five"}.get(positions, str(positions))
            raise ValueError(f"prizes must be a tuple of exactly {words} positive integers")
        for prize in self.prizes:
            _strict_int(prize, "prize")
        if self.stake_style in {"bold", "ladder"} and self.prizes[0] <= self.coverage:
            raise ValueError("bold and ladder require first prize greater than coverage")
        if self.stake_style == "oscars_grind" and self.prizes[0] <= self.coverage:
            raise ValueError(
                "Oscar's Grind necesita que el premio del primer puesto sea mayor que la cobertura."
            )
        if self.stake_style == "ladder":
            first_ladder_unit = max(
                1, (10 + self.prizes[0] - self.coverage - 1) // (self.prizes[0] - self.coverage)
            )
            if self.capital < self.coverage * first_ladder_unit:
                raise ValueError("capital cannot fund the first ladder stake")
        start = _validate_window_label(self.window_start)
        end = _validate_window_label(self.window_end)
        if start > end:
            raise ValueError("window_start must not exceed window_end")
        if self.list_id == DEFAULT_LIST_ID and (start < _REFERENCE_START or end > _REFERENCE_END):
            raise ValueError("window must be inside the archived reference date bounds")
        _financial_bounds(self)

    @property
    def selection_kind(self):
        return "parity" if self.system == "parity" else "ranking"

    def to_mapping(self):
        mapping = {
            "schema_version": SNAPSHOT_VERSION,
            "system": self.system,
            "coverage": self.coverage,
            "stake_style": self.stake_style,
            "capital": self.capital,
            "goal": self.goal,
            "prizes": list(self.prizes),
            "window_start": self.window_start,
            "window_end": self.window_end,
        }
        if self.list_id != DEFAULT_LIST_ID:
            mapping["list_id"] = self.list_id
        if self.max_session_draws is not None:
            mapping["max_session_draws"] = self.max_session_draws
        if self.max_stake_per_number is not None:
            mapping["max_stake_per_number"] = self.max_stake_per_number
        if self.ranking_params is not None:
            mapping["ranking_params"] = copy.deepcopy(self.ranking_params)
        return mapping

    @classmethod
    def from_mapping(cls, value):
        keys = {
            "schema_version",
            "system",
            "coverage",
            "stake_style",
            "capital",
            "goal",
            "prizes",
            "window_start",
            "window_end",
        }
        list_id = DEFAULT_LIST_ID
        if type(value) is dict and "list_id" in value:
            list_id = value["list_id"]
            # Only non-default lists carry the id; an explicit default would not round-trip.
            if type(list_id) is not str or list_id == DEFAULT_LIST_ID or get_list(list_id) is None:
                raise ValueError("invalid laboratory config snapshot")
            keys = keys | {"list_id"}
        if type(value) is dict and "max_session_draws" in value:
            keys = keys | {"max_session_draws"}
        if type(value) is dict and "max_stake_per_number" in value:
            keys = keys | {"max_stake_per_number"}
        if type(value) is dict and "ranking_params" in value:
            keys = keys | {"ranking_params"}
        if (
            type(value) is not dict
            or set(value) != keys
            or type(value["schema_version"]) is not int
        ):
            raise ValueError("invalid laboratory config snapshot")
        if value["schema_version"] != SNAPSHOT_VERSION or type(value["prizes"]) is not list:
            raise ValueError("unsupported laboratory config snapshot version or shape")
        return cls(
            system=value["system"],
            coverage=value["coverage"],
            stake_style=value["stake_style"],
            capital=value["capital"],
            goal=value["goal"],
            prizes=tuple(value["prizes"]),
            window_start=value["window_start"],
            window_end=value["window_end"],
            list_id=list_id,
            max_session_draws=value.get("max_session_draws"),
            max_stake_per_number=value.get("max_stake_per_number"),
            ranking_params=value.get("ranking_params"),
        )


@dataclass(frozen=True, slots=True)
class LaboratoryDefinition:
    """Immutable definition identity plus an immutable config snapshot."""

    id: str
    name: str
    config: LaboratoryConfig
    reference_id: str | None = None

    def __post_init__(self):
        if type(self.id) is not str:
            raise ValueError("id must be a canonical UUID")
        try:
            canonical = str(uuid.UUID(self.id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("id must be a canonical UUID") from exc
        if canonical != self.id:
            raise ValueError("id must be a canonical lowercase UUID")
        _validate_name(self.name)
        if type(self.config) is not LaboratoryConfig:
            raise ValueError("config must be a validated LaboratoryConfig")
        if self.reference_id is not None:
            if type(self.reference_id) is not str or self.reference_id not in {
                lab.lab_id for lab in REFERENCE_LABS
            }:
                raise ValueError("reference_id must identify an archived seed template")

    def to_mapping(self):
        return {
            "schema_version": SNAPSHOT_VERSION,
            "id": self.id,
            "name": self.name,
            "reference_id": self.reference_id,
            "config": self.config.to_mapping(),
        }

    @classmethod
    def from_mapping(cls, value):
        keys = {"schema_version", "id", "name", "reference_id", "config"}
        if (
            type(value) is not dict
            or set(value) != keys
            or type(value["schema_version"]) is not int
        ):
            raise ValueError("invalid laboratory definition snapshot")
        if value["schema_version"] != SNAPSHOT_VERSION:
            raise ValueError("unsupported laboratory definition snapshot version")
        config = LaboratoryConfig.from_mapping(value["config"])
        return cls(value["id"], value["name"], config, value["reference_id"])

    def to_reference_lab(self):
        """Adapt config to the legacy engine DTO; this does not enable execution."""
        config = self.config
        return ReferenceLab(
            self.id,
            config.system,
            config.coverage,
            config.stake_style,
            config.selection_kind,
            config.capital,
            config.goal,
            config.prizes,
            config.window_start,
            config.window_end,
            config.list_id,
            config.max_session_draws,
            config.max_stake_per_number,
        )


_PROGRESSION_STYLES = ("martingale", "paroli", "dalembert", "fibonacci")


def validate_new_laboratory_config(config):
    """Extra rules for laboratories created from now on (stored ones keep loading as saved).

    Martingale, Paroli, D'Alembert and Fibonacci can only go broke when the first prize does
    not exceed the coverage, so a new lab like that is refused (B-009).
    """
    if type(config) is not LaboratoryConfig:
        raise ValueError("config must be a validated LaboratoryConfig")
    if config.stake_style in _PROGRESSION_STYLES and config.prizes[0] <= config.coverage:
        label = STAKE_STYLE_LABELS[config.stake_style]
        raise ValueError(
            f"{label} necesita que el primer premio sea mayor que la cobertura: "
            "con un premio igual o menor solo puede perder."
        )


def create_laboratory_definition(name, config, *, existing_names=()):
    """Create a fresh user identity even when name/config match an older definition."""
    _validate_name(name)
    if type(config) is not LaboratoryConfig:
        raise ValueError("config must be a validated LaboratoryConfig")
    for existing in existing_names:
        if type(existing) is not str or existing.casefold() == name.casefold():
            raise ValueError("laboratory name must be unique")
    return LaboratoryDefinition(str(uuid.uuid4()), name, config)


def initial_laboratory_definitions():
    """Return the fourteen deterministic seed definitions; callers seed only once."""
    definitions = []
    for lab in REFERENCE_LABS:
        identity = str(uuid.uuid5(_REFERENCE_NAMESPACE, lab.lab_id))
        config = LaboratoryConfig(
            system=lab.system,
            coverage=lab.coverage,
            stake_style=lab.stake_style,
            capital=lab.capital,
            goal=lab.goal,
            prizes=tuple(lab.prizes),
            window_start=lab.window_start,
            window_end=lab.window_end,
        )
        definitions.append(LaboratoryDefinition(identity, lab.lab_id, config, lab.lab_id))
    return tuple(definitions)
