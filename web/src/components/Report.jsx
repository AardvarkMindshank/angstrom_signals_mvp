import React, { useState } from "react";
import { T } from "../lib/i18n.js";
import { supabase } from "../lib/supabase.js";
import Icon from "./Icon.jsx";

// 🚩 Report a comment or chat message that breaks the socials policy, right under it: a reason, a note, Send report.
// Saved to comment_reports (only the admins see it, in Admin › Reported comments; the worker emails them).
export const REASONS = () => [["promotion", T("Promoting an asset")], ["advice", T("Presented as financial advice")],
  ["harassment", T("Harassment or a personal attack")], ["spam", T("Spam")], ["other", T("Something else")]];

export function ReportButton({ onOpen }) {
  return <button type="button" className="linkish" onClick={onOpen} title={T("Report")} aria-label={T("Report")}><Icon n="flag" size={15} tone={false} /></button>;
}

export function ReportBox({ n, place, kind, asset = "", onClose }) {
  const [reason, setReason] = useState("promotion");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const send = async () => {
    const words = note.split(/\s+/).join(" ").trim().slice(0, 500);
    if (reason === "other" && words.length < 4) { setMsg(["bad", T("Report needs a few words when the reason is Something else.")]); return; }
    setBusy(true);
    const { data: u } = await supabase.auth.getUser();
    const row = { user_id: u.user.id, user_email: u.user.email || "unknown", place, message_id: Number(n.id), message_kind: kind,
      asset_key: String(asset || n.asset_key || "").slice(0, 200), comment_body: String(n.body || "").split(/\s+/).join(" ").slice(0, 160),
      reason, note: words, status: "reported", ...(n.author_id ? { author_id: n.author_id } : {}) };
    const { error } = await supabase.from("comment_reports").insert(row);
    setBusy(false);
    if (!error) { setMsg(["ok", T("Report sent. Thank you.")]); setTimeout(onClose, 2500); return; }
    setMsg(["bad", /duplicate|23505/.test(error.message || "") ? T("Report already sent for this comment.") : T("Report could not be sent.")]);
  };
  return (
    <div className="reportbox" role="group" aria-label={T("Report this comment")}>
      <b>{T("Report this comment")}</b>
      <label>{T("Reason")}<select value={reason} onChange={(e) => setReason(e.target.value)}>{REASONS().map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
      <textarea maxLength={500} rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={T("What should we look at? Add a note for Something else.")} />
      {msg && <p className={"note " + (msg[0] === "ok" ? "good" : "bad")}>{msg[1]}</p>}
      <div className="row">
        <button type="button" className="danger-btn sm" disabled={busy || (msg && msg[0] === "ok")} onClick={send}>{T("Send report")}</button>
        <button type="button" className="ghost sm" onClick={onClose}>{T("Cancel")}</button>
      </div>
      <span className="m">{T("Only the MarketNavi team sees reports.")}</span>
    </div>
  );
}
