"""Fixed catalog of selectable number lists (draw histories the app can work with)."""

from dataclasses import dataclass

from laboratorio.domain.contracts import SYSTEMS
from laboratorio.settings import HISTORY_SHA256

DEFAULT_LIST_ID = "chance_express"
PARITY_SYSTEM = "parity"
PARITY_LABEL = "Paridad"
UNAVAILABLE_REASON = "No disponible para esta lista"


@dataclass(frozen=True, slots=True)
class NumberList:
    id: str
    name: str
    history_file: str  # repository-relative, resolved from REPO_ROOT
    positions: int
    number_range: tuple[int, int]
    default_prizes: tuple[int, ...]
    history_sha256: str | None  # None: the history is not pinned
    has_rankings: bool
    # Ids usable on this list: "parity" (computed on the fly) plus the ranking systems it can feed.
    available_systems: tuple[str, ...] = ()

    @property
    def stem(self) -> str:
        return self.history_file.rsplit("/", 1)[-1]


CATALOG: tuple[NumberList, ...] = (
    NumberList(
        id="chance_express",
        name="Loteka Chance Express",
        history_file="datos/chance_express_history.json",
        positions=5,
        number_range=(0, 99),
        default_prizes=(80, 8, 4, 2, 1),
        history_sha256=HISTORY_SHA256,
        has_rankings=True,
        available_systems=(PARITY_SYSTEM, *SYSTEMS),
    ),
    NumberList(
        id="leidsa_quiniela",
        name="Quiniela Leidsa",
        history_file="datos/leidsa_quiniela_history.json",
        positions=3,
        number_range=(0, 99),
        default_prizes=(60, 8, 4),
        history_sha256=None,
        has_rankings=False,
        available_systems=(PARITY_SYSTEM, "cold", "freq_hist", "freq_recent", "decay"),
    ),
)

_BY_ID = {item.id: item for item in CATALOG}


def get_list(list_id: object) -> NumberList | None:
    return _BY_ID.get(list_id) if isinstance(list_id, str) else None


def system_label(system: str) -> str:
    return PARITY_LABEL if system == PARITY_SYSTEM else SYSTEMS.get(system, system)


def unavailable_message(system: str) -> str:
    """Spanish rejection for a system the list cannot offer."""
    return f"El sistema «{system_label(system)}»: {UNAVAILABLE_REASON}."
