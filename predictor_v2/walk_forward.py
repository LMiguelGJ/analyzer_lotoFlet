"""Strict chronological prequential evaluation and frozen model selection."""

from __future__ import annotations

import math
from array import array
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from .bayesian_predictor import CandidateModel, Prediction, default_candidate_models
from .calibration import CalibrationBin, CalibrationFit, IsotonicCalibrator
from .feature_engineering import IMPAR, PAR, parity_label
from .statistical_tests import ClassificationMetrics, metrics_from_aggregates

SPLITS = ("development", "validation", "test")


@dataclass(frozen=True)
class WalkForwardConfig:
    warmup: int = 1000
    development_fraction: float = 0.60
    validation_fraction: float = 0.20
    calibration_bins: int = 10
    retain_test_predictions: bool = False

    def validate(self) -> None:
        if self.warmup < 0:
            raise ValueError("warmup must be non-negative")
        if not 0.0 < self.development_fraction < 1.0:
            raise ValueError("development_fraction must be in (0, 1)")
        if not 0.0 < self.validation_fraction < 1.0:
            raise ValueError("validation_fraction must be in (0, 1)")
        if self.development_fraction + self.validation_fraction >= 1.0:
            raise ValueError(
                "development and validation fractions must leave a test partition"
            )
        if self.calibration_bins <= 0:
            raise ValueError("calibration_bins must be positive")


@dataclass(frozen=True)
class PartitionInfo:
    name: str
    start_target_index: int
    end_target_index: int
    count: int


class MetricAccumulator:
    """Streaming probability/classification metrics plus reliability bins."""

    def __init__(self, n_bins: int) -> None:
        self.n_bins = n_bins
        self.count = 0
        self.correct = 0
        self.true_positive = 0
        self.false_positive = 0
        self.true_negative = 0
        self.false_negative = 0
        self.brier_sum = 0.0
        self.log_loss_sum = 0.0
        self.boundary_probability_count = 0
        self.raw_counts = [0] * n_bins
        self.raw_probability_sums = [0.0] * n_bins
        self.raw_outcome_sums = [0.0] * n_bins
        self.calibrated_counts = [0] * n_bins
        self.calibrated_probability_sums = [0.0] * n_bins
        self.calibrated_outcome_sums = [0.0] * n_bins

    def _add_curve_point(
        self, probability: float, outcome_positive: bool, calibrated: bool
    ) -> None:
        p = min(1.0, max(0.0, probability))
        index = min(self.n_bins - 1, int(p * self.n_bins))
        if calibrated:
            counts = self.calibrated_counts
            probability_sums = self.calibrated_probability_sums
            outcome_sums = self.calibrated_outcome_sums
        else:
            counts = self.raw_counts
            probability_sums = self.raw_probability_sums
            outcome_sums = self.raw_outcome_sums
        counts[index] += 1
        probability_sums[index] += p
        outcome_sums[index] += 1.0 if outcome_positive else 0.0

    def update(self, actual_side: str, prediction: Prediction) -> None:
        outcome_positive = actual_side == PAR
        predicted_positive = prediction.side == PAR
        probability = min(1.0, max(0.0, prediction.probability_par))
        self.count += 1
        self.correct += int(outcome_positive == predicted_positive)
        if outcome_positive and predicted_positive:
            self.true_positive += 1
        elif not outcome_positive and predicted_positive:
            self.false_positive += 1
        elif not outcome_positive and not predicted_positive:
            self.true_negative += 1
        else:
            self.false_negative += 1
        if probability <= 0.0 or probability >= 1.0:
            self.boundary_probability_count += 1
        epsilon = 1e-15
        clipped = min(1.0 - epsilon, max(epsilon, probability))
        target = 1.0 if outcome_positive else 0.0
        self.brier_sum += (probability - target) ** 2
        self.log_loss_sum += -(
            target * math.log(clipped) + (1.0 - target) * math.log1p(-clipped)
        )
        self._add_curve_point(probability, outcome_positive, calibrated=False)

    def add_calibrated(self, probability: float, actual_side: str) -> None:
        self._add_curve_point(probability, actual_side == PAR, calibrated=True)

    def metrics(self) -> ClassificationMetrics:
        return metrics_from_aggregates(
            count=self.count,
            correct=self.correct,
            true_positive=self.true_positive,
            false_positive=self.false_positive,
            true_negative=self.true_negative,
            false_negative=self.false_negative,
            brier_sum=self.brier_sum,
            log_loss_sum=self.log_loss_sum,
            boundary_probability_count=self.boundary_probability_count,
        )

    def _curve_from(
        self,
        counts: list[int],
        probability_sums: list[float],
        outcome_sums: list[float],
    ) -> tuple[CalibrationBin, ...]:
        result: list[CalibrationBin] = []
        for index, count in enumerate(counts):
            lower = index / self.n_bins
            upper = (index + 1) / self.n_bins
            if count:
                mean = probability_sums[index] / count
                observed = outcome_sums[index] / count
                gap = abs(mean - observed)
            else:
                mean = observed = gap = None
            result.append(
                CalibrationBin(index, lower, upper, count, mean, observed, gap)
            )
        return tuple(result)

    def raw_curve(self) -> tuple[CalibrationBin, ...]:
        return self._curve_from(
            self.raw_counts, self.raw_probability_sums, self.raw_outcome_sums
        )

    def calibrated_curve(self) -> tuple[CalibrationBin, ...]:
        return self._curve_from(
            self.calibrated_counts,
            self.calibrated_probability_sums,
            self.calibrated_outcome_sums,
        )


