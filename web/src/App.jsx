import React, { useEffect, useState } from "react";
import { supabase, configured, CLASSIC } from "./lib/supabase.js";
import { T, loadWords, pickLanguage } from "./lib/i18n.js";
import { applyTheme } from "./lib/theme.js";
import * as api from "./lib/api.js";
import SignIn from "./pages/SignIn.jsx";
import TradeLog from "./pages/tradelog/TradeLog.jsx";
import Asset from "./pages/asset/Asset.jsx";
import Search from "./components/Search.jsx";
import SidePanel from "./components/SidePanel.jsx";
import Settings from "./pages/settings/Settings.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import Snapshot from "./pages/snapshot/Snapshot.jsx";
import Signals from "./pages/signals/Signals.jsx";
import Tides from "./pages/tides/Tides.jsx";

// The new MarketNavi app (beta). One page so far, the Trade Log; each page moves across from the classic app in
// turn, and the classic app keeps running until every page is here.
const PAGES = [["snapshot", () => T("Quick Snapshot")], ["signals", () => T("Signals")], ["tides", () => T("Tides")], ["tradelog", () => T("Trade Log")]];

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
          <a className="ghost" href={CLASSIC} title={T("Everything not moved across yet is in the classic app.")}>{T("Classic app")}</a>
          <a className={"ghost icon" + (page === "settings" ? " on" : "")} href="#settings" title={T("Settings")} aria-label={T("Settings")} aria-current={page === "settings" ? "page" : undefined}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
          </a>
        </div>
      </header>
      <main className="main">
        {page === "snapshot" && account && <Snapshot account={account} />}
        {page === "signals" && account && <Signals key={route[1] || "crypto"} market={route[1] || "crypto"} account={account} />}
        {page === "tides" && account && <Tides account={account} />}
        {page === "tradelog" && account && <TradeLog account={account} />}
        {page === "asset" && account && <Asset key={route[1]} assetKey={route[1]} tab={route[2]} account={account} />}
        {page === "search" && account && <SearchPage key={route[1]} q={route[1] || ""} />}
        {page === "settings" && account && <Settings account={account} section={route[1]} />}
      </main>
    </div>
  );
}
