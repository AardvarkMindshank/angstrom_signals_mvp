import React, { useEffect, useRef, useState } from "react";
import { T } from "../lib/i18n.js";
import Icon from "./Icon.jsx";

// 🗑️ The app's two ways of guarding a delete, both right where you pressed:
// · ConfirmButton: for what can't be undone or others see (a chat message, a comment, blocking someone). The button
//   turns into "Delete? [Delete] [Cancel]" in its own place; it goes back by itself after a few seconds.
// · useDelayed + UndoButton: for small things (a watchlist coin, clearing alerts). It happens on screen at once, an
//   Undo button stands where you pressed for a few seconds, and only then is it saved (also when you leave the page).
// The big ones (a Set, a funnel, a scan, Trade Log data) keep their red "Delete <name>" confirm in place.

export function ConfirmButton({ children, ask = T("Delete?"), yes = T("Delete"), onYes, className = "linkish", title, label }) {
  const [open, setOpen] = useState(false);
  useEffect(() => { if (!open) return; const t = setTimeout(() => setOpen(false), 6000); return () => clearTimeout(t); }, [open]);
  if (!open) return <button type="button" className={className} title={title} aria-label={label || title} onClick={() => setOpen(true)}>{children}</button>;
  return (
    <span className="confirm" role="group">
      <span className="m">{ask}</span>
      <button type="button" className="danger-btn sm" onClick={() => { setOpen(false); onYes(); }}>{yes}</button>
      <button type="button" className="ghost sm" onClick={() => setOpen(false)}>{T("Cancel")}</button>
    </span>
  );
}

// later.run(key, commit) holds commit for a few seconds; later.undo(key) drops it; later.held(key) says if it is held.
export function useDelayed(ms = 6000) {
  const jobs = useRef({});
  const [, tick] = useState(0);
  const finish = (key) => { const j = jobs.current[key]; if (!j) return; clearTimeout(j.t); delete jobs.current[key]; tick((n) => n + 1); j.commit(); };
  useEffect(() => {
    const flush = () => Object.keys(jobs.current).forEach(finish);
    window.addEventListener("pagehide", flush);
    return () => { window.removeEventListener("pagehide", flush); flush(); };
  }, []);
  return {
    run: (key, commit) => { if (jobs.current[key]) clearTimeout(jobs.current[key].t); jobs.current[key] = { commit, t: setTimeout(() => finish(key), ms) }; tick((n) => n + 1); },
    undo: (key) => { const j = jobs.current[key]; if (j) { clearTimeout(j.t); delete jobs.current[key]; tick((n) => n + 1); } },
    held: (key) => !!jobs.current[key],
  };
}

export function UndoButton({ onUndo, className = "" }) {
  return <button type="button" className={"undo " + className} onClick={onUndo}><Icon n="undo-2" size={15} /> {T("Undo")}</button>;
}
