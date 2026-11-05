"""
Development inspector for the Signal Library: admin accounts only (app.py calls it next to the admin
panel). Nothing runs until the button is pressed, and nothing here changes readings, alerts or settings.
"""

from __future__ import annotations

import json

import signal_library as sl
from signal_library import loaders
from signal_library.core import EVENTS, LEVELS, OBSERVATION, OK

TIMEFRAME_LABELS = {"15m": "15 min", "1h": "1 hour", "4h": "4 hours", "1D": "1 day", "1W": "1 week"}
STATUS_ICON = {"ok": "✅", "insufficient_data": "⏳", "missing_data": "❓", "stale": "🕰️", "unsupported": "➖",
               "error": "⚠️"}


def summary(result) -> str:
    """One line for the table; the full value is in the details."""
    if result.status != OK and result.value is None:
        return (result.notes or [result.status])[0]
    value = result.value
    if not isinstance(value, dict):
        return str(value)
    if "summary" in value:
        return value["summary"]
    if "events" in value:
        latest = (value.get("events") or [])[-1:] or [None]
        dev = value.get("developing") or []
        text = "no recent events" if latest[0] is None else (
            f"latest {latest[0].get('type') or latest[0].get('kind')} {latest[0].get('direction', '')} "
            f"({latest[0].get('status', 'confirmed')}) at {latest[0].get('confirmed_at') or latest[0].get('time')}")
        return text + (f"; developing: {', '.join(d['type'] for d in dev)}" if dev else "")
    if "support" in value:
        s = value.get("support") or []
        r = value.get("resistance") or []
        fmt = lambda z: f"{z['low']:.6g}–{z['high']:.6g} ({z['touches']}×)"  # noqa: E731
        return f"support {', '.join(map(fmt, s)) or '–'} | resistance {', '.join(map(fmt, r)) or '–'}"
    if "structure" in value:
        return f"{value['structure']}; last high {value.get('last_swing_high')}, last low {value.get('last_swing_low')}"
    if "state" in value:
        return (f"{value['state']} ({value.get('direction')}), ADX {value.get('adx')}, ER {value.get('efficiency_ratio_20')}, "
                f"volatility {value.get('volatility')}")
    keys = list(value)[:4]
    return ", ".join(f"{k} {value[k]}" for k in keys)


def asset_refs(kind: str, timeframe: str) -> list:
    refs = []
    for definition in sl.REGISTRY.latest():
        if definition.id.startswith("test."):
            continue
        if definition.scope == "asset" or (definition.scope == "crypto_asset" and kind == "crypto"):
            tf = timeframe if timeframe in definition.timeframes else definition.timeframes[0]
            refs.append(sl.SignalRef.make(definition, tf))
    return refs


def market_refs() -> list:
    return [sl.SignalRef.make(d, d.timeframes[0]) for d in sl.REGISTRY.latest() if d.scope.startswith("market:")]


