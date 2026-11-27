import React, { useEffect, useRef, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import { SUPABASE_URL, CLASSIC } from "../../lib/supabase.js";
import { saveSettings } from "../../lib/account.js";
import { usd, signed, weekday } from "../../lib/format.js";
import { assetHref, Logo } from "../../components/Search.jsx";
import Icon, { Arrow, Emo, Glyphs, Lead, plain } from "../../components/Icon.jsx";

// 📸 Quick Snapshot: where a member starts the day. The daily video and the two spoken briefings, the Tides card, what
// changed since the last visit, the two market moods, the highest and lowest Trend in your watchlist, your funnels and
// the markets strip. The data service works each part out as the classic page does (service/snapshot.py).
const MEDIA = (path) => `${SUPABASE_URL.replace(/\/$/, "")}/storage/v1/object/public/briefings/${path}`;
const fresh = (path) => fetch(`${MEDIA(path)}?fresh=${Math.floor(Date.now() / 60000)}`, { cache: "no-store" });
const versioned = (path, madeAt) => { const v = String(madeAt || "").replace(/\D/g, "").slice(0, 14); return v ? `${MEDIA(path)}?v=${v}` : MEDIA(path); };
const clock = (s) => { s = Math.round(+s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const rtone = (v) => (v == null ? "" : v >= 20 ? "good" : v <= -20 ? "bad" : "");
const newest = (meta) => Object.entries(meta || {}).filter(([, m]) => m && typeof m === "object").sort((a, b) => String(b[1].made_at || "").localeCompare(String(a[1].made_at || "")))[0];
const read = (k) => { try { return JSON.parse(sessionStorage.getItem(k)); } catch (e) { return null; } };
const keep = (k, v) => { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private window */ } };

export default function Snapshot({ account }) {
  const [snap, setSnap] = useState(() => { try { return JSON.parse(localStorage.getItem("mn_snap_last")); } catch (e) { return null; } });   // the last one seen, at once
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    // The first look of a browser session keeps this visit as the "last visit" for next time, as the classic page
    // does; what changed is worked out once, against the visit before, and kept for the rest of the session.
    const first = !read("mn_snap_saved");
    const load = () => call(`/snapshot?lang=${lang}&save=${first ? "true" : "false"}`, { timeout: 45000 }).then((s) => {
      if (!live) return;
      if (first) { keep("mn_snap_saved", true); keep("mn_snap_changes", s.changes); }
      else { const c = read("mn_snap_changes"); if (c) s.changes = c; }
      setSnap(s);
      try { localStorage.setItem("mn_snap_last", JSON.stringify(s)); } catch (e) { /* full or private */ }
    }).catch((e) => live && setErr(e.status === 0 ? T("Quick Snapshot isn't reachable just now. Please try again in a minute.") : T("Quick Snapshot couldn't load just now. Please try again.")));
    load();
    const timer = setInterval(() => { if (document.visibilityState === "visible") call(`/snapshot?lang=${lang}`).then((s) => { if (!live) return; const c = read("mn_snap_changes"); if (c) s.changes = c; setSnap(s); }).catch(() => {}); }, 5 * 60000);
    return () => { live = false; clearInterval(timer); };
  }, []);

  return (
    <div className="page qsnap">
      <h1 className="ptitle">{T("Quick Snapshot")}</h1>
      <div className="snaptop">
        <Video account={account} />
        <div className="snapcol">
          <Outlook />
          <Passage account={account} />
        </div>
        {snap ? <Tides card={snap.tides} /> : <div className="empty" style={{ minHeight: 240 }}>{err || T("Loading…")}</div>}
      </div>
      {err && <p className="note bad">{err}</p>}
      {snap && (
        <>
          <Changes c={snap.changes} />
          {snap.moods && snap.moods.length > 0 && <div className="snapgrid">{snap.moods.map((m) => <Mood key={m.key} m={m} />)}</div>}
          <Extremes x={snap.extremes} trade={snap.trade} />
          <Funnels tiles={snap.funnels} />
          <Markets m={snap.markets} />
        </>
      )}
    </div>
  );
}

// ---- 🎬 the daily video, and the once-a-day pop-up ---------------------------------------------------------------

