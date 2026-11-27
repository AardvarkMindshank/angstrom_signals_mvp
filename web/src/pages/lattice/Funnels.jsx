import React, { useCallback, useEffect, useRef, useState } from "react";
import { T, lang } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import ClassicComponent from "../../components/ClassicComponent.jsx";
import Icon from "../../components/Icon.jsx";
import funnelStages, { css as funnelCss } from "../../generated/funnel_stages.js";

// 🔻 Funnels: start from a provided funnel (read-only; make your own copy) or one of your own → change it → save and
// activate. The browser keeps the working copy (and, in this browser, unsaved changes between visits); the data
// service applies each change, checks it and says what saving will reset (service/funnels_page.py).
const draftKey = (id) => `mn_funnel_draft_${id}`;
const readDraft = (id) => { try { return JSON.parse(window.localStorage.getItem(draftKey(id)) || "null"); } catch (e) { return null; } };
const writeDraft = (id, f) => { try { if (f) window.localStorage.setItem(draftKey(id), JSON.stringify({ f, at: Date.now() })); else window.localStorage.removeItem(draftKey(id)); } catch (e) { /* private window */ } };
const NOTE = () => T("Candidate means an asset matches your selected conditions. It is not a recommendation to trade.");

export default function Funnels() {
  const [list, setList] = useState(null);
  const [pick, setPick] = useState("");
  const [err, setErr] = useState("");
  const load = useCallback(async (want) => {
    try {
      const l = await call(`/funnels/list?lang=${lang}`);
      setList(l);
      const keys = [...l.own.map((x) => x.key), ...l.provided.map((x) => x.key)];
      setPick((p) => (want && keys.includes(want) ? want : keys.includes(p) ? p : keys[0]));
    } catch (e) { setErr(T("Funnels aren't reachable just now. Please try again in a minute.")); }
  }, []);
  useEffect(() => { load(); }, [load]);
  if (err) return <p className="note bad" style={{ marginTop: 16 }}>{err}</p>;
  if (!list) return <div className="empty" style={{ height: 300, marginTop: 16 }}>{T("Loading…")}</div>;
  const mine = list.own.find((x) => x.key === pick);
  return (
    <div className="funp">
      <p className="sub">{T("🔻 A funnel narrows the top coins or equities down in stages, from the longest timeframe to the hour, and keeps the list up to date by itself. It shows as **Dynamic funnel** above the crypto and equity tables.").replace(/\*\*/g, "")} {NOTE()}</p>
      <div className="latstart">
        <label className="m" htmlFor="fun-pick">{T("Funnel")}</label>
        <select id="fun-pick" value={pick} onChange={(e) => setPick(e.target.value)}
          title={T("Your own funnels first, then the provided ones (marked provided). As with provided Groups and Sets, a provided funnel can't be changed or deleted: make your own copy to use it.")}>
          {list.own.map((x) => <option key={x.key} value={x.key}>{x.name}{x.paused ? ` (${T("paused")})` : ""}</option>)}
          {list.provided.map((x) => <option key={x.key} value={x.key}>{x.name} ({T("provided")})</option>)}
        </select>
      </div>
      {mine ? <Editor key={pick} id={pick} count={list.own.length} limit={list.limit} onSaved={(id) => load(id)} onDeleted={() => load()} />
        : <Provided key={pick} kind={pick.split(":")[1] || "trend"} list={list} onMade={(id) => load(id)} />}
    </div>
  );
}

function Seg({ value, options, onChange, label }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={value === k} className={value === k ? "on" : ""} onClick={() => onChange(k)}>{l}</button>)}
    </div>
  );
}
const DIRS = () => [["long", <><Icon n="trending-up" size={15} /> {T("Long")}</>], ["short", <><Icon n="trending-down" size={15} /> {T("Short")}</>]];

