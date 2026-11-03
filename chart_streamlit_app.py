"""
A tiny Streamlit page for CI: mounts the real TradingView chart component (lw_chart.js)
the same way app.py does, so chart_streamlit_check.js can test it through real
Streamlit reruns. Not part of the dashboard.

Run: streamlit run chart_streamlit_app.py -- <fixtures folder>
"""

import json
import sys
from pathlib import Path

import streamlit as st

FIXTURES = Path(sys.argv[1] if len(sys.argv) > 1 else "out/fixtures")
JS = (Path(__file__).resolve().parent / "lw_chart.js").read_text(encoding="utf-8")
chart = st.components.v2.component("lw_chart", js=JS, isolate_styles=False)

st.title("Chart component check")
name = st.radio("Fixture", ["crypto_4h_all", "crypto_4h_overlay", "equity_daily_earnings"], horizontal=True, key="fixture")
st.button("Rerun", key="rerun")
st.checkbox("Unrelated toggle", key="toggle")
payload = json.loads((FIXTURES / f"{name}.json").read_text())
chart(key="lw_chart", data=payload)
st.write("Reruns:", st.session_state.setdefault("runs", 0))
st.session_state["runs"] += 1
