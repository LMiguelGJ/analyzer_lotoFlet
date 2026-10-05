"""Runtime settings: loopback binding, data location and frozen inputs.

The database lives outside the repository and OneDrive, under
``%LOCALAPPDATA%\\LaboratorioQuiniela`` by default. ``LABORATORIO_DATA_DIR``
overrides it (tests always use a temporary directory).
"""

import os
from dataclasses import dataclass
from pathlib import Path

from laboratorio.domain.contracts import Game, configure_game, make_game
from laboratorio.storage.quota import validate_quota_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
APP_DIR_NAME = "LaboratorioQuiniela"

# Frozen inputs: the lab refuses to run if either file changes.
HISTORY_SHA256 = "d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711"
RANKINGS_SHA256 = "b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d"
DEFAULT_QUOTA_BYTES = 5 * 1024**3
DEFAULT_GAME_PRIZES = (80, 8, 4, 2, 1)


def _port_from(value):
    if value is None or value == "":
        return DEFAULT_PORT
    if not value.isdigit() or not 1024 <= int(value) <= 65535:
        raise ValueError(f"LABORATORIO_PORT must be an integer between 1024 and 65535: {value!r}")
    return int(value)


def _quota_from(value: str | None) -> int:
    if value is None or value == "":
        return DEFAULT_QUOTA_BYTES
    if not value.isdecimal():
        raise ValueError("LABORATORIO_QUOTA_BYTES must be a positive integer in bytes")
    return validate_quota_bytes(int(value))


def _int_from(name: str, value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer: {value!r}") from None


def _prizes_from(value: str | None) -> tuple[int, ...]:
    if value is None or value == "":
        return DEFAULT_GAME_PRIZES
    try:
        return tuple(int(part.strip()) for part in value.split(","))
    except ValueError:
        raise ValueError(
            f"LABORATORIO_GAME_PRIZES must be comma-separated integers: {value!r}"
        ) from None


def _bool_from(name: str, value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    lowered = value.strip().lower()
    if lowered in ("1", "true"):
        return True
    if lowered in ("0", "false"):
        return False
    raise ValueError(f"{name} must be one of 1, 0, true or false: {value!r}")


def _default_data_dir():
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / ".local" / "share" / APP_DIR_NAME


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    history_path: Path
    rankings_path: Path
    frontend_dist: Path
    host: str = LOOPBACK_HOST
    port: int = DEFAULT_PORT
    quota_bytes: int = DEFAULT_QUOTA_BYTES
    # None preserves compatibility for manually constructed settings and dataclasses.replace.
    quota_explicit: bool | None = None
    # Game rules; the defaults reproduce Quiniela 80 and are applied on construction.
    game_name: str = "Quiniela 80"
    game_numbers: int = 100
    game_positions: int = 5
    game_prizes: tuple[int, ...] = DEFAULT_GAME_PRIZES
    game_allows_repeats: bool = True
    game_minimum_stake: int = 1

    @property
    def game(self) -> Game:
        return make_game(
            self.game_name,
            self.game_numbers,
            self.game_positions,
            self.game_prizes,
            self.game_allows_repeats,
            self.game_minimum_stake,
        )

    def __post_init__(self):
        validate_quota_bytes(self.quota_bytes)
        if self.quota_explicit is not None and type(self.quota_explicit) is not bool:
            raise ValueError("quota_explicit must be a boolean")
        configure_game(self.game)

    @property
    def is_quota_explicit(self) -> bool:
        return (
            self.quota_explicit
            if self.quota_explicit is not None
            else self.quota_bytes != DEFAULT_QUOTA_BYTES
        )

    @property
    def database_path(self):
        return self.data_dir / "laboratorio.db"

    @property
    def cache_dir(self):
        return self.data_dir / "cache"

    @property
    def log_dir(self):
        return self.data_dir / "logs"

    @classmethod
    def from_environment(cls):
        data_dir = os.environ.get("LABORATORIO_DATA_DIR")
        port = os.environ.get("LABORATORIO_PORT")
        env = os.environ
        return cls(
            data_dir=Path(data_dir) if data_dir else _default_data_dir(),
            history_path=Path(
                os.environ.get("LABORATORIO_HISTORY", REPO_ROOT / "chance_express_history.json")
            ),
            rankings_path=Path(
                os.environ.get(
                    "LABORATORIO_RANKINGS",
                    REPO_ROOT / "repo_ref/reports/chance_rank_v1/predictions/pos1.npz",
                )
            ),
            frontend_dist=REPO_ROOT / "webapp/frontend/dist",
            port=_port_from(port),
            quota_bytes=_quota_from(os.environ.get("LABORATORIO_QUOTA_BYTES")),
            quota_explicit="LABORATORIO_QUOTA_BYTES" in os.environ,
            game_name=env.get("LABORATORIO_GAME_NAME") or "Quiniela 80",
            game_numbers=_int_from(
                "LABORATORIO_GAME_NUMBERS", env.get("LABORATORIO_GAME_NUMBERS"), 100
            ),
            game_positions=_int_from(
                "LABORATORIO_GAME_POSITIONS", env.get("LABORATORIO_GAME_POSITIONS"), 5
            ),
            game_prizes=_prizes_from(env.get("LABORATORIO_GAME_PRIZES")),
            game_allows_repeats=_bool_from(
                "LABORATORIO_GAME_REPEATS", env.get("LABORATORIO_GAME_REPEATS"), True
            ),
            game_minimum_stake=_int_from(
                "LABORATORIO_GAME_MINIMUM_STAKE", env.get("LABORATORIO_GAME_MINIMUM_STAKE"), 1
            ),
        )
