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

# --- OPTION B: Center-Screen Auth Screen if Logged Out ---
if st.session_state.user is None:
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    
    # Center column container for login card
    _, col_center, _ = st.columns([1, 1.2, 1])
    
    with col_center:
        st.title("📈 angstrom signals")
        st.caption("Multi-factor technical scoring research platform • Please log in to continue")
        
        auth_tab1, auth_tab2 = st.tabs(["🔑 Log In", "📝 Sign Up"])
        
        with auth_tab1:
            st.markdown("### Welcome Back")
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("Log In", type="primary", use_container_width=True):
                try:
                    response = supabase.auth.sign_in_with_password({
                        "email": login_email, 
                        "password": login_password
                    })
                    st.session_state.user = response.user
                    st.success("Logged in successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
                    
        with auth_tab2:
            st.markdown("### Create New Account")
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("Create Account", type="primary", use_container_width=True):
                try:
                    response = supabase.auth.sign_up({
                        "email": signup_email, 
                        "password": signup_password
                    })
                    st.success("Account created! Check your email to confirm if required, or try logging in.")
                except Exception as e:
                    st.error(f"Sign up failed: {e}")
                    
    # Halt execution here so dashboard elements don't render behind the login screen
    st.stop()


# =========================================================================
# LOGGED-IN DASHBOARD VIEW (Everything below only runs when authenticated)
# =========================================================================

# Sidebar Account Management & Logout
st.sidebar.header("Account")
st.sidebar.success(f"Logged in as:\n**{st.session_state.user.email}**")
if st.sidebar.button("Log Out", use_container_width=True):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("---")

# Main Title Header
st.title("angstrom signals - level 1")

# Full, comprehensive guide placed at the top of the main screen with plenty of reading space
with st.expander("📖 Comprehensive Platform Guide & Help Manual", expanded=False):
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
            "rsi": 0.8, "stochastic": 0.8, "sma": 1.5, "adx": 1.0, 
            "macd": 1.2, "ichimoku": 1.0, "bb": 0.8, "volume": 1.0, 
            "obv": 1.0, "performance": 1.2
        },
        "📉 Mean Reversion": {
            "rsi": 1.5, "stochastic": 1.2, "sma": 0.8, "adx": 1.0, 
            "macd": 0.8, "ichimoku": 1.0, "bb": 1.5, "volume": 0.8, 
            "obv": 0.8, "performance": 0.8
        },
        "🚀 Momentum Heavy": {
            "rsi": 1.0, "stochastic": 1.2, "sma": 1.0, "adx": 1.0, 
            "macd": 1.5, "ichimoku": 1.0, "bb": 1.0, "volume": 1.2, 
            "obv": 1.2, "performance": 1.5
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
        "rsi": w_rsi, "stochastic": w_stoch, "sma": w_sma, "adx": w_adx,
        "macd": w_macd, "ichimoku": w_ichi, "bb": w_bb, "volume": w_vol,
        "obv": w_obv, "performance": w_perf
    }
    
    if new_weights != current_weights:
        save_scoring_weights(new_weights)
        current_weights = new_weights

    if st.button("🔄 Reset to Default (1.0)"):
        st.session_state.reset_weights = True
        st.rerun()

    st.markdown("---")
    with st.expander("💡 Scoring Weights Guide", expanded=False):
        st.markdown("""
        - **Indicator Sliders**: Adjust how heavily each technical indicator influences the final 0–100 score (from `0.0` to `2.0`). Setting a weight to `0.0` completely disables that indicator.
        - **Reset to Default**: Instantly snaps all indicator weights back to their central balanced baseline (`1.0`).
        - **Named Weight Sets**: 
          - *Save Current as New Set*: Store your custom configuration under a custom name (e.g., "Volatility Focus").
          - *Load Saved Set*: Instantly switch between built-in profiles (Trend Following, Mean Reversion, Momentum Heavy) or your own custom saved sets.
          - *Delete Set*: Clean up and remove any unwanted custom profiles.
        """)


