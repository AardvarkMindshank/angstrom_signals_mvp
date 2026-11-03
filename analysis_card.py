"""
Analysis card for the selected asset: a Signal Set evaluated by the real Groups/Sets evaluator (signal_groups).

Shown under the price chart, to admin accounts only for now (app.py decides). Nothing here touches the asset
tables, Trend/Stretch/Flow, alerts or settings: it builds its own DataContext for the one selected asset and runs
only when "Analyse" is pressed. The last result is kept for that asset and Set only (one entry per session, with
the bulky signal evidence removed).

The HTML builders are pure functions so they can be tested without Streamlit. Scores, confirmations and vetoes are
kept in separate places on purpose: a positive score never implies that a confirmation passed or a veto cleared.
"""

from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone

import signal_groups as sg
import signal_library as sl
from signal_library import loaders
from signals_view import mini_bar, number_badge

EXAMPLE_KEY = "example:multi-timeframe"
SETS_TTL = 300  # seconds the list of Sets is kept per session

TIMEFRAME = {"15m": "15 min", "1h": "1 hour", "4h": "4 hours", "1D": "Daily", "1W": "Weekly"}

GROUP_STATUS = {
    "ok": ("✅", "Evaluated", "Every veto was checked and none is active."),
    "vetoed": ("⛔", "Vetoed", "A veto condition is active: this Group's own rules say its reading should not be relied on now."),
    "veto_unknown": ("❔", "Veto unknown", "A veto could not be checked because its data is missing, so it may or may not apply."),
    "insufficient": ("⏳", "Not enough data", "Too few scoring signals have data for the Group's minimum coverage."),
    "invalid": ("⚠️", "Invalid", "This Group's definition did not pass validation, so nothing was evaluated."),
    "unsupported": ("➖", "Not supported", "This kind of evaluation is not supported yet."),
}
CONDITION = {
    ("confirmation", "met"): ("✅", "Met", "Every part of this condition is true on the latest data."),
    ("confirmation", "not_met"): ("✖️", "Not met", "The data needed was available, and the condition is false."),
    ("confirmation", "unknown"): ("❔", "Unknown", "Some data this condition needs is missing, so it is neither met nor failed."),
    ("veto", "active"): ("⛔", "Active", "The veto applies: the Group's reading should not be relied on now."),
    ("veto", "clear"): ("🟢", "Clear", "The veto was checked and does not apply."),
    ("veto", "unknown"): ("❔", "Unknown", "The veto could not be checked because its data is missing."),
}
WITHHELD = {
    "below_min_coverage": "Not enough of the scoring signals have data to give a score.",
    "all_unavailable": "None of the scoring signals has data right now.",
    "no_enabled_members": "This Group has no scoring signals switched on.",
}
SIGNAL_STATUS = {
    "ok": "OK", "insufficient_data": "Not enough history", "missing_data": "Data missing", "stale": "Out of date",
    "unsupported": "Not available for this asset", "error": "Error while calculating",
}
MEMBER_STATE = {
    "observed": "Counted in the score",
    "excluded": "Left out of the score (no usable value)",
    "imputed": "Counted as neutral (no usable value)",
    "disabled": "Switched off (weight 0)",
}
ROLE = {"score": "Score", "condition": "Used in conditions", "levels": "Levels", "context": "Context only"}
SEPARATE_NOTE = ("The score and the conditions are separate readings: a positive score does not mean a "
                 "confirmation passed, and it does not clear a veto.")


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def _tip(icon: str, text: str, hint: str, colour: str = "inherit") -> str:
    return (f"<span title='{_esc(hint)}' style='display:inline-flex;align-items:center;gap:4px;padding:2px 8px;"
            f"border-radius:999px;border:1px solid var(--ang-border, #e5e7eb);font-size:0.8rem;color:{colour};"
            f"white-space:nowrap;'>{icon} {_esc(text)}</span>")


def _when(stamp) -> str:
    if not stamp:
        return "–"
    return str(stamp)[:16].replace("T", " ") + " UTC"


def _age(stamp, now=None) -> str:
    if not stamp:
        return ""
    try:
        then = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        hours = ((now or datetime.now(timezone.utc)) - then).total_seconds() / 3600
    except ValueError:
        return ""
    if hours < 1:
        return "under an hour old"
    if hours < 48:
        return f"{hours:.0f} h old"
    return f"{hours / 24:.0f} days old"


