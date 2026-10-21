"""
Crypto & Equity Signals Dashboard
Run with: streamlit run app.py
"""

import base64
import html
import io
import json
import time
import traceback
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

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

# A normal link starts a new Streamlit session and logs the user out.
# This stays on the page and reports the clicked name back to Python.
_SCORE_TABLE_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  let host = parentElement.querySelector("[data-score-host]");
  Array.from(parentElement.children).forEach((child) => {
    if (child !== host) child.remove();
  });
  if (!host) {
    host = document.createElement("div");
    host.setAttribute("data-score-host", "");
    parentElement.appendChild(host);
  }
  host.innerHTML = typeof data === "string" ? data : "";
  host.querySelectorAll("button[data-pick]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      button.blur();
      setTriggerValue("picked", button.getAttribute("data-pick"));
    });
  });
  return () => host.remove();
}
"""
_score_table = st.components.v2.component(
    "score_table",
    js=_SCORE_TABLE_JS,
    isolate_styles=False,
)

_SCROLL_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const token = String((data && data.token) || "");
  const targetId = String((data && data.target) || "interactive-chart");
  if (!token || window.scrollChartToken === token) return;
  window.scrollChartToken = token;
  const alreadyOnScreen = () => {
    if (targetId !== "interactive-chart") return false;
    const target = document.getElementById(targetId);
    if (!target) return false;
    const scroller = target.closest('[data-testid="stMain"]') || target.closest("section.main");
    const viewTop = scroller ? scroller.getBoundingClientRect().top : 0;
    const viewBottom = scroller ? scroller.getBoundingClientRect().bottom : window.innerHeight;
    const rect = target.getBoundingClientRect();
    return rect.top >= viewTop - 16 && rect.top <= viewTop + (viewBottom - viewTop) * 0.55;
  };
  const go = () => {
    if (alreadyOnScreen()) return;
    const target = document.getElementById(targetId);
    if (!target) return;
    target.scrollIntoView({behavior: "auto", block: "start"});
    const scroller = target.closest('[data-testid="stMain"]') || target.closest("section.main");
    if (!scroller) return;
    const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 72;
    scroller.scrollTop = Math.max(0, top);
  };
  go();
  setTimeout(go, 50);
  setTimeout(go, 250);
  setTimeout(go, 700);
}
"""
_scroll_chart = st.components.v2.component(
    "scroll_chart",
    js=_SCROLL_JS,
    isolate_styles=False,
)

_BACK_TO_TOP_JS = """
export default function(component) {
  const { parentElement } = component;
  let host = parentElement.querySelector("[data-top-host]");
  Array.from(parentElement.children).forEach((child) => {
    if (child !== host) child.remove();
  });
  if (!host) {
    host = document.createElement("div");
    host.setAttribute("data-top-host", "");
    parentElement.appendChild(host);
  }
  host.style.textAlign = "right";
  host.innerHTML = "<button type='button' data-back-to-top "
    + "style='background:none;border:none;padding:4px 0;margin:0;color:#6b7280;"
    + "font:inherit;font-weight:600;cursor:pointer;white-space:nowrap;'>↑ Top</button>";
  host.querySelector("button").addEventListener("click", (event) => {
    event.preventDefault();
    const scroller = document.querySelector('[data-testid="stMain"]')
      || document.querySelector("section.main");
    if (scroller) scroller.scrollTop = 0;
    window.scrollTo({top: 0, behavior: "auto"});
  });
}
"""
_back_to_top = st.components.v2.component(
    "back_to_top",
    js=_BACK_TO_TOP_JS,
    isolate_styles=False,
)

