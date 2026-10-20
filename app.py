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
        except Exception:
            pass
    return saved

def save_weight_profiles(profiles):
    try:
        with open(PROFILES_FILE, "w") as f:
            json.dump(profiles, f)
    except Exception:
        pass

@st.cache_data(ttl=300)
def load_crypto(coin_id, days):
    return fetch_crypto_data(coin_id, days)

@st.cache_data(ttl=300)
def load_stock(ticker):
    return fetch_stock_data(ticker, period="1y")

# --- Watchlist setup ---
if "crypto_watchlist" not in st.session_state or "stock_watchlist" not in st.session_state:
    c, s = load_watchlists()
    st.session_state.crypto_watchlist = c
    st.session_state.stock_watchlist = s

st.sidebar.header("Watchlists")

with st.sidebar.expander("Edit Crypto", expanded=False):
    st.caption("Add by CoinGecko-style id (bitcoin, ethereum, solana, etc.)")
    new_crypto = st.text_input("Add crypto id", key="new_crypto", placeholder="e.g. dogecoin")
    if st.button("Add Crypto") and new_crypto:
        cid = new_crypto.strip().lower()
        if cid and cid not in st.session_state.crypto_watchlist:
            st.session_state.crypto_watchlist[cid] = cid.replace("-", " ").title()
            save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
            st.rerun()
    if st.session_state.crypto_watchlist:
        to_remove = st.selectbox("Remove crypto", [""] + list(st.session_state.crypto_watchlist.keys()), key="rm_crypto")
        if to_remove:
            if st.button("Remove Crypto"):
                st.session_state.crypto_watchlist.pop(to_remove, None)
                save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
                st.rerun()

with st.sidebar.expander("Edit Stocks", expanded=False):
    st.caption("Add by ticker (AAPL, MSFT, etc.)")
    new_stock = st.text_input("Add stock ticker", key="new_stock", placeholder="e.g. GOOGL")
    if st.button("Add Stock") and new_stock:
        tic = new_stock.strip().upper()
        if tic and tic not in st.session_state.stock_watchlist:
            st.session_state.stock_watchlist[tic] = tic
            save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
            st.rerun()
    if st.session_state.stock_watchlist:
        to_remove = st.selectbox("Remove stock", [""] + list(st.session_state.stock_watchlist.keys()), key="rm_stock")
        if to_remove:
            if st.button("Remove Stock"):
                st.session_state.stock_watchlist.pop(to_remove, None)
                save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
                st.rerun()

CRYPTO_WATCHLIST = st.session_state.crypto_watchlist
STOCK_WATCHLIST = st.session_state.stock_watchlist

current_weights = load_scoring_weights()
built_in_profiles = get_builtin_profiles()
custom_profiles = load_weight_profiles()
all_profiles = {**built_in_profiles, **custom_profiles}

indicators = ["rsi", "stochastic", "sma", "adx", "macd", "ichimoku", "bb", "volume", "obv", "performance"]

for ind in indicators:
    key_name = f"weight_{ind}"
    if key_name not in st.session_state:
        st.session_state[key_name] = float(current_weights.get(ind, 1.0))

if "reset_weights" in st.session_state and st.session_state.reset_weights:
    for ind in indicators:
        st.session_state[f"weight_{ind}"] = 1.0
    current_weights = {ind: 1.0 for ind in indicators}
    save_scoring_weights(current_weights)
    st.session_state.reset_weights = False

# Sidebar Settings
st.sidebar.header("Settings")
days_history = st.sidebar.slider("Days of history", 90, 365, 200)
show_reasons = st.sidebar.checkbox("Show score breakdown", value=True)
show_extra_metrics = st.sidebar.checkbox("Show extra metrics (7d, ATR, volume)", value=True)

st.sidebar.header("Scoring Balance Weights")

with st.sidebar.expander("Customize Indicator Weights", expanded=False):
    st.caption("Adjust relative importance of indicators (saved automatically).")

    st.markdown("**Named Weight Sets**")
    profile_names = ["Select saved set..."] + list(all_profiles.keys())
    selected_profile = st.selectbox("Load Saved Set", profile_names, key="load_profile_sb")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Load Set") and selected_profile != "Select saved set...":
            if selected_profile in all_profiles:
                loaded = all_profiles[selected_profile]
                for ind in indicators:
                    st.session_state[f"weight_{ind}"] = float(loaded.get(ind, 1.0))
                current_weights = loaded
                save_scoring_weights(current_weights)
                st.success(f"Loaded '{selected_profile}'!")
                st.rerun()
    with col_p2:
        if st.button("Delete Set") and selected_profile != "Select saved set...":
            if selected_profile in built_in_profiles:
                st.error("Built-in profiles cannot be deleted!")
            elif selected_profile in custom_profiles:
                custom_profiles.pop(selected_profile)
                save_weight_profiles(custom_profiles)
                st.success(f"Deleted '{selected_profile}'!")
                st.rerun()

    new_profile_name = st.text_input("New set name", placeholder="e.g. Volatility Focus")
    if st.button("Save Current as New Set") and new_profile_name:
        pname = new_profile_name.strip()
        if pname:
            if pname in built_in_profiles:
                st.error("Cannot overwrite built-in profile names!")
            else:
                custom_profiles[pname] = current_weights
                save_weight_profiles(custom_profiles)
                st.success(f"Saved set '{pname}'!")
                st.rerun()

    st.markdown("---")