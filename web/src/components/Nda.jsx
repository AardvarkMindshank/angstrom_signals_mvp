import React, { useEffect, useRef, useState } from "react";
import { T } from "../lib/i18n.js";
import { supabase } from "../lib/supabase.js";
import { call, DATA_URL } from "../lib/service.js";
import Icon from "./Icon.jsx";
import Markdown from "./Markdown.jsx";

// ✍️ The beta NDA page (nda.py): until a tester has signed the current NDA, the app shows only this page. Read it,
// tick, type a full name and country, draw a signature, sign. The data service builds the signed copy and records it;
// a copy is emailed to the signer and the admins by the worker, and can be downloaded here at once. Admins never
// sign but can open a preview from Admin › Beta requests, which records nothing. In English, as the NDA itself is
// (the classic page too); only the signature pad's words are translated, as in the classic pad.

export const NDA_ICONS = ["file-text", "pen-line", "download", "x", "log-out"];

const save = (b64, name) => {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
};

async function downloadPdf(file) {
  const { data } = await supabase.auth.getSession();
  const r = await fetch(DATA_URL + "/nda/pdf", { headers: { Authorization: `Bearer ${data.session ? data.session.access_token : ""}` } });
  if (!r.ok) return;
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a"); a.href = url; a.download = file || "NDA.pdf"; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

function Pad({ onChange }) {
  const cv = useRef(null);
  const st = useRef({ drawing: false, last: null, inked: 0 });
  const [captured, setCaptured] = useState(false);
  const ratio = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
  const reset = () => {
    const c = cv.current; if (!c) return;
    const r = c.getBoundingClientRect();
    c.width = Math.max(300, Math.round(r.width * ratio)); c.height = Math.round(170 * ratio);
    const g = c.getContext("2d");
    g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);
    g.lineWidth = 2.4 * ratio; g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = "#111";
    st.current.inked = 0; setCaptured(false); onChange("");
  };
  useEffect(reset, []);
  const at = (e) => { const r = cv.current.getBoundingClientRect(); return [(e.clientX - r.left) * ratio, (e.clientY - r.top) * ratio]; };
  const down = (e) => { e.preventDefault(); st.current.drawing = true; st.current.last = at(e); cv.current.setPointerCapture(e.pointerId); };
  const move = (e) => {
    const s = st.current; if (!s.drawing) return;
    e.preventDefault();
    const p = at(e), g = cv.current.getContext("2d");
    g.beginPath(); g.moveTo(s.last[0], s.last[1]); g.lineTo(p[0], p[1]); g.stroke();
    s.inked += Math.hypot(p[0] - s.last[0], p[1] - s.last[1]); s.last = p;
  };
  const up = () => {
    const s = st.current; if (!s.drawing) return;
    s.drawing = false;
    if (s.inked > 60 * ratio) { setCaptured(true); onChange(cv.current.toDataURL("image/png").split(",")[1]); }
  };
  return (
    <div className="sigpad">
      <canvas ref={cv} role="img" aria-label={T("Signature pad: draw your signature")} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onPointerLeave={up} />
      <div className="bar">
        <button type="button" className="ghost bordered sm" onClick={reset}>{T("Clear")}</button>
        <span className="m">{captured ? T("Signature captured.") : T("Sign inside the box.")}</span>
      </div>
    </div>
  );
}

export default function Nda({ info, preview = false, onDone, onClose }) {
  const [agreed, setAgreed] = useState(false);
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [drawing, setDrawing] = useState("");
  const [problems, setProblems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [sample, setSample] = useState(null);
  const sign = async () => {
    setBusy(true); setProblems([]);
    try {
      const r = await call("/nda/sign", { method: "POST", body: { full_name: name, country, agreed, drawing, preview }, timeout: 60000 });
      if (!r.ok) { setProblems(r.problems || ["The signature could not be saved. Please try again."]); return; }
      if (preview) { setSample(r); return; }
      onDone(r);
    } catch (e) { setProblems(["The signature could not be saved. Please try again."]); } finally { setBusy(false); }
  };
  return (
    <div className="nda">
      {preview && (
        <div className="ndapreview">
          <span><b>Preview</b>: this is the page testers see before they can use the app{info.enforce ? "" : " (switched off for now: nobody is asked to sign yet)"}. Signing here records nothing; you get a sample signed copy to download.</span>
          {sample && <button type="button" className="ghost bordered sm" onClick={() => save(sample.pdf, sample.name)}><Icon n="download" size={15} /> Download the sample signed copy</button>}
          <button type="button" className="ghost icon" onClick={onClose} title="Close the preview" aria-label="Close the preview"><Icon n="x" /></button>
        </div>
      )}
      <h1><Icon n="pen-line" size={24} /> {info.title}</h1>
      <p>Welcome to the MarketNavi closed beta. Before you start, please read and sign the beta non-disclosure agreement. It takes a minute, and you only do it once.</p>
      <button type="button" className="ghost bordered" onClick={() => downloadPdf(info.file)}><Icon n="file-text" size={16} /> Download the NDA (PDF)</button>
      <div className="ndatext">{info.markdown ? <Markdown text={info.markdown} /> : <p style={{ whiteSpace: "pre-wrap" }}>{info.text || "The NDA could not be shown here: please download the PDF above and read it."}</p>}</div>
      <p className="m">Version {info.version} · document fingerprint {String(info.sha256 || "").slice(0, 16)}…</p>
      <label className="ptog"><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} /> <span>I have read the NDA and agree to its terms.</span></label>
      <div className="ndaform">
        <label>Your full legal name<input type="text" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
        <label>Country of residence<input type="text" maxLength={80} value={country} onChange={(e) => setCountry(e.target.value)} autoComplete="country-name" /></label>
      </div>
      <div><b>Your signature</b>: draw it with your finger or mouse.</div>
      <Pad onChange={setDrawing} />
      {problems.map((p) => <p key={p} className="note bad">{p}</p>)}
      <div className="ndabar">
        <button type="button" className="primary" disabled={busy} onClick={sign}><Icon n="pen-line" size={16} /> {busy ? "Signing…" : "Sign and continue"}</button>
        {!preview && <button type="button" className="ghost" onClick={() => supabase.auth.signOut()}><Icon n="log-out" size={16} /> {T("Log out")}</button>}
      </div>
      <p className="m">Signing records your typed name and country, your drawn signature, the time, your IP address and browser, and which version of the NDA you signed. You will get a signed copy by email.</p>
    </div>
  );
}

// After signing: thanks, and the signed copy to keep (shown once, at the top of the app).
export function Signed({ copy, onClose }) {
  return (
    <div className="ndadone">
      <span>Thank you: the NDA is signed. A signed copy is on its way to your email.</span>
      <button type="button" className="ghost bordered sm" onClick={() => save(copy.pdf, copy.name)}><Icon n="download" size={15} /> Download your signed copy</button>
      <button type="button" className="ghost icon" onClick={onClose} title={T("Close")} aria-label={T("Close")}><Icon n="x" /></button>
    </div>
  );
}
