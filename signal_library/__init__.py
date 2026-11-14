"""Angstrom Signal Library (v3 foundation). Development only: nothing here is shown to users yet,
and nothing here changes the existing Trend, Stretch and Flow readings or alerts."""

from .core import REGISTRY, SignalRef, SignalResult  # noqa: F401
from .display_names import install as _display_names

_display_names(REGISTRY)    # "Sonar", not the trademarked "Market Cipher", on every page (display_names.py)
from .context import DataContext  # noqa: F401
from .engine import evaluate  # noqa: F401
from . import signals_basic, signals_components, signals_market, signals_sentiment, signals_ta  # noqa: F401  (registers the signals)
from . import signals_candles  # noqa: F401,E402  (moving averages of any length, the candle, volatility)
from . import signals_oscillators  # noqa: F401,E402  (WaveTrend, money flow, Stochastic on OHLC4, divergence across timeframes)
from . import signals_options  # noqa: F401,E402  (options max pain, from stored snapshots)
from . import signals_sonar  # noqa: F401,E402  (Sonar markers on the price chart, Stoch RSI pair)
from . import signals_shapes  # noqa: F401,E402  (chart shapes: head and shoulders, double tops and bottoms)
