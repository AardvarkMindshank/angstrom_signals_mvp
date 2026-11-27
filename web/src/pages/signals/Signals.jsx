import React, { useEffect, useMemo, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import { saveSettings, saveWatchlist, preferences } from "../../lib/account.js";
import { watchlists } from "../../lib/assets.js";
import { usd, signed, compact } from "../../lib/format.js";
import { assetHref, Logo } from "../../components/Search.jsx";

// ₿ Crypto Signals and 📈 Equity Signals: your watchlist (or a funnel's assets at one stage) with the readings you
// choose as columns. The data service works every column out as the classic tables do (service/signals.py).
const rtone = (v) => (v == null ? "" : v >= 20 ? "good" : v <= -20 ? "bad" : "");
const pctTone = (v) => (v == null ? "" : v > 0.05 ? "good" : v < -0.05 ? "bad" : "");
const MARK = { yes: "✓", no: "✕", unknown: "?" };

function Bar({ v }) {
  const size = v == null ? 0 : Math.max(1, Math.min(50, Math.round(Math.abs(v) / 2)));
  return <span className="mbar" aria-hidden="true">{v != null && <i className={rtone(v) || "mid"} style={v >= 0 ? { left: "50%", width: size + "%" } : { right: "50%", width: size + "%" }} />}</span>;
}

function Spark({ values, tone }) {
  const pts = (values || []).filter((v) => v != null && isFinite(v));
  if (pts.length < 2) return <span className="m">—</span>;
  const W = 84, H = 24, lo = Math.min(...pts), hi = Math.max(...pts), span = hi - lo || 1, last = pts.length - 1;
  const path = pts.map((v, i) => `${(2 + (W - 4) * i / last).toFixed(1)},${(2 + (H - 4) * (1 - (v - lo) / span)).toFixed(1)}`).join(" ");
  return <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true"><polyline fill="none" stroke={tone === "bad" ? "var(--bad)" : tone === "good" ? "var(--good)" : "var(--grey)"} strokeWidth="1.5" vectorEffect="non-scaling-stroke" points={path} /></svg>;
}

export default function Signals({ market: wanted, account }) {
  const settings = (account && account.settings) || {};
  const trades = { crypto: settings.trade_crypto !== false, equity: settings.trade_equities !== false };
  const market = wanted === "equity" || (!trades.crypto && wanted !== "crypto") ? "equity" : "crypto";
  const [got, setGot] = useState(null);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [view, setView] = useState({});            // mode, pick, stage asked for (else the saved ones)
  const [sort, setSort] = useState({ by: "trend", dir: -1 });
  const [fold, setFold] = useState(() => { try { return JSON.parse(localStorage.getItem("mn_sig_fold")) || {}; } catch (e) { return {}; } });
  const [chooser, setChooser] = useState(false);
  const [round, setRound] = useState(0);

  useEffect(() => { setView({}); setGot(null); }, [market]);
  useEffect(() => {
    let live = true; setBusy(true); setErr("");
    const q = new URLSearchParams({ market, lang, ...(view.mode ? { mode: view.mode } : {}), ...(view.pick ? { pick: view.pick } : {}), ...(view.stage ? { stage: view.stage } : {}), ...(round ? { fresh: "true" } : {}) });
    call(`/signals?${q}`, { timeout: 60000 }).then((g) => { if (live) { setGot(g); setBusy(false); } })
      .catch((e) => { if (live) { setBusy(false); setErr(e.status === 0 ? T("The table service isn't reachable just now. Please try again in a minute.") : T("The table couldn't load just now. Please try again.")); } });
    return () => { live = false; };
  }, [market, view.mode, view.pick, view.stage, round]);

  const keys = market === "crypto" ? ["funnel_pick", "funnel_stage", "crypto_table"] : ["eq_funnel_pick", "eq_funnel_stage", "equity_table"];
  const setMode = (mode) => { setView({ mode }); saveSettings({ [keys[2]]: mode }).catch(() => {}); };
  const setPick = (pick, stage) => { setView({ mode: "funnel", pick, stage }); saveSettings({ [keys[0]]: pick, [keys[1]]: stage }).catch(() => {}); };
  const toggleFold = (part) => setFold((f) => { const n = { ...f, [part]: !f[part] }; try { localStorage.setItem("mn_sig_fold", JSON.stringify(n)); } catch (e) { /* private window */ } return n; });
  const mode = got ? got.mode : view.mode || "watchlist";
  const cols = got ? got.columns : [];
  const groups = cols.filter((c) => c.part === "groups"), sets = cols.filter((c) => c.part === "sets");
  const flags = (got && got.flags) || { period: true, extra: true };
  const crypto = market === "crypto";
  const staged = got && got.rows.some((r) => r.stage);
  const showComments = got && got.rows.some((r) => r.comments);

  const value = (r, by) => {
    if (by === "name") return String(r.symbol).toLowerCase();
    const c = cols.find((x) => x.key === by || x.cluster === by);
    if (c && c.cluster) return (r.clusters[c.cluster] || {}).value;
    if (c && c.part === "groups") return (r.cells[c.key] || {}).value;
    if (c && c.part === "sets") return { yes: 2, unknown: 1, no: 0 }[(r.cells[c.key] || {}).answer];
    if (by === "stage") return r.stage ? r.stage.sort : null;
    if (by === "community") return (r.crowd.up || 0) - (r.crowd.down || 0);
    if (by === "groups") { const v = groups.map((g) => (g.cluster ? (r.clusters[g.cluster] || {}).value : (r.cells[g.key] || {}).value)).filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; }
    if (by === "sets") return sets.filter((s) => (r.cells[s.key] || {}).answer === "yes").length;
    return r[by];
  };
  const rows = useMemo(() => !got ? [] : [...got.rows].sort((a, b) => {
    const x = value(a, sort.by), y = value(b, sort.by);
    if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
  }), [got, sort]);
  const Th = ({ by, children, title, cls }) => (
    <th className={cls} title={title} aria-sort={sort.by === by ? (sort.dir > 0 ? "ascending" : "descending") : undefined}>
      <button type="button" onClick={() => setSort({ by, dir: sort.by === by ? -sort.dir : by === "name" ? 1 : -1 })}>{children}{sort.by === by ? (sort.dir > 0 ? " ↑" : " ↓") : ""}</button>
    </th>
  );
  const add = async (r) => {
    try { const p = await preferences(); const kind = crypto ? "crypto" : "equity"; const list = { ...(crypto ? p.crypto : p.equity), [r.id]: r.symbol.replace(/ \(.*\)$/, "") }; await saveWatchlist(kind, list); watchlists.reset(); setRound((n) => n + 1); } catch (e) { /* stays as it was */ }
  };

  return (
    <div className="page sigs">
      <div className="bar">
        <h1 className="ptitle">{crypto ? "₿ " + T("Crypto Signals") : "📈 " + T("Equity Signals")}</h1>
        <div className="right">
          {trades.crypto && trades.equity && (
            <div className="seg" role="tablist" aria-label={T("Market")}>
              <a role="tab" aria-selected={crypto} className={"segl" + (crypto ? " on" : "")} href="#signals/crypto">{T("Crypto")}</a>
              <a role="tab" aria-selected={!crypto} className={"segl" + (!crypto ? " on" : "")} href="#signals/equity">{T("Equities")}</a>
            </div>
          )}
        </div>
      </div>
      <div className="bar">
        <div className="seg" role="radiogroup" aria-label={T("Show")}>
          <button type="button" role="radio" aria-checked={mode === "watchlist"} className={mode === "watchlist" ? "on" : ""} onClick={() => setMode("watchlist")}>⭐ {T("My Watchlist")}</button>
          <button type="button" role="radio" aria-checked={mode === "funnel"} className={mode === "funnel" ? "on" : ""} onClick={() => setMode("funnel")}>🔻 {T("Dynamic funnel")}</button>
        </div>
        <div className="right">
          <button type="button" className="ghost" onClick={() => setChooser(true)} title={T("Choose which Signal Groups and Signal Sets the tables show")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 4h18v16H3zM5 6v12h3V6zm5 0v12h4V6zm6 0v12h3V6z" /></svg>{T("Columns")}
          </button>
          <button type="button" className="ghost icon" onClick={() => setRound((n) => n + 1)} title={T("Refresh")} aria-label={T("Refresh")}>⟳</button>
        </div>
      </div>
      {got && got.funnel && <FunnelBar f={got.funnel} onPick={setPick} />}
      {err && <p className="note bad">{err}</p>}
      {!got && busy && <div className="empty" style={{ height: 300 }}>{T("Loading…")}</div>}
      {got && !rows.length && <p className="sub">{mode === "funnel" ? (got.funnel && !got.funnel.funnels.length ? T("You have no funnels in this market yet.") : T("No assets hold this stage right now.")) : T("This watchlist is empty. Add assets in ⚙️ Settings.")}</p>}
      {got && rows.length > 0 && (
        <>
          <p className="sub">{T("Click a column title to sort. 📈 Trend, 🎯 Stretch and 🔊 Flow each run from -100 to +100 (positive means up); they describe the market and are not forecasts. Hover a reading for what it means, click it for the breakdown. Click a name to open the asset.")}</p>
          <div className="tscroll" style={{ opacity: busy ? 0.6 : 1 }}>
            <table className="t sig">
              <thead>
                <tr>
                  <Th by="name" cls="sticky">{T("Asset")}</Th>
                  {staged && <Th by="stage">{T("Stage")}</Th>}
                  <Th by="holders" title={T("How many members watch this asset")}>{T("Watching")}</Th>
                  {crypto && <Th by="rank">{T("Rank")}</Th>}
                  {groups.length > 0 && (fold.g ? <th className="fold"><button type="button" onClick={() => toggleFold("g")} title={T("Show the {name} columns", { name: "Signal Groups" })}>▸ {T("Groups")}</button></th>
                    : groups.map((c, i) => <Th key={c.key} by={c.cluster || c.key} title={c.hint} cls={i === 0 ? "secfirst" : ""}>{i === 0 && <span className="foldbtn" role="button" tabIndex={0} onClick={(e) => { e.stopPropagation(); toggleFold("g"); }} title={T("Fold the {name} columns", { name: "Signal Groups" })}>◂ </span>}{c.icon ? c.icon + " " : ""}{c.name}</Th>))}
                  {sets.length > 0 && (fold.s ? <th className="fold"><button type="button" onClick={() => toggleFold("s")} title={T("Show the {name} columns", { name: "Signal Sets" })}>▸ {T("Sets")}</button></th>
                    : sets.map((c, i) => <Th key={c.key} by={c.key} title={c.hint} cls={"c" + (i === 0 ? " secfirst" : "")}>{i === 0 && <span className="foldbtn" role="button" tabIndex={0} onClick={(e) => { e.stopPropagation(); toggleFold("s"); }} title={T("Fold the {name} columns", { name: "Signal Sets" })}>◂ </span>}{c.name}</Th>))}
                  <Th by="price" cls="r">{T("Price")}</Th>
                  <Th by="rsi" cls="r">RSI</Th>
                  {!crypto && <Th by="next_earnings">{T("Earnings")}</Th>}
                  {flags.period && <Th by="change_1d" cls="r" title={T("Change since the previous daily close")}>1d %</Th>}
                  {flags.extra && <Th by="change_7d" cls="r">7d %</Th>}
                  {flags.period && <Th by="change_30d" cls="r">30d %</Th>}
                  {flags.extra && <><Th by="market_cap" cls="r">{T("Market Cap")}</Th><Th by="atr_pct" cls="r" title={T("Average daily range as a share of the price")}>ATR %</Th><Th by="volume_ratio" cls="r" title={T("Volume against its usual level")}>{T("Vol")}</Th></>}
                  <Th by="mood" cls="r">{T("Sentiment")}</Th>
                  <Th by="community">{T("Community")}</Th>
                  {showComments && <Th by="comments" cls="c">{T("Comments")}</Th>}
                  <Th by="change_30d" cls="r">{T("30-day trend")}</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key}>
                    <td className="sticky">
                      <span className="aname"><Logo a={{ symbol: r.symbol }} src={r.logo} size={24} /><a href={assetHref(r.key, "chart")}><b>{r.symbol}</b></a>
                        {!r.own && <button type="button" className="ghost icon addw" title={T("Add {symbol} to My Watchlist", { symbol: r.symbol })} aria-label={T("Add {symbol} to My Watchlist", { symbol: r.symbol })} onClick={() => add(r)}>＋</button>}</span>
                      {r.problem && <div className="m">{r.problem}</div>}
                    </td>
                    {staged && <td title={r.stage ? r.stage.tip : ""} className="help">{r.stage ? r.stage.icon : "—"}</td>}
                    <td>{r.holders ? `👥 ${r.holders}` : <span className="m">—</span>}</td>
                    {crypto && <td>{r.rank ? `#${r.rank}` : <span className="m">—</span>}</td>}
                    {groups.length > 0 && (fold.g ? <td className="c" title={groups.map((g) => { const v = g.cluster ? (r.clusters[g.cluster] || {}).value : (r.cells[g.key] || {}).value; return `${g.name}: ${v == null ? "—" : signed(v)}`; }).join("\n")}>
                      <span className="dots">{groups.map((g) => { const v = g.cluster ? (r.clusters[g.cluster] || {}).value : (r.cells[g.key] || {}).value; return <i key={g.key} className={rtone(v) || (v == null ? "none" : "mid")} />; })}</span></td>
                      : groups.map((g) => <GroupCell key={g.key} r={r} g={g} />))}
                    {sets.length > 0 && (fold.s ? <td className="c"><b className={sets.some((s) => (r.cells[s.key] || {}).answer === "yes") ? "good" : "m"} title={T("{n} of {total} Sets say Yes", { n: sets.filter((s) => (r.cells[s.key] || {}).answer === "yes").length, total: sets.length })}>{sets.filter((s) => (r.cells[s.key] || {}).answer === "yes").length}✓</b></td>
                      : sets.map((s) => <SetCell key={s.key} r={r} s={s} />))}
                    <td className="r num">{r.price == null ? "—" : usd(r.price)}</td>
                    <td className="r num">{r.rsi == null ? "—" : r.rsi.toFixed(1)}</td>
                    {!crypto && <td>{r.next_earnings || <span className="m">—</span>}</td>}
                    {flags.period && <td className={"r num " + pctTone(r.change_1d)}>{r.change_1d == null ? "—" : `${r.change_1d > 0 ? "+" : ""}${r.change_1d.toFixed(1)}%`}</td>}
                    {flags.extra && <td className={"r num " + pctTone(r.change_7d)}>{r.change_7d == null ? "—" : `${r.change_7d > 0 ? "+" : ""}${r.change_7d.toFixed(1)}%`}</td>}
                    {flags.period && <td className={"r num " + pctTone(r.change_30d)}>{r.change_30d == null ? "—" : `${r.change_30d > 0 ? "+" : ""}${r.change_30d.toFixed(1)}%`}</td>}
                    {flags.extra && <><td className="r num">{r.market_cap ? compact(r.market_cap) : "—"}</td><td className="r num">{r.atr_pct == null ? "—" : r.atr_pct.toFixed(2)}</td><td className="r num">{r.volume_ratio == null ? "—" : r.volume_ratio.toFixed(2)}</td></>}
                    <td className="r">{r.mood == null ? <span className="m">—</span> : <a className={"rv " + rtone(r.mood)} href={assetHref(r.key, "news")} title={T("Headline sentiment for this asset, -100 to +100")}>📰 {signed(r.mood)}</a>}</td>
                    <td><a className="crowdc" href={assetHref(r.key, "community")} title={T("Members who agree and disagree with this reading")}>👍 {r.crowd.up || 0} · 👎 {r.crowd.down || 0}{r.crowd.alt_count ? <span className={"rv " + rtone(r.crowd.alt_avg)} title={T("members' own score {s} ({n})", { s: signed(r.crowd.alt_avg), n: r.crowd.alt_count })}>{signed(r.crowd.alt_avg)}</span> : null}</a></td>
                    {showComments && <td className="c">{r.comments ? <a href={assetHref(r.key, "community")} title={T("Open the comments")}>💬 {r.comments}</a> : ""}</td>}
                    <td className="r"><Spark values={r.closes} tone={pctTone(r.change_30d)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {got.funnel && got.funnel.more > 0 && <p className="sub">{T("Showing the largest {n} by market cap; {more} more hold this stage.", { n: rows.length, more: got.funnel.more })}</p>}
        </>
      )}
      {chooser && <ColumnChooser onClose={(changed) => { setChooser(false); if (changed) setRound((n) => n + 1); }} />}
    </div>
  );
}

function GroupCell({ r, g }) {
  if (g.cluster) {
    const c = r.clusters[g.cluster] || {};
    return <td><a className="rcell" href={assetHref(r.key, "readings")} title={c.tip}><Bar v={c.value} /><span className={"rv " + rtone(c.value)}>{c.value == null ? "—" : signed(c.value)}</span></a></td>;
  }
  const c = r.cells[g.key];
  if (!c) return <td><span className="m">—</span></td>;
  if (c.waiting) return <td title={c.tip}><span className="m">—</span></td>;
  return <td><a className="rcell" href={assetHref(r.key, "sets")} title={c.tip}><Bar v={c.value} />{c.label ? <b className="glabel">{c.label}</b> : <span className={"rv " + rtone(c.value)}>{c.value == null ? "—" : signed(c.value)}</span>}{c.stale && <sup>⏳</sup>}</a></td>;
}

function SetCell({ r, s }) {
  const c = r.cells[s.key];
  if (!c) return <td className="c"><span className="m">—</span></td>;
  if (c.waiting) return <td className="c" title={c.tip}><span className="m">—</span></td>;
  return <td className="c"><a className={"ans " + c.answer} href={assetHref(r.key, "sets")} title={c.tip} aria-label={c.answer}>{MARK[c.answer]}</a>{c.stale && <sup>⏳</sup>}</td>;
}

function FunnelBar({ f, onPick }) {
  if (!f.funnels.length) return <p className="sub">{T("You have no funnels in this market yet.")}</p>;
  return (
    <div className="funnelbar">
      <div className="fpick">
        {f.funnels.map((x) => (
          <div key={x.id} className={"frow" + (x.id === f.picked ? " on" : "")}>
            <div className="fhead"><b>{x.dir_icon} {x.name}</b>{x.paused && <span className="m"> · ⏸️ {T("paused")}</span>}<span className="m"> · {x.checked}</span></div>
            <div className="chips fchips">
              {x.chips.map((c) => (
                <button key={c.key} type="button" className={x.id === f.picked && f.stage === c.key ? "on" : ""} title={c.hover || c.label} onClick={() => onPick(x.id, c.key)}>
                  {c.icon} {c.count}{c.new ? <span className="good"> ＋{c.new}</span> : null} <span className="clabel">{c.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      {f.line && <p className="m" style={{ margin: "6px 0 0" }}>{f.line}</p>}
      {f.health && <p className="note bad">{f.health}</p>}
    </div>
  );
}

function ColumnChooser({ onClose }) {
  const [o, setO] = useState(null);
  const [pick, setPick] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { call(`/signals/columns?lang=${lang}`).then((x) => { setO(x); setPick(x.chosen); }).catch(() => setO({ down: true })); }, []);
  useEffect(() => { const k = (e) => { if (e.key === "Escape") onClose(false); }; window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, []);
  const flip = (part, key) => setPick((p) => { const has = p[part].includes(key); if (!has && p[part].length >= o.max) return p; return { ...p, [part]: has ? p[part].filter((k) => k !== key) : [...p[part], key] }; });
  const save = async () => { setSaving(true); try { await saveSettings({ table_columns: pick }); onClose(true); } catch (e) { setSaving(false); } };
  return (
    <div className="dvpop" role="dialog" aria-modal="true" aria-label={T("Choose table columns")} onClick={(e) => { if (e.target === e.currentTarget) onClose(false); }}>
      <div className="modal">
        <div className="bar"><h2 style={{ margin: 0 }}>{T("Choose table columns")}</h2><button type="button" className="ghost icon" style={{ marginLeft: "auto" }} onClick={() => onClose(false)} aria-label={T("Close")}>✕</button></div>
        <p className="sub">{T("Pick up to {n} Signal Groups and {n} Signal Sets. Both tables show the same columns.", { n: o && o.max ? o.max : 12 })}</p>
        {!o ? <p className="sub">{T("Loading…")}</p> : o.down ? <p className="note bad">{T("The choices couldn't load just now.")}</p> : (
          <div className="choose">
            {[["groups", T("Signal Groups")], ["sets", T("Signal Sets")]].map(([part, title]) => (
              <div key={part}>
                <div className="rowtitle">{title} <span className="m">{pick[part].length}/{o.max}</span></div>
                <div className="chklist">
                  {o[part].map(([k, l]) => <label key={k} className="ptog"><input type="checkbox" checked={pick[part].includes(k)} onChange={() => flip(part, k)} /><span>{l}</span></label>)}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="bar" style={{ marginTop: 14 }}><div className="right"><button type="button" className="ghost" onClick={() => onClose(false)}>{T("Cancel")}</button><button type="button" className="primary" disabled={!pick || saving} onClick={save}>{T("Save")}</button></div></div>
      </div>
    </div>
  );
}
