"""Fixed catalog of selectable number lists (draw histories the app can work with)."""

from dataclasses import dataclass

from laboratorio.settings import HISTORY_SHA256

DEFAULT_LIST_ID = "chance_express"


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
    ),
)

_BY_ID = {item.id: item for item in CATALOG}


def get_list(list_id: object) -> NumberList | None:
    return _BY_ID.get(list_id) if isinstance(list_id, str) else None