_TECHNICAL_REFRESH_SECONDS = 300
_COUNTDOWN_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const timerKey = "cd_" + ((data && data.key) || "x");
  window.clearInterval(window[timerKey]);
  let host = parentElement.querySelector("[data-countdown]");
  if (!host) {
    host = document.createElement("div");
    host.setAttribute("data-countdown", "");
    parentElement.appendChild(host);
  }
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const end = Number(data && data.deadlineMs);
  const token = String((data && data.token) || "");
  function buttonLabel() {
    const column = parentElement.closest('[data-testid="column"]')
      || parentElement.closest('[data-testid="stColumn"]');
    const button = column && column.querySelector("button");
    if (!button) return null;
    button.style.whiteSpace = "nowrap";
    return button.querySelector("p") || button.querySelector('[data-testid="stMarkdownContainer"]') || button;
  }
  function render() {
    if (!Number.isFinite(end)) return;
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    const hours = Math.floor(left / 3600);
    const minutes = Math.floor((left % 3600) / 60);
    const seconds = String(left % 60).padStart(2, "0");
    const clock = hours > 0
      ? hours + ":" + String(minutes).padStart(2, "0") + ":" + seconds
      : minutes + ":" + seconds;
    const label = buttonLabel();
    if (label) label.textContent = "🔄 Refresh " + clock;
    if (left <= 0 && token && window[timerKey + "_sent"] !== token) {
      window.clearInterval(window[timerKey]);
      window[timerKey + "_sent"] = token;
      setTriggerValue("due", token);
    }
  }
  render();
  window[timerKey] = setInterval(render, 1000);
  return () => {
    window.clearInterval(window[timerKey]);
    host.remove();
  };
}
"""
_countdown = st.components.v2.component(
    "refresh_countdown",
    js=_COUNTDOWN_JS,
    isolate_styles=False,
)


def _countdown_due(deadline: float, widget_key: str) -> bool:
    """Show the time left and report when this deadline has been reached."""
    token = str(int(deadline * 1000))
    result = _countdown(
        key=widget_key,
        data={"deadlineMs": int(deadline * 1000), "token": token, "key": widget_key},
        on_due_change=lambda: None,
    )
    return result.due == token

try:
    from alerts import evaluate_alerts
    from data_fetchers import (
        crypto_ticker,
        fetch_crypto_data,
        fetch_stock_data,
        find_crypto,
        period_for_days,
        resolve_crypto_id,
    )
    from scoring import calculate_indicators, compute_score, find_column
    from sentiment import (
        analyze_market_sentiment,
        cached_sentiment_score,
        newest_first,
        sentiment_cached_at,
        sentiment_query,
        sentiment_ready,
        SENTIMENT_REFRESH_SECONDS,
    )
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
    st.session_state.pop("profile", None)


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


def load_profile():
    try:
        response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
    except Exception:
        return None
    return {}


def save_profile(updates: dict):
    payload = {
        "user_id": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **updates,
    }
    supabase.table("profiles").upsert(payload).execute()


def upload_avatar(uploaded) -> str:
    if uploaded.size > 5_000_000:
        raise ValueError("Use a photo smaller than 5 MB.")
    from PIL import Image

    image = Image.open(io.BytesIO(uploaded.getvalue())).convert("RGB")
    image.thumbnail((512, 512))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    path = f"{user_id}/avatar.jpg"
    bucket = supabase.storage.from_("avatars")
    file_options = {"content-type": "image/jpeg", "upsert": "true"}
    try:
        bucket.upload(path, buffer.getvalue(), file_options)
    except Exception:
        bucket.update(path, buffer.getvalue(), {"content-type": "image/jpeg"})
    public_url = bucket.get_public_url(path)
    return f"{public_url}?v={int(time.time())}"


def profile_card(profile: dict, email: str) -> str:
    name = (profile or {}).get("display_name") or email.split("@")[0]
    bio = ((profile or {}).get("bio") or "").strip()
    avatar = (profile or {}).get("avatar_url") or ""
    safe_name = html.escape(name)
    safe_email = html.escape(email)
    if avatar:
        face = (
            f"<img src='{html.escape(avatar, quote=True)}' alt='' "
            "style='width:52px;height:52px;border-radius:50%;object-fit:cover;display:block;'>"
        )
    else:
        initial = html.escape((name[:1] or "?").upper())
        face = (
            "<div style='width:52px;height:52px;border-radius:50%;background:#dbeafe;color:#1d4ed8;"
            "display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.2rem;'>"
            f"{initial}</div>"
        )
    bio_html = (
        f"<div style='margin-top:8px;font-size:0.85rem;color:#374151;'>{html.escape(bio)}</div>"
        if bio else ""
    )
    return (
        "<div style='background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:12px;'>"
        "<div style='display:flex;gap:10px;align-items:center;'>"
        f"{face}<div><div style='font-weight:600;color:#111827;'>{safe_name}</div>"
        f"<div style='font-size:0.78rem;color:#6b7280;'>{safe_email}</div></div></div>"
        f"{bio_html}</div>"
    )


if "cloud_prefs" not in st.session_state:
    st.session_state.cloud_prefs = load_user_preferences()
if "profile" not in st.session_state:
    st.session_state.profile = load_profile()

prefs = st.session_state.cloud_prefs
alert_prefs = prefs.get("alerts", {})
profile = st.session_state.profile

with st.sidebar.expander("👤 Account", expanded=False):
    if profile is None:
        st.warning("Profile storage is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor.")
        profile = {}
    st.markdown(profile_card(profile, st.session_state.user.email or ""), unsafe_allow_html=True)
    with st.expander("Edit profile", expanded=False):
        profile_name = st.text_input(
            "Display name",
            value=profile.get("display_name") or "",
            max_chars=40,
            key="profile_display_name",
        )
        profile_bio = st.text_area(
            "Short bio",
            value=profile.get("bio") or "",
            max_chars=160,
            height=80,
            key="profile_bio",
            placeholder="A line about you, for when social features arrive.",
        )
        profile_photo = st.file_uploader(
            "Profile photo",
            type=["png", "jpg", "jpeg", "webp"],
            key="profile_photo",
        )
        if profile.get("avatar_url"):
            st.caption("A new photo replaces the current one.")
        if st.button("Save profile", use_container_width=True):
            updates = {
                "display_name": profile_name.strip() or None,
                "bio": profile_bio.strip() or None,
            }
            try:
                if profile_photo is not None:
                    updates["avatar_url"] = upload_avatar(profile_photo)
                save_profile(updates)
                st.session_state.profile = {**profile, **updates}
                st.success("Profile saved.")
                st.rerun()
            except Exception as exc:
                st.error(
                    "Could not save the profile. If this is the first time, "
                    f"run the latest supabase_rls.sql in Supabase. {exc}"
                )

    if st.button("Log Out", use_container_width=True):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        clear_session()
        st.rerun()

def tone(score):
    """Text color, badge background, arrow, and bar color for a score."""
    if score is None or pd.isna(score):
        return "#6b7280", "#f3f4f6", "—", "#6b7280"
    if score >= 53:
        return "#15803d", "#dcfce7", "↑", "#22c55e"
    if score >= 47:
        return "#b45309", "#fef3c7", "→", "#f59e0b"
    return "#b91c1c", "#fee2e2", "↓", "#ef4444"


def sentiment_badge(score, pick: str | None = None) -> str:
    """Colored number box used for a headline score. A dash when there is no score yet."""
    if score is None or pd.isna(score):
        return "<span style='color:#6b7280;'>—</span>"
    color, background, _arrow, _bar = tone(score)
    box = (
        f"<span style='display:inline-block;min-width:52px;text-align:center;background:{background};"
        f"color:{color};border-radius:4px;padding:2px 8px;font-weight:600;'>{float(score):.0f}</span>"
    )
    if not pick:
        return box
    safe_pick = html.escape(pick, quote=True)
    return (
        f"<button type='button' data-pick='{safe_pick}' "
        "style='display:inline-block;margin:0;padding:0;border:none;background:transparent;"
        "cursor:pointer;font:inherit;line-height:1;'>"
        f"{box}</button>"
    )


def score_from_alert(note: dict):
    message = str(note.get("message") or "")
    if "/100" in message:
        token = message.split("/100", 1)[0].rsplit(None, 1)[-1]
        try:
            return float(token)
        except ValueError:
            pass
    kind = str(note.get("alert_type") or "")
    if kind.startswith("BULLISH"):
        return 70.0
    if kind.startswith("BEARISH"):
        return 30.0
    return None


notifications_list = fetch_user_notifications()
unread_count = sum(1 for note in notifications_list if not note.get("is_read", False))
notifications_label = "🔔 Notifications" + (f" ({unread_count})" if unread_count else "")

with st.sidebar.expander(notifications_label, expanded=False):
    with st.expander("Alert Feed", expanded=False):
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
                st.caption("Click an alert to highlight that asset and open it on the chart.")
                crypto_list = prefs.get("crypto") or {}
                stock_list = prefs.get("stock") or {}

                def notification_target(symbol: str):
                    raw = str(symbol or "").strip()
                    if not raw:
                        return None
                    if raw in crypto_list:
                        return "Crypto", raw
                    if raw in stock_list:
                        return "Stock", raw
                    crypto_ids = {str(key).lower(): key for key in crypto_list}
                    stock_ids = {str(key).upper(): key for key in stock_list}
                    if raw.lower() in crypto_ids:
                        return "Crypto", crypto_ids[raw.lower()]
                    if raw.upper() in stock_ids:
                        return "Stock", stock_ids[raw.upper()]
                    return None

                for note in filtered_notifs:
                    color, background, arrow, _bar = tone(score_from_alert(note))
                    name = html.escape(str(note.get("asset_name") or "Asset"))
                    message = html.escape(str(note.get("message") or ""))
                    created = html.escape(str(note.get("created_at") or "")[:16].replace("T", " "))
                    weight = "700" if not note.get("is_read") else "500"
                    border = color if not note.get("is_read") else "#e5e7eb"
                    target = notification_target(note.get("asset_symbol"))
                    card = (
                        "<div style='background:"
                        f"{background};border:1px solid {border};border-radius:8px;padding:8px 10px;margin-bottom:8px;'>"
                        f"<div style='font-weight:{weight};color:{color};'>{arrow} {name}</div>"
                        f"<div style='font-size:0.8rem;color:#374151;margin-top:2px;'>{message}</div>"
                        f"<div style='font-size:0.75rem;color:#6b7280;margin-top:2px;'>{created}</div></div>"
                    )
                    note_id = note.get("id") or name
                    if target:
                        kind_name, asset_id = target
                        pick_value = html.escape(f"{kind_name}|{asset_id}", quote=True)
                        card = (
                            f"<button type='button' data-pick='{pick_value}' "
                            "style='display:block;width:100%;margin:0;padding:0;border:none;"
                            "background:transparent;text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
                            f"{card}</button>"
                        )
                    picked = _score_table(
                        key=f"notif_{note_id}",
                        data=card,
                        on_picked_change=lambda: None,
                    ).picked
                    signature = f"{note_id}:{picked}"
                    if picked and target:
                        if st.session_state.get("notif_handled") != signature:
                            st.session_state.notif_handled = signature
                            st.session_state.chart_pick = target
                            st.session_state.chart_pick_from_row = True
                            st.session_state.scroll_target = "interactive-chart"
                            st.session_state.scroll_token = str(time.time_ns())
                            st.rerun()
                    elif str(st.session_state.get("notif_handled") or "").startswith(f"{note_id}:"):
                        st.session_state.notif_handled = None

                if st.button("🗑️ Clear Read Alerts", use_container_width=True, key="clear_read_btn"):
                    try:
                        supabase.table("user_notifications").delete().eq("user_id", user_id).eq("is_read", True).execute()
                        st.success("Cleared read alerts.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not clear alerts: {exc}")

    with st.expander("Configure Alert Rules", expanded=False):
        st.caption(
            "70 is a strong bullish setup. 30 is a strong bearish setup. "
            "An email is sent once when a score crosses a boundary, and again only after it leaves and crosses later."
        )
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

st.title("angstrom signals - level 1")

with st.expander("Help and guides", expanded=False):
    st.markdown("""
