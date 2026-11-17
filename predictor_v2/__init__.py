"""Transparent parity prediction and paper-trading toolkit.

This package is intentionally independent from the legacy application.  It only
supports historical analysis, forecasts, and an in-memory paper ledger; it
never connects to a real-money execution venue.
"""

__version__ = "2.0.0"

from .bayesian_predictor import ExactFeaturePredictor, ParityMarkovPredictor, Prediction
from .betting_economics import economics_for_probability

__all__ = [
    "ExactFeaturePredictor",
    "ParityMarkovPredictor",
    "Prediction",
    "economics_for_probability",
]
