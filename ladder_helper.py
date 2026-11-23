"""
🪜 Ladder helper (19 Nov 2026): plan a ladder of limit orders below the price (or above it, for a short) instead of
buying all at once, spaced by the coin's own typical daily move (ATR 14 of daily candles), with a stop beyond the last
order. A calculator for planning: nothing is placed or sent anywhere.

Two styles, after a beta tester's practice:
* consolidating (a narrow range): equal orders, close to the price;
* trending (you don't want to miss the move): the order nearest the price smallest, the furthest largest (1 : 2 : 3 …).

📐 Orders can also go on Fibonacci levels (20 Nov 2026, as a beta tester ladders into the golden pocket): measured
from the member's own Fibonacci drawing on that asset, or else from the last swing low to the high since (a long; the
mirror for a short) on the chart's candles, with the stop a little past the swing (the 100% level).

Defaults come from the hourly research (30 coins, 2021 to Oct 2024): within a day of a bottom signal price dipped a
typical 0.4 daily moves further, 1 time in 4 about 0.75, 1 time in 10 about 1.3. So the deepest order sits at 0.6 daily
moves (consolidating) or 0.9 (trending), and the stop 0.4 beyond it.
"""

from __future__ import annotations

import html

STYLES = {"consolidating": {"first": 0.15, "deepest": 0.6, "weights": "equal"},
          "trending": {"first": 0.3, "deepest": 0.9, "weights": "rising"}}
STOP_BEYOND = 0.4                          # daily moves past the deepest order
PLACES = ("moves", "fib")                  # orders spaced by daily moves, or on Fibonacci levels
FIB_SETS = {2: (0.618, 0.786), 3: (0.5, 0.618, 0.786), 4: (0.5, 0.618, 0.65, 0.786),
            5: (0.382, 0.5, 0.618, 0.65, 0.786), 6: (0.236, 0.382, 0.5, 0.618, 0.65, 0.786)}
FIB_STOP_BEYOND = 0.2                      # daily moves past the swing (the 100% level) for the stop
SWING = 5                                  # candles each side that make a swing low or high


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
        rows.append({"n": i, "price": p, "pct": (p / price - 1) * 100, "moves": d, "share": s, "fib": None,
                     "amount": amount * s if amount else None})
    stop_moves = deep + STOP_BEYOND
    stop = price + sign * stop_moves * atr
    avg = 1 / sum(r["share"] / r["price"] for r in rows)       # the average price paid for the whole amount
    loss_pct = (stop / avg - 1) * 100 * (1 if side == "long" else -1)
    return {"ok": True, "rows": rows, "stop": stop, "stop_pct": (stop / price - 1) * 100, "stop_moves": stop_moves,
            "avg": avg, "avg_pct": (avg / price - 1) * 100, "loss_pct": loss_pct,
            "loss_amount": amount * loss_pct / 100 if amount else None, "atr_pct": atr / price * 100}


def _rows(price, prices, levels, moves, style, amount, sign):
    cfg = STYLES.get(style, STYLES["consolidating"])
    raw = [1.0] * len(prices) if cfg["weights"] == "equal" else [float(i + 1) for i in range(len(prices))]
    shares = [w / sum(raw) for w in raw]
    return [{"n": i, "price": p, "pct": (p / price - 1) * 100, "moves": m, "share": s, "fib": f,
             "amount": amount * s if amount else None}
            for i, (p, m, s, f) in enumerate(zip(prices, moves, shares, levels), start=1)]


def _finish(price, atr, side, rows, stop, amount):
    avg = 1 / sum(r["share"] / r["price"] for r in rows)
    loss_pct = (stop / avg - 1) * 100 * (1 if side == "long" else -1)
    return {"ok": True, "rows": rows, "stop": stop, "stop_pct": (stop / price - 1) * 100,
            "stop_moves": abs(stop - price) / atr, "avg": avg, "avg_pct": (avg / price - 1) * 100, "loss_pct": loss_pct,
            "loss_amount": amount * loss_pct / 100 if amount else None, "atr_pct": atr / price * 100}


