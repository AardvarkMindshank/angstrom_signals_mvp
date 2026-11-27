import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { insights, connections, forgetInsights, rpc } from "../../lib/api.js";
import { money, pct, tone, monthYear, stamp } from "../../lib/format.js";
import { Connect, Manage, names, LIMIT } from "./Connections.jsx";
import Performance from "./Performance.jsx";
import Edge from "./Edge.jsx";
import Risk from "./Risk.jsx";
import Behaviour from "./Behaviour.jsx";
import OpenNow from "./OpenNow.jsx";
import Trades from "./Trades.jsx";
import Review from "./Review.jsx";

const TABS = [["perf", () => T("Performance")], ["edge", () => T("Edge")], ["risk", () => T("Risk & exits")],
  ["behav", () => T("Behaviour")], ["open", () => T("Open now")], ["trades", () => T("Trades")]];
const PERIODS = { "1y": () => T("1Y"), "3y": () => T("3Y"), "5y": () => T("5Y"), all: () => T("All") };
const HISTORY_DAYS = { plus: 90 };          // as the classic Trade Log: Plus keeps the most recent history only

function remembered(key, fallback, allowed) {
  try { const v = window.localStorage.getItem("tl2_" + key); return allowed.includes(v) ? v : fallback; } catch (e) { return fallback; }
}
function remember(key, value) { try { window.localStorage.setItem("tl2_" + key, value); } catch (e) { /* private window */ } }

export default function TradeLog({ account }) {
  const plan = account.plan;
  const limited = !!HISTORY_DAYS[plan];
  const periods = limited ? ["1y"] : ["1y", "3y", "5y", "all"];
  const [conns, setConns] = useState(null);
  const [manage, setManage] = useState(false);
  const [scope, setScope] = useState("all");
  const [tab, setTab] = useState(() => remembered("tab", "perf", TABS.map((x) => x[0])));
  const [whose, setWhose] = useState(() => remembered("whose", "own", ["own", "copied", "all"]));
  const [period, setPeriod] = useState(() => remembered("period", periods[periods.length - 1], periods));
  const [doc, setDoc] = useState(null);
  const [state, setState] = useState("loading");
  const [toast, setToast] = useState("");

  const loadConns = () => connections().then(setConns).catch(() => setConns([]));
  useEffect(() => { loadConns(); }, []);

  useEffect(() => {
    if (!conns || !conns.length) return;
    let live = true;
    setState((s) => (s === "ready" ? "ready" : "loading"));
    insights(scope, whose, period).then((row) => {
      if (!live) return;
      if (!row) { setDoc(null); setState("none"); return; }
      setDoc(row); setState("ready");
    }).catch(() => live && setState("error"));
    return () => { live = false; };
  }, [conns, scope, whose, period]);

  const pick = (setter, key) => (v) => { setter(v); if (key) remember(key, v); };

  if (conns === null) return <div className="empty">{T("Loading your Trade Log…")}</div>;
  if (!LIMIT[plan]) {
    return (
      <section className="card">
        <h2>{T("Trade Log")}</h2>
        <p>{T("Connect your trading platform to see how your trades went and what the market looked like at the time. The Trade Log is part of the Plus, Pro and Elite plans.")}</p>
      </section>
    );
  }
  if (!conns.length) return <div className="page"><Connect onDone={() => { forgetInsights(); loadConns(); }} /><Disclaimer /></div>;

  const label = names(conns);
  const synced = conns.map((c) => c.last_sync_at).filter(Boolean).sort().pop();
  const refresh = async () => {
    try {
      const asked = await Promise.all(conns.map((c) => rpc("tradelog_request_refresh", { p_id: c.id })));
      setToast(asked.some(Boolean) ? T("Refresh requested.") : T("Synced recently. Try again in a few minutes."));
    } catch (e) { setToast(T("Could not ask for a refresh. Please try again.")); }
    setTimeout(() => setToast(""), 5000);
  };
  const d = doc && doc.data;
  const classRow = d && d.edge && (d.edge.rows || []).find((r) => r.dim === "asset_class");
  const classes = classRow ? classRow.cells.map((c) => c.label) : [];

  return (
    <div className="page">
      <div className="bar">
        <span className="meta">{synced ? T("Synced {when}", { when: stamp(synced) }) : T("Importing")}
          {doc ? " · " + T("Worked out {when}", { when: stamp(doc.computed_at) }) : ""}</span>
        <div className="right">
          {toast && <span className="m">{toast}</span>}
          <button type="button" className="ghost" onClick={refresh}>{T("Refresh")}</button>
          <button type="button" className={"ghost" + (manage ? " on" : "")} aria-pressed={manage} onClick={() => setManage(!manage)}>{T("Manage")}</button>
        </div>
      </div>

      {manage && <Manage conns={conns} plan={plan} onChange={() => { forgetInsights(); loadConns(); }} />}

      {conns.length > 1 && (
        <nav className="tabs" aria-label={T("Platforms")}>
          {[["all", T("All platforms")], ...conns.map((c) => [c.id, label[c.id]])].map(([k, l]) => (
            <button key={k} type="button" className={scope === k ? "on" : ""} aria-current={scope === k} onClick={() => setScope(k)}>{l}</button>
          ))}
        </nav>
      )}

      <div className="bar">
        <div className="seg" role="group" aria-label={T("Whose trades")}>
          {[["own", T("Yours")], ["copied", T("Copied")], ["all", T("All")]].map(([k, l]) => (
            <button key={k} type="button" className={whose === k ? "on" : ""} aria-pressed={whose === k} onClick={() => pick(setWhose, "whose")(k)}>{l}</button>
          ))}
        </div>
        {periods.length > 1
          ? (
            <div className="chips" role="group" aria-label={T("Period")}>
              {periods.map((p) => (
                <button key={p} type="button" className={period === p ? "on" : ""} aria-pressed={period === p} onClick={() => pick(setPeriod, "period")(p)}>{PERIODS[p]()}</button>
              ))}
            </div>
          )
          : <span className="m">{T("Your plan shows the last year. Pro and Elite show your whole history.")}</span>}
      </div>

      {state === "loading" && !d && <div className="empty">{T("Loading your Trade Log…")}</div>}
      {state === "none" && <div className="empty">{T("Your Trade Log is being worked out after the first sync. Check back in about 10 minutes.")}</div>}
      {state === "error" && !d && <div className="empty">{T("The Trade Log could not load just now.")}</div>}

      {d && <Scorecard d={d} />}
      {d && <ClosedRow d={d} whose={whose} />}

      {d && (
        <nav className="tabs" aria-label={T("Trade Log sections")}>
          {TABS.map(([k, l]) => (
            <button key={k} type="button" className={tab === k ? "on" : ""} aria-current={tab === k} onClick={() => pick(setTab, "tab")(k)}>{l()}</button>
          ))}
        </nav>
      )}
      {d && tab === "perf" && <Performance d={d} whose={whose} />}
      {d && tab === "edge" && <Edge d={d} />}
      {d && tab === "risk" && <Risk d={d} />}
      {d && tab === "behav" && <><Behaviour d={d} /><Review account={account} classes={classes} /></>}
      {d && tab === "open" && <OpenNow d={d} />}
      {d && tab === "trades" && <Trades scope={scope} whose={whose} since={d.start} hideRewards={!!(d.rewards && d.rewards.count)} />}
      <Disclaimer />
    </div>
  );
}

