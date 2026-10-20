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
    with st.popover("❓ Help", use_container_width=True):
        st.markdown("""
        ### What this dashboard does
        It scores a watchlist of cryptos and stocks using technical indicators and shows the results in tables and an interactive chart.  
        **Higher score = more bullish setup** according to the rules below. This is a research tool, not financial advice.

        ### How the score is calculated (0–100)
        Starts at 50 and adjusts based on:
        - **RSI (14)** — oversold (<30) adds points, overbought (>70) subtracts
        - **Stochastic** — similar momentum check
        - **Price vs SMAs** — above SMA 20 / 50 / 200 is bullish, below is bearish
        - **MACD** — above signal line and positive histogram add points
        - **Bollinger Bands** — near the lower band is more bullish, near the upper band is more bearish
        - **Volume** — elevated volume can strengthen the existing direction
        - **ADX / trend strength** — strong trends amplify the current bias
        - **Recent performance** — large 7-day moves have a mild effect

        ### Customizing Indicator Weights & Sets
        In the sidebar under **Scoring Balance Weights**:
        - **Sliders**: Adjust the relative importance of each technical indicator.
        - **Reset to Default**: Instantly snap all weights back to their central position (`1.0`).
        - **Named Weight Sets**: Save your current custom weight configuration under a custom name, instantly load any saved profile from the dropdown, or delete unwanted sets.

        ### Column meanings
        - **Score** — the composite 0–100 number (bar color: green ≥60, amber 45–59, red <45)
        - **Signal** — text label (Strong Bullish → Strong Bearish)
        - **RSI** — Relative Strength Index
        - **7d %** — price change over the last 7 days
        - **ATR %** — Average True Range as a percentage of price (volatility)
        - **Vol** — current volume vs 20-day average
        - **ADX** — trend strength (higher = stronger trend)
        - **Conf** — confluence (bullish reasons minus bearish reasons)

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
    }, {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "TSLA": "Tesla",
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
        "macd": 1.0, "bb": 1.0, "volume": 1.0, "performance": 1.0
    }

def save_scoring_weights(weights):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(weights, f)
    except Exception:
        pass

def load_weight_profiles():
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_weight_profiles(profiles):
    try:
        with open(PROFILES_FILE, "w") as f:
            json.dump(profiles, f)
    except Exception:
        pass

# --- Watchlist setup ---
if "crypto_watchlist" not in st.session_state or "stock_watchlist" not in st.session_state:
    c, s = load_watchlists()
    st.session_state.crypto_watchlist = c
    st.session_state.stock_watchlist = s

st.sidebar.header("Watchlists")

with st.sidebar.expander("Edit Crypto", expanded=False):
    st.caption("Add by CoinGecko-style id (bitcoin, ethereum, solana, cardano, ripple, etc.)")
    new_crypto = st.text_input("Add crypto id", key="new_crypto", placeholder="e.g. dogecoin")
    if st.button("Add Crypto") and new_crypto:
        cid = new_crypto.strip().lower()
        if cid and cid not in st.session_state.crypto_watchlist:
            st.session_state.crypto_watchlist[cid] = cid.replace("-", " ").title()
            save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
            st.rerun()
    if st.session_state.crypto_watchlist:
        to_remove = st.selectbox("Remove crypto", [""] + list(st.session_state.crypto_watchlist.keys()), key="rm_crypto")
        if st.button("Remove Crypto") and to_remove:
            st.session_state.crypto_watchlist.pop(to_remove, None)
            save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
            st.rerun()

with st.sidebar.expander("Edit Stocks", expanded=False):
    st.caption("Add by ticker (AAPL, MSFT, GOOGL, etc.)")
    new_stock = st.text_input("Add stock ticker", key="new_stock", placeholder="e.g. GOOGL")
    if st.button("Add Stock") and new_stock:
        tic = new_stock.strip().upper()
        if tic and tic not in st.session_state.stock_watchlist:
            st.session_state.stock_watchlist[tic] = tic
            save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
            st.rerun()
    if st.session_state.stock_watchlist:
        to_remove = st.selectbox("Remove stock", [""] + list(st.session_state.stock_watchlist.keys()), key="rm_stock")
        if st.button("Remove Stock") and to_remove:
            st.session_state.stock_watchlist.pop(to_remove, None)
            save_watchlists(st.session_state.crypto_watchlist, st.session_state.stock_watchlist)
            st.rerun()

CRYPTO_WATCHLIST = st.session_state.crypto_watchlist
STOCK_WATCHLIST = st.session_state.stock_watchlist

current_weights = load_scoring_weights()
weight_profiles = load_weight_profiles()
indicators = ["rsi", "stochastic", "sma", "adx", "macd", "bb", "volume", "performance"]

# Initialize session state keys for the sliders if not already present
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

    w_rsi = st.slider("RSI Weight", 0.0, 2.0, key="weight_rsi", step=0.1)
    w_stoch = st.slider("Stochastic Weight", 0.0, 2.0, key="weight_stochastic", step=0.1)
    w_sma = st.slider("Moving Averages Weight", 0.0, 2.0, key="weight_sma", step=0.1)
    w_adx = st.slider("ADX Trend Weight", 0.0, 2.0, key="weight_adx", step=0.1)
    w_macd = st.slider("MACD Weight", 0.0, 2.0, key="weight_macd", step=0.1)
    w_bb = st.slider("Bollinger Bands Weight", 0.0, 2.0, key="weight_bb", step=0.1)
    w_vol = st.slider("Volume Weight", 0.0, 2.0, key="weight_volume", step=0.1)
    w_perf = st.slider("Performance Weight", 0.0, 2.0, key="weight_performance", step=0.1)
    
    new_weights = {
        "rsi": w_rsi, "st