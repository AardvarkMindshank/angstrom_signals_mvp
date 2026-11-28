import React, { Suspense, lazy, startTransition, useEffect, useState } from "react";
import { supabase, configured, CLASSIC, arrival, arrived } from "./lib/supabase.js";
import { T, loadWords, pickLanguage } from "./lib/i18n.js";
import { applyTheme } from "./lib/theme.js";
import * as api from "./lib/api.js";
import SignIn, { SetPassword } from "./pages/SignIn.jsx";
import Search from "./components/Search.jsx";
import SidePanel from "./components/SidePanel.jsx";
import Icon, { TONE } from "./components/Icon.jsx";
import Snapshot from "./pages/snapshot/Snapshot.jsx";
import Nda, { Signed } from "./components/Nda.jsx";
import { call } from "./lib/service.js";
// Each page loads when first opened (the Quick Snapshot, the usual first page, comes with the app).
// Each page's code, fetched ahead once the app has opened (so moving between pages never waits on a download).
const LOAD = {};
const TradeLog = lazy(LOAD.TradeLog = () => import("./pages/tradelog/TradeLog.jsx"));
const Asset = lazy(LOAD.Asset = () => import("./pages/asset/Asset.jsx"));
const Settings = lazy(LOAD.Settings = () => import("./pages/settings/Settings.jsx"));
const SearchPage = lazy(LOAD.SearchPage = () => import("./pages/SearchPage.jsx"));
const Signals = lazy(LOAD.Signals = () => import("./pages/signals/Signals.jsx"));
const Tides = lazy(LOAD.Tides = () => import("./pages/tides/Tides.jsx"));
const Mood = lazy(LOAD.Mood = () => import("./pages/mood/Mood.jsx"));
const Logbook = lazy(LOAD.Logbook = () => import("./pages/logbook/Logbook.jsx"));
const Alerts = lazy(LOAD.Alerts = () => import("./pages/alerts/Alerts.jsx"));
const Lattice = lazy(LOAD.Lattice = () => import("./pages/lattice/Lattice.jsx"));
const Help = lazy(LOAD.Help = () => import("./pages/help/Help.jsx"));
const Admin = lazy(LOAD.Admin = () => import("./pages/admin/Admin.jsx"));

// The new MarketNavi app (beta). One page so far, the Trade Log; each page moves across from the classic app in
// turn, and the classic app keeps running until every page is here.
const PAGES = [["snapshot", () => T("Quick Snapshot"), "camera"], ["signals", () => T("Signals"), "activity"], ["tides", () => T("Tides"), "waves-horizontal"], ["lattice", () => T("Lattice"), "puzzle"], ["logbook", () => T("Logbook"), "notebook"], ["tradelog", () => T("Trade Log"), "book-open"]];

