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

# Caching
@st.cache_data(ttl=300)
def load_crypto(coin_id, days):
    return fetch_crypto_data(coin_id, days)

@st.cache_data(ttl=300)
def load_stock(ticker):
    return fetch_stock_data(ticker, period="6mo")

# --- Load & score data ---
def process_watchlist(watchlist, is_crypto=True):
    results = []
    for key, name in watchlist.items():
        with st.spinner(f"Loading {name}..."):
            if is_crypto:
                df = load_crypto(key, days_history)
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

# --- Tables with graphical scores ---
def style_and_show_table(results, title, key_prefix):
    if not results:
        return None, None
    df = pd.DataFrame(results)
    df = df.sort_values("score", ascending=False, na_position="last")

    display_cols = ["symbol", "score", "label", "latest_price", "rsi"]
    if show_extra_metrics:
        display_cols += ["change_7d", "atr_pct", "volume_ratio"]

    st.subheader(title)
    column_config = {
        "symbol": st.column_config.TextColumn("Asset"),
        "score": st.column_config.ProgressColumn(
            "Score",
            help="Composite technical score (0–100, higher = more bullish)",
            min_value=0,
            max_value=100,
            format="%d",
        ),
        "label": st.column_config.TextColumn("Signal"),
        "latest_price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "rsi": st.column_config.NumberColumn("RSI", format="%.1f"),
        "change_7d": st.column_config.NumberColumn("7d %", format="%.1f%%"),
        "atr_pct": st.column_config.NumberColumn("ATR %", help="Average True Range as % of price (volatility)", format="%.2f"),
        "volume_ratio": st.column_config.NumberColumn("Vol Ratio", help="Current volume vs 20-day average", format="%.2f"),
    }

    event = st.dataframe(
        df[display_cols],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=min(400, 40 + len(df) * 35),
        on_select="rerun",
        selection_mode="single-row",
        key=f"table_{key_prefix}",
    )
    return event, df

# Initialize session state for selection
if "selected_type" not in st.session_state:
    st.session_state.selected_type = "Crypto"
if "selected_key" not in st.session_state:
    st.session_state.selected_key = list(CRYPTO_WATCHLIST.keys())[0]

crypto_event, crypto_df_sorted = style_and_show_table(crypto_results, "Crypto Scores", "crypto")
stock_event, stock_df_sorted = style_and_show_table(stock_results, "Equity Scores", "stock")

# Robust selection handling — only one table can have a selection
def get_selected_key(event, df_sorted):
    if (event and hasattr(event, "selection") and event.selection
            and event.selection.rows and len(event.selection.rows) > 0):
        idx = event.selection.rows[0]
        if idx < len(df_sorted):
            return df_sorted.iloc[idx]["key"]
    return None

crypto_key = get_selected_key(crypto_event, crypto_df_sorted)
stock_key = get_selected_key(stock_event, stock_df_sorted)

# Clear the other table's selection when one is chosen
if crypto_key and not stock_key:
    st.session_state.selected_type = "Crypto"
    st.session_state.selected_key = crypto_key
    # Clear stock table selection
    if "table_stock" in st.session_state:
        st.session_state["table_stock"] = {"selection": {"rows": [], "columns": []}}
elif stock_key and not crypto_key:
    st.session_state.selected_type = "Stock"
    st.session_state.selected_key = stock_key
    # Clear crypto table selection
    if "table_crypto" in st.session_state:
        st.session_state["table_crypto"] = {"selection": {"rows": [], "columns": []}}
elif crypto_key and stock_key:
    # Both selected — prefer the one that differs from current (or last click)
    if st.session_state.selected_type != "Crypto" or st.session_state.selected_key != crypto_key:
        st.session_state.selected_type = "Crypto"
        st.session_state.selected_key = crypto_key
        if "table_stock" in st.session_state:
            st.session_state["table_stock"] = {"selection": {"rows": [], "columns": []}}
    else:
        st.session_state.selected_type = "Stock"
        st.session_state.selected_key = stock_key
        if "table_crypto" in st.session_state:
            st.session_state["table_crypto"] = {"selection": {"rows": [], "columns": []}}

# --- Interactive Chart ---
st.subheader("Interactive Chart")
st.caption(f"Currently showing: **{st.session_state.selected_type}** — click a row in either table above to change")

# Reliable backup selector (always works)
col1, col2 = st.columns([1, 3])
with col1:
    backup_type = st.selectbox("Type", ["Crypto", "Stock"], index=0 if st.session_state.selected_type == "Crypto" else 1, key="backup_type")
with col2:
    if backup_type == "Crypto":
        options = list(CRYPTO_WATCHLIST.keys())
        backup_key = st.selectbox("Asset", options, index=options.index(st.session_state.selected_key) if st.session_state.selected_key in options else 0, format_func=lambda x: CRYPTO_WATCHLIST[x], key="backup_crypto")
    else:
        options = list(STOCK_WATCHLIST.keys())
        backup_key = st.selectbox("Asset", options, index=options.index(st.session_state.selected_key) if st.session_state.selected_key in options else 0, format_func=lambda x: f"{STOCK_WATCHLIST[x]} ({x})", key="backup_stock")

if backup_type != st.session_state.selected_type or backup_key != st.session_state.selected_key:
    st.session_state.selected_type = backup_type
    st.session_state.selected_key = backup_key
    st.rerun()

# Load data based on current selection
if st.session_state.selected_type == "Crypto":
    df_chart = load_crypto(st.session_state.selected_key, days_history)
    title = CRYPTO_WATCHLIST.get(st.session_state.selected_key, st.session_state.selected_key)
else:
    df_chart = load_stock(st.session_state.selected_key)
    title = f"{STOCK_WATCHLIST.get(st.session_state.selected_key, st.session_state.selected_key)} ({st.session_state.selected_key})"

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

st.sidebar.markdown("---")
st.sidebar.info("Data is cached for 5 minutes. Refresh the page to update.")
st.sidebar.caption("Edit the watchlists at the top of `app.py` to add or remove assets.")
st.sidebar.caption("Click any row in the tables above to update the chart and score breakdown.")
