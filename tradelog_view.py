"""📒 Trade Log page (spec v0.5, phase 1): connect eToro with a read-only key, then an Overview tab and one tab per
connection, the trade list, and each trade's detail with what MarketNavi read at entry and exit.

Reads with the member's own session (row-level security: their rows only). Keys are typed here and passed straight
to the database function that puts them in Vault; this page never shows, stores or logs them.
Plans: Free has no Trade Log; Plus one connection and the last 90 days; Pro every platform, full history; Elite
several accounts per platform.
"""

from __future__ import annotations

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
        label = st.text_input(t("Name (optional)"), max_chars=60, key="tl_label")
        sure = st.checkbox(t("I created this key with Read permission only"), key="tl_sure")
        if st.form_submit_button(t("Connect"), type="primary"):
            if not public.strip() or not user.strip() or not sure:
                st.warning(t("Paste both keys and tick the box first."))
                return
            try:
                supabase.rpc("tradelog_save_connection", {
                    "p_platform": "etoro", "p_label": label.strip(),
                    "p_keys": {"api_key": public.strip(), "user_key": user.strip()}}).execute()
            except Exception:
                st.error(t("Could not save the connection. Please try again."))
                return
            st.success(t("Connected. Your closed trades will appear within about 5 minutes."))


def _manage(st, supabase, conns: list[dict]) -> None:
    if not conns:
        return
    st.markdown(t("**Manage connections**"))
    for c in conns:
        name = c.get("label") or PLATFORMS.get(c["platform"], c["platform"])
        st.markdown(f"**{name}** · {t(STATUS_WORDS.get(c.get('status') or 'new', 'Importing'))}"
                    + (f"  \n:orange[{t(c['last_error'])}]" if c.get("last_error") else ""))
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

def _filters(st, key: str) -> tuple[str | None, bool]:
    cols = st.columns([4, 2])
    classes = ["all", "crypto", "stocks", "etfs", "commodities", "currencies", "indices"]
    pick = cols[0].segmented_control(
        t("Asset class"), classes, default="all", key=f"tl_class_{key}",
        format_func=lambda c: t("All") if c == "all" else t(CLASS_WORDS[c]), label_visibility="collapsed")
    copied = cols[1].checkbox(t("Include copied trades"), key=f"tl_copied_{key}",
                              help=t("Trades copied from other eToro traders are left out unless you include them."))
    return (None if pick in (None, "all") else pick), copied


def _headline(st, s: dict) -> None:
    c = st.columns(4)
    c[0].metric(t("Net result"), _money(s["net"]), help=t("Costs included in the price (eToro's spread)."))
    c[1].metric(t("Win rate"), "—" if s["win_rate"] is None else f"{s['win_rate']:.0f}%",
                help=t("{w} wins, {l} losses", w=s["wins"], l=s["losses"]))
    c[2].metric(t("Profit factor"), "—" if s["profit_factor"] is None else f"{s['profit_factor']:.2f}",
                help=t("Gross wins divided by gross losses."))
    hold = (f"{s['avg_hold_win_days'] or 0:.1f} / {s['avg_hold_loss_days'] or 0:.1f} {t('days')}"
            if s["avg_hold_win_days"] or s["avg_hold_loss_days"] else "—")
    c[3].metric(t("Average hold"), hold, help=t("Winners / losers."))
    st.caption(t("{n} closed trades", n=s["trades"])
               + ("" if s["enough"] else " · " + t("too few trades to call anything a pattern yet")))


def _overview(st, trips: list[dict], snaps: dict, copied: bool) -> None:
    _headline(st, tradelog.stats(trips, copied))
    curve = tradelog.equity_curve(trips, copied)
    if len(curve) >= 2:
        st.markdown(t("**Equity curve**"))
        st.line_chart(pd.DataFrame({t("Net result (USD)"): [v for _, v in curve]},
                                   index=pd.to_datetime([d for d, _ in curve], utc=True, format="ISO8601")))
    left, right = st.columns(2)
    with left:
        st.markdown(t("**By asset class**"))
        by = tradelog.stats_by(trips, "asset_class", copied)
        st.dataframe(pd.DataFrame([{t("Asset class"): t(CLASS_WORDS.get(k, k)), t("Trades"): v["trades"],
                                    t("Net result"): _money(v["net"]),
                                    t("Win rate"): "—" if v["win_rate"] is None else f"{v['win_rate']:.0f}%"}
                                   for k, v in by.items() if v["trades"]]), hide_index=True, width="stretch")
    with right:
        st.markdown(t("**Results by regime at entry**"))
        tagged = [{**trip, "regime": (snaps.get((trip["id"], "entry")) or {}).get("regime") or "unknown"}
                  for trip in trips]
        by = tradelog.stats_by(tagged, "regime", copied)
        st.dataframe(pd.DataFrame([{t("Regime"): _regime({"regime": k}) if k != "unknown" else t("Not known"),
                                    t("Trades"): v["trades"], t("Net result"): _money(v["net"]),
                                    t("Note"): "" if v["enough"] else t("too few to say")}
                                   for k, v in by.items() if v["trades"]]), hide_index=True, width="stretch")
        st.caption(t("Shows what happened together, not a cause."))
    platforms = tradelog.stats_by(trips, "platform", copied)
    if len(platforms) > 1:
        st.markdown(t("**By platform**"))
        st.dataframe(pd.DataFrame([{t("Platform"): PLATFORMS.get(k, k), t("Trades"): v["trades"],
                                    t("Net result"): _money(v["net"]),
                                    t("Win rate"): "—" if v["win_rate"] is None else f"{v['win_rate']:.0f}%"}
                                   for k, v in platforms.items()]), hide_index=True, width="stretch")


