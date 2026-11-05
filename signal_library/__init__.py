"""Angstrom Signal Library (v3 foundation). Development only: nothing here is shown to users yet,
and nothing here changes the existing Trend, Stretch and Flow readings or alerts."""

from .core import REGISTRY, SignalRef, SignalResult  # noqa: F401
from .context import DataContext  # noqa: F401
from .engine import evaluate  # noqa: F401
from . import signals_basic, signals_components, signals_market, signals_sentiment, signals_ta  # noqa: F401  (registers the signals)
