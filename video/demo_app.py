"""
Demo page for training videos: the real Angstrom Lattice section with made-up account data (no sign-in, no
database; scans live in this browser session) and live prices. Not part of the dashboard.

Run: streamlit run video/demo_app.py
"""

import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lattice_panel  # noqa: E402


class Query:
    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return lambda *a, **k: self

    def execute(self):
        self.data = self.rows
        return self


class DemoDb:
    def table(self, name):
        if name == "prism_scans":
            return Query(list(st.session_state.setdefault("_scans", {}).values()))
        if name in ("prism_scan_runs", "prism_scan_latches"):
            return Query([])
        raise RuntimeError("demo page")

    def rpc(self, name, params=None):
        scans = st.session_state.setdefault("_scans", {})
        if name == "prism_put_scan":
            sid = params["p_id"] or str(uuid.uuid4())
            o = params["p_scan"]
            scans[sid] = {"id": sid, "owner_id": "demo", "name": o["name"], "set_body": o["set"],
                          "set_source": o.get("source") or {}, "schedule": o["schedule"], "notify": o["notify"],
                          "paused": o["paused"], "assets": o["assets"], "snoozes": o["snoozes"],
                          "alert_mode": "change", "set_version": 1}
            return Query(sid)
        if name == "prism_delete_scan":
            scans.pop(params["p_id"], None)
            return Query(None)
        raise RuntimeError("demo page")


st.set_page_config(page_title="Angstrom Signals", layout="wide")
st.markdown("<style>header[data-testid='stHeader'],[data-testid='stToolbar'],[data-testid='stDecoration']"
            "{display:none!important} .block-container{padding-top:1.2rem!important}"
            ".st-key-video_caption_hide{display:none}</style>", unsafe_allow_html=True)
st.session_state.setdefault("lattice_section", "prism")
lattice_panel.render(st, DemoDb(), [
    ("crypto", "bitcoin", "Bitcoin"), ("crypto", "ethereum", "Ethereum"), ("crypto", "solana", "Solana"),
    ("crypto", "chainlink", "Chainlink"), ("equity", "COIN", "Coinbase (COIN)"), ("equity", "NVDA", "NVIDIA (NVDA)"),
], user_id="demo")
