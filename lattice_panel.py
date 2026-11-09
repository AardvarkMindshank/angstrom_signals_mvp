"""
Angstrom Lattice, for every signed-in account (docs/design/lattice_prism.md §8; build stages 5 and 6).

One section on the dashboard with four parts across the top: Signal Groups, Signal Sets, Prism Scan and
Strategies (coming later). Only the chosen part is drawn; saved Groups and Sets are read at most once a minute,
and Prism only does real work when Run now is pressed.
"""

from __future__ import annotations

TITLE = "Angstrom Lattice"
ICON = ":material/hub:"
# (icon, name, one line on what it is for); the lines make the bar's hover note.
SECTIONS = {
    "groups": (":material/layers:", "Signal Groups", "Combine signals into one reading, with labels such as Bullish."),
    "sets": (":material/account_tree:", "Signal Sets", "Connect Groups and signals into a Yes / No decision."),
    "prism": (":material/radar:", "Prism Scan", "Scan your Watchlist with a Set: now, at a past moment, or on a "
                                                "schedule with alerts."),
    "strategies": (":material/route:", "Strategies", "Entries, exits and risk plans. Coming later."),
}
PENDING = {"strategies"}

HEADER = "### :material/hub: Angstrom Lattice"
SUBTITLE = "Your market research workspace · preview: descriptive readings, not forecasts or advice"


def label(key: str) -> str:
    icon, name, _ = SECTIONS[key]
    return f"{icon} {name}" + (" (soon)" if key in PENDING else "")


def rerun(st) -> None:
    """Redraw only the Angstrom Lattice section when it runs as a fragment, else the page."""
    try:
        st.rerun(scope="fragment")
    except Exception:                  # not inside a fragment (tests, older Streamlit): the whole page
        st.rerun()


def rerun_page(st) -> None:
    """Redraw the whole page: only for a change outside Lattice (Visualize History opening the price chart)."""
    st.rerun(scope="app")


def pending(st, key: str, field: str):
    """A value the browser sent for component `key` before this run, read before the component is drawn, so a change
    needs one redraw, not two. None when there is nothing (or this Streamlit keeps it elsewhere)."""
    try:
        value = st.session_state.get(key)
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


PROVIDED_TITLE = "Provided by Angstrom Signals"     # the folded section that holds starters, examples and alerts


def provided_shown(st) -> bool:
    """⚙️ Settings → Show provided starters and examples (on unless switched off)."""
    try:
        return st.session_state.get("show_provided", True) is not False
    except Exception:
        return True


def render(st, supabase, assets: list[tuple[str, str, str]], user_id: str) -> None:
    """The section runs as a Streamlit fragment: a change inside it redraws only this section, not the dashboard."""
    fragment = getattr(st, "fragment", None)
    if not callable(fragment):
        _render(st, supabase, assets, user_id)
        return
    try:
        # Lattice sits inside the dashboard (under the chart), itself a fragment: a fragment of its own keeps a
        # change in Lattice from redrawing the dashboard.
        fragment(lambda: _render(st, supabase, assets, user_id))()
    except Exception as exc:
        if "Rerun" in type(exc).__name__ or "StopException" in type(exc).__name__:
            raise
        if "fragment" not in str(exc).lower():
            raise
        _render(st, supabase, assets, user_id)       # this Streamlit refuses a fragment here: draw it plainly


class _nothing:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


_ADVISOR = []


def _advisor_window(st, supabase, user_id: str) -> None:
    """The AI Advisor in a window over the page; the conversation is kept while you close it and follow the steps."""
    if not _ADVISOR:
        import advisor

        _ADVISOR.append(st.dialog("✨ AI Advisor", width="large")(
            lambda sb, uid: advisor.render(st, sb, uid)))
    _ADVISOR[0](supabase, user_id)


def _render(st, supabase, assets: list[tuple[str, str, str]], user_id: str) -> None:
    import perspectives

    perspectives.load_studies(supabase)              # "What followed" on people's own Sets, shared by Set logic
    st.markdown(HEADER)
    st.caption(SUBTITLE)
    state = getattr(st, "session_state", None)
    if state is not None and "_lattice_section_next" in state:   # a button elsewhere in Lattice asked for another tab
        state["lattice_section"] = state.pop("_lattice_section_next")
    hover = "\n\n".join(f"**{SECTIONS[k][1]}**: {SECTIONS[k][2]}" for k in SECTIONS)
    bar = st.container(horizontal=True, vertical_alignment="center", gap="small") if hasattr(st, "container") else None
    with (bar if bar is not None else _nothing()):
        chosen = st.segmented_control("Lattice section", list(SECTIONS), format_func=label, default="groups",
                                      key="lattice_section", label_visibility="collapsed", help=hover) or "groups"
        if hasattr(st, "dialog") and st.button("AI", icon=":material/auto_awesome:", key="advisor_open",
                                                help="✨ AI Advisor: describe a trading idea in plain words and get "
                                                     "step-by-step help building and testing it. It explains; you "
                                                     "do the clicks."):
            _advisor_window(st, supabase, user_id)
    if chosen == "groups":
        import lattice_view

        lattice_view.render(st, supabase, assets, user_id)
    elif chosen == "sets":
        import lattice_set_view

        lattice_set_view.render(st, supabase, user_id)
    elif chosen == "prism":
        import prism_view

        prism_view.render(st, supabase, assets, user_id)
    else:
        st.info("🛣️ **Strategies are coming later.** A strategy will turn a Set's Yes into a plan: when to enter, "
                "when to exit, and how much risk to take, including sequences such as \"A, then B within N days\". "
                "They will be designed with Drew's trading rules.")
