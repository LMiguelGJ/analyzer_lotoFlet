"""Immutable structural v2 definitions and complete run-snapshot values.

A structural value does not compile a strategy, prove source provenance or admit
execution. The catalog/service must establish those facts before persistence.
"""

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Any, Self

from laboratorio.domain.configurable_runs import RunWindow
from laboratorio.domain.contracts import MAX_MONEY
from laboratorio.domain.quiniela_profiles import QuinielaProfile

_HASH = re.compile(r"[0-9a-f]{64}")
_BLOCK_KINDS = {
    "selection": frozenset({"manual", "parity", "archived-ranking", "archived-mixture"}),
    "stake": frozenset({"fixed", "flat", "bold", "ladder"}),
    "close": frozenset({"goal-or-ruin"}),
}


def _text(value: object, *, maximum=120) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("text must be nonempty and already trimmed")
    if len(value.encode("utf-8")) > maximum:
        raise ValueError("text exceeds its UTF-8 byte limit")
    return value


def _identifier(value: object) -> str:
    text = _text(value)
    try:
        if str(uuid.UUID(text)) != text:
            raise ValueError("id must be a canonical UUID")
    except (ValueError, AttributeError) as error:
        raise ValueError("id must be a canonical UUID") from error
    return text


def _sha(value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError("digest must be lowercase SHA-256 hex")
    return value


def _money(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_MONEY:
        raise ValueError("money must be a positive safe integer")
    return value


def _freeze(value: object, *, depth=0, nodes=None) -> object:
    nodes = [0] if nodes is None else nodes
    nodes[0] += 1
    if depth > 8 or nodes[0] > 2000:
        raise ValueError("parameters exceed depth/node limits")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if abs(value) > 2**53 - 1:
            raise ValueError("parameter integer exceeds JavaScript-safe bounds")
        return value
    if type(value) is str:
        if len(value.encode("utf-8")) > 512:
            raise ValueError("parameter string exceeds512 UTF-8 bytes")
        return value
    if isinstance(value, Mapping):
        if len(value) > 64:
            raise ValueError("parameters contain too many keys")
        result = {}
        for key, child in value.items():
            name = _text(key, maximum=80)
            result[name] = _freeze(child, depth=depth + 1, nodes=nodes)
        return MappingProxyType(result)
    if isinstance(value, (list, tuple)):
        if len(value) > 1000:
            raise ValueError("parameter array exceeds1000 elements")
        return tuple(_freeze(child, depth=depth + 1, nodes=nodes) for child in value)
    raise ValueError(
        "parameters must contain bounded exact JSON values, never floats or code objects"
    )


def _encode(value):
    if isinstance(value, (_Value, QuinielaProfile, RunWindow)):
        return value.to_mapping()
    if isinstance(value, Mapping):
        return {key: _encode(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_encode(child) for child in value]
    return value


def _mapping_sha(value) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Value:
    schema_version: int

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 2:
            raise ValueError("schema_version must be integer2")

    @classmethod
    def _parts(cls, value: dict[str, Any]) -> dict[str, Any]:
        return value

    @classmethod
    def from_mapping(cls, value: object) -> Self:
        expected = {field.name for field in fields(cls)}
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("mapping must contain exactly the supported v2 fields")
        return cls(**cls._parts(dict(value)))

    def to_mapping(self) -> dict[str, Any]:
        return {field.name: _encode(getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True)
class SourceReference(_Value):
    id: str
    sha256: str
    profile_sha256: str
    origin: str
    raw_sha256: str
    rankings_sha256: str | None

    def __post_init__(self):
        super().__post_init__()
        _identifier(self.id)
        _sha(self.sha256)
        _sha(self.profile_sha256)
        _sha(self.raw_sha256)
        if self.origin not in ("included", "imported"):
            raise ValueError("unknown source origin")
        if self.rankings_sha256 is not None:
            _sha(self.rankings_sha256)
        if self.origin == "imported" and self.rankings_sha256 is not None:
            raise ValueError("an imported source cannot claim archived rankings")


@dataclass(frozen=True)
class BlockSnapshot(_Value):
    role: str
    kind: str
    version: int
    parameters: Mapping[str, object]

    def __post_init__(self):
        super().__post_init__()
        if type(self.role) is not str or self.role not in _BLOCK_KINDS:
            raise ValueError("unknown block role")
        if type(self.kind) is not str or self.kind not in _BLOCK_KINDS[self.role]:
            raise ValueError("unknown or misplaced block kind")
        if type(self.version) is not int or self.version != 1:
            raise ValueError("unsupported block version")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("parameters must be an object")
        object.__setattr__(self, "parameters", _freeze(self.parameters))


@dataclass(frozen=True)
class StrategySnapshot(_Value):
    selection: BlockSnapshot
    stake: BlockSnapshot
    close: BlockSnapshot

    def __post_init__(self):
        super().__post_init__()
        for role in ("selection", "stake", "close"):
            block = getattr(self, role)
            if not isinstance(block, BlockSnapshot) or block.role != role:
                raise ValueError("strategy must contain the correct three block roles")

    @classmethod
    def _parts(cls, value):
        return value | {
            role: BlockSnapshot.from_mapping(value[role])
            for role in ("selection", "stake", "close")
        }


@dataclass(frozen=True)
class RunConditions(_Value):
    capital: int
    goal: int
    window: RunWindow

    def __post_init__(self):
        super().__post_init__()
        _money(self.capital)
        _money(self.goal)
        if self.goal <= self.capital:
            raise ValueError("goal must exceed capital")
        if not isinstance(self.window, RunWindow):
            raise ValueError("window must be a validated v2 window")

    @classmethod
    def _parts(cls, value):
        return value | {"window": RunWindow.from_mapping(value["window"])}


@dataclass(frozen=True)
class ConfigurableLaboratoryConfig(_Value):
    profile: QuinielaProfile
    source: SourceReference
    strategy: StrategySnapshot
    conditions: RunConditions

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.profile, QuinielaProfile):
            raise ValueError("profile must be a validated v2 profile")
        if not isinstance(self.source, SourceReference):
            raise ValueError("source must be a validated v2 reference")
        if not isinstance(self.strategy, StrategySnapshot):
            raise ValueError("strategy must be a structural v2 snapshot")
        if not isinstance(self.conditions, RunConditions):
            raise ValueError("conditions must be validated v2 values")
        if self.source.profile_sha256 != _mapping_sha(self.profile.to_mapping()):
            raise ValueError("source profile identity does not match snapshot")
        if self.conditions.capital < self.profile.rules.minimum_stake:
            raise ValueError("capital cannot fund even one minimum stake")

    @classmethod
    def _parts(cls, value):
        return value | {
            "profile": QuinielaProfile.from_mapping(value["profile"]),
            "source": SourceReference.from_mapping(value["source"]),
            "strategy": StrategySnapshot.from_mapping(value["strategy"]),
            "conditions": RunConditions.from_mapping(value["conditions"]),
        }


@dataclass(frozen=True)
class ConfigurableLaboratoryDefinition(_Value):
    id: str
    name: str
    reference_id: str | None
    config: ConfigurableLaboratoryConfig

    def __post_init__(self):
        super().__post_init__()
        _identifier(self.id)
        _text(self.name)
        if self.reference_id is not None:
            _text(self.reference_id, maximum=80)
        if not isinstance(self.config, ConfigurableLaboratoryConfig):
            raise ValueError("config must be a structural v2 configuration")

    @classmethod
    def _parts(cls, value):
        return value | {"config": ConfigurableLaboratoryConfig.from_mapping(value["config"])}


@dataclass(frozen=True)
class ConfigurableRunSnapshot(_Value):
    kind: str
    definition: ConfigurableLaboratoryDefinition
    engine_version: str
    profile_sha256: str
    strategy_sha256: str
    history_sha256: str

    def __post_init__(self):
        super().__post_init__()
        if self.kind != "configurable_quiniela_run":
            raise ValueError("unknown run snapshot kind")
        _text(self.engine_version, maximum=80)
        if not isinstance(self.definition, ConfigurableLaboratoryDefinition):
            raise ValueError("snapshot requires its complete definition")
        config = self.definition.config
        if (
            _sha(self.profile_sha256) != _mapping_sha(config.profile.to_mapping())
            or _sha(self.strategy_sha256) != _mapping_sha(config.strategy.to_mapping())
            or _sha(self.history_sha256) != config.source.sha256
        ):
            raise ValueError("run snapshot reference digests do not match its values")

    @classmethod
    def _parts(cls, value):
        return value | {
            "definition": ConfigurableLaboratoryDefinition.from_mapping(value["definition"])
        }


def create_definition(name, config, *, reference_id=None):
    if type(name) is not str:
        raise ValueError("name must be a string")
    if isinstance(config, ConfigurableLaboratoryConfig):
        config = config.to_mapping()
    validated = ConfigurableLaboratoryConfig.from_mapping(config)
    return ConfigurableLaboratoryDefinition(
        2, str(uuid.uuid4()), name.strip(), reference_id, validated
    )


def create_run_snapshot(definition, engine_version):
    if not isinstance(definition, ConfigurableLaboratoryDefinition):
        raise ValueError("definition must be a validated v2 value")
    definition = ConfigurableLaboratoryDefinition.from_mapping(definition.to_mapping())
    config = definition.config
    return ConfigurableRunSnapshot(
        2,
        "configurable_quiniela_run",
        definition,
        engine_version,
        _mapping_sha(config.profile.to_mapping()),
        _mapping_sha(config.strategy.to_mapping()),
        config.source.sha256,
    )
