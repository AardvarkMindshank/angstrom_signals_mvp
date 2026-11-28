import React, { useEffect, useRef, useState } from "react";
import { T } from "../../lib/i18n.js";
import { supabase } from "../../lib/supabase.js";
import Icon from "../../components/Icon.jsx";

// 💬 Feedback: an issue or an idea, with up to three screenshots (made smaller here, as the classic app does: JPEG,
// at most 1600 px on the long side), saved to feedback_notes and the private feedback store. The admins see it in
// Admin › Feedback and get an email from the worker; the member is told as it moves along. Below, your own notes
// and where each one is.
const MAX = 3;
const STATUS = { submitted: "Submitted", under_review: "Under review", accepted: "Accepted", in_development: "In development", in_production: "In production", rejected: "Rejected", closed: "Closed" };

function shrink(file) {
  return new Promise((resolve, reject) => {
    if (file.size > 20_000_000) { reject(new Error("too large")); return; }
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      const k = Math.min(1, 1600 / Math.max(img.naturalWidth, img.naturalHeight));
      const c = document.createElement("canvas"); c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
      const g = c.getContext("2d"); g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob((b) => (b ? resolve(b) : reject(new Error("unreadable"))), "image/jpeg", 0.85);
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("unreadable")); };
    img.src = url;
  });
}

export default function Feedback() {
  const [kind, setKind] = useState("issue");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [mine, setMine] = useState(null);
  const pick = useRef(null);
  const load = () => supabase.from("feedback_notes").select("id, kind, body, status, created_at").order("created_at", { ascending: false }).limit(20)
    .then(({ data }) => setMine(data || [])).catch(() => setMine([]));
  useEffect(() => { load(); }, []);
  const add = (list) => {
    const next = [...files, ...Array.from(list || [])].slice(0, MAX);
    if (files.length + (list ? list.length : 0) > MAX) setMsg(["bad", T("Add at most {n} screenshots.", { n: MAX })]);
    setFiles(next);
  };
  const submit = async () => {
    const text = body.trim();
    if (!text) { setMsg(["bad", T("Write a few words first.")]); return; }
    setBusy(true); setMsg(null);
    const { data: u } = await supabase.auth.getUser();
    const uid = u.user.id;
    let problem = "", paths = [];
    for (const f of files) {
      let blob = null;
      try { blob = await shrink(f); } catch (e) { problem = T("A picture could not be read, so it was left out."); continue; }
      const day = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const path = `${uid}/${day}-${Math.random().toString(16).slice(2, 14)}.jpg`;
      let failed = true;
      try { ({ error: failed } = await supabase.storage.from("feedback").upload(path, blob, { contentType: "image/jpeg" })); } catch (e) { failed = true; }
      if (failed) { problem = T("The screenshots could not be stored yet, so the note was saved without them."); paths = []; break; }
      paths.push(path);
    }
    const note = { user_id: uid, user_email: u.user.email || "unknown", kind, body: text.slice(0, 4000), status: "submitted" };
    let { error } = await supabase.from("feedback_notes").insert(paths.length ? { ...note, images: paths } : note);
    if (error && paths.length) { ({ error } = await supabase.from("feedback_notes").insert(note)); problem = T("The screenshots could not be stored yet, so the note was saved without them."); }
    setBusy(false);
    if (error) { setMsg(["bad", T("That could not be saved. Please try again.")]); return; }
    setBody(""); setFiles([]);
    setMsg(["ok", (T("Sent. Thank you: it's with the MarketNavi team, and you'll be told as it moves along.") + " " + problem).trim()]);
    load();
  };
  return (
    <div className="fbk">
      <p className="sub">{T("An issue or an idea. It is stored as submitted, with your account and the date.")}</p>
      <div className="seg" role="radiogroup" aria-label={T("Type")}>
        {[["issue", "triangle-exclamation-point", T("Issue")], ["enhancement", "lightbulb", T("Enhancement")]].map(([k, ic, l]) => (
          <button key={k} type="button" role="radio" aria-checked={kind === k} className={kind === k ? "on" : ""} onClick={() => setKind(k)}><Icon n={ic} size={15} /> {l}</button>
        ))}
      </div>
      <label className="fbl">{T("Details")}
        <textarea rows={5} maxLength={4000} value={body} onChange={(e) => setBody(e.target.value)} placeholder={T("What happened, or what would you like?")} />
      </label>
      <div className="fbshots">
        <button type="button" className="ghost bordered" disabled={files.length >= MAX} onClick={() => pick.current && pick.current.click()}
          title={T("Up to {n} pictures, to show where in the app it happened. On a phone, take a screenshot first, then pick it from your photos.", { n: MAX })}>
          <Icon n="image" size={16} /> {T("Screenshots (optional)")}
        </button>
        <input ref={pick} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        {files.map((f, i) => (
          <span key={i} className="fbfile"><img src={URL.createObjectURL(f)} alt="" />
            <button type="button" className="ghost icon" onClick={() => setFiles(files.filter((_, j) => j !== i))} title={T("Remove")} aria-label={T("Remove")}><Icon n="x" size={14} /></button></span>
        ))}
      </div>
      {msg && <p className={"note " + (msg[0] === "ok" ? "good" : "bad")}>{msg[1]}</p>}
      <div><button type="button" className="primary" disabled={busy} onClick={submit}>{busy ? T("Sending…") : T("Submit")}</button></div>
      {mine && mine.length > 0 && (
        <section className="fbmine">
          <div className="rowtitle">{T("Your feedback")}</div>
          {mine.map((n) => (
            <div key={n.id} className="fbrow">
              <Icon n={n.kind === "enhancement" ? "lightbulb" : "triangle-exclamation-point"} size={15} />
              <span className="fbtext">{n.body}</span>
              <span className={"fbstat " + n.status}>{T(STATUS[n.status] || n.status)}</span>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