export function Video({ account, day: chosen }) {
  const [meta, setMeta] = useState(undefined);
  const [text, setText] = useState(null);
  const [pop, setPop] = useState(false);
  useEffect(() => { fresh("video/videos.json").then((r) => (r.ok ? r.json() : {})).then(setMeta).catch(() => setMeta({})); }, []);
  const top = meta ? (chosen ? (meta[chosen] && typeof meta[chosen] === "object" ? [chosen, meta[chosen]] : null) : newest(meta)) : null;
  const day = top ? top[0] : "", m = top ? top[1] : {};
  const urls = day ? { land: versioned(`video/${day}_land.mp4`, m.made_at), port: versioned(`video/${day}_port.mp4`, m.made_at),
    lp: versioned(`video/${day}_land.jpg`, m.made_at), pp: versioned(`video/${day}_port.jpg`, m.made_at) } : null;
  // Once a day, the first time the app opens after the new video is out (switch it off in ⚙️ Settings).
  useEffect(() => {
    if (!day || chosen || navigator.webdriver) return;
    const settings = (account && account.settings) || {};
    if (settings.daily_video_auto === false) return;
    let seen = ""; try { seen = localStorage.getItem("mn_dv_seen") || ""; } catch (e) { /* private window */ }
    if (seen === day || settings.daily_video_seen === day) return;
    setPop(true);
    try { localStorage.setItem("mn_dv_seen", day); } catch (e) { /* private window */ }
    saveSettings({ daily_video_seen: day }).catch(() => {});
  }, [day]);
  const tip = T("Today's markets in about two minutes, presented by the crew. It plays when you first open the app each day; switch that off in ⚙️ Settings. A summary of the app's readings, not advice.");
  return (
    <section className="media">
      <div className="mhead" title={tip}><b><Icon n="clapperboard" /> {T("Daily video")}</b>{day && <span className="m">{T("{day} · {who} · {length}", { day: weekday(day), who: T(String(m.presenter || "")), length: clock(m.seconds) })}</span>}</div>
      {meta === undefined ? <div className="empty" style={{ aspectRatio: "16/9" }}>{T("Loading…")}</div>
        : !urls ? <p className="sub">{chosen ? T("None for this day.") : T("The first video is on its way.")}</p> : (
          <>
            <div className="dv">
              <video className="land" controls playsInline preload="none" poster={urls.lp}><source src={urls.land} type="video/mp4" /></video>
              <video className="port" controls playsInline preload="none" poster={urls.pp}><source src={urls.port} type="video/mp4" /></video>
            </div>
            <ReadIt text={text} load={() => fresh(`video/${day}.txt`).then((r) => (r.ok ? r.text() : "")).then(setText).catch(() => setText(""))} />
          </>
        )}
      {pop && urls && <VideoPop urls={urls} onClose={() => setPop(false)} />}
    </section>
  );
}

function VideoPop({ urls, onClose }) {
  const v = useRef(null);
  const phone = window.matchMedia("(max-width: 640px)").matches;
  useEffect(() => {
    const k = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    const el = v.current; if (el) el.play().catch(() => { /* the browser wants a tap first: the controls are there */ });
    return () => window.removeEventListener("keydown", k);
  }, []);
  return (
    <div className="dvpop" role="dialog" aria-modal="true" aria-label={T("Daily video")} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dvbox">
        <button type="button" className="ghost icon dvclose" onClick={onClose} aria-label={T("Close")}><Icon n="x" /></button>
        <video ref={v} controls playsInline autoPlay poster={phone ? urls.pp : urls.lp} onEnded={onClose}><source src={phone ? urls.port : urls.land} type="video/mp4" /></video>
      </div>
    </div>
  );
}

function ReadIt({ text, load }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={"readit" + (open ? " open" : "")}>
      <button type="button" className="linkish" aria-expanded={open} onClick={() => { if (!open && text == null) load(); setOpen(!open); }}><Icon n="scroll-text" size={16} /> {T("Read it")} <Icon n={open ? "chevron-up" : "chevron-down"} size={14} /></button>
      {open && <div className="readtext">{text == null ? T("Loading…") : text || T("Not available.")}</div>}
    </div>
  );
}

// ---- 🌍 the Morning Outlook and 🧭 your Passage Plan --------------------------------------------------------------

const EDITION = () => ({ east: T("Asia & Europe edition"), west: T("Americas edition") });

