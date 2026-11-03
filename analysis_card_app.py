"""
A tiny Streamlit page for CI: shows the real Analysis card (analysis_card.render) with the dashboard's card styles,
so analysis_card_check.js can press Analyse, open the Group details and take screenshots. Not part of the dashboard.

Candles are live from Yahoo unless "--synthetic" is passed. There is no database here, so stored-data readings
(Bitcoin ETF flows, derivatives) show as missing.

Run: streamlit run analysis_card_app.py [-- --synthetic]
"""

import sys

import streamlit as st

import analysis_card

if "--synthetic" in sys.argv:
    import chart_data
    from analysis_card_measure import synthetic_load_candles

    chart_data.load_candles = synthetic_load_candles


class NoDb:
    def table(self, name):
        raise RuntimeError("no database on this test page")


st.set_page_config(page_title="Analysis card check", layout="wide")
# The dashboard's own card styles (app.py), so the screenshots look like the site.
st.markdown(
    "<style>html{--ang-surface:#ffffff;--ang-border:#e5e7eb;--ang-text:#111827;--ang-muted:#6b7280;"
    "--ang-track:#e5e7eb;}"
    ".ang-card{background:var(--ang-surface);color:var(--ang-text);border:1px solid var(--ang-border);"
    "border-radius:10px;padding:12px 16px;}"
    ".ang-kicker{font-size:.8rem;color:var(--ang-muted);margin-bottom:4px;}</style>",
    unsafe_allow_html=True,
)
assets = {"bitcoin": ("Crypto", "Bitcoin"), "ethereum": ("Crypto", "Ethereum"), "AAPL": ("Stock", "Apple (AAPL)")}
pick = st.radio("Asset", list(assets), horizontal=True, key="asset", format_func=lambda k: assets[k][1])
st.caption("Test page: " + ("made-up candles" if "--synthetic" in sys.argv else "live Yahoo candles")
           + "; no database, so stored-data readings show as missing.")
analysis_card.render(st, NoDb(), assets[pick][0], pick, assets[pick][1])
