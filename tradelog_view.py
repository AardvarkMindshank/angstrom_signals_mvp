"""📒 Trade Log page (spec v0.5, phase 1): connect eToro with a read-only key, then an Overview tab and one tab per
connection, the trade list, and each trade's detail with what MarketNavi read at entry and exit.

Reads with the member's own session (row-level security: their rows only). Keys are typed here and passed straight
to the database function that puts them in Vault; this page never shows, stores or logs them.
Plans: Free has no Trade Log; Plus one connection and the last 90 days; Pro every platform, full history; Elite
several accounts per platform.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

import tradelog
from i18n import mark, t

PLATFORMS = {"etoro": "eToro", "binance": "Binance"}
CONNECTIONS = {"free": 0, "plus": 1, "pro": 2, "elite": 10}
HISTORY_DAYS = {"plus": 90}
REGIME_WORDS = {"trending_up": mark("Trending up"), "trending_down": mark("Trending down"),
                "trending_mixed": mark("Trending, mixed"), "ranging": mark("Ranging"),
                "transitional": mark("Transitional")}
REGIME_DOTS = {"trending_up": "🟢", "trending_down": "🔴", "ranging": "⚪", "transitional": "🟡",
               "trending_mixed": "🟡"}
CLASS_WORDS = {"crypto": mark("Crypto"), "stocks": mark("Stocks"), "etfs": mark("ETFs"), "indices": mark("Indices"),
               "commodities": mark("Commodities"), "currencies": mark("Currencies"), "other": mark("Other")}
STATUS_WORDS = {"new": mark("Importing"), "importing": mark("Importing"), "ok": mark("Connected"),
                "failing": mark("Needs attention"), "paused": mark("Paused")}
SOURCE_WORDS = {"observed": mark("observed"), "reconstructed": mark("reconstructed"),
                "unavailable": mark("not available")}
DISCLAIMER = mark("Read-only connections. Descriptive readings, not financial advice.")


# ---- data ----------------------------------------------------------------------------------------------------

def load(supabase) -> dict:
    """The member's connections, trades, snapshots and notes (their own rows only)."""
    def rows(table, cols="*", order=None):
        try:
            q = supabase.table(table).select(cols)
            if order:
                q = q.order(order, desc=True)
            return q.limit(5000).execute().data or []
        except Exception:
            return None
    conns = rows("trade_connections",
                 "id,platform,label,status,last_sync_at,last_error,history_from,created_at")
    if conns is None:
        return {"ready": False}
    return {"ready": True, "connections": conns, "trips": rows("trade_round_trips", order="closed_at") or [],
            "snapshots": rows("trade_snapshots", "round_trip_id,moment,readings,source") or [],
            "notes": rows("trade_notes", "round_trip_id,note,tags") or []}


def _zone(st) -> ZoneInfo:
    try:
        return ZoneInfo(str(getattr(st.context, "timezone", "") or "UTC"))
    except Exception:
        return ZoneInfo("UTC")


def _when(value):
    return tradelog._when(value)


def _regime(readings: dict | None) -> str:
    key = str((readings or {}).get("regime") or "")
    if not key:
        return "—"
    return f"{REGIME_DOTS.get(key, '⚪')} {t(REGIME_WORDS.get(key, key))}"


def _money(v) -> str:
    if v is None:
        return "—"
    return f"{'+' if v > 0 else '−' if v < 0 else ''}${abs(v):,.2f}"


def _usd_cols(st, *names) -> dict:
    """Money columns kept as numbers (so they sort and line up on the right), shown with a sign and two decimals."""
    return {n: st.column_config.NumberColumn(n, format="%+,.2f") for n in names}


def _pct_cols(st, *names, digits=0) -> dict:
    return {n: st.column_config.NumberColumn(n, format=f"%.{digits}f%%") for n in names}


def _signed(v, digits=0) -> str:
    return "—" if v is None else f"{v:+.{digits}f}"


# ---- connect -------------------------------------------------------------------------------------------------

