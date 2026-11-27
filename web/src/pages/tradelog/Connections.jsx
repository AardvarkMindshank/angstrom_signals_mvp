import React, { useState } from "react";
import { T } from "../../lib/i18n.js";
import { rpc } from "../../lib/api.js";
import { stamp } from "../../lib/format.js";

export const LIMIT = { free: 0, plus: 1, pro: 2, elite: 10 };
export const PLATFORMS = { etoro: "eToro", binance: "Binance" };
const STATUS = () => ({ new: T("Importing"), importing: T("Importing"), ok: T("Connected"), failing: T("Needs attention"), paused: T("Paused") });

// Each connection's name: the member's own label, else the platform, numbered when there are several.
export function names(conns) {
  const seen = {}, out = {};
  [...conns].sort((a, b) => String(a.created_at).localeCompare(String(b.created_at))).forEach((c) => {
    const base = PLATFORMS[c.platform] || c.platform;
    seen[base] = (seen[base] || 0) + 1;
    out[c.id] = (c.label || "").trim() || (seen[base] === 1 ? base : `${base} ${seen[base]}`);
  });
  return out;
}

// Connect eToro with a read-only key. The keys go straight to the database, which keeps them encrypted.
export function Connect({ onDone }) {
  const [pub, setPub] = useState("");
  const [user, setUser] = useState("");
  const [label, setLabel] = useState("eToro");
  const [sure, setSure] = useState(false);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!pub.trim() || !user.trim() || !sure) { setMsg(["bad", T("Paste both keys and tick the box first.")]); return; }
    setBusy(true);
    try {
      await rpc("tradelog_save_connection", { p_platform: "etoro", p_label: label.trim() || "eToro", p_keys: { api_key: pub.trim(), user_key: user.trim() } });
      setPub(""); setUser(""); setSure(false);
      setMsg(["good", T("Connected. Your closed trades will appear within about 5 minutes.")]);
      onDone && onDone();
    } catch (err) {
      setMsg(["bad", T("Could not save the connection. Please try again.")]);
    }
    setBusy(false);
  };
  return (
    <section className="card">
      <h2>{T("Connect eToro (read-only)")}</h2>
      <ol className="steps">
        <li>{T("In eToro, open Settings, then Trading, then API Key Management, and create a key.")}</li>
        <li>{T("Choose Read permission only (never Write) and your real account. Leave the IP list empty.")}</li>
        <li>{T("Paste the key below, with eToro's public key. MarketNavi stores them encrypted and can only read your trades. It can never place, change or close a trade.")}</li>
      </ol>
      <p className="sub">{T("MarketNavi will never ask for a key by email or message.")}</p>
      <form className="form" onSubmit={submit} autoComplete="off">
        <label>{T("eToro public key")}<input type="password" value={pub} onChange={(e) => setPub(e.target.value)} /></label>
        <label>{T("Your eToro API key (Read)")}<input type="password" value={user} onChange={(e) => setUser(e.target.value)} /></label>
        <label>{T("Name for this platform's tab")}<input type="text" maxLength={30} value={label} onChange={(e) => setLabel(e.target.value)} /></label>
        <label className="check"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />{T("I created this key with Read permission only")}</label>
        {msg && <div className={"note " + msg[0]}>{msg[1]}</div>}
        <button type="submit" className="primary" disabled={busy}>{T("Connect")}</button>
      </form>
    </section>
  );
}

// Rename or disconnect a connection, or delete everything.
export function Manage({ conns, plan, onChange }) {
  const label = names(conns);
  const [edits, setEdits] = useState({});
  const [wipe, setWipe] = useState(false);
  const status = STATUS();
  const act = async (fn) => { try { await fn(); onChange && onChange(); } catch (e) { /* the row rules said no */ } };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <section className="card">
        <h2>{T("Manage connections")}</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 10 }}>
          {conns.map((c) => (
            <div key={c.id} className="conn">
              <div><b>{label[c.id]}</b> · <span className="m">{status[c.status] || status.new}</span>
                {c.last_sync_at && <span className="m"> · {T("Synced {when}", { when: stamp(c.last_sync_at) })}</span>}
                {c.last_error && <div className="note bad" style={{ marginTop: 6 }}>{T(c.last_error)}</div>}
              </div>
              <div className="bar">
                <input type="text" maxLength={30} value={edits[c.id] ?? label[c.id]} onChange={(e) => setEdits({ ...edits, [c.id]: e.target.value })} aria-label={T("Name for this platform's tab")} />
                <button type="button" className="ghost" disabled={!(edits[c.id] || "").trim() || edits[c.id] === label[c.id]}
                  onClick={() => act(() => rpc("tradelog_rename_connection", { p_id: c.id, p_label: edits[c.id].trim() }))}>{T("Save name")}</button>
                <button type="button" className="ghost" onClick={() => act(() => rpc("tradelog_delete_connection", { p_id: c.id }))}>{T("Disconnect")}</button>
              </div>
            </div>
          ))}
        </div>
        <div className="danger">
          <label className="check"><input type="checkbox" checked={wipe} onChange={(e) => setWipe(e.target.checked)} />{T("Delete every connection, trade, snapshot and note")}</label>
          <button type="button" className="danger-btn" disabled={!wipe} onClick={() => act(() => rpc("tradelog_delete_everything", {}))}>{T("Delete all my Trade Log data")}</button>
        </div>
      </section>
      {conns.length < (LIMIT[plan] ?? 2)
        ? <Connect onDone={onChange} />
        : <p className="sub">{T("Your plan includes {n} connection(s). Disconnect one, or upgrade, to add another.", { n: LIMIT[plan] ?? 2 })}</p>}
    </div>
  );
}
