"""
Standalone Background Alert Worker for Angstrom Signals
Runs independently via cron or GitHub Actions to check thresholds and populate notifications.
"""

import os
import pandas as pd
from supabase import create_client
from data_fetchers import fetch_crypto_data, fetch_stock_data
from scoring import calculate_indicators, compute_score

# Initialize Supabase using environment variables or fallback to secrets config
SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Fallback for local testing if streamlit secrets.toml exists
    try:
        import streamlit as st
        SUPABASE_URL = st.secrets["supabase"]["url"]
        SUPABASE_KEY = st.secrets["supabase"]["key"]
    except Exception:
        raise ValueError("Supabase URL and Key must be provided via environment variables or Streamlit secrets.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_background_checks():
    print("Starting background alert check worker...")
    
    try:
        # Fetch all user preferences to know who to check watchlists for
        prefs_res = supabase.table("user_preferences").select("user_id, crypto_watchlist, stock_watchlist, settings").execute()
        all_user_prefs = prefs_res.data
        
        if not all_user_prefs:
            print("No user preferences found.")
            return

        # Fetch all alert preferences
        alerts_res = supabase.table("alert_preferences").select("*").execute()
        alerts_map = {row["user_id"]: row for row in alerts_res.data}

        for user_pref in all_user_prefs:
            user_id = user_pref["user_id"]
            alert_config = alerts_map.get(user_id, {"enabled": True, "min_score_alert": 70, "max_score_alert": 30})
            
            if not alert_config.get("enabled", True):
                continue

            crypto_list = user_pref.get("crypto_watchlist", {})
            stock_list = user_pref.get("stock_watchlist", {})
            settings = user_pref.get("settings", {})
            days_history = settings.get("days_history", 200)

            print(f"Checking assets for user: {user_id}")

            results = []

            # Process Crypto Watchlist
            for key, name in crypto_list.items():
                try:
                    df = fetch_crypto_data(key, days_history)
                    if not df.empty and len(df) >= 15:
                        df = calculate_indicators(df)
                        res = compute_score(df)
                        if isinstance(res, dict):
                            results.append({
                                "key": key,
                                "symbol": name,
                                "score": res.get("score")
                            })
                except Exception as e:
                    print(f"Error fetching crypto {key} for user {user_id}: {e}")

            # Process Stock Watchlist
            for key, name in stock_list.items():
                try:
                    df = fetch_stock_data(key, period="1y")
                    if not df.empty and len(df) >= 15:
                        df = calculate_indicators(df)
                        res = compute_score(df)
                        if isinstance(res, dict):
                            results.append({
                                "key": key,
                                "symbol": f"{name} ({key})",
                                "score": res.get("score")
                            })
                except Exception as e:
                    print(f"Error fetching stock {key} for user {user_id}: {e}")

            # Evaluate thresholds and record notifications
            evaluate_and_store_notifications(user_id, results, alert_config)

        print("Background alert check worker completed successfully.")

    except Exception as e:
        print(f"Error in background worker execution: {e}")

def evaluate_and_store_notifications(user_id, results, alerts_config):
    min_thresh = float(alerts_config.get("min_score_alert", 70))
    max_thresh = float(alerts_config.get("max_score_alert", 30))

    try:
        existing = supabase.table("user_notifications").select("asset_symbol, alert_type").eq("user_id", user_id).execute().data
        existing_keys = {(n["asset_symbol"], n["alert_type"]) for n in existing}
    except Exception:
        existing_keys = set()

    for r in results:
        score = r.get("score")
        if score is None or pd.isna(score):
            continue
        
        symbol = r.get("key")
        name = r.get("symbol")
        
        if score >= min_thresh:
            alert_type = "BULLISH_THRESHOLD"
            msg = f"Score reached {score:.1f}/100 (Bullish setup)"
            if (symbol, alert_type) not in existing_keys:
                supabase.table("user_notifications").insert({
                    "user_id": user_id,
                    "asset_symbol": symbol,
                    "asset_name": name,
                    "alert_type": alert_type,
                    "message": msg
                }).execute()
                print(f"Triggered Bullish alert for {name} ({score:.1f})")

        elif score <= max_thresh:
            alert_type = "BEARISH_THRESHOLD"
            msg = f"Score dropped to {score:.1f}/100 (Bearish/Oversold setup)"
            if (symbol, alert_type) not in existing_keys:
                supabase.table("user_notifications").insert({
                    "user_id": user_id,
                    "asset_symbol": symbol,
                    "asset_name": name,
                    "alert_type": alert_type,
                    "message": msg
                }).execute()
                print(f"Triggered Bearish alert for {name} ({score:.1f})")

if __name__ == "__main__":
    run_background_checks()