export function Outlook({ day: chosen }) {
  const [meta, setMeta] = useState(undefined);
  const [text, setText] = useState(null);
  const [edition, setEdition] = useState(null);
  useEffect(() => { fresh("general/episodes.json").then((r) => (r.ok ? r.json() : {})).then(setMeta).catch(() => setMeta({})); }, []);
  useEffect(() => { setText(null); setEdition(null); }, [chosen]);
  const ofDay = chosen && meta ? Object.entries(meta).filter(([k, m]) => m && typeof m === "object" && k.slice(0, 10) === chosen)
    .sort((a, b) => String(b[1].made_at || "").localeCompare(String(a[1].made_at || ""))) : [];
  const top = meta ? (chosen ? (ofDay.find(([k]) => k === edition) || ofDay[0] || null) : newest(meta)) : null;
  const tip = T("The same for everyone, twice a day: the Asia & Europe edition just after the US close, and the Americas edition before the New York morning. You always get the newest, which is the one made for your morning. The main markets, the top five coins, the Tide and the week's events. A summary of the app's readings, not advice.");
  return (
    <section className="media">
      <div className="mhead" title={tip}><b><Icon n="globe" /> {T("Morning Outlook")}</b>
        {top && <span className="m">{T("{day} · {edition} · {length}", { day: weekday(top[0].slice(0, 10)), edition: EDITION()[top[0].slice(11)] || "", length: clock(top[1].seconds) })}</span>}</div>
      {meta === undefined ? <p className="sub">{T("Loading…")}</p> : !top ? <p className="sub">{chosen ? T("None for this day.") : T("The first edition is on its way.")}</p> : (
        <>
          {ofDay.length > 1 && <div className="seg" style={{ marginBottom: 8, width: "fit-content" }}>{ofDay.map(([k]) => <button key={k} type="button" className={top[0] === k ? "on" : ""} onClick={() => { setEdition(k); setText(null); }}>{EDITION()[k.slice(11)] || k.slice(11)}</button>)}</div>}
          <audio key={top[0]} controls preload="none" src={versioned(`general/${top[0]}.mp3`, top[1].made_at)} />
          <ReadIt text={text} load={() => fresh(`general/${top[0]}.txt`).then((r) => (r.ok ? r.text() : "")).then(setText).catch(() => setText(""))} />
        </>
      )}
    </section>
  );
}

export function Passage({ account, day: chosen, written }) {
  const pro = ["pro", "elite"].includes(account && account.plan);
  const b = ((account && account.settings) || {}).briefing || {};
  const [meta, setMeta] = useState(undefined);
  const [text, setText] = useState(null);
  useEffect(() => { if (pro && b.token) fresh(`${b.token}/episodes.json`).then((r) => (r.ok ? r.json() : {})).then(setMeta).catch(() => setMeta({})); else setMeta({}); }, []);
  useEffect(() => { setText(null); }, [chosen]);
  const top = meta ? (chosen ? (Object.entries(meta).filter(([k, m]) => m && typeof m === "object" && k.slice(0, 10) === chosen)
    .sort((a, b) => String(b[1].made_at || "").localeCompare(String(a[1].made_at || "")))[0] || null) : newest(meta)) : null;
  const tip = T("Today's AI Passage Plan for your own watchlist and funnels, read aloud: the same plan you can read in the 📓 Logbook. It is ready each day an hour before your daily summary's time; set the time, time zone and voice in 🔔 Notifications.");
  return (
    <section className="media">
      <div className="mhead" title={tip}><b><Icon n="compass" /> {T("Your Passage Plan")}</b>
        {top && <span className="m">{T("{day} · {length}", { day: weekday(top[0].slice(0, 10)), length: clock(top[1].seconds) })}</span>}</div>
      {!pro ? <p className="sub">{T("Written and spoken for your own watchlist and funnels each morning. Comes with Pro.")}</p>
        : meta === undefined ? <p className="sub">{T("Loading…")}</p>
        : !top && !written ? <p className="sub">{chosen ? T("None for this day.") : T("Not made yet today. It is made ready each morning.")}</p> : (
          <>
            {top && <audio key={top[0]} controls preload="none" src={versioned(`${b.token}/${top[0]}.mp3`, top[1].made_at)} />}
            {written ? <div className="plantext">{written}</div>
              : <ReadIt text={text} load={() => fresh(`${b.token}/${top[0]}.txt`).then((r) => (r.ok ? r.text() : "")).then(setText).catch(() => setText(""))} />}
          </>
        )}
    </section>
  );
}

