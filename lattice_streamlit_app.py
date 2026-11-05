"""
A tiny Streamlit page for CI: the real Lattice Group editor (lattice_view.render) with no database, so
lattice_streamlit_check.js can tap, click and check that every edit goes to Python and comes back checked.
Not part of the dashboard.

Run: streamlit run lattice_streamlit_app.py
"""

import streamlit as st

import lattice_view


class NoDb:
    def table(self, name):
        raise RuntimeError("no database on this test page")

    def rpc(self, name, params=None):
        raise RuntimeError("no database on this test page")


st.set_page_config(page_title="Lattice editor check", layout="wide")
lattice_view.render(st, NoDb(), [("crypto", "bitcoin", "Bitcoin")], user_id="test")
