"""Small, transparent Bayesian candidate models for strict walk-forward use."""

from __future__ import annotations

import copy
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from .feature_engineering import PAR, context_keys, extract_past_features, parity_label


@dataclass(frozen=True)
class Prediction:
    """Point prediction plus probability, support, and model context metadata."""

    side: str
    probability_par: float
    probability_impar: float
    point_probability: float
    support: int
    context: str
    model_name: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def probabilities(self) -> dict[str, float]:
        return {"PAR": self.probability_par, "IMPAR": self.probability_impar}


class CandidateModel(Protocol):
    """Structural contract every walk-forward candidate model must satisfy."""

    model_name: str

    def predict(self) -> Prediction: ...

    def update(self, number: int) -> None: ...


def _beta_probability(par_count: int, impar_count: int, alpha: float = 0.5) -> float:
    """Jeffreys-smoothed probability of PAR."""

    if alpha <= 0:
        raise ValueError("alpha must be positive")
    return (par_count + alpha) / (par_count + impar_count + 2 * alpha)


def _validate_number(number: int) -> None:
    if isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= 99:
        raise ValueError(
            "observations must be integer numbers in the inclusive range 0..99"
        )


class ParityMarkovPredictor:
    """Variable-order parity model with support-aware hierarchical shrinkage.

    Context probabilities use Jeffreys smoothing and are blended back toward
    shorter contexts and the global rate according to observed support.  No
    probability is amplified beyond the empirical/smoothed evidence.
    """

    model_name = "parity_history_markov"

    def __init__(
        self, max_order: int = 3, alpha: float = 0.5, shrinkage_strength: float = 4.0
    ) -> None:
        if max_order <= 0:
            raise ValueError("max_order must be positive")
        if alpha <= 0 or shrinkage_strength <= 0:
            raise ValueError("alpha and shrinkage_strength must be positive")
        self.max_order = max_order
        self.alpha = alpha
        self.shrinkage_strength = shrinkage_strength
        self.reset()

    def reset(self) -> None:
        self._history: deque[str] = deque(maxlen=self.max_order)
        self._par_count = 0
        self._impar_count = 0
        self._contexts: dict[tuple[str, ...], list[int]] = defaultdict(lambda: [0, 0])
        self._history_length = 0

    @property
    def history_length(self) -> int:
        return self._history_length

    def clone(self) -> ParityMarkovPredictor:
        return copy.deepcopy(self)

    def _blend_context(
        self, p: float, counts: list[int], used: list[dict[str, object]]
    ) -> tuple[float, int]:
        support = counts[0] + counts[1]
        if support == 0:
            return p, 0
        context_probability = _beta_probability(counts[0], counts[1], self.alpha)
        weight = support / (support + self.shrinkage_strength)
        blended = weight * context_probability + (1.0 - weight) * p
        used.append(
            {
                "support": support,
                "context_probability_par": context_probability,
                "weight": weight,
            }
        )
        return blended, support

    def predict(self) -> Prediction:
        p = _beta_probability(self._par_count, self._impar_count, self.alpha)
        used_contexts: list[dict[str, object]] = []
        last_support = 0
        selected_context = "global"
        history = tuple(self._history)
        max_available_order = min(self.max_order, len(history))
        for order in range(1, max_available_order + 1):
            context = history[-order:]
            counts = self._contexts.get(context)
            if counts is None:
                continue
            p, support = self._blend_context(p, counts, used_contexts)
            if support:
                last_support = support
                selected_context = f"order={order};suffix={''.join(context)}"

        p = min(1.0, max(0.0, p))
        side = PAR if p >= 0.5 else "IMPAR"
        point = p if side == PAR else 1.0 - p
        return Prediction(
            side=side,
            probability_par=p,
            probability_impar=1.0 - p,
            point_probability=point,
            support=last_support
            if last_support
            else self._par_count + self._impar_count,
            context=selected_context,
            model_name=self.model_name,
            metadata={
                "history_length": self._history_length,
                "max_order": self.max_order,
                "alpha": self.alpha,
                "shrinkage_strength": self.shrinkage_strength,
                "used_contexts": tuple(tuple(item.items()) for item in used_contexts),
                "past_only": True,
            },
        )

    def update(self, number: int) -> None:
        """Update after the target is revealed; prediction must happen first."""

        _validate_number(number)
        observed = parity_label(number)
        history = tuple(self._history)
        max_available_order = min(self.max_order, len(history))
        for order in range(1, max_available_order + 1):
            context = history[-order:]
            counts = self._contexts[context]
            if observed == PAR:
                counts[0] += 1
            else:
                counts[1] += 1
        if observed == PAR:
            self._par_count += 1
        else:
            self._impar_count += 1
        self._history.append(observed)
        self._history_length += 1


