"""
🔍 Why these readings: the selected asset's table columns, one folded block each, part by part (replaces the old
Signals Breakdown, which only covered Trend, Stretch and Flow).

- A Group block lists each part with its bar, its share of the score and its reading in plain words.
- A Set block lists each line of its decision with ✓ / ✕ and the reading, and the reason for the answer.
- Columns that read 4-hour or hourly candles are worked out in the background (column_answers.py), which keeps
  only the short answer, so their block shows that answer and when it was worked out.

Trend, Stretch and Flow are worked out by the same Groups and the same stored daily bars as the table, so the block
and the table cell always agree. Each block links to Angstrom Lattice, where the Group or Set is built.
"""

from __future__ import annotations

import html

import group_readings as gr
import signal_groups as sg
import signals_v2 as v2
import table_columns as tc

GROUP_ICON = "🧩"


def _esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def lattice_pick(spec: dict) -> str:
    if spec["part"] == "groups":
        return f"lattice|groups|{spec['config'] or spec['key']}"
    return f"lattice|sets|{spec['config'] or spec['key']}"


def _number(v) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.2f}" if abs(v) < 10 else f"{v:.1f}"


def plain_reading(member: dict, readings: dict) -> str:
    """The part's reading in words. A dashboard part on daily bars with its usual settings uses the dashboard's
    wording (the same numbers); anything else shows the signal's own measurements."""
    signal = member.get("signal") or {}
    if member.get("state") != "observed":
        return (signal.get("reason") or signal.get("status") or "No data from this source").replace("_", " ")
    ref = signal.get("ref") or {}
    comp = (signal.get("evidence") or {}).get("component")
    if comp in v2.COMPONENT_NAMES and ref.get("timeframe", "1D") == "1D" and not ref.get("params") and readings:
        return v2.component_reading(comp, readings)
    value = signal.get("value")
    if not isinstance(value, dict):
        return f"{_number(value)} {signal.get('unit') or ''}".strip() if value is not None else ""
    bits = [f"{k.replace('_', ' ')} {_number(v)}" for k, v in value.items()
            if k not in ("standard_score", "close") and isinstance(v, (int, float)) and not isinstance(v, bool)]
    return ", ".join(bits[:3])


def group_item(spec: dict, result: dict, readings: dict) -> dict:
    score = (result.get("score") or {}).get("value")
    pct = v2.percent(score)
    outcome = result.get("outcome") or {}
    label = outcome.get("label") if outcome.get("id") not in (None, "unknown") else None
    if spec["cluster"]:
        label = label or gr.UNKNOWN_LABEL
    rows = []
    for m in result.get("members") or []:
        part = m.get("contribution") if m.get("state") == "observed" else None
        role = m.get("role") or "score"
        rows.append({"name": m.get("label") or m.get("key"), "percent": v2.percent(part) if role == "score" else None,
                     "role": role, "text": plain_reading(m, readings),
                     "share": m.get("weight_share") if role == "score" else None})
    status = result.get("status")
    note = tc._group_why(result) if status and status != "ok" else ""
    icon = v2.CLUSTERS[spec["cluster"]]["icon"] if spec["cluster"] else GROUP_ICON
    head = f"{icon} {spec['name']} · " + (f"{pct:+d}" if pct is not None else "no reading") + (f" · {label}" if label else "")
    return {"key": spec["key"], "part": "groups", "title": head, "percent": pct, "label": label, "rows": rows,
            "note": note, "lattice": lattice_pick(spec), "name": spec["name"]}


def set_item(spec: dict, result: dict) -> dict:
    import prism

    row = prism.row(spec["name"], result, "")
    answer = row["answer"] if row["answer"] in tc.ANSWER_MARK else "unknown"
    mark, word, _ = tc.ANSWER_MARK[answer]
    lines = []
    try:
        for path, text in prism.columns(spec["doc"]):
            got = row["lines"].get(path)
            lines.append({"text": text, "value": got or "not checked"})
    except Exception:
        pass
    return {"key": spec["key"], "part": "sets", "title": f"{mark} {spec['name']} · {word}", "answer": answer,
            "rows": lines, "note": row.get("reason") or "", "how_sure": row.get("how_sure"),
            "lattice": lattice_pick(spec), "name": spec["name"]}


