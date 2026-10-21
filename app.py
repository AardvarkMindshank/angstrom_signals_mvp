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
    -