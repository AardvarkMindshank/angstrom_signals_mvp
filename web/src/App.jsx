import React, { Suspense, lazy, useEffect, useState } from "react";
import { supabase, configured, CLASSIC } from "./lib/supabase.js";
import { T, loadWords, pickLanguage } from "./lib/i18n.js";
import { applyTheme } from "./lib/theme.js";
import * as api from "./lib/api.js";
import SignIn from "./pages/SignIn.jsx";
import Search from "./components/Search.jsx";
import SidePanel from "./components/SidePanel.jsx";
import Icon from "./components/Icon.jsx";
import Snapshot from "./pages/snapshot/Snapshot.jsx";
// Each page loads when first opened (the Quick Snapshot, the usual first page, comes with the app).
const TradeLog = lazy(() => import("./pages/tradelog/TradeLog.jsx"));
const Asset = lazy(() => import("./pages/asset/Asset.jsx"));
const Settings = lazy(() => import("./pages/settings/Settings.jsx"));
const SearchPage = lazy(() => import("./pages/SearchPage.jsx"));
const Signals = lazy(() => import("./pages/signals/Signals.jsx"));
const Tides = lazy(() => import("./pages/tides/Tides.jsx"));
const Mood = lazy(() => import("./pages/mood/Mood.jsx"));
const Logbook = lazy(() => import("./pages/logbook/Logbook.jsx"));
const Alerts = lazy(() => import("./pages/alerts/Alerts.jsx"));
const Lattice = lazy(() => import("./pages/lattice/Lattice.jsx"));
const Help = lazy(() => import("./pages/help/Help.jsx"));

// The new MarketNavi app (beta). One page so far, the Trade Log; each page moves across from the classic app in
// turn, and the classic app keeps running until every page is here.
const PAGES = [["snapshot", () => T("Quick Snapshot")], ["signals", () => T("Signals")], ["tides", () => T("Tides")], ["lattice", () => T("Lattice")], ["logbook", () => T("Logbook")], ["tradelog", () => T("Trade Log")]];

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
  const page = route[0];

  useEffect(() => {
    applyTheme({});
    if (!configured) { setSession(null); return; }
    supabase.auth.getSession().then(({ data }) => setSession(data.session || null));
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
      const [settings, plan] = await Promise.all([api.settings(user.id), api.plan(user.id)]);
      applyTheme(settings);
      await loadWords(pickLanguage(settings.language));
      if (live) { setAccount({ user, settings, plan, zone: settings.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone }); setReady(true); }
    })();
    return () => { live = false; };
  }, [session && session.user && session.user.id, session === null]);

  useEffect(() => { const f = () => setRoute(readRoute()); window.addEventListener("hashchange", f); return () => window.removeEventListener("hashchange", f); }, []);

  if (!ready) return <div className="boot">{"MarketNavi"}</div>;
  if (!configured) return <div className="boot">{T("The new app isn't set up yet.")}</div>;
  if (!session) return <SignIn />;

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
          {PAGES.map(([k, label]) => <a key={k} href={`#${k}`} className={page === k ? "on" : ""} aria-current={page === k ? "page" : undefined}>{label()}</a>)}
        </nav>
        <div className="right">
          <SidePanel onScreen={page === "asset" ? `The person is looking at the asset page for ${route[1]} (${route[2] || "chart"} tab).` : page === "search" ? `The person searched for “${route[1]}”.` : `The person is on the ${page} page.`} />
          <a className="ghost icon" href={CLASSIC} title={T("Everything not moved across yet is in the classic app.") + " · " + T("Classic app")} aria-label={T("Classic app")}>
            <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4h6v6M20 4 10 14M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>
          </a>
          <Bell on={page === "alerts"} />
          <a className={"ghost icon" + (page === "help" ? " on" : "")} href="#help" title={T("Help and guides")} aria-label={T("Help and guides")} aria-current={page === "help" ? "page" : undefined}><Icon n="circle-question-mark" /></a>
          <a className={"ghost icon" + (page === "settings" ? " on" : "")} href="#settings" title={T("Settings")} aria-label={T("Settings")} aria-current={page === "settings" ? "page" : undefined}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
          </a>
        </div>
      </header>
      <main className="main">
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