def background_item(spec: dict, cell: dict | None) -> dict:
    """A 4-hour or hourly column: only the answer is kept."""
    when, stale = tc.freshness(spec, cell or {}) if cell else ("", False)
    if spec["part"] == "groups":
        pct = None if not cell or cell.get("value") is None else round(cell["value"])
        head = f"{GROUP_ICON} {spec['name']} · " + (f"{pct:+d}" if pct is not None else "no answer yet")
        head += f" · {cell['label']}" if cell and cell.get("label") else ""
    else:
        answer = (cell or {}).get("answer") if (cell or {}).get("answer") in tc.ANSWER_MARK else None
        head = (f"{tc.ANSWER_MARK[answer][0]} {spec['name']} · {tc.ANSWER_MARK[answer][1]}" if answer
                else f"— {spec['name']} · no answer yet")
    if stale:
        head += " ⏳"
    if cell is None:
        note = "Reads 4-hour or hourly candles, so it is worked out in the background at each close; the first answer appears within the hour."
    else:
        note = " · ".join(x for x in ((cell.get("why") or cell.get("error") or ""), when) if x)
    return {"key": spec["key"], "part": spec["part"], "title": head, "rows": [], "note": note,
            "detail_note": "Part-by-part detail is shown for daily columns; this one keeps only its answer.",
            "lattice": lattice_pick(spec), "name": spec["name"]}


def items(specs: list[dict], ctx, readings: dict, subject_context=None, background: dict | None = None) -> list[dict]:
    """One block per chosen column, in table order. background: column key -> the stored answer for columns that
    read 4-hour or hourly candles."""
    out = []
    background = background or {}
    for spec in specs:
        try:
            if spec["cluster"]:
                out.append(group_item(spec, sg.evaluate_group(gr.dashboard_group(spec["cluster"]), ctx), readings))
            elif spec["doc"] is None:
                continue
            elif not tc.daily_only(spec["doc"]):
                out.append(background_item(spec, background.get(spec["key"])))
            elif spec["part"] == "groups":
                out.append(group_item(spec, sg.evaluate_group(spec["doc"], ctx), readings))
            else:
                out.append(set_item(spec, sg.evaluate_set(spec["doc"], ctx, subject_context=subject_context)))
        except Exception as exc:          # one block never breaks the panel
            out.append({"key": spec["key"], "part": spec["part"], "title": f"{spec['name']} · could not be worked out",
                        "rows": [], "note": str(exc)[:200], "lattice": lattice_pick(spec), "name": spec["name"]})
    return out


def block_html(item: dict) -> str:
    """The inside of one block."""
    from signals_view import mini_bar, signed

    parts = []
    if item["part"] == "groups":
        for r in item["rows"]:
            if r["role"] == "score":
                share = f"{r['share'] * 100:.0f}% of the score" if r.get("share") else ""
                parts.append(
                    "<div style='display:flex;align-items:center;gap:10px;padding:4px 0;flex-wrap:wrap;'>"
                    f"<span style='width:210px;'>{_esc(r['name'])}</span>{mini_bar(r['percent'], 90)}"
                    f"<span style='width:44px;text-align:right;font-weight:600;'>{signed(r['percent'])}</span>"
                    f"<span class='ang-kicker' title='{_esc(share)}'>{_esc(r['text'])}</span></div>")
            else:
                word = {"veto": "🚫 Veto", "condition": "🔀 Condition"}.get(r["role"], r["role"].title())
                parts.append(
                    "<div style='display:flex;align-items:center;gap:10px;padding:4px 0;flex-wrap:wrap;'>"
                    f"<span style='width:210px;'>{_esc(r['name'])}</span>"
                    f"<span style='font-size:12px;'>{_esc(word)}</span>"
                    f"<span class='ang-kicker'>{_esc(r['text'])}</span></div>")
    else:
        for r in item["rows"]:
            parts.append(
                "<div style='display:flex;align-items:center;gap:10px;padding:4px 0;flex-wrap:wrap;'>"
                f"<span style='min-width:24px;font-weight:700;'>{_esc(str(r['value'])[:1])}</span>"
                f"<span style='flex:1 1 220px;'>{_esc(r['text'])}</span>"
                f"<span class='ang-kicker'>reading: {_esc(str(r['value'])[1:].strip() or r['value'])}</span></div>")
    if item.get("note"):
        parts.append(f"<div class='ang-kicker' style='margin-top:8px;'>{_esc(item['note'])}</div>")
    if item.get("detail_note"):
        parts.append(f"<div class='ang-kicker' style='margin-top:4px;opacity:.8;'>{_esc(item['detail_note'])}</div>")
    return "".join(parts) or "<div class='ang-kicker'>Nothing to show yet.</div>"
