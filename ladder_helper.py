"""
🪜 Ladder helper (19 Nov 2026): plan a ladder of limit orders below the price (or above it, for a short) instead of
buying all at once, spaced by the coin's own typical daily move (ATR 14 of daily candles), with a stop beyond the last
order. A calculator for planning: nothing is placed or sent anywhere.

Two styles, after a beta tester's practice:
* consolidating (a narrow range): equal orders, close to the price;
* trending (you don't want to miss the move): the order nearest the price smallest, the furthest largest (1 : 2 : 3 …).

Defaults come from the hourly research (30 coins, 2021 to Oct 2024): within a day of a bottom signal price dipped a
typical 0.4 daily moves further, 1 time in 4 about 0.75, 1 time in 10 about 1.3. So the deepest order sits at 0.6 daily
moves (consolidating) or 0.9 (trending), and the stop 0.4 beyond it.
"""

from __future__ import annotations

import html

STYLES = {"consolidating": {"first": 0.15, "deepest": 0.6, "weights": "equal"},
          "trending": {"first": 0.3, "deepest": 0.9, "weights": "rising"}}
STOP_BEYOND = 0.4                          # daily moves past the deepest order


def plan(price: float, atr: float, side: str = "long", style: str = "consolidating", orders: int = 3,
         deepest: float | None = None, amount: float | None = None) -> dict:
    """The orders (price, distance in % and in daily moves, share of the amount), the stop, and what a fill of every
    order would mean. side = long (orders below the price) or short (above)."""
    if not price or not atr or price <= 0 or atr <= 0:
        return {"ok": False}
    cfg = STYLES.get(style, STYLES["consolidating"])
    orders = max(2, min(6, int(orders)))
    deep = float(deepest if deepest is not None else cfg["deepest"])
    first = min(cfg["first"], deep / 2)
    steps = [first + (deep - first) * i / (orders - 1) for i in range(orders)]
    raw = [1.0] * orders if cfg["weights"] == "equal" else [float(i + 1) for i in range(orders)]
    shares = [w / sum(raw) for w in raw]
    sign = -1 if side == "long" else 1
    rows = []
    for i, (d, s) in enumerate(zip(steps, shares), start=1):
        p = price + sign * d * atr
        rows.append({"n": i, "price": p, "pct": (p / price - 1) * 100, "moves": d, "share": s,
                     "amount": amount * s if amount else None})
    stop_moves = deep + STOP_BEYOND
    stop = price + sign * stop_moves * atr
    avg = 1 / sum(r["share"] / r["price"] for r in rows)       # the average price paid for the whole amount
    loss_pct = (stop / avg - 1) * 100 * (1 if side == "long" else -1)
    return {"ok": True, "rows": rows, "stop": stop, "stop_pct": (stop / price - 1) * 100, "stop_moves": stop_moves,
            "avg": avg, "avg_pct": (avg / price - 1) * 100, "loss_pct": loss_pct,
            "loss_amount": amount * loss_pct / 100 if amount else None, "atr_pct": atr / price * 100}


def settings(st, key: str, price: float, atr: float) -> dict:
    """The helper's current choices for this asset, read before its controls are drawn (the chart above them needs
    them first). The same keys and defaults as render()."""
    ss = st.session_state
    side = ss.get(f"ladder_side_{key}") or "long"
    style = ss.get(f"ladder_style_{key}") or "consolidating"
    return {"show": bool(ss.get(f"ladder_show_{key}")), "side": side, "style": style,
            "orders": int(ss.get(f"ladder_n_{key}") or 3),
            "start": float(ss.get(f"ladder_px_{key}") or price or 0),
            "deepest": float(ss.get(f"ladder_deep_{key}_{style}") or STYLES[style]["deepest"]),
            "amount": float(ss.get(f"ladder_amt_{key}") or 0) or None}


def chart_lines(st, key: str, price: float | None, atr: float | None, t=lambda x: x) -> list[dict]:
    """Horizontal lines for the chart when "Show on chart" is on: one per order (blue, dashed, thicker for a bigger
    share), the stop (red) and the average price if every order fills (grey, dotted). [] when off."""
    if not price or not atr:
        return []
    c = settings(st, key, price, atr)
    if not c["show"]:
        return []
    p = plan(c["start"], atr, c["side"], c["style"], c["orders"], c["deepest"], c["amount"])
    if not p["ok"]:
        return []
    lines = [{"price": round(r["price"], 10), "color": "#2563eb", "width": max(1, min(4, round(r["share"] * len(p["rows"]) * 2))),
              "style": "dashed", "label": f"{t('Order')} {r['n']} · {r['share'] * 100:.0f}%"} for r in p["rows"]]
    lines.append({"price": round(p["stop"], 10), "color": "#dc2626", "width": 2, "style": "solid", "label": t("Stop")})
    lines.append({"price": round(p["avg"], 10), "color": "#64748b", "width": 1, "style": "dotted",
                  "label": t("Average if all fill")})
    return lines