// A provided funnel, as a provided Group or Set is shown: choose the market and direction, see it, make your own copy.
function Provided({ kind, list, onMade }) {
  const [market, setMarket] = useState("crypto");
  const [dir, setDir] = useState("long");
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setD(null);
    call("/funnels/provided", { method: "POST", body: { kind, market, direction: dir, lang } }).then(setD).catch(() => setMsg(["error", T("That didn't work just now. Please try again.")]));
  }, [kind, market, dir]);
  const make = async () => {
    setBusy(true);
    try {
      const r = await call("/funnels/save", { method: "POST", body: { funnel: d.funnel, lang } });
      setMsg([r.status, r.message]);
      if (r.status === "ok") onMade(r.id);
    } catch (e) { setMsg(["error", T("That didn't work just now. Please try again.")]); }
    setBusy(false);
  };
  return (
    <>
      <div className="funrow">
        <Seg label={T("Market")} value={market} onChange={setMarket} options={[["crypto", <><Icon n="coins" size={15} /> {T("Crypto")}</>], ["equity", <><Icon n="landmark" size={15} /> {T("Equities")}</>]]} />
        <Seg label={T("Direction")} value={dir} onChange={setDir} options={DIRS()} />
      </div>
      {!d ? <div className="empty" style={{ height: 280 }}>{T("Loading…")}</div> : (
        <>
          {d.about && <p className="sub">{d.about}</p>}
          <p className="m"><b>{market === "crypto" ? T("Crypto") : T("Equities")}</b> · {dir === "long" ? T("Long") : T("Short")} · <i>{T("Provided by MarketNavi")}</i> · {T("can't be changed or deleted")}</p>
          <p className="sub">{d.leave}</p>
          <ClassicComponent fn={funnelStages} css={funnelCss} data={d.board} onTrigger={() => {}} className="funboard" />
          <p className="sub">{NOTE()}</p>
          {d.copy && <p className="m">{T("You already have an unchanged copy: {name}.", { name: d.copy })}</p>}
          {d.limit === 0 ? <p className="m">{T("You can watch this funnel's Candidates and Flagged assets. Making your own funnel starts on Plus.")}</p>
            : d.count >= d.limit ? <p className="m">{T("Your plan includes {n} funnels of your own.", { n: d.limit })}</p> : null}
          {(d.limit > 0 || d.display !== "hide") && (
            <button type="button" className="primary" disabled={busy || d.count >= d.limit} onClick={make}
              title={T("Your copy runs for your account, with its own places and alerts. You can then change it, pause it or delete it; this provided one stays as it is.")}>
              <Icon n="copy" size={16} /> {T("Make my own copy")}</button>
          )}
        </>
      )}
      {msg && <p className={"note " + (msg[0] === "ok" ? "good" : "bad")}>{msg[1]}</p>}
    </>
  );
}

