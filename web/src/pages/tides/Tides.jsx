import React, { useEffect, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import { supabase } from "../../lib/supabase.js";
import { saveSettings } from "../../lib/account.js";
import { postComment } from "../../lib/assets.js";
import { signed } from "../../lib/format.js";

// 🌊 Tides: the macro picture. The sky and sea are drawn from the readings (calm to storm, the water level from the
// Tide's score); then the Navigator's factual note, your take, the storm-warnings calendar, the waves and the
// currents. The data service builds it from the snapshot the worker saves every 6 hours (service/tides_page.py).
const toStored = (shown) => Math.max(0, Math.min(100, Math.round((Number(shown) + 100) / 2)));

export default function Tides({ account }) {
  const saved = ((account && account.settings) || {}).tides_range;
  const [range, setRange] = useState(["3M", "6M", "1Y", "2Y"].includes(saved) ? saved : "1Y");
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    call(`/tides?lang=${lang}&range=${range}`).then((x) => live && setD(x))
      .catch((e) => live && setErr(e.status === 0 ? T("Tides isn't reachable just now. Please try again in a minute.") : T("Tides couldn't load just now. Please try again.")));
    return () => { live = false; };
  }, [range]);
  const pick = (r) => { setRange(r); saveSettings({ tides_range: r }).catch(() => {}); };
  if (err) return <div className="page"><h1 className="ptitle">🌊 {T("Tides")}</h1><p className="note bad">{err}</p></div>;
  if (!d) return <div className="page"><h1 className="ptitle">🌊 {T("Tides")}</h1><div className="empty" style={{ height: 300 }}>{T("Loading…")}</div></div>;
  if (!d.ready) return <div className="page"><h1 className="ptitle">🌊 {T("Tides")}</h1><p className="sub">{T("Tides has not got enough data yet.")}</p></div>;
  const h = d.hero;
  return (
    <div className="page tidesp">
      <h1 className="ptitle">🌊 {T("Tides")}</h1>
      <section className={"thero" + (h.dark ? " dark" : "")}>
        <img className="tsea" src={h.src} alt="" />
        <div className="tover">
          <div>
            <div className="tbig">{h.name}<span className="tplain">{h.plain}</span></div>
            <div className="tsub">{h.held}{h.pending ? ` · ${h.pending}` : ""} · {h.score}</div>
            {h.sea && <div className="tsub">{h.sea[0]} <span className="tplain">{h.sea[1]}</span></div>}
          </div>
          <div className="tchips">
            {h.winds.map((w) => <span key={w.name} className={"tchip " + w.wind} title={w.tip}>{w.icon} {w.name}: {w.word}</span>)}
            {h.warning && <span className="tchip warn" title={h.warning.tip}>{h.warning.flags} {T("Storm warning:")} {h.warning.short} {h.warning.when}</span>}
          </div>
        </div>
      </section>

      <div className="tnoterow">
        <section className="tnote">
          <div className="rowtitle">🧭 {T("Navigator")} · <span className="m">{T("today's note, facts only, written from the readings below")}</span></div>
          <ul>{d.note.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </section>
        <Take since={d.since} score={d.tide_score} words={d.tide_words} />
      </div>

      {d.events.length > 0 && (
        <section className="card">
          <h2>⚑ {T("Storm warnings: the macro calendar")}</h2>
          <p className="sub">{T("(two pennants: major, one: notable, square flag: extreme)")}</p>
          <div className="tevents">
            {d.events.map((e, i) => (
              <div key={i} className={"tev " + e.state} title={e.tip}>
                <div className="m">{e.flags} {e.icon}</div>
                <b>{e.name} · {e.ref}</b>
                <div className="m">{e.day} · {e.when}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="card">
        <div className="bar">
          <h2 style={{ margin: 0 }}>〰️ {T("The waves: each current's pull, and the swell they make together")}</h2>
          <div className="chips right" role="group" aria-label={T("Time range")}>
            {d.ranges.map((r) => <button key={r} type="button" className={range === r ? "on" : ""} aria-pressed={range === r} onClick={() => pick(r)}>{r}</button>)}
          </div>
        </div>
        {d.waves && <img className="twaves" src={d.waves} alt={T("Each current and the swell")} />}
        <p className="sub">{T("Above a lane's line pulls towards risk-taking, below pulls away. The swell is the Tide's score: each family's average, weighted (money and rates 30%, growth and credit 30%, safe havens 20%, rotation 20%); the grey band is slack. Dashed lines mark past releases: red Fed rate decisions, amber CPI inflation, purple jobs reports. Drawn from the readings, nothing added.")}</p>
      </section>

      <section className="card">
        <h2>🧭 {T("The currents")}</h2>
        {d.families.map((f) => (
          <div key={f.name} className="tfam">
            <div className="rowtitle">{f.icon} {f.name} <span className="m">({f.meta})</span></div>
            <div className="tcur">
              {f.cards.map((c) => c.none ? (
                <div key={c.name} className="tc mute" title={c.tip}><b>{c.icon} {c.name}</b><div className="m">{T("No data right now.")}</div></div>
              ) : (
                <div key={c.name} className={"tc" + (c.voting ? "" : " mute")} title={c.tip}>
                  <div className="tctop"><b>{c.icon} {c.name}</b><span className="num">{c.value}</span></div>
                  <div className="m">{c.band}</div>
                  <div className={c.tone}>{c.arrow} {c.dir}</div>
                  <div className="m">{c.change}{c.voting ? "" : T(" · not voting")}</div>
                  <Spark values={c.spark} good={c.positive_good} />
                </div>
              ))}
            </div>
          </div>
        ))}
        {d.side.length > 0 && (
          <div className="tfam">
            <div className="rowtitle">🔭 {T("Also on the horizon (shown, not voting)")}</div>
            <div className="tcur">{d.side.map((s) => <div key={s.name} className="tc mute" title={s.tip}><b>{s.name}</b><div className="num">{s.val}</div><div className="m">{s.meta}</div></div>)}</div>
          </div>
        )}
        <p className="sub" style={{ marginTop: 18 }}>{T("Readings from Yahoo Finance and FRED (St. Louis Fed), updated {stamp} UTC. Each current is scored against its own last 5 years; its pull is its 30-day move against the usual size of such a move. Macro conditions frame risk; they do not time trades, and a coin can rise on its own news while the tide goes out. Not advice.", { stamp: d.stamp })}</p>
      </section>
    </div>
  );
}

function Spark({ values, good }) {
  const v = (values || []).filter((x) => x != null && isFinite(x));
  if (v.length < 3) return null;
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const pts = v.map((x, i) => `${(i * 200 / (v.length - 1)).toFixed(1)},${(28 - (x - lo) / span * 26).toFixed(1)}`).join(" ");
  const ok = (v[v.length - 1] >= v[0]) === good;
  return <svg className="tspark" viewBox="0 0 200 30" preserveAspectRatio="none" aria-hidden="true"><polyline points={pts} fill="none" stroke={ok ? "var(--good)" : "var(--bad)"} strokeWidth="1.6" vectorEffect="non-scaling-stroke" /></svg>;
}

// 👍 / 👎 the Tide's current reading (on 👎 your own Tide score), and a short comment; both stay until the Tide changes.
function Take({ since, score, words }) {
  const [c, setC] = useState(null);
  const [alt, setAlt] = useState(0);
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => supabase.rpc("tides_crowd", { p_since: since }).then(({ data }) => {
    const r = (data || [])[0] || {};
    setC({ up: +r.thumbs_up || 0, down: +r.thumbs_down || 0, mine: r.my_vote == null ? null : +r.my_vote, alt_count: +r.alt_count || 0,
      alt_avg: r.alt_avg == null ? null : Math.round((+r.alt_avg - 50) * 2), my_alt: r.my_alt == null ? null : Math.round((+r.my_alt - 50) * 2) });
    if (r.my_alt != null) setAlt(Math.round((+r.my_alt - 50) * 2));
  }).catch(() => setC({ up: 0, down: 0, mine: null }));
  useEffect(() => { if (since) load(); }, [since]);
  const vote = async (v, altScore) => {
    try {
      const { data: u } = await supabase.auth.getUser();
      if (v !== 1 && v !== -1) await supabase.from("tides_votes").delete().eq("user_id", u.user.id).eq("since", since);
      else await supabase.from("tides_votes").upsert({ user_id: u.user.id, since, vote: v, alt_score: v === -1 && altScore != null ? toStored(altScore) : null }, { onConflict: "user_id,since" });
      load();
    } catch (e) { setMsg(T("That didn't save. Please try again.")); }
  };
  const comment = async (e) => {
    e.preventDefault(); if (!text.trim()) return;
    try { await postComment("Tides|macro", `${since}T00:00:00+00:00`, text, score, words); setText(""); setMsg(T("Comment posted. It shows in 💬 Social under 🌊 Tides.")); }
    catch (err) { setMsg(T("That didn't save. Please try again.")); }
  };
  return (
    <section className="ttake">
      <div className="rowtitle">👍 {T("Your take")} <span className="m">{T("on the Tide's current reading")}</span></div>
      {!c ? <p className="sub">{T("Loading…")}</p> : (
        <>
          <div className="bar">
            <button type="button" className={"ghost" + (c.mine === 1 ? " on" : "")} aria-pressed={c.mine === 1} onClick={() => vote(c.mine === 1 ? 0 : 1)}>👍 {T("Agree")} · {c.up}</button>
            <button type="button" className={"ghost" + (c.mine === -1 ? " on" : "")} aria-pressed={c.mine === -1} onClick={() => vote(c.mine === -1 ? 0 : -1, alt)}>👎 {T("Disagree")} · {c.down}</button>
          </div>
          {c.mine === -1 && (
            <div className="psub" style={{ marginTop: 10 }}>
              <span className="m">{T("Your own Tide score: −100 going out to +100 coming in")}</span>
              <div className="bar"><input type="range" min="-100" max="100" step="5" value={alt} onChange={(e) => setAlt(+e.target.value)} onMouseUp={() => vote(-1, alt)} onTouchEnd={() => vote(-1, alt)} aria-label={T("Your own Tide score")} style={{ flex: 1, accentColor: "var(--gold)" }} /><b className="num">{signed(alt)}</b></div>
            </div>
          )}
          {c.alt_count > 0 && <p className="m" style={{ margin: "8px 0 0" }}>{T("members' own score {s} ({n})", { s: signed(c.alt_avg), n: c.alt_count })}</p>}
          <form className="cform" onSubmit={comment} style={{ marginTop: 12 }}>
            <input type="text" maxLength={160} value={text} onChange={(e) => setText(e.target.value)} placeholder={T("Add a short comment…")} aria-label={T("Your comment")} />
            <button type="submit" className="primary" disabled={!text.trim()}>{T("Post")}</button>
          </form>
          {msg && <p className="m">{msg}</p>}
        </>
      )}
    </section>
  );
}
