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

import pandas as pd

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
        rows.append({"key": m.get("key"), "name": m.get("label") or m.get("key"),
                     "percent": v2.percent(part) if role == "score" else None,
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
            "status": status_marks(answer, row.get("available"), row.get("available_detail"), spec.get("doc"),
                                   spec.get("key")),
            "lattice": lattice_pick(spec), "name": spec["name"]}


def status_marks(answer: str, available: str | None, detail: str | None = None, doc: dict | None = None,
                 key: str | None = None) -> list[tuple[str, str]]:
    """The three-line status: conditions met, data complete, evidence. (icon, words) each."""
    import perspectives

    mark, _, _ = tc.ANSWER_MARK[answer if answer in tc.ANSWER_MARK else "unknown"]
    data_icon, data_words = perspectives.data_mark(available)
    if detail and detail != "All readings available":
        data_words += f": {detail}"
    return [(mark, tc.ANSWER_HOVER[answer if answer in tc.ANSWER_HOVER else "unknown"]), (data_icon, data_words),
            perspectives.evidence(doc, key)]


def with_trend(item: dict, t: dict) -> None:
    """Add the 30-day line, the week's change and the plain sentence to a block."""
    item["trend"] = t
    if item["part"] == "groups":
        item["change"] = week_change(t["scores"])
        item["sentence"] = group_sentence(item["name"], item.get("percent"), item.get("label"), item["change"])
        for r in item["rows"]:
            r["change"] = week_change(t["parts"].get(r.get("key"), []))
    else:
        item["sentence"] = set_sentence(t["answers"], t["dates"])


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


TREND_DAYS = 30
WEEK = 7


def trend(spec: dict, frame, kind: str, asset_id: str, subject_context=None, days: int = TREND_DAYS) -> dict:
    """The last `days` daily closes of one daily column: a Group's score and each part's share of it, or a Set's
    answer. frame: the stored daily bars with indicators (as the table reads them)."""
    import set_history as sh

    doc = gr.dashboard_group(spec["cluster"]) if spec["cluster"] else spec["doc"]
    out = {"dates": [], "scores": [], "parts": {}, "answers": []}
    for day in frame.index[-days:]:
        try:
            ctx, last = sh.context_at(frame, kind, day, asset_id)
        except Exception:
            continue
        if pd.Timestamp(last) != pd.Timestamp(day):
            continue
        out["dates"].append(pd.Timestamp(day).strftime("%Y-%m-%d"))
        try:
            if spec["part"] == "groups":
                result = sg.evaluate_group(doc, ctx)
                out["scores"].append(v2.percent((result.get("score") or {}).get("value")))
                for m in result.get("members") or []:
                    part = m.get("contribution") if m.get("state") == "observed" else None
                    out["parts"].setdefault(m.get("key"), []).append(v2.percent(part))
            else:
                import prism

                result = sg.evaluate_set(doc, ctx, subject_context=subject_context)
                out["answers"].append(prism.row("", result, "")["answer"])
        except Exception:
            out["scores"].append(None) if spec["part"] == "groups" else out["answers"].append("unknown")
    return out


def week_change(values: list) -> int | None:
    """Change over the last WEEK closes, or None."""
    if len(values) <= WEEK or values[-1] is None or values[-1 - WEEK] is None:
        return None
    return int(values[-1] - values[-1 - WEEK])


def group_sentence(name: str, pct, label, change) -> str:
    if pct is None:
        return f"{name} has no reading today."
    now = f"{name} reads {label.lower() if label else 'neutral'} ({pct:+d})"
    if change is None:
        return now + "."
    if abs(change) < 5:
        return now + "; it has barely changed over the past week."
    return now + f"; it has {'risen' if change > 0 else 'fallen'} {abs(change)} points over the past week."


def set_sentence(answers: list, dates: list) -> str:
    if not answers:
        return ""
    last = answers[-1]
    run = 1
    while run < len(answers) and answers[-1 - run] == last:
        run += 1
    word = {"yes": "Yes", "no": "No"}.get(last, "Unknown")
    days = f"{run} day{'s' if run > 1 else ''}" if run < len(answers) else f"all of the last {len(answers)} days"
    text = f"{word} for {days}"
    yes = sum(a == "yes" for a in answers)
    if last != "yes" and yes:
        when = pd.Timestamp(dates[max(i for i, a in enumerate(answers) if a == "yes")]).strftime("%-d %b")
        text += f"; last Yes on {when}"
    if run < len(answers):
        text += f" (Yes on {yes} of the last {len(answers)} days)"
    return text + "."


def items(specs: list[dict], ctx, readings: dict, subject_context=None, background: dict | None = None,
          frame=None, kind: str | None = None, asset_id: str | None = None) -> list[dict]:
    """One block per chosen column, in table order. background: column key -> the stored answer for columns that
    read 4-hour or hourly candles. frame/kind/asset_id: the stored daily bars, for the 30-day trend of each daily
    column (left out when not given)."""
    out = []
    background = background or {}
    for spec in specs:
        try:
            if spec["cluster"]:
                item = group_item(spec, sg.evaluate_group(gr.dashboard_group(spec["cluster"]), ctx), readings)
            elif spec["doc"] is None:
                continue
            elif not tc.daily_only(spec["doc"]):
                out.append(background_item(spec, background.get(spec["key"])))
                continue
            elif spec["part"] == "groups":
                item = group_item(spec, sg.evaluate_group(spec["doc"], ctx), readings)
            else:
                item = set_item(spec, sg.evaluate_set(spec["doc"], ctx, subject_context=subject_context))
            if frame is not None:
                try:
                    with_trend(item, trend(spec, frame, kind, asset_id, subject_context))
                except Exception:
                    pass
            out.append(item)
        except Exception as exc:          # one block never breaks the panel
            out.append({"key": spec["key"], "part": spec["part"], "title": f"{spec['name']} · could not be worked out",
                        "rows": [], "note": str(exc)[:200], "lattice": lattice_pick(spec), "name": spec["name"]})
    return out


def sparkline(values: list, width: int = 140, height: int = 32) -> str:
    """A small line of a Group's score over the last days (−100 to +100, the zero line dashed)."""
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 2:
        return ""
    n = max(len(values) - 1, 1)
    y = lambda v: round(height / 2 - v / 100 * (height / 2 - 2), 1)  # noqa: E731
    line = " ".join(f"{round(i / n * width, 1)},{y(v)}" for i, v in pts)
    last_x, last_y = round(pts[-1][0] / n * width, 1), y(pts[-1][1])
    return (f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' aria-hidden='true' "
            f"style='overflow:visible'><line x1='0' x2='{width}' y1='{height / 2}' y2='{height / 2}' "
            f"stroke='currentColor' stroke-opacity='.25' stroke-dasharray='3 3'/>"
            f"<polyline points='{line}' fill='none' stroke='currentColor' stroke-opacity='.75' stroke-width='1.6' "
            f"stroke-linejoin='round'/><circle cx='{last_x}' cy='{last_y}' r='2.4' fill='currentColor'/></svg>")


STRIP = {"yes": ("#3f9d5a", "Yes"), "no": ("rgba(127,127,127,.28)", "No"), "unknown": ("transparent", "Unknown")}


def strip(answers: list, dates: list) -> str:
    """One small box per day: Yes filled, No grey, Unknown outlined. Hover shows the day."""
    boxes = []
    for a, d in zip(answers, dates):
        colour, word = STRIP.get(a, STRIP["unknown"])
        boxes.append(f"<span title='{_esc(d)}: {word}' style='display:inline-block;width:6px;height:16px;"
                     f"margin-right:1px;border-radius:1px;background:{colour};"
                     f"border:1px solid rgba(127,127,127,.35)'></span>")
    return f"<span aria-label='Last {len(answers)} days' style='white-space:nowrap'>{''.join(boxes)}</span>"


def _change(change) -> str:
    if change is None:
        return ""
    if abs(change) < 1:
        return "<span class='ang-kicker' title='Change over the past week'>→ 0 this week</span>"
    arrow = "▲" if change > 0 else "▼"
    return f"<span class='ang-kicker' title='Change over the past week'>{arrow} {change:+d} this week</span>"


def head_html(item: dict) -> str:
    """The card's top: the line or strip for the last 30 days, the week's change and one plain sentence."""
    t = item.get("trend")
    if not t:
        return ""
    if item["part"] == "groups":
        visual = sparkline(t["scores"])
        side = _change(item.get("change"))
    else:
        visual = strip(t["answers"], t["dates"])
        side = ""
    days = len(t["dates"])
    return ("<div style='display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:2px 0 6px'>"
            f"<span title='The last {days} daily closes'>{visual}</span>{side}</div>"
            + (f"<div style='margin:0 0 8px'>{_esc(item['sentence'])}</div>" if item.get("sentence") else ""))


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
                    f"<span class='ang-kicker' title='{_esc(share)}'>{_esc(r['text'])}</span>"
                    f"{_change(r.get('change'))}</div>")
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
    if item.get("trend"):
        parts.insert(0, head_html(item))
    if item.get("status"):
        marks = "".join(f"<span title='{_esc(w)}' aria-label='{_esc(w)}' style='cursor:help;margin-right:10px'>"
                        f"{_esc(i)} <span class='ang-kicker'>{_esc(w.split(':')[0])}</span></span>"
                        for i, w in item["status"])
        parts.insert(0, f"<div style='margin:2px 0 8px'>{marks}</div>")
    if item.get("note"):
        parts.append(f"<div class='ang-kicker' style='margin-top:8px;'>{_esc(item['note'])}</div>")
    if item.get("detail_note"):
        parts.append(f"<div class='ang-kicker' style='margin-top:4px;opacity:.8;'>{_esc(item['detail_note'])}</div>")
    return "".join(parts) or "<div class='ang-kicker'>Nothing to show yet.</div>"
