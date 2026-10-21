"""
Background alert worker for Angstrom Signals.

Run on a schedule with the Supabase service-role key. Do not use that key
in the Streamlit app.
"""

from __future__ import annotations

import base64
import html
import json
import os

import requests
from supabase import create_client

from alerts import evaluate_alerts
from data_fetchers import fetch_crypto_data, fetch_stock_data, period_for_days
from scoring import calculate_indicators, compute_score

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def jwt_role(key: str) -> str | None:
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role")
    except Exception:
        return None


def describe_key(key: str) -> str:
    """Classify a Supabase key without revealing the key itself."""
    key = key.strip()
    if key.startswith("sb_secret_"):
        return "secret"
    if key.startswith("sb_publishable_"):
        return "publishable"
    role = jwt_role(key)
    if role in ("service_role", "anon"):
        return role
    return "unrecognized"


def load_credentials() -> tuple[str, str]:
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or "").strip()
    if not url or not key:
        try:
            import streamlit as st
            url = str(st.secrets["supabase"]["url"]).strip()
            key = str(
                st.secrets["supabase"].get("service_role_key")
                or st.secrets["supabase"].get("key")
                or ""
            ).strip()
        except Exception as exc:
            raise ValueError(
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for the alert worker."
            ) from exc
    kind = describe_key(key)
    if kind not in ("secret", "service_role"):
        raise ValueError(
            "SUPABASE_SERVICE_ROLE_KEY is the wrong key. Use the Supabase secret key "
            "(it starts with sb_secret_) or the legacy service_role key. "
            f"The saved value looks like: {kind}."
        )
    return url, key


def user_email(supabase, user_id: str) -> str | None:
    try:
        response = supabase.auth.admin.get_user_by_id(user_id)
        user = getattr(response, "user", None)
        if user is None and isinstance(response, dict):
            user = response.get("user")
        if user is None:
            return None
        return getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)
    except Exception as exc:
        print(f"Could not look up the account email for {user_id}: {exc}")
        return None


def send_alert_email(to_email: str, asset_name: str, message: str) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key or not to_email:
        return

    sender = os.getenv("RESEND_FROM") or "onboarding@resend.dev"
    safe_name = html.escape(str(asset_name))
    safe_message = html.escape(str(message))
    subject = "Angstrom alert: " + " ".join(str(asset_name).split())
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json={
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": f"<p><strong>{safe_name}</strong> triggered an alert.</p><p>{safe_message}</p>",
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except Exception as exc:
        print(f"Email failed for {asset_name}: {exc}")
        return
    if response.status_code in (200, 201):
        print(f"Email sent for {asset_name}")
    else:
        print(f"Email failed for {asset_name}: HTTP {response.status_code}")


def _score_asset(df, weights):
    if df is None or df.empty or len(df) < 15:
        return None
    scored = compute_score(calculate_indicators(df), weights=weights)
    if not isinstance(scored, dict):
        return None
    return scored.get("score")


def run_background_checks() -> None:
    print("Starting background alert check...")
    url, key = load_credentials()
    supabase = create_client(url, key)

    prefs_res = (
        supabase.table("user_preferences")
        .select("user_id, crypto_watchlist, stock_watchlist, settings, scoring_weights")
        .execute()
    )
    all_user_prefs = prefs_res.data or []
    if not all_user_prefs:
        print("No user preferences found.")
        return

    alerts_res = supabase.table("alert_preferences").select("*").execute()
    alerts_map = {row["user_id"]: row for row in (alerts_res.data or [])}

    crypto_cache = {}
    stock_cache = {}

    for user_pref in all_user_prefs:
        user_id = user_pref["user_id"]
        alert_config = alerts_map.get(user_id, {
            "enabled": True,
            "min_score_alert": 70,
            "max_score_alert": 30,
        })
        if not alert_config.get("enabled", True):
            continue

        crypto_list = user_pref.get("crypto_watchlist") or {}
        stock_list = user_pref.get("stock_watchlist") or {}
        if not isinstance(crypto_list, dict):
            crypto_list = {}
        if not isinstance(stock_list, dict):
            stock_list = {}

        settings = user_pref.get("settings") or {}
        days_history = int(settings.get("days_history", 200) or 200)
        weights = user_pref.get("scoring_weights") or None
        results = []

        print(f"Checking assets for user {user_id}")

        for coin_id, name in crypto_list.items():
            cache_key = (str(coin_id).lower(), days_history)
            if cache_key not in crypto_cache:
                crypto_cache[cache_key] = fetch_crypto_data(coin_id, days_history)
            df, err = crypto_cache[cache_key]
            if err:
                print(err)
                continue
            try:
                score = _score_asset(df, weights)
            except Exception as exc:
                print(f"Scoring failed for {coin_id}: {exc}")
                continue
            if score is None:
                continue
            results.append({"key": coin_id, "symbol": name, "score": score})

        for ticker, name in stock_list.items():
            cache_key = (str(ticker).upper(), days_history)
            if cache_key not in stock_cache:
                stock_cache[cache_key] = fetch_stock_data(ticker, period=period_for_days(days_history))
            df, err = stock_cache[cache_key]
            if err:
                print(err)
                continue
            try:
                score = _score_asset(df, weights)
            except Exception as exc:
                print(f"Scoring failed for {ticker}: {exc}")
                continue
            if score is None:
                continue
            results.append({"key": ticker, "symbol": f"{name} ({ticker})", "score": score})

        try:
            opened = evaluate_alerts(
                supabase,
                user_id,
                results,
                alert_config,
                notify_email=user_email(supabase, user_id),
                send_email=send_alert_email,
            )
        except Exception as exc:
            print(f"Alerts failed for user {user_id}: {exc}")
            continue
        for alert in opened:
            print(f"Opened {alert['alert_type']} for {alert['asset_name']}")

    print("Background alert check finished.")


if __name__ == "__main__":
    run_background_checks()
