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
    # Add some vertical spacing to align the popover nicely with the title
    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
    # Help popover
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
        4. Edit your watchlists from the sidebar (changes are saved).

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
    # Defaults
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
        "rsi": 1.0, 
        "stochastic": 1.0, 
        "sma": 1.0, 
        "adx": 1.0, 
        "macd": 1.0, 
        "bb": 1.0, 
        "volume": 1.0, 
        "performance": 1.0
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

# --- Watchlist (persisted to file) ---
if "crypto_watchlist" not in st.session_state or "stock_watchlist" not in st.session_state:
    c, s = load_watchlists()
    st.session_state.crypto_watchlist = c
    st.session_state.stock_watchlist = s

# Sidebar watchlist editor
st.sidebar.header("Watchlists")

with st.sidebar.expander("Edit Crypto", expanded=False):
    st.caption("Add by CoinGecko-style id (bitcoin, ethereum, solana, cardano, ripple, dogecoin, etc.)")
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
    st.caption("Add by ticker (AAPL, MSFT, GOOGL, AMZN, etc.)")
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

# Use the session-state watchlists
CRYPTO_WATCHLIST = st.session_state.crypto_watchlist
STOCK_WATCHLIST = st.session_state.stock_watchlist

# Load scoring weights and profiles
current_weights = load_scoring_weights()
weight_profiles = load_weight_profiles()

# Handle reset trigger in session state if requested
if "reset_weights" in st.session_state and st.session_state.reset_weights:
    current_weights = {
        "rsi": 1.0, "stochastic": 1.0, "sma": 1.0, "adx": 1.0, 
        "macd": 1.0, "bb": 1.0, "volume": 1.0, "performance": 1.0
    }
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

    # Sliders for individual indicator weights at the top
    w_rsi = st.slider("RSI Weight", 0.0, 2.0, float(current_weights.get("rsi", 1.0)), 0.1)
    w_stoch = st.slider("Stochastic Weight", 0.0, 2.0, float(current_weights.get("stochastic", 1.0)), 0.1)
    w_sma = st.slider("Moving Averages Weight", 0.0, 2.0, float(current_weights.get("sma", 1.0)), 0.1)
    w_adx = st.slider("ADX Trend Weight", 0.0, 2.0, float(current_weights.get("adx", 1.0)), 0.1)
    w_macd = st.slider("MACD Weight", 0.0, 2.0, float(current_weights.get("macd", 1.0)), 0.1)
    w_bb = st.slider("Bollinger Bands Weight", 0.0, 2.0, float(current_weights.get("bb", 1.0)), 0.1)
    w_vol = st.slider("Volume Weight", 0.0, 2.0, float(current_weights.get("volume", 1.0)), 0.1)
    w_perf = st.slider("Performance Weight", 0.0, 2.0, float(current_weights.get("performance", 1.0)), 0.1)
    
    new_weights = {
        "rsi": w_rsi, "stochastic": w_stoch, "sma": w_sma, "adx": w_adx,
        "macd": w_macd, "bb": w_bb, "volume": w_vol, "performance": w_perf
    }
    
    if new_weights != current_weights:
        save_scoring_weights(new_weights)
        current_weights = new_weights

    # Reset to Default Button
    if st.button("🔄 Reset to Default (1.0)"):
        st.session_state.reset_weights = True
        st.rerun()

    st.markdown("---")

    # --- Named Weight Sets Manager at the bottom ---
    st.markdown("**Named Weight Sets**")
    
    # Load profile selection if present
    profile_names = ["Select saved set..."] + list(weight_profiles.keys())
    selected_profile = st.selectbox("Load Saved Set", profile_names, key="load_profile_sb")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Load Set") and selected_profile != "Select saved set...":
            if selected_profile in weight_profiles:
                current_weights = weight_profiles[selected_profile]
                save_scoring_weights(current_weights)
                st.success(f"Loaded '{selected_profile}'!")
                st.rerun()
    with col_p2:
        if st.button("Delete Set") and selected_profile != "Select saved set...":
            if selected_profile in weight_profiles:
                weight_profiles.pop(selected_profile)
                save_weight_profiles(weight_profiles)
                st.success(f"Deleted '{selected_profile}'!")
                st.rerun()

    new_profile_name = st.text_input("New set name", placeholder="e.g. Trend Heavy")
    if st.button("Save Current as New Set") and new_profile_name:
        pname = new_profile_name.strip()
        if pname:
            weight_profiles[pname] = current_weights
            save_weight_profiles(weight_profiles)
            st.success(f"Saved set '{pname}'!")
            st.rerun()

# Caching — data refreshes every 5 minutes
@st.cache_data(ttl=300)
def load_crypto(coin_id, days):
    return fetch_crypto_data(coin_id, days)

@st.cache_data(ttl=300)
def load_stock(ticker):
    return fetch_stock_data(ticker, period="1y")

# Auto-refresh the dashboard every 5 minutes
@st.fragment(run_every=300)
def live_dashboard():
    # --- Load & score data ---
    def process_watchlist(watchlist, is_crypto=True):
        results = []
        for key, name in watchlist.items():
            with st.spinner(f"Loading {name}..."):
                if is_crypto:
                    df = load_crypto(key, days_history)
                else:
                    df = load_stock(key)
                if not df.empty:
                    df = calculate_indicators(df)
                    result = compute_score(df, weights=current_weights)
                    result["symbol"] = name if is_crypto else f"{name} ({key})"
                    result["type"] = "Crypto" if is_crypto else "Stock"
                    result["key"] = key
                    results.append(result)
                else:
                    results.append({
                        "symbol": name if is_crypto else f"{name} ({key})",
                        "score": None,
                        "label": "No data",
                        "reasons": [],
                        "latest_price": None,
                        "rsi": None,
                        "change_7d": None,
                        "change_30d": None,
                        "atr_pct": None,
                        "volume_ratio": None,
                        "bb_position": None,
                        "adx": None,
                        "confluence": None,
                        "type": "Crypto" if is_crypto else "Stock",
                        "key": key,
                    })
        return results

    crypto_results = process_watchlist(CRYPTO_WATCHLIST, is_crypto=True)
    stock_results = process_watchlist(STOCK_WATCHLIST, is_crypto=False)

    # --- Summary metrics ---
    def get_top_bottom(results):
        valid = [r for r in results if r.get("score") is not None]
        if not valid:
            return None, None
        sorted_r = sorted(valid, key=lambda x: x["score"], reverse=True)
        return sorted_r[0], sorted_r[-1]

    crypto_top, crypto_bot = get_top_bottom(crypto_results)
    stock_top, stock_bot = get_top_bottom(stock_results)

    st.subheader("Quick Snapshot")
    c1, c2, c3, c4 = st.columns(4)
    if crypto_top:
        c1.metric("Top Crypto", crypto_top["symbol"], f"{crypto_top['score']}/100")
    if crypto_bot:
        c2.metric("Weakest Crypto", crypto_bot["symbol"], f"{crypto_bot['score']}/100")
    if stock_top:
        c3.metric("Top Stock", stock_top["symbol"], f"{stock_top['score']}/100")
    if stock_bot:
        c4.metric("Weakest Stock", stock_bot["symbol"], f"{stock_bot['score']}/100")

    # --- Responsive HTML Tables with Color-Coded Score Bars ---
    def score_bar_color(score):
        if score is None or pd.isna(score):
            return "#6b7280"
        if score >= 60:
            return "#22c55e"  # green
        if score >= 45:
            return "#f59e0b"  # amber
        return "#ef4444"      # red

    def render_score_bar(score):
        """HTML colored progress bar."""
        if score is None or pd.isna