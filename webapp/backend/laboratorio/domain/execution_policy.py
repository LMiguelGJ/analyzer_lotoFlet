"""Bounded shared admission/execution limits; worker parallelism is fixed."""

from dataclasses import dataclass

POLICY_FIELDS = frozenset(
    {
        "max_strategies_per_batch",
        "worker_count",
        "max_pending_runs",
        "max_bet_draws",
        "max_elapsed_draws",
        "run_timeout_seconds",
    }
)
EDITABLE_FIELDS = POLICY_FIELDS - {"worker_count"}
POLICY_DEFAULTS = {
    "max_strategies_per_batch": 3,
    "worker_count": 1,
    "max_pending_runs": 10,
    "max_bet_draws": 1_000,
    "max_elapsed_draws": 10_000,
    "run_timeout_seconds": 120,
}
POLICY_BOUNDS = {
    "max_strategies_per_batch": (1, 3),
    "worker_count": (1, 1),
    "max_pending_runs": (1, 100),
    "max_bet_draws": (1, 10_000),
    "max_elapsed_draws": (1, 10_000),
    "run_timeout_seconds": (1, 3_600),
}


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    max_strategies_per_batch: int
    worker_count: int
    max_pending_runs: int
    max_bet_draws: int
    max_elapsed_draws: int
    run_timeout_seconds: int

    @classmethod
    def defaults(cls) -> "ExecutionPolicy":
        return cls.from_values(POLICY_DEFAULTS)

    @classmethod
    def from_values(cls, values: dict) -> "ExecutionPolicy":
        if type(values) is not dict or values.keys() != POLICY_FIELDS:
            raise ValueError("execution policy must contain exactly the supported fields")
        for field, (minimum, maximum) in POLICY_BOUNDS.items():
            value = values[field]
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{field} must be an integer from {minimum} to {maximum}")
        if values["worker_count"] != 1:
            raise ValueError("worker_count is fixed at one and cannot be changed")
        return cls(**values)

    def as_dict(self) -> dict[str, int]:
        return {field: getattr(self, field) for field in POLICY_DEFAULTS}