// ---- 🌊 Tides ---------------------------------------------------------------------------------------------------------

function Tides({ card }) {
  if (!card) return <section className="tidecard"><div className="kick"><Icon n="waves-horizontal" size={16} /> {T("Tides")}</div><p className="sub">{T("Tides has not got enough data yet.")}</p></section>;
  const arrow = { in: "↗", out: "↘" }[card.label] || "↔";
  const tip = T("🌊 Tides: the macro picture (money and rates, safe havens, growth and credit, rotation), what it means for crypto and equity longs, and the next scheduled event. Click to open the Tides panel. A description, not a forecast.");
  return (
    <a className={"tidecard " + card.label} href="#tides" title={tip}>
      <div className="kick"><Icon n="waves-horizontal" size={16} /> {T("Tides")}</div>
      <div className="tidehead"><span className="tarrow"><Arrow a={arrow} size={26} /></span><div><div className="tname">{plain(card.name)}</div><div className="m">{card.plain}{card.held ? ` · ${card.held}` : ""}</div></div></div>
      {card.tiles.length > 0 && <div className="ttiles">{card.tiles.map((x) => <div key={x.k}><div className="m"><Lead text={x.k} size={14} /></div><b>{x.v}</b><div className="m">{x.sub}</div></div>)}</div>}
      {card.winds.map((w) => <div key={w.name} className="twind"><Emo e={w.icon} /> {plain(w.name)}: <b className={w.wind === "tailwind" ? "good" : w.wind === "headwind" ? "bad" : ""}>{w.word}</b>{w.drivers && <span className="m"> · {w.drivers}</span>}</div>)}
      {card.event && <div className="tevent"><span><Emo e={card.event.icon} /></span><span><b>{plain(card.event.name)}</b><span className="m"> · {card.event.when}</span></span></div>}
      <div className="topen">{T("Open Tides ›")}</div>
    </a>
  );
}

// ---- what changed since your last visit ------------------------------------------------------------------------------

function Changes({ c }) {
  if (!c) return null;
  return (
    <section className="card">
      <h2>{T("What changed")}</h2>
      {!c.seen ? <p className="sub">{T("Changes show here from your next visit.")}</p> : (
        <>
          {!c.crossings.length && <p className="sub">{T("No Trend reading crossed a colour border you alert on since your last visit.")}</p>}
          <div className="changes">{c.crossings.map((x) => <Change key={x.pick} x={x} />)}</div>
          {c.moves.length > 0 && <><div className="rowtitle" style={{ marginTop: 18 }}>{T("Largest moves")}</div><div className="changes">{c.moves.map((x) => <Change key={x.pick} x={x} />)}</div></>}
        </>
      )}
    </section>
  );
}

function Spark({ values, width = 84, height = 24, invert }) {
  const pts = (values || []).filter((v) => v != null && isFinite(v));
  if (pts.length < 2) return null;
  const lo = Math.min(...pts), hi = Math.max(...pts), span = hi - lo || 1, last = pts.length - 1;
  const path = pts.map((v, i) => `${(2 + (width - 4) * i / last).toFixed(1)},${(2 + (height - 4) * (1 - (v - lo) / span)).toFixed(1)}`).join(" ");
  const up = pts[last] >= pts[0];
  return <svg className="spark" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true"><polyline fill="none" stroke={up !== !!invert ? "var(--good)" : "var(--bad)"} strokeWidth="1.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" points={path} /></svg>;
}

