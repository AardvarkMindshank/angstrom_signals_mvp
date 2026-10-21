"""
Crypto & Equity Signals Dashboard
Run with: streamlit run app.py
"""

import base64
import html
import json
import time
import traceback

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from supabase import create_client

st.set_page_config(
    page_title="angstrom signals - level 1",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from alerts import evaluate_alerts
    from data_fetchers import fetch_crypto_data, fetch_stock_data, period_for_days
    from scoring import calculate_indicators, compute_score, find_column
except Exception:
    st.error("The dashboard could not load its scoring code.")
    st.code(traceback.format_exc())
    st.stop()


def jwt_role(key: str) -> str | None:
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role")
    except Exception:
        return None


def _secret(name: str):
    try:
        return st.secrets["supabase"][name]
    except Exception:
        return None


def get_supabase():
    """A new client per script run, authenticated only for this browser session."""
    url = _secret("url")
    key = _secret("anon_key") or _secret("key")

    if not url or not key:
        st.error(
            "Add your Supabase URL and anon key to `.streamlit/secrets.toml` "
            "under `[supabase]` as `url` and `anon_key`."
        )
        st.stop()

    if jwt_role(key) == "service_role":
        st.error(
            "This app is using the Supabase service-role key. Put the anon key in "
            "`.streamlit/secrets.toml` as `anon_key`. Keep the service-role key only "
            "on the alert worker."
        )
        st.stop()

    client = create_client(url, key)
    access = st.session_state.get("access_token")
    refresh = st.session_state.get("refresh_token")
    if access and refresh:
        try:
            client.auth.set_session(access, refresh)
        except Exception:
            st.session_state.user = None
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            client = create_client(url, key)
    return client


def clear_session():
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.pop("cloud_prefs", None)


if "user" not in st.session_state:
    st.session_state.user = None
if st.session_state.user is not None and not st.session_state.get("access_token"):
    st.session_state.user = None
if "data_nonce" not in st.session_state:
    st.session_state.data_nonce = 0

supabase = get_supabase()

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
                        "password": login_password,
                    })
                    session = response.session
                    if session is None:
                        st.error("Login did not return a session. Confirm your email, then try again.")
                    else:
                        st.session_state.user = response.user
                        st.session_state.access_token = session.access_token
                        st.session_state.refresh_token = session.refresh_token
                        st.rerun()
                except Exception:
                    st.error("Login failed. Check your email and password.")

        with auth_tab2:
            st.markdown("### Create New Account")
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("Create Account", type="primary", use_container_width=True):
                try:
                    supabase.auth.sign_up({
                        "email": signup_email,
                        "password": signup_password,
                    })
                    st.success("Account created. Confirm the email if required, then log in.")
                except Exception:
                    st.error("Sign up failed. Try a different email, or a longer password.")

    st.stop()


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
        "macd": 1.0, "ichimoku": 1.0, "bb": 1.0, "volume": 1.0, "obv": 1.0, "performance": 1.0,
    }
    default_settings = {
        "days_history": 200,
        "show_reasons": True,
        "show_extra_metrics": True,
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
                "settings": row.get("settings") or default_settings,
            }
        else:
            initial_row = {
                "user_id": user_id,
                "crypto_watchlist": default_crypto,
                "stock_watchlist": default_stock,
                "scoring_weights": default_weights,
                "weight_profiles": {},
                "settings": default_settings,
            }
            supabase.table("user_preferences").insert(initial_row).execute()
            prefs_dict = {
                "crypto": default_crypto,
                "stock": default_stock,
                "weights": default_weights,
                "profiles": {},
                "settings": default_settings,
            }

        alert_res = supabase.table("alert_preferences").select("*").eq("user_id", user_id).execute()
        if alert_res.data and len(alert_res.data) > 0:
            prefs_dict["alerts"] = alert_res.data[0]
        else:
            default_alerts = {
                "user_id": user_id,
                "enabled": True,
                "min_score_alert": 70,
                "max_score_alert": 30,
            }
            supabase.table("alert_preferences").insert(default_alerts).execute()
            prefs_dict["alerts"] = default_alerts

        return prefs_dict

    except Exception as exc:
        st.error(f"Error loading cloud preferences: {exc}")
        return {
            "crypto": default_crypto,
            "stock": default_stock,
            "weights": default_weights,
            "profiles": {},
            "settings": default_settings,
            "alerts": {"enabled": True, "min_score_alert": 70, "max_score_alert": 30},
        }