**Higher score = a more bullish setup.** Every score starts at 50 and each indicator adds or subtracts points. The result is kept between 0 and 100. This is a research tool, not financial advice.
""")
    bands = [
        ("Strong bullish", "70+", "#15803d", "#dcfce7"),
        ("Bullish", "60–69", "#15803d", "#dcfce7"),
        ("Neutral", "47–52", "#b45309", "#fef3c7"),
        ("Strong bearish", "below 30", "#b91c1c", "#fee2e2"),
    ]
    band_cols = st.columns(4)
    for column, (name, span, color, background) in zip(band_cols, bands):
        column.markdown(
            f"<div style='background:{background};color:{color};border-radius:8px;padding:12px 14px;'>"
            f"<div style='font-size:0.8rem;font-weight:600;'>{name}</div>"
            f"<div style='font-size:1.6rem;font-weight:700;line-height:1.2;'>{span}</div></div>",
            unsafe_allow_html=True,
        )
    st.caption("The same colors are used on the scores. Green is 53 and above. Amber is 47–52. Red is below 47.")

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
2. Click a name in either table, a Quick Snapshot box, or an alert under Notifications. That asset stays highlighted, and the page moves down to the chart when the chart is off screen. Click a sentiment score in the table to open that asset's headlines.
3. **7d %** is the seven-day price change. **ATR %** is volatility. **Vol** is volume versus its 20-day average.
4. Alerts fire at 70 and 30 unless you move those sliders. One email goes to the address on your account when a score crosses a boundary. It is not sent again until the score leaves that boundary and crosses it later.
5. Market sentiment, under the chart, asks Grok to score each recent headline from 0 to 100. The number at the top of that section is the average of those article scores. It is separate from the technical score. The time on the Refresh button beside Quick Snapshot reloads prices and technical scores every 5 minutes. The time on the Refresh button beside Market sentiment reloads the headlines and score for the asset on the chart about every 12 hours. Pressing either button refreshes that section now and starts its timer again.

**Alerts keep running in the background**

Prices and technical scores on this page refresh every 5 minutes while it is open. Market sentiment refreshes about every 12 hours while it is open. The same 5-minute alert check keeps running after you close the page or log out.

- A crossing is saved on your account. It shows up under Notifications the next time you log in.
- The email goes only to you.
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


def stored_weight(name: str) -> float:
    raw = current_weights.get(name, 1.0) if isinstance(current_weights, dict) else 1.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 1.0
    return min(2.0, max(0.0, round(value, 1)))


# A slider with no starting value mounts at 0. That blank set was saved, and
# every factor then adds nothing, so every score stays at 50.
weights_blank = all(stored_weight(name) == 0.0 for name in indicators)
if weights_blank:
    current_weights = {name: 1.0 for name in indicators}
    prefs["weights"] = current_weights
    save_preferences_to_cloud({"scoring_weights": current_weights})

for indicator in indicators:
    key_name = f"weight_{indicator}"
    if weights_blank or key_name not in st.session_state:
        st.session_state[key_name] = stored_weight(indicator)

if st.session_state.get("reset_weights"):
    for indicator in indicators:
        st.session_state[f"weight_{indicator}"] = 1.0
    current_weights = {indicator: 1.0 for indicator in indicators}
    prefs["weights"] = current_weights
    save_preferences_to_cloud({"scoring_weights": current_weights})
    st.session_state.reset_weights = False

with st.sidebar.expander("⭐ Watchlists", expanded=False):
    with st.expander("Edit Crypto", expanded=False):
        st.caption("Add a ticker (XLM) or a name (Stellar).")
        new_crypto = st.text_input("Add crypto", key="new_crypto", placeholder="e.g. XLM or Stellar")
        if st.button("Add Crypto") and new_crypto:
            found = find_crypto(new_crypto)
            if not found:
                st.warning(f"No coin found for '{new_crypto.strip()}'. Try the ticker, such as XLM, or the name, such as Stellar.")
            else:
                cid, label = found
                ticker = crypto_ticker(cid)
                alias = (ticker or "").lower()
                changed = False
                if alias and alias != cid and alias in CRYPTO_WATCHLIST:
                    CRYPTO_WATCHLIST.pop(alias, None)
                    changed = True
                if cid and cid not in CRYPTO_WATCHLIST:
                    CRYPTO_WATCHLIST[cid] = label
                    changed = True
                if changed:
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

    with st.expander("Edit Stocks", expanded=False):
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

with st.sidebar.expander("⚖️ Scoring Balance Weights", expanded=False):
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

    def weight_slider(label: str, name: str):
        key_name = f"weight_{name}"
        # Pass the saved weight as the value. Without it, the slider's own
        # default is the bottom of the range, which is 0.
        return st.slider(
            label,
            0.0,
            2.0,
            float(st.session_state[key_name]),
            step=0.1,
            key=key_name,
        )

    w_rsi = weight_slider("RSI Weight", "rsi")
    w_stoch = weight_slider("Stochastic Weight", "stochastic")
    w_sma = weight_slider("Moving Averages Weight", "sma")
    w_adx = weight_slider("ADX Trend Weight", "adx")
    w_macd = weight_slider("MACD & Hist Weight", "macd")
    w_ichi = weight_slider("Ichimoku Cloud Weight", "ichimoku")
    w_bb = weight_slider("Bollinger Bands Weight", "bb")
    w_vol = weight_slider("Volume Weight", "volume")
    w_obv = weight_slider("OBV Weight", "obv")
    w_perf = weight_slider("Performance Weight", "performance")

    new_weights = {
        "rsi": w_rsi, "stochastic": w_stoch, "sma": w_sma, "adx": w_adx,
        "macd": w_macd, "ichimoku": w_ichi, "bb": w_bb, "volume": w_vol,
        "obv": w_obv, "performance": w_perf,
    }

    # Every slider at 0 is the blank mount, not a mix worth keeping.
    # One slider can still be 0 to turn that single factor off.
    if new_weights != current_weights and any(float(value) != 0 for value in new_weights.values()):
        save_preferences_to_cloud({"scoring_weights": new_weights})
        current_weights = new_weights
        prefs["weights"] = current_weights

    if st.button("🔄 Reset to Default (1.0)"):
        st.session_state.reset_weights = True
        st.rerun()

with st.sidebar.expander("⚙️ Settings", expanded=False):
    days_history = st.slider("Days of history", 90, 365, int(settings.get("days_history", 200)))
    show_reasons = st.checkbox("Show score breakdown", value=settings.get("show_reasons", True))
    show_extra_metrics = st.checkbox(
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


@st.cache_data(ttl=300)
def load_crypto(coin_id, days, nonce):
    del nonce
    return fetch_crypto_data(coin_id, days)


@st.cache_data(ttl=300)
def load_stock(ticker, days, nonce):
    del nonce
    return fetch_stock_data(ticker, period=period_for_days(days))


def load_market_sentiment(query: str, enabled: bool, force: bool = False):
    return analyze_market_sentiment(query, enabled, force=force)


@st.fragment
def render_dashboard(crypto_watchlist, stock_watchlist, history_days, weights, show_reasons_flag, show_extra_metrics_flag):
    if "technical_due" not in st.session_state:
        st.session_state.technical_due = time.time() + _TECHNICAL_REFRESH_SECONDS

    snap_title, snap_refresh = st.columns([4, 1.45], vertical_alignment="center")
    with snap_title:
        st.subheader("Quick Snapshot")
    with snap_refresh:
        technical_now = st.button(
            "🔄 Refresh",
            key="refresh_technical",
            use_container_width=True,
            help="Pull fresh prices and technical scores. This also runs on its own when the timer reaches zero.",
        )
        technical_due = _countdown_due(st.session_state.technical_due, "technical_countdown")
        if technical_now or technical_due:
            st.session_state.data_nonce += 1
            st.session_state.technical_due = time.time() + _TECHNICAL_REFRESH_SECONDS
            st.rerun(scope="fragment")

    # Wall-clock window so a scheduled rerun fetches new prices instead of the 5-minute cache.
    nonce = (st.session_state.data_nonce, int(time.time() // 300))

    def process_watchlist(watchlist, is_crypto=True):
        results = []
        for key, name in watchlist.items():
            if is_crypto:
                ticker = crypto_ticker(key)
                if ticker and str(key).strip().upper() == ticker:
                    name = ticker
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

    def _select_chart_asset(raw):
        parts = str(raw).split("|")
        if len(parts) < 2:
            return
        kind_name, asset_id = parts[0], parts[1]
        destination = parts[2] if len(parts) > 2 else "chart"
        chosen = crypto_watchlist if kind_name == "Crypto" else stock_watchlist if kind_name == "Stock" else None
        if not chosen or asset_id not in chosen:
            return
        st.session_state.scroll_target = "market-sentiment" if destination == "sentiment" else "interactive-chart"
        st.session_state.scroll_token = str(time.time_ns())
        if st.session_state.get("chart_pick") != (kind_name, asset_id):
            st.session_state.chart_pick = (kind_name, asset_id)
            st.session_state.chart_pick_from_row = True
        st.rerun(scope="fragment")

    c1, c2, c3, c4 = st.columns(4)

    def render_snapshot_card(title, name, score, pick):
        color, bg, arrow, _bar = tone(score)
        score_str = f"{score:.1f}/100" if score is not None and not pd.isna(score) else "—"
        safe_title = html.escape(str(title))
        safe_name = html.escape(str(name))
        body = (
            "<div style='background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e5e7eb;'>"
            f"<div style='font-size: 0.8rem; color: #6b7280; margin-bottom: 4px;'>{safe_title}</div>"
            f"<div style='font-size: 1.1rem; font-weight: 600; color: #111827; margin-bottom: 8px; "
            f"white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{safe_name}</div>"
            f"<div style='display: inline-flex; align-items: center; gap: 4px; background: {bg}; "
            f"color: {color}; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 600;'>"
            f"{arrow} {score_str}</div></div>"
        )
        if not pick:
            return body
        safe_pick = html.escape(pick, quote=True)
        return (
            f"<button type='button' data-pick='{safe_pick}' "
            "style='display:block;width:100%;margin:0;padding:0;border:none;background:transparent;"
            "text-align:left;cursor:pointer;font:inherit;color:inherit;'>"
            f"{body}</button>"
        )

    def show_snapshot(column, title, row, kind, widget_key):
        pick = None
        name = "—"
        score = None
        if row and row.get("key"):
            name = row["symbol"]
            score = row.get("score")
            pick = f"{kind}|{row['key']}"
        with column:
            picked = _score_table(
                key=widget_key,
                data=render_snapshot_card(title, name, score, pick),
                on_picked_change=lambda: None,
            ).picked
            if picked:
                _select_chart_asset(str(picked))

    show_snapshot(c1, "Top Crypto", crypto_top, "Crypto", "snapshot_crypto_top")
    show_snapshot(c2, "Weakest Crypto", crypto_bot, "Crypto", "snapshot_crypto_weak")
    show_snapshot(c3, "Top Stock", stock_top, "Stock", "snapshot_stock_top")
    show_snapshot(c4, "Weakest Stock", stock_bot, "Stock", "snapshot_stock_weak")
    st.caption("Click a box to open that asset on the chart.")

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
        return f"<td style='padding:10px;white-space:nowrap;'>{html.escape(str(value))}</td>"

    def style_and_show_table(results, title, kind):
        if not results:
            return
        frame = pd.DataFrame(results).sort_values("score", ascending=False, na_position="last")
        st.subheader(title)
        st.caption("Click a name to show that asset on the chart. Click a sentiment score to open its headlines.")

        headers = ["Asset", "Score", "Signal", "Price", "RSI"]
        if show_extra_metrics_flag:
            headers += ["7d %", "ATR %", "Vol"]
        headers.append("Sentiment")
        header_html = "".join(
            f"<th style='padding:8px 10px;text-align:{'right' if name == 'Sentiment' else 'left'};"
            f"white-space:nowrap;'>{html.escape(name)}</th>"
            for name in headers
        )

        pick = st.session_state.get("chart_pick")
        rows_html = ""
        for _, row in frame.iterrows():
            asset_id = str(row["key"])
            selected = pick == (kind, asset_id)
            row_style = "background:#e5e7eb;color:#111827;" if selected else ""
            price = row.get("latest_price")
            rsi = row.get("rsi")
            price_str = f"${price:,.2f}" if pd.notna(price) else "—"
            rsi_str = f"{rsi:.1f}" if pd.notna(rsi) else "—"
            pick_value = html.escape(f"{kind}|{asset_id}", quote=True)
            name_button = (
                "<button type='button' data-pick='"
                f"{pick_value}' style='background:none;border:none;padding:0;margin:0;"
                "color:inherit;font:inherit;font-weight:600;text-decoration:underline;"
                "cursor:pointer;white-space:nowrap;'>"
                f"{html.escape(str(row['symbol']))}</button>"
            )
            rows_html += (
                f"<tr style='border-bottom:1px solid #f0f0f0;{row_style}'>"
                f"<td style='padding:10px;white-space:nowrap;'>{name_button}</td>"
                f"<td style='padding:10px;min-width:130px;'>{render_score_bar(row['score'])}</td>"
                f"{cell(row.get('label') or '—')}{cell(price_str)}{cell(rsi_str)}"
            )
            if show_extra_metrics_flag:
                change = row.get("change_7d")
                atr = row.get("atr_pct")
                volume = row.get("volume_ratio")
                rows_html += (
                    f"{cell(f'{change:+.1f}%' if pd.notna(change) else '—')}"
                    f"{cell(f'{atr:.2f}' if pd.notna(atr) else '—')}"
                    f"{cell(f'{volume:.2f}' if pd.notna(volume) else '—')}"
                )
            watchlist = crypto_watchlist if kind == "Crypto" else stock_watchlist
            label = watchlist.get(asset_id)
            headline_score = None
            if label:
                ticker = crypto_ticker(asset_id) if kind == "Crypto" else asset_id
                headline_score = cached_sentiment_score(sentiment_query(kind, str(label), ticker))
            sentiment_pick = f"{kind}|{asset_id}|sentiment" if headline_score is not None else None
            rows_html += (
                f"<td style='padding:10px;text-align:right;white-space:nowrap;'>"
                f"{sentiment_badge(headline_score, sentiment_pick)}</td></tr>"
            )

        table_html = (
            "<div style='width:100%;overflow-x:auto;margin-bottom:8px;-webkit-overflow-scrolling:touch;'>"
            "<table style='width:100%;border-collapse:collapse;font-size:0.95rem;'>"
            f"<thead><tr style='border-bottom:2px solid #e5e7eb;'>{header_html}</tr></thead>"
            f"<tbody>{rows_html}</tbody></table></div>"
        )
        picked = _score_table(
            key=f"score_table_{kind}",
            data=table_html,
            on_picked_change=lambda: None,
        ).picked
        if picked:
            _select_chart_asset(str(picked))

        problems = [
            f"{row['symbol']}: {row['reasons'][0]}"
            for row in results
            if row.get("label") in ("No data", "Error") and row.get("reasons")
        ]
        for problem in problems:
            st.text(problem)

    chosen_kind = st.query_params.get("chart_kind")
    chosen_asset = st.query_params.get("chart_asset")
    if chosen_kind and chosen_asset:
        chosen_kind = str(chosen_kind)
        chosen_asset = str(chosen_asset)
        chosen_list = crypto_watchlist if chosen_kind == "Crypto" else stock_watchlist if chosen_kind == "Stock" else {}
        if chosen_asset in chosen_list:
            st.session_state.chart_pick = (chosen_kind, chosen_asset)
            st.session_state.chart_pick_from_row = True
        del st.query_params["chart_kind"]
        del st.query_params["chart_asset"]

    if "chart_pick" not in st.session_state:
        if crypto_watchlist:
            st.session_state.chart_pick = ("Crypto", next(iter(crypto_watchlist)))
        elif stock_watchlist:
            st.session_state.chart_pick = ("Stock", next(iter(stock_watchlist)))

    style_and_show_table(crypto_results, "Crypto Scores", "Crypto")
    style_and_show_table(stock_results, "Equity Scores", "Stock")

    st.html(
        "<div id='interactive-chart' style='scroll-margin-top:4.5rem;'></div>"
    )
    pick = st.session_state.get("chart_pick")
    if pick and (
        st.session_state.pop("chart_pick_from_row", False)
        or "asset_type" not in st.session_state
    ):
        pick_kind, pick_key = pick
        pick_list = crypto_watchlist if pick_kind == "Crypto" else stock_watchlist
        if pick_key in pick_list:
            st.session_state.asset_type = pick_kind
            if pick_kind == "Crypto":
                st.session_state.asset_crypto = pick_key
            else:
                st.session_state.asset_stock = pick_key

    def selected_chart_name():
        kind = st.session_state.get("asset_type")
        if kind not in ("Crypto", "Stock"):
            kind = "Crypto" if crypto_watchlist else "Stock"
        watchlist = crypto_watchlist if kind == "Crypto" else stock_watchlist
        state_key = "asset_crypto" if kind == "Crypto" else "asset_stock"
        asset_id = st.session_state.get(state_key)
        if asset_id not in watchlist:
            asset_id = next(iter(watchlist), None)
        if not asset_id:
            return ""
        if kind == "Crypto":
            return str(watchlist[asset_id])
        return f"{watchlist[asset_id]} ({asset_id})"

    chart_name = selected_chart_name()
    chart_heading, chart_top = st.columns([5.2, 0.9], vertical_alignment="center")
    with chart_heading:
        st.subheader(f"Interactive Chart - {chart_name}" if chart_name else "Interactive Chart")
    with chart_top:
        _back_to_top(key="chart_back_to_top")
    _scroll_chart(
        key="scroll_to_chart",
        data={
            "token": st.session_state.get("scroll_token") or "",
            "target": st.session_state.get("scroll_target") or "interactive-chart",
        },
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        asset_type = st.selectbox("Type", ["Crypto", "Stock"], key="asset_type")
    with col2:
        watchlist = crypto_watchlist if asset_type == "Crypto" else stock_watchlist
        options = list(watchlist.keys())
        asset_state_key = "asset_crypto" if asset_type == "Crypto" else "asset_stock"
        if options and st.session_state.get(asset_state_key) not in options:
            st.session_state[asset_state_key] = options[0]
        if options:
            asset_key = st.selectbox(
                "Asset",
                options,
                format_func=lambda item: watchlist[item] if asset_type == "Crypto" else f"{watchlist[item]} ({item})",
                key=asset_state_key,
            )
        else:
            asset_key = None
            st.caption("This watchlist is empty.")

    if asset_key and st.session_state.get("chart_pick") != (asset_type, asset_key):
        st.session_state.chart_pick = (asset_type, asset_key)
        st.rerun(scope="fragment")

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

    sentiment_label = crypto_watchlist[asset_key] if asset_type == "Crypto" else stock_watchlist[asset_key]
    show_market_sentiment(
        asset_type,
        sentiment_label,
        crypto_ticker(asset_key) if asset_type == "Crypto" else asset_key,
    )


def _published_label(value) -> str:
    """Turn an RSS pubDate into a calendar date. Empty when the feed omitted one."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return ""
    return f"{when.strftime('%b')} {when.day}, {when.year}"


