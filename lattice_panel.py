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
    if callable(fragment):
        fragment(lambda: _render(st, supabase, assets, user_id))()
    else:
        _render(st, supabase, assets, user_id)


def _render(st, supabase, assets: list[tuple[str, str, str]], user_id: str) -> None:
    st.markdown(HEADER)
    st.caption(SUBTITLE)
    hover = "\n\n".join(f"**{SECTIONS[k][1]}**: {SECTIONS[k][2]}" for k in SECTIONS)
    chosen = st.segmented_control("Lattice section", list(SECTIONS), format_func=label, default="groups",
                                  key="lattice_section", label_visibility="collapsed", help=hover) or "groups"
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
