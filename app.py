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
from supabase import create_client, Client

# Page config
st.set_page_config(
    page_title="angstrom signals - level 1",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Supabase client using Streamlit Secrets
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# Manage user session state
if "user" not in st.session_state:
    st.session_state.user = None

# Custom CSS for popover text wrapping
st.markdown("""
<style>
/* Force text wrapping inside all Streamlit popovers and expanders */
[data-testid="stPopoverBody"] {
    max-width: 450px !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
}
[data-testid="stPopoverBody"] p, 
[data-testid="stPopoverBody"] li,
[data-testid="stPopoverBody"] span {
    word-break: normal !important;
    overflow-wrap: break-word !important;
}
</style>
""", unsafe_allow_html=True)

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

        ### Column meanings
        - **Score** — the composite 0–100 number (bar color: green ≥60, amber 45–59, red <45)
        - **Signal** — text label (Strong Bullish → Strong Bearish)
        - **RSI** — Relative Strength Index
        - **7d %** — price change over the last 7 days
        - **ATR %** — Average True Range as a percentage of price (volatility)
        - **Vol** — current volume vs 20-day average

        ### How to use it
        1. Check the tables for the highest/lowest scores.
        2. Use the **Type** and **Asset** dropdowns under the chart to inspect any symbol.
        3. Read the **Score Breakdown** to see exactly why the score is what it is.
        4. Edit your watchlists or indicator weights from the sidebar (changes are saved).

        Data refreshes automatically every 5 minutes.
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
            "volume": 1.0, 
            "obv": 1.0, 
            "performance": 1.2
        },
        "📉 Mean Reversion": {
            "rsi": 1.5, 
            "stochastic": 1.2, 
            "sma": 0.8, 
            "adx": 1.0, 
            "macd": 0.8, 
            "ichimoku": 1.0, 
            "bb": 1.5, 
            "volume": 0.8, 
            "obv": 0.8, 
            "performance": 0.8
        },
        "🚀 Momentum Heavy": {
            "rsi": 1.0, 
            "stochastic": 1.2, 
            "sma": 1.0, 
            "adx": 1.0, 
            "macd": 1.5, 
            "ichimoku": 1.0, 
            "bb": 1.0, 
            "volume": 1.2, 
            "obv": 1.2, 
            "performance": 1.5
        }
    }

def load_weight_profiles():
    saved = {}
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r") as f:
                saved = json.load(f)
        except