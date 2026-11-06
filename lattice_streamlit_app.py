"""
A tiny Streamlit page for CI: the real Angstrom Lattice section (lattice_panel.render) with no database, so
lattice_streamlit_check.js can tap, click and check that every edit goes to Python and comes back checked.
Not part of the dashboard.

Run: streamlit run lattice_streamlit_app.py
"""

import uuid

import streamlit as st

import lattice_panel


class Query:
    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):                       # select, order, in_, limit, eq: no filtering needed here
        return lambda *a, **k: self

    def execute(self):
        self.data = self.rows
        return self


class NoDb:
    """No database: Groups and Sets can't be saved here; Prism Scans live in this browser session only."""

    def table(self, name):
        if name == "prism_scans":
            return Query(list(st.session_state.setdefault("_scans", {}).values()))
        if name in ("prism_scan_runs", "prism_scan_latches"):
            return Query([])
        raise RuntimeError("no database on this test page")

    def rpc(self, name, params=None):
        scans = st.session_state.setdefault("_scans", {})
        if name == "prism_put_scan":
            sid = params["p_id"] or str(uuid.uuid4())
            obj = params["p_scan"]
            scans[sid] = {"id": sid, "owner_id": "test", "name": obj["name"], "set_body": obj["set"],
                          "set_source": obj.get("source") or {}, "schedule": obj["schedule"], "notify": obj["notify"],
                          "paused": obj["paused"], "assets": obj["assets"], "snoozes": obj["snoozes"],
                          "alert_mode": "change", "set_version": 1}
            return Query(sid)
        if name == "prism_delete_scan":
            scans.pop(params["p_id"], None)
            return Query(None)
        raise RuntimeError("no database on this test page")


st.set_page_config(page_title="Lattice editor check", layout="wide")
st.session_state.setdefault("lattice_open", True)
lattice_panel.render(st, NoDb(), [("crypto", "bitcoin", "Bitcoin"), ("equity", "COIN", "Coinbase (COIN)")],
                    user_id="test")
