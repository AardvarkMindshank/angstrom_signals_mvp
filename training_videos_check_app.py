"""A page with the Help and guides video links, for the browser check (training_videos_check.js). Not the app."""
import streamlit as st

import training_videos as tv

st.set_page_config(page_title="Training videos check", layout="wide")
if st.query_params.get("view") == tv.VIEW:
    tv.render_popout(st, st.query_params.get("v"))
    st.stop()
if st.query_params.get("view") == "advisor":
    import lattice_panel

    lattice_panel.render_popout(st, None, "check")
    st.stop()
tv.install(st)
st.markdown("**🎬 Training videos**")
tv.all_links(st, key="check")
import lattice_panel  # noqa: E402

lattice_panel._advisor_button(st)      # the ✨ AI button opens the Advisor in its own window too
