"""Dependency-free out-of-sample isotonic calibration and reliability bins."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationBin:
    bin_index: int
    lower: float
    upper: float
    count: int
    mean_predicted: float | None
    observed_rate: float | None
    absolute_gap: float | None


@dataclass(frozen=True)
class CalibrationFit:
    fitted: bool
    source: str
    sample_count: int
    block_count: int
    warning: str | None = None


def _as_binary(value: object) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, str):
        normalized = value.upper()
        if normalized == "PAR":
            return 1
        if normalized == "IMPAR":
            return 0
    if value in (0, 1):
        return int(value)
    raise ValueError(f"unsupported binary outcome: {value!r}")


def calibration_curve(
    probabilities: Iterable[float],
    outcomes: Iterable[object],
    n_bins: int = 10,
) -> tuple[CalibrationBin, ...]:
    """Build reliability bins without fitting any parameters."""

    if n_bins <= 0:
        raise ValueError("n_bins must be positive")
    bins: list[list[float | int]] = [[0, 0.0, 0.0] for _ in range(n_bins)]
    for probability, outcome in zip(probabilities, outcomes):
        p = min(1.0, max(0.0, float(probability)))
        index = min(n_bins - 1, int(p * n_bins))
        bins[index][0] += 1
        bins[index][1] += p
        bins[index][2] += _as_binary(outcome)
    result: list[CalibrationBin] = []
    for index, (count_raw, probability_sum, outcome_sum) in enumerate(bins):
        count = int(count_raw)
        lower = index / n_bins
        upper = (index + 1) / n_bins
        if count:
            mean = float(probability_sum) / count
            observed = float(outcome_sum) / count
            gap = abs(mean - observed)
        else:
            mean = observed = gap = None
        result.append(
            CalibrationBin(
                bin_index=index,
                lower=lower,
                upper=upper,
                count=count,
                mean_predicted=mean,
                observed_rate=observed,
                absolute_gap=gap,
            )
        )
    return tuple(result)


class IsotonicCalibrator:
    """Monotone PAV calibrator intended for OOS development predictions only."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._blocks: list[tuple[float, float, float]] = []
        self.fit_info = CalibrationFit(
            fitted=False,
            source="none",
            sample_count=0,
            block_count=0,
            warning="calibrator is not fitted; identity transform is used",
        )

    def fit(
        self,
        probabilities: Sequence[float],
        outcomes: Sequence[object],
        source: str = "development_oos",
    ) -> IsotonicCalibrator:
        """Fit PAV and reject labels that would imply fitting on final test data."""

        if len(probabilities) != len(outcomes):
            raise ValueError("probabilities and outcomes must have equal length")
        if "test" in source.lower() or "final" in source.lower():
            raise ValueError(
                "calibration must be frozen before final test; test data cannot fit it"
            )
        if not probabilities:
            self.reset()
            self.fit_info = CalibrationFit(
                fitted=False,
                source=source,
                sample_count=0,
                block_count=0,
                warning="no OOS development predictions were available",
            )
            return self

        sorted_points = sorted(
            (min(1.0, max(0.0, float(probability))), float(_as_binary(outcome)))
            for probability, outcome in zip(probabilities, outcomes)
        )
        grouped_points: list[tuple[float, float, float]] = []
        for probability, outcome in sorted_points:
            if grouped_points and grouped_points[-1][0] == probability:
                previous_probability, outcome_sum, weight = grouped_points[-1]
                grouped_points[-1] = (
                    previous_probability,
                    outcome_sum + outcome,
                    weight + 1.0,
                )
            else:
                grouped_points.append((probability, outcome, 1.0))

        blocks: list[dict[str, float]] = []
        for probability, outcome_sum, weight in grouped_points:
            blocks.append(
                {
                    "start": probability,
                    "end": probability,
                    "sum": outcome_sum,
                    "weight": weight,
                }
            )
            while len(blocks) >= 2:
                previous = blocks[-2]
                current = blocks[-1]
                previous_mean = previous["sum"] / previous["weight"]
                current_mean = current["sum"] / current["weight"]
                if previous_mean <= current_mean:
                    break
                previous["end"] = current["end"]
                previous["sum"] += current["sum"]
                previous["weight"] += current["weight"]
                blocks.pop()

        self._blocks = [
            (block["start"], block["end"], block["sum"] / block["weight"])
            for block in blocks
        ]
        self.fit_info = CalibrationFit(
            fitted=True,
            source=source,
            sample_count=len(sorted_points),
            block_count=len(self._blocks),
            warning=None,
        )
        return self

    def transform_one(self, probability: float) -> float:
        p = min(1.0, max(0.0, float(probability)))
        if not self._blocks:
            return p
        for start, end, value in self._blocks:
            if p <= end:
                return value
        return self._blocks[-1][2]

    def transform(self, probabilities: Iterable[float]) -> list[float]:
        return [self.transform_one(probability) for probability in probabilities]

    def calibration_curve(
        self,
        probabilities: Iterable[float],
        outcomes: Iterable[object],
        n_bins: int = 10,
    ) -> tuple[CalibrationBin, ...]:
        return calibration_curve(self.transform(probabilities), outcomes, n_bins=n_bins)
