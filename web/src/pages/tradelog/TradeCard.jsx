import React, { useEffect, useState } from "react";
import Icon from "../../components/Icon.jsx";
import { T } from "../../lib/i18n.js";
import { closes, note as loadNote, saveNote } from "../../lib/api.js";
import { money, pct, price, tone, when, dayMonthYear } from "../../lib/format.js";
import { LABEL } from "./Edge.jsx";

const REGIME = () => ({ trending_up: T("Trending up"), trending_down: T("Trending down"), trending_mixed: T("Trending, mixed"),
  ranging: T("Ranging"), transitional: T("Transitional"), trending: T("Trending") });
const SOURCE = () => ({ observed: T("observed"), reconstructed: T("reconstructed"), unavailable: T("not available") });
const signed = (v) => (v == null ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(Math.round(v)));

// Daily closes from 30 days before the trade to 10 days after, the holding period shaded, entry and exit marked.
function PriceAround({ trip }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { let live = true; if (trip.asset_key) closes(trip.asset_key).then((c) => live && setRows(c)); return () => { live = false; }; }, [trip.asset_key]);
  if (!trip.asset_key || !rows) return null;
  const o = new Date(trip.opened_at), c = new Date(trip.closed_at);
  const lo = new Date(o.getTime() - 30 * 864e5).toISOString().slice(0, 10), hi = new Date(c.getTime() + 10 * 864e5).toISOString().slice(0, 10);
  const pts = rows.filter(([d]) => d >= lo && d <= hi);
  if (pts.length < 3) return null;
  const vals = pts.map((p) => p[1]).concat([trip.entry_price, trip.exit_price].filter((v) => v != null));
  const min = Math.min(...vals), max = Math.max(...vals), pad = (max - min) * 0.08 || 1;
  const W = 1000, H = 200;
  const X = (d) => (pts.findIndex((p) => p[0] >= d) < 0 ? W : (pts.findIndex((p) => p[0] >= d) / (pts.length - 1)) * W);
  const Y = (v) => H - ((v - (min - pad)) / (max - min + 2 * pad)) * H;
  const od = o.toISOString().slice(0, 10), cd = c.toISOString().slice(0, 10);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${((i / (pts.length - 1)) * W).toFixed(1)} ${Y(p[1]).toFixed(1)}`).join(" ");
  return (
    <div style={{ marginTop: 14 }}>
      <h3>{T("Price around the trade")}</h3>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={T("Price around the trade")} style={{ width: "100%", height: 200, display: "block" }}>
        <rect x={X(od)} y="0" width={Math.max(2, X(cd) - X(od))} height={H} fill="var(--good)" fillOpacity="0.1" />
        <path d={line} fill="none" stroke="var(--grey)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        {trip.entry_price != null && <circle cx={X(od)} cy={Y(trip.entry_price)} r="6" fill="var(--good)" />}
        {trip.exit_price != null && <circle cx={X(cd)} cy={Y(trip.exit_price)} r="6" fill="var(--gold)" />}
      </svg>
      <div className="axis"><span>{dayMonthYear(pts[0][0])}</span><span><i className="dot" style={{ background: "var(--good)" }} /> {T("At entry")} · <i className="dot" style={{ background: "var(--gold)" }} /> {T("At exit")}</span><span>{dayMonthYear(pts[pts.length - 1][0])}</span></div>
    </div>
  );
}

function Readings({ entry, exit }) {
  if (!entry && !exit) return <p className="sub">{T("Working out the readings for this trade. They appear after the next background pass.")}</p>;
  const regime = REGIME();
  const reg = (r) => (r && r.regime ? regime[r.regime] || r.regime : "—");
  const fear = (r) => (r && r.fear && r.fear.value != null ? Number(r.fear.value).toFixed(1) : "—");
  const sent = (r, k) => (r && r[k] && r[k].value != null ? Math.round(r[k].value) : T("Not recorded then"));
  const rows = [[T("Regime"), reg(entry), reg(exit)], ["Trend", signed(entry && entry.trend), signed(exit && exit.trend)],
    ["Stretch", signed(entry && entry.stretch), signed(exit && exit.stretch)], ["Flow", signed(entry && entry.flow), signed(exit && exit.flow)],
    [T("Fear index ({name})", { name: ((entry || exit || {}).fear || {}).name || "—" }), fear(entry), fear(exit)],
    [T("Asset sentiment"), sent(entry, "asset_sentiment"), sent(exit, "asset_sentiment")],
    [T("Market sentiment"), sent(entry, "market_sentiment"), sent(exit, "market_sentiment")]];
  const src = SOURCE()[(entry || {})._source] || "—";
  return (
    <>
      <div className="snap">
        <span /><span className="h">{T("At entry")}</span><span className="h">{T("At exit")}</span>
        {rows.map(([n, a, b]) => <React.Fragment key={n}><span className="lbl">{n}</span><span>{a}</span><span>{b}</span></React.Fragment>)}
      </div>
      <p className="sub">{T("Observed: what MarketNavi saved that day. Reconstructed: rebuilt from data known then. This trade's entry: {s}.", { s: src })}</p>
    </>
  );
}

function Note({ trip }) {
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [saved, setSaved] = useState("");
  useEffect(() => { let live = true; loadNote(trip.id).then((n) => { if (live) { setText(n.note || ""); setTags((n.tags || []).join(", ")); } }).catch(() => {}); return () => { live = false; }; }, [trip.id]);
  const save = async (e) => {
    e.preventDefault();
    const clean = tags.split(",").map((x) => x.trim().slice(0, 30)).filter(Boolean);
    try { await saveNote(trip, text, clean); setSaved(T("Note saved.")); } catch (err) { setSaved(T("Could not save the note. Please try again.")); }
  };
  return (
    <form className="form" onSubmit={save} style={{ marginTop: 14 }}>
      <label>{T("Your note")}<textarea rows={3} maxLength={2000} value={text} onChange={(e) => { setText(e.target.value); setSaved(""); }} /></label>
      <label>{T("Tags (comma-separated)")}<input type="text" value={tags} onChange={(e) => { setTags(e.target.value); setSaved(""); }} /></label>
      <div className="bar"><button type="submit" className="primary">{T("Save note")}</button>{saved && <span className="m">{saved}</span>}</div>
    </form>
  );
}

const END = () => ({ stop_loss: T("Stop loss"), take_profit: T("Take profit"), trailing_stop: T("Trailing stop"), by_hand: T("By hand") });

export default function TradeCard({ trip, onClose }) {
  const held = (new Date(trip.closed_at) - new Date(trip.opened_at)) / 864e5;
  const L = LABEL();
  return (
    <section className="card tradecard">
      <div className="bar" style={{ alignItems: "flex-start" }}>
        <div>
          <div className="big">{trip.name || trip.symbol}</div>
          <div className="chips">
            <span className="chip">{trip.direction === "short" ? T("Sell") : T("Buy")}</span>
            <span className="chip">{L[trip.asset_class] || trip.asset_class}</span>
            {trip.copied && <span className="chip">{T("Copied")}</span>}
            {trip.exit_kind && <span className="chip">{END()[trip.exit_kind]}</span>}
          </div>
          <div className="m" style={{ fontSize: 13 }}>{T("Opened {o} · closed {c} · one position until flat, average prices", { o: when(trip.opened_at), c: when(trip.closed_at) })}</div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div className={"big " + tone(trip.net_result_usd)}>{money(trip.net_result_usd)}</div>
          <div className={tone(trip.net_result_usd)}>{pct(trip.result_pct, 1)} · {held.toFixed(1)} {T("days")}</div>
        </div>
        <button type="button" className="ghost" onClick={onClose} aria-label={T("Close")}><Icon n="x" /></button>
      </div>
      <div className="mini">
        <div><div className="ml">{T("Average entry")}</div><div className="mv">{price(trip.entry_price)}</div></div>
        <div><div className="ml">{T("Average exit")}</div><div className="mv">{price(trip.exit_price)}</div></div>
        <div><div className="ml">{T("Invested")}</div><div className="mv">{money(trip.invested_usd, false)}</div></div>
        <div><div className="ml">{T("Leverage")}</div><div className="mv">{(trip.leverage || 1) <= 1 ? T("None") : `x${trip.leverage}`}</div></div>
        {trip.stop_loss != null && <div><div className="ml">{T("Stop loss")}</div><div className="mv">{price(trip.stop_loss)}</div><div className="ms">{trip.risk_r != null ? `${trip.risk_r >= 0 ? "+" : "−"}${Math.abs(trip.risk_r).toFixed(1)}R` : ""}</div></div>}
        {trip.kept_pct != null && <div><div className="ml">{T("Kept of best move")}</div><div className="mv">{Math.round(trip.kept_pct)}%</div></div>}
      </div>
      <PriceAround trip={trip} />
      <h3>{T("What MarketNavi read at the time")}</h3>
      <Readings entry={trip.entry} exit={trip.exit} />
      <Note trip={trip} />
    </section>
  );
}