def fib_plan(price: float, atr: float, low: float, high: float, side: str = "long", style: str = "consolidating",
             orders: int = 3, amount: float | None = None) -> dict:
    """Orders on Fibonacci retracement levels of the move from `low` to `high` (a long buys the pullback from the high:
    level r = high - (high - low) x r; a short sells the bounce from the low: low + (high - low) x r). Only levels on
    the right side of the price are used (below it for a long). The stop sits FIB_STOP_BEYOND daily moves past the
    100% level. ok False, with a reason, when the swing is unusable or no level is left."""
    if not price or not atr or not low or not high or high <= low or atr <= 0:
        return {"ok": False, "reason": "no_swing"}
    levels = FIB_SETS[max(2, min(6, int(orders)))]
    sign = -1 if side == "long" else 1
    at = (lambda r: high - (high - low) * r) if side == "long" else (lambda r: low + (high - low) * r)
    picked = [(r, at(r)) for r in levels if (at(r) < price if side == "long" else at(r) > price)]
    if not picked:
        return {"ok": False, "reason": "past_levels"}
    prices = [p for _r, p in picked]
    rows = _rows(price, prices, [r for r, _p in picked], [abs(p - price) / atr for p in prices], style, amount, sign)
    stop = (low - FIB_STOP_BEYOND * atr) if side == "long" else (high + FIB_STOP_BEYOND * atr)
    return {**_finish(price, atr, side, rows, stop, amount), "low": low, "high": high}


def last_swing(frame, side: str = "long", swing: int = SWING) -> dict | None:
    """The move a Fibonacci is drawn on: for a long, the last swing low (swing candles each side) and the highest high
    since; for a short, the last swing high and the lowest low since. {low, high} or None."""
    if frame is None or len(frame) < swing * 2 + 3:
        return None
    from signal_library.swings import pivots

    high, low = frame["high"].astype(float).to_numpy(), frame["low"].astype(float).to_numpy()
    kind = "low" if side == "long" else "high"
    found = [p for p in pivots(high, low, swing, swing) if p["kind"] == kind]
    if not found:
        return None
    i = found[-1]["index"]
    if side == "long":
        lo, hi = float(low[i]), float(high[i:].max())
    else:
        hi, lo = float(high[i]), float(low[i:].min())
    return {"low": lo, "high": hi} if hi > lo else None


def drawn_fib(items) -> dict | None:
    """The newest Fibonacci on the chart drawings of this asset: {low, high}, or None."""
    for it in reversed(list(items or [])):
        if isinstance(it, dict) and it.get("tool") == "fib" and len(it.get("pts") or []) >= 2:
            try:
                a, b = float(it["pts"][0]["p"]), float(it["pts"][1]["p"])
            except (TypeError, ValueError, KeyError):
                continue
            if a != b:
                return {"low": min(a, b), "high": max(a, b)}
    return None


REGIME_WORDS = {"trending_up": "Trending up", "trending_down": "Trending down", "trending_mixed": "Trending, mixed",
                "ranging": "Ranging", "transitional": "Transitional"}


def auto_style(label: str | None) -> str:
    """The Market choice that fits the asset's regime: Trending for any trending regime, else Consolidating (a
    ranging or transitional market, or no reading yet)."""
    return "trending" if str(label or "").startswith("trending") else "consolidating"


def auto_side(label: str | None) -> str:
    """The side the example ladder starts on: Short in a trending-down regime, else Long. A rule to illustrate a
    ladder, said so on screen; the member picks either side."""
    return "short" if str(label or "") == "trending_down" else "long"


def note_regime(st, key: str, regime: dict | None) -> None:
    """Remember this asset's regime label, so the Market choice starts from it (the member can still change it)."""
    st.session_state[f"ladder_auto_{key}"] = (regime or {}).get("label")


