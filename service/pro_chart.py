"""The Pro chart for the new app: the classic chart's data (lw_chart.build_payload), built the same way the classic
app builds it (_tv_candles and _tv_chart in app.py), without Streamlit. The browser draws it with a port of
lw_chart.js and lw_draw.js (web/src/pages/asset/pro/).

options(): what the chart controls can offer for one asset (candle sizes, ranges, indicators, Sonar markers, Sets).
payload(): the chart itself for one choice of candle size, range and indicators.
"""
from __future__ import annotations

import threading
import time

import pandas as pd

import chart_candles
import chart_data
import chart_plan
import i18n
import lw_chart

LIQ_KEY, FVG_KEY, SP_KEY = "liq", "fvg", "single_prints"
SP_INTERVALS = ("5m", "15m", "30m", "1h", "4h")
ICONS = {"sma200": "📏", "ichimoku": "☁️", "cipher": "📡", "sonar_marks": "🛰️", "shapes": "📐", "rsi": "🌡️",
         "macd": "〰️", "stoch": "🎚️", "stochrsi": "🎛️", "adx": "🧭", "obv": "📊"}
SONAR_LABELS = {"trend_turn_up": "🔺 Trend turn up", "trend_turn_down": "🔻 Trend turn down", "long_cross": "🟢 Green dot",
                "short_cross": "🔴 Red dot", "red_cross": "❌ Red cross", "red_diamond": "♦️ Red diamond",
                "blood_diamond": "🩸 Blood diamond", "yellow_cross": "⚠️ Yellow cross", "strength_candle": "🔶 Strength"}

_frames: dict = {}
_lock = threading.Lock()
FRAME_TTL = 60          # seconds: candles with indicators, shared by everyone looking at the same chart


def _kind(asset_type: str) -> str:
    return "crypto" if asset_type == "Crypto" else "equity"


def _stored_daily(db, asset_type: str, aid: str):
    """The shared daily prices (asset_market), for coins neither Binance nor Yahoo has candles for."""
    import market_store

    key = market_store.asset_market_key(asset_type, aid)
    try:
        return market_store.frame_from_row(market_store.load_shared_market(db, [key]).get(key))
    except Exception:
        return None


def candles_with_indicators(db, asset_type: str, aid: str, interval: str, range_key: str) -> dict:
    """{frame, start, session, source} or {error}. As app._tv_candles, cached for a minute across members."""
    from chart_indicators import add_chart_only
    from scoring import calculate_indicators

    token = (asset_type, aid, interval, range_key)
    with _lock:
        hit = _frames.get(token)
        if hit and time.time() - hit[0] < FRAME_TTL:
            return hit[1]
    kind = _kind(asset_type)
    loaded = chart_candles.load_candles(kind, aid, interval, range_key)
    if loaded["error"] and interval in ("1D", "1W", "1Mo") and chart_candles.availability(interval, range_key)[0]:
        daily = _stored_daily(db, asset_type, aid)
        if daily is not None and not daily.empty:
            base = daily[["open", "high", "low", "close", "volume"]]
            candles = (chart_data.group_daily(base) if interval == "1D" else chart_data.group_weekly(base)
                       if interval == "1W" else chart_candles.group_monthly(base))
            if len(candles) >= chart_data.MIN_CANDLES:
                candles = (chart_candles.mark_forming(candles) if interval == "1Mo"
                           else chart_data.mark_forming(candles, interval, kind))
                days = chart_data.RANGE_DAYS[range_key]
                start = candles.index[0] if days is None else max(
                    candles.index[0], pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days))
                loaded = {"candles": candles, "start": start, "session": None, "error": None,
                          "source": i18n.t("Shared daily prices (neither Binance nor Yahoo has candles for this coin)")
                          + (i18n.t(", grouped into weeks") if interval == "1W" else
                             i18n.t(", grouped into months") if interval == "1Mo" else "")}
    if loaded["error"]:
        return {"error": loaded["error"]}
    candles = loaded["candles"]
    frame = calculate_indicators(candles[["open", "high", "low", "close", "volume"]])
    frame["forming"] = candles["forming"]
    frame = add_chart_only(frame)
    out = {"frame": frame, "start": loaded.get("start"), "session": loaded.get("session"),
           "source": loaded.get("source") or ""}
    with _lock:
        if len(_frames) > 200:
            _frames.clear()
        _frames[token] = (time.time(), out)
    return out