// Your own funnel: the working copy, changed here and on the stages board, saved when you choose.
function Editor({ id, count, limit, onSaved, onDeleted }) {
  const [saved, setSaved] = useState(null);
  const [f, setF] = useState(null);
  const [sc, setSc] = useState(null);
  const [restored, setRestored] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sure, setSure] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    call("/funnels/open", { method: "POST", body: { key: id, lang } }).then((r) => {
      if (r.status !== "ok") { setMsg(["error", r.message]); return; }
      setSaved(r.saved);
      const kept = readDraft(id);
      if (kept && kept.f && kept.f.stages) { setF(kept.f); setRestored(kept.at); } else setF(r.funnel);
    }).catch(() => setMsg(["error", T("Funnels aren't reachable just now. Please try again in a minute.")]));
  }, [id]);

  useEffect(() => {                                         // check the working copy after each change
    if (!f || !saved) return;
    const n = ++seq.current;
    const timer = setTimeout(() => {
      call("/funnels/screen", { method: "POST", body: { funnel: f, saved, scope: id, lang } })
        .then((s) => { if (n === seq.current) setSc(s); }).catch(() => {});
    }, 250);
    writeDraft(id, JSON.stringify(f) === JSON.stringify({ ...saved, pool: saved.pool || {} }) ? null : f);
    return () => clearTimeout(timer);
  }, [f, saved]);

  const apply = async (action) => {
    setMsg(null);
    try {
      const r = await call("/funnels/apply", { method: "POST", body: { funnel: f, action, lang } });
      if (r.goto) { window.location.hash = r.goto.slice(1); return; }
      if (r.problem) setMsg(["error", r.problem]);
      setF(r.funnel);
    } catch (e) { setMsg(["error", T("That didn't work just now. Please try again.")]); }
  };
  const onTrigger = (name, value) => { if (name === "action") { try { apply(JSON.parse(value)); } catch (e) { /* not JSON */ } } };
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const alerts = (f && f.alerts) || { in_app: true, email: false };
  const setAlert = (k, v) => set("alerts", (() => { const a = { ...alerts, [k]: v }; if (!a.first_matches) delete a.first_matches; return a; })());
  const save = async (which) => {
    setBusy(true); setMsg(null);
    try {
      const body = which === "copy" ? { ...saved, id: null, name: `${saved.name} (copy)`.slice(0, 80) } : f;
      const r = await call("/funnels/save", { method: "POST", body: { funnel: body, lang } });
      setMsg([r.status, r.message]);
      if (r.status === "ok") { if (which !== "copy") writeDraft(id, null); onSaved(r.id); }
    } catch (e) { setMsg(["error", T("That didn't work just now. Please try again.")]); }
    setBusy(false);
  };
  const del = async () => {
    setBusy(true);
    try {
      const r = await call("/funnels/delete", { method: "POST", body: { id, lang } });
      if (r.status === "ok") { writeDraft(id, null); onDeleted(); } else setMsg(["error", r.message]);
    } catch (e) { setMsg(["error", T("That didn't work just now. Please try again.")]); }
    setBusy(false);
  };

  if (!f) return msg ? <p className="note bad">{msg[1]}</p> : <div className="empty" style={{ height: 300 }}>{T("Loading…")}</div>;
  const market = f.market || "crypto";
  return (
    <>
      {restored && (
        <p className="note"><Icon n="clock-arrow-up" size={15} /> {T("Your unsaved changes from {when} are back.", { when: new Date(restored).toLocaleString() })} {T("Save to use them, or Discard changes to go back to the saved funnel.")}</p>
      )}
      {sc && (
        <p className="m"><b>{market === "crypto" ? T("Crypto") : T("Equities")}</b> · {f.direction === "long" ? T("Long") : T("Short")} · <i>{sc.badge}</i>{sc.reviewed ? "" : T(" · not reviewed or tested by MarketNavi")}</p>
      )}
      {sc && sc.earlier && (
        <button type="button" className="ghost bordered" onClick={() => apply({ op: "latest" })}
          title={T("MarketNavi's provided funnel has changed since you made your copy (its daily stage reads WaveTrend turning back from an extreme; crypto funnels now start with a wider daily-trend stage). This takes its stages; your name, pool and alerts stay. Then Save and activate: every asset starts again from the pool, quietly.")}>
          <Icon n="arrow-up-right" size={16} /> {T("⬆ Update to the latest provided version")}</button>
      )}
      <div className="fungrid">
        <label className="funfield"><span className="m">{T("Name")}</span>
          <input type="text" maxLength={80} value={f.name} onChange={(e) => set("name", e.target.value)} /></label>
        <div className="funfield"><span className="m" title={T("For every stage: provided Sets switch to their long or short version with it.")}>{T("Direction")}</span>
          <Seg label={T("Direction")} value={f.direction} onChange={(v) => v !== f.direction && apply({ op: "direction", direction: v })} options={DIRS()} /></div>
        <div className="funfield"><span className="m" title={T("Two in a row stops coins flickering in and out near a threshold (recommended).")}>{sc ? sc.leave_words : ""}</span>
          <Seg label={sc ? sc.leave_words : ""} value={f.flicker === false ? "one" : "two"} onChange={(v) => set("flicker", v === "two")}
            options={[["two", T("after 2 No closes in a row")], ["one", T("on the first No")]]} /></div>
        <div className="funfield">
          <label className="ptog" title={T("One message per hourly run, only for new Candidates.")}><input type="checkbox" checked={alerts.in_app !== false} onChange={(e) => setAlert("in_app", e.target.checked)} /> <span>{T("Alert me on new Candidates")}</span></label>
          <label className="ptog" title={T("Off (recommended): a new or changed funnel starts quietly, without alerts for everything that already qualifies.")}><input type="checkbox" checked={!!alerts.first_matches} onChange={(e) => setAlert("first_matches", e.target.checked)} /> <span>{T("…including the first run")}</span></label>
        </div>
      </div>
      {f.paused && <p className="m">{T("⏸ Paused: not checked until resumed on the Dynamic funnel page.")}</p>}
      <p className="sub">{T("Each stage checks one Set, only for the assets that hold every stage before it. The timeframe is **when the stage is checked**; the Set's readings keep their own timeframes. To change a threshold, edit a copy of the Set in Signal Sets, then pick it here.").replace(/\*\*/g, "")}</p>
      {msg && msg[0] !== "ok" && <p className="note bad">{msg[1]}</p>}
      {sc ? <ClassicComponent fn={funnelStages} css={funnelCss} data={sc.board} onTrigger={onTrigger} className="funboard" /> : <div className="empty" style={{ height: 320 }}>{T("Loading…")}</div>}
      {sc && (
        <div className="funchecks">
          {sc.blocks.map((b, i) => <p key={"b" + i} className="note bad">{b}</p>)}
          {sc.warnings.map((w, i) => <p key={"w" + i} className="note warn">{w}</p>)}
          {sc.unchanged ? <p className="m">{T("No changes.")}</p>
            : <p className="m"><b>{T("If you save:")}</b> {sc.changes.join(" ")}{sc.reset ? T(" Every asset starts again from the pool, quietly (no alerts for what already qualifies).") : ""}</p>}
        </div>
      )}
      <div className="latacts">
        <button type="button" className="primary" disabled={busy || !sc || sc.blocks.length > 0 || sc.unchanged} onClick={() => save("this")}><Icon n="save" size={16} /> {T("Save and activate")}</button>
        <button type="button" className="ghost bordered" disabled={busy || !sc || sc.unchanged} onClick={() => { writeDraft(id, null); setRestored(null); setF({ ...saved, pool: saved.pool || {} }); }}
          title={T("Discard changes")} aria-label={T("Discard changes")}><Icon n="undo-2" /></button>
        <button type="button" className="ghost bordered" disabled={busy || count >= limit} onClick={() => save("copy")}
          title={T("A copy to experiment with; this one keeps running.")} aria-label={T("Duplicate")}><Icon n="copy" /></button>
        {!sure ? <button type="button" className="ghost bordered icondanger" onClick={() => setSure(true)} title={T("Delete")} aria-label={T("Delete")}><Icon n="trash" /></button> : (
          <div className="latpop">
            <p className="m" style={{ margin: 0 }}>{T("The funnel and its places are deleted for good.")}</p>
            <div className="bar">
              <button type="button" className="danger-btn" disabled={busy} onClick={del}>{T('Delete “{saved_name}”', { saved_name: saved.name })}</button>
              <button type="button" className="ghost" onClick={() => setSure(false)}>{T("Cancel")}</button>
            </div>
          </div>
        )}
      </div>
      {msg && msg[0] === "ok" && <p className="note good">{msg[1]}</p>}
    </>
  );
}