function Change({ x }) {
  const days = x.next_earnings ? Math.round((new Date(x.next_earnings + "T00:00:00Z") - new Date(new Date().toISOString().slice(0, 10) + "T00:00:00Z")) / 864e5) : null;
  const near = !x.crossed && x.now > 0 && 20 - x.now > 0 && 20 - x.now <= 5 ? [20 - x.now, "+20"] : !x.crossed && x.now < 0 && x.now + 20 > 0 && x.now + 20 <= 5 ? [x.now + 20, "−20"] : null;
  const sym = { symbol: x.symbol };
  return (
    <a className="change" href={assetHref(x.pick, "chart")}>
      <div className="cname"><Logo a={sym} src={x.logo} size={24} /><div><b className={x.delta > 0 ? "good" : x.delta < 0 ? "bad" : ""}>{x.title}</b><div className="m">{x.detail}</div></div></div>
      <div className="cctx">
        <span className="rpair" title={T("📈 Trend reading at your last visit, and now (-100 to +100)")}><span className={"rv " + rtone(x.was)}>{signed(x.was)}</span><span className="m">→</span><span className={"rv " + rtone(x.now)}>{signed(x.now)}</span></span>
        {x.price != null && <span className="cprice">{usd(x.price)} {x.change_1d != null && <span className={x.change_1d > 0.05 ? "good" : x.change_1d < -0.05 ? "bad" : "m"} title={T("Change since the previous daily close")}>{x.change_1d > 0.05 ? "▲" : x.change_1d < -0.05 ? "▼" : ""} {Math.abs(x.change_1d).toFixed(1)}%</span>}</span>}
        <span title={T("Price over the last 7 days")}><Spark values={x.closes} width={64} height={20} /></span>
        {days != null && days >= 0 && days <= 14 && <span className="tag" title={T("Earnings report {when} ({date})", { when: days === 0 ? T("today") : days === 1 ? T("tomorrow") : T("in {n} days", { n: days }), date: x.next_earnings })}><Icon n="calendar" size={14} /> {days === 0 ? T("today") : days === 1 ? T("tomorrow") : T("in {n} days", { n: days })}</span>}
        {x.mood != null && <span className={"tag " + rtone(x.mood)} title={T("Headline sentiment for this asset, -100 to +100")}><Icon n="newspaper" size={14} /> {signed(x.mood)}</span>}
        {near && <span className="tag" title={T("{gap} points from your Trend alert line ({line})", { gap: near[0].toFixed(1), line: near[1] })}><Icon n="target" size={14} /> {T("{gap} to {line}", { gap: Math.round(near[0]), line: near[1] })}</span>}
      </div>
    </a>
  );
}

// ---- the market moods ---------------------------------------------------------------------------------------------------

function Mood({ m }) {
  const c = m.crowd || {};
  return (
    <a className="card mood moodlink" href={`#mood/${m.key}`} title={T("Open {label} sentiment", { label: m.label })}>
      <div className="rowtitle"><Lead text={m.label} /></div>
      <div className="moodrow">
        <div className="moodfig"><div className={"big-num " + rtone(m.score)}>{m.score == null ? "—" : signed(m.score)}</div><div className={"m " + rtone(m.score)}>{m.score == null ? T("Not scored yet") : m.coverage}</div></div>
        {m.summary && <p className="moodtext">{m.summary}</p>}
      </div>
      {(c.up || c.down || c.alt_count) ? <div className="m" style={{ marginTop: 8 }} title={T("Members who agree and disagree with this reading")}><Icon n="thumbs-up" size={14} /> {c.up || 0} · <Icon n="thumbs-down" size={14} /> {c.down || 0}{c.alt_count ? ` · ${T("members' own score {s} ({n})", { s: signed(c.alt_avg), n: c.alt_count })}` : ""}</div> : null}
    </a>
  );
}

// ---- highest and lowest Trend --------------------------------------------------------------------------------------------

function Extremes({ x, trade }) {
  const cards = [["crypto", "coins", T("Crypto · highest and lowest Trend in your watchlist")], ["equity", "landmark", T("Equities · highest and lowest Trend in your watchlist")]]
    .filter(([k]) => trade && trade[k]);
  if (!cards.length) return null;
  const row = (icon, word, r) => !r ? null : (
    <a className="xrow" href={assetHref(r.pick, "chart")} title={T("Open {name} on the chart", { name: r.symbol })}>
      <span><Icon n={icon} size={16} /></span><span className="m xw">{word}</span><Logo a={{ symbol: r.symbol }} src={r.logo} size={22} /><b className="xn">{r.symbol}</b>
      <span className={"rv " + rtone(r.trend)} title={T("Trend reading, -100 to +100: where price sits against its longer averages. A description, not a forecast.")}>{r.trend >= 0 ? "▲" : "▼"} Trend {signed(r.trend)}</span>
    </a>
  );
  return (
    <div className="snapgrid">
      {cards.map(([k, ic, title]) => (
        <section key={k} className="card">
          <div className="rowtitle"><Icon n={ic} size={16} /> {title}</div>
          {!x[k] ? <p className="sub">{T("No readings yet: add assets to your watchlist in ⚙️ Settings.")}</p> : <>{row("trending-up", T("Highest"), x[k].top)}{row("trending-down", T("Lowest"), x[k].bottom)}</>}
        </section>
      ))}
    </div>
  );
}

