import React, { useEffect, useRef, useState } from "react";
import { Glyphs } from "./Icon.jsx";
import { T, lang } from "../lib/i18n.js";
import { ask } from "../lib/service.js";

// ✨ The AI Navigator. Ask about the app, a reading, an asset or an idea; it can look things up in MarketNavi
// (readings, your Sets) but never trades or saves anything for you. Opened from the top bar, or from anywhere with
// openNavigator({question, onScreen}), which opens the side panel on its Navigator tab.
const KEY = "mn_nav_chat";
const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY)) || []; } catch (e) { return []; } };
const keep = (c) => { try { sessionStorage.setItem(KEY, JSON.stringify(c.slice(-30))); } catch (e) { /* private window */ } };

export function openNavigator(detail) { window.dispatchEvent(new CustomEvent("mn-navigator", { detail: detail || {} })); }

// The chat itself, shown in the side panel's Navigator tab. `ask` (from the panel) is a question to send now.
export default function NavigatorChat({ onScreen, ask: incoming }) {
  const [chat, setChat] = useState(load);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const end = useRef(null), box = useRef(null);

  const send = async (question, extra) => {
    const text = String(question || "").trim();
    if (!text || busy) return;
    setErr(""); setBusy(true);
    const before = chat;
    const next = [...chat, { role: "user", content: text }];
    setChat(next); setQ("");
    try {
      const got = await ask(text, before.map(({ role, content }) => ({ role, content })), lang, [onScreen || "", extra || ""].filter(Boolean).join("\n"));
      const done = [...next, { role: "assistant", content: got.answer, notes: got.notes || [] }];
      setChat(done); keep(done);
    } catch (e) {
      setChat(before);
      setQ(text);
      setErr(e.status === 429 ? T("That's your Navigator questions for today. It's back tomorrow.") : e.status === 0
        ? T("The Navigator isn't reachable just now. Please try again in a minute.") : T("The Navigator couldn't answer just now. Please try again."));
    }
    setBusy(false);
  };

  useEffect(() => { if (incoming && incoming.question) send(incoming.question, incoming.onScreen); else if (box.current) box.current.focus(); }, [incoming]);
  useEffect(() => { if (end.current) end.current.scrollIntoView({ block: "end" }); }, [chat, busy]);

  return (
    <div className="navchat">
      <div className="navbody">
        {!chat.length && (
          <div className="navhint">
            <p>{T("Ask anything about MarketNavi: what a reading means, where to find something, or how to test an idea. It explains; no buy or sell calls.")}</p>
            {[T("What does a Stretch of −40 mean?"), T("Why is the Tide going out?"), T("Which of my Sets say yes on this asset?")].map((s) => (
              <button key={s} type="button" className="navsug" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        {chat.map((m, i) => (
          <div key={i} className={"navmsg " + m.role}>
            {m.role === "assistant" ? <Rich text={m.content} /> : m.content}
            {(m.notes || []).map((n, j) => <div key={j} className="navnote">{n}</div>)}
          </div>
        ))}
        {busy && <div className="navmsg assistant m">{T("Thinking…")}</div>}
        {err && <div className="note bad">{err}</div>}
        <div ref={end} />
      </div>
      <form className="navform" onSubmit={(e) => { e.preventDefault(); send(q); }}>
        {chat.length > 0 && <button type="button" className="ghost" onClick={() => { setChat([]); keep([]); setErr(""); }} title={T("New chat")} aria-label={T("New chat")}>＋</button>}
        <textarea ref={box} rows={2} value={q} maxLength={4000} placeholder={T("Ask about the app, an asset, a Set or an idea…")} aria-label={T("Your question")}
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(q); } }} />
        <button type="submit" className="primary" disabled={busy || !q.trim()}>{T("Ask")}</button>
      </form>
    </div>
  );
}

export function Sparkle() {
  return <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"><path d="M12 3l1.8 4.6L18 9l-4.2 1.4L12 15l-1.8-4.6L6 9l4.2-1.4z" /><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" /></svg>;
}

// A small, safe Markdown subset: paragraphs, bullet and numbered lists, **bold**, *italic*, `code` and headings.
function inline(s) {
  const out = []; const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/g; let last = 0, m, k = 0;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(<Glyphs key={k++} text={s.slice(last, m.index)} />);
    const t = m[0];
    out.push(t.startsWith("**") ? <b key={k++}><Glyphs text={t.slice(2, -2)} /></b> : t.startsWith("`") ? <code key={k++}>{t.slice(1, -1)}</code> : <i key={k++}><Glyphs text={t.slice(1, -1)} /></i>);
    last = m.index + t.length;
  }
  if (last < s.length) out.push(<Glyphs key={k++} text={s.slice(last)} />);
  return out;
}
export function Rich({ text }) {
  const blocks = []; let list = null;
  String(text || "").split("\n").forEach((raw, i) => {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*•]\s+(.*)/.exec(line), num = /^\s*\d+[.)]\s+(.*)/.exec(line), head = /^#{1,4}\s+(.*)/.exec(line);
    if (bullet || num) {
      const kind = bullet ? "ul" : "ol";
      if (!list || list.kind !== kind) { list = { kind, items: [] }; blocks.push(list); }
      list.items.push((bullet || num)[1]);
      return;
    }
    list = null;
    if (!line.trim()) return;
    blocks.push(head ? { kind: "h", text: head[1] } : { kind: "p", text: line });
  });
  return <>{blocks.map((b, i) => b.kind === "ul" ? <ul key={i}>{b.items.map((x, j) => <li key={j}>{inline(x)}</li>)}</ul>
    : b.kind === "ol" ? <ol key={i}>{b.items.map((x, j) => <li key={j}>{inline(x)}</li>)}</ol>
    : b.kind === "h" ? <p key={i}><b>{inline(b.text)}</b></p> : <p key={i}>{inline(b.text)}</p>)}</>;
}