def settings(st, key: str, price: float, atr: float) -> dict:
    """The helper's current choices for this asset, read before its controls are drawn (the chart above them needs
    them first). The same keys and defaults as render()."""
    ss = st.session_state
    side = ss.get(f"ladder_side_{key}") or auto_side(ss.get(f"ladder_auto_{key}"))
    style = ss.get(f"ladder_style_{key}") or auto_style(ss.get(f"ladder_auto_{key}"))
    return {"show": bool(ss.get(f"ladder_show_{key}")), "side": side, "style": style,
            "place": ss.get(f"ladder_place_{key}") or "moves",
            "orders": int(ss.get(f"ladder_n_{key}") or 3),
            "start": float(ss.get(f"ladder_px_{key}") or price or 0),
            "deepest": float(ss.get(f"ladder_deep_{key}_{style}") or STYLES[style]["deepest"]),
            "amount": float(ss.get(f"ladder_amt_{key}") or 0) or None}


def wants_fib(st, key: str) -> bool:
    return (st.session_state.get(f"ladder_place_{key}") or "moves") == "fib"


def current_plan(st, key: str, price, atr, swing: dict | None = None) -> tuple[dict, dict]:
    """(settings, plan) for this asset: by daily moves, or on the Fibonacci levels of `swing` ({low, high, origin})."""
    c = settings(st, key, price, atr)
    if c["place"] == "fib":
        if not swing:
            return c, {"ok": False, "reason": "no_swing"}
        return c, fib_plan(c["start"], atr, swing["low"], swing["high"], c["side"], c["style"], c["orders"], c["amount"])
    return c, plan(c["start"], atr, c["side"], c["style"], c["orders"], c["deepest"], c["amount"])


def _fib_words(r) -> str:
    return f"{r * 100:.1f}".rstrip("0").rstrip(".") + "%"


def chart_lines(st, key: str, price: float | None, atr: float | None, t=lambda x: x, swing: dict | None = None) -> list[dict]:
    """Horizontal lines for the chart when "Show on chart" is on: one per order (blue, dashed, thicker for a bigger
    share; on Fibonacci levels, labelled with the level), the stop (red) and the average price if every order fills
    (grey, dotted). [] when off."""
    if not price or not atr:
        return []
    c, p = current_plan(st, key, price, atr, swing)
    if not c["show"] or not p["ok"]:
        return []
    lines = [{"price": round(r["price"], 10), "color": "#2563eb", "width": max(1, min(4, round(r["share"] * len(p["rows"]) * 2))),
              "style": "dashed", "label": f"{t('Order')} {r['n']} · {r['share'] * 100:.0f}%"
              + (f" · {_fib_words(r['fib'])}" if r.get("fib") is not None else "")} for r in p["rows"]]
    lines.append({"price": round(p["stop"], 10), "color": "#dc2626", "width": 2, "style": "solid", "label": t("Stop")})
    lines.append({"price": round(p["avg"], 10), "color": "#64748b", "width": 1, "style": "dotted",
                  "label": t("Average if all fill")})
    return lines


def _price(v: float) -> str:
    a = abs(v)
    digits = 2 if a >= 100 else 3 if a >= 1 else 5 if a >= 0.01 else 8
    return f"{v:,.{digits}f}"