class _FiftyFiftyBaseline:
    model_name = "baseline_50_50"

    def __init__(self) -> None:
        self._history_length = 0

    def predict(self) -> Prediction:
        return Prediction(
            side=PAR,
            probability_par=0.5,
            probability_impar=0.5,
            point_probability=0.5,
            support=self._history_length,
            context="fixed_50_50",
            model_name=self.model_name,
            metadata={"history_length": self._history_length, "past_only": True},
        )

    def update(self, number: int) -> None:
        self._history_length += 1


class _MajorityBaseline:
    model_name = "baseline_majority"

    def __init__(self) -> None:
        self._par_count = 0
        self._impar_count = 0

    def predict(self) -> Prediction:
        probability_par = (self._par_count + 0.5) / (
            self._par_count + self._impar_count + 1.0
        )
        side = PAR if probability_par >= 0.5 else IMPAR
        point = probability_par if side == PAR else 1.0 - probability_par
        return Prediction(
            side=side,
            probability_par=probability_par,
            probability_impar=1.0 - probability_par,
            point_probability=point,
            support=self._par_count + self._impar_count,
            context="empirical_majority_with_Jeffreys_smoothing",
            model_name=self.model_name,
            metadata={
                "history_length": self._par_count + self._impar_count,
                "past_only": True,
            },
        )

    def update(self, number: int) -> None:
        if parity_label(number) == PAR:
            self._par_count += 1
        else:
            self._impar_count += 1