function Disclaimer() {
  return <p className="sub" style={{ marginTop: 18 }}>{T("Read-only connections. Descriptive readings, not financial advice.")}</p>;
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

function Scorecard({ d }) {
  const a = d.account;
  if (!a) return null;
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

// The chosen trades (Yours / Copied / All), closed in this period: the row that changes with the switch. The tiles
// above are the whole account, which eToro's daily return can't split.
function ClosedRow({ d, whose }) {
  const c = d.closed;
  const r = d.rewards;
  if (!c) return null;
  const title = { own: T("Your own closed trades"), copied: T("Copied closed trades"), all: T("All closed trades") }[whose];
  return (
    <section aria-label={title}>
      <div className="rowtitle">{title}</div>
      <div className="tiles">
        <Tile label={T("Result")} value={money(c.net)} cls={tone(c.net)} sub={T("{n} closed trades", { n: c.trades.toLocaleString() })} />
        <Tile label={T("Win rate")} value={pct(c.win_rate, 0, false)} sub={T("{w} wins, {l} losses", { w: c.wins.toLocaleString(), l: c.losses.toLocaleString() })} />
        <Tile label={T("Profit factor")} value={c.profit_factor == null ? "—" : c.profit_factor.toFixed(2)} sub={T("Gross wins divided by gross losses.")} />
        <Tile label={T("Average trade")} value={money(c.average)} cls={tone(c.average)} sub={T("Fees: {v}", { v: money(c.fees, false) })} />
        {r && r.count > 0 && whose !== "copied" && (
          <Tile label={T("Staking rewards")} value={money(r.credited + r.result, false)} sub={T("{n} rewards and airdrops, not counted as trades", { n: r.count.toLocaleString() })}
            tip={T("eToro pays crypto staking rewards as small new positions each month. They are kept out of the trade numbers; this is what they were worth when sold.")} />
        )}
      </div>
    </section>
  );
}
