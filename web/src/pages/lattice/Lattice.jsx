import React, { useCallback, useEffect, useRef, useState } from "react";
import Icon, { Lead, plain } from "../../components/Icon.jsx";
import { T, lang, noEmoji } from "../../lib/i18n.js";
import { call } from "../../lib/service.js";
import { supabase, CLASSIC } from "../../lib/supabase.js";
import { watchlists } from "../../lib/assets.js";
import { signed } from "../../lib/format.js";
import { preferences, saveSettings } from "../../lib/account.js";
import ClassicComponent from "../../components/ClassicComponent.jsx";
import latticeGroup, { css as groupCss } from "../../generated/lattice_group.js";
import latticeSet, { css as setCss } from "../../generated/lattice_set.js";
import Prism from "./Prism.jsx";

// 🧩 Lattice, the research workspace: Signal Groups (signals combined into one reading with labels) and Signal Sets
// (Groups and signals connected into a Yes / No decision). The editors are the classic app's own (hosted by
// ClassicComponent); every change is cleaned, checked and described by the data service (service/lattice.py), and
// saving, renaming and deleting go through the same database functions as the classic app.
const SECTIONS = [
  ["groups", "blocks", () => T("Signal Groups"), () => T("Combine signals into one reading, with labels such as Bullish.")],
  ["sets", "workflow", () => T("Signal Sets"), () => T("Connect Groups and signals into a Yes / No decision.")],
  ["prism", "scan-search", () => T("Prism Scan"), null],
  ["funnels", "funnel", () => T("Funnels"), null],
  ["soundings", "compass", () => T("Soundings"), null],
];

export default function Lattice({ section, start }) {
  const sec = SECTIONS.some((s) => s[0] === section) ? section : "groups";
  return (
    <div className="page latp">
      <h1 className="ptitle"><Icon n="puzzle" size={26} /> {T("Lattice")}</h1>
      <p className="sub">{T("Your market research workspace · preview: descriptive readings, not forecasts or advice")}</p>
      <div className="chips" role="tablist" aria-label={T("Lattice section")}>
        {SECTIONS.map(([k, icon, name, help]) => (
          <button key={k} type="button" role="tab" aria-selected={sec === k} className={sec === k ? "on" : ""} title={help ? help() : ""}
            onClick={() => { window.location.hash = `lattice/${k}`; }}><Icon n={icon} size={16} /> {name()}</button>
        ))}
      </div>
      {sec === "groups" || sec === "sets" ? <Editor key={sec + (start || "")} kind={sec === "groups" ? "group" : "set"} start={start} />
        : sec === "prism" ? <Prism />
        : <section className="card" style={{ marginTop: 16 }}><p className="sub" style={{ margin: 0 }}>{T("This part of Lattice is still in the classic app while it moves across.")} <a className="linkish" href={CLASSIC} target="_blank" rel="noreferrer">{T("Open the classic app")} ↗</a></p></section>}
    </div>
  );
}

let staticCache = null;
const groupStatic = () => (staticCache = staticCache || call(`/lattice/group/static?lang=${lang}`).catch((e) => { staticCache = null; throw e; }));