def save_preferences_to_cloud(updates: dict):
    try:
        supabase.table("user_preferences").update(updates).eq("user_id", user_id).execute()
    except Exception as exc:
        st.error(f"Error saving preferences to cloud: {exc}")


def save_alert_preferences_to_cloud(updates: dict):
    try:
        supabase.table("alert_preferences").update(updates).eq("user_id", user_id).execute()
    except Exception as exc:
        st.error(f"Error saving alert preferences: {exc}")


def fetch_user_notifications():
    try:
        res = (
            supabase.table("user_notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


if "cloud_prefs" not in st.session_state:
    st.session_state.cloud_prefs = load_user_preferences()

prefs = st.session_state.cloud_prefs
alert_prefs = prefs.get("alerts", {})

st.sidebar.header("Account")
st.sidebar.success(f"Logged in as:\n**{st.session_state.user.email}**")
if st.sidebar.button("Log Out", use_container_width=True):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    clear_session()
    st.rerun()

st.sidebar.markdown("---")

st.sidebar.header("🔔 Notifications")
notifications_list = fetch_user_notifications()
unread_count = sum(1 for note in notifications_list if not note.get("is_read", False))

with st.sidebar.expander(f"Alert Feed {f'({unread_count} new)' if unread_count > 0 else ''}", expanded=False):
    if not notifications_list:
        st.caption("No alerts yet. When a watchlist asset crosses a threshold, it shows up here.")
    else:
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            feed_filter = st.radio(
                "Filter",
                ["Unread", "All"],
                horizontal=True,
                label_visibility="collapsed",
                key="notif_filter_radio",
            )
        with f_col2:
            if st.button("Mark read", key="mark_read_btn", use_container_width=True):
                try:
                    supabase.table("user_notifications").update({"is_read": True}).eq("user_id", user_id).execute()
                    st.rerun()
                except Exception:
                    st.error("Could not mark alerts as read.")

        filtered_notifs = (
            [note for note in notifications_list if not note.get("is_read", False)]
            if feed_filter == "Unread"
            else notifications_list
        )

        if not filtered_notifs:
            st.caption(f"No {feed_filter.lower()} notifications.")
        else:
            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            for note in filtered_notifs:
                badge = "🔴" if not note.get("is_read") else "⚪"
                created = str(note.get("created_at") or "")[:16].replace("T", " ")
                st.write(f"{badge} {note.get('asset_name') or 'Asset'}")
                st.caption(note.get("message") or "")
                if created:
                    st.caption(created)
                st.markdown("---")

            if st.button("🗑️ Clear Read Alerts", use_container_width=True, key="clear_read_btn"):
                try:
                    supabase.table("user_notifications").delete().eq("user_id", user_id).eq("is_read", True).execute()
                    st.success("Cleared read alerts.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not clear alerts: {exc}")

with st.sidebar.expander("Configure Alert Rules", expanded=False):
    st.caption("70 is a strong bullish setup. 30 is a strong bearish setup. An alert re-arms after the score leaves the threshold.")
    alert_enabled = st.checkbox("Enable Alerts", value=alert_prefs.get("enabled", True), key="alert_enabled_cb")
    min_score = st.slider(
        "Bullish Alert Threshold (Score ≥)",
        50, 95, int(alert_prefs.get("min_score_alert", 70)),
        key="min_score_slider",
    )
    max_score = st.slider(
        "Bearish Alert Threshold (Score ≤)",
        5, 50, int(alert_prefs.get("max_score_alert", 30)),
        key="max_score_slider",
    )

    new_alert_settings = {
        "enabled": alert_enabled,
        "min_score_alert": min_score,
        "max_score_alert": max_score,
    }
    if new_alert_settings != {name: alert_prefs.get(name) for name in new_alert_settings}:
        alert_prefs.update(new_alert_settings)
        prefs["alerts"] = alert_prefs
        save_alert_preferences_to_cloud(new_alert_settings)

st.sidebar.markdown("---")

header_col1, header_col2 = st.columns([5, 1])
with header_col1:
    st.title("angstrom signals - level 1")
with header_col2:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True, help="Pull fresh data for this session"):
        st.session_state.data_nonce += 1
        st.rerun()

with st.expander("Help and guides", expanded=False):
    st.markdown("""
**Higher score = a more bullish setup.** Every score starts at 50 and each indicator adds or subtracts points. The result is kept between 0 and 100. This is a research tool, not financial advice.
""")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Strong bullish", "70+")
    c2.metric("Bullish", "60–69")
    c3.metric("Neutral", "47–52")
    c4.metric("Strong bearish", "below 30")
    st.caption("Green is 53 and above. Amber is 47–52. Red is below 47. Mildly bullish starts at 53, mildly bearish at 40, and bearish at 30.")

    left, right = st.columns(2)
    with left:
        st.markdown("""
**What moves the score** (at weight 1.0)

- **RSI** — oversold adds up to 8, overbought subtracts up to 8
- **Stochastic** — below 20 adds 5, above 80 subtracts 5
- **Moving averages** — 4 points for each of SMA 20, 50, and 200, added when price is above and subtracted when price is below
- **ADX** — a strong trend adds or subtracts 4, in the direction of the 50-day average
- **MACD** — up to 4 for the line versus zero, 3 for the signal cross, and 2 for the histogram
""")
    with right:
        st.markdown("""
**More factors**

- **Ichimoku** — 5 points for price versus the cloud, 3 for Tenkan versus Kijun
- **Bollinger Bands** — near the lower band adds 4, near the upper band subtracts 4
- **Volume** — a high-volume up bar adds 3, a high-volume down bar subtracts 3
- **OBV** — 3 points for whether volume flow is above or below its average
- **7-day move** — up to 4 points either way

Sidebar sliders scale each factor. Zero turns that factor off. Named sets save a slider mix to your account.
""")

    st.markdown("""
**How to use it**

1. Read the snapshot and the tables. The top row is the strongest score, the bottom is the weakest.
2. Open a name in the chart. The score breakdown shows which factors added or removed points.
3. **7d %** is the seven-day price change. **ATR %** is volatility. **Vol** is volume versus its 20-day average.
4. Alerts fire at 70 and 30 unless you move those sliders. An alert re-arms after the score leaves that zone.
5. While this page is open, prices and scores refresh every 5 minutes. Email checks run separately, about every 15 minutes, even if the page is closed.
""")

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
            "obv": 1.0, "performance": 1.2,
        },
        "📉 Mean Reversion": {
            "rsi": 1.5, "stochastic": 1.2, "sma": 0.8, "adx": 1.0,
            "macd": 0.8, "ichimoku": 1.0, "bb": 1.5, "volume": 0.8,
            "obv": 0.8, "performance": 0.8,
        },
        "🚀 Momentum Heavy": {
            "rsi": 1.0, "stochastic": 1.2, "sma": 1.0, "adx": 1.0,
            "macd": 1.5, "ichimoku": 1.0, "bb": 1.0, "volume": 1.2,
            "obv": 1.2, "performance": 1.5,
        },
    }


