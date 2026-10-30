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

from alerts import evaluate_alerts, market_rows
from beta_worker import send_beta_decision_emails
from digest import send_due_digest
from email_brand import alert_tone, asset_logo, render_email
from scoring import calculate_indicators, compute_score
from market_store import asset_market_key
from shared_refresh import (
    canonical_asset_id,
    refresh_due_sentiment,
    refresh_price_catalog,
    slice_history,
)

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


def send_alert_email(to_email: str, asset_name: str, message: str, logo_url: str = "") -> bool:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not api_key:
        print(f"Email skipped for {asset_name}: RESEND_API_KEY is not set.")
        return False
    if not to_email:
        print(f"Email skipped for {asset_name}: this account has no email address.")
        return False

    sender = (os.getenv("RESEND_FROM") or "").strip() or "Angstrom Signals <onboarding@resend.dev>"
    if "onboarding@resend.dev" in sender and not getattr(send_alert_email, "_warned_test_sender", False):
        print(
            "Sending from onboarding@resend.dev. Resend only delivers that test "
            "address to the inbox that owns the Resend account."
        )
        send_alert_email._warned_test_sender = True
    safe_name = html.escape(str(asset_name))
    safe_message = html.escape(str(message))
    subject = "Angstrom alert: " + " ".join(str(asset_name).split())
    app_url = (os.getenv("APP_URL") or "https://app.angstromsignals.com").strip()
    page, plain = render_email(
        f"{asset_logo(logo_url, size=26)}{safe_name} crossed an alert boundary",
        [
            "This email is sent once for that crossing. "
            "It is sent again only after the score moves 10 points back from the boundary and then crosses it again.",
        ],
        callout=safe_message,
        tone=alert_tone(message),
        button=("Open the dashboard", app_url),
        preheader=" ".join(str(message).split())[:120],
    )
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json={
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": page,
                "text": plain,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except Exception as exc:
        print(f"Email failed for {asset_name}: {exc}")
        return False
    if response.status_code in (200, 201):
        print(f"Email sent for {asset_name}")
        return True
    detail = " ".join((response.text or "").split())[:300]
    print(f"Email failed for {asset_name}: HTTP {response.status_code} {detail}")
    return False


def send_digest_email(to_email: str, subject: str, page: str, plain: str) -> bool:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not api_key or not to_email:
        print("Digest skipped: RESEND_API_KEY or the account email is missing.")
        return False
    sender = (os.getenv("RESEND_FROM") or "").strip() or "Angstrom Signals <onboarding@resend.dev>"
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json={"from": sender, "to": [to_email], "subject": subject, "html": page, "text": plain},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except Exception as exc:
        print(f"Digest email failed: {exc}")
        return False
    if response.status_code in (200, 201):
        print("Digest email sent")
        return True
    detail = " ".join((response.text or "").split())[:300]
    print(f"Digest email failed: HTTP {response.status_code} {detail}")
    return False


def load_logos(supabase, catalog) -> dict[str, str]:
    """Logo address per shared asset key. Empty if the lookup fails: emails go out without logos."""
    keys = [asset_market_key(kind, asset_id) for kind, asset_id in catalog]
    logos = {}
    for start in range(0, len(keys), 100):
        try:
            rows = (
                supabase.table("asset_market")
                .select("asset_key, logo_url")
                .in_("asset_key", keys[start:start + 100])
                .execute()
                .data
                or []
            )
        except Exception as exc:
            print(f"Logos skipped for emails: {str(exc)[:160]}")
            return logos
        for row in rows:
            url = str(row.get("logo_url") or "").strip()
            if url:
                logos[str(row.get("asset_key"))] = url
    return logos


# A market score older than this is not used for alerts: the 12-hour refresh has stalled.
MARKET_SCORE_MAX_AGE_HOURS = 36


def load_market_scores(supabase) -> dict[str, float]:
    """Current crypto and stock market sentiment scores. Missing or stale ones are left out."""
    from datetime import datetime, timedelta, timezone

    try:
        rows = (
            supabase.table("market_mood")
            .select("market_key, sentiment_score, sentiment_updated_at")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"Market sentiment alerts skipped: {str(exc)[:160]}")
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MARKET_SCORE_MAX_AGE_HOURS)
    scores = {}
    for row in rows:
        try:
            score = float(row.get("sentiment_score"))
            stamp = datetime.fromisoformat(str(row.get("sentiment_updated_at")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if score == score and stamp >= cutoff:
            scores[str(row.get("market_key"))] = score
    return scores


def followed_markets(user_pref: dict) -> list[str]:
    """The markets this account has switched on in its settings."""
    settings = user_pref.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    markets = []
    if settings.get("trade_crypto", True) is not False:
        markets.append("crypto")
    if settings.get("trade_equities", True) is not False:
        markets.append("stock")
    return markets


def _score_asset(df, weights):
    if df is None or df.empty or len(df) < 15:
        return None
    scored = compute_score(calculate_indicators(df), weights=weights)
    if not isinstance(scored, dict):
        return None
    return scored.get("score")


def _watchlist(user_pref: dict) -> tuple[dict, dict, int]:
    """Crypto, stocks, and history length for one account. A hidden market is left out."""
    settings = user_pref.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    crypto = user_pref.get("crypto_watchlist") or {}
    stock = user_pref.get("stock_watchlist") or {}
    if not isinstance(crypto, dict):
        crypto = {}
    if not isinstance(stock, dict):
        stock = {}
    if settings.get("trade_crypto", True) is False:
        crypto = {}
    if settings.get("trade_equities", True) is False:
        stock = {}
    try:
        days = int(settings.get("days_history", 200) or 200)
    except (TypeError, ValueError):
        days = 200
    return crypto, stock, min(730, max(90, days))


def run_background_checks() -> None:
    print("Starting background alert check...")
    url, key = load_credentials()
    supabase = create_client(url, key)

    try:
        send_beta_decision_emails(supabase)
    except Exception as exc:
        print(f"Beta decision emails failed: {exc}")

    prefs_res = (
        supabase.table("user_preferences")
        .select("user_id, crypto_watchlist, stock_watchlist, settings, scoring_weights")
        .execute()
    )
    all_user_prefs = prefs_res.data or []

    catalog = {}
    max_days = 200
    for user_pref in all_user_prefs:
        crypto_list, stock_list, days_history = _watchlist(user_pref)
        max_days = max(max_days, days_history)
        for coin_id, name in crypto_list.items():
            catalog[("Crypto", str(coin_id))] = str(name)
        for ticker, name in stock_list.items():
            catalog[("Stock", str(ticker).upper())] = str(name)

    frames = refresh_price_catalog(supabase, catalog, max_days)
    refresh_due_sentiment(supabase, catalog)
    try:
        from data_fetchers import crypto_ticker
        from liquidation_levels import refresh_due as refresh_liquidation_levels

        refresh_liquidation_levels(
            supabase, catalog, (os.getenv("COINALYZE_API_KEY") or "").strip(), crypto_ticker
        )
    except Exception as exc:
        # Liquidation levels are a chart extra. They must never hold up the alert pass.
        print(f"Liquidation levels skipped: {str(exc)[:160]}")
    try:
        from evidence import refresh_due_evidence

        refresh_due_evidence(supabase, catalog)
    except Exception as exc:
        # Evidence is a nice-to-have. It must never hold up the alert pass.
        print(f"Evidence pass skipped: {str(exc)[:160]}")

    logos = load_logos(supabase, catalog)
    market_scores = load_market_scores(supabase)

    if not all_user_prefs:
        print("No user preferences found.")
        print("Background alert check finished.")
        return

    alerts_res = supabase.table("alert_preferences").select("*").execute()
    alerts_map = {row["user_id"]: row for row in (alerts_res.data or [])}

    for user_pref in all_user_prefs:
        user_id = user_pref["user_id"]
        # An account with no saved alert settings gets the new-account defaults:
        # asset and market alerts, in a daily digest only.
        alert_config = alerts_map.get(user_id, {
            "enabled": True,
            "min_score_alert": 70,
            "max_score_alert": 30,
            "market_alerts_enabled": True,
            "instant_email": False,
            "digest_enabled": True,
            "digest_hour": 8,
        })
        if alert_config.get("enabled", True) is False and not alert_config.get("market_alerts_enabled"):
            continue
        markets = market_rows(market_scores, followed_markets(user_pref))

        crypto_list, stock_list, days_history = _watchlist(user_pref)
        weights = user_pref.get("scoring_weights") or None
        results = []
        print(f"Checking assets for user {user_id}")

        for kind, assets, name_for in (
            ("Crypto", crypto_list, lambda asset_id, name: name),
            ("Stock", stock_list, lambda asset_id, name: f"{name} ({asset_id})"),
        ):
            for asset_id, name in assets.items():
                frame = frames.get((kind, canonical_asset_id(kind, asset_id)))
                scored = slice_history(frame, days_history)
                try:
                    score = _score_asset(scored, weights)
                except Exception as exc:
                    print(f"Scoring failed for {asset_id}: {exc}")
                    continue
                if score is None:
                    continue
                results.append({
                    "key": asset_id,
                    "symbol": name_for(asset_id, name),
                    "score": score,
                    "logo": logos.get(asset_market_key(kind, asset_id), ""),
                })

        try:
            opened = evaluate_alerts(
                supabase,
                user_id,
                results,
                alert_config,
                notify_email=user_email(supabase, user_id),
                send_email=send_alert_email,
                markets=markets,
            )
        except Exception as exc:
            print(f"Alerts failed for user {user_id}: {exc}")
            continue
        for alert in opened:
            print(f"Opened {alert['alert_type']} for {alert['asset_name']}")

        digest_state = send_due_digest(
            supabase,
            user_id,
            alert_config,
            results,
            user_email(supabase, user_id) if alert_config.get("digest_enabled") else None,
            send_digest_email,
            (os.getenv("APP_URL") or "https://app.angstromsignals.com").strip(),
            markets=markets,
        )
        if digest_state in ("sent", "error", "start"):
            print(f"Daily digest for user {user_id}: {digest_state}")

    print("Background alert check finished.")


if __name__ == "__main__":
    run_background_checks()