@st.fragment
def show_market_sentiment(kind: str, label: str, ticker: str | None):
    """Headline sentiment for the asset on the chart. Cached for 12 hours."""
    st.html("<div id='market-sentiment' style='scroll-margin-top:4.5rem;'></div>")
    st.markdown(
        "<hr style='margin:1.4rem 0 0.6rem;border:none;border-top:1px solid #e5e7eb;'>",
        unsafe_allow_html=True,
    )
    shown_name = " ".join((label or "").split())
    if kind == "Stock" and ticker and ticker.upper() not in shown_name.upper():
        shown_name = f"{shown_name} ({ticker})" if shown_name else ticker
    sentiment_heading = f"Market sentiment - {shown_name}" if shown_name else "Market sentiment"
    sentiment_title, sentiment_top, sentiment_refresh = st.columns([3.5, 0.9, 2.05], vertical_alignment="center")
    with sentiment_title:
        st.subheader(sentiment_heading)
    with sentiment_top:
        _back_to_top(key="sentiment_back_to_top")
    query = sentiment_query(kind, label, ticker)
    sentiment_deadlines = st.session_state.setdefault("sentiment_due", {})
    if query not in sentiment_deadlines:
        cached_at = sentiment_cached_at(query)
        sentiment_deadlines[query] = (
            cached_at + SENTIMENT_REFRESH_SECONDS
            if cached_at
            else time.time() + SENTIMENT_REFRESH_SECONDS
        )
    with sentiment_refresh:
        sentiment_now = st.button(
            "🔄 Refresh",
            key="refresh_sentiment",
            use_container_width=True,
            help="Pull fresh headlines and a new sentiment score for this asset. This also runs on its own when the timer reaches zero.",
        )
        sentiment_due = _countdown_due(sentiment_deadlines[query], "sentiment_countdown")
        if sentiment_now or sentiment_due:
            sentiment_deadlines[query] = time.time() + SENTIMENT_REFRESH_SECONDS
            st.session_state.sentiment_force = query
            st.rerun(scope="fragment")
    force_sentiment = st.session_state.get("sentiment_force") == query
    if force_sentiment:
        st.session_state.sentiment_force = None
    cached_before = sentiment_cached_at(query)
    with st.spinner("Reading recent headlines..."):
        report = load_market_sentiment(query, sentiment_ready(), force=force_sentiment)
    cached_after = sentiment_cached_at(query)
    if report.get("ok") and cached_after and cached_after != cached_before:
        st.rerun(scope="app")

    headlines = newest_first(report.get("headlines") or [])
    score = report.get("score")
    if report.get("ok") and score is not None:
        color, background, arrow, _bar = tone(score)
        if score >= 60:
            coverage = "Bullish coverage"
        elif score >= 53:
            coverage = "Mildly bullish coverage"
        elif score >= 47:
            coverage = "Mixed coverage"
        elif score >= 40:
            coverage = "Mildly bearish coverage"
        else:
            coverage = "Bearish coverage"
        summary = html.escape(report.get("summary") or "")
        driver_items = "".join(
            f"<li style='margin:4px 0;color:#374151;'>{html.escape(str(driver))}</li>"
            for driver in (report.get("drivers") or [])
        )
        drivers_html = (
            f"<ul style='margin:10px 0 0;padding-left:1.15rem;'>{driver_items}</ul>"
            if driver_items else ""
        )
        st.markdown(
            "<div style='background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;'>"
            "<div style='font-size:0.8rem;color:#6b7280;margin-bottom:4px;'>"
            + (
                "Average of the article scores below, from the last 7 days"
                if any(item.get("score") is not None for item in headlines)
                else "Score for these headlines, from the last 7 days"
            )
            + "</div>"
            f"<div style='display:inline-flex;align-items:center;gap:6px;background:{background};color:{color};"
            f"padding:2px 8px;border-radius:4px;font-weight:600;'>{arrow} {score:.0f}/100</div>"
            f"<div style='margin-top:8px;font-weight:600;color:{color};'>{html.escape(coverage)}</div>"
            f"<div style='margin-top:8px;color:#111827;'>{summary}</div>"
            f"{drivers_html}</div>",
            unsafe_allow_html=True,
        )
    elif report.get("reason") == "missing_key":
        st.info("Headlines are in. Add an xAI API key so Grok can score them. See the README under Market sentiment.")
    elif report.get("reason") == "no_headlines":
        st.info("No recent headlines turned up for this asset.")
    elif report.get("reason") == "model_busy":
        st.info("Grok is busy right now. The articles are below, and the score will be tried again in about a minute.")
    elif report.get("reason") == "bad_key":
        st.warning("The xAI API key was rejected. Check the key in the Streamlit secrets.")
    else:
        st.info("The sentiment score could not be built this time. The articles are below.")

    if headlines:
        rows = [
            "<div style='display:flex;align-items:center;gap:16px;padding:4px 0 8px;'>"
            "<div style='flex:1;font-size:0.8rem;font-weight:600;color:#6b7280;'>Article</div>"
            "<div style='width:112px;flex:none;text-align:right;font-size:0.8rem;font-weight:600;color:#6b7280;'>Published</div>"
            "<div style='width:76px;flex:none;text-align:right;font-size:0.8rem;font-weight:600;color:#6b7280;'>Score</div>"
            "</div>"
        ]
        for item in headlines:
            source = f" — {html.escape(item['source'])}" if item.get("source") else ""
            published = _published_label(item.get("published"))
            published_html = (
                html.escape(published)
                if published
                else "<span style='color:#6b7280;'>—</span>"
            )
            badge = sentiment_badge(item.get("score"))
            rows.append(
                "<div style='display:flex;align-items:center;gap:16px;padding:8px 0;border-top:1px solid #f3f4f6;'>"
                "<div style='flex:1;min-width:0;'>"
                f"<a href='{html.escape(item['link'], quote=True)}' target='_blank' rel='noopener noreferrer'>"
                f"{html.escape(item['title'])}</a>{source}</div>"
                f"<div style='width:112px;flex:none;text-align:right;white-space:nowrap;color:#4b5563;'>{published_html}</div>"
                f"<div style='width:76px;flex:none;text-align:right;'>{badge}</div></div>"
            )
        st.html(f"<div style='margin-top:10px;'>{''.join(rows)}</div>")
    st.caption("This reads recent coverage. It is not the technical score, and it is not advice.")


render_dashboard(
    CRYPTO_WATCHLIST,
    STOCK_WATCHLIST,
    days_history,
    current_weights,
    show_reasons,
    show_extra_metrics,
)

st.sidebar.markdown("---")
st.sidebar.info("Prices and technical scores refresh every 5 minutes while this page is open. Market sentiment refreshes about every 12 hours. Alert checks continue every 5 minutes after you leave.")
st.sidebar.caption("Watchlists, settings, and alerts are stored on your account.")