def _connect_form(st, supabase, plan: str, count: int) -> None:
    limit = CONNECTIONS.get(plan, 0)
    if count >= limit:
        st.caption(t("Your plan includes {n} connection(s). Disconnect one, or upgrade, to add another.", n=limit))
        return
    st.markdown(t("**Connect eToro (read-only)**"))
    st.markdown(t(
        "1. In eToro, open **Settings → Trading → API Key Management** and create a key.\n"
        "2. Choose **Read** permission only (never Write) and your real account. Leave the IP list empty.\n"
        "3. Paste the key below, with eToro's public key. MarketNavi stores them encrypted and can only read your "
        "closed trades. It can never place, change or close a trade.\n\n"
        "MarketNavi will never ask for a key by email or message."))
    with st.form("tradelog_connect", clear_on_submit=True):
        public = st.text_input(t("eToro public key"), type="password", key="tl_public")
        user = st.text_input(t("Your eToro API key (Read)"), type="password", key="tl_user")
        label = st.text_input(t("Name for this platform's tab"), value="eToro", max_chars=30, key="tl_label",
                              help=t("Shown on the platform's tab in the Trade Log. Handy if you connect more than "
                                     "one account on the same platform, such as eToro main and eToro long-term."))
        sure = st.checkbox(t("I created this key with Read permission only"), key="tl_sure")
        if st.form_submit_button(t("Connect"), type="primary"):
            if not public.strip() or not user.strip() or not sure:
                st.warning(t("Paste both keys and tick the box first."))
                return
            try:
                supabase.rpc("tradelog_save_connection", {
                    "p_platform": "etoro", "p_label": label.strip() or "eToro",
                    "p_keys": {"api_key": public.strip(), "user_key": user.strip()}}).execute()
            except Exception:
                st.error(t("Could not save the connection. Please try again."))
                return
            st.success(t("Connected. Your closed trades will appear within about 5 minutes."))


def tab_names(conns: list[dict]) -> dict:
    """Each connection's tab name: the name the member gave it, else its platform, numbered when there are several
    on one platform (eToro, eToro 2)."""
    seen, out = {}, {}
    for c in sorted(conns, key=lambda c: str(c.get("created_at") or "")):
        base = PLATFORMS.get(c["platform"], c["platform"])
        seen[base] = seen.get(base, 0) + 1
        out[c["id"]] = (str(c.get("label") or "").strip()
                        or (base if seen[base] == 1 else f"{base} {seen[base]}"))
    return out


def _manage(st, supabase, conns: list[dict]) -> None:
    if not conns:
        return
    names = tab_names(conns)
    st.markdown(t("**Manage connections**"))
    for c in conns:
        name = names.get(c["id"])
        st.markdown(f"**{name}** · {t(STATUS_WORDS.get(c.get('status') or 'new', 'Importing'))}"
                    + (f"  \n:orange[{t(c['last_error'])}]" if c.get("last_error") else ""))
        new = st.text_input(t("Name for this platform's tab"), value=name, max_chars=30, key=f"tl_name_{c['id']}")
        if new.strip() and new.strip() != name and st.button(t("Save name"), key=f"tl_rename_{c['id']}"):
            supabase.rpc("tradelog_rename_connection", {"p_id": c["id"], "p_label": new.strip()}).execute()
            st.rerun()
        if st.button(t("Disconnect"), key=f"tl_drop_{c['id']}", icon=":material/link_off:"):
            supabase.rpc("tradelog_delete_connection", {"p_id": c["id"]}).execute()
            st.rerun()
    with st.popover(t("Delete all my Trade Log data"), icon=":material/delete:"):
        sure = st.checkbox(t("Delete every connection, trade, snapshot and note"), key="tl_wipe_sure")
        if st.button(t("Delete all my Trade Log data"), disabled=not sure, key="tl_wipe", type="primary"):
            supabase.rpc("tradelog_delete_everything", {}).execute()
            st.rerun()
    st.divider()


# ---- views ---------------------------------------------------------------------------------------------------

WHOSE = ("own", "copied", "all")


def _filters(st, key: str) -> tuple[str | None, str]:
    """(asset class or None, whose trades: "own", "copied" or "all")."""
    cols = st.columns([4, 2])
    classes = ["all", "crypto", "stocks", "etfs", "commodities", "currencies", "indices"]
    pick = cols[0].pills(
        t("Asset class"), classes, default="all", key=f"tl_class_{key}",
        format_func=lambda c: t("All") if c == "all" else t(CLASS_WORDS[c]), label_visibility="collapsed")
    whose = cols[1].segmented_control(
        t("Trades"), WHOSE, default="own", key=f"tl_whose_{key}", label_visibility="collapsed",
        format_func=lambda w: {"own": t("Yours"), "copied": t("Copied"), "all": t("All")}[w],
        help=t("Which trades to count: yours, those copied from other eToro traders, or both."))
    return (None if pick in (None, "all") else pick), (whose or "own")


def _whose(trips: list[dict], whose: str) -> list[dict]:
    if whose == "all":
        return trips
    return [x for x in trips if bool(x.get("copied")) == (whose == "copied")]


