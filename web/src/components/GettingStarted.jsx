import React, { useEffect, useState } from "react";
import { T } from "../lib/i18n.js";
import { supabase } from "../lib/supabase.js";
import { saveSettings } from "../lib/account.js";
import { watchlists } from "../lib/assets.js";
import Icon from "./Icon.jsx";

// 🚀 Getting started: five first steps on Quick Snapshot for new members (the classic app's checklist, onboarding.py,
// with the same saved progress: settings.onboarding). Two tick themselves (3 or more watchlist assets, a saved Prism
// scan); the others are ticked by the member. Skip hides it; Help and guides → Start here brings it back.
const STEPS = () => [
  ["markets", "settings", T("Choose the markets you trade"), T("Crypto, equities or both, in Settings › Markets & watchlists. The other market's pages and tables hide."), "#settings/markets"],
  ["watchlist", "star", T("Add a few assets you follow"), T("Search (Ctrl K) or Settings › Markets & watchlists. This ticks itself once you have 3 or more."), "#settings/markets"],
  ["reading", "trending-up", T("Open an asset and its readings"), T("Click a name in Signals: its page shows the chart, the readings and the news. Hover any reading for what it means."), "#signals/crypto"],
  ["alerts", "bell", T("Choose how alerts reach you"), T("Settings › Alerts & email: instant emails, a daily summary, or both."), "#settings/alerts"],
  ["prism", "scan-search", T("Try a Prism scan"), T("Lattice › Prism Scan: tap + on an example Set, then ▶. This ticks itself once you have a scan."), "#lattice/prism"],
];
const AUTO = ["watchlist", "prism"];

export function onboarding(settings) {
  const raw = (settings && settings.onboarding) || {};
  return { done: Array.isArray(raw.done) ? raw.done : [], hidden: !!raw.hidden };
}

export default function GettingStarted({ account }) {
  const [saved, setSaved] = useState(() => onboarding(account && account.settings));
  const [auto, setAuto] = useState(null);
  useEffect(() => {
    if (saved.hidden) return;
    (async () => {
      const a = {};
      try { const w = await watchlists(); a.watchlist = Object.keys(w.crypto || {}).length + Object.keys(w.equity || {}).length >= 3; } catch (e) { /* unknown */ }
      try {
        const { data: u } = await supabase.auth.getUser();
        const { data } = await supabase.from("prism_scans").select("id").eq("owner_id", u.user.id).is("builtin", null).limit(1);
        a.prism = !!(data && data.length);
      } catch (e) { /* unknown */ }
      setAuto(a);
    })();
  }, [saved.hidden]);
  if (saved.hidden || !auto) return null;
  const rows = STEPS().map(([k, icon, title, hint, href]) => ({ k, icon, title, hint, href, auto: AUTO.includes(k) && !!auto[k], done: (AUTO.includes(k) && !!auto[k]) || saved.done.includes(k) }));
  const count = rows.filter((r) => r.done).length;
  if (count === rows.length) return null;
  const store = (next) => { setSaved(next); saveSettings({ onboarding: next }).catch(() => {}); };
  const tick = (k) => store({ ...saved, done: saved.done.includes(k) ? saved.done.filter((x) => x !== k) : [...saved.done, k] });
  return (
    <section className="gstart">
      <div className="bar">
        <b><Icon n="rocket" size={16} /> {T("Getting started")}</b>
        <span className="m">{T("optional · {count} of {total} done", { count, total: rows.length })}</span>
        <button type="button" className="ghost icon" style={{ marginLeft: "auto" }} onClick={() => store({ ...saved, hidden: true })}
          title={T("Optional: skip this guide. Nothing depends on it; Help and guides › Start here brings it back.")} aria-label={T("Skip")}><Icon n="x" /></button>
      </div>
      <div className="gbar"><i style={{ width: `${(count / rows.length) * 100}%` }} /></div>
      <ol className="gsteps">
        {rows.map((r) => (
          <li key={r.k} className={r.done ? "done" : ""}>
            <button type="button" className="gtick" disabled={r.auto} onClick={() => tick(r.k)} aria-pressed={r.done}
              title={r.auto ? T("This ticks itself.") : r.done ? T("Mark as not done") : T("Mark as done")}>
              <Icon n={r.done ? "circle-check" : "circle"} size={20} />
            </button>
            <a href={r.href} title={r.hint}><Icon n={r.icon} size={15} /> {r.title}</a>
          </li>
        ))}
      </ol>
    </section>
  );
}

export async function showAgain(account) {
  const s = onboarding(account && account.settings);
  await saveSettings({ onboarding: { ...s, hidden: false } });
}
