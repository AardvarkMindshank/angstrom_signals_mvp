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

# --- Center-Screen Auth Screen if Logged Out ---
if st.session_state.user is None:
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    
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
                    
    st.stop()


# =========================================================================
# CLOUD PREFERENCES & NOTIFICATIONS SYNC FUNCTIONS (Per-User Isolation)
# =========================================================================

user_id = st.session_state.user.id

def load_user_preferences():
    default_crypto = {
        "bitcoin": "Bitcoin (BTC)",
        "ethereum": "Ethereum (ETH)",
        "solana": "Solana (SOL)",
        "cardano": "Cardano (ADA)",
        "ripple": "XRP",
        "polkadot": "Dot",
        "sui": "Sui",
    }
    default_stock = {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "TSLA": "Tesla",
        "GOOGL": "GOOGL",
    }
    default_weights = {
        "rsi": 1.0, "stochastic": 1.0, "sma": 1.0, "adx": 1.0, 
        "macd": 1.0, "ichimoku": 1.0, "bb": 1.0, "volume": 1.0, "obv": 1.0, "performance": 1.0
    }
    default_settings = {
        "days_history": 200,
        "show_reasons": True,
        "show_extra_metrics": True
    }

    try:
        response = supabase.table("user_preferences").select("*").eq("user_id", user_id).execute()
        data = response.data
        
        if data and len(data) > 0:
            row = data[0]
            prefs_dict = {
                "crypto": row.get("crypto_watchlist") or default_crypto,
                "stock": row.get("stock_watchlist") or default_stock,
                "weights": row.get("scoring_weights") or default_weights,
                "profiles": row.get("weight_profiles") or {},
                "settings": row.get("settings") or default_settings
            }
        else:
            initial_row = {
                "user_id": user_id,
                "crypto_watchlist": default_crypto,
                "stock_watchlist": default_stock,
                "scoring_weights": default_weights,
                "weight_profiles": {},
                "settings": default_settings
            }
            supabase.table("user_preferences").insert(initial_row).execute()
            prefs_dict = {
                "crypto": default_crypto,
                "stock": default_stock,
                "weights": default_weights,
                "profiles": {},
                "settings": default_settings
            }
            
        # Also fetch alert preferences
        alert_res = supabase.table("alert_preferences").select("*").eq("user_id", user_id).execute()
        if alert_res.data and len(alert_res.data) > 0:
            prefs_dict["alerts"] = alert_res.data[0]
        else:
            default_alerts = {"user_id": user_id, "enabled": True, "min_score_alert": 70, "max_score_alert": 30}
            supabase.table("alert_preferences").insert(default_alerts).execute()
            prefs_dict["alerts"] = default_alerts

        return prefs_dict

    except Exception as e:
        st.error(f"Error loading cloud preferences: {e}")
        return {
            "crypto": default_crypto, "stock": default_stock, 
            "weights": default_weights, "profiles": {}, "settings": default_settings,
            "alerts": {"enabled": True, "min_score_alert": 70, "max_score_alert": 30}
        }

def save_preferences_to_cloud(updates: dict):
    try:
        supabase.table("user_preferences").update(updates).eq("user_id", user_id).execute()
    except Exception as e:
        st.error(f"Error saving preferences to cloud: {e}")

def save_alert_preferences_to_cloud(updates: dict):
    try:
        supabase.table("alert_preferences").update(updates).eq("user_id", user_id).execute()
    except Exception as e:
        st.error(f"Error saving alert preferences: {e}")

def fetch_user_notifications():
    try:
        res = supabase.table("user_notifications").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(10).execute()
        return res.data or []
    except Exception:
        return []


# Load user data into session state
if "cloud_prefs" not in st.session_state:
    st.session_state.cloud_prefs = load_user_preferences()

prefs = st.session_state.cloud_prefs
alert_prefs = prefs.get("alerts", {})

# =========================================================================
# LOGGED-IN DASHBOARD VIEW
# =========================================================================

st.sidebar.header("Account")
st.sidebar.success(f"Logged in as:\n**{st.session_state.user.email}**")
if st.sidebar.button("Log Out", use_container_width=True):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.session_state.pop("cloud_prefs", None)
    st.rerun()

st.sidebar.markdown("---")

# --- NOTIFICATIONS SIDEBAR SECTION ---
st.sidebar.header("🔔 Notifications")
notifications_list = fetch_user_notifications()
unread_count = sum(1 for n in notifications_list if not n.get("is_read", False))

with st.sidebar.expander(f"Alert Feed {f'({unread_count} new)' if unread_count > 0 else ''}", expanded=False):
    if not notifications_list:
        st.caption("No alerts yet. When your watchlisted assets cross your thresholds, they'll show up here.")
    else:
        if st.button("Mark all as read", key="mark_read_btn"):
            try:
                supabase.table("user_notifications").update({"is_read": True}).eq("user_id", user_id).execute()
                st.rerun()
            except Exception:
                pass
        
        for notif in notifications_list:
            badge = "🔴" if not notif.get("is_read") else "⚪"
            st.markdown(f"**{badge} {notif['asset_name']}**")
            st.caption(f"{notif['message']}\n\n*{notif['created_at'][:16].replace('T', ' ')}*")
            st.markdown("---")

with st.sidebar.expander("Configure Alert Rules", expanded=False):
    alert_enabled = st.checkbox("Enable Alerts", value=alert_prefs.get("enabled", True), key="alert_enabled_cb")
    min_score = st.slider("Bullish Alert Threshold (Score ≥)", 50, 95, int(alert_prefs.get("min_score_alert", 70)), key="min_score_slider")
    max_score = st.slider("Bearish Alert Threshold (Score ≤)", 5, 50, int(alert_prefs.get("max_score_alert", 30)), key="max_score_slider")
    
    new_alert_settings = {
        "enabled": alert_enabled,
        "min_score_alert": min_score,
        "max_score_alert": max_score
    }
    if new_alert_settings != {k: alert_prefs.get(k) for k in new_alert_settings}:
        alert_prefs.update(new_alert_settings)
        prefs["alerts"] = alert_prefs
        save_alert_preferences_to_cloud(new_alert_settings)