@dataclass(frozen=True)
class WalkForwardResult:
    observations: int
    warmup: int
    partitions: tuple[PartitionInfo, ...]
    selected_model: str
    selection_reason: str
    selection_scores: Mapping[str, Mapping[str, float | None]]
    split_metrics: Mapping[str, Mapping[str, ClassificationMetrics]]
    baseline_metrics: Mapping[str, Mapping[str, ClassificationMetrics]]
    calibration_fit: CalibrationFit
    calibration_curves: Mapping[str, tuple[CalibrationBin, ...]]
    forecast: Prediction
    test_predictions: tuple[tuple[int, int, str, float, str, int], ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def test_metrics(self) -> ClassificationMetrics:
        return self.split_metrics["test"][self.selected_model]


def _partition_bounds(eligible: int, config: WalkForwardConfig) -> tuple[int, int]:
    development = max(1, int(eligible * config.development_fraction))
    validation_end = max(
        development + 1,
        int(eligible * (config.development_fraction + config.validation_fraction)),
    )
    validation_end = min(eligible - 1, validation_end)
    development = min(development, validation_end - 1)
    return development, validation_end


def _split_for_position(
    position: int, development_end: int, validation_end: int
) -> str:
    if position < development_end:
        return "development"
    if position < validation_end:
        return "validation"
    return "test"


def _calibrated_prediction(
    prediction: Prediction,
    calibrator: IsotonicCalibrator,
) -> Prediction:
    """Apply the frozen development calibrator while preserving raw metadata."""

    raw_probability_par = float(prediction.probability_par)
    raw_probability_impar = float(prediction.probability_impar)
    calibrated_probability_par = calibrator.transform_one(raw_probability_par)
    calibrated_probability_impar = 1.0 - calibrated_probability_par
    # The calibrated probabilities define the operative side and point value;
    # the raw side may disagree after calibration and is kept in metadata.
    calibrated_side = PAR if calibrated_probability_par >= 0.5 else IMPAR
    calibrated_point_probability = max(
        calibrated_probability_par, calibrated_probability_impar
    )
    metadata = dict(prediction.metadata)
    metadata.update(
        {
            "raw_probability_par": raw_probability_par,
            "raw_probability_impar": raw_probability_impar,
            "raw_point_probability": float(prediction.point_probability),
            "raw_side": prediction.side,
            "raw_probabilities": {
                "PAR": raw_probability_par,
                "IMPAR": raw_probability_impar,
            },
            "calibrated_probability_par": calibrated_probability_par,
            "calibrated_probability_impar": calibrated_probability_impar,
            "calibrated_point_probability": calibrated_point_probability,
            "calibrated_side": calibrated_side,
            "calibrated_probabilities": {
                "PAR": calibrated_probability_par,
                "IMPAR": calibrated_probability_impar,
            },
            "calibration_source": calibrator.fit_info.source,
        }
    )
    return replace(
        prediction,
        side=calibrated_side,
        probability_par=calibrated_probability_par,
        probability_impar=calibrated_probability_impar,
        point_probability=calibrated_point_probability,
        metadata=metadata,
    )


class WalkForwardEngine:
    """Evaluate every target chronologically, predicting before updating."""

    def __init__(
        self,
        config: WalkForwardConfig | None = None,
        candidate_factory: Callable[
            [], dict[str, CandidateModel]
        ] = default_candidate_models,
    ) -> None:
        self.config = config or WalkForwardConfig()
        self.config.validate()
        self.candidate_factory = candidate_factory

    def _select_model(
        self,
        split_metrics: Mapping[str, Mapping[str, ClassificationMetrics]],
    ) -> tuple[str, str, dict[str, dict[str, float | None]]]:
        candidates = tuple(split_metrics["validation"].keys())
        scores: dict[str, dict[str, float | None]] = {}
        for name in candidates:
            development = split_metrics["development"][name]
            validation = split_metrics["validation"][name]
            scores[name] = {
                "development_brier": development.brier_score,
                "validation_brier": validation.brier_score,
                "validation_accuracy": validation.accuracy,
            }
        selected = min(
            candidates,
            key=lambda name: (
                scores[name]["validation_brier"]
                if scores[name]["validation_brier"] is not None
                else float("inf"),
                -(scores[name]["validation_accuracy"] or 0.0),
                name,
            ),
        )
        return (
            selected,
            "lowest validation Brier score; ties favor accuracy then name",
            scores,
        )

    def run(self, numbers: Sequence[int] | Iterable[int]) -> WalkForwardResult:
        values = list(numbers)
        if len(values) <= self.config.warmup:
            raise ValueError(
                "not enough observations for configured warmup and test target"
            )
        for number in values:
            if (
                isinstance(number, bool)
                or not isinstance(number, int)
                or not 0 <= number <= 99
            ):
                raise ValueError(
                    "walk-forward input must contain only integer values in 0..99"
                )

        eligible = len(values) - self.config.warmup
        if eligible < 3:
            raise ValueError(
                "at least three scored targets are required for development, validation, and test"
            )
        development_end, validation_end = _partition_bounds(eligible, self.config)
        partitions = (
            PartitionInfo(
                "development",
                self.config.warmup,
                self.config.warmup + development_end - 1,
                development_end,
            ),
            PartitionInfo(
                "validation",
                self.config.warmup + development_end,
                self.config.warmup + validation_end - 1,
                validation_end - development_end,
            ),
            PartitionInfo(
                "test",
                self.config.warmup + validation_end,
                len(values) - 1,
                eligible - validation_end,
            ),
        )

        models = self.candidate_factory()
        if not models:
            raise ValueError("candidate_factory must return at least one model")
        model_names = tuple(models.keys())
        accumulators: dict[str, dict[str, MetricAccumulator]] = {
            split: {
                name: MetricAccumulator(self.config.calibration_bins)
                for name in model_names
            }
            for split in SPLITS
        }
        baselines = {
            _FiftyFiftyBaseline.model_name: _FiftyFiftyBaseline(),
            _MajorityBaseline.model_name: _MajorityBaseline(),
        }
        baseline_accumulators: dict[str, dict[str, MetricAccumulator]] = {
            split: {
                name: MetricAccumulator(self.config.calibration_bins)
                for name in baselines
            }
            for split in SPLITS
        }
        development_probabilities = {name: array("d") for name in model_names}
        development_outcomes = {name: bytearray() for name in model_names}

        for number in values[: self.config.warmup]:
            for model in models.values():
                model.update(number)
            for baseline in baselines.values():
                baseline.update(number)

        selected_model: str | None = None
        selection_reason = ""
        selection_scores: dict[str, dict[str, float | None]] = {}
        calibrator = IsotonicCalibrator()
        test_predictions: list[tuple[int, int, str, float, str, int]] = []
        warnings: list[str] = []

        for position, target_index in enumerate(range(self.config.warmup, len(values))):
            split = _split_for_position(position, development_end, validation_end)
            if split == "test" and selected_model is None:
                completed_metrics = {
                    partition: {
                        name: accumulators[partition][name].metrics()
                        for name in model_names
                    }
                    for partition in SPLITS
                }
                selected_model, selection_reason, selection_scores = self._select_model(
                    completed_metrics
                )
                calibrator.fit(
                    development_probabilities[selected_model].tolist(),
                    development_outcomes[selected_model],
                    source="development_oos_predictions_only",
                )

            actual_number = values[target_index]
            actual_side = parity_label(actual_number)
            predictions: dict[str, Prediction] = {}
            for name, model in models.items():
                prediction = model.predict()
                predictions[name] = prediction
                accumulators[split][name].update(actual_side, prediction)
                if split == "development":
                    development_probabilities[name].append(prediction.probability_par)
                    development_outcomes[name].append(1 if actual_side == PAR else 0)
                if split == "test" and name == selected_model:
                    calibrated_prediction = _calibrated_prediction(
                        prediction, calibrator
                    )
                    accumulators[split][name].add_calibrated(
                        calibrated_prediction.probability_par,
                        actual_side,
                    )
                    if self.config.retain_test_predictions:
                        test_predictions.append(
                            (
                                target_index,
                                actual_number,
                                calibrated_prediction.side,
                                calibrated_prediction.point_probability,
                                actual_side,
                                calibrated_prediction.support,
                            )
                        )

            baseline_predictions: dict[str, Prediction] = {}
            for name, baseline in baselines.items():
                prediction = baseline.predict()
                baseline_predictions[name] = prediction
                baseline_accumulators[split][name].update(actual_side, prediction)

            # This is deliberately after every prediction and metric update.
            for model in models.values():
                model.update(actual_number)
            for baseline in baselines.values():
                baseline.update(actual_number)

        if selected_model is None:
            # A valid partition always has a test target, but retain a safe guard.
            completed_metrics = {
                partition: {
                    name: accumulators[partition][name].metrics()
                    for name in model_names
                }
                for partition in SPLITS
            }
            selected_model, selection_reason, selection_scores = self._select_model(
                completed_metrics
            )
            calibrator.fit(
                development_probabilities[selected_model].tolist(),
                development_outcomes[selected_model],
                source="development_oos_predictions_only",
            )

        split_metrics = {
            split: {
                name: accumulator.metrics()
                for name, accumulator in values_by_model.items()
            }
            for split, values_by_model in accumulators.items()
        }
        baseline_metrics = {
            split: {
                name: accumulator.metrics()
                for name, accumulator in values_by_model.items()
            }
            for split, values_by_model in baseline_accumulators.items()
        }
        selected_accumulator = accumulators["test"][selected_model]
        calibration_curves = {
            "raw_test": selected_accumulator.raw_curve(),
            "calibrated_test": selected_accumulator.calibrated_curve(),
        }
        forecast = _calibrated_prediction(models[selected_model].predict(), calibrator)
        if self.config.warmup < 1000:
            warnings.append(
                "warmup is below the documented default of 1000 observations"
            )
        warnings.append("No dates or IDs exist; list order is treated as chronology.")
        warnings.append(
            "Development/validation results are exploratory; final test is reported separately."
        )
        return WalkForwardResult(
            observations=len(values),
            warmup=self.config.warmup,
            partitions=partitions,
            selected_model=selected_model,
            selection_reason=selection_reason,
            selection_scores=selection_scores,
            split_metrics=split_metrics,
            baseline_metrics=baseline_metrics,
            calibration_fit=calibrator.fit_info,
            calibration_curves=calibration_curves,
            forecast=forecast,
            test_predictions=tuple(test_predictions),
            warnings=tuple(warnings),
        )


def run_walk_forward(
    numbers: Sequence[int] | Iterable[int],
    config: WalkForwardConfig | None = None,
) -> WalkForwardResult:
    """Convenience wrapper around :class:`WalkForwardEngine`."""

    return WalkForwardEngine(config=config).run(numbers)
