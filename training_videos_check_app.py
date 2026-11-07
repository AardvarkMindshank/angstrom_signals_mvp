"""A page with the Help and guides video links, for the browser check (training_videos_check.js). Not the app."""
import streamlit as st

import training_videos as tv

st.set_page_config(page_title="Training videos check", layout="wide")
st.markdown("**🎬 Training videos**")
tv.all_links(st, key="check")