st.sidebar.markdown("---")

st.title("angstrom signals - level 1")

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
    - **Strong Bullish / Bullish (Score ≥ 45) [Green]**: Clear upward technical alignment or baseline positive momentum.
    - **Neutral / Transition (Score 35–44) [Amber]**: Mixed signals, consolidation, or slight consolidation.
    - **Bearish / Strong Bearish (Score < 35) [Red]**: Downward momentum, trading below key moving averages, or overbought exhaustion.

    ### Customizing Indicator Weights & Weight Sets
    In the sidebar under **Scoring Balance Weights**:
    - **Sliders**: Tailor the relative importance (multiplier from `0.0` to `2.0`) of individual technical indicators to fit your trading style.
    - **Named Weight Sets**: Save your custom weight profiles, instantly load built-in or saved profiles from the dropdown, or delete unwanted sets. Changes persist automatically.

    ### Column meanings
    - **Score** — the composite 0–100 number (bar color: green ≥45, amber 35–44, red <35)
    - **Signal** — text label (Strong Bullish → Strong Bearish)
    - **RSI** — Relative Strength Index
    - **7d %** — price change over the last 7 days
    - **ATR %** — Average True Range as a percentage of price (volatility)
    - **Vol** — current volume vs 20-day average

    ### How to use it
    1. Check the tables for the highest/lowest scores.
    2. Use the **Type** and **Asset** dropdowns under the chart to inspect any symbol.
    3. Read the **Score Breakdown** to see exactly why the score is what it is.
    4. Edit your watchlists, alerts, or indicator weights from the sidebar (changes are saved to your account).

    Data refreshes automatically every 5 minutes.
    """)

st.markdown("### Crypto & Equity Signals Dashboard")
st.caption("Research prototype • Multi-factor technical scoring • Not financial advice")

CRYPTO_WATCHLIST = prefs["crypto"]
STOCK_WATCHLIST = prefs["stock"]
current_weights = prefs["weights"]
custom_profiles = prefs["profiles"]
settings = prefs["settings"]

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

built_in_profiles = get_builtin_profiles()
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
    prefs["weights"] = current_weights
    save_preferences_to_cloud({"scoring_weights": current_weights})
    st.session_state.reset_weights = False

# Sidebar Watchlists Management
st.sidebar.header("Watchlists")

with st.sidebar.expander("Edit Crypto", expanded=False):
    st.caption("Add by CoinGecko-style id (bitcoin, ethereum, solana, etc.)")
    new_crypto = st.text_input("Add crypto id", key="new_crypto", placeholder="e.g. dogecoin")
    if st.button("Add Crypto") and new_crypto:
        cid = new_crypto.strip().lower()
        if cid and cid not in CRYPTO_WATCHLIST:
            CRYPTO_WATCHLIST[cid] = cid.replace("-", " ").title()
            prefs["crypto"] = CRYPTO_WATCHLIST
            save_preferences_to_cloud({"crypto_watchlist": CRYPTO_WATCHLIST})
            st.rerun()
    if CRYPTO_WATCHLIST:
        to_remove = st.selectbox("Remove crypto", [""] + list(CRYPTO_WATCHLIST.keys()), key="rm_crypto")
        if to_remove:
            if st.button("Remove Crypto"):
                CRYPTO_WATCHLIST.pop(to_remove, None)
                prefs["crypto"] = CRYPTO_WATCHLIST
                save_preferences_to_cloud({"crypto_watchlist": CRYPTO_WATCHLIST})
                st.rerun()

with st.sidebar.expander("Edit Stocks", expanded=False):
    st.caption("Add by ticker (AAPL, MSFT, etc.)")
    new_stock = st.text_input("Add stock ticker", key="new_stock", placeholder="e.g. GOOGL")
    if st.button("Add Stock") and new_stock:
        tic = new_stock.strip().upper()
        if tic and tic not in STOCK_WATCHLIST:
            STOCK_WATCHLIST[tic] = tic
            prefs["stock"] = STOCK_WATCHLIST
            save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
            st.rerun()
    if STOCK_WATCHLIST:
        to_remove = st.selectbox("Remove stock", [""] + list(STOCK_WATCHLIST.keys()), key="rm_stock")
        if to_remove:
            if st.button("Remove Stock"):
                STOCK_WATCHLIST.pop(to_remove, None)
                prefs["stock"] = STOCK_WATCHLIST
                save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
                st.rerun()

# Sidebar Settings
st.sidebar.header("Settings")
days_history = st.sidebar.slider("Days of history", 90, 365, settings.get("days_history", 200))
show_reasons = st.sidebar.checkbox("Show score breakdown", value=settings.get("show_reasons", True))
show_extra_metrics = st.sidebar.checkbox("Show extra metrics (7d, ATR, volume)", value=settings.get("show_extra_metrics", True))

new_settings = {"days_history": days_history, "show_reasons": show_reasons, "show_extra_metrics": show_extra_metrics}
if new_settings != settings:
    settings = new_settings
    prefs["settings"] = settings
    save_preferences_to_cloud({"settings": settings})

st.sidebar.header("Scoring Balance Weights")

with st.sidebar.expander("Customize Indicator Weights", expanded=False):
    st.caption("Adjust relative importance of indicators (saved to your account).")

    st.markdown("**Named Weight Sets**")
    profile_names = ["Select saved set..."] + list(all_