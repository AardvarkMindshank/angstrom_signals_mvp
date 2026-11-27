import React, { useEffect, useState } from "react";
import Icon from "./Icon.jsx";
import { createPortal } from "react-dom";
import { T } from "../lib/i18n.js";
import NavigatorChat, { Sparkle } from "./Navigator.jsx";
import Social from "./Social.jsx";

// One panel on the right for 💬 Social and ✨ the AI Navigator, switched by its two tabs (one place to look, and the
// page keeps its width). It slides over the page, or, pinned, sits beside it and the page makes room.
// The top bar's two buttons open it on their tab; openNavigator() opens it on the Navigator with a question.
const read = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };
const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private window */ } };

export default function SidePanel({ onScreen }) {
  const isWide = () => typeof window !== "undefined" && window.matchMedia("(min-width: 1100px)").matches;
  // Reopens by itself only when pinned on a wide screen; on a phone it always starts closed.
  const [open, setOpen] = useState(() => read("mn_panel_open", false) && read("mn_panel_pinned", false) && isWide());
  const [tab, setTab] = useState(() => read("mn_panel_tab", "social"));
  const [pinned, setPinned] = useState(() => read("mn_panel_pinned", false));
  const [incoming, setIncoming] = useState(null);
  const [wide, setWide] = useState(isWide);
  useEffect(() => { const m = window.matchMedia("(min-width: 1100px)"); const f = () => setWide(m.matches); m.addEventListener("change", f); return () => m.removeEventListener("change", f); }, []);

  const show = (t) => { setTab(t); setOpen(true); write("mn_panel_tab", t); write("mn_panel_open", true); };
  const close = () => { setOpen(false); write("mn_panel_open", false); };
  useEffect(() => {
    const f = (e) => { show("navigator"); setIncoming({ ...(e.detail || {}), n: Date.now() }); };
    window.addEventListener("mn-navigator", f);
    const k = (e) => { if (e.key === "Escape" && !pinned) close(); };
    window.addEventListener("keydown", k);
    return () => { window.removeEventListener("mn-navigator", f); window.removeEventListener("keydown", k); };
  }, [pinned]);
  useEffect(() => { document.body.classList.toggle("docked", open && pinned && wide); }, [open, pinned, wide]);

  const btn = (t, icon, label, tip) => (
    <button type="button" className={"panelbtn" + (open && tab === t ? " on" : "")} aria-pressed={open && tab === t} title={tip}
      onClick={() => (open && tab === t ? close() : show(t))}>{icon}<span>{label}</span></button>
  );
  return (
    <>
      {btn("social", <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"><path d="M4 5h16v11H9l-5 4z" /></svg>, T("Social"), T("Members' comments and the chat."))}
      {btn("navigator", <Sparkle />, T("Navigator"), T("Ask the AI Navigator about the app, a reading, an asset or an idea."))}
      {createPortal(
        <aside className={"sidepanel" + (open ? " open" : "") + (pinned && wide ? " pinned" : "")} aria-label={tab === "social" ? T("Social") : T("AI Navigator")} aria-hidden={!open}>
          <div className="sphead">
            <div className="sptabs" role="tablist">
              <button type="button" role="tab" aria-selected={tab === "social"} className={tab === "social" ? "on" : ""} onClick={() => show("social")}>{T("Social")}</button>
              <button type="button" role="tab" aria-selected={tab === "navigator"} className={tab === "navigator" ? "on nav" : "nav"} onClick={() => show("navigator")}><Sparkle /> {T("AI Navigator")}</button>
            </div>
            {wide && (
              <button type="button" className={"ghost icon" + (pinned ? " on" : "")} aria-pressed={pinned} title={pinned ? T("Unpin: let the panel slide over the page") : T("Pin beside the page")}
                onClick={() => { setPinned(!pinned); write("mn_panel_pinned", !pinned); }}>
                <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill={pinned ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"><path d="M9 3h6l-1 6 4 4H6l4-4zM12 13v8" /></svg>
              </button>
            )}
            <button type="button" className="ghost icon" onClick={close} aria-label={T("Close")}><Icon n="x" /></button>
          </div>
          <div className="spbody">
            <div style={{ display: tab === "social" ? "block" : "none" }} className="spscroll"><Social visible={open && tab === "social"} /></div>
            <div style={{ display: tab === "navigator" ? "flex" : "none", flex: 1, minHeight: 0 }}><NavigatorChat onScreen={onScreen} ask={incoming} /></div>
          </div>
        </aside>, document.body)}
    </>
  );
}