class ExactFeaturePredictor:
    """Bayesian model conditioned on prior exact number and derived run features."""

    model_name = "exact_number_derived_features"

    def __init__(
        self,
        alpha: float = 0.5,
        shrinkage_strength: float = 8.0,
        recent_window: int = 8,
    ) -> None:
        if alpha <= 0 or shrinkage_strength <= 0 or recent_window <= 0:
            raise ValueError(
                "alpha, shrinkage_strength, and recent_window must be positive"
            )
        self.alpha = alpha
        self.shrinkage_strength = shrinkage_strength
        self.recent_window = recent_window
        self.reset()

    def reset(self) -> None:
        self._recent_numbers: deque[int] = deque(maxlen=self.recent_window)
        self._par_count = 0
        self._impar_count = 0
        self._contexts: dict[tuple[object, ...], list[int]] = defaultdict(
            lambda: [0, 0]
        )
        self._history_length = 0

    @property
    def history_length(self) -> int:
        return self._history_length

    def clone(self) -> ExactFeaturePredictor:
        return copy.deepcopy(self)

    def _features(self):
        return extract_past_features(
            self._recent_numbers, recent_window=self.recent_window
        )

    def predict(self) -> Prediction:
        p = _beta_probability(self._par_count, self._impar_count, self.alpha)
        used_contexts: list[dict[str, object]] = []
        selected_context = "global"
        last_support = 0
        features = self._features()
        for key in context_keys(features):
            counts = self._contexts.get(key)
            if counts is None:
                continue
            support = counts[0] + counts[1]
            if support == 0:
                continue
            context_probability = _beta_probability(counts[0], counts[1], self.alpha)
            weight = support / (support + self.shrinkage_strength)
            p = weight * context_probability + (1.0 - weight) * p
            used_contexts.append(
                {
                    "key": key,
                    "support": support,
                    "context_probability_par": context_probability,
                    "weight": weight,
                }
            )
            selected_context = repr(key)
            last_support = support

        p = min(1.0, max(0.0, p))
        side = PAR if p >= 0.5 else "IMPAR"
        point = p if side == PAR else 1.0 - p
        return Prediction(
            side=side,
            probability_par=p,
            probability_impar=1.0 - p,
            point_probability=point,
            support=last_support
            if last_support
            else self._par_count + self._impar_count,
            context=selected_context,
            model_name=self.model_name,
            metadata={
                "history_length": self._history_length,
                "last_number": features.last_number,
                "last_parity": features.last_parity,
                "run_length": features.run_length,
                "run_bucket": features.run_bucket,
                "alpha": self.alpha,
                "shrinkage_strength": self.shrinkage_strength,
                "used_contexts": tuple(tuple(item.items()) for item in used_contexts),
                "past_only": True,
            },
        )

    def update(self, number: int) -> None:
        """Record one revealed target only after its prediction has been consumed."""

        _validate_number(number)
        features = self._features()
        observed = parity_label(number)
        for key in context_keys(features):
            counts = self._contexts[key]
            if observed == PAR:
                counts[0] += 1
            else:
                counts[1] += 1
        if observed == PAR:
            self._par_count += 1
        else:
            self._impar_count += 1
        self._recent_numbers.append(number)
        self._history_length += 1


def default_candidate_models() -> dict[str, CandidateModel]:
    """Construct fresh candidates; callers own and update the returned models."""

    return {
        ParityMarkovPredictor.model_name: ParityMarkovPredictor(max_order=3),
        ExactFeaturePredictor.model_name: ExactFeaturePredictor(),
    }
