import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { maxPain, earningsHistory } from "../../lib/assets.js";
import { usd, compact, pct, tone, dayMonthYear, stamp } from "../../lib/format.js";

// Crypto: the futures market (funding, open interest, liquidations and where they cluster) and Max pain. Equities:
// the earnings dates.
export default function Derivatives({ row, crypto, who }) {
  return crypto ? <Futures row={row} /> : <Earnings row={row} who={who} />;
}

function Futures({ row }) {
  const [pain, setPain] = useState(undefined);
  useEffect(() => { maxPain(row.asset_key).then(setPain); }, [row.asset_key]);
  const liq = row.liq_levels || {};
  if (liq.status !== "ok") return <div className="empty">{T("No futures data for this coin: it isn't traded on the futures markets MarketNavi follows.")}</div>;
  const s = liq.series || {};
  const lastOf = (k) => (s[k] || []).filter((v) => v != null).slice(-1)[0];
  const dayAgo = (k) => { const v = s[k] || []; return v.length >= 25 ? v[v.length - 25] : null; };
  const oi = lastOf("oi"), oi0 = dayAgo("oi"), fund = lastOf("funding"), ls = lastOf("ls");
  const l24 = (s.liq_long || []).slice(-24).reduce((a, b) => a + (b || 0), 0), s24 = (s.liq_short || []).slice(-24).reduce((a, b) => a + (b || 0), 0);
  const p = liq.price;
  const levels = [...(liq.shorts || []).map((x) => ({ ...x, side: "shorts" })), ...(liq.longs || []).map((x) => ({ ...x, side: "longs" }))]
    .filter((x) => x.price && x.usd).sort((a, b) => b.price - a.price);
  const most = Math.max(1, ...levels.map((x) => x.usd));
  const cut = levels.findIndex((x) => x.price <= p);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="tiles closed" aria-label={T("Futures market")}>
        <div className="tile" title={T("The value of all open futures positions on Binance, Bybit and OKX. Rising means new money is betting.")}>
          <div className="l">{T("Open interest")}</div><div className="v">{compact(oi)}</div>
          <div className="s">{oi && oi0 ? <span className={tone(oi - oi0)}>{pct((oi / oi0 - 1) * 100, 1)} {T("in 24 hours")}</span> : ""}</div></div>
        <div className="tile" title={T("What one side pays the other to hold its position, each funding period. Positive: longs pay shorts, so traders lean long. Negative: shorts pay longs. Large either way is a sign of a crowded side.")}>
          <div className="l">{T("Funding rate")}</div><div className="v">{fund == null ? "—" : (fund > 0 ? "+" : "") + fund.toFixed(4) + "%"}</div>
          <div className="s">{fund == null ? "" : fund >= 0.03 ? T("high, longs crowded") : fund < 0 ? T("negative, shorts paying") : T("normal")}</div></div>
        <div className="tile" title={T("Positions actually force-closed in the last 24 hours, longs and shorts.")}>
          <div className="l">{T("Liquidated, 24h")}</div><div className="v">{compact(l24 + s24)}</div>
          <div className="s">{T("longs {a} · shorts {b}", { a: compact(l24), b: compact(s24) })}</div></div>
        <div className="tile" title={T("Accounts holding longs for each account holding shorts. Above 1 means more traders are long.")}>
          <div className="l">{T("Long/short ratio")}</div><div className="v">{ls == null ? "—" : ls.toFixed(2)}</div>
          <div className="s">{ls == null ? "" : ls > 1 ? T("more traders long") : T("more traders short")}</div></div>
      </section>

      <section className="card">
        <h2>{T("Where liquidations cluster")}</h2>
        <p className="sub">{T("Estimated prices where leveraged positions would be forced to close. Shorts above the price, longs below. Price now {p}.", { p: usd(p) })}</p>
        <div className="ladder">
          {levels.map((x, i) => {
            const before = i === cut;
            return (
              <React.Fragment key={x.side + x.price}>
                {before && <div className="lnow"><span>{T("Price now")} {usd(p)}</span></div>}
                <div className="lrow">
                  <span className="lp">{usd(x.price)}</span>
                  <span className="lbar"><span className={x.side === "shorts" ? "good" : "bad"} style={{ width: `${(x.usd / most) * 100}%` }} /></span>
                  <span className="lv">{compact(x.usd)}</span>
                  <span className="m lg">{p ? pct((x.price / p - 1) * 100, 1) : ""}</span>
                </div>
              </React.Fragment>
            );
          })}
          {cut === -1 && <div className="lnow"><span>{T("Price now")} {usd(p)}</span></div>}
        </div>
        <p className="sub">{T("Updated {when}.", { when: stamp(row.liq_updated_at) })}</p>
      </section>

      <section className="card">
        <h2>{T("Max pain")}</h2>
        {pain === undefined ? <p className="sub">{T("Loading…")}</p> : pain ? (
          <>
            <p className="sub">{T("The price at which the most options would expire worthless at the next expiry, from Deribit's open options.")}</p>
            <div className="facts">
              <span>{T("Max pain")} <b>{usd(pain.max_pain)}</b></span>
              <span>{T("Expiry")} <b>{dayMonthYear(pain.expiry)}</b></span>
              <span>{T("Price then")} <b>{usd(pain.spot)}</b> <span className="m">{stamp(pain.recorded_at)}</span></span>
            </div>
          </>
        ) : <p className="sub">{T("There is no options market MarketNavi records for this coin, so Max pain isn't available. It shows for Bitcoin and Ethereum.")}</p>}
      </section>
    </div>
  );
}

function Earnings({ row, who }) {
  const [past, setPast] = useState([]);
  useEffect(() => { earningsHistory(who.id).then(setPast); }, [who.id]);
  const days = row.next_earnings ? Math.round((new Date(row.next_earnings + "T12:00:00Z") - Date.now()) / 864e5) : null;
  return (
    <section className="card">
      <h2>{T("Earnings")}</h2>
      <div className="facts" style={{ marginTop: 10 }}>
        <span>{T("Next report")} <b>{row.next_earnings ? dayMonthYear(row.next_earnings) : T("none scheduled")}</b>{days != null && days >= 0 ? <span className="m"> · {T("in {n} days", { n: days })}</span> : null}</span>
      </div>
      {past.length > 0 && (<>
        <h3>{T("Past reports")}</h3>
        <div className="facts">{past.map((p) => <span key={p.report_date}>{dayMonthYear(p.report_date)}</span>)}</div>
      </>)}
      <p className="sub" style={{ marginTop: 14 }}>{T("Prices often move sharply around an earnings report.")}</p>
    </section>
  );
}
