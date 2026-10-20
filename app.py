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
        It scores a watchlist of cryptos and stocks using technical indicators and shows the results in tables and an interactive chart.  
        **Higher score = more bullish setup** according to the rules below. This is a research tool, not financial advice.

        ### How the score is calculated (0–100)
        Starts at 50 and adjusts based on:
        - **RSI (14)** — oversold (<40) adds points, overbought (>60) subtracts
        - **Price vs SMAs** — above SMA 20 / 50 is bullish, below is neutral/bearish
        - **MACD Momentum** — bullish crossover adds points
        - **Bollinger Bands** — near the lower band adds support points, near the upper band subtracts resistance points
        - **Performance** — recent 7-day momentum moves adjust the score

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
        except Exception:
            pass
    return saved

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
        if st.button("Remove Crypto") and to_remove:
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
        if st.button("Remove Stock") and to_remove:
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
    
    # Restored Help Text
    st.markdown("""
    - **Sliders**: Adjust the relative importance of each technical indicator.
    - **Reset to Default**: Instantly snap all weights back to their central position (`1.0`).
    - **Named Weight Sets**: Save your current custom weight configuration under a custom name, instantly load any saved profile from the dropdown, or delete unwanted sets.
    """)
    st.markdown("---")

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

    w_rsi = st.slider("RSI Weight", 0.0, 2.0, key="weight_rsi", step=0.1)
    w_stoch = st.slider("Stochastic Weight", 0.0, 2.0, key="weight_stochastic", step=0.1)
    w_sma = st.slider("Moving Averages Weight", 0.0, 2.0, key="weight_sma", step=0.1)
    w_adx = st.slider("ADX Trend Weight", 0.0, 2.0, key="weight_adx", step=0.1)
    w_macd = st.slider("MACD & Hist Weight", 0.0, 2.0, key="weight_macd", step=0.1)
    w_ichi = st.slider("Ichimoku Cloud Weight", 0.0, 2.0, key="weight_ichimoku", step=0.1)
    w_bb = st.slider("Bollinger Bands Weight", 0.0, 2.0, key="weight_bb", step=0.1)
    w_vol = st.slider("Volume Weight", 0.0, 2.0, key="weight_volume", step=0.1)
    w_obv = st.slider("OBV Weight", 0.0, 2.0, key="weight_obv", step=0.1)
    w_perf = st.slider("Performance Weight", 0.0, 2.0, key="weight_performance", step=0.1)
    
    new_weights = {
        "rsi": w_rsi,
        "stochastic": w_stoch,
        "sma": w_sma,
        "adx": w_adx,
        "macd": w_macd,
        "ichimoku": w_ichi,
        "bb": w_bb,
        "volume": w_vol,
        "obv": w_obv,
        "performance": w_perf
    }
    
    if new_weights != current_weights:
        save_scoring_weights(new_weights)
        current_weights = new_weights

    if st.button("🔄 Reset to Default (1.0)"):
        st.session_state.reset_weights = True
        st.rerun()

@st.cache_data(ttl=300)
def load_crypto(coin_id, days):
    return fetch_crypto_data(coin_id, days)


@st.cache_data(ttl=300)
def load_stock(ticker):
    return fetch_stock_data(ticker, period="1y")


