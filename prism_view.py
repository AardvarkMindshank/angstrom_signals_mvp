"""
Prism · Run now, admin view (docs/design/lattice_prism.md §5.1, build stage 2).

A tab in the 🧪 Signal Library panel, visible to admin accounts only. Pick a Set that has a decision, pick assets
(default: the whole Watchlist), choose Now or a past moment, and press Run now. Runs nothing until the button is
pressed. Display only: results are not saved or exported, and past moments are reconstructions, not records.
"""

from __future__ import annotations

import datetime as dt
import time

import pandas as pd

import prism
import signal_groups as sg
import signal_library as sl
from signal_library import loaders

HELP = {
    "answer": "Yes: every necessary line holds. No: at least one necessary line fails (missing data could not change "
              "that). Unknown: nothing fails, but something needed could not be decided.",
    "how_sure": "Definite: the answer cannot change with the missing data. Undecided: it could.",
    "available": "How much of the input data existed. Separate from how sure the answer is.",
}


def scannable_sets(saved: list[dict], user_id: str) -> tuple[dict, dict]:
    """(labels, documents) for the demo Sets and every readable saved Set version that has a decision."""
    labels = {k: f"⭐ {d['name']}" for k, d in prism.demo_sets().items()}
    docs = dict(prism.demo_sets())
    for c in saved:
        if c.get("kind") != "set":
            continue
        for v in c["versions"]:
            if sg.scannable(v.get("body") or {}):
                key = f"saved:{c['id']}:{v['version']}"
                owner = "mine" if c.get("owner_id") == user_id else "shared"
                labels[key] = f"🗂️ {c['name']} v{v['version']} ({owner})"
                docs[key] = v["body"]
    return labels, docs


def render(st, supabase, assets: list[tuple[str, str, str]], user_id: str = "") -> None:
    st.caption("🔎 **Prism · Run now** (admin preview). Checks a Set on your Watchlist and answers Yes, No or Unknown "
               "for each asset, with the reason. Nothing is saved; past moments are reconstructions from today's data "
               "providers, not records.")
    if not assets:
        st.info("No assets in the watchlists.")
        return
    import signal_groups_inspector as gi

    cached = st.session_state.get("siggroups_saved")
    if not cached or time.time() - cached[0] > 60:
        cached = (time.time(), *gi.saved_configs(supabase))
        st.session_state["siggroups_saved"] = cached
    _, saved, problem = cached
    labels, docs = scannable_sets(saved, user_id)
    names = {f"{kind}:{key}": name for kind, key, name in assets}

    with st.form("prism_form", border=False):
        top = st.columns([3, 1])
        pick = top[0].selectbox("Set", list(labels), format_func=lambda k: labels[k], key="prism_set",
                                help="Only Sets with a decision can be scanned. A Set without one is never treated as No.")
        go = top[1].form_submit_button("Run now", width="stretch", type="primary")
        chosen = st.multiselect("Assets", list(names), default=list(names)[:prism.MAX_ASSETS],
                                format_func=lambda k: names[k], key="prism_assets",
                                help=f"Your Watchlist, at most {prism.MAX_ASSETS} per run.")
        when = st.columns([2, 2, 2])
        mode = when[0].radio("When", ["Now", "A past moment"], horizontal=True, key="prism_when",
                             help="Now uses the latest finished candles. A past moment rebuilds what was known then, "
                                  "using only data available at that time.")
        day = when[1].date_input("Date (UTC)", key="prism_day",
                                 value=(pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)).date())
        clock = when[2].time_input("Time (UTC)", key="prism_time", value=dt.time(0, 5))

    doc = docs[pick]
    with st.expander("What this Set checks", expanded=False):
        st.markdown(f"**{doc['name']}**: {doc.get('purpose') or 'no description'}")
        st.markdown("\n".join(f"- {head}" for _, head in prism.columns(doc)))
        st.caption("All lines must hold (ALL). A failed line gives No even if other data is missing; Unknown is "
                   "never turned into Yes or No.")

    if go:
        picked = [(k.split(":", 1)[0], k.split(":", 1)[1], names[k]) for k in chosen]
        if not picked:
            st.warning("Choose at least one asset.")
            return
        bar = st.progress(0.0, text="Checking…")
        progress = lambda n, total: bar.progress(n / total, text=f"Checked {n} of {total}")
        try:
            if mode == "Now":
                rows = prism.run_now(
                    doc, picked,
                    live_context=lambda kind, aid: sl.DataContext(
                        kind, aid, derivatives_loader=loaders.derivatives_loader(supabase),
                        sentiment_loader=loaders.sentiment_loader(supabase)),
                    market_context=lambda scope: sl.DataContext(
                        "market", scope.split(":", 1)[1], flows_loader=loaders.flows_loader(supabase),
                        sentiment_loader=loaders.sentiment_loader(supabase)),
                    progress=progress)
            else:
                as_of = pd.Timestamp(dt.datetime.combine(day, clock), tz="UTC")
                if as_of >= pd.Timestamp.now(tz="UTC"):
                    st.warning("Choose a moment in the past.")
                    return
                from signal_library.replay_display import display_run

                run = display_run(supabase, max_steps=1, shortcut=True)   # one moment, every asset
                rows = prism.run_now(doc, picked, live_context=None, replay=(run, as_of), progress=progress)
        except ValueError as exc:
            st.error(str(exc))
            return
        finally:
            bar.empty()
        st.session_state["prism_result"] = (pick, labels[pick], rows)

    stored = st.session_state.get("prism_result")
    if stored and stored[0] in docs:
        _results(st, docs[stored[0]], stored[1], stored[2])
    if problem:
        st.caption(f"Saved Sets could not be read: {problem}")


def _results(st, doc: dict, title: str, rows: list[dict]) -> None:
    counts = {a: sum(r["answer"] == a for r in rows) for a in ("yes", "no", "unknown")}
    path = rows[0]["path"] if rows else ""
    st.markdown(f"**{title}** · {path} · {prism.ANSWER_ICON['yes']} {counts['yes']} Yes · "
                f"{prism.ANSWER_ICON['no']} {counts['no']} No · {prism.ANSWER_ICON['unknown']} {counts['unknown']} Unknown")
    if path.startswith("Reconstruction"):
        st.info("Reconstruction: today's rules on data cut at that moment, from today's providers. Not a record of what "
                "was shown then, and not for statistics.")
    order = {"yes": 0, "unknown": 1, "no": 2}
    frame = prism.table(doc, sorted(rows, key=lambda r: (order[r["answer"]], r["asset"])))
    st.dataframe(frame, hide_index=True, width="stretch", column_config={
        "Answer": st.column_config.TextColumn("Answer", help=HELP["answer"]),
        "How sure": st.column_config.TextColumn("How sure", help=HELP["how_sure"]),
        "Data available": st.column_config.TextColumn("Data available", help=HELP["available"]),
    })