def _earnings(db, aid: str):
    """(past report days, next report day or None) for a stock."""
    import market_store

    past, nxt = [], None
    try:
        past = list(market_store.held_report_dates(market_store.load_earnings_history(db, aid.upper())))
    except Exception:
        past = []
    try:
        key = market_store.asset_market_key("Stock", aid.upper())
        nxt = market_store.earnings_from_rows(market_store.load_shared_market(db, [key])).get(aid.upper())
    except Exception:
        nxt = None
    return past, nxt


def _liquidation(db, aid: str):
    import market_store

    try:
        rows = (db.table("asset_market").select("liq_levels, liq_updated_at")
                .eq("asset_key", market_store.asset_market_key("Crypto", aid)).limit(1).execute().data or [])
    except Exception:
        return None
    if not rows or not isinstance(rows[0].get("liq_levels"), dict):
        return None
    record = dict(rows[0]["liq_levels"])
    record["updated_at"] = rows[0].get("liq_updated_at")
    return record


def _events():
    import macro_calendar as mc

    return [e for e in mc.events() if e.get("kind") in ("fomc", "cpi", "jobs")]


def _single_prints(asset_type: str, aid: str, frame) -> list:
    try:
        import single_prints

        loaded = chart_candles.load_candles(_kind(asset_type), aid, "30m", "1M")
        if loaded.get("error"):
            return []
        return single_prints.payload(single_prints.zones(loaded["candles"], loaded.get("session")), frame.index)
    except Exception:
        return []


def set_options(db, owner_id: str) -> dict:
    """key -> (name, document) for Sets that can be drawn as bands: the provided ones and the member's own that read
    daily or weekly candles only (as app._chart_set_options)."""
    import column_answers
    import perspectives
    import signal_groups_inspector as gi
    import table_columns

    def named(doc: dict, name: str, tail: str = "") -> str:
        icons = perspectives.icons(doc)
        return f"{name} {icons}{tail}".replace("  ", " ") if icons else f"{name}{tail}"

    out = {}
    for key, doc in table_columns.provided_sets().items():
        if not doc["name"].endswith("(demo)"):
            out[key] = (named(doc, doc["name"], " (provided)"), doc)
    try:
        saved, _ = gi.saved_configs(db)
    except Exception:
        saved = []
    for c in saved or []:
        if c.get("kind") != "set" or not c.get("versions"):
            continue
        doc = c["versions"][-1].get("body") or {}
        if doc.get("decision") and set(column_answers.timeframes(doc)) <= {"1D", "1W"}:
            out[f"saved:{c['id']}"] = (named(doc, c["name"]), doc)
    return out


def _bands(db, owner_id: str, asset_type: str, aid: str, band: str, show_no: bool, frame) -> dict | None:
    import column_answers  # noqa: F401  (set_history needs it loaded)
    import set_history

    found = set_options(db, owner_id).get(band)
    if not found:
        return None
    doc = found[1]
    kind = _kind(asset_type)
    span_list = set_history.history_for(db, doc, kind, aid if kind == "crypto" else aid.upper())
    if not span_list:
        return {"none": i18n.t("No long daily history is available for this asset, so the Set can't be shown on the chart.")}
    days = [pd.Timestamp(x).strftime("%Y-%m-%d") for x in frame.index]
    stats = set_history.summary(span_list)
    return {"colors": set_history.colours_for(days, span_list, show_no),
            "answers": set_history.answers_for(days, span_list), "name": doc.get("name") or "Set",
            "legend": (i18n.t("{name}: green = Yes ({n} times since {year}), amber = Unknown", name=doc.get("name"),
                              n=stats["episodes"]["yes"], year=span_list[0][0][:4])
                       + (i18n.t(", red = No") if show_no else ""))}