def render(st, supabase, assets: list[tuple[str, str, str]], my_communities=None, user_id: str = "") -> None:
    """assets: (kind "crypto"|"equity", id, display name). my_communities() -> [{"id", "name"}]."""
    st.caption(
        "Development view of the v3 Signal Library. Visible to admin accounts only; it does not change any reading, "
        "alert or setting. Signals run only when you press the button. Intraday timeframes fetch Yahoo candles for "
        "the chosen asset."
    )
    # Lattice and Prism moved to their own panel for every account (lattice_panel.py).
    tab_run, tab_groups, tab_catalogue = st.tabs(["Inspect an asset", "Groups & Sets", "Catalogue"])
    with tab_groups:
        import signal_groups_inspector

        signal_groups_inspector.render(st, supabase, assets, my_communities or (lambda: []), user_id)
    with tab_run:
        if not assets:
            st.info("No assets in the watchlists.")
            return
        names = {f"{kind}:{key}": name for kind, key, name in assets}
        with st.form("siglib_form", border=False):
            cols = st.columns([3, 2, 1])
            pick = cols[0].selectbox("Asset", list(names), format_func=lambda k: names[k], key="siglib_asset")
            timeframe = cols[1].selectbox("Timeframe", list(TIMEFRAME_LABELS), index=3,
                                          format_func=lambda t: TIMEFRAME_LABELS[t], key="siglib_tf")
            go = cols[2].form_submit_button("Evaluate", width="stretch")
        if go:
            kind, asset_id = pick.split(":", 1)
            ctx = sl.DataContext(kind, asset_id, derivatives_loader=loaders.derivatives_loader(supabase),
                                 sentiment_loader=loaders.sentiment_loader(supabase))
            results = list(sl.evaluate(asset_refs(kind, timeframe), ctx).values())
            for subject in ("bitcoin", "crypto", "stocks"):
                market = sl.DataContext("market", subject, flows_loader=loaders.flows_loader(supabase),
                                        sentiment_loader=loaders.sentiment_loader(supabase))
                results += [r for r in sl.evaluate(market_refs(), market).values() if r.status != "unsupported"]
            st.session_state["siglib_results"] = (pick, timeframe, [r.as_dict() for r in results])
        stored = st.session_state.get("siglib_results")
        if stored:
            _show(st, *stored, names)
    with tab_catalogue:
        for entry in sl.REGISTRY.catalogue():
            if entry["id"].startswith("test."):
                continue
            with st.expander(f"{entry['name']} · `{entry['key']}`"):
                st.markdown(
                    f"**Output:** {entry['output']} ({entry['unit']}) · **Scope:** {entry['scope']} · "
                    f"**Timeframes:** {', '.join(entry['timeframes'])} · **Data:** {', '.join(entry['requires'])} · "
                    f"**Evidence:** {entry['evidence_strength']}"
                )
                st.markdown(f"**Calculation.** {entry['calculation']}")
                st.markdown(f"**How to read it.** {entry['interpretation']}")
                st.markdown(f"**Limitations.** {entry['limitations']}")
                if entry["params"]:
                    st.json(entry["params"], expanded=False)


def _show(st, pick, timeframe, results, names) -> None:
    st.markdown(f"**{names.get(pick, pick)}**, main timeframe {TIMEFRAME_LABELS[timeframe]}")
    rows = []
    for r in results:
        definition = sl.REGISTRY.get(r["ref"]["id"], r["ref"]["version"])
        rows.append({
            "": STATUS_ICON.get(r["status"], ""), "Signal": definition.name, "Timeframe": r["ref"]["timeframe"],
            "Status": r["status"], "Confirmation": r["confirmation"], "Reading": summary(sl.SignalResult(**r)),
            "Observed": (r["observed_at"] or "")[:16].replace("T", " "),
            "Available": (r["available_at"] or "")[:16].replace("T", " "),
        })
    st.dataframe(rows, hide_index=True, width="stretch")
    st.download_button("Download results (JSON)", json.dumps(results, indent=1, default=str),
                       file_name=f"signals_{pick.replace(':', '_')}_{timeframe}.json", mime="application/json",
                       key="siglib_download")
    for r in results:
        definition = sl.REGISTRY.get(r["ref"]["id"], r["ref"]["version"])
        label = f"{STATUS_ICON.get(r['status'], '')} {definition.name} · {r['ref']['timeframe']} · `{definition.key}`"
        with st.expander(label):
            if r["notes"]:
                for note in r["notes"]:
                    st.caption(note)
            st.markdown(f"**Calculation.** {definition.calculation}")
            st.markdown(f"**Limitations.** {definition.limitations}")
            st.markdown(f"**Sources.** {'; '.join(r['provenance']) or '–'}"
                        + (" · **backfilled history**" if r["backfilled"] else ""))
            st.markdown(f"**Parameters.** `{json.dumps(r['ref']['params'])}` · **Instance** `{r['instance_key']}`")
            if definition.output in (EVENTS, LEVELS, OBSERVATION) or isinstance(r["value"], (dict, list)):
                st.json(r["value"], expanded=False)
            else:
                st.markdown(f"**Value.** {r['value']} {r['unit']}")
            if r["evidence"]:
                st.markdown("**Evidence**")
                st.json(r["evidence"], expanded=False)
