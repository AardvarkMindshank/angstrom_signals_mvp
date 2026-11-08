"""
Visualize History as one TradingView chart (agreed plan, Stage B): the chosen asset's daily candles on top with the
Set's answers as coloured bands behind them, and underneath one thin pane per asset in the scan, each with its own
price line and its own bands, all on the same time axis (like the main chart's indicator panels).

Every row is lined up on the chosen asset's days (a share's price is carried over weekends when a coin is chosen).
No Streamlit here: prism_view draws the payload with lw_chart.js.
"""

from __future__ import annotations

import pandas as pd

import lw_chart
import set_history as sh

ROW_PX = 56
MAIN_PX = 320


def payload(strip: dict, selected: str, years: int, frames=sh.full_daily, dark: bool = False,
            show_no: bool = False, set_name: str = "Set") -> dict | None:
    rows = [r for r in strip.get("rows") or [] if r.get("spans")]
    if not rows:
        return None
    main = next((r for r in rows if r["key"] == selected), rows[0])
    frame = frames(main["kind"], main["id"])
    if frame is None or frame.empty:
        return None
    df = frame[["open", "high", "low", "close", "volume"]].copy()
    if years:
        df = df[df.index >= df.index[-1] - pd.Timedelta(days=int(365.25 * years))]
    df["forming"] = False
    days = [t.strftime("%Y-%m-%d") for t in df.index]
    out = lw_chart.build_payload(
        df, {"panels": [], "overlays": [], "secondary": []}, kind=main["kind"], interval="1D",
        range_key="All", view_key=f"history|{selected}|{years}|{len(rows)}", price_px=MAIN_PX, dark=dark,
        source="Daily prices from Yahoo", title=f"{main['name']} · {set_name}")
    out["pane_keys"] = [main["key"]]
    out["log_scale"] = True                   # ten years of prices span a huge range: equal steps are equal % moves
    out["zones"] = sh.colours_for(days, main["spans"], show_no)
    out["zones_answers"] = sh.answers_for(days, main["spans"])
    out["zones_name"] = set_name
    out["zones_legend"] = f"{set_name}: green = Yes, amber = Unknown" + (", red = No" if show_no else "")
    for r in rows:
        if r["key"] == main["key"]:
            continue
        other = frames(r["kind"], r["id"])
        if other is None or other.empty:
            continue
        closes = other["close"].reindex(df.index, method="ffill")
        closes[df.index < other.index[0]] = float("nan")
        pane = len(out["panes"])
        out.setdefault("pane_keys", [main["key"]]).append(r["key"])
        out["panes"].append({"title": r["name"], "height": ROW_PX})
        out["series"].append({
            "id": f"row_{r['key']}", "type": "line", "name": r["name"], "pane": pane,
            "values": lw_chart._values(closes), "color": "#64748b", "width": 1, "legend": True,
            "zones": sh.colours_for(days, r["spans"], show_no)})
    return out
