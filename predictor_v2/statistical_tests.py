"""Dependency-free metrics, exact binomial testing, intervals, and bootstrap notes."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from .feature_engineering import PAR

MULTIPLE_COMPARISON_NOTE = (
    "Candidate and baseline comparisons are multiple comparisons; a nominal p-value "
    "is descriptive and is not an adjusted claim of an edge."
)


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int


@dataclass(frozen=True)
class WilsonInterval:
    lower: float
    upper: float
    confidence: float


@dataclass(frozen=True)
class BinomialTestResult:
    trials: int
    successes: int
    null_probability: float
    alternative: str
    p_value: float | None
    method: str
    note: str


@dataclass(frozen=True)
class ClassificationMetrics:
    count: int
    accuracy: float | None
    precision_par: float | None
    recall_par: float | None
    f1_par: float | None
    confusion: ConfusionMatrix
    brier_score: float | None
    log_loss: float | None
    boundary_probability_count: int
    log_loss_boundary_handling: str
    binomial_test: BinomialTestResult
    accuracy_wilson: WilsonInterval | None
    multiple_comparison_note: str = MULTIPLE_COMPARISON_NOTE


@dataclass(frozen=True)
class BootstrapSummary:
    resamples: int
    block_size: int
    mean_accuracy: float | None
    lower_accuracy: float | None
    upper_accuracy: float | None
    seed: int
    note: str


def wilson_interval(
    successes: int, trials: int, confidence: float = 0.95
) -> WilsonInterval | None:
    """Return a two-sided Wilson interval, or ``None`` for no trials."""

    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("successes and trials must define a valid binomial count")
    if trials == 0:
        return None
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return WilsonInterval(
        lower=max(0.0, center - radius),
        upper=min(1.0, center + radius),
        confidence=confidence,
    )


def _log_binomial_pmf(trials: int, successes: int, probability: float) -> float:
    if successes < 0 or successes > trials:
        return float("-inf")
    if probability == 0.0:
        return 0.0 if successes == 0 else float("-inf")
    if probability == 1.0:
        return 0.0 if successes == trials else float("-inf")
    return (
        math.lgamma(trials + 1)
        - math.lgamma(successes + 1)
        - math.lgamma(trials - successes + 1)
        + successes * math.log(probability)
        + (trials - successes) * math.log1p(-probability)
    )


def exact_one_sided_binomial(
    successes: int,
    trials: int,
    null_probability: float = 0.5,
) -> BinomialTestResult:
    """Compute exact ``P(X >= successes)`` under H0 for H1: accuracy > H0."""

    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("successes and trials must define a valid binomial count")
    if not 0.0 < null_probability < 1.0:
        raise ValueError("null_probability must be in (0, 1)")
    if trials == 0:
        return BinomialTestResult(
            trials=0,
            successes=0,
            null_probability=null_probability,
            alternative="greater",
            p_value=None,
            method="exact one-sided binomial",
            note="No trials: significance is undefined.",
        )
    if successes <= 0:
        p_value = 1.0
    elif successes > trials * null_probability:
        term = math.exp(_log_binomial_pmf(trials, successes, null_probability))
        total = term
        for value in range(successes, trials):
            if term == 0.0:
                break
            term *= (trials - value) / (value + 1)
            term *= null_probability / (1.0 - null_probability)
            total += term
        p_value = min(1.0, max(0.0, total))
    else:
        # Sum the lower tail through successes-1 and use its complement.  This
        # avoids walking a long upper tail when the observed result is not high.
        cutoff = successes - 1
        term = math.exp(_log_binomial_pmf(trials, cutoff, null_probability))
        lower = term
        for value in range(cutoff, 0, -1):
            if term == 0.0:
                break
            term *= value / (trials - value + 1)
            term *= (1.0 - null_probability) / null_probability
            lower += term
        p_value = min(1.0, max(0.0, 1.0 - lower))
    return BinomialTestResult(
        trials=trials,
        successes=successes,
        null_probability=null_probability,
        alternative="greater",
        p_value=p_value,
        method="exact one-sided binomial",
        note="H0: accuracy equals 0.5; H1: accuracy is greater than 0.5.",
    )


def metrics_from_aggregates(
    count: int,
    correct: int,
    true_positive: int,
    false_positive: int,
    true_negative: int,
    false_negative: int,
    brier_sum: float,
    log_loss_sum: float,
    boundary_probability_count: int,
    epsilon: float = 1e-15,
) -> ClassificationMetrics:
    if count < 0:
        raise ValueError("count cannot be negative")
    confusion = ConfusionMatrix(
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
    )
    accuracy = correct / count if count else None
    predicted_positive = true_positive + false_positive
    actual_positive = true_positive + false_negative
    precision = true_positive / predicted_positive if predicted_positive else None
    recall = true_positive / actual_positive if actual_positive else None
    if precision is not None and recall is not None and precision + recall:
        f1 = 2.0 * precision * recall / (precision + recall)
    else:
        f1 = None
    return ClassificationMetrics(
        count=count,
        accuracy=accuracy,
        precision_par=precision,
        recall_par=recall,
        f1_par=f1,
        confusion=confusion,
        brier_score=brier_sum / count if count else None,
        log_loss=log_loss_sum / count if count else None,
        boundary_probability_count=boundary_probability_count,
        log_loss_boundary_handling=(
            f"p=0 or p=1 occurred {boundary_probability_count} time(s); "
            f"log loss used clipping to [{epsilon:g}, {1.0 - epsilon:g}]"
        ),
        binomial_test=exact_one_sided_binomial(correct, count),
        accuracy_wilson=wilson_interval(correct, count),
    )


def classification_metrics(
    actual: Sequence[str],
    predicted: Sequence[str],
    probability_par: Sequence[float] | None = None,
    epsilon: float = 1e-15,
) -> ClassificationMetrics:
    """Calculate classification and probability metrics with explicit edge handling."""

    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have equal length")
    if probability_par is not None and len(probability_par) != len(actual):
        raise ValueError("probability_par must match actual length")
    count = len(actual)
    correct = tp = fp = tn = fn = boundary = 0
    brier_sum = log_loss_sum = 0.0
    for index, (observed, predicted_side) in enumerate(zip(actual, predicted)):
        observed_positive = observed == PAR
        predicted_positive = predicted_side == PAR
        correct += int(observed_positive == predicted_positive)
        if observed_positive and predicted_positive:
            tp += 1
        elif not observed_positive and predicted_positive:
            fp += 1
        elif not observed_positive and not predicted_positive:
            tn += 1
        else:
            fn += 1
        probability = (
            float(probability_par[index])
            if probability_par is not None
            else float(predicted_positive)
        )
        if probability <= 0.0 or probability >= 1.0:
            boundary += 1
        p = min(1.0 - epsilon, max(epsilon, probability))
        target = 1.0 if observed_positive else 0.0
        brier_sum += (probability - target) ** 2
        log_loss_sum += -(target * math.log(p) + (1.0 - target) * math.log1p(-p))
    return metrics_from_aggregates(
        count=count,
        correct=correct,
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        brier_sum=brier_sum,
        log_loss_sum=log_loss_sum,
        boundary_probability_count=boundary,
        epsilon=epsilon,
    )


def block_bootstrap_accuracy(
    actual: Sequence[str],
    predicted: Sequence[str],
    block_size: int = 10,
    resamples: int = 200,
    seed: int = 12345,
) -> BootstrapSummary:
    """Estimate accuracy uncertainty while preserving short-range blocks."""

    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have equal length")
    if block_size <= 0 or resamples < 0:
        raise ValueError("block_size must be positive and resamples cannot be negative")
    n = len(actual)
    if not n or not resamples:
        return BootstrapSummary(
            resamples,
            block_size,
            None,
            None,
            None,
            seed,
            "No bootstrap samples were requested or available.",
        )
    rng = random.Random(seed)
    block_size = min(block_size, n)
    estimates: list[float] = []
    for _ in range(resamples):
        correct = 0
        drawn = 0
        while drawn < n:
            start = rng.randrange(0, n - block_size + 1)
            take = min(block_size, n - drawn)
            for offset in range(take):
                correct += int(actual[start + offset] == predicted[start + offset])
            drawn += take
        estimates.append(correct / n)
    estimates.sort()
    lower = estimates[int(0.025 * (len(estimates) - 1))]
    upper = estimates[int(0.975 * (len(estimates) - 1))]
    return BootstrapSummary(
        resamples=resamples,
        block_size=block_size,
        mean_accuracy=sum(estimates) / len(estimates),
        lower_accuracy=lower,
        upper_accuracy=upper,
        seed=seed,
        note="Block bootstrap is descriptive; it does not correct multiple comparisons or establish causality.",
    )