function Editor({ kind, start: first }) {
  const word = kind === "group" ? T("Group") : T("Set");
  const [sources, setSources] = useState(null);
  const [start, setStart] = useState("new");
  const [stat, setStat] = useState(null);
  const [screen, setScreen] = useState(null);
  const [source, setSource] = useState(null);
  const [search, setSearch] = useState(null);
  const [flash, setFlash] = useState(null);
  const [undo, setUndo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const seq = useRef(0);
  const model = screen && screen.model;

  const loadSources = useCallback(() => call(`/lattice/${kind}/sources?lang=${lang}`).then((d) => setSources(d.sources)).catch(() => setSources([["new", kind === "group" ? T("➕ New Group") : T("➕ New Set")]])), [kind]);
  useEffect(() => { loadSources(); groupStatic().then(setStat).catch(() => setErr(T("Lattice isn't reachable just now. Please try again in a minute."))); }, [loadSources]);

  const check = useCallback(async (m) => {
    const n = ++seq.current;
    try {
      const s = await call(`/lattice/${kind}/screen`, { method: "POST", body: { model: m, lang } });
      if (n === seq.current) setScreen(s);
    } catch (e) { if (n === seq.current) setErr(T("That change couldn't be checked just now. Please try again.")); }
  }, [kind]);

  const open = useCallback(async (key) => {
    setStart(key); setScreen(null); setSearch(null); setErr("");
    try {
      const o = await call(`/lattice/${kind}/open`, { method: "POST", body: { start: key, lang } });
      setSource(o.source || null);
      if (o.warning) setFlash(["warn", o.warning]);
      await check(o.model);
    } catch (e) { setErr(T("Lattice isn't reachable just now. Please try again in a minute.")); }
  }, [kind, check]);
  useEffect(() => { open(first || "new"); }, [open]);   // #lattice/sets/<start>: opened from Prism's Look inside

  const onTrigger = (name, value) => {
    if (name === "model") { try { check(JSON.parse(value)); } catch (e) { /* not JSON */ } }
    if (name === "search") {
      call("/lattice/set/search", { method: "POST", body: { raw: value, lang } }).then((r) => setSearch(r && Object.keys(r).length ? r : null)).catch(() => {});
    }
  };

  const data = React.useMemo(() => {
    if (!screen || !stat) return null;
    return kind === "group" ? { ...screen, catalogue: stat.catalogue, families: stat.families, role_hints: stat.role_hints, suggested_labels: stat.suggested_labels }
      : { ...screen, search, catalogue: stat.catalogue, families: stat.families };
  }, [screen, stat, search, kind]);

  const afterSave = async (id, message) => {
    setFlash(["ok", message]);
    await loadSources();
    if (id) await open(`saved:${id}`);
  };
  const save = async (next) => {
    setBusy(true); setFlash(null);
    try {
      const r = await call(`/lattice/${kind}/save`, { method: "POST", body: { model, lang, source_id: next ? source.id : null, expected_version: next ? source.current_version : null } });
      if (r.ok) await afterSave(r.id, r.message); else setFlash(["warn", r.message]);
    } catch (e) { setFlash(["warn", T("That didn't save. Please try again.")]); }
    setBusy(false);
  };
  const mine = !!source;   // only your own Groups and Sets open with a source
  const checks = (screen && screen.checks) || { blocks: [], warnings: [] };
  const fresh = (key) => { setUndo(null); open(key); };

  return (
    <>
      {undo && (
        <div className="note latundo">
          <span><Icon n="trash" size={16} /> {T("Deleted {name}.", { name: undo.name })}</span>
          <button type="button" className="ghost" onClick={async () => {
            const { error } = await supabase.rpc("analysis_restore_config", { cfg: undo.id });
            if (error) setFlash(["warn", T("Could not undo: {why}", { why: error.message || "" })]);
            else { setUndo(null); await afterSave(undo.id, T("{name} is back.", { name: undo.name })); }
          }}><Icon n="undo-2" size={16} /> {T("Undo")}</button>
        </div>
      )}
      <div className="latstart">
        <label className="m" htmlFor={`lat-start-${kind}`}>{T("Start from")}</label>
        <select id={`lat-start-${kind}`} value={start} onChange={(e) => fresh(e.target.value)} disabled={!sources}>
          {(sources || [["new", "…"]]).map(([k, v]) => <option key={k} value={k}>{noEmoji(v)}</option>)}
        </select>
      </div>
      <p className="sub">{kind === "group"
        ? T("Drag signals in, or tap + on a tablet. Rules give the Group labels such as Bullish; the checks below say what blocks saving and what is only a warning.")
        : T("Combine saved Groups and single signals, then say when the Set answers Yes. A Group goes in exactly as saved; save a Group with labels in Signal Groups first to test its label here.")}</p>
      {err && <p className="note bad">{err}</p>}
      {!data ? <div className="empty" style={{ height: 360 }}>{T("Loading…")}</div>
        : <ClassicComponent fn={kind === "group" ? latticeGroup : latticeSet} css={kind === "group" ? groupCss : setCss} data={data} onTrigger={onTrigger} className="latedit" />}

      {screen && (
        <div className="latgrid">
          <section className="card">
            <h2>{T("Checks")}</h2>
            {checks.blocks.map((b, i) => <p key={"b" + i} className="note bad">{T("Can't save: {b}", { b })}</p>)}
            {checks.warnings.map((w, i) => <p key={"w" + i} className="note warn">{plain(w)}</p>)}
            {!checks.blocks.length && !checks.warnings.length && <p className="note good">{T("No problems found.")}</p>}
          </section>
          <section className="card">
            <h2>{kind === "group" ? T("What this Group returns") : T("What this Set returns")}</h2>
            {kind === "group" ? (
              <ul className="latret">
                <li><b>{T("Score")}</b>: {screen.returns && screen.returns.score ? T("an average from −100 to +100 (a number).") : T("none (no Score members).")}</li>
                <li><b>{T("Label")}</b>: {T("{labels}, or Unknown if a rule can't be checked.", { labels: ((screen.returns && screen.returns.labels) || []).join(", ") })}</li>
                <li><b>{T("Completeness")}</b>: {T("Complete, Partial or Limited, listing anything missing.")}</li>
              </ul>
            ) : (
              <ul className="latret">
                <li><b>{T("Answer")}</b>: {T("Yes, No, or Unknown when a needed reading is missing.")}</li>
                <li><b>{T("Lines")}</b>: {T("each line's reading, and the deciding reason.")}</li>
                <li><b>{T("Data available")}</b>: {T("Complete or Partial, separate from how sure the answer is.")}</li>
                <li>{T("No combined Set score.")}</li>
              </ul>
            )}
            <div className="rowtitle" style={{ marginTop: 12 }}>{T("Description")} <span className="m">· {T("written automatically")}</span></div>
            <p className="sub" style={{ margin: "4px 0 0" }}>{screen.description}</p>
          </section>
        </div>
      )}

      {screen && (
        <div className="latacts">
          <button type="button" className="primary" disabled={busy || !screen.can_save} onClick={() => save(false)}
            title={T("Saves version 1. It is private until you publish it.")}><Icon n="save" size={16} /> {kind === "group" ? T("Save as a new Group") : T("Save as a new Set")}</button>
          {source && <button type="button" className="ghost bordered" disabled={busy || !screen.can_save} onClick={() => save(true)}
            title={T("Saves a new version. Earlier versions stay as they were.")}><Icon n="save" size={16} /> {T("Save as version {v} of {name}", { v: (source.current_version || 0) + 1, name: source.name })}</button>}
          {mine && <Rename kind={kind} source={source} word={word} onDone={(name) => afterSave(source.id, T("Renamed to “{name}”. It shows under the new name everywhere.", { name }))} />}
          {mine && <Delete kind={kind} source={source} word={word} onDone={() => { setUndo({ id: source.id, name: source.name }); loadSources(); open("new"); }} />}
        </div>
      )}
      {flash && <p className={"note " + (flash[0] === "ok" ? "good" : "warn")}>{flash[1]}</p>}
      {kind === "group" && screen && screen.can_save && <TryIt model={model} />}
      {kind === "set" && source && <Study source={source} />}
    </>
  );
}

function Rename({ kind, source, word, onDone }) {
  const [openIt, setOpen] = useState(false);
  const [name, setName] = useState(source.name);
  const [msg, setMsg] = useState("");
  const clean = name.split(/\s+/).filter(Boolean).join(" ");
  const same = clean.toLowerCase() === String(source.name).trim().toLowerCase();
  const go = async () => {
    const { error } = await supabase.rpc("analysis_rename_config", { cfg: source.id, new_name: clean });
    if (!error) { setOpen(false); onDone(clean); return; }
    const text = String(error.message || "");
    setMsg(text.includes("name_taken") ? T("You already have a {word} called {name}.", { word, name: clean }) : T("Refused: {why}", { why: text }));
  };
  if (!openIt) return <button type="button" className="ghost bordered" onClick={() => { setName(source.name); setMsg(""); setOpen(true); }} title={T("Give {name} a new name.", { name: source.name })} aria-label={T("Rename")}><Icon n="pencil" /></button>;
  return (
    <div className="latpop">
      <label className="m" htmlFor="lat-rename">{T("New name for this {word}", { word })}</label>
      <input id="lat-rename" type="text" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      <div className="bar">
        <button type="button" className="primary" disabled={!clean || same} onClick={go}>{T("Rename")}</button>
        <button type="button" className="ghost" onClick={() => setOpen(false)}>{T("Cancel")}</button>
      </div>
      {msg && <p className="note warn">{msg}</p>}
    </div>
  );
}

function Delete({ kind, source, word, onDone }) {
  const [state, setState] = useState(null);
  const ask = async () => {
    setState({ busy: true });
    try { setState(await call(`/lattice/${kind}/delete-check`, { method: "POST", body: { source_id: source.id, lang } })); }
    catch (e) { setState({ ok: false, message: T("Lattice isn't reachable just now. Please try again in a minute.") }); }
  };
  const go = async () => {
    const { error } = await supabase.rpc("analysis_archive_config", { cfg: source.id });
    if (error) { setState({ ok: false, message: T("Refused: {why}", { why: error.message || "" }) }); return; }
    try {
      // A table column showing it goes too (the classic app's lattice_delete.column_settings_without).
      const s = (await preferences()).settings || {};
      const cols = s.table_columns, drop = `saved:${source.id}`;
      if (cols && typeof cols === "object" && ["groups", "sets"].some((k) => (cols[k] || []).includes(drop))) {
        await saveSettings({ table_columns: { ...cols, groups: (cols.groups || []).filter((c) => c !== drop), sets: (cols.sets || []).filter((c) => c !== drop) } });
      }
    } catch (e) { /* the column stays until it is chosen again */ }
    setState(null); onDone();
  };
  if (!state) return <button type="button" className="ghost bordered icondanger" onClick={ask} title={T("Remove {name} from your {word}s. You can undo it straight after.", { name: source.name, word })} aria-label={T("Delete this {word}", { word })}><Icon n="trash" /></button>;
  return (
    <div className="latpop">
      {state.busy ? <p className="m">{T("Checking…")}</p> : state.ok ? (
        <>
          <p className="m" style={{ margin: 0 }}>{T("Delete {name}? It disappears from your lists; if it is a column in your tables, that column is removed too. You can undo this straight after.", { name: source.name })}</p>
          <div className="bar">
            <button type="button" className="danger-btn" onClick={go}>{T("Delete {name}", { name: source.name })}</button>
            <button type="button" className="ghost" onClick={() => setState(null)}>{T("Cancel")}</button>
          </div>
        </>
      ) : (
        <>
          <p className="note warn" style={{ margin: 0 }}>{state.message}</p>
          <button type="button" className="ghost" onClick={() => setState(null)}>{T("Close")}</button>
        </>
      )}
    </div>
  );
}

function TryIt({ model }) {
  const [wl, setWl] = useState(null);
  const [pick, setPick] = useState("");
  const [out, setOut] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { watchlists().then(setWl).catch(() => setWl({ crypto: {}, equity: {} })); }, []);
  const list = wl ? [...Object.entries(wl.crypto || {}).map(([k, v]) => [`Crypto|${k}`, String(v)]), ...Object.entries(wl.equity || {}).map(([k, v]) => [`Stock|${k}`, `${v} (${k})`])] : [];
  useEffect(() => { if (!pick && list.length) setPick(list[0][0]); }, [list.length]);
  const go = async () => {
    setBusy(true); setOut(null);
    try { setOut(await call("/lattice/group/try", { method: "POST", body: { model, asset: pick, lang } })); }
    catch (e) { setOut({ error: true }); }
    setBusy(false);
  };
  if (wl && !list.length) return null;
  const name = (list.find((x) => x[0] === pick) || [])[1];
  return (
    <details className="card latdet">
      <summary><Icon n="play" size={16} /> {T("Try it on one asset (live)")}</summary>
      <div className="bar" style={{ marginTop: 10 }}>
        <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label={T("Asset")}>{list.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <button type="button" className="primary" disabled={busy || !pick} onClick={go}>{busy ? T("Checking…") : T("Try it")}</button>
      </div>
      {out && (out.error ? <p className="note bad">{T("That couldn't be checked just now. Please try again.")}</p> : (
        <p className="m" style={{ marginTop: 10 }}>
          <b>{name}</b>: {T("score {score}", { score: out.score == null ? "—" : signed(out.score) })}
          {out.label ? <> · {T("label")} <b>{out.label}</b>{out.qualified ? " " + T("(qualified)") : ""}</> : null}
          {" · "}{T("status {status}", { status: out.status })}
        </p>
      ))}
    </details>
  );
}

function Study({ source }) {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = (ask) => {
    setBusy(true);
    call(`/lattice/set/${ask ? "study-ask" : "study"}`, { method: "POST", body: { source_id: source.id, lang } })
      .then(setS).catch(() => setS({ state: "error", why: T("Lattice isn't reachable just now. Please try again in a minute.") })).finally(() => setBusy(false));
  };
  useEffect(() => { load(false); }, [source.id, source.current_version]);
  if (!s || s.state === "none" && !s.version) return null;
  const wait = T("Studies run in the background, usually within an hour; you can leave this page.");
  return (
    <section className="card" style={{ marginTop: 16 }}>
      <h2><Icon n="microscope" /> {T("What followed")} <span className="m">· {T("what happened after this Set turned Yes in the past")}</span></h2>
      {s.state === "done" ? <StudyCard icon={s.icon} card={s.card} />
        : s.state === "no" ? <p className="sub">{T("Can't be studied: {why}", { why: s.why })}</p>
        : s.state === "queued" || s.state === "running" ? <p className="note"><Icon n="hourglass" size={16} /> {s.state === "running" ? T("The study of version {v} is being worked out.", { v: s.version }) : T("The study of version {v} is waiting its turn.", { v: s.version })} {wait}</p>
        : s.state === "refused" ? <p className="sub">{T("Last try: {why}", { why: s.error || "" })}</p>
        : (
          <>
            {s.state === "failed" && s.error && <p className="sub">{T("Last try: {why}", { why: s.error })}</p>}
            {s.state === "error" && <p className="note bad">{s.why}</p>}
            <button type="button" className="primary" disabled={busy} onClick={() => load(true)}
              title={T("Checks what happened after this Set turned Yes on 25 major coins and 61 large US equities, Sep 2014 to Oct 2024, against comparable days.") + " " + wait}>
              <Icon n="microscope" size={16} /> {T("Study this Set (version {v})", { v: s.version || source.current_version })}</button>
          </>
        )}
    </section>
  );
}

function Table({ rows }) {
  if (!rows || !rows.length) return null;
  const cols = Object.keys(rows[0]);
  return (
    <div className="latscroll">
      <table className="lattbl"><thead><tr>{cols.map((c) => <th key={c}>{T(c)}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c}>{r[c] == null ? "" : String(r[c])}</td>)}</tr>)}</tbody></table>
    </div>
  );
}

function StudyCard({ icon, card }) {
  return (
    <details className="latdet" open>
      <summary><b>{card.verdict || T("not studied on its own")}</b> <span className="m">{String(card.title || "").replace("What followed · ", "")}</span></summary>
      <ul>{(card.lines || []).map((l, i) => <li key={i}>{l}</li>)}</ul>
      {card.parts && <><div className="rowtitle">{T("Coins and equities")}</div><ul>{card.parts.map((p, i) => <li key={i}>{p.line}</li>)}{card.compare && <li>{card.compare}</li>}</ul>{card.parts_note && <p className="m">{card.parts_note}</p>}</>}
      {card.periods && <><div className="rowtitle">{T("By period")}</div><Table rows={card.periods} /></>}
      {card.assets && <><div className="rowtitle">{T("Asset by asset")} <span className="m">({T("a guide only")})</span></div><p className="m">{card.assets.line}</p><p className="m">{card.assets.note}</p><Table rows={card.assets.rows} /></>}
      {card.history && <p className="m"><Icon n="folder" size={14} /> {card.history}</p>}
      {card.note && <p className="m">{card.note}</p>}
    </details>
  );
}
