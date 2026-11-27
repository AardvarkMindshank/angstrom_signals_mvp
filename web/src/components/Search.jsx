import React, { useEffect, useMemo, useRef, useState } from "react";
import { T } from "../lib/i18n.js";
import { universe, watchlists, match, brief, keyFor } from "../lib/assets.js";
import { usd as price, pct, tone } from "../lib/format.js";
import { openNavigator } from "./Navigator.jsx";

export const assetHref = (key, tab) => `#asset/${encodeURIComponent(key)}${tab ? "/" + tab : ""}`;
const go = (href) => { window.location.hash = href.slice(1); };

const PAGES = () => [{ href: "#tradelog", label: T("Trade Log"), words: "trade log trades journal etoro binance logbook review" }];

function Logo({ a, src, size = 36 }) {
  const [bad, setBad] = useState(false);
  if (src && !bad) return <img className="alogo" src={src} alt="" width={size} height={size} onError={() => setBad(true)} />;
  return <span className="alogo letter" style={{ width: size, height: size }}>{(a.symbol || a.name || "?").slice(0, 1)}</span>;
}
export { Logo };

// The search at the top of every page: type an asset (or a page) and go straight to it. Ctrl K (⌘K) from anywhere.
export default function Search() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [list, setList] = useState([]);
  const [watch, setWatch] = useState({ crypto: {}, equity: {} });
  const [info, setInfo] = useState({});
  const [sel, setSel] = useState(0);
  const box = useRef(null), input = useRef(null);

  useEffect(() => { universe().then(setList).catch(() => {}); watchlists().then(setWatch).catch(() => {}); }, []);
  useEffect(() => {
    const k = (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); input.current && input.current.focus(); setOpen(true); } };
    const out = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    window.addEventListener("keydown", k); document.addEventListener("mousedown", out);
    return () => { window.removeEventListener("keydown", k); document.removeEventListener("mousedown", out); };
  }, []);

  const watched = useMemo(() => new Set([...Object.keys(watch.crypto || {}).map((id) => keyFor("crypto", id)),
    ...Object.keys(watch.equity || {}).map((id) => keyFor("equity", id))]), [watch]);
  const byKey = useMemo(() => Object.fromEntries(list.map((a) => [a.key, a])), [list]);
  const hits = useMemo(() => match(list, q, watched), [list, q, watched]);
  const watchRows = useMemo(() => [...watched].map((k) => byKey[k] || (() => {
    const [kind, id] = k.split("|"); const name = (kind === "Crypto" ? watch.crypto : watch.equity)[id];
    return { key: k, kind: kind === "Crypto" ? "crypto" : "equity", id, symbol: id.toUpperCase(), name: typeof name === "string" ? name : id };
  })()), [watched, byKey, watch]);
  const pages = useMemo(() => { const w = q.trim().toLowerCase(); return w.length < 2 ? [] : PAGES().filter((p) => p.words.includes(w) || p.label.toLowerCase().includes(w)); }, [q]);
  const shown = q.trim() ? hits : watchRows.slice(0, 12);

  useEffect(() => {
    const need = shown.map((a) => a.key).filter((k) => !info[k]);
    if (open && need.length) brief(need).then((b) => setInfo((i) => ({ ...i, ...b }))).catch(() => {});
  }, [open, shown.map((a) => a.key).join(",")]);
  useEffect(() => setSel(0), [q]);

  const pick = (href) => { setOpen(false); setQ(""); input.current && input.current.blur(); go(href); };
  const topic = q.trim().length >= 2 ? `#search/${encodeURIComponent(q.trim())}` : null;
  const items = [...shown.map((a) => assetHref(a.key)), ...pages.map((p) => p.href), ...(topic ? [topic, "nav"] : [])];
  const pickAny = (href) => { if (href === "nav") { const text = q.trim(); setOpen(false); setQ(""); openNavigator({ question: text }); } else pick(href); };
  const key = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
    else if (e.key === "Enter" && items[sel]) { e.preventDefault(); pickAny(items[sel]); }
    else if (e.key === "Escape") { setOpen(false); input.current.blur(); }
  };
  const cls = (a) => (a.kind === "crypto" ? T("crypto") : T("equity"));
  const top = q.trim() && hits[0];

  return (
    <div className="search" ref={box}>
      <label className="sr" htmlFor="mn-search">{T("Search MarketNavi")}</label>
      <div className={"sfield" + (open ? " on" : "")}>
        <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        <input id="mn-search" ref={input} type="search" autoComplete="off" placeholder={T("Search an asset, e.g. XRP or Apple")} value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} onKeyDown={key}
          role="combobox" aria-expanded={open} aria-controls="mn-search-list" />
        <kbd>{/Mac|iPhone|iPad/.test(navigator.platform) ? "⌘K" : "Ctrl K"}</kbd>
      </div>
      {open && (
        <div className="sdrop" id="mn-search-list" role="listbox">
          {!q.trim() && <div className="shead">{watchRows.length ? T("Your watchlist") : T("Type a crypto or equity name or symbol.")}</div>}
          {top && (
            <a href={assetHref(top.key)} className={"stop" + (sel === 0 ? " sel" : "")} onClick={(e) => { e.preventDefault(); pick(assetHref(top.key)); }}>
              <Logo a={top} src={(info[top.key] || {}).logo} size={40} />
              <span className="sname"><b>{top.symbol}</b> <span className="m">{top.name} · {cls(top)}</span>
                <span className="m block">{T("Everything about {name} on one page", { name: top.name })}</span></span>
              <Quote i={info[top.key]} />
              <span className="sgo">{T("Open")} ›</span>
            </a>
          )}
          {top && (
            <div className="sjump">
              {[["chart", T("Chart")], ["readings", T("Readings")], ["news", T("News")], ["activity", T("Your activity")]].map(([tab, l]) => (
                <a key={tab} href={assetHref(top.key, tab)} onClick={(e) => { e.preventDefault(); pick(assetHref(top.key, tab)); }}>{l}</a>
              ))}
            </div>
          )}
          {(top ? shown.slice(1) : shown).length > 0 && top && <div className="shead">{T("Also matching")}</div>}
          {(top ? shown.slice(1) : shown).map((a, i) => {
            const n = top ? i + 1 : i;
            return (
              <a key={a.key} href={assetHref(a.key)} className={"srow" + (sel === n ? " sel" : "")} onMouseEnter={() => setSel(n)}
                onClick={(e) => { e.preventDefault(); pick(assetHref(a.key)); }}>
                <Logo a={a} src={(info[a.key] || {}).logo} size={28} />
                <span className="sname"><b>{a.symbol}</b> <span className="m">{a.name} · {cls(a)}</span></span>
                <Quote i={info[a.key]} />
              </a>
            );
          })}
          {pages.length > 0 && <div className="shead">{T("Pages")}</div>}
          {pages.map((p, i) => (
            <a key={p.href} href={p.href} className={"srow" + (sel === shown.length + i ? " sel" : "")} onClick={(e) => { e.preventDefault(); pick(p.href); }}>
              <span className="sname"><b>{p.label}</b></span>
            </a>
          ))}
          {topic && (
            <>
              <div className="shead">{T("Everywhere in MarketNavi")}</div>
              <a href={topic} className={"srow" + (sel === shown.length + pages.length ? " sel" : "")} onClick={(e) => { e.preventDefault(); pick(topic); }}>
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 5h16v11H8l-4 4z" /></svg>
                <span className="sname">{T("News and your Logbook mentioning “{q}”", { q: q.trim() })}</span>
              </a>
              <a href="#" className={"srow" + (sel === shown.length + pages.length + 1 ? " sel" : "")} onClick={(e) => { e.preventDefault(); pickAny("nav"); }}>
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="var(--gold)" strokeWidth="1.8" strokeLinejoin="round"><path d="M12 3l1.8 4.6L18 9l-4.2 1.4L12 15l-1.8-4.6L6 9l4.2-1.4z" /></svg>
                <span className="sname">{T("Ask the AI Navigator: “{q}”", { q: q.trim() })}</span>
              </a>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Quote({ i }) {
  if (!i || i.price == null) return <span className="squote" />;
  return (
    <span className="squote">
      <b>{price(i.price)}</b>
      {i.change != null && <span className={tone(i.change)}>{pct(i.change, 1)}</span>}
    </span>
  );
}