def _price(v: float) -> str:
    a = abs(v)
    digits = 2 if a >= 100 else 3 if a >= 1 else 5 if a >= 0.01 else 8
    return f"{v:,.{digits}f}"


def render(st, t, price: float | None, atr: float | None, name: str, key: str) -> None:
    """The helper's controls and its table, for the asset on the chart."""
    if not price or not atr:
        st.caption(t("The ladder helper needs at least 15 days of prices for this asset."))
        return
    c1, c2, c3 = st.columns([1.2, 1.4, 1])
    side = c1.segmented_control(t("Side"), ["long", "short"], default="long", key=f"ladder_side_{key}",
                                format_func=lambda v: {"long": "📈 " + t("Long"), "short": "📉 " + t("Short")}[v],
                                help=t("Long: orders below the price. Short: orders above it."))
    style = c2.segmented_control(t("Market"), ["consolidating", "trending"], default="consolidating",
                                 key=f"ladder_style_{key}",
                                 format_func=lambda v: {"consolidating": "🧱 " + t("Consolidating"),
                                                        "trending": "🚀 " + t("Trending")}[v],
                                 help=t("Consolidating: equal orders, close to the price. Trending: the order "
                                        "nearest the price smallest, the furthest largest."))
    orders = c3.number_input(t("Orders"), 2, 6, 3, key=f"ladder_n_{key}")
    side, style = side or "long", style or "consolidating"
    c4, c5, c6 = st.columns([1.2, 1.4, 1])
    start = c4.number_input(t("From price"), min_value=0.0, value=float(price), format="%.6g", key=f"ladder_px_{key}",
                            help=t("The latest close; change it to plan from another price."))
    deepest = c5.slider(t("Deepest order, in daily moves"), 0.2, 2.0, STYLES[style]["deepest"], 0.05,
                        key=f"ladder_deep_{key}_{style}",
                        help=t("One daily move = this asset's typical daily range (ATR 14), {pct:.1f}% now.",
                               pct=atr / price * 100))
    amount = c6.number_input(t("Amount (optional)"), min_value=0.0, value=0.0, step=100.0, key=f"ladder_amt_{key}",
                             help=t("The total to split across the orders, in your account's currency."))
    st.toggle("📏 " + t("Show on chart"), key=f"ladder_show_{key}",
              help=t("Draws the orders (blue, thicker for a bigger share), the stop (red) and the average price if "
                     "every order fills (grey) as lines across the chart above. A plan from the price here, not live "
                     "orders."))
    p = plan(start, atr, side, style, orders, deepest, amount or None)
    if not p["ok"]:
        return
    head = (f"<tr><th>#</th><th>{t('Price')}</th><th>{t('From price')}</th><th>{t('Daily moves')}</th>"
            f"<th>{t('Share')}</th>" + (f"<th>{t('Amount')}</th>" if amount else "") + "</tr>")
    body = "".join(
        f"<tr><td>{r['n']}</td><td><b>{_price(r['price'])}</b></td><td>{r['pct']:+.2f}%</td><td>{r['moves']:.2f}</td>"
        f"<td>{r['share'] * 100:.0f}%</td>" + (f"<td>{r['amount']:,.2f}</td>" if amount else "") + "</tr>"
        for r in p["rows"])
    stop_row = (f"<tr class='lad-stop'><td>🛑</td><td><b>{_price(p['stop'])}</b></td><td>{p['stop_pct']:+.2f}%</td>"
                f"<td>{p['stop_moves']:.2f}</td><td colspan='{2 if amount else 1}'>{html.escape(t('Stop'))}</td></tr>")
    st.html(
        "<style>.lad{border-collapse:collapse;font-size:.88rem;margin:4px 0 6px;}"
        ".lad th,.lad td{padding:5px 12px;text-align:right;border-bottom:1px solid var(--ang-border,#e5e7eb);}"
        ".lad th{font-weight:600;opacity:.75;font-size:.78rem;}.lad .lad-stop td{color:#b91c1c;}</style>"
        f"<table class='lad'>{head}{body}{stop_row}</table>")
    loss = t("If every order fills, the average price is {avg} ({avg_pct:+.2f}%); a stop there loses {loss:.1f}% of "
             "the amount", avg=_price(p["avg"]), avg_pct=p["avg_pct"], loss=abs(p["loss_pct"]))
    if p["loss_amount"]:
        loss += f" ({abs(p['loss_amount']):,.2f})"
    st.caption(loss + ". " + t("In our test of 30 coins on hourly candles, price dipped a typical 0.4 daily moves "
                               "further within a day after a bottom signal, 1 time in 4 about 0.75 and 1 time in 10 "
                               "about 1.3. A planning calculator: nothing is placed, and it is not advice."))
