"""
Demo page for training videos: the real Angstrom Lattice section with made-up account data (no sign-in, no
database; everything saved lives in this browser session) and live prices. Not part of the dashboard.

Address options (all optional):
  ?section=groups | sets | prism     the part shown first (default prism)
  &seed=trend | pullback            already saved: My Trend (video 3); with pullback, also the Set from video 4
  &preset=1                         open the saved Group and Set in their editors (for quick looks)

With DEMO_PRICES set (a folder of saved daily prices), "Run at a past moment" reads those, cut before 30 Oct 2024.

Run: streamlit run video/demo_app.py
"""

import copy
import os
import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_panel  # noqa: E402
import seed  # noqa: E402

if os.environ.get("DEMO_PRICES"):
    # Past-moment scans read the saved daily prices, cut before the protected hold-out (saved_prices.py), instead of
    # today's providers: nothing from 30 Oct 2024 onwards is loaded.
    import saved_prices  # noqa: E402
    from signal_library import replay_display  # noqa: E402

    replay_display.live_candles = saved_prices.candles

ASSETS = [
    ("crypto", "bitcoin", "Bitcoin"), ("crypto", "ethereum", "Ethereum"), ("crypto", "solana", "Solana"),
    ("crypto", "ripple", "XRP"), ("crypto", "binancecoin", "BNB"), ("crypto", "cardano", "Cardano"),
    ("crypto", "dogecoin", "Dogecoin"), ("crypto", "avalanche-2", "Avalanche"), ("crypto", "chainlink", "Chainlink"),
    ("equity", "AAPL", "Apple (AAPL)"), ("equity", "MSFT", "Microsoft (MSFT)"), ("equity", "NVDA", "NVIDIA (NVDA)"),
    ("equity", "AMZN", "Amazon (AMZN)"), ("equity", "META", "Meta (META)"), ("equity", "GOOGL", "Alphabet (GOOGL)"),
    ("equity", "TSLA", "Tesla (TSLA)"), ("equity", "NFLX", "Netflix (NFLX)"), ("equity", "JPM", "JPMorgan (JPM)"),
]


class Query:
    """Enough of the Supabase query builder for the Lattice pages. Filters are ignored: every list is this
    session's own."""

    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return lambda *a, **k: self

    def execute(self):
        self.data = self.rows
        return self


def _store() -> dict:
    if "_demo" not in st.session_state:
        which = set(str(st.query_params.get("seed", "")).split(","))
        st.session_state["_demo"] = {"configs": {c["id"]: c for c in seed.configs(which)}, "scans": {}, "seed": which}
    return st.session_state["_demo"]


class DemoDb:
    def table(self, name):
        s = _store()
        if name == "analysis_configs":
            return Query([{k: v for k, v in c.items() if k != "versions"} for c in s["configs"].values()])
        if name == "analysis_config_versions":
            return Query([v for c in s["configs"].values() for v in c["versions"]])
        if name == "prism_scans":
            return Query(list(s["scans"].values()))
        if name == "set_studies":
            return Query(list(s.setdefault("studies", {}).values()))
        return Query([])                 # run history and anything else: nothing yet

    def rpc(self, name, params=None):
        s, params = _store(), params or {}
        if name == "analysis_create_config":
            cid = f"cfg-{uuid.uuid4().hex[:8]}"
            s["configs"][cid] = seed.config(cid, params["kind"], copy.deepcopy(params["body"]))
            return Query(cid)
        if name == "analysis_save_version":
            c = s["configs"][params["cfg"]]
            if params.get("expected_version") != c["current_version"]:
                raise RuntimeError("conflict")
            c["current_version"] += 1
            c["versions"].append(seed._version(c["id"], c["current_version"], copy.deepcopy(params["body"])))
            return Query(c["current_version"])
        if name == "prism_put_scan":
            sid = params["p_id"] or str(uuid.uuid4())
            o = params["p_scan"]
            s["scans"][sid] = {"id": sid, "owner_id": seed.USER, "name": o["name"], "set_body": o["set"],
                               "set_source": o.get("source") or {}, "schedule": o["schedule"], "notify": o["notify"],
                               "paused": o["paused"], "assets": o["assets"], "snoozes": o["snoozes"],
                               "alert_mode": "change", "set_version": 1}
            return Query(sid)
        if name == "request_set_study":          # queued, never worked out on this page
            s.setdefault("studies", {})[params["set_hash"]] = {"set_hash": params["set_hash"], "status": "queued"}
            return Query("queued")
        if name == "prism_delete_scan":
            s["scans"].pop(params["p_id"], None)
            return Query(None)
        return Query([])


st.set_page_config(page_title="Angstrom Signals", layout="wide")
st.markdown("<style>header[data-testid='stHeader'],[data-testid='stToolbar'],[data-testid='stDecoration']"
            "{display:none!important} .block-container{padding-top:1.2rem!important}"
            "</style>", unsafe_allow_html=True)
store = _store()
if "show_provided" not in st.session_state:
    st.session_state["show_provided"] = st.query_params.get("provided", "1") != "0"
if "lattice_section" not in st.session_state:
    st.session_state["lattice_section"] = st.query_params.get("section", "prism")
    if st.query_params.get("preset"):
        if seed.MY_TREND in store["configs"]:
            st.session_state["lattice_start"] = f"saved:{seed.MY_TREND}"
        if seed.PULLBACK in store["configs"]:
            st.session_state["lattice_set_start"] = f"saved:{seed.PULLBACK}"
lattice_panel.render(st, DemoDb(), ASSETS, user_id=seed.USER)