def _trade_list(st, trips: list[dict], snaps: dict, zone, key: str):
    """The trade table; returns the picked trade, if any."""
    if not trips:
        st.info(t("No closed trades here yet."))
        return None
    def held(trip):
        a, b = _when(trip["opened_at"]), _when(trip["closed_at"])
        days = (b - a).total_seconds() / 86400
        return f"{days:.1f} {t('days')}" if days < 10 else f"{days:.0f} {t('days')}"
    table = pd.DataFrame([{
        t("Closed"): _when(trip["closed_at"]).astimezone(zone).strftime("%d %b %Y"),
        t("Asset"): trip.get("name") or trip.get("symbol") or "—",
        t("Class"): t(CLASS_WORDS.get(trip.get("asset_class"), "Other")),
        t("Direction"): t("Buy") if trip.get("direction") == "long" else t("Sell"),
        t("Held"): held(trip),
        t("Result"): _money(trip.get("net_result_usd")),
        "%": _signed(trip.get("result_pct"), 1),
        t("Regime at entry"): _regime(snaps.get((trip["id"], "entry"))),
        t("Copied"): "✓" if trip.get("copied") else "",
    } for trip in trips])
    picked = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                          key=f"tl_table_{key}")
    st.caption(t("Times in your time zone ({zone}). Pick a row to see the trade.", zone=str(zone)))
    rows = list(getattr(getattr(picked, "selection", None), "rows", []) or [])
    return trips[rows[0]] if rows else None


def _detail(st, supabase, trip: dict, snaps: dict, notes: dict, zone) -> None:
    st.markdown(f"#### {trip.get('name') or trip.get('symbol')} · "
                f"{t('Buy') if trip.get('direction') == 'long' else t('Sell')} · {_money(trip.get('net_result_usd'))}")
    o, c = _when(trip["opened_at"]).astimezone(zone), _when(trip["closed_at"]).astimezone(zone)
    st.caption(t("Opened {o} · closed {c} · one position until flat, average prices",
                 o=o.strftime("%d %b %Y %H:%M"), c=c.strftime("%d %b %Y %H:%M")))
    m = st.columns(4)
    m[0].metric(t("Average entry"), "—" if trip.get("entry_price") is None else f"{trip['entry_price']:,.4g}")
    m[1].metric(t("Average exit"), "—" if trip.get("exit_price") is None else f"{trip['exit_price']:,.4g}")
    m[2].metric(t("Invested"), _money(trip.get("invested_usd")).lstrip("+"))
    m[3].metric(t("Leverage"), t("None") if (trip.get("leverage") or 1) <= 1 else f"x{trip['leverage']:g}")
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
        st.dataframe(pd.DataFrame(rows, columns=["", t("At entry"), t("At exit")]), hide_index=True,
                     width="stretch")
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

def render(st, supabase, plan: str) -> None:
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

    top = st.columns([5, 1])
    synced = [c["last_sync_at"] for c in conns if c.get("last_sync_at")]
    if synced:
        last = max(_when(x) for x in synced).astimezone(zone)
        top[0].caption(t("Synced {when}", when=last.strftime("%d %b %H:%M")))
    elif any(c.get("status") == "new" for c in conns):
        top[0].caption(t("Importing your history: your trades appear within about 5 minutes."))
    if top[1].button(t("Refresh"), key="tl_refresh", icon=":material/refresh:",
                     help=t("Fetch new closed trades on the next background pass (about 5 minutes).")):
        asked = [supabase.rpc("tradelog_request_refresh", {"p_id": c["id"]}).execute().data for c in conns]
        st.toast(t("Refresh requested.") if any(asked) else t("Synced recently. Try again in a few minutes."))

    names = [c.get("label") or PLATFORMS.get(c["platform"], c["platform"]) for c in conns]
    tabs = st.tabs([t("Overview")] + names)
    with tabs[0]:
        pick, copied = _filters(st, "all")
        shown = [x for x in trips if pick is None or x.get("asset_class") == pick]
        _overview(st, shown, snaps, copied)
    for tab, conn in zip(tabs[1:], conns):
        with tab:
            pick, copied = _filters(st, conn["id"])
            mine = [x for x in trips if x["connection_id"] == conn["id"]
                    and (pick is None or x.get("asset_class") == pick)]
            _headline(st, tradelog.stats(mine, copied))
            chosen = _trade_list(st, mine, snaps, zone, conn["id"])
            if chosen:
                _detail(st, supabase, chosen, snaps, notes, zone)
    st.caption(t(DISCLAIMER))


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
