import React, { useEffect, useState } from "react";
import { T } from "../../lib/i18n.js";
import { asset, universe, watchlists, readingsHistory, tide, parseKey } from "../../lib/assets.js";
import { usd, pct, signed, tone, dayMonthYear, stamp } from "../../lib/format.js";
import { Logo, assetHref } from "../../components/Search.jsx";
import { label, WIND, COVERAGE } from "./words.js";
import Chart from "./Chart.jsx";
import Readings from "./Readings.jsx";
import News from "./News.jsx";
import Derivatives from "./Derivatives.jsx";
import Conditions from "./Conditions.jsx";
import Activity from "./Activity.jsx";

// One page per asset: everything MarketNavi knows about it, reached from the search (and later from any table).
export const mood = (s) => (s == null ? null : Math.round((Number(s) - 50) * 2));   // stored 0..100, shown −100..+100

export default function Asset({ assetKey, tab, account }) {
  const who = parseKey(assetKey);
  const [row, setRow] = useState(undefined);
  const [meta, setMeta] = useState(null);
  const [hist, setHist] = useState([]);
  const [sea, setSea] = useState(null);
  const [watched, setWatched] = useState(false);

  useEffect(() => {
    let live = true;
    setRow(undefined); setHist([]);
    asset(assetKey).then((r) => live && setRow(r)).catch(() => live && setRow(null));
    universe().then((u) => live && setMeta(u.find((a) => a.key === assetKey) || null)).catch(() => {});
    readingsHistory(assetKey).then((h) => live && setHist(h)).catch(() => {});
    tide().then((t) => live && setSea(t)).catch(() => {});
    watchlists().then((w) => live && who && setWatched(!!(who.kind === "crypto" ? w.crypto : w.equity)[who.id])).catch(() => {});
    window.scrollTo(0, 0);
    return () => { live = false; };
  }, [assetKey]);

  if (!who) return <div className="empty">{T("That asset isn't one MarketNavi follows.")}</div>;
  if (row === undefined) return <div className="empty">{T("Loading…")}</div>;
  if (row === null) return <div className="empty">{T("MarketNavi has no data for this asset yet.")}</div>;

  const crypto = who.kind === "crypto";
  const f = (row.readings && row.readings.fields) || {};
  const sig = f.signals || {};
  const cl = sig.clusters || {};
  const bars = row.prices || [];
  const last = bars[bars.length - 1] || {};
  const name = (meta && meta.name) || (sig.name) || who.id;
  const symbol = (meta && meta.symbol) || who.id.toUpperCase();
  const a = { symbol, name };
  const weekAgo = hist.length > 5 ? hist[Math.max(0, hist.length - 8)] : null;
  const delta = (k) => (weekAgo && weekAgo[k] != null && f[k] != null ? f[k] - weekAgo[k] : null);
  const m = mood(row.sentiment_score);
  const rep = row.sentiment_report || {};
  const wind = sea ? sea[crypto ? "wind_crypto" : "wind_equity"] : null;
  const tabs = [["chart", T("Chart")], ["readings", T("Readings")], ["news", T("News")],
    [crypto ? "derivatives" : "earnings", crypto ? T("Derivatives") : T("Earnings")], ["conditions", T("Conditions")], ["activity", T("Your activity")]];
  const on = tabs.some((x) => x[0] === tab) ? tab : "chart";

  const arrow = (d) => (d == null || Math.round(d) === 0 ? "" : (d > 0 ? "▲ " : "▼ ") + Math.abs(Math.round(d)) + " " + T("in a week"));

  return (
    <div className="page asset">
      <div className="ahead">
        <Logo a={a} src={row.logo_url} size={48} />
        <div>
          <h1>{name} <span className="m">{symbol}</span></h1>
          <div className="m">{crypto ? T("Crypto") : T("Equity")}{meta && meta.pair ? ` · Binance ${meta.pair}` : ""}{meta && meta.sector ? ` · ${meta.sector}` : ""}
            {row.market_rank ? ` · #${row.market_rank}` : ""}{watched ? <span className="onlist"> · {T("On your watchlist")}</span> : null}</div>
        </div>
        <div className="right m">{T("Prices updated {when}", { when: stamp(row.prices_updated_at) })}</div>
      </div>

      <section className="tiles hero" aria-label={T("Key figures")}>
        <Tile l={T("Price")} v={usd(f.latest_price ?? last.c)} s={<><span className={tone(f.change_1d)}>{pct(f.change_1d, 1)}</span> {T("today")} · <span className={tone(f.change_7d)}>{pct(f.change_7d, 1)}</span> {T("week")}</>} />
        <Tile l={T("Trend")} v={signed(f.trend)} cls={tone(f.trend)} s={label((cl.trend || {}).label)} s2={arrow(delta("trend"))}
          tip={T("Direction and firmness of the move, from −100 (strong downtrend) to +100 (strong uptrend). Horizon: weeks to months.")} />
        <Tile l={T("Stretch")} v={signed(f.stretch)} cls={tone(f.stretch)} s={label((cl.stretch || {}).label)} s2={arrow(delta("stretch"))}
          tip={T("How far the price has run from its usual range: near −100 very stretched down (oversold), near +100 very stretched up.")} />
        <Tile l={T("Flow")} v={signed(f.flow)} cls={tone(f.flow)} s={label((cl.flow || {}).label)} s2={arrow(delta("flow"))}
          tip={T("Whether volume is backing rises (+) or falls (−).")} />
        <Tile l={T("News mood")} v={signed(m)} cls={m ? tone(m) : ""} s={rep.ok ? T("{n} articles", { n: rep.scored || (rep.headlines || []).length }) : T("Not scored yet")} />
        <Tile l={crypto ? T("Tide for crypto") : T("Tide for equities")} v={wind ? WIND()[wind] || wind : "—"} cls={wind === "headwind" ? "bad" : wind === "tailwind" ? "good" : ""}
          s={sea ? T("held {n} trading days", { n: sea.tide_held }) : ""} />
      </section>

      <p className="lede">
        {[label((cl.trend || {}).label), label((cl.stretch || {}).label), label((cl.flow || {}).label)].filter(Boolean).join(" · ")}
        {m != null ? " · " + T("news: {mood}", { mood: COVERAGE(m) }) : ""}
        {wind && wind !== "neither" ? " · " + (wind === "headwind" ? T("the Tide is a headwind") : T("the Tide is a tailwind")) : ""}
        {!crypto && row.next_earnings ? " · " + T("next earnings {d}", { d: dayMonthYear(row.next_earnings) }) : ""}
      </p>

      <nav className="tabs" aria-label={T("Asset sections")}>
        {tabs.map(([k, l]) => <a key={k} href={assetHref(assetKey, k)} className={on === k ? "on" : ""} aria-current={on === k ? "page" : undefined}>{l}</a>)}
      </nav>
      <div>
        {on === "chart" && <Chart row={row} meta={meta} crypto={crypto} />}
        {on === "readings" && <Readings f={f} hist={hist} />}
        {on === "news" && <News rep={rep} score={m} at={row.sentiment_updated_at} />}
        {(on === "derivatives" || on === "earnings") && <Derivatives row={row} crypto={crypto} who={who} />}
        {on === "conditions" && <Conditions sea={sea} crypto={crypto} />}
        {on === "activity" && <Activity assetKey={assetKey} who={who} account={account} />}
      </div>
      <p className="sub" style={{ marginTop: 8 }}>{crypto ? T("Prices from Binance; derivatives from Coinalyze.") : T("Prices from Yahoo Finance.")} {T("Readings, news mood and Tides from MarketNavi, the same numbers as the rest of the app. Descriptive readings, not financial advice.")}</p>
    </div>
  );
}

function Tile({ l, v, s, s2, cls, tip }) {
  return (
    <div className="tile" title={tip || ""}>
      <div className="l">{l}</div>
      <div className={"v " + (cls || "")}>{v}</div>
      <div className="s">{s}</div>
      {s2 ? <div className="s">{s2}</div> : null}
    </div>
  );
}
