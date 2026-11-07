"""Browser check page for 🔍 Why these readings (why_check.js). Not the app: made-up daily bars, the real blocks
(why_panel.py) drawn the way app._render_why_panel draws them, with Trend, two of your own and a waiting
hourly column."""
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, "video")
import group_readings as gr  # noqa: E402
import seed  # noqa: E402
import table_columns as tc  # noqa: E402
import why_panel as wp  # noqa: E402
from signal_library import certify as cf  # noqa: E402
from tests.replay_helpers import full_indicators  # noqa: E402

st.set_page_config(page_title="Why check", layout="wide")
frame = full_indicators(cf.synthetic_crypto(days=420, seed=11).histories["1D"].raw)
later = frame.index[-1] + pd.Timedelta(days=3)
ctx, _ = gr.stored_context(frame, "crypto", later, asset_id="x")
result = gr.score(frame, "crypto", later)
specs = tc.resolve({"groups": ["starter:trend", "starter:flow", "saved:cfg-my-trend"], "sets": ["saved:cfg-pullback"]},
                   seed.configs({"pullback"}))
specs.append({"key": "saved:fast", "part": "sets", "name": "Hourly dip", "config": "fast", "version": 1,
              "cluster": None, "doc": {"members": [{"ref": {"timeframe": "1h"}}]}})
items = wp.items(specs, ctx, result["readings"])
focus = st.query_params.get("focus", "saved:cfg-pullback")
with st.expander("🔍 Why these readings — Bitcoin", expanded=True):
    for item in items:
        with st.expander(item["title"], expanded=item["key"] == focus, key=f"why_{item['key']}"):
            st.html(wp.block_html(item))
            st.button("Open in Lattice", icon=":material/hub:", type="tertiary", key=f"why_open_{item['key']}",
                      help=f"See or change how {item['name']} is built, in Angstrom Lattice")