@st.fragment(run_every=300)
def live_dashboard():
    def process_watchlist(watchlist, is_crypto=True):
        results = []
        for key, name in watchlist.items():
            with st.spinner(f"Loading {name}..."):
                if is_crypto:
                    df = load_crypto(key, days_history)
                else:
                    df = load_stock(key)
                
                result = {
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
                    "contributions": {},
                    "type": "Crypto" if is_crypto else "Stock",
                    "key": key,
                }

                if not df.empty and len(df) >= 15:
                    try:
                        df = calculate_indicators(df)
                        res = compute_score(df, weights=current_weights)
                        if isinstance(res, dict):
                            result.update(res)
                            result["symbol"] = name if is_crypto else f"{name} ({key})"
                            result["type"] = "Crypto" if is_crypto else "Stock"
                            result["key"] = key
                    except Exception:
                        pass
                
                results.append(result)
        return results

    crypto_results = process_watchlist(CRYPTO_WATCHLIST, is_crypto=True)
    stock_results = process_watchlist(STOCK_WATCHLIST, is_crypto=False)

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

    def score_bar_color(score):
        if score is None or pd.isna(score):
            return "#6b7280"
        if score >= 60:
            return "#22c55e"
        if score >= 45:
            return "#f59e0b"
        return "#ef4444"

    def render_score_bar(score):
        if score is None or pd.isna(score):
            pct = 0
            color = "#6b7280"
            label = "—"
        else:
            pct = max(0, min(100, float(score)))
            color = score_bar_color(score)
            label = f"{int(score)}"
        return f'''<div style="display:flex;align-items:center;gap:8px;width:100%;min-width:100px;"><div style="flex:1;background:#e5e7eb;border-radius:6px;height:14px;overflow:hidden;"><div style="width:{pct}%;background:{color};height:100%;border-radius:6px;"></div></div><span style="min-width:28px;font-weight:600;font-size:0.9em;">{label}</span></div>'''

    def style_and_show_table(results, title):
        if not results:
            return
        df = pd.DataFrame(results)
        df = df.sort_values("score", ascending=False, na_position="last")

        st.subheader(title)

        if show_extra_metrics:
            headers = ["Asset", "Score", "Signal", "Price", "RSI", "7d %", "ATR %", "Vol"]
        else:
            headers = ["Asset", "Score", "Signal", "Price", "RSI"]

        header_html = "".join([f"<th style='padding: 8px 10px; text-align: left; white-space: nowrap;'>{h}</th>" for h in headers])
        
        rows_html = ""
        for _, row in df.iterrows():
            symbol = row["symbol"]
            score_bar_markup = render_score_bar(row["score"])
            signal_label = row.get("label") or "—"
            
            price = row.get("latest_price")
            price_str = f"${price:,.2f}" if pd.notna(price) else "—"
            
            rsi = row.get("rsi")
            rsi_str = f"{rsi:.1f}" if pd.notna(rsi) else "—"

            if show_extra_metrics:
                chg = row.get("change_7d")
                atr = row.get("atr_pct")
                vol = row.get("volume_ratio")
                chg_str = f"{chg:+.1f}%" if pd.notna(chg) else "—"
                atr_str = f"{atr:.2f}" if pd.notna(atr) else "—"
                vol_str = f"{vol:.2f}" if pd.notna(vol) else "—"

                rows_html += f'<tr style="border-bottom: 1px solid #f0f0f0;"><td style="padding: 10px; white-space: nowrap; font-weight: 500;">{symbol}</td><td style="padding: 10px; min-width: 130px;">{score_bar_markup}</td><td style="padding: 10px; white-space: nowrap;">{signal_label}</td><td style="padding: 10px; white-space: nowrap;">{price_str}</td><td style="padding: 10px; white-space: nowrap;">{rsi_str}</td><td style="padding: 10px; white-space: nowrap;">{chg_str}</td><td style="padding: 10px; white-space: nowrap;">{atr_str}</td><td style="padding: 10px; white-space: nowrap;">{vol_str}</td></tr>'
            else:
                rows_html += f'<tr style="border-bottom: 1px solid #f0f0f0;"><td style="padding: 10px; white-space: nowrap; font-weight: 500;">{symbol}</td><td style="padding: 10px; min-width: 130px;">{score_bar_markup}</td><td style="padding: 10px; white-space: nowrap;">{signal_label}</td><td style="padding: 10px; white-space: nowrap;">{price_str}</td><td style="padding: 10px; white-space: nowrap;">{rsi_str}</td></tr>'

        complete_table_html = f'<div style="width: 100%; overflow-x: auto; margin-bottom: 20px;"><table style="width: 100%; border-collapse: collapse; font-size: 0.95rem;"><thead><tr style="border-bottom: 2px solid