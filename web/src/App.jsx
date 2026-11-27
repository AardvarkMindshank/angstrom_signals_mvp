import React, { useEffect, useState } from "react";
import { supabase, configured, CLASSIC } from "./lib/supabase.js";
import { T, loadWords, pickLanguage } from "./lib/i18n.js";
import { applyTheme } from "./lib/theme.js";
import * as api from "./lib/api.js";
import SignIn from "./pages/SignIn.jsx";
import TradeLog from "./pages/tradelog/TradeLog.jsx";
import Asset from "./pages/asset/Asset.jsx";
import Search from "./components/Search.jsx";

// The new MarketNavi app (beta). One page so far, the Trade Log; each page moves across from the classic app in
// turn, and the classic app keeps running until every page is here.
const PAGES = [["tradelog", () => T("Trade Log")]];

// The address after # picks the page: #tradelog, or #asset/<asset key>/<tab>.
function readRoute() {
  const parts = window.location.hash.replace(/^#/, "").split("/").map((p) => { try { return decodeURIComponent(p); } catch (e) { return p; } });
  return parts[0] ? parts : ["tradelog"];
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
        <a className="brand" href="#tradelog" aria-label="MarketNavi">
          <img src="/logo.png" alt="" width="28" height="28" />
          <span>MarketNavi</span>
          <span className="beta" title={T("The new MarketNavi app, being built page by page. The classic app keeps working meanwhile.")}>{T("New · beta")}</span>
        </a>
        <Search />
        <nav className="pages" aria-label={T("Pages")}>
          {PAGES.map(([k, label]) => <a key={k} href={`#${k}`} className={page === k ? "on" : ""} aria-current={page === k ? "page" : undefined}>{label()}</a>)}
        </nav>
        <div className="right">
          <a className="ghost" href={CLASSIC} title={T("Everything not moved across yet is in the classic app.")}>{T("Classic app")}</a>
          <button type="button" className="ghost" onClick={() => supabase.auth.signOut()} title={account && account.user.email}>{T("Log out")}</button>
        </div>
      </header>
      <main className="main">
        {page === "tradelog" && account && <TradeLog account={account} />}
        {page === "asset" && account && <Asset key={route[1]} assetKey={route[1]} tab={route[2]} account={account} />}
      </main>
    </div>
  );
}