// The address after # picks the page: #tradelog, or #asset/<asset key>/<tab>.
function readRoute() {
  const parts = window.location.hash.replace(/^#/, "").split("/").map((p) => { try { return decodeURIComponent(p); } catch (e) { return p; } });
  return parts[0] ? parts : ["snapshot"];
}

export default function App() {
  const [session, setSession] = useState(undefined);
  const [account, setAccount] = useState(null);
  const [ready, setReady] = useState(false);
  const [route, setRoute] = useState(readRoute);
  const [signed, setSigned] = useState(null);
  // 🔑 Arrived from a welcome or Forgot password link: choose a password first.
  const [needPassword, setNeedPassword] = useState(() => !!(arrival && arrival.access_token && ["invite", "recovery", "magiclink"].includes(arrival.type)));
  const page = route[0];

  useEffect(() => {
    applyTheme({});
    if (!configured) { setSession(null); return; }
    arrived.then(() => supabase.auth.getSession()).then(({ data }) => setSession(data.session || null));
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s || null));
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    let live = true;
    if (session === undefined) return;
    (async () => {
      if (!session) { await loadWords(pickLanguage(null)); if (live) setReady(true); return; }
      const user = session.user;
      // A barred account is signed out here too, as in the classic app.
      try { if (await api.rpc("account_barred")) { await supabase.auth.signOut(); return; } } catch (e) { /* no check function: carry on */ }
      // ✍️ Whether this tester still has to sign the beta NDA (checked on the data service, nda.py's own rules).
      const [settings, plan, nda] = await Promise.all([api.settings(user.id), api.plan(user.id), call("/nda", { timeout: 45000 }).catch(() => null)]);
      applyTheme(settings);
      await loadWords(pickLanguage(settings.language));
      // The admin role only shows the Admin link; the admin lists themselves are checked by the database.
      let admin = false;
      try { admin = (await api.rpc("is_admin")) === true; } catch (e) { /* no check function: not an admin */ }
      if (live) { setAccount({ user, settings, plan, admin, nda, zone: settings.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone }); setReady(true); }
    })();
    return () => { live = false; };
  }, [session && session.user && session.user.id, session === null]);

  // A new page keeps the one on screen until its code is ready (no flash of "Loading…"), and opens at the top.
  useEffect(() => {
    const f = () => {
      const next = readRoute();
      startTransition(() => setRoute((cur) => { if (cur[0] !== next[0]) window.scrollTo(0, 0); return next; }));
    };
    window.addEventListener("hashchange", f); return () => window.removeEventListener("hashchange", f);
  }, []);
  // Tell the database this account has the app open (the admin Members list: last seen, visits, time in the app), at
  // most once a minute while the tab is in view, as the classic app does.
  useEffect(() => {
    if (!account) return;
    let last = 0;
    const touch = () => { if (document.visibilityState !== "visible" || Date.now() - last < 60000) return; last = Date.now(); supabase.rpc("touch_activity").then(() => {}, () => {}); };
    touch();
    const t = setInterval(touch, 120000);
    document.addEventListener("visibilitychange", touch);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", touch); };
  }, [!!account]);
  // 👋 A new account that was invited: the inviter gets their 100 social points (once; the database checks).
  useEffect(() => { if (account) supabase.rpc("claim_invite_points").then(() => {}, () => {}); }, [!!account]);
  useEffect(() => {
    if (!account) return;
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 1500));
    idle(() => Object.values(LOAD).forEach((load) => load().catch(() => {})));
  }, [!!account]);

  if (!ready) return <div className="boot">{"MarketNavi"}</div>;
  if (!configured) return <div className="boot">{T("The new app isn't set up yet.")}</div>;
  if (!session) return <SignIn />;
  if (needPassword) return <SetPassword type={arrival.type} email={session.user.email || ""} onDone={() => setNeedPassword(false)} />;
  if (account && account.nda && account.nda.needed && !signed) {
    return <div className="shell"><header className="top"><a className="brand" href="#snapshot" aria-label="MarketNavi"><img src="/logo.png" alt="" width="28" height="28" /><span>MarketNavi</span></a></header>
      <main className="main"><Nda info={account.nda} onDone={(copy) => { setSigned(copy); setAccount({ ...account, nda: { ...account.nda, needed: false } }); }} /></main></div>;
  }
  if (page === "ndapreview" && account && account.admin && account.nda && account.nda.title) {
    return <div className="shell"><main className="main"><Nda info={account.nda} preview onClose={() => { window.location.hash = "admin/beta"; }} /></main></div>;
  }

  return (
    <div className="shell">
      <header className="top">
        <a className="brand" href="#snapshot" aria-label="MarketNavi">
          <img src="/logo.png" alt="" width="28" height="28" />
          <span>MarketNavi</span>
          <span className="beta" title={T("The new MarketNavi app, being built page by page. The classic app keeps working meanwhile.")}>{T("New · beta")}</span>
        </a>
        <Search />
        <nav className="pages" aria-label={T("Pages")}>
          {PAGES.map(([k, label, icon]) => <a key={k} href={`#${k}`} className={page === k ? "on" : ""} aria-current={page === k ? "page" : undefined} style={{ "--pc": `var(--t-${TONE[icon] || "gold"})` }}><Icon n={icon} size={20} /><span>{label()}</span></a>)}
        </nav>
        <div className="right">
          <SidePanel onScreen={page === "asset" ? `The person is looking at the asset page for ${route[1]} (${route[2] || "chart"} tab).` : page === "search" ? `The person searched for “${route[1]}”.` : `The person is on the ${page} page.`} />
          <a className="ghost icon" href={CLASSIC} title={T("Everything not moved across yet is in the classic app.") + " · " + T("Classic app")} aria-label={T("Classic app")}>
            <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4h6v6M20 4 10 14M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>
          </a>
          <Bell on={page === "alerts"} />
          {account && account.admin && <a className={"ghost icon" + (page === "admin" ? " on" : "")} href="#admin" title="Admin" aria-label="Admin" aria-current={page === "admin" ? "page" : undefined}><Icon n="shield" /></a>}
          <a className={"ghost icon" + (page === "help" ? " on" : "")} href="#help" title={T("Help and guides")} aria-label={T("Help and guides")} aria-current={page === "help" ? "page" : undefined}><Icon n="circle-question-mark" /></a>
          <a className={"ghost icon" + (page === "settings" ? " on" : "")} href="#settings" title={T("Settings")} aria-label={T("Settings")} aria-current={page === "settings" ? "page" : undefined}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
          </a>
        </div>
      </header>
      <main className="main">
        {signed && <Signed copy={signed} onClose={() => setSigned(null)} />}
        <Suspense fallback={<div className="page"><div className="empty" style={{ height: 300 }}>{T("Loading…")}</div></div>}>
        {page === "snapshot" && account && <Snapshot account={account} />}
        {page === "signals" && account && <Signals key={route[1] || "crypto"} market={route[1] || "crypto"} account={account} />}
        {page === "tides" && account && <Tides account={account} />}
        {page === "logbook" && account && <Logbook account={account} />}
        {page === "alerts" && account && <Alerts />}
        {page === "mood" && account && <Mood key={route[1] || "crypto"} market={route[1] || "crypto"} account={account} />}
        {page === "tradelog" && account && <TradeLog account={account} view={route[1]} />}
        {page === "asset" && account && <Asset key={route[1]} assetKey={route[1]} tab={route[2]} account={account} />}
        {page === "search" && account && <SearchPage key={route[1]} q={route[1] || ""} />}
        {page === "settings" && account && <Settings account={account} section={route[1]} />}
        {page === "lattice" && account && <Lattice section={route[1]} start={route[2]} />}
        {page === "help" && account && <Help topic={route[1]} account={account} />}
        {page === "admin" && account && (account.admin ? <Admin section={route[1]} account={account} /> : <Snapshot account={account} />)}
        </Suspense>
      </main>
    </div>
  );
}

// 🔔 Alerts, with how many are unread (checked when the app opens and every 5 minutes).
function Bell({ on }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    const count = async () => {
      try {
        const { data: u } = await supabase.auth.getUser();
        const { count: c } = await supabase.from("user_notifications").select("id", { count: "exact", head: true })
          .eq("user_id", u.user.id).eq("is_read", false).neq("alert_type", "group_invite").not("alert_type", "like", "%_HELD");
        if (live) setN(c || 0);
      } catch (e) { /* no count */ }
    };
    count();
    const t = setInterval(count, 5 * 60000);
    const f = () => count();
    window.addEventListener("hashchange", f);
    return () => { live = false; clearInterval(t); window.removeEventListener("hashchange", f); };
  }, []);
  return (
    <a className={"ghost icon bell" + (on ? " on" : "")} href="#alerts" title={n ? T("{n} unread alerts", { n }) : T("Alerts")} aria-label={n ? T("{n} unread alerts", { n }) : T("Alerts")}>
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21a2 2 0 0 0 4 0" /></svg>
      {n > 0 && <span className="badge">{n > 99 ? "99+" : n}</span>}
    </a>
  );
}