def reading(signal: dict) -> str:
    """A signal's own value in words (the same summaries as the Signal Library inspector)."""
    import signal_inspector

    try:
        text = signal_inspector.summary(sl.SignalResult(**signal))
    except Exception:
        value = signal.get("value")
        text = "–" if value is None else str(value)[:120]
    return tidy(text)


_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2}(?:\.\d+)?)?(?:\+00:00|Z)?")
_LONG_NUMBER = re.compile(r"-?\d+\.\d{4,}")


def tidy(text: str) -> str:
    """Readable numbers and times: 114.9389960682998 -> 114.94, 2026-10-30T20:00:00+00:00 -> 2026-10-30 20:00 UTC."""
    text = _ISO.sub(lambda m: f"{m.group(1)} {m.group(2)} UTC", str(text))
    return _LONG_NUMBER.sub(lambda m: f"{float(m.group(0)):.5g}", text)


def _words(key: str) -> str:
    text = str(key).replace("_", " ").strip()
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------------------------- view pieces

def score_html(result: dict) -> str:
    score = result.get("score")
    if score is None:
        return _tip("➖", "No score", "This Group does not produce a score: read its conditions instead.", "#6b7280")
    if score.get("value") is None:
        why = WITHHELD.get(score.get("withheld"), "No score this time.")
        return _tip("⏳", "Score withheld", why, "#6b7280")
    value = score["value"] * 100
    hint = f"{score.get('meaning') or ''} Observed coverage {score.get('observed_coverage', 0):.0%}."
    return (f"<span title='{_esc(hint)}' style='display:inline-flex;align-items:center;gap:6px;'>"
            f"{mini_bar(value, 90)}{number_badge(value)}</span>")


def condition_chips(result: dict) -> str:
    chips = []
    for c in result.get("conditions") or []:
        icon, word, hint = CONDITION.get((c["kind"], c["state"]), ("", c["state"], ""))
        kind = "Veto" if c["kind"] == "veto" else "Confirmation"
        label = c.get("label") or c["key"]
        chips.append(_tip(icon, f"{_words(c['key'])}: {word}", f"{kind}: {label}. {hint}"))
    return "".join(chips)