def render_dashboard(crypto_watchlist, stock_watchlist, history_days, weights, show_reasons_flag, show_extra_metrics_flag):
    def process_watchlist(watchlist, is_crypto=True):
        results = []
        for key, name in watchlist.items():
            with st.spinner(f"Loading {name}..."):
                if is_crypto:
                    df = load_crypto(key, history_days)
                else:
                    df = load_stock(key)
                
                result = {
                    "symbol": name if is_crypto else f"{name} ({key})",
                    "score": None, "label": "No data", "reasons": [],
                    "latest_price": None, "rsi": None, "change_7d": None,
                    "change_30d": None, "atr_pct": None, "volume_ratio": None,
                    "bb_position": None, "adx": None, "confluence": None,
                    "contributions": {}, "type": "Crypto" if is_crypto else "Stock",
                    "key": key,
                }

                if not df.empty and len(df) >= 15:
                    try:
                        df = calculate_indicators(df)
                        res = compute_score(df, weights=weights)
                        if isinstance(res, dict):
                            result.update(res)
                            result["symbol"] = name if is_crypto else f"{name} ({key})"
                            result["type"] = "Crypto" if is_crypto else "Stock"
                            result["key"] = key
                    except Exception:
                        pass
                
                results.append(result)
        return results

    crypto_results = process_watchlist(crypto_watchlist, is_crypto=True)
    stock_results = process_watchlist(stock_watchlist, is_crypto=False)

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

    def render_snapshot_card(title, name, score):
        if score is None or pd.isna(score):
            color, bg, arrow = "#6b7280", "#f3f4f6", "—"
        elif score >= 60:
            color, bg, arrow = "#15803d", "#dcfce7", "↑"
        elif score >= 45:
            color, bg, arrow = "#b45309", "#fef3c7", "→"
        else:
            color, bg, arrow = "#b91c1c", "#fee2e2", "↓"
            
        score_str = f"{score:.1f}/100" if score is not None else "—"
        return f"<div style='background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e5e7eb;'><div style='font-size: 0.8rem; color: #6b7280; margin-bottom: 4px;'>{title}</div><div style='font-size: 1.1rem; font-weight: 600; color: #111827; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{name}</div><div style='display: inline-flex; align-items: center; gap: 4px; background: {bg}; color: {color}; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 600;'>{arrow} {score_str}</div></div>"

    with c1:
        st.markdown(render_snapshot_card("Top Crypto", crypto_top["symbol"] if crypto_top else "—", crypto_top["score"] if crypto_top else None), unsafe_allow_html=True)
    with c2:
        st.markdown(render_snapshot_card("Weakest Crypto", crypto_bot["symbol"] if crypto_bot else "—", crypto_bot["score"] if crypto_bot else None), unsafe_allow_html=True)
    with c3:
        st.markdown(render_snapshot_card("Top Stock", stock_top["symbol"] if stock_top else "—", stock_top["score"] if stock_top else None), unsafe_allow_html=True)
    with c4:
        st.markdown(render_snapshot_card("Weakest Stock", stock_bot["symbol"] if stock_bot else "—", stock_bot["score"] if stock_bot else None), unsafe_allow_html=True)

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

        if show_extra_metrics_flag:
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

            if show_extra_metrics_flag:
                chg = row.get("change_7d")
                atr = row.get("atr_pct")
                vol = row.get("volume_ratio")
                chg_str = f"{chg:+.1f}%" if pd.notna(chg) else "—"
                atr_str = f"{atr:.2f}" if pd.notna(atr) else "—"
                vol_str = f"{vol:.2f}" if pd.notna(vol) else "—"

                rows_html += f'<tr style="border-bottom: 1px solid #f0f0f0;"><td style="padding: 10px; white-space: nowrap; font-weight: 500;">{symbol}</td><td style="padding: 10px; min-width: 130px;">{score_bar_markup}</td><td style="padding: 10px; white-space: nowrap;">{signal_label}</td><td style="padding: 10px; white-space: nowrap;">{price_str}</td><td style="padding: 10px; white-space: nowrap;">{rsi_str}</td><td style="padding: 10px; white-space: nowrap;">{chg_str}</td><td style="padding: 10px; white-space: nowrap;">{atr_str}</td><td style="padding: 10px; white-space: nowrap;">{vol_str}</td></tr>'
            else:
                rows_html += f'<tr style="border-bottom: 1px solid #f0f0f0;"><td style="padding: 10px; white-space: nowrap; font-weight: 500;">{symbol}</td><td style="padding: 10px; min-width: 130px;">{score_bar_markup}</td><td style="padding: 10px; white-space: nowrap;">{signal_label}</td><td style="padding: 10px; white-space: nowrap;">{price_str}</td><td style="padding: 10px; white-space: nowrap;">{rsi_str}</td></tr>'

        complete_table_html = f'<div style="width: 100%; overflow-x: auto; margin-bottom: 20px;"><table style="width: 100%; border-collapse: collapse; font-size: 0.95rem;"><thead><tr style="border-bottom: 2px solid #e5e7eb;">{header_html}</tr></thead><tbody>{rows_html}</tbody></table></div>'
        st.html(complete_table_html)

    style_and_show_table(crypto_results, "Crypto Scores")
    style_and_show_table(stock_results, "Equity Scores")

    st.subheader("Interactive Chart")

    col1, col2 = st.columns([1, 3])
    with col1:
        asset_type = st.selectbox("Type", ["Crypto", "Stock"], key="asset_type")
    with col2:
        if asset_type == "Crypto":
            options = list(crypto_watchlist.keys())
            asset_key = st.selectbox(
                "Asset", options,
                format_func=lambda x: crypto_watchlist[x],
                key="asset_crypto",
            )
            df_chart = load_crypto(asset_key, history_days)
            title = crypto_watchlist[asset_key]
        else:
            options = list(stock_watchlist.keys())
            asset_key = st.selectbox(
                "Asset", options,
                format_func=lambda x: f"{stock_watchlist[x]} ({x})",
                key="asset_stock",
            )
            df_chart = load_stock(asset_key)
            title = f"{stock_watchlist[asset_key]} ({asset_key})"

    if not df_chart.empty:
        df_chart = calculate_indicators(df_chart)

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.55, 0.2, 0.25],
            subplot_titles=(f"{title} Price", "Volume", "RSI (14)"),
        )

        fig.add_trace(
            go.Candlestick(
                x=df_chart.index, open=df_chart["open"], high=df_chart["high"],
                low=df_chart["low"], close=df_chart["close"], name="Price",
            ),
            row=1, col=1,
        )

        if "sma_20" in df_chart.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_chart.index, y=df_chart["sma_20"], name="SMA 20",
                    line=dict(color="orange", width=1.5)
                ),
                row=1, col=1,
            )
        if "sma_50" in df_chart.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_chart.index, y=df_chart["sma_50"], name="SMA 50",
                    line=dict(color="royalblue", width=1.5)
                ),
                row=1, col=1,
            )

        if "BBU_20_2.0" in df_chart.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_chart.index, y=df_chart["BBU_20_2.0"], name="BB Upper",
                    line=dict(color="gray", width=1, dash="dot"), showlegend=False
                ),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df_chart.index, y=df_chart["BBL_20_2.0"], name="BB Lower",
                    line=dict(color="gray", width=1, dash="dot"), fill="tonexty",
                    fillcolor="rgba(128,128,128,0.08)", showlegend=False
                ),
                row=1, col=1,
            )

        colors = ["green" if df_chart["close"].iloc[i] >= df_chart["open"].iloc[i] else "red"
                  for i in range(len(df_chart))]
        fig.add_trace(
            go.Bar(x=df_chart.index, y=df_chart["volume"], name="Volume", marker_color=colors, opacity=0.6),
            row=2, col=1,
        )

        if "rsi" in df_chart.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_chart.index, y=df_chart["rsi"], name="RSI",
                    line=dict(color="purple", width=1.5)
                ),
                row=3, col=1,
            )
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
            fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.3, row=3, col=1)

        fig.update_layout(
            height=750,
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60, b=20),
        )
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)

        st.plotly_chart(fig, width="stretch")

        result = compute_score(df_chart, weights=weights)
        col_a, col_b, col_c = st.columns(3)
        
        score_val = result['score']
        if score_val >= 60:
            score_color = "green"
            arrow = "↑"
        elif score_val >= 45:
            score_color = "orange"
            arrow = "→"
        else:
            score_color = "red"
            arrow = "↓"

        with col_a:
            score_card_html = f"<div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 2px;'>Current Score</div><div style='font-size: 2.2rem; font-weight: 600; line-height: 1.1; margin-bottom: 4px;'>{score_val}/100</div><div style='font-size: 0.95rem; font-weight: 500; color: {score_color};'>{arrow} {result['label']}</div>"
            st.markdown(score_card_html, unsafe_allow_html=True)

        if result.get("change_7d") is not None:
            col_b.metric("7-Day Change", f"{result['change_7d']:+.1f}%")
        if result.get("atr_pct") is not None:
            col_c.metric("Volatility (ATR%)", f"{result['atr_pct']:.2f}%")

        if show_reasons_flag and result.get("reasons") and result.get("score") is not None:
            st.subheader(f"Score Breakdown — {title}")
            color = "green" if result["score"] >= 60 else "orange" if result["score"] >= 45 else "red"
            st.markdown(
                f"<span style='color:{color};font-weight:bold;font-size:1.1em'>{result['score']}/100 ({result['label']})</span>",
                unsafe_allow_html=True,
            )

            breakdown_col1, breakdown_col2 = st.columns(2)

            with breakdown_col1:
                contributions = result.get("contributions", {})
                if contributions:
                    indicators_list = list(contributions.keys())
                    points_list = list(contributions.values())
                    bar_colors = ['#22c55e' if p >= 0 else '#ef4444' for p in points_list]

                    fig_contrib = go.Figure(go.Bar(
                        x=points_list, y=indicators_list,
                        orientation='h', marker_color=bar_colors
                    ))
                    fig_contrib.update_layout(
                        title="Indicator Point Contributions",
                        xaxis_title="Points Added/Subtracted",
                        yaxis=dict(autorange="reversed"),
                        height=280,
                        margin=dict(t=30, b=20, l=10, r=10)
                    )
                    fig_contrib.add_vline(x=0, line_width=1.5, line_dash="dash", line_color="gray", opacity=0.7)
                    st.plotly_chart(fig_contrib, width="stretch")

            with breakdown_col2:
                st.markdown("**Detailed Reasons**")
                for reason in result["reasons"]:
                    st.caption(f"• {reason}")

    else:
        st.warning("Could not load chart data. Check your internet connection.")

render_dashboard(CRYPTO_WATCHLIST, STOCK_WATCHLIST, days_history, current_weights, show_reasons, show_extra_metrics)

st.sidebar.markdown("---")
st.sidebar.info("Dashboard and data auto-refresh every 5 minutes.")
st.sidebar.caption("Watchlists are saved and survive page refreshes.")