CSS = """<style>
[class*='st-key-tl_card']{background:var(--ang-surface);color:var(--ang-text);border:1px solid var(--ang-border);
  border-radius:14px;padding:14px 18px;gap:10px}
.tl-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:2px 0 8px}
.tl-tile{background:var(--ang-surface);color:var(--ang-text);border:1px solid var(--ang-border);border-radius:14px;
  padding:14px 16px;display:flex;flex-direction:column;gap:4px}
.tl-tile .k{font-size:.8rem;opacity:.72}.tl-tile .v{font-size:1.55rem;font-weight:700;line-height:1.15}
.tl-tile .s{font-size:.75rem;opacity:.65}
.tl-up{color:#15803d}.tl-down{color:#b91c1c}
.tl-h{font-weight:700;font-size:1rem;margin:0 0 4px}
.tl-bars{display:grid;grid-template-columns:105px minmax(0,1fr) 92px;gap:10px 12px;align-items:center;font-size:.9rem}
.tl-track{height:12px;border-radius:6px;background:var(--ang-track,#e5e7eb);overflow:hidden}
.tl-fill{height:12px;border-radius:6px}.tl-num{text-align:right;font-weight:600;font-variant-numeric:tabular-nums}
.tl-rows .r{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1.4fr) 92px;gap:10px;padding:7px 0;
  font-size:.9rem;border-top:1px solid var(--ang-line,rgba(127,127,127,.18))}
.tl-rows .r:first-child{border-top:0}.tl-dim{opacity:.5}.tl-note{font-size:.75rem;opacity:.65;margin-top:6px}
.tl-snap{display:grid;grid-template-columns:minmax(120px,1fr) minmax(0,1.3fr) minmax(0,1.3fr);
  border:1px solid var(--ang-border);border-radius:10px;overflow:hidden;font-size:.9rem}
.tl-snap div{padding:9px 12px;border-top:1px solid var(--ang-line,rgba(127,127,127,.18))}
.tl-snap .h{font-weight:600;border-top:0;background:rgba(127,127,127,.10)}
.tl-snap .lbl{opacity:.8}
.tl-chip{display:inline-block;font-size:.78rem;padding:2px 10px;border-radius:999px;margin-right:6px;
  background:rgba(127,127,127,.14)}
.tl-big{font-size:1.7rem;font-weight:700;line-height:1.1}
[class*='st-key-tl_class'] [data-testid='stButtonGroup'],[class*='st-key-tl_class'] [data-testid='stButtonGroup'] > div{
  flex-wrap:wrap !important;overflow:visible !important}
</style>"""


def _tone(v) -> str:
    return "tl-up" if (v or 0) > 0 else "tl-down" if (v or 0) < 0 else ""


def _tile(label: str, value: str, sub: str = "", tone: str = "", tip: str = "") -> str:
    return (f"<div class='tl-tile' title='{html.escape(tip, quote=True)}'><span class='k'>{html.escape(label)}</span>"
            f"<span class='v {tone}'>{value}</span><span class='s'>{html.escape(sub)}</span></div>")


def _headline(st, s: dict) -> None:
    hold = (f"{s['avg_hold_win_days'] or 0:.1f} <span style='font-size:.9rem;opacity:.65'>vs</span> "
            f"{s['avg_hold_loss_days'] or 0:.1f}" if s["avg_hold_win_days"] or s["avg_hold_loss_days"] else "—")
    tiles = [
        _tile(t("Net result"), _money(s["net"]), t("{n} closed trades", n=s["trades"]), _tone(s["net"]),
              t("Costs included in the price (eToro's spread).")),
        _tile(t("Win rate"), "—" if s["win_rate"] is None else f"{s['win_rate']:.0f}%",
              t("{w} wins, {l} losses", w=s["wins"], l=s["losses"])),
        _tile(t("Profit factor"), "—" if s["profit_factor"] is None else f"{s['profit_factor']:.2f}",
              t("Gross wins divided by gross losses.")),
        _tile(t("Average hold"), hold, t("days") + " · " + t("Winners / losers.")),
    ]
    st.html(CSS + "<div class='tl-tiles'>" + "".join(tiles) + "</div>")
    if not s["enough"]:
        st.caption(t("too few trades to call anything a pattern yet"))


def _bars_html(by: dict) -> str:
    rows = [(k, v) for k, v in by.items() if v["trades"]]
    top = max((abs(v["net"]) for _, v in rows), default=0) or 1
    out = []
    for k, v in rows:
        colour = "#15803d" if v["net"] >= 0 else "#b91c1c"
        width = max(3, round(abs(v["net"]) / top * 100))
        out.append(f"<span title='{v['trades']}'>{html.escape(t(CLASS_WORDS.get(k, k)))}</span>"
                   f"<span class='tl-track'><span class='tl-fill' style='display:block;width:{width}%;"
                   f"background:{colour}'></span></span><span class='tl-num {_tone(v['net'])}'>{_money(v['net'])}</span>")
    return "<div class='tl-bars'>" + "".join(out) + "</div>"


