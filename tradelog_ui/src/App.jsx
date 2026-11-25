import React, { useEffect, useMemo, useState } from "react";
import { T, settings, followColours, followHeight, signedOut } from "./env.js";
import { insights } from "./api.js";
import { money, pct, tone, monthYear, stamp } from "./format.js";
import Performance from "./tabs/Performance.jsx";
import Edge from "./tabs/Edge.jsx";
import Risk from "./tabs/Risk.jsx";
import Behaviour from "./tabs/Behaviour.jsx";
import OpenNow from "./tabs/OpenNow.jsx";
import Trades from "./tabs/Trades.jsx";

const TABS = [["perf", () => T("Performance")], ["edge", () => T("Edge")], ["risk", () => T("Risk & exits")],
  ["behav", () => T("Behaviour")], ["open", () => T("Open now")], ["trades", () => T("Trades")]];
const PERIODS = { "1y": () => T("1Y"), "3y": () => T("3Y"), "5y": () => T("5Y"), all: () => T("All") };

function remembered(key, fallback, allowed) {
  try { const v = window.localStorage.getItem("tl2_" + key); return allowed.includes(v) ? v : fallback; } catch (e) { return fallback; }
}
function remember(key, value) { try { window.localStorage.setItem("tl2_" + key, value); } catch (e) { /* private window */ } }

export default function App() {
  const periods = settings.periods;
  const [tab, setTab] = useState(() => remembered("tab", "perf", TABS.map((x) => x[0])));
  const [whose, setWhose] = useState(() => remembered("whose", "own", ["own", "copied", "all"]));
  const [period, setPeriod] = useState(() => remembered("period", periods[periods.length - 1], periods));
  const [doc, setDoc] = useState(null);
  const [state, setState] = useState("loading");
  const [, setNight] = useState(false);

  useEffect(() => { followColours(setNight); followHeight(); }, []);
  useEffect(() => {
    let live = true;
    setState((s) => (s === "ready" ? "ready" : "loading"));
    insights(whose, period).then((row) => {
      if (!live) return;
      if (!row) { setState("none"); return; }
      setDoc(row); setState("ready");
    }).catch(() => live && setState(signedOut() ? "signedout" : "error"));
    return () => { live = false; };
  }, [whose, period]);

  const pick = (setter, key) => (v) => { setter(v); remember(key, v); };
  const d = doc && doc.data;

  return (
    <div className="page">
      <div className="bar">
        <span className="meta">{doc ? T("Worked out {when}", { when: stamp(doc.computed_at) }) : ""}</span>
        <div className="right">
          <div className="seg" role="group" aria-label={T("Whose trades")}>
            {[["own", T("Yours")], ["copied", T("Copied")], ["all", T("All")]].map(([k, label]) => (
              <button key={k} type="button" className={whose === k ? "on" : ""} aria-pressed={whose === k} onClick={() => pick(setWhose, "whose")(k)}>{label}</button>
            ))}
          </div>
          {periods.length > 1 && (
            <div className="chips" role="group" aria-label={T("Period")}>
              {periods.map((p) => (
                <button key={p} type="button" className={period === p ? "on" : ""} aria-pressed={period === p} onClick={() => pick(setPeriod, "period")(p)}>{PERIODS[p]()}</button>
              ))}
            </div>
          )}
        </div>
      </div>

      {state === "loading" && !d && <div className="empty">{T("Loading your Trade Log…")}</div>}
      {state === "none" && <div className="empty">{T("Your Trade Log is being worked out after the first sync. Check back in about 10 minutes.")}</div>}
      {state === "signedout" && <div className="empty">{T("Sign in on the main page to see your Trade Log.")}</div>}
      {state === "error" && !d && <div className="empty">{T("The Trade Log could not load just now.")}</div>}

      {d && <Scorecard d={d} whose={whose} />}

      {d && (
        <nav className="tabs" aria-label={T("Trade Log sections")}>
          {TABS.map(([k, label]) => (
            <button key={k} type="button" className={tab === k ? "on" : ""} aria-current={tab === k} onClick={() => pick(setTab, "tab")(k)}>{label()}</button>
          ))}
        </nav>
      )}
      {d && tab === "perf" && <Performance d={d} whose={whose} />}
      {d && tab === "edge" && <Edge d={d} />}
      {d && tab === "risk" && <Risk d={d} />}
      {d && tab === "behav" && <Behaviour d={d} />}
      {d && tab === "open" && <OpenNow d={d} />}
      {d && tab === "trades" && <Trades whose={whose} since={d.start} />}
    </div>
  );
}

function Tile({ label, value, sub, cls, tip }) {
  return (
    <div className="tile" title={tip || ""}>
      <div className="l">{label}</div>
      <div className={"v " + (cls || "")}>{value}</div>
      <div className="s">{sub}</div>
    </div>
  );
}

function Scorecard({ d, whose }) {
  const a = d.account;
  const c = d.closed;
  if (a) {
    const b = a.bench || {};
    return (
      <section className="tiles" aria-label={T("Scorecard")}>
        <Tile label={T("Total return")} value={pct(a.total_pct)} cls={tone(a.total_pct)} sub={T("since {when}", { when: monthYear(a.from) })}
          tip={T("eToro's own daily return for your whole account, chained together. Money paid in or taken out doesn't move it.")} />
        <Tile label={T("Yearly average")} value={pct(a.yearly_pct, 1)} cls={tone(a.yearly_pct)} sub={T("compounded")}
          tip={T("The steady yearly return that ends at the same place.")} />
        <Tile label={T("Deepest fall")} value={pct(a.deepest.pct)} cls="bad" sub={`${monthYear(a.deepest.from)} – ${monthYear(a.deepest.to)}`}
          tip={T("The largest drop from a high point to a low.")} />
        <Tile label={T("Best year")} value={pct(a.best_year.pct)} cls={tone(a.best_year.pct)} sub={a.best_year.year} />
        <Tile label={T("Worst year")} value={pct(a.worst_year.pct)} cls={tone(a.worst_year.pct)} sub={a.worst_year.year} />
        <Tile label={T("Bitcoin, same days")} value={b.btc ? pct(b.btc.total) : "—"}
          sub={b.spx ? T("S&P 500: {v}", { v: pct(b.spx.total) }) : ""}
          tip={T("What simply holding each would have returned over the same days, to set your return against.")} />
      </section>
    );
  }
  return (
    <section className="tiles" aria-label={T("Scorecard")}>
      <Tile label={T("Closed trades result")} value={money(c.net)} cls={tone(c.net)} sub={T("{n} closed trades", { n: c.trades })} />
      <Tile label={T("Win rate")} value={pct(c.win_rate, 0, false)} sub={T("{w} wins, {l} losses", { w: c.wins, l: c.losses })} />
      <Tile label={T("Profit factor")} value={c.profit_factor == null ? "—" : c.profit_factor.toFixed(2)} sub={T("Gross wins divided by gross losses.")} />
    </section>
  );
}
