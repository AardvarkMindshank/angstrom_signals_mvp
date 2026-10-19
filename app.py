"""
Phase 1 MVP – Crypto & Equity Signals Dashboard
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_fetchers import fetch_crypto_data, fetch_stock_data, get_current_price_crypto, get_current_price_stock
from scoring import calculate_indicators, compute_score

# Page config
st.set_page_config(
    page_title="Signals MVP",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Crypto & Equity Signals Dashboard – Phase 1")
st.caption("Simple research prototype. Edit the watchlist below or in the code to add more assets.")

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

# Sidebar controls
st.sidebar.header("Settings")
days_history = st.sidebar.slider("Days of history", 30, 180, 90)
show_reasons = st.sidebar.checkbox("Show score reasons", value=True)

# Cache data fetching so it doesn't re-download every interaction
@st.cache_data(ttl=300)  # cache for 5 minutes
def load_crypto(coin_id, days):
    return fetch_crypto_data(coin_id, days)

@st.cache_data(ttl=300)
def load_stock(ticker):
    return fetch_stock_data(ticker, period="6mo")

# --- Main dashboard ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Crypto Scores")
    crypto_results = []
    for coin_id, name in CRYPTO_WATCHLIST.items():
        with st.spinner(f"Loading {name}..."):
            df = load_crypto(coin_id, days_history)
            if not df.empty:
                df = calculate_indicators(df)
                result = compute_score(df)
                result["symbol"] = name
                result["type"] = "Crypto"
                crypto_results.append(result)
            else:
                crypto_results.append({
                    "symbol": name, "score": None, "label": "No data",
                    "reasons": [], "latest_price": None, "rsi": None, "type": "Crypto"
                })

with col2:
    st.subheader("Equity Scores")
    stock_results = []
    for ticker, name in STOCK_WATCHLIST.items():
        with st.spinner(f"Loading {name}..."):
            df = load_stock(ticker)
            if not df.empty:
                df = calculate_indicators(df)
                result = compute_score(df)
                result["symbol"] = f"{name} ({ticker})"
                result["type"] = "Stock"
                stock_results.append(result)
            else:
                stock_results.append({
                    "symbol": f"{name} ({ticker})", "score": None, "label": "No data",
                    "reasons": [], "latest_price": None, "rsi": None, "type": "Stock"
                })

# Display separate tables
display_cols = ["symbol", "score", "label", "latest_price", "rsi"]

st.subheader("Crypto Scores")
crypto_df = pd.DataFrame(crypto_results)
if not crypto_df.empty:
    st.dataframe(
        crypto_df[display_cols].sort_values("score", ascending=False, na_position="last"),
        use_container_width=True,
        hide_index=True
    )

st.subheader("Equity Scores")
stock_df = pd.DataFrame(stock_results)
if not stock_df.empty:
    st.dataframe(
        stock_df[display_cols].sort_values("score", ascending=False, na_position="last"),
        use_container_width=True,
        hide_index=True
    )

if show_reasons:
    st.subheader("Score Details")
    all_results = crypto_results + stock_results
    for result in all_results:
        if result.get("reasons"):
            st.write(f"**{result['symbol']}** ({result['score']}/100 – {result['label']})")
            for reason in result["reasons"]:
                st.write(f"- {reason}")
            st.divider()

# Chart section
st.subheader("Price Chart")
chart_asset_type = st.radio("Asset type", ["Crypto", "Stock"], horizontal=True)

if chart_asset_type == "Crypto":
    selected = st.selectbox("Select crypto", list(CRYPTO_WATCHLIST.keys()), 
                            format_func=lambda x: CRYPTO_WATCHLIST[x])
    df_chart = load_crypto(selected, days_history)
    title = CRYPTO_WATCHLIST[selected]
else:
    selected = st.selectbox("Select stock", list(STOCK_WATCHLIST.keys()),
                            format_func=lambda x: f"{STOCK_WATCHLIST[x]} ({x})")
    df_chart = load_stock(selected)
    title = f"{STOCK_WATCHLIST[selected]} ({selected})"

if not df_chart.empty:
    df_chart = calculate_indicators(df_chart)
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart.index,
        open=df_chart["open"],
        high=df_chart["high"],
        low=df_chart["low"],
        close=df_chart["close"],
        name="Price"
    ))
    
    if "sma_20" in df_chart.columns:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["sma_20"], 
                                 name="SMA 20", line=dict(color="orange", width=1)))
    if "sma_50" in df_chart.columns:
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart["sma_50"], 
                                 name="SMA 50", line=dict(color="blue", width=1)))
    
    fig.update_layout(
        title=f"{title} – Price & Moving Averages",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        height=500,
        xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Show latest score for the selected asset
    result = compute_score(df_chart)
    st.metric(label=f"Current Score for {title}", 
              value=f"{result['score']}/100", 
              delta=result["label"])
else:
    st.warning("Could not load chart data. Check your internet connection.")

st.sidebar.info("Tip: Data is cached for 5 minutes. Refresh the page or wait to update prices.")
st.sidebar.markdown("---")
st.sidebar.markdown("**Phase 1 MVP** – Edit `app.py` to change the watchlist.")
