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

# Page config
st.set_page_config(
    page_title="angstrom signals - level 1",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("angstrom signals - level 1")
st.markdown("### Crypto & Equity Signals Dashboard")
st.caption("Research prototype • Multi-factor technical scoring • Not financial advice")

# --- Watchlist (easy to edit) ---
CRYPTO_WATCHLIST = {
    "bitcoin": "Bitcoin (BTC)",
    "ethereum": "Ethereum (ETH)",
    "solana": "Solana (SOL)",
    "cardano": "Cardano (ADA)",
    "ripple": "XRP",
}

STOCK_WATCHLIST = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
}

# Sidebar
st.sidebar.header("Settings")
days_history = st.sidebar.slider("Days of history", 30, 180, 90)
show_reasons = st.sidebar.checkbox("Show score breakdown", value=True)
show_extra_metrics = st.sidebar.checkbox("Show extra metrics (7d, ATR, volume)", value=True)

# Caching — data refreshes every 5 minutes
@st.cache_data(ttl=300)
def load_crypto(coin_id, days):
    return fetch_crypto_data(coin_id, days)

@st.cache_data(ttl=300)
def load_stock(ticker):
    return fetch_stock_data(ticker, period="6mo")

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
                    import time
                    time.sleep(0.8)
                else:
                    df = load_stock(key)
                if not df.empty:
                    df = calculate_indicators(df)
                    result = compute_score(df)
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

    # --- Tables with graphical scores (custom colored bars) ---
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
        if score is None or pd.isna(score):
            pct = 0
            color = "#6b7280"
            label = "—"
        else:
            pct = max(0, min(100, float(score)))
            color = score_bar_color(score)
            label = f"{int(score)}"
        return f'''
        <div style="display:flex;align-items:center;gap:8px;width:100%;">
            <div style="flex:1;background:#e5e7eb;border-radius:6px;height:16px;overflow:hidden;">
                <div style="width:{pct}%;background:{color};height:100%;border-radius:6px;"></div>
            </div>
            <span style="min-width:32px;font-weight:600;font-size:0.95em;">{label}</span>
        </div>
        '''

    def style_and_show_table(results, title):
        if not results:
            return
        df = pd.DataFrame(results)
        df = df.sort_values("score", ascending=False, na_position="last")

        st.subheader(title)

        # Column widths — everything on one row
        if show_extra_metrics:
            widths = [2.0, 2.2, 1.4, 1.2, 0.8, 0.9, 0.9, 1.0]
            headers = ["Asset", "Score", "Signal", "Price", "RSI", "7d %", "ATR %", "Vol"]
        else:
            widths = [2.4, 2.6, 1.6, 1.4, 1.0]
            headers = ["Asset", "Score", "Signal", "Price", "RSI"]

        # Header
        h = st.columns(widths)
        for i, header in enumerate(headers):
            h[i].markdown(f"**{header}**")

        # Data rows
        for _, row in df.iterrows():
            c = st.columns(widths)
            c[0].write(row["symbol"])
            c[1].markdown(render_score_bar(row["score"]), unsafe_allow_html=True)
            c[2].write(row.get("label") or "—")
            price = row.get("latest_price")
            c[3].write(f"${price:,.2f}" if pd.notna(price) else "—")
            rsi = row.get("rsi")
            c[4].write(f"{rsi:.1f}" if pd.notna(rsi) else "—")

            if show_extra_metrics:
                chg = row.get("change_7d")
                atr = row.get("atr_pct")
                vol = row.get("volume_ratio")
                c[5].write(f"{chg:+.1f}%" if pd.notna(chg) else "—")
                c[6].write(f"{atr:.2f}" if pd.notna(atr) else "—")
                c[7].write(f"{vol:.2f}" if pd.notna(vol) else "—")

            st.markdown("<hr style='margin:2px 0;border:none;border-top:1px solid #f0f0f0;'>", unsafe_allow_html=True)

    style_and_show_table(crypto_results, "Crypto Scores")
    style_and_show_table(stock_results, "Equity Scores")

    # --- Interactive Chart ---
    st.subheader("Interactive Chart")

    # Simple, reliable selector
    col1, col2 = st.columns([1, 3])
    with col1:
        asset_type = st.selectbox("Type", ["Crypto", "Stock"], key="asset_type")
    with col2:
        if asset_type == "Crypto":
            options = list(CRYPTO_WATCHLIST.keys())
            asset_key = st.selectbox(
                "Asset",
                options,
                format_func=lambda x: CRYPTO_WATCHLIST[x],
                key="asset_crypto",
            )
            df_chart = load_crypto(asset_key, days_history)
            title = CRYPTO_WATCHLIST[asset_key]
        else:
            options = list(STOCK_WATCHLIST.keys())
            asset_key = st.selectbox(
                "Asset",
                options,
                format_func=lambda x: f"{STOCK_WATCHLIST[x]} ({x})",
                key="asset_stock",
            )
            df_chart = load_stock(asset_key)
            title = f"{STOCK_WATCHLIST[asset_key]} ({asset_key})"

    if not df_chart.empty:
        df_chart = calculate_indicators(df_chart)

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.55, 0.2, 0.25],
            subplot_titles=(f"{title} Price", "Volume", "RSI (14)"),
        )

        fig.add_trace(
            go.Candlestick(
                x=df_chart.index,
                open=df_chart["open"],
                high=df_chart["high"],
                low=df_chart["low"],
                close=df_chart["close"],
                name="Price",
            ),
            row=1, col=1,
        )

        if "sma_20" in df_chart.columns:
            fig.add_trace(
                go.Scatter(x=df_chart.index, y=df_chart["sma_20"], name="SMA 20",
                           line=dict(color="orange", width=1.5)),
                row=1, col=1,
            )
        if "sma_50" in df_chart.columns:
            fig.add_trace(
                go.Scatter(x=df_chart.index, y=df_chart["sma_50"], name="SMA 50",
                           line=dict(color="royalblue", width=1.5)),
                row=1, col=1,
            )

        if "BBU_20_2.0" in df_chart.columns:
            fig.add_trace(
                go.Scatter(x=df_chart.index, y=df_chart["BBU_20_2.0"], name="BB Upper",
                           line=dict(color="gray", width=1, dash="dot"), showlegend=False),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(x=df_chart.index, y=df_chart["BBL_20_2.0"], name="BB Lower",
                           line=dict(color="gray", width=1, dash="dot"), fill="tonexty",
                           fillcolor="rgba(128,128,128,0.08)", showlegend=False),
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
                go.Scatter(x=df_chart.index, y=df_chart["rsi"], name="RSI",
                           line=dict(color="purple", width=1.5)),
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

        st.plotly_chart(fig, use_container_width=True)

        # Current score metrics for selected asset
        result = compute_score(df_chart)
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Current Score", f"{result['score']}/100", result["label"])
        if result.get("change_7d") is not None:
            col_b.metric("7-Day Change", f"{result['change_7d']:+.1f}%")
        if result.get("atr_pct") is not None:
            col_c.metric("Volatility (ATR%)", f"{result['atr_pct']:.2f}%")

        # Score breakdown ONLY for the selected asset
        if show_reasons and result.get("reasons") and result.get("score") is not None:
            st.subheader(f"Score Breakdown — {title}")
            color = "green" if result["score"] >= 60 else "orange" if result["score"] >= 45 else "red"
            st.markdown(
                f"<span style='color:{color};font-weight:bold;font-size:1.1em'>{result['score']}/100 ({result['label']})</span>",
                unsafe_allow_html=True,
            )
            for reason in result["reasons"]:
                st.caption(f"• {reason}")

    else:
        st.warning("Could not load chart data. Check your internet connection.")

# Run the auto-refreshing dashboard
live_dashboard()

st.sidebar.markdown("---")
st.sidebar.info("Dashboard and data auto-refresh every 5 minutes.")
st.sidebar.caption("Edit the watchlists at the top of `app.py` to add or remove assets.")
st.sidebar.caption("Use the Type and Asset dropdowns under the chart to select what to view.")
