"""
Angstrom Lattice, for every signed-in account (docs/design/lattice_prism.md §8; build stages 5 and 6).

One section on the dashboard with four parts across the top: Signal Groups, Signal Sets, Prism Scan and
Strategies (coming later). Only the chosen part is drawn; saved Groups and Sets are read at most once a minute,
and Prism only does real work when Run now is pressed.
"""

from __future__ import annotations

TITLE = "Angstrom Lattice"
ICON = ":material/hub:"
# (icon, name, one line on what it is for); the line is shown under the bar and in the hover note.
SECTIONS = {
    "groups": (":material/layers:", "Signal Groups", "Combine signals into one reading, with labels such as Bullish."),
    "sets": (":material/account_tree:", "Signal Sets", "Connect Groups and signals into a Yes / No decision."),
    "prism": (":material/radar:", "Prism Scan", "Scan your Watchlist with a Set: now, at a past moment, or on a "
                                                "schedule with alerts."),
    "strategies": (":material/route:", "Strategies", "Entries, exits and risk plans. Coming later."),
}
PENDING = {"strategies"}

LOGO = """
<div style="display:flex;align-items:center;gap:12px;margin:2px 0 6px;">
  <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
       stroke-linecap="round" aria-hidden="true">
    <circle cx="12" cy="4.5" r="2.2"/><circle cx="5" cy="18.5" r="2.2"/><circle cx="19" cy="18.5" r="2.2"/>
    <circle cx="12" cy="13" r="1.6"/>
    <path d="M12 6.7v4.7M10.7 14.1l-4.2 3M13.3 14.1l4.2 3M7.2 18.5h9.6"/>
  </svg>
  <div><div style="font-size:1.45rem;font-weight:700;line-height:1.15;">Angstrom Lattice</div>
  <div style="opacity:.7;font-size:.9rem;">Your market research workspace · preview: descriptive readings, not
  forecasts or advice</div></div>
</div>
"""


def label(key: str) -> str:
    icon, name, _ = SECTIONS[key]
    return f"{icon} {name}" + (" (soon)" if key in PENDING else "")


def render(st, supabase, assets: list[tuple[str, str, str]], user_id: str) -> None:
    st.html(LOGO)
    hover = "\n\n".join(f"**{SECTIONS[k][1]}**: {SECTIONS[k][2]}" for k in SECTIONS)
    chosen = st.segmented_control("Lattice section", list(SECTIONS), format_func=label, default="groups",
                                  key="lattice_section", label_visibility="collapsed", help=hover) or "groups"
    st.caption(SECTIONS[chosen][2])
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