def render(st, t, price: float | None, atr: float | None, name: str, key: str, swing: dict | None = None) -> None:
    """The helper's controls and its table, for the asset on the chart. swing = the move the Fibonacci orders are
    measured on ({low, high, origin: "drawing" or "swing"}), when orders go on Fibonacci levels."""
    if not price or not atr:
        st.caption(t("The ladder helper needs at least 15 days of prices for this asset."))
        return
    c1, c2, c3 = st.columns([1.2, 1.4, 1])
    regime_label = st.session_state.get(f"ladder_auto_{key}")
    side_preset = auto_side(regime_label)
    side = c1.segmented_control(t("Side"), ["long", "short"], default=side_preset, key=f"ladder_side_{key}",
                                format_func=lambda v: {"long": "📈 " + t("Long"), "short": "📉 " + t("Short")}[v],
                                help=t("Long: orders below the price. Short: orders above it."))
    preset = auto_style(regime_label)
    style = c2.segmented_control(t("Market"), ["consolidating", "trending"], default=preset,
                                 key=f"ladder_style_{key}",
                                 format_func=lambda v: {"consolidating": "🧱 " + t("Consolidating"),
                                                        "trending": "🚀 " + t("Trending")}[v],
                                 help=t("Consolidating: equal orders, close to the price. Trending: the order "
                                        "nearest the price smallest, the furthest largest."))
    orders = c3.number_input(t("Orders"), 2, 6, 3, key=f"ladder_n_{key}")
    side, style = side or side_preset, style or preset
    if str(regime_label or "").startswith("trending_") and regime_label in REGIME_WORDS:
        c1.caption(t("Starts on {side} by a simple rule: the regime reads {regime}. An illustration of a ladder, "
                     "not a recommendation; pick either side.",
                     side=t("Short") if side_preset == "short" else t("Long"), regime=t(REGIME_WORDS[regime_label])))
    if regime_label in REGIME_WORDS:
        c2.caption(t("Preset from this asset's regime ({regime}). Change it if you see it differently.",
                     regime=t(REGIME_WORDS[regime_label])) if style == preset else
                   t("The regime reads {regime}; you chose otherwise.", regime=t(REGIME_WORDS[regime_label])))
    place = st.segmented_control(
        t("Place the orders"), list(PLACES), default="moves", key=f"ladder_place_{key}",
        format_func=lambda v: {"moves": "📏 " + t("By daily move"), "fib": "📐 " + t("On Fibonacci levels")}[v],
        help=t("By daily move: spaced by this asset's typical daily range. On Fibonacci levels: at the retracement "
               "levels of the last move, from your own 📐 Fibonacci drawing on this asset, or else from the last swing "
               "low to the high since (a short: the last swing high to the low since), with the stop just past the "
               "swing.")) or "moves"
    if place == "fib":
        if swing:
            where = (t("your Fibonacci drawing") if swing.get("origin") == "drawing"
                     else t("the last swing on these candles"))
            st.caption("📐 " + t("Measured on {where}: low {low}, high {high}.", where=where, low=_price(swing["low"]),
                                 high=_price(swing["high"])))
        else:
            st.caption("📐 " + t("No swing found on these candles. Draw a Fibonacci on the chart, or pick a longer range."))
    c4, c5, c6 = st.columns([1.2, 1.4, 1])
    start = c4.number_input(t("From price"), min_value=0.0, value=float(price), format="%.6g", key=f"ladder_px_{key}",
                            help=t("The latest close; change it to plan from another price."))
    if place == "fib":
        deepest = None
        c5.caption(t("Levels used: {levels}", levels=", ".join(_fib_words(r) for r in FIB_SETS[max(2, min(6, int(orders)))])))
    else:
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
    if place == "fib":
        p = fib_plan(start, atr, swing["low"], swing["high"], side, style, orders, amount or None) if swing else \
            {"ok": False, "reason": "no_swing"}
        if not p["ok"]:
            if p.get("reason") == "past_levels":
                st.caption(t("Price is already past every Fibonacci level of this move on that side. Pick fewer "
                             "orders, the other side, or draw a new Fibonacci."))
            return
    else:
        p = plan(start, atr, side, style, orders, deepest, amount or None)
        if not p["ok"]:
            return
    fib = place == "fib"
    head = (f"<tr><th>#</th><th>{t('Price')}</th>" + (f"<th>{t('Fibonacci')}</th>" if fib else "")
            + f"<th>{t('From price')}</th><th>{t('Daily moves')}</th>"
            f"<th>{t('Share')}</th>" + (f"<th>{t('Amount')}</th>" if amount else "") + "</tr>")
    body = "".join(
        f"<tr><td>{r['n']}</td><td><b>{_price(r['price'])}</b></td>"
        + (f"<td>{_fib_words(r['fib'])}</td>" if fib else "")
        + f"<td>{r['pct']:+.2f}%</td><td>{r['moves']:.2f}</td>"
        f"<td>{r['share'] * 100:.0f}%</td>" + (f"<td>{r['amount']:,.2f}</td>" if amount else "") + "</tr>"
        for r in p["rows"])
    stop_row = (f"<tr class='lad-stop'><td>🛑</td><td><b>{_price(p['stop'])}</b></td>"
                + (f"<td>{html.escape(t('past 100%'))}</td>" if fib else "")
                + f"<td>{p['stop_pct']:+.2f}%</td>"
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