def _regime_rows_html(by: dict) -> str:
    out = []
    for k, v in by.items():
        if not v["trades"]:
            continue
        name = _regime({"regime": k}) if k != "unknown" else t("Not known")
        detail = (t("{n} closed trades", n=v["trades"]) + " · "
                  + (f"{v['win_rate']:.0f}%" if v["enough"] and v["win_rate"] is not None else t("too few to say")))
        dim = "" if v["enough"] else " tl-dim"
        out.append(f"<div class='r{dim}'><span>{html.escape(name)}</span><span style='opacity:.75'>"
                   f"{html.escape(detail)}</span><span class='tl-num {_tone(v['net']) if v['enough'] else ''}'>"
                   f"{_money(v['net'])}</span></div>")
    return "<div class='tl-rows'>" + "".join(out) + "</div>"


PATTERN_WORDS = {
    "hold_losers": mark("You held losing trades about {x} times as long as winning ones ({n} trades)."),
    "hold_winners": mark("You held winning trades about {x} times as long as losing ones ({n} trades)."),
    "size_after_loss": mark("After a loss, your next trade was on average {x} times the size of one after a win "
                            "({n} trades)."),
    "class_gap": mark("Your {better} trades did better on average than your {worse} trades ({n} trades)."),
}


def _patterns_html(trips: list[dict], copied: bool) -> str:
    items = []
    for p in tradelog.patterns(trips, copied):
        words = t(PATTERN_WORDS[p["kind"]], x=p.get("times"), n=p["trades"],
                  better=t(CLASS_WORDS.get(p.get("better"), "Other")).lower(),
                  worse=t(CLASS_WORDS.get(p.get("worse"), "Other")).lower())
        items.append(f"<li>{html.escape(words)}</li>")
    body = ("<ul style='margin:0;padding-left:20px;display:flex;flex-direction:column;gap:8px;font-size:.92rem'>"
            + "".join(items) + "</ul>") if items else (
        f"<div style='font-size:.9rem;opacity:.75'>{html.escape(t('No clear patterns yet. They show once there are enough trades behind them.'))}</div>")
    return (f"<div class='tl-h'>{html.escape(t('**Patterns in your own trades**').strip('*'))}</div>" + body
            + f"<div class='tl-note'>{html.escape(t('Describes your past trades. Not advice.'))}</div>")


def _review_card(st, supabase, trips: list[dict], snaps: dict, plan: str, ai: str | None, zone) -> None:
    """🧭 The weekly review (Pro and Elite): last week's trades, written by the AI from checked facts when first
    opened, then kept. Narrow it to an asset class or a platform."""
    import i18n
    import plans
    import tradelog_coach

    with st.container(key="tl_card_review"):
        if not plans.includes(plan, "pro"):
            st.html(CSS + f"<div class='tl-h'>{html.escape(t('**Weekly review**').strip('*'))}</div>"
                    f"<div style='font-size:.9rem;opacity:.8'>{html.escape(t('A short review of your week, written for you each week. Comes with Pro.'))}</div>")
            return
        start, end = tradelog_coach.week_of(datetime.now(zone).date())
        st.html(CSS + f"<div class='tl-h'>{html.escape(t('**Weekly review**').strip('*'))} · "
                + html.escape(t("{a} to {b}", a=start.strftime("%d %b"), b=end.strftime("%d %b %Y"))) + "</div>")
        own = [x for x in trips if not x.get("copied")]
        scopes = ["all"] + [f"class:{c}" for c in sorted({x.get("asset_class") for x in own if x.get("asset_class")})]
        if len({x.get("platform") for x in own}) > 1:
            scopes += [f"platform:{p}" for p in sorted({x.get("platform") for x in own})]
        scope = st.pills(t("Review"), scopes, default="all", key="tl_review_scope", label_visibility="collapsed",
                         format_func=lambda sc: t("All") if sc == "all" else (
                             t(CLASS_WORDS.get(sc[6:], "Other")) if sc.startswith("class:") else
                             PLATFORMS.get(sc[9:], sc[9:]))) or "all"
        try:
            saved = (supabase.table("trade_reviews").select("review").eq("week_start", start.isoformat())
                     .eq("scope", scope).limit(1).execute().data or [])
        except Exception:
            st.caption(t("The weekly review is being set up. Please check back soon."))
            return
        review = (saved[0] or {}).get("review") if saved else None
        fact = tradelog_coach.facts(trips, snaps, (start, end), zone, scope)
        if review is None:
            if not fact["trades"]:
                st.caption(t("No trades closed that week."))
                return
            if not st.button(t("Write my review"), key=f"tl_review_go_{scope}", type="primary",
                             icon=":material/edit_note:",
                             help=t("Written once from your own trades, then kept. Describes, never advises.")):
                return
            import ai_providers

            code = i18n.current()
            language = next((x["english"] for x in i18n.LANGUAGES if x["code"] == code), "English")
            with st.spinner(t("Writing your review…")):
                review = tradelog_coach.write(fact, ai_providers.pick("navigator", ai), language=language)
            try:
                supabase.table("trade_reviews").upsert({
                    "user_id": trips[0]["user_id"], "week_start": start.isoformat(), "scope": scope,
                    "review": review, "provider": ai_providers.pick("navigator", ai)[:20], "language": code[:10],
                }, on_conflict="user_id,week_start,scope").execute()
            except Exception:
                pass
        parts = [(t("What happened"), review.get("happened")), (t("One pattern worth noticing"), review.get("pattern")),
                 (t("One question for you"), review.get("question"))]
        st.html(CSS + "".join(f"<div style='margin:6px 0 10px'><div style='font-size:.78rem;letter-spacing:.04em;"
                              f"text-transform:uppercase;opacity:.7'>{html.escape(h)}</div>"
                              f"<div style='font-size:.95rem;line-height:1.5'>{html.escape(str(b or ''))}</div></div>"
                              for h, b in parts))
        if review.get("plain"):
            st.caption(t("A plain summary of the facts: the written review didn't pass our checks this time."))
        cited = [x for x in fact["trades"] if x["id"] in set(review.get("cited") or [])]
        if cited:
            with st.expander(t("Trades mentioned")):
                st.dataframe(pd.DataFrame([{"": x["id"], t("Asset"): x["asset"], t("Result (USD)"): x["result_usd"],
                                            t("Held (days)"): x["held_days"]} for x in cited]),
                             hide_index=True, width="stretch", column_config=_usd_cols(st, t("Result (USD)")))
        st.caption(t("Describes your past trades. Not advice."))