built_in_profiles = get_builtin_profiles()
all_profiles = {**built_in_profiles, **custom_profiles}

indicators = ["rsi", "stochastic", "sma", "adx", "macd", "ichimoku", "bb", "volume", "obv", "performance"]

for indicator in indicators:
    key_name = f"weight_{indicator}"
    if key_name not in st.session_state:
        st.session_state[key_name] = float(current_weights.get(indicator, 1.0))

if st.session_state.get("reset_weights"):
    for indicator in indicators:
        st.session_state[f"weight_{indicator}"] = 1.0
    current_weights = {indicator: 1.0 for indicator in indicators}
    prefs["weights"] = current_weights
    save_preferences_to_cloud({"scoring_weights": current_weights})
    st.session_state.reset_weights = False

st.sidebar.header("Watchlists")

with st.sidebar.expander("Edit Crypto", expanded=False):
    st.caption("Add by CoinGecko id (bitcoin, ethereum, polkadot, dogecoin).")
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
        if to_remove and st.button("Remove Crypto"):
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
        if to_remove and st.button("Remove Stock"):
            STOCK_WATCHLIST.pop(to_remove, None)
            prefs["stock"] = STOCK_WATCHLIST
            save_preferences_to_cloud({"stock_watchlist": STOCK_WATCHLIST})
            st.rerun()

