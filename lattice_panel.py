"""
🧩 Lattice · 🔎 Prism (preview), for every signed-in account (docs/design/lattice_prism.md §8; build stage 5).

Opened from its own panel on the dashboard. Nothing runs, and nothing is read from the database, until the panel is
switched on, so the dashboard costs the same for people who do not use it.
"""

from __future__ import annotations


def render(st, supabase, assets: list[tuple[str, str, str]], user_id: str) -> None:
    st.caption("Build your own Groups and Sets from the signals behind the dashboard, then scan your Watchlist with "
               "them in Prism, now, at a past moment, or on a schedule with alerts. Preview: descriptive readings, "
               "not forecasts or advice.")
    if not st.toggle("Open Lattice and Prism", key="lattice_open",
                     help="Loads your Groups and Sets. Switch off to keep the page light."):
        return
    tab_lattice, tab_prism = st.tabs(["🧩 Lattice", "🔎 Prism"])
    with tab_lattice:
        import lattice_view

        lattice_view.render(st, supabase, assets, user_id)
    with tab_prism:
        import prism_view

        prism_view.render(st, supabase, assets, user_id)