def options(db, owner_id: str, asset_type: str, lang: str) -> dict:
    with i18n.using(lang):
        sets = [{"key": k, "name": v[0]} for k, v in set_options(db, owner_id).items()]
        return {
            "intervals": list(chart_candles.INTERVALS),
            "ranges": list(chart_candles.RANGES),
            "indicators": [[k, f"{ICONS.get(k, '')} {i18n.t(v['label'])}".strip()] for k, v in chart_plan.INDICATORS.items()]
                          + ([[LIQ_KEY, i18n.t("🔥 Liquidation levels")]] if asset_type == "Crypto" else [])
                          + [[FVG_KEY, i18n.t("🕳️ Fair value gaps")], [SP_KEY, i18n.t("📍 Single prints")]],
            "single_print_intervals": list(SP_INTERVALS),
            "sonar_marks": [[k, SONAR_LABELS[k], v[4]] for k, v in lw_chart.SONAR_MARKS.items()],
            "sonar_default": list(lw_chart.SONAR_DEFAULT),
            "sets": sets,
        }


def payload(db, owner_id: str, asset_type: str, aid: str, ask, lang: str, title: str = "") -> dict:
    """The classic chart's data for one choice. `ask` carries interval, range, indicators, overlay, sonar_marks,
    dot_buildup, earnings, events, fvg, single_prints, band, band_no, dark, price_px."""
    with i18n.using(lang):
        usable, reason = chart_candles.availability(ask.interval, ask.range)
        if not usable:
            return {"error": i18n.t(reason), "nearest": chart_candles.nearest_range(ask.interval, ask.range)}
        tv = candles_with_indicators(db, asset_type, aid, ask.interval, ask.range)
        if tv.get("error"):
            return {"error": i18n.t(tv["error"])}
        frame = tv["frame"]
        wanted = set(ask.indicators or [])
        chosen = [k for k in chart_plan.INDICATORS if k in wanted]
        layout = chart_plan.plan(chosen, frame.columns, overlay_curves=bool(ask.overlay))
        layout["sonar_marks"] = [k for k in (ask.sonar_marks or []) if k in lw_chart.SONAR_MARKS] \
            if ask.sonar_marks is not None else None
        layout["dot_buildup"] = bool(ask.dot_buildup)
        past, nxt = (_earnings(db, aid) if asset_type != "Crypto" and ask.earnings else ([], None))
        liq = _liquidation(db, aid) if asset_type == "Crypto" and LIQ_KEY in wanted else None
        data = lw_chart.build_payload(
            frame, layout, kind=_kind(asset_type), interval=ask.interval, range_key=ask.range,
            session=tv.get("session"), range_start=tv.get("start"),
            view_key=f"{asset_type}:{aid}|{ask.interval}|{ask.range}",
            price_px=max(220, min(1100, int(ask.price_px or 460))), dark=bool(ask.dark),
            past_reports=past, next_report=nxt, liquidation=liq, source=tv.get("source") or "", title=title,
            events=_events() if ask.events else (),
        )
        data.pop("lib", None)
        data["fvg"] = FVG_KEY in wanted
        data["single_prints"] = _single_prints(asset_type, aid, frame) \
            if SP_KEY in wanted and ask.interval in SP_INTERVALS else []
        note = ""
        if ask.band:
            try:
                bands = _bands(db, owner_id, asset_type, aid, ask.band, bool(ask.band_no), frame)
            except Exception as exc:
                bands = {"none": i18n.t("Could not work out the Set's history: {str_exc_160}", str_exc_160=str(exc)[:160])}
            if bands and bands.get("colors"):
                data["zones"], data["zones_legend"] = bands["colors"], bands["legend"]
                data["zones_answers"], data["zones_name"] = bands["answers"], bands["name"]
            elif bands:
                note = bands.get("none") or ""
        data["skipped"] = layout.get("skipped") or []
        return {"payload": data, "note": note}