// ---- 🔻 your funnels ----------------------------------------------------------------------------------------------------

function Funnels({ tiles }) {
  const [open, setOpen] = useState(null);
  if (!tiles) return null;
  const MARK = { crypto: <><Icon n="coins" size={14} /> {T("Crypto")}</>, equity: <><Icon n="landmark" size={14} /> {T("Equities")}</> };
  const DIR = { long: T("longs"), short: T("shorts") };
  return (
    <section className="card">
      <h2><Icon n="funnel" /> {T("🔻 Your funnels")}</h2>
      {!tiles.length ? <p className="sub">{T("None yet: a funnel narrows the market down in stages by itself, to a short list of Candidates.")} <a className="linkish" href={CLASSIC}>{T("Make one in the classic app ›")}</a></p> : (
        <div className="ftiles">
          {tiles.map((f) => (
            <div key={f.id} className="ftile">
              <div className="m">{MARK[f.market] || f.market} · {DIR[f.direction] || f.direction}{f.paused ? <> · <Icon n="pause" size={14} /> {T("paused")}</> : ""}</div>
              <div className="fname">{f.name}</div>
              <div className="fnums">
                <button type="button" className="linkish" onClick={() => setOpen(open === f.id ? null : f.id)} aria-expanded={open === f.id} title={f.candidate_names.length ? T("Candidates now: {names}.", { names: f.candidate_names.join(", ") }) : T("No Candidates right now.")}>
                  <Icon n="circle-check" size={16} /> <b>{f.candidates}</b> {T("Candidates")}</button>
                <span><Icon n="flag" size={16} /> <b>{f.flagged}</b> <span className="m">{T("Flagged")}</span></span>
                {f.new.length > 0 && <span className="good" title={T("New Candidates since your last visit: {names}", { names: f.new.join(", ") })}>＋{T("{n} new", { n: f.new.length })}</span>}
                {f.gone.length > 0 && <span className="m" title={T("No longer Candidates since your last visit: {names}", { names: f.gone.join(", ") })}>－{T("{n} left", { n: f.gone.length })}</span>}
                {!f.new.length && !f.gone.length && f.seen && <span className="m">{T("no change")}</span>}
              </div>
              <div className="m" style={{ marginTop: 6 }}><Glyphs text={f.line} size={14} /></div>
              {open === f.id && f.candidate_keys.length > 0 && <div className="fcands">{f.candidate_keys.map((k, i) => <a key={k} className="tag" href={assetHref(k, "chart")}>{f.candidate_names[i]}</a>)}</div>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ---- 🌍 the markets strip ------------------------------------------------------------------------------------------------

function Markets({ m }) {
  if (!m || !m.cards || !m.cards.length) return null;
  return (
    <section className="card">
      <h2><Icon n="globe" /> {T("Markets")}</h2>
      <p className="sub">{T("Hover a card for what it measures. Shared for everyone and refreshed about every 15 minutes. Stock prices can be delayed about 15 minutes; gold and oil are futures prices.")}</p>
      <div className="mkt">
        {m.groups.map(([g, heading]) => {
          const cards = m.cards.filter((c) => c.group === g);
          if (!cards.length) return null;
          return (
            <div key={g} className="mktg" style={{ flex: `${cards.length} 1 ${cards.length * 150}px` }}>
              <div className="rowtitle"><Lead text={heading} /></div>
              <div className="mktcards">
                {cards.map((c) => (
                  <div key={c.key} className="mktc" title={c.hint}>
                    <div className="m mktl">{c.open != null && <i className={"dot" + (c.open ? " on" : "")} title={c.place_state} />}{c.label}</div>
                    <div className="mktv"><b>{c.value}</b>{c.change && <span className={c.tone === "up" ? "good" : c.tone === "down" ? "bad" : "m"}>{c.rising == null ? "" : c.rising ? "▲ " : "▼ "}{c.change.replace(/^[+-]/, c.rising == null ? "$&" : "")}</span>}</div>
                    {c.word && <div className="m">{c.word}</div>}
                    <Spark values={c.spark} invert={c.invert} />
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