def group_row(entry: dict) -> str:
    """One compact row: status, name and purpose, score, then the condition chips (kept apart from the score)."""
    result = entry["result"]
    icon, word, hint = GROUP_STATUS.get(result.get("status"), ("", result.get("status"), ""))
    purpose = entry.get("purpose") or ""
    return (
        "<div style='display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid "
        "var(--ang-border, #e5e7eb);flex-wrap:wrap;'>"
        f"<span title='{_esc(hint)}' style='font-size:1.1rem;'>{icon}</span>"
        f"<span style='flex:1 1 220px;'><span style='font-weight:600;'>{_esc(result.get('name') or entry['key'])}</span>"
        f"<br><span class='ang-kicker'>{_esc(purpose)}</span></span>"
        f"<span style='min-width:150px;'>{score_html(result)}</span>"
        f"<span style='display:flex;flex-wrap:wrap;gap:4px;flex:1 1 260px;'>{_tip(icon, word, hint)}"
        f"{condition_chips(result)}</span></div>"
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th style='text-align:left;padding:4px 8px;font-weight:600;'>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td style='padding:4px 8px;vertical-align:top;border-top:1px solid "
                                    f"var(--ang-border, #e5e7eb);'>{cell}</td>" for cell in r) + "</tr>" for r in rows)
    return (f"<div style='overflow-x:auto;'><table style='border-collapse:collapse;width:100%;font-size:0.85rem;'>"
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")


def group_details(result: dict, now=None) -> str:
    """Everything behind one Group's row, in words."""
    if result.get("status") in ("invalid", "unsupported"):
        lines = result.get("errors") or [result.get("reason") or "Not evaluated."]
        return "".join(f"<div>⚠️ {_esc(e)}</div>" for e in lines)
    parts = []
    score = result.get("score")
    if score is not None:
        weights = score.get("weights") or {}
        mc = score.get("min_coverage") or {}
        line = (f"<b>Score</b> {score_html(result)} · data for {score.get('observed_coverage', 0):.0%} of the scoring "
                f"weight (needs at least {mc.get('num', 0)}/{mc.get('den', 1)})")
        if weights.get("imputed"):
            line += f" · {weights['imputed']:g} weight counted as neutral"
        parts.append(f"<div style='margin:4px 0;'>{line}</div>")
        if score.get("meaning"):
            parts.append(f"<div class='ang-kicker' style='margin-bottom:6px;'>{_esc(score['meaning'])}</div>")
    else:
        parts.append("<div style='margin:4px 0;'><b>No score</b>: this Group reports conditions only.</div>")

    conditions = result.get("conditions") or []
    for kind, title in (("confirmation", "Confirmations"), ("veto", "Vetoes")):
        rows = []
        for c in [c for c in conditions if c["kind"] == kind]:
            icon, word, hint = CONDITION.get((kind, c["state"]), ("", c["state"], ""))
            rows.append([f"<span title='{_esc(hint)}'>{icon} {_esc(word)}</span>", _esc(c.get("label") or c["key"]),
                         _esc(", ".join(c.get("sources") or []) or "–")])
        if rows:
            parts.append(f"<div style='margin-top:10px;font-weight:600;'>{title}</div>")
            parts.append(_table(["Result", "Condition", "Data it rests on"], rows))

    rows = []
    for m in result.get("members") or []:
        sig = m.get("signal") or {}
        ref = sig.get("ref") or {}
        status = sig.get("status")
        status_text = SIGNAL_STATUS.get(status, status or "–")
        if status != "ok" and sig.get("notes"):
            status_text += f": {sig['notes'][0]}"
        if m["role"] == "score":
            state = MEMBER_STATE.get(m.get("state"), m.get("state") or "")
            if m.get("contribution") is not None:
                share = m.get("weight_share")
                state = (f"{m['contribution'] * 100:+.0f} × weight {m.get('weight', 0):g}"
                         + (f" ({share:.0%} of the score)" if share is not None else "") + f" · {state}")
            if m.get("unobserved_reason") == "transform_unknown":
                state += " · value could not be mapped to a score"
            if m.get("flags"):
                state += " · " + ", ".join(str(f).replace("_", " ") for f in m["flags"])
        else:
            state = ROLE.get(m["role"], m["role"])
        fresh = _when(sig.get("available_at"))
        age = _age(sig.get("available_at"), now)
        rows.append([_esc(m.get("label") or m["key"]), _esc(TIMEFRAME.get(ref.get("timeframe"), ref.get("timeframe"))),
                     _esc(reading(sig)), _esc(status_text), _esc(state),
                     _esc(fresh + (f" ({age})" if age else "")), _esc(", ".join(m.get("lineage") or []))])
    if rows:
        parts.append("<div style='margin-top:10px;font-weight:600;'>Signals</div>")
        parts.append(_table(["Signal", "Timeframe", "Reading", "Data", "In this Group", "Data as of", "Source"], rows))

    parts.append(f"<div class='ang-kicker' style='margin-top:8px;'>ℹ️ {_esc(SEPARATE_NOTE)}</div>")
    for note in diagnostic_notes(result):
        parts.append(f"<div class='ang-kicker'>ℹ️ {_esc(note)}</div>")
    return "".join(parts)


def diagnostic_notes(result: dict) -> list[str]:
    diag = result.get("diagnostics") or {}
    notes = []
    agreement = diag.get("agreement") or {}
    if agreement.get("share_of_observed_weight") is not None:
        notes.append(f"{agreement['share_of_observed_weight']:.0%} of the counted weight points the same way as the score"
                     + (f"; opposing: {', '.join(agreement['opposing'])}" if agreement.get("opposing") else "") + ".")
    if diag.get("source_separation"):
        notes.append(diag["source_separation"]["note"])
    notes += diag.get("known_redundancy") or []
    if diag.get("duplicates"):
        notes.append("The same signal is used more than once: " + "; ".join(", ".join(d) for d in diag["duplicates"]) + ".")
    if diag.get("category_conflicts"):
        notes.append("Signals in these categories point opposite ways: " + ", ".join(diag["category_conflicts"]) + ".")
    missing = (diag.get("timing") or {}).get("unavailable") or []
    if missing:
        notes.append("No usable data from: " + ", ".join(missing) + ".")
    return notes


def context_html(result: dict, asset_kind: str, asset_name: str) -> str:
    """Standalone signals for this asset, then market backdrop, each labelled with what it describes."""
    parts = []
    standalone = result.get("standalone") or []
    if standalone:
        rows = []
        for s in standalone:
            sig = s.get("signal") or {}
            ref = sig.get("ref") or {}
            rows.append([_esc(s.get("label") or s["key"]), _esc(TIMEFRAME.get(ref.get("timeframe"), ref.get("timeframe"))),
                         _esc(reading(sig)), _esc(SIGNAL_STATUS.get(sig.get("status"), sig.get("status"))),
                         _esc(_when(sig.get("available_at")))])
        parts.append(f"<div style='margin-top:12px;font-weight:600;'>🧭 More on {_esc(asset_name)}</div>")
        parts.append(_table(["Reading", "Timeframe", "Value", "Data", "Data as of"], rows))
    shown = [m for m in result.get("market_context") or [] if not m.get("skipped")]
    if shown and asset_kind == "crypto":
        rows = []
        for m in shown:
            sig = m.get("signal") or {}
            rows.append([_esc(m.get("label") or m["key"]), _esc(reading(sig)),
                         _esc(SIGNAL_STATUS.get(sig.get("status"), sig.get("status"))), _esc(_when(sig.get("available_at")))])
        subjects = sorted({m["subject"].split(":", 1)[-1].title() for m in shown})
        parts.append(f"<div style='margin-top:12px;font-weight:600;'>🌐 Market backdrop ({_esc(', '.join(subjects))})</div>")
        parts.append(f"<div class='ang-kicker'>Describes the {_esc(' and '.join(subjects))} market as a whole, "
                     f"not a reading of {_esc(asset_name)}'s own price.</div>")
        parts.append(_table(["Reading", "Value", "Data", "Data as of"], rows))
    return "".join(parts)


def header_html(set_name: str, purpose: str, result: dict) -> str:
    when = _when(result.get("evaluated_at"))
    return (f"<div class='ang-kicker'>Analysis · {_esc(set_name)} · evaluated {_esc(when)}</div>"
            f"<div class='ang-kicker' style='margin-bottom:4px;'>{_esc(purpose)} No overall score: each Group is read "
            "on its own.</div>")


# ---------------------------------------------------------------------------------------------- data

def example_set() -> dict:
    import signal_groups_inspector

    return signal_groups_inspector.example_set()


def readable_sets(supabase) -> tuple[list[tuple[str, str, dict]], str | None]:
    """[(key, label, body)]: the example Set, then saved Sets this account can read (row-level security decides),
    each at its current version. Errors leave the example Set available."""
    out = [(EXAMPLE_KEY, "Multi-Timeframe Analysis", None)]
    try:
        configs = (supabase.table("analysis_configs").select("id, name, current_version")
                   .eq("kind", "set").eq("archived", False).order("updated_at", desc=True).limit(30).execute().data or [])
        if configs:
            versions = (supabase.table("analysis_config_versions").select("config_id, version, body")
                        .in_("config_id", [c["id"] for c in configs]).execute().data or [])
            body = {(v["config_id"], v["version"]): v["body"] for v in versions}
            for c in configs:
                doc = body.get((c["id"], c["current_version"]))
                if doc is not None:
                    out.append((f"saved:{c['id']}:{c['current_version']}", f"{c['name']} (v{c['current_version']})", doc))
    except Exception as exc:
        return out, f"Saved Sets could not be loaded ({str(exc)[:100]}); the built-in Set is still available."
    return out, None


def _slim(value):
    """Drop signal evidence (pivots, bars): the card does not show it, and it is most of the result's size."""
    if isinstance(value, dict):
        return {k: _slim(v) for k, v in value.items() if k != "evidence"}
    if isinstance(value, list):
        return [_slim(v) for v in value]
    return value


def evaluate(doc: dict, asset_kind: str, asset_id: str, supabase, *, candle_loader=None) -> dict:
    """Runs the real Set evaluator for one asset. Signals shared by several Groups are calculated once."""
    ctx = sl.DataContext(asset_kind, asset_id, candle_loader=candle_loader,
                         derivatives_loader=loaders.derivatives_loader(supabase))
    flows = loaders.flows_loader(supabase)
    result = sg.evaluate_set(doc, ctx, market_context=lambda scope: sl.DataContext(
        "market", scope.split(":", 1)[1], flows_loader=flows, candle_loader=candle_loader))
    return _slim(result)


def group_entries(doc: dict, result: dict) -> list[dict]:
    purposes = {g["key"]: g["snapshot"].get("purpose") or g["snapshot"].get("question") or "" for g in doc.get("groups") or []}
    return [{"key": g["key"], "purpose": purposes.get(g["key"], ""), "result": g["result"]} for g in result.get("groups") or []]


# ---------------------------------------------------------------------------------------------- Streamlit

def render(st, supabase, asset_type: str, asset_key: str, asset_name: str, *, candle_loader=None) -> None:
    """asset_type is the app's "Crypto" or "Stock"; asset_key the watchlist key (coin id or ticker)."""
    kind = "crypto" if str(asset_type).lower() == "crypto" else "equity"
    cached = st.session_state.get("analysis_sets")
    if not cached or time.time() - cached[0] > SETS_TTL:
        cached = (time.time(), *readable_sets(supabase))
        st.session_state["analysis_sets"] = cached
    _, sets, problem = cached
    labels = {key: label for key, label, _ in sets}
    bodies = {key: body for key, _, body in sets}

    st.markdown("**🔬 Analysis** <span class='ang-kicker'>(Signal Sets, admin preview)</span>", unsafe_allow_html=True)
    cols = st.columns([4, 1])
    pick = cols[0].selectbox("Signal Set", list(labels), format_func=lambda k: labels[k], key="analysis_set",
                             label_visibility="collapsed") if len(labels) > 1 else EXAMPLE_KEY
    if len(labels) == 1:
        cols[0].markdown(f"<span class='ang-kicker'>Set: {_esc(labels[EXAMPLE_KEY])}</span>", unsafe_allow_html=True)
    go = cols[1].button("Analyse", key="analysis_go", width="stretch",
                        help="Evaluates this Set for the selected asset only. Takes a few seconds the first time.")
    if problem:
        st.caption(problem)

    here = (kind, asset_key, pick)
    stored = st.session_state.get("analysis_result")
    if stored and stored[0] != here:
        st.session_state.pop("analysis_result", None)  # keep one result only: this asset and Set
        stored = None
    if go:
        doc = bodies.get(pick) or example_set()
        started = time.perf_counter()
        with st.spinner(f"Evaluating {labels.get(pick)} for {asset_name}…"):
            try:
                result = evaluate(doc, kind, asset_key, supabase, candle_loader=candle_loader)
                error = None
            except Exception as exc:  # the evaluator reports data problems itself; this is a last resort
                result, error = None, f"The analysis could not be completed ({type(exc).__name__}: {str(exc)[:160]})."
        stored = (here, doc, result, error, round(time.perf_counter() - started, 2))
        st.session_state["analysis_result"] = stored
    if not stored:
        st.caption("Press Analyse to evaluate this Set for the selected asset.")
        return
    _, doc, result, error, seconds = stored
    if error:
        st.warning(error, icon=":material/error:")
        return
    show(st, doc, result, kind, asset_name, seconds)


def show(st, doc: dict, result: dict, kind: str, asset_name: str, seconds=None) -> None:
    if result.get("status") in ("invalid", "unsupported"):
        st.warning(" ".join(result.get("errors") or [result.get("reason") or "This Set could not be evaluated."]))
        return
    entries = group_entries(doc, result)
    st.html("<div class='ang-card' style='margin-bottom:6px;'>"
            + header_html(doc.get("name") or "Set", doc.get("purpose") or "", result)
            + "".join(group_row(e) for e in entries) + "</div>")
    for e in entries:
        icon = GROUP_STATUS.get(e["result"].get("status"), ("",))[0]
        with st.expander(f"{icon} {e['result'].get('name') or e['key']}: details", expanded=False):
            st.html(group_details(e["result"]))
    extra = context_html(result, kind, asset_name)
    if extra:
        st.html(f"<div class='ang-card'>{extra}</div>")
    note = (result.get("diagnostics") or {}).get("note")
    if note:
        st.caption(f"ℹ️ {note}" + (f" · took {seconds:.1f} s" if seconds is not None else ""))