def _overview(st, trips: list[dict], snaps: dict, copied: bool) -> None:
    _headline(st, tradelog.stats(trips, copied))
    curve = tradelog.equity_curve(trips, copied)
    platforms = tradelog.stats_by(trips, "platform", copied)
    if len(curve) >= 2:
        with st.container(key="tl_card_curve"):
            # Not the account's value (no deposits, withdrawals or open positions): said so, 26 Nov 2026.
            st.html(CSS + f"<div class='tl-h'>{html.escape(t('**Profit and loss from closed trades**').strip('*'))}</div>")
            st.caption(t("Each trade's result added up on the day it closed. This is not your account value: money "
                         "paid in or taken out and open positions are not included, and a loss only shows once the "
                         "trade is closed."))
            st.line_chart(pd.DataFrame({t("Net result (USD)"): [v for _, v in curve]},
                                       index=pd.to_datetime([d for d, _ in curve], utc=True, format="ISO8601")),
                          height=220)
    left, right = st.columns(2)
    with left, st.container(key="tl_card_classes"):
        st.html(CSS + f"<div class='tl-h'>{html.escape(t('**By asset class**').strip('*'))}</div>"
                + _bars_html(tradelog.stats_by(trips, "asset_class", copied)))
    with right, st.container(key="tl_card_regimes"):
        tagged = [{**trip, "regime": (snaps.get((trip["id"], "entry")) or {}).get("regime") or "unknown"}
                  for trip in trips]
        st.html(CSS + f"<div class='tl-h'>{html.escape(t('**Results by regime at entry**').strip('*'))}</div>"
                + _regime_rows_html(tradelog.stats_by(tagged, "regime", copied))
                + f"<div class='tl-note'>{html.escape(t('Shows what happened together, not a cause.'))}</div>")
    with st.container(key="tl_card_patterns"):
        st.html(CSS + _patterns_html(trips, copied))
    if len(platforms) > 1:
        with st.container(key="tl_card_platforms"):
            st.html(CSS + f"<div class='tl-h'>{html.escape(t('**By platform**').strip('*'))}</div>")
            st.dataframe(pd.DataFrame([{t("Platform"): PLATFORMS.get(k, k), t("Trades"): v["trades"],
                                        t("Net result (USD)"): v["net"], t("Win rate"): v["win_rate"]}
                                       for k, v in platforms.items()]), hide_index=True, width="stretch",
                         column_config={**_usd_cols(st, t("Net result (USD)")), **_pct_cols(st, t("Win rate"))})