st.sidebar.header("Settings")
days_history = st.sidebar.slider("Days of history", 90, 365, int(settings.get("days_history", 200)))
show_reasons = st.sidebar.checkbox("Show score breakdown", value=settings.get("show_reasons", True))
show_extra_metrics = st.sidebar.checkbox(
    "Show extra metrics (7d, ATR, volume)",
    value=settings.get("show_extra_metrics", True),
)

new_settings = {
    "days_history": days_history,
    "show_reasons": show_reasons,
    "show_extra_metrics": show_extra_metrics,
}
if new_settings != settings:
    settings = new_settings
    prefs["settings"] = settings
    save_preferences_to_cloud({"settings": settings})

st.sidebar.header("Scoring Balance Weights")

with st.sidebar.expander("Customize Indicator Weights", expanded=False):
    st.caption("Adjust the relative importance of each indicator. Every slider changes the score.")

    st.markdown("**Named Weight Sets**")
    profile_names = ["Select saved set..."] + list(all_profiles.keys())
    selected_profile = st.selectbox("Load Saved Set", profile_names, key="load_profile_sb")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Load Set") and selected_profile != "Select saved set...":
            if selected_profile in all_profiles:
                loaded = all_profiles[selected_profile]
                for indicator in indicators:
                    st.session_state[f"weight_{indicator}"] = float(loaded.get(indicator, 1.0))
                current_weights = loaded
                prefs["weights"] = current_weights
                save_preferences_to_cloud({"scoring_weights": current_weights})
                st.success(f"Loaded '{selected_profile}'.")
                st.rerun()
    with col_p2:
        if st.button("Delete Set") and selected_profile != "Select saved set...":
            if selected_profile in built_in_profiles:
                st.error("Built-in profiles cannot be deleted.")
            elif selected_profile in custom_profiles:
                custom_profiles.pop(selected_profile)
                prefs["profiles"] = custom_profiles
                save_preferences_to_cloud({"weight_profiles": custom_profiles})
                st.success(f"Deleted '{selected_profile}'.")
                st.rerun()

    new_profile_name = st.text_input("New set name", placeholder="e.g. Volatility Focus")
    if st.button("Save Current as New Set") and new_profile_name:
        pname = new_profile_name.strip()
        if pname:
            if pname in built_in_profiles:
                st.error("Cannot overwrite a built-in profile name.")
            else:
                custom_profiles[pname] = current_weights
                prefs["profiles"] = custom_profiles
                save_preferences_to_cloud({"weight_profiles": custom_profiles})
                st.success(f"Saved set '{pname}'.")
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
        "obv": w_obv, "performance": w_perf,
    }

    if new_weights != current_weights:
        save_preferences_to_cloud({"scoring_weights": new_weights})
        current_weights = new_weights
        prefs["weights"] = current_weights

    if st.button("🔄 Reset to Default (1.0)"):
        st.session_state.reset_weights = True
        st.rerun()


@st.cache_data(ttl=300)
def load_crypto(coin_id, days, nonce):
    del nonce
    return fetch_crypto_data(coin_id, days)


@st.cache_data(ttl=300)
def load_stock(ticker, days, nonce):
    del nonce
    return fetch_stock_data(ticker, period=period_for_days(days))


def tone(score):
    """Text color, badge background, arrow, and bar color for a score."""
    if score is None or pd.isna(score):
        return "#6b7280", "#f3f4f6", "—", "#6b7280"
    if score >= 53:
        return "#15803d", "#dcfce7", "↑", "#22c55e"
    if score >= 47:
        return "#b45309", "#fef3c7", "→", "#f59e0b"
    return "#b91c1c", "#fee2e2", "↓", "#ef4444"


