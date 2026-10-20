"""
Crypto & Equity Signals Dashboard
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_fetchers import fetch_crypto_data, fetch_stock_data
from scoring import calculate_indicators, compute_score
import json
import os

# Page config
st.set_page_config(
    page_title="angstrom signals - level 1",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Top row layout: Title on the left, Help button aligned to the right
title_col, help_col = st.columns([5, 1])

with title_col:
    st.title("angstrom signals - level 1")

with help_col:
    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
    with st.popover("❓ Help", width="stretch"):
        st.markdown("""
        ### What this dashboard does
        It scores a watchlist of cryptos and stocks using multi-factor technical indicators and displays results in structured tables and an interactive chart. **Higher score = more bullish setup** according to the scoring rules below. This is a research tool, not financial advice.

        ### Comprehensive Scoring Model (0–100 Scale)
        The composite score starts at a baseline neutral value of **50** and adjusts dynamically based on weighted technical factors:
        - **RSI (14)**: Oversold (<40) adds bullish points for potential mean-reversion bounces; overbought (>60) subtracts points due to pullback risks.
        - **Stochastic Oscillator**: Oversold levels add support points; overbought levels subtract points.
        - **Moving Averages (SMA 20 & SMA 50)**: Trading above both short- and medium-term SMAs adds major trend points; trading below both subtracts points.
        - **ADX (Trend Strength)**: Strong trends (high ADX values) amplify the weight of active moving average and momentum directions.
        - **MACD & Histogram**: Bullish MACD crossovers and positive histogram expansion add upward momentum points; bearish crosses subtract points.
        - **Ichimoku Cloud**: Price trading cleanly above the cloud adds bullish trend support; trading below the cloud subtracts points.
        - **Bollinger Bands (20, 2.0)**: Price hugging or dipping below the lower band adds support/reversion points; pressing against the upper band subtracts resistance points.
        - **Volume & OBV (On-Balance Volume)**: High relative volume supporting an upward move adds conviction points; negative volume trends weigh the score down.
        - **Performance (7-Day)**: Positive 7-day trailing price momentum boosts the score; sharp trailing declines weigh it down.

        ### Signal Zones & Color Coding
        - **Strong Bullish / Bullish (Score ≥ 60) [Green]**: Clear upward technical alignment across multiple indicators.
        - **Neutral / Transition (Score 45–59) [Amber]**: Mixed signals, consolidation, or conflicting indicator readings.
        - **Bearish / Strong Bearish (Score < 45) [Red]**: Downward momentum, trading below key moving averages, or overbought exhaustion.

        ### Customizing Indicator Weights & Weight Sets
        In the sidebar under **Scoring Balance Weights**:
        - **Sliders**: Tailor the relative importance (multiplier from `0.0` to `2.0`) of individual technical indicators to fit your trading style.
        - **Named Weight Sets**: Save your custom weight profiles, instantly load built-in or saved profiles from the dropdown, or delete unwanted sets. Changes persist automatically.
        """)

st.markdown("### Crypto & Equity Signals Dashboard")
st.caption("Research prototype • Multi-factor technical scoring • Not financial advice")

WATCHLIST_FILE = "watchlists.json"
CONFIG_FILE = "scoring_config.json"
PROFILES_FILE = "weight_profiles.json"

def load_watchlists():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                data = json.load(f)
                return data.get("crypto", {}), data.get("stock", {})
        except Exception:
            pass
    return {
        "bitcoin": "Bitcoin (BTC)",
        "ethereum": "Ethereum (ETH)",
        "solana": "Solana (SOL)",
        "cardano": "Cardano (ADA)",
        "ripple": "XRP",
        "polkadot": "Dot",
        "sui": "Sui",
    }, {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "TSLA": "Tesla",
        "GOOGL": "GOOGL",
    }

def save_watchlists(crypto, stock):
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump({"crypto": crypto, "stock": stock}, f)
    except Exception:
        pass

def load_scoring_weights():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "rsi": 1.0, "stochastic": 1.0, "sma": 1.0, "adx": 1.0, 
        "macd": 1.0, "ichimoku": 1.0, "bb": 1.0, "volume": 1.0, "obv": 1.0, "performance": 1.0
    }

def save_scoring_weights(weights):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(weights, f)
    except Exception:
        pass

def get_builtin_profiles():
    return {
        "📊 Trend Following": {
            "rsi": 0.8, 
            "stochastic": 0.8, 
            "sma": 1.5, 
            "adx": 1.0, 
            "macd": 1.2, 
            "ichimoku": 1.0, 
            "bb": 0.8, 
            "volume":