def _trade_list(st, trips: list[dict], snaps: dict, zone, key: str):
    """The trade table; returns the picked trade, if any."""
    if not trips:
        st.info(t("No closed trades here yet."))
        return None
    def held(trip):
        a, b = _when(trip["opened_at"]), _when(trip["closed_at"])
        return round((b - a).total_seconds() / 86400, 1)
    table = pd.DataFrame([{
        t("Closed"): _when(trip["closed_at"]).astimezone(zone).replace(tzinfo=None),
        t("Asset"): trip.get("name") or trip.get("symbol") or "—",
        t("Class"): t(CLASS_WORDS.get(trip.get("asset_class"), "Other")),
        t("Direction"): t("Buy") if trip.get("direction") == "long" else t("Sell"),
        t("Held (days)"): held(trip),
        t("Result (USD)"): trip.get("net_result_usd"),
        "%": trip.get("result_pct"),
        t("Regime at entry"): _regime(snaps.get((trip["id"], "entry"))),
        t("Copied"): "✓" if trip.get("copied") else "",
    } for trip in trips])
    res, held_col = t("Result (USD)"), t("Held (days)")
    colour = lambda v: ("color:#15803d;font-weight:600" if (v or 0) > 0 else           # noqa: E731
                        "color:#b91c1c;font-weight:600" if (v or 0) < 0 else "")
    styled = (table.style.map(colour, subset=[res, "%"])
              .format({res: "{:+,.2f}", "%": "{:+.1f}%", held_col: "{:.1f}"}, na_rep="—")
              .format(lambda d: d.strftime("%d %b %Y"), subset=[t("Closed")]))
    picked = st.dataframe(
        styled, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key=f"tl_table_{key}",
        column_config={t("Closed"): st.column_config.DatetimeColumn(t("Closed"), format="D MMM YYYY"),
                       t("Held (days)"): st.column_config.NumberColumn(t("Held (days)"), format="%.1f"),
                       **_usd_cols(st, t("Result (USD)")),
                       "%": st.column_config.NumberColumn("%", format="%+.1f%%")})
    st.caption(t("Times in your time zone ({zone}). Pick a row to see the trade.", zone=str(zone)))
    rows = list(getattr(getattr(picked, "selection", None), "rows", []) or [])
    return trips[rows[0]] if rows else None


def _closes(supabase, asset_key: str) -> list[tuple[str, float]]:
    """Daily closes for one asset from the shared price store (date, close), cached for an hour."""
    return _closes_cached(supabase, asset_key)


def _closes_uncached(_supabase, asset_key: str) -> list[tuple[str, float]]:
    try:
        rows = (_supabase.table("asset_market").select("prices").eq("asset_key", asset_key).limit(1)
                .execute().data or [])
    except Exception:
        return []
    from market_store import frame_from_records

    prices = (rows[0] or {}).get("prices") if rows else None
    if not prices:
        return []
    frame = frame_from_records(prices)
    return [(pd.Timestamp(i).strftime("%Y-%m-%d"), float(c)) for i, c in frame["close"].items()]


def _price_chart(st, supabase, trip: dict) -> None:
    """Daily closes around the trade, with the entry and exit marked. Only for assets MarketNavi follows."""
    key = trip.get("asset_key")
    if not key or supabase is None:
        return
    closes = _closes(supabase, key)
    if not closes:
        return
    import altair as alt

    o, c = _when(trip["opened_at"]), _when(trip["closed_at"])
    lo, hi = (o - timedelta(days=30)).strftime("%Y-%m-%d"), (c + timedelta(days=10)).strftime("%Y-%m-%d")
    data = pd.DataFrame([{"day": pd.Timestamp(d), "close": v} for d, v in closes if lo <= d <= hi])
    if len(data) < 3:
        return
    marks = pd.DataFrame([
        {"day": pd.Timestamp(o.date()), "price": trip.get("entry_price"), "what": t("At entry")},
        {"day": pd.Timestamp(c.date()), "price": trip.get("exit_price"), "what": t("At exit")}]).dropna()
    line = alt.Chart(data).mark_line(color="#64748b", strokeWidth=2).encode(
        x=alt.X("day:T", title=None), y=alt.Y("close:Q", title=None, scale=alt.Scale(zero=False)))
    band = alt.Chart(pd.DataFrame([{"a": pd.Timestamp(o.date()), "b": pd.Timestamp(c.date())}])).mark_rect(
        opacity=0.12, color="#007F73").encode(x="a:T", x2="b:T")
    dots = alt.Chart(marks).mark_point(filled=True, size=110).encode(
        x="day:T", y="price:Q", tooltip=["what:N", alt.Tooltip("price:Q", format=",.4g")],
        color=alt.Color("what:N", legend=None, scale=alt.Scale(range=["#007F73", "#C69420"])))
    st.markdown(t("**Price around the trade**"))
    st.altair_chart((band + line + dots).properties(height=220), width="stretch")


def _detail(st, supabase, trip: dict, snaps: dict, notes: dict, zone) -> None:
    o, c = _when(trip["opened_at"]).astimezone(zone), _when(trip["closed_at"]).astimezone(zone)
    net, pct = trip.get("net_result_usd"), trip.get("result_pct")
    held = (c - o).total_seconds() / 86400
    side = t("Buy") if trip.get("direction") == "long" else t("Sell")
    chips = (f"<span class='tl-chip'>{html.escape(side)}</span>"
             f"<span class='tl-chip'>{html.escape(t(CLASS_WORDS.get(trip.get('asset_class'), 'Other')))}</span>"
             + (f"<span class='tl-chip'>{html.escape(t('Copied'))}</span>" if trip.get("copied") else ""))
    price = lambda v: "—" if v is None else f"{v:,.4g}"                                # noqa: E731
    st.html(CSS + "<div style='display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:12px'>"
            f"<div><div class='tl-big'>{html.escape(trip.get('name') or trip.get('symbol') or '')}</div>"
            f"<div style='margin:6px 0 2px'>{chips}</div><div style='font-size:.82rem;opacity:.7'>"
            + html.escape(t("Opened {o} · closed {c} · one position until flat, average prices",
                            o=o.strftime("%d %b %Y %H:%M"), c=c.strftime("%d %b %Y %H:%M")))
            + f"</div></div><div style='text-align:right'><div class='tl-big {_tone(net)}'>{_money(net)}</div>"
            f"<div class='{_tone(net)}' style='font-size:.9rem'>{_signed(pct, 1) + "%" if pct is not None else "—"} · {held:.1f} "
            f"{html.escape(t('days'))}</div></div></div>"
            "<div class='tl-tiles' style='margin-top:12px'>"
            + _tile(t("Average entry"), price(trip.get("entry_price")))
            + _tile(t("Average exit"), price(trip.get("exit_price")))
            + _tile(t("Invested"), _money(trip.get("invested_usd")).lstrip("+"))
            + _tile(t("Leverage"), t("None") if (trip.get("leverage") or 1) <= 1 else f"x{trip['leverage']:g}")
            + "</div>")
    _price_chart(st, supabase, trip)
    entry, exit_ = snaps.get((trip["id"], "entry")), snaps.get((trip["id"], "exit"))
    st.markdown(t("**What MarketNavi read at the time**"))
    if not entry and not exit_:
        st.caption(t("Working out the readings for this trade. They appear after the next background pass."))
    else:
        def fear(r):
            f = (r or {}).get("fear") or {}
            return "—" if f.get("value") is None else f"{f['value']:.1f}"
        def sent(r, k):
            v = ((r or {}).get(k) or {}).get("value")
            return t("Not recorded then") if v is None else f"{v:.0f}"
        rows = [(t("Regime"), _regime(entry), _regime(exit_)),
                ("📈 Trend", _signed((entry or {}).get("trend")), _signed((exit_ or {}).get("trend"))),
                ("🎯 Stretch", _signed((entry or {}).get("stretch")), _signed((exit_ or {}).get("stretch"))),
                ("🔊 Flow", _signed((entry or {}).get("flow")), _signed((exit_ or {}).get("flow"))),
                (t("Fear index ({name})", name=((entry or exit_ or {}).get("fear") or {}).get("name") or "—"),
                 fear(entry), fear(exit_)),
                (t("Asset sentiment"), sent(entry, "asset_sentiment"), sent(exit_, "asset_sentiment")),
                (t("Market sentiment"), sent(entry, "market_sentiment"), sent(exit_, "market_sentiment"))]
        grid = (f"<div class='h'></div><div class='h'>{html.escape(t('At entry'))}</div>"
                f"<div class='h'>{html.escape(t('At exit'))}</div>")
        for name, a, b in rows:
            grid += (f"<div class='lbl'>{html.escape(name)}</div><div>{html.escape(str(a))}</div>"
                     f"<div>{html.escape(str(b))}</div>")
        st.html(CSS + f"<div class='tl-snap'>{grid}</div>")
        source = (entry or {}).get("_source") or ""
        st.caption(t("Observed: what MarketNavi saved that day. Reconstructed: rebuilt from data known then. "
                     "This trade's entry: {s}.", s=t(SOURCE_WORDS[source]) if source in SOURCE_WORDS else "—"))
    note = notes.get(trip["id"]) or {}
    with st.form(f"tl_note_{trip['id']}"):
        text = st.text_area(t("Your note"), value=note.get("note") or "", max_chars=2000,
                            placeholder=t("Why you took it, how it felt"), key=f"tl_note_text_{trip['id']}")
        tags = st.text_input(t("Tags (comma-separated)"), value=", ".join(note.get("tags") or []),
                             key=f"tl_note_tags_{trip['id']}")
        if st.form_submit_button(t("Save note")):
            clean = [x.strip()[:30] for x in tags.split(",") if x.strip()][:12]
            supabase.table("trade_notes").upsert({"round_trip_id": trip["id"], "user_id": trip["user_id"],
                                                  "note": text, "tags": clean,
                                                  "updated_at": datetime.now(timezone.utc).isoformat()},
                                                 on_conflict="round_trip_id").execute()
            st.toast(t("Note saved."))


# ---- the page ------------------------------------------------------------------------------------------------

def render(st, supabase, plan: str, ai: str | None = None) -> None:
    """The main-page Trade Log, as a fragment: a filter, tab or row picked redraws only this section."""
    _render_fragment(st, supabase, plan, ai)


def _render(st, supabase, plan: str, ai: str | None = None) -> None:
    if CONNECTIONS.get(plan, 0) == 0:
        st.info(t("The Trade Log comes with Plus: connect eToro read-only and see your own trades against the "
                  "market conditions at the time."))
        return
    data = load(supabase)
    if not data["ready"]:
        st.info(t("The Trade Log is being set up. Please check back soon."))
        return
    conns = data["connections"]
    if not conns:
        return
    zone = _zone(st)
    snaps = {}
    for s in data["snapshots"]:
        snaps[(s["round_trip_id"], s["moment"])] = {**(s.get("readings") or {}), "_source": s.get("source")}
    notes = {n["round_trip_id"]: n for n in data["notes"]}
    trips = data["trips"]
    days = HISTORY_DAYS.get(plan)
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        trips = [x for x in trips if (_when(x["closed_at"]) or since) >= since]
        st.caption(t("Plus shows the last {n} days. Pro keeps your full history.", n=days))

    # Synced time and Refresh together on the right, on one line, with the tabs straight under them.
    with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small",
                      key="tl_topbar"):
        synced = [c["last_sync_at"] for c in conns if c.get("last_sync_at")]
        if synced:
            last = max(_when(x) for x in synced).astimezone(zone)
            st.caption(t("Synced {when}", when=last.strftime("%d %b %H:%M")))
        elif any(c.get("status") == "new" for c in conns):
            st.caption(t("Importing your history: your trades appear within about 5 minutes."))
        if st.button(t("Refresh"), key="tl_refresh", icon=":material/refresh:",
                     help=t("Fetch new closed trades on the next background pass (about 5 minutes).")):
            asked = [supabase.rpc("tradelog_request_refresh", {"p_id": c["id"]}).execute().data for c in conns]
            st.toast(t("Refresh requested.") if any(asked) else t("Synced recently. Try again in a few minutes."))
    st.html("<style>.st-key-tl_topbar{margin-bottom:-14px}.st-key-tl_topbar [data-testid='stCaptionContainer']"
            "{margin:0}</style>")

    by_id = tab_names(conns)
    names = [by_id[c["id"]] for c in conns]
    tabs = st.tabs([t("Overview")] + names)
    with tabs[0]:
        pick, whose = _filters(st, "all")
        shown = _whose([x for x in trips if pick is None or x.get("asset_class") == pick], whose)
        _overview(st, shown, snaps, True)          # already narrowed to the chosen trades
        _review_card(st, supabase, trips, snaps, plan, ai, zone)
    for tab, conn in zip(tabs[1:], conns):
        with tab:
            pick, whose = _filters(st, conn["id"])
            mine = _whose([x for x in trips if x["connection_id"] == conn["id"]
                           and (pick is None or x.get("asset_class") == pick)], whose)
            _headline(st, tradelog.stats(mine, True))
            with st.container(key=f"tl_card_list_{conn['id']}"):
                chosen = _trade_list(st, mine, snaps, zone, conn["id"])
            if chosen:
                with st.container(key=f"tl_card_detail_{conn['id']}"):
                    _detail(st, supabase, chosen, snaps, notes, zone)
    st.caption(t(DISCLAIMER))


import streamlit as _streamlit                                           # noqa: E402  (the fragment wrapper)

_render_fragment = _streamlit.fragment(_render)
_closes_cached = _streamlit.cache_data(ttl=3600, show_spinner=False)(_closes_uncached)


def has_connections(supabase) -> bool:
    """Whether the main-page Trade Log should show: only once a platform is connected (set up in the sidebar)."""
    try:
        return bool(supabase.table("trade_connections").select("id").limit(1).execute().data)
    except Exception:
        return False


def render_setup(st, supabase, plan: str) -> None:
    """The sidebar's Trade Log section: connect a platform with a read-only key, manage or delete connections."""
    if CONNECTIONS.get(plan, 0) == 0:
        st.caption(t("The Trade Log comes with Plus: connect eToro read-only and see your own trades against the "
                     "market conditions at the time."))
        return
    data = load(supabase)
    if not data["ready"]:
        st.caption(t("The Trade Log is being set up. Please check back soon."))
        return
    conns = data["connections"]
    _manage(st, supabase, conns)
    _connect_form(st, supabase, plan, len(conns))
    st.caption(t(DISCLAIMER))
