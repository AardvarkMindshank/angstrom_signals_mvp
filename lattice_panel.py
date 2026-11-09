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

_ADVISOR_JS = """
export default function(component) {
  const { parentElement, data } = component;
  const button = parentElement.querySelector("button");
  if (!button) return;
  button.dataset.start = (data && data.start) || "lattice";
  // Beside the Lattice tabs it matches their smaller height (less padding; the icon keeps its size).
  button.classList.toggle("compact", button.dataset.start === "lattice");
  if (data && data.tip) { button.title = data.tip; button.setAttribute("aria-label", data.tip); }
  if (button.dataset.ready) return;
  button.dataset.ready = "1";
  button.addEventListener("click", () => {
    const address = window.location.origin + window.location.pathname + "?view=advisor&from="
      + encodeURIComponent(button.dataset.start);
    // One small window beside the app, shared by every ✨ button. If it is already open it is brought to the front
    // as it is, so the conversation carries on; if pop-ups are blocked, a tab.
    const left = Math.max(0, (window.screenX || 0) + (window.outerWidth || 1200) - 540);
    const opened = window.open("", "ang_advisor", "popup=yes,width=520,height=820,top=60,left=" + left);
    if (!opened) { window.open(address, "_blank"); return; }
    let blank = true;
    try { blank = !opened.location.href || opened.location.href === "about:blank"; } catch (e) { blank = false; }
    if (blank) opened.location.href = address;
    opened.focus();
  });
}
"""

_ADVISOR_HTML = (
    "<button type='button' class='ang-ai-btn' title='{tip}'>"
    "<svg viewBox='0 0 24 24' width='18' height='18' fill='currentColor' aria-hidden='true'><path d='M19 9l1.25-2.75"
    "L23 5.5l-2.75-1.25L19 1.5l-1.25 2.75L15 5.5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 "
    "12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z'/></svg>"
    "<span>AI</span></button>")

_ADVISOR_CSS = """
.ang-ai-btn{display:inline-flex;align-items:center;gap:6px;height:2.5rem;padding:0 14px;border-radius:.5rem;
  border:1px solid var(--st-border-color, rgba(128,128,128,.35));background:transparent;color:inherit;font:inherit;
  cursor:pointer}
.ang-ai-btn svg{color:#f5a524;filter:drop-shadow(0 0 2px rgba(245,165,36,.35))}
.ang-ai-btn.compact{height:2rem;padding:0 10px;gap:5px}
.ang-ai-btn:hover{border-color:var(--st-primary-color,#ff4b4b);color:var(--st-primary-color,#ff4b4b)}
"""


TIPS = {
    "lattice": "✨ Angstrom Assistant (opens in its own window): describe a trading idea in plain words and get "
               "step-by-step help building and testing it. It also answers questions about the rest of the app. It "
               "explains; you do the clicks.",
    "app": "✨ Angstrom Assistant (opens in its own window): ask anything about the app, such as where things are, "
           "how to use them, or what a reading means, or get help building and testing an idea. It explains; you do "
           "the clicks.",
}


def advisor_button(st, start: str = "lattice", key: str = "advisor_open") -> None:
    """A ✨ AI button: opens the Angstrom Assistant in a pop-out window, so the pages under it stay free to work on.
    Every ✨ button opens the same window; `start` says where it was opened from."""
    import html

    if not _ADVISOR:
        _ADVISOR.append(st.components.v2.component(
            "advisor_popout", html=_ADVISOR_HTML.replace("{tip}", html.escape(TIPS["lattice"], quote=True)),
            css=_ADVISOR_CSS, js=_ADVISOR_JS, isolate_styles=False))
    _ADVISOR[0](key=key, data={"start": start, "tip": TIPS.get(start, TIPS["lattice"])})


_advisor_button = advisor_button


def render_popout(st, supabase, user_id: str, start: str = "lattice") -> None:
    """The Angstrom Assistant alone in its own window (?view=advisor&from=app|lattice)."""
    import advisor

    st.markdown("#### ✨ Angstrom Assistant")
    advisor.render(st, supabase, user_id, start if start in advisor.START else "lattice")


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
        if hasattr(st, "components") and hasattr(st.components, "v2"):
            advisor_button(st, "lattice")
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
