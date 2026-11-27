import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { calendar } from "../../lib/assets.js";
import { weekday, dayMonthYear } from "../../lib/format.js";
import { TIDE, TIDE_PLAIN, SEA, SEA_PLAIN, WIND, CURRENT, EFFECT, EVENT } from "./words.js";
import { CLASSIC } from "../../lib/supabase.js";

const KEYS = ["short_rates", "long_rates", "curve", "dollar", "inflation", "gold", "fear", "copper_gold", "oil", "credit", "equity_rotation", "crypto_rotation"];

// The market around the asset: the Tide (money moving into or out of risk), the sea state, what is pushing it, and
// the scheduled events ahead.
export default function Conditions({ sea, crypto }) {
  const [events, setEvents] = useState([]);
  useEffect(() => { calendar().then(setEvents); }, []);
  const now = Date.now();
  const ahead = events.filter((e) => new Date(e.at).getTime() > now - 864e5).slice(0, 6);
  if (!sea) return <div className="empty">{T("Loading…")}</div>;
  const wind = sea[crypto ? "wind_crypto" : "wind_equity"];
  const currents = KEYS.filter((k) => sea[k + "_contrib"] != null).sort((a, b) => Math.abs(sea[b + "_contrib"]) - Math.abs(sea[a + "_contrib"]));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="card">
        <h2>{TIDE()[sea.tide] || T("The Tide")} <span className="m" style={{ fontWeight: 500 }}>· {TIDE_PLAIN()[sea.tide] || ""}</span></h2>
        <p className="sub">{T("Held {n} trading days, since {d}. The sea is {state} ({plain}).", { n: sea.tide_held, d: dayMonthYear(sea.tide_since), state: SEA()[sea.sea] || sea.sea, plain: SEA_PLAIN()[sea.sea] || "" })}</p>
        <div className="facts">
          <span>{crypto ? T("For crypto") : T("For equities")} <b className={wind === "headwind" ? "bad" : wind === "tailwind" ? "good" : ""}>{WIND()[wind] || "—"}</b></span>
        </div>
        <h3>{T("What is pushing it")}</h3>
        <div className="parts">
          {currents.map((k) => {
            const v = Math.round(sea[k + "_contrib"] * 100);
            return (
              <div key={k} className="part">
                <span>{CURRENT()[k]} <span className="m">· {EFFECT()[sea[k + "_effect"]] || ""}</span></span>
                <span className="ptrack"><span className="pzero" /><span className={"pfill " + (v >= 0 ? "good" : "bad")} style={{ left: v >= 0 ? "50%" : `${50 + v / 2}%`, width: `${Math.abs(v) / 2}%` }} /></span>
                <b className={v >= 0 ? "good" : "bad"}>{v > 0 ? "+" : v < 0 ? "−" : ""}{Math.abs(v)}</b>
              </div>
            );
          })}
        </div>
        <p className="sub">{T("Green helps risk assets, red holds them back.")} <a href={CLASSIC} className="linkish">{T("Open Tides in the classic app")} ›</a></p>
      </section>
      <section className="card">
        <h2>{T("Events ahead")}</h2>
        <p className="sub">{T("Scheduled US releases that often move markets.")}</p>
        <ol className="events">
          {ahead.map((e) => {
            const days = Math.round((new Date(e.at).getTime() - now) / 864e5);
            return (
              <li key={e.kind + e.at}>
                <span className={"tier t" + e.tier} aria-hidden="true" />
                <b>{EVENT()[e.kind] || e.kind}</b>
                <span className="m">{e.reference}</span>
                <span className="when">{weekday(e.at)} · {days <= 0 ? T("today") : days === 1 ? T("tomorrow") : T("in {n} days", { n: days })}</span>
              </li>
            );
          })}
          {!ahead.length && <li className="m">{T("No scheduled events in the calendar yet.")}</li>}
        </ol>
      </section>
    </div>
  );
}