@st.fragment(run_every=300)
def render_dashboard(crypto_watchlist, stock_watchlist, history_days, weights, show_reasons_flag, show_extra_metrics_flag):
    # Wall-clock window so a scheduled rerun fetches new prices instead of the 5-minute cache.
    nonce = (st.session_state.data_nonce, int(time.time() // 300))

    def process_watchlist(watchlist, is_crypto=True):
        results = []
        for key, name in watchlist.items():
            with st.spinner(f"Loading {name}..."):
                if is_crypto:
                    df, err = load_crypto(key, history_days, nonce)
                else:
                    df, err = load_stock(key, history_days, nonce)

                result = {
                    "symbol": name if is_crypto else f"{name} ({key})",
                    "score": None,
                    "label": "No data",
                    "reasons": [err] if err else [],
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

                if err:
                    results.append(result)
                    continue

                if not df.empty and len(df) >= 15:
                    try:
                        df = calculate_indicators(df)
                        scored = compute_score(df, weights=weights)
                        if isinstance(scored, dict):
                            result.update(scored)
                            result["symbol"] = name if is_crypto else f"{name} ({key})"
                            result["type"] = "Crypto" if is_crypto else "Stock"
                            result["key"] = key
                    except Exception as exc:
                        result["label"] = "Error"
                        result["reasons"] = [str(exc)]

                results.append(result)
        return results

    crypto_results = process_watchlist(crypto_watchlist, is_crypto=True)
    stock_results = process_watchlist(stock_watchlist, is_crypto=False)

    try:
        evaluate_alerts(supabase, user_id, crypto_results + stock_results, alert_prefs)
    except Exception:
        st.warning("Alerts were not updated on this refresh.")

    def get_top_bottom(results):
        valid = [row for row in results if row.get("score") is not None and not pd.isna(row.get("score"))]
        if not valid:
            return None, None
        ordered = sorted(valid, key=lambda row: row["score"], reverse=True)
        return ordered[0], ordered[-1]

    crypto_top, crypto_bot = get_top_bottom(crypto_results)
    stock_top, stock_bot = get_top_bottom(stock_results)

    st.subheader("Quick Snapshot")
    c1, c2, c3, c4 = st.columns(4)

    def render_snapshot_card(title, name, score):
        color, bg, arrow, _bar = tone(score)
        score_str = f"{score:.1f}/100" if score is not None and not pd.isna(score) else "—"
        safe_title = html.escape(str(title))
        safe_name = html.escape(str(name))
        return (
            "<div style='background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e5e7eb;'>"
            f"<div style='font-size: 0.8rem; color: #6b7280; margin-bottom: 4px;'>{safe_title}</div>"
            f"<div style='font-size: 1.1rem; font-weight: 600; color: #111827; margin-bottom: 8px; "
            f"white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{safe_name}</div>"
            f"<div style='display: inline-flex; align-items: center; gap: 4px; background: {bg}; "
            f"color: {color}; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 600;'>"
            f"{arrow} {score_str}</div></div>"
        )

    with c1:
        st.markdown(
            render_snapshot_card("Top Crypto", crypto_top["symbol"] if crypto_top else "—", crypto_top["score"] if crypto_top else None),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            render_snapshot_card("Weakest Crypto", crypto_bot["symbol"] if crypto_bot else "—", crypto_bot["score"] if crypto_bot else None),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            render_snapshot_card("Top Stock", stock_top["symbol"] if stock_top else "—", stock_top["score"] if stock_top else None),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            render_snapshot_card("Weakest Stock", stock_bot["symbol"] if stock_bot else "—", stock_bot["score"] if stock_bot else None),
            unsafe_allow_html=True,
        )

    def render_score_bar(score):
        if score is None or pd.isna(score):
            pct, color, label = 0, "#6b7280", "—"
        else:
            pct = max(0, min(100, float(score)))
            color = tone(score)[3]
            label = f"{score:.0f}"
        return (
            '<div style="display:flex;align-items:center;gap:8px;width:100%;min-width:100px;">'
            '<div style="flex:1;background:#e5e7eb;border-radius:6px;height:14px;overflow:hidden;">'
            f'<div style="width:{pct}%;background:{color};height:100%;border-radius:6px;"></div></div>'
            f'<span style="min-width:28px;font-weight:600;font-size:0.9em;">{label}</span></div>'
        )

    def cell(value):
        return f"<td style='padding: 10px; white-space: nowrap;'>{html.escape(str(value))}</td>"

    def style_and_show_table(results, title):
        if not results:
            return
        frame = pd.DataFrame(results).sort_values("score", ascending=False, na_position="last")
        st.subheader(title)

        headers = ["Asset", "Score", "Signal", "Price", "RSI"]
        if show_extra_metrics_flag:
            headers += ["7d %", "ATR %", "Vol"]

        header_html = "".join(
            f"<th style='padding: 8px 10px; text-align: left; white-space: nowrap;'>{html.escape(name)}</th>"
            for name in headers
        )

        rows_html = ""
        for _, row in frame.iterrows():
            price = row.get("latest_price")
            rsi = row.get("rsi")
            price_str = f"${price:,.2f}" if pd.notna(price) else "—"
            rsi_str = f"{rsi:.1f}" if pd.notna(rsi) else "—"
            rows_html += (
                "<tr style='border-bottom: 1px solid #f0f0f0;'>"
                f"<td style='padding: 10px; white-space: nowrap; font-weight: 500;'>{html.escape(str(row['symbol']))}</td>"
                f"<td style='padding: 10px; min-width: 130px;'>{render_score_bar(row['score'])}</td>"
                f"{cell(row.get('label') or '—')}{cell(price_str)}{cell(rsi_str)}"
            )
            if show_extra_metrics_flag:
                change = row.get("change_7d")
                atr = row.get("atr_pct")
                volume = row.get("volume_ratio")
                change_str = f"{change:+.1f}%" if pd.notna(change) else "—"
                atr_str = f"{atr:.2f}" if pd.notna(atr) else "—"
                volume_str = f"{volume:.2f}" if pd.notna(volume) else "—"
                rows_html += f"{cell(change_str)}{cell(atr_str)}{cell(volume_str)}"
            rows_html += "</tr>"

        st.html(
            "<div style='width: 100%; overflow-x: auto; margin-bottom: 8px;'>"
            "<table style='width: 100%; border-collapse: collapse; font-size: 0.95rem;'>"
            f"<thead><tr style='border-bottom: 2px solid #e5e7eb;'>{header_html}</tr></thead>"
            f"<tbody>{rows_html}</tbody></table></div>"
        )

        problems = [
            f"{row['symbol']}: {row['reasons'][0]}"
            for row in results
            if row.get("label") in ("No data", "Error") and row.get("reasons")
        ]
        for problem in problems:
            st.text(problem)

    style_and_show_table(crypto_results, "Crypto Scores")
    style_and_show_table(stock_results, "Equity Scores")

    st.subheader("Interactive Chart")
    col1, col2 = st.columns([1, 3])
    with col1:
        asset_type = st.selectbox("Type", ["Crypto", "Stock"], key="asset_type")
    with col2:
        watchlist = crypto_watchlist if asset_type == "Crypto" else stock_watchlist
        options = list(watchlist.keys())
        if options:
            asset_key = st.selectbox(
                "Asset",
                options,
                format_func=lambda item: watchlist[item] if asset_type == "Crypto" else f"{watchlist[item]} ({item})",
                key="asset_crypto" if asset_type == "Crypto" else "asset_stock",
            )
        else:
            asset_key = None
            st.caption("This watchlist is empty.")

    if not asset_key:
        st.info("Add an asset to this watchlist to see a chart.")
        return

    if asset_type == "Crypto":
        df_chart, chart_err = load_crypto(asset_key, history_days, nonce)
        title = crypto_watchlist[asset_key]
    else:
        df_chart, chart_err = load_stock(asset_key, history_days, nonce)
        title = f"{stock_watchlist[asset_key]} ({asset_key})"

    if chart_err or df_chart.empty:
        st.warning(chart_err or "Could not load chart data. Check your internet connection.")
        return

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
            go.Scatter(x=df_chart.index, y=df_chart["sma_20"], name="SMA 20", line=dict(color="orange", width=1.5)),
            row=1, col=1,
        )
    if "sma_50" in df_chart.columns:
        fig.add_trace(
            go.Scatter(x=df_chart.index, y=df_chart["sma_50"], name="SMA 50", line=dict(color="royalblue", width=1.5)),
            row=1, col=1,
        )

    upper_name = find_column(df_chart, "BBU_")
    lower_name = find_column(df_chart, "BBL_")
    if upper_name and lower_name:
        fig.add_trace(
            go.Scatter(
                x=df_chart.index, y=df_chart[upper_name], name="BB Upper",
                line=dict(color="gray", width=1, dash="dot"), showlegend=False,
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df_chart.index, y=df_chart[lower_name], name="BB Lower",
                line=dict(color="gray", width=1, dash="dot"), fill="tonexty",
                fillcolor="rgba(128,128,128,0.08)", showlegend=False,
            ),
            row=1, col=1,
        )

    colors = [
        "green" if df_chart["close"].iloc[i] >= df_chart["open"].iloc[i] else "red"
        for i in range(len(df_chart))
    ]
    fig.add_trace(
        go.Bar(x=df_chart.index, y=df_chart["volume"], name="Volume", marker_color=colors, opacity=0.6),
        row=2, col=1,
    )
    if "rsi" in df_chart.columns:
        fig.add_trace(
            go.Scatter(x=df_chart.index, y=df_chart["rsi"], name="RSI", line=dict(color="purple", width=1.5)),
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
    score_val = result["score"]
    color, _bg, arrow, _bar = tone(score_val)
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(
            "<div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 2px;'>Current Score</div>"
            f"<div style='font-size: 2.2rem; font-weight: 600; line-height: 1.1; margin-bottom: 4px;'>{score_val}/100</div>"
            f"<div style='font-size: 0.95rem; font-weight: 500; color: {color};'>"
            f"{arrow} {html.escape(str(result['label']))}</div>",
            unsafe_allow_html=True,
        )
    if result.get("change_7d") is not None:
        col_b.metric("7-Day Change", f"{result['change_7d']:+.1f}%")
    if result.get("atr_pct") is not None:
        col_c.metric("Volatility (ATR%)", f"{result['atr_pct']:.2f}%")

    if show_reasons_flag and result.get("reasons") and result.get("score") is not None:
        st.subheader(f"Score Breakdown — {title}")
        st.markdown(
            f"<span style='color:{color};font-weight:bold;font-size:1.1em'>"
            f"{result['score']}/100 ({html.escape(str(result['label']))})</span>",
            unsafe_allow_html=True,
        )
        breakdown_col1, breakdown_col2 = st.columns(2)
        with breakdown_col1:
            contributions = result.get("contributions") or {}
            if contributions:
                fig_contrib = go.Figure(go.Bar(
                    x=list(contributions.values()),
                    y=list(contributions.keys()),
                    orientation="h",
                    marker_color=["#22c55e" if points >= 0 else "#ef4444" for points in contributions.values()],
                ))
                fig_contrib.update_layout(
                    title="Indicator Point Contributions",
                    xaxis_title="Points Added or Subtracted",
                    yaxis=dict(autorange="reversed"),
                    height=320,
                    margin=dict(t=30, b=20, l=10, r=10),
                )
                fig_contrib.add_vline(x=0, line_width=1.5, line_dash="dash", line_color="gray", opacity=0.7)
                st.plotly_chart(fig_contrib, width="stretch")
        with breakdown_col2:
            st.markdown("**Detailed Reasons**")
            for reason in result["reasons"]:
                st.caption(f"• {reason}")


render_dashboard(
    CRYPTO_WATCHLIST,
    STOCK_WATCHLIST,
    days_history,
    current_weights,
    show_reasons,
    show_extra_metrics,
)

st.sidebar.markdown("---")
st.sidebar.info("While this page is open, prices and scores refresh every 5 minutes.")
st.sidebar.caption("Watchlists, settings, and alerts are stored on your account.")
