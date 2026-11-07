"""Browser check page for the table's Groups and Sets sections (table_columns_check.js). Not the app: it draws one
watchlist table with the app's own table script and fold styles (read from app.py) and the real cells."""
import ast
import re
from pathlib import Path

import streamlit as st

import signals_view
import table_columns as tc

SOURCE = Path(__file__).with_name("app.py").read_text()
TREE = ast.parse(SOURCE)


def _constant(name, env):
    for node in TREE.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == name for t in node.targets):
            return eval(compile(ast.Expression(node.value), "app.py", "eval"), {}, env)   # noqa: S307
    raise KeyError(name)


bind = _constant("_COMMENT_BIND_JS", {})
JS = _constant("_SCORE_TABLE_JS", {"_COMMENT_BIND_JS": bind})
CSS = "\n".join(re.findall(r'"(\.ang-table[^"]*)",', SOURCE))

st.set_page_config(page_title="Table columns check", layout="wide")
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
groups = [{"key": "starter:trend", "part": "groups", "name": "Trend", "cluster": "trend", "config": None, "version": None},
          {"key": "saved:g1", "part": "groups", "name": "My Trend", "cluster": None, "config": "g1", "version": 2}]
sets = [{"key": "saved:s1", "part": "sets", "name": "Pullback in an uptrend", "cluster": None, "config": "s1",
         "version": 1},
        {"key": "saved:s2", "part": "sets", "name": "Breakout with volume", "cluster": None, "config": "s2",
         "version": 1}]
rows = [("Bitcoin", 62.0, {"saved:g1": {"value": 41.0, "label": "Bullish"}, "saved:s1": {"answer": "yes", "why": "every line holds"},
                           "saved:s2": {"answer": "no", "why": "volume ratio 1.2 is below 2"}}),
        ("Ethereum", -18.0, {"saved:g1": {"value": -22.0, "label": "Neutral"}, "saved:s1": {"answer": "no"},
                             "saved:s2": {"answer": "unknown", "why": "volume missing"}})]


def th(text, sec="", fold=False, col=0):
    btn = (f"<button type='button' data-fold='{sec}' style='border:none;background:none'>◂</button>" if fold else "")
    attr = f" data-sec='{sec}'" if sec else ""
    return (f"<th{attr}>{btn}<button type='button' data-sort-col='{col}' style='border:none;background:none'>"
            f"{text}<span data-sort-mark></span></button></th>")


head = (th("Asset", col=0) + th("📈 Trend", "g", True, 1) + th("My Trend", "g", col=2)
        + "<th data-sec-folded='g'><button type='button' data-fold='g'>▸ Groups</button></th>"
        + th("Pullback in an uptrend", "s", True, 4) + th("Breakout with volume", "s", col=5)
        + "<th data-sec-folded='s'><button type='button' data-fold='s'>▸ Sets</button></th>" + th("Price", col=7))
body = ""
for name, trend, extra in rows:
    body += (f"<tr><td data-sort='{name.lower()}'>{name}</td>"
             + signals_view.table_cell("trend", {"trend": trend}, None, section="g")
             + tc.group_cell(groups[1], extra["saved:g1"]) + tc.folded_cell("groups", [])
             + tc.set_cell(sets[0], extra["saved:s1"]) + tc.set_cell(sets[1], extra["saved:s2"])
             + tc.folded_cell("sets", [extra["saved:s1"], extra["saved:s2"]]) + "<td data-sort='1'>$1</td></tr>")
html = f"<table class='ang-table' data-table='check'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
table = st.components.v2.component("score_table_check", js=JS, isolate_styles=False)
picked = table(key="t", data=html, on_picked_change=lambda: None).picked
st.markdown(f"<div id='picked'>picked: {picked or ''}</div>", unsafe_allow_html=True)
