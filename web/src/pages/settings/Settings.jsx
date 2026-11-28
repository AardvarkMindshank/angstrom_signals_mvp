import React, { useEffect, useMemo, useRef, useState } from "react";
import Icon, { Lead, plain, Tile } from "../../components/Icon.jsx";
import { useDelayed, UndoButton } from "../../components/Confirm.jsx";
import { T, lang } from "../../lib/i18n.js";
import { applyTheme } from "../../lib/theme.js";
import { supabase, SUPABASE_URL } from "../../lib/supabase.js";
import * as acct from "../../lib/account.js";
import { universe, match, keyFor, watchlists, coinLabel } from "../../lib/assets.js";
import { call } from "../../lib/service.js";
import { assetHref } from "../../components/Search.jsx";
import Communities from "../../components/Communities.jsx";
import Push from "../../components/Push.jsx";

// ⚙️ Settings: one page, sections down the left, each choice saved the moment it changes. Everything is stored
// where the classic app keeps it, so both apps stay in step.
const SECTIONS = () => [
  ["account", T("Account"), "user"],
  ["display", T("Display & language"), "sun-moon"],
  ["markets", T("Markets & watchlists"), "chart-candlestick"],
  ["alerts", T("Alerts & email"), "bell"],
  ["logbook", T("Logbook & podcasts"), "notebook"],
  ["ai", T("AI"), "sparkles"],
  ["privacy", T("Chat & communities"), "users"],
  ["lattice", T("Lattice"), "puzzle"],
];

export default function Settings({ account, section }) {
  const [prefs, setPrefs] = useState(null);
  const [alerts, setAlerts] = useState(undefined);
  const [saved, setSaved] = useState("");
  const timer = useRef(null);
  useEffect(() => { acct.preferences().then(setPrefs).catch(() => setPrefs({ settings: {}, crypto: {}, equity: {} })); acct.alertPrefs().then(setAlerts); }, []);
  const on = SECTIONS().some((s) => s[0] === section) ? section : "account";
  const flash = (ok) => { setSaved(ok ? T("Saved") : T("That didn't save. Please try again.")); clearTimeout(timer.current); timer.current = setTimeout(() => setSaved(""), 2200); };
  const set = async (updates) => {
    setPrefs((p) => ({ ...p, settings: { ...p.settings, ...updates } }));
    try { await acct.saveSettings(updates); flash(true); } catch (e) { flash(false); }
  };
  const setAlert = async (updates) => {
    setAlerts((a) => ({ ...(a || {}), ...updates }));
    try { await acct.saveAlertPrefs(updates); flash(true); } catch (e) { flash(false); }
  };
  if (!prefs) return <div className="empty">{T("Loading…")}</div>;
  const s = prefs.settings;
  const props = { s, set, alerts, setAlert, prefs, setPrefs, account, flash };
  return (
    <div className="settings">
      <nav className="snav" aria-label={T("Settings")}>
        <h1>{T("Settings")}</h1>
        {SECTIONS().map(([k, l, d]) => (
          <a key={k} href={`#settings/${k}`} className={on === k ? "on" : ""} aria-current={on === k ? "page" : undefined}>
            <Tile n={d} size={17} />{l}
          </a>
        ))}
      </nav>
      <div className="sbody">
        {on === "account" && <Account {...props} />}
        {on === "display" && <Display {...props} />}
        {on === "markets" && <Markets {...props} />}
        {on === "alerts" && <Alerts {...props} />}
        {on === "logbook" && <Logbook {...props} />}
        {on === "ai" && <AI {...props} />}
        {on === "privacy" && <Privacy {...props} />}
        {on === "lattice" && <LatticeSet {...props} />}
      </div>
      <div className={"toast" + (saved ? " show" : "")} role="status" aria-live="polite">{saved}</div>
    </div>
  );
}

// ---- building blocks ---------------------------------------------------------------------------------------------

function Row({ title, help, children, wide }) {
  return (
    <div className={"srow2" + (wide ? " wide" : "")}>
      <div className="stext"><div className="stitle">{title}</div>{help && <div className="shelp">{help}</div>}</div>
      <div className="sctl">{children}</div>
    </div>
  );
}
function Switch({ on, onChange, label }) {
  return <button type="button" role="switch" aria-checked={!!on} aria-label={label} className={"switch" + (on ? " on" : "")} onClick={() => onChange(!on)}><span /></button>;
}
function Seg({ value, options, onChange, label }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={value === k} className={value === k ? "on" : ""} onClick={() => onChange(k)}>{l}</button>)}
    </div>
  );
}
function Section({ title, sub, children }) {
  return <section className="sgroup"><h2>{title}</h2>{sub && <p className="sub">{sub}</p>}<div className="srows">{children}</div></section>;
}

// ---- Account -------------------------------------------------------------------------------------------------------

const PLAN_LABEL = () => ({ free: T("Free"), plus: "Plus", pro: "Pro", elite: "Elite" });

function Account({ s, set, account, flash }) {
  const [p, setP] = useState(null);
  const [name, setName] = useState(""), [bio, setBio] = useState("");
  const [busy, setBusy] = useState(false);
  const file = useRef(null);
  useEffect(() => { acct.profile().then((x) => { setP(x); setName(x.display_name || ""); setBio(x.bio || ""); }); }, []);
  const save = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await acct.saveProfile({ display_name: name.trim() || null, bio: bio.trim() || null }); setP({ ...p, display_name: name.trim(), bio: bio.trim() }); flash(true); } catch (err) { flash(false); }
    setBusy(false);
  };
  const photo = async (f) => {
    if (!f) return; setBusy(true);
    try { const url = await acct.uploadAvatar(f); await acct.saveProfile({ avatar_url: url }); setP({ ...p, avatar_url: url }); flash(true); } catch (err) { flash(false); }
    setBusy(false);
  };
  return (
    <>
      <Section title={T("Your profile")} sub={T("How other members see you in comments and chat.")}>
        {p === null ? <p className="sub">{T("Loading…")}</p> : (
          <form className="profile" onSubmit={save}>
            <button type="button" className="avatar" onClick={() => file.current.click()} title={T("Change your photo")} aria-label={T("Change your photo")}>
              {p.avatar_url ? <img src={p.avatar_url} alt="" /> : <span>{(name || account.user.email || "?").slice(0, 1).toUpperCase()}</span>}
              <i>{T("Change")}</i>
            </button>
            <input ref={file} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => photo(e.target.files[0])} />
            <div className="form" style={{ flex: 1, minWidth: 220 }}>
              <label>{T("Display name")}<input type="text" maxLength={40} value={name} onChange={(e) => setName(e.target.value)} /></label>
              <label>{T("Short bio")}<textarea rows={2} maxLength={160} value={bio} onChange={(e) => setBio(e.target.value)} /></label>
              <div><button type="submit" className="primary" disabled={busy}>{T("Save profile")}</button></div>
            </div>
          </form>
        )}
      </Section>
      <Section title={T("Plan")}>
        <Row title={T("Account level: {plan}", { plan: PLAN_LABEL()[account.plan] || account.plan })} help={T("Free during the beta.")}>
          <a className="ghost" href="https://marketnavi.ai/pricing.html" target="_blank" rel="noopener noreferrer">{T("Upgrade")}</a>
        </Row>
        <Row title={T("Features not in my plan")} help={T("Hide keeps the screens simple: you only see what your plan includes. Grey out shows everything, with what your plan doesn't include greyed.")}>
          <Seg label={T("Features not in my plan")} value={s.plan_display === "grey" ? "grey" : "hide"} options={[["hide", T("Hide")], ["grey", T("Grey out")]]} onChange={(v) => set({ plan_display: v })} />
        </Row>
      </Section>
      <InviteFriend account={account} />
      <Section title={T("Sign-in")}>
        <Row title={account.user.email} help={T("The email you sign in with.")}>
          <button type="button" className="ghost" onClick={() => supabase.auth.signOut()}>{T("Log out")}</button>
        </Row>
      </Section>
    </>
  );
}

// 👋 Invite a friend, as the classic app: the invite is saved here and the worker emails it within five minutes. The
// inviter gets 100 social points when they join (claim_invite_points, when the new account first signs in).
const cleanEmail = (v) => { const t = String(v || "").trim().toLowerCase(); return /^[^@\s]+@[^@\s]+\.[^@\s.]+$/.test(t) ? t : ""; };
function InviteFriend({ account }) {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [list, setList] = useState(null);
  const load = () => supabase.from("invites").select("email, created_at, credited_at").order("created_at", { ascending: false }).limit(500)
    .then(({ data }) => setList(data || []), () => setList([]));
  useEffect(() => { load(); }, []);
  const send = async (e) => {
    e.preventDefault();
    const to = cleanEmail(email);
    if (!to) { setMsg(["bad", T("Enter a valid email address.")]); return; }
    if (to === String(account.user.email || "").toLowerCase()) { setMsg(["bad", T("Use someone else's email address.")]); return; }
    setBusy(true);
    const { error } = await supabase.from("invites").insert({ inviter_id: account.user.id, email: to });
    let m = ["ok", T("Invite sent.")];
    if (error) {
      const text = String(error.message || "").toLowerCase();
      if (error.code === "23505" || text.includes("duplicate")) {
        const { data } = await supabase.rpc("invite_again", { address: to });
        const c = String(data || "").replace(/"/g, "");
        m = c === "ok" ? ["ok", T("That invite was already saved. The email was sent again.")]
          : c === "recent" ? ["bad", T("They were emailed in the last day. Try again tomorrow.")]
          : c === "joined" ? ["ok", T("They have already joined.")] : ["bad", T("That invite couldn't be saved. Please try again.")];
      } else if (text.includes("invite limit")) m = ["bad", T("The day's invites are used. Try again tomorrow.")];
      else if (text.includes("someone else")) m = ["bad", T("Use someone else's email address.")];
      else m = ["bad", T("That invite couldn't be saved. Please try again.")];
    }
    setBusy(false); setMsg(m);
    if (m[0] === "ok") setEmail("");
    load();
  };
  const joined = (list || []).filter((r) => r.credited_at).length;
  return (
    <Section title={T("Invite a friend")} sub={T("Know an experienced trader who would suit the beta? We will email them. Seats are approved by our team, and you get 100 social points once they join.")}>
      <form className="invform" onSubmit={send}>
        <input type="email" value={email} onChange={(e) => { setEmail(e.target.value); setMsg(null); }} placeholder={T("name@example.com")} aria-label={T("Their email")} autoComplete="off" />
        <button type="submit" className="primary" disabled={busy || !email.trim()}><Icon n="send" size={15} /> {T("Send invite")}</button>
      </form>
      {msg && <p className={"note " + (msg[0] === "ok" ? "good" : "bad")}>{msg[1]}</p>}
      {list && list.length > 0 && (
        <div className="invlist">
          <div className="m">{T("Invited {n} · joined {j}", { n: list.length, j: joined })}</div>
          <ul>
            {list.map((r) => {
              const done = !!r.credited_at, when = String((done ? r.credited_at : r.created_at) || "").slice(0, 10);
              return <li key={r.email} title={done ? T("Joined on {date}", { date: when }) : T("Invited on {date}, not joined yet", { date: when })}>
                <Icon n={done ? "circle-check" : "hourglass"} size={15} tone={done ? "green" : false} /><span>{r.email}</span></li>;
            })}
          </ul>
        </div>
      )}
    </Section>
  );
}

// ---- Display & language ----------------------------------------------------------------------------------------------

function Display({ s, set }) {
  const [m, setM] = useState(null);
  useEffect(() => { acct.meta().then(setM); }, []);
  const mode = s.ui_mode || "auto";
  return (
    <>
      <Section title={T("Appearance")}>
        <Row title={T("Day or night")} help={T("Auto follows your device.")}>
          <Seg label={T("Day or night")} value={mode} options={[["day", <><Icon n="sun" size={16} /> {T("Day")}</>], ["night", <><Icon n="moon" size={16} /> {T("Night")}</>], ["auto", <><Icon n="sun-moon" size={16} /> {T("Auto")}</>]]}
            onChange={(v) => { applyTheme({ ...s, ui_mode: v }); set({ ui_mode: v }); }} />
        </Row>
      </Section>
      <Section title={T("Language")} sub={T("The app follows your browser's language until you pick one here.")}>
        <div className="langs">
          {(m ? m.languages : []).map((l) => (
            <button key={l.code} type="button" className={"lang" + (lang === l.code ? " on" : "")} aria-pressed={lang === l.code}
              onClick={async () => { await set({ language: l.code }); window.location.reload(); }}>
              <img src={`${import.meta.env.BASE_URL}flags/${l.flag}.svg`} alt="" width="28" height="21" />
              <span><b>{l.name}</b><span className="m">{l.english}</span></span>
            </button>
          ))}
        </div>
      </Section>
    </>
  );
}

// ---- Markets & watchlists ---------------------------------------------------------------------------------------------

function Markets({ s, set, prefs, setPrefs, flash }) {
  const crypto = s.trade_crypto !== false, equity = s.trade_equities !== false;
  const markets = crypto && equity ? "both" : crypto ? "crypto" : "equity";
  return (
    <>
      <Section title={T("Markets you trade")}>
        <Row title="" help={T("Which markets the app shows: tables, alerts and the daily summary.")}>
          <Seg label={T("Markets you trade")} value={markets} options={[["crypto", T("Crypto")], ["equity", T("Equities")], ["both", T("Both")]]}
            onChange={(v) => set({ trade_crypto: v !== "equity", trade_equities: v !== "crypto" })} />
        </Row>
      </Section>
      <Watchlist kind="crypto" title={T("Crypto watchlist")} list={prefs.crypto} setList={(l) => setPrefs((p) => ({ ...p, crypto: l }))} flash={flash} />
      <Watchlist kind="equity" title={T("Equity watchlist")} list={prefs.equity} setList={(l) => setPrefs((p) => ({ ...p, equity: l }))} flash={flash} />
    </>
  );
}

function Watchlist({ kind, title, list, setList, flash }) {
  const later = useDelayed();
  const latest = useRef(list);
  latest.current = list;
  const [all, setAll] = useState([]);
  const [q, setQ] = useState("");
  useEffect(() => { universe().then((u) => setAll(u.filter((a) => a.kind === kind))).catch(() => {}); }, [kind]);
  const ids = Object.keys(list || {});
  const hits = useMemo(() => match(all, q, new Set(), 6).filter((a) => !ids.includes(a.id)), [all, q, ids.join(",")]);
  const save = async (next) => { setList(next); try { await acct.saveWatchlist(kind, next); watchlists.reset(); flash(true); } catch (e) { flash(false); } };
  const label = (id) => { const v = list[id]; return typeof v === "string" ? v : id; };
  return (
    <Section title={title} sub={T("The app's tables, alerts and daily summary follow these.")}>
      <div className="wl">
        {ids.map((id) => (
          <span key={id} className="wlitem">
            <a href={assetHref(keyFor(kind, id))} className={later.held(id) ? "gone" : ""}>{label(id)}</a>
            {later.held(id) ? <UndoButton onUndo={() => later.undo(id)} />
              : <button type="button" aria-label={T("Remove from your watchlist")} title={T("Remove from your watchlist")}
                onClick={() => later.run(id, () => { const n = { ...latest.current }; delete n[id]; save(n); })}><Icon n="x" size={14} /></button>}
          </span>
        ))}
        {!ids.length && <span className="m">{T("Nothing here yet.")}</span>}
      </div>
      <div className="wladd">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={kind === "crypto" ? T("Add a coin, e.g. Solana") : T("Add a company, e.g. Microsoft")} aria-label={T("Add to watchlist")} />
        {q.trim() && (
          <div className="wlhits">
            {hits.map((a) => <button key={a.id} type="button" onClick={() => { save({ ...list, [a.id]: kind === "crypto" ? coinLabel(a.name, a.symbol) : a.name }); setQ(""); }}><b>{a.symbol}</b> <span className="m">{a.name}</span> <span className="add">+ {T("Add")}</span></button>)}
            {!hits.length && <span className="m" style={{ padding: "8px 12px" }}>{T("No match.")}</span>}
          </div>
        )}
      </div>
    </Section>
  );
}

// ---- Alerts & email ------------------------------------------------------------------------------------------------

const CROSS_ROWS = [["p50", "+50"], ["p20", "+20"], ["m20", "−20"], ["m50", "−50"]];
const CROSS_WORDS = () => ({
  up_p50: T("gets strongly bullish"), dn_p50: T("fades back from strongly bullish"), up_p20: T("turns bullish (leaves neutral)"),
  dn_p20: T("falls back into neutral"), up_m20: T("rises back into neutral"), dn_m20: T("turns bearish (leaves neutral)"),
  up_m50: T("fades back from strongly bearish"), dn_m50: T("gets strongly bearish"), flip_up: T("flips from bearish to bullish"), flip_dn: T("flips from bullish to bearish"),
});
const DEFAULTS = { trend: ["up_p20", "dn_m20", "up_p50", "dn_m50", "flip_up", "flip_dn"], stretch: ["up_p50", "dn_m50", "dn_p50", "up_m50"], flow: ["up_p20", "dn_m20", "flip_up", "flip_dn"] };

function Borders({ reading, s, set }) {
  const ticked = Array.isArray(s[`${reading}_crossings`]) ? s[`${reading}_crossings`] : DEFAULTS[reading];
  const w = CROSS_WORDS();
  const flip = (k) => set({ [`${reading}_crossings`]: ticked.includes(k) ? ticked.filter((x) => x !== k) : [...ticked, k] });
  const chip = (k, arrow) => <button key={k} type="button" className={"xchip" + (ticked.includes(k) ? " on" : "")} aria-pressed={ticked.includes(k)} onClick={() => flip(k)}>{arrow} {w[k]}</button>;
  return (
    <div className="borders">
      {CROSS_ROWS.map(([code, v]) => (
        <div key={code} className="brow"><span className="bval">{v}</span>{chip(`up_${code}`, "▲")}{chip(`dn_${code}`, "▼")}</div>
      ))}
      <div className="brow"><span className="bval">⇅</span>{chip("flip_up", "⇧")}{chip("flip_dn", "⇩")}</div>
      {!ticked.length && <p className="sub">{T("Nothing ticked: no alerts for this reading.")}</p>}
    </div>
  );
}

function Alerts({ s, set, alerts, setAlert, account }) {
  const [m, setM] = useState(null);
  useEffect(() => { acct.meta().then(setM); }, []);
  if (alerts === undefined) return <p className="sub">{T("Loading…")}</p>;
  const a = alerts || {};
  const trendOn = a.enabled !== false, stretchOn = !!s.stretch_alert_on, flowOn = !!s.flow_alert_on;
  const line = Math.round(((Number(a.market_high_alert) || 65) - 50) * 2);
  const zone = a.digest_tz || Intl.DateTimeFormat().resolvedOptions().timeZone;
  const zones = m ? (m.zones.includes(zone) ? m.zones : [zone, ...m.zones]) : [zone];
  const brief = s.briefing && typeof s.briefing === "object" ? s.briefing : {};
  const pro = ["pro", "elite"].includes(account.plan);
  return (
    <>
      <Section title={T("Notifications on this device")} sub={T("Your alerts as phone or computer notifications, as well as under the bell. Turn them on for each device you use.")}>
        <Push />
      </Section>
      <Section title={T("Reading alerts")} sub={T("An alert when a reading of an asset on your watchlists crosses a colour border you tick, once the new colour holds at the daily close.")}>
        <Row title={<><Icon n="trending-up" size={16} /> {T("Trend alerts")}</>} wide={trendOn}>
          <Switch label={T("Trend alerts")} on={trendOn} onChange={(v) => setAlert({ enabled: v })} />
        </Row>
        {trendOn && <Borders reading="trend" s={s} set={set} />}
        <Row title={<><Icon n="target" size={16} /> {T("Stretch alerts")}</>} help={T("Off unless you switch it on. When switched on, the current colours are noted quietly; only new crossings alert.")}>
          <Switch label={T("Stretch alerts")} on={stretchOn} onChange={(v) => set({ stretch_alert_on: v })} />
        </Row>
        {stretchOn && <Borders reading="stretch" s={s} set={set} />}
        <Row title={<><Icon n="audio-lines" size={16} /> {T("Flow alerts")}</>}>
          <Switch label={T("Flow alerts")} on={flowOn} onChange={(v) => set({ flow_alert_on: v })} />
        </Row>
        {flowOn && <Borders reading="flow" s={s} set={set} />}
      </Section>
      <Section title={T("Other alerts")}>
        {"market_alerts_enabled" in a && (
          <Row title={<><Icon n="globe" size={16} /> {T("Market sentiment alerts")}</>} help={T("Alert when the crypto or stock market sentiment score crosses one of your lines. It covers the markets you have switched on. Market sentiment updates about every 12 hours.")}>
            <Switch label={T("Market sentiment alerts")} on={!!a.market_alerts_enabled} onChange={(v) => setAlert({ market_alerts_enabled: v })} />
          </Row>
        )}
        {a.market_alerts_enabled && (
          <Row title={<><Icon n="globe" size={16} /> {T("🌐 Market sentiment alert line (±)")}</>} help={T("Positive alert at +{n} or above, negative at −{n} or below.", { n: line })}>
            <input type="range" min="10" max="90" step="5" value={line} aria-label={T("🌐 Market sentiment alert line (±)")}
              onChange={(e) => { const L = +e.target.value; setAlert({ market_high_alert: 50 + L / 2, market_low_alert: 50 - L / 2 }); }} />
            <b className="rangev">±{line}</b>
          </Row>
        )}
        <Row title={<><Icon n="funnel" size={16} /> {T("Funnel alerts")}</>} help={T("A note when assets newly become Candidates in one of your funnels.")}>
          <Switch label={T("Funnel alerts")} on={s.funnel_alerts !== false} onChange={(v) => set({ funnel_alerts: v })} />
        </Row>
      </Section>
      <Section title={T("Emails")}>
        <Row title={<><Icon n="zap" size={16} /> {T("Instant alerts")}</>} help={T("One email as soon as a reading crosses a border you ticked, or market sentiment crosses your line.")}>
          <Switch label={T("Instant alerts")} on={a.instant_email !== false} onChange={(v) => setAlert({ instant_email: v })} />
        </Row>
        <Row title={<><Icon n="mail" size={16} /> {T("Daily alerts summary")}</>} help={T("One email a day with everything that crossed your lines.")}>
          <Switch label={T("Daily alerts summary")} on={!!a.digest_enabled} onChange={(v) => setAlert(v && !a.digest_enabled ? { digest_enabled: true, last_digest_at: new Date().toISOString(), digest_tz: zone, digest_hour: a.digest_hour ?? 8 } : { digest_enabled: v })} />
        </Row>
        {a.digest_enabled && (
          <>
            <Row title={<><Icon n="clipboard-list" size={16} /> {T("Include watchlist summary")}</>}><Switch label={T("Include watchlist summary")} on={a.digest_watchlist !== false} onChange={(v) => setAlert({ digest_watchlist: v })} /></Row>
            <Row title={<><Icon n="funnel" size={16} /> {T("Include funnels summary")}</>}><Switch label={T("Include funnels summary")} on={s.digest_funnels !== false} onChange={(v) => set({ digest_funnels: v })} /></Row>
          </>
        )}
        <Row title={T("Your morning time")} help={T("Your daily summary email is sent at this time, and your Passage Plan is ready an hour before it.")}>
          <select value={a.digest_hour ?? 8} onChange={(e) => setAlert({ digest_hour: +e.target.value, digest_tz: zone })} aria-label={T("Your morning time")}>
            {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}
          </select>
          <select value={zone} onChange={(e) => setAlert({ digest_tz: e.target.value })} aria-label={T("Time zone")}>
            {zones.map((z) => <option key={z} value={z}>{z.replace(/_/g, " ")}</option>)}
          </select>
        </Row>
        {a.instant_email === false && !a.digest_enabled && <p className="sub">{T("Both are off, so alerts only appear in the dashboard.")}</p>}
      </Section>
    </>
  );
}

// ---- 📓 Logbook & podcasts: the daily video, your Passage Plan, and the podcast feeds ------------------------------

function Logbook({ s, set, account }) {
  const [m, setM] = useState(null);
  useEffect(() => { acct.meta().then(setM); }, []);
  const brief = s.briefing && typeof s.briefing === "object" ? s.briefing : {};
  const pro = ["pro", "elite"].includes(account.plan);
  return (
    <>
      <Section title={<><Icon n="clapperboard" /> {T("Daily video")}</>}>
        <Row title={T("🎬 Play the daily video when I open the app")} help={T("Once a day, the first time you open the app after the new video is out. You can always watch it in 📸 Quick Snapshot or the 📓 Logbook.")}>
          <Switch label={T("Daily video")} on={s.daily_video_auto !== false} onChange={(v) => set({ daily_video_auto: v })} />
        </Row>
      </Section>
      <Section title={<><Icon n="compass" /> {T("Your Passage Plan")}</>} sub={pro ? T("Ready each day an hour before your morning time, which you set in Alerts & email.") : T("Written and spoken for your own watchlist and funnels each morning. Comes with Pro.")}>
        {pro && (
          <>
            <Row title={T("Email me when my Passage Plan is ready")} help={T("The daily summary email links it anyway.")}>
              <Switch label={T("Email me when my Passage Plan is ready")} on={!!brief.email} onChange={(v) => set({ briefing: { ...brief, email: v } })} />
            </Row>
            {m && Object.keys(m.voices).length > 0 && (
              <Row title={<><Icon n="audio-lines" size={16} /> {T("Passage Plan voice")}</>}>
                <select value={brief.voice || Object.keys(m.voices)[0]} onChange={(e) => set({ briefing: { ...brief, voice: e.target.value } })} aria-label={T("Passage Plan voice")}>
                  {Object.entries(m.voices).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </Row>
            )}
            <Row title={T("Your morning time")}><a className="linkish" href="#settings/alerts">{T("Alerts & email")} ›</a></Row>
          </>
        )}
      </Section>
      {pro && <Feeds brief={brief} set={set} />}
    </>
  );
}

function Feeds({ brief, set }) {
  const [copied, setCopied] = useState("");
  const token = brief.token || "";
  const url = (path) => `${SUPABASE_URL.replace(/\/$/, "")}/storage/v1/object/public/briefings/${path}`;
  const copy = (u) => { navigator.clipboard.writeText(u).then(() => { setCopied(u); setTimeout(() => setCopied(""), 1800); }).catch(() => {}); };
  const renew = () => {
    const bytes = crypto.getRandomValues(new Uint8Array(18));
    const fresh = btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    set({ briefing: { ...brief, token: fresh } });
  };
  const rows = [[<><Icon n="compass" size={16} /> {T("Your Passage Plan")}</>, "p", token ? url(`${token}/feed.xml`) : ""], [<><Icon n="globe" size={16} /> {T("Morning Outlook")}</>, "o", url("general/feed.xml")]];
  return (
    <Section title={<><Icon n="mic" /> {T("Listen in a podcast app")}</>} sub={T("Add these feeds to Apple Podcasts (Library, then Follow a Show by URL), Pocket Casts or Overcast, and each one downloads by itself. Your own feed is private: anyone with the link can listen, so keep it to yourself. Spotify can't take private feeds.")}>
      {rows.map(([name, key, u]) => u && (
        <Row key={key} title={name} help={<span className="feedurl">{u}</span>}>
          <button type="button" className="ghost" onClick={() => copy(u)}>{copied === u ? <><Icon n="check" size={16} /> {T("Copied")}</> : <><Icon n="copy" size={16} /> {T("Copy link")}</>}</button>
        </Row>
      ))}
      <Row title={<><Icon n="refresh-cw" size={16} /> {T("Make a new private link")}</>} help={T("The old link stops getting new plans.")}>
        <button type="button" className="ghost bordered" onClick={renew} title={T("Make a new private link")} aria-label={T("Make a new private link")}><Icon n="refresh-cw" /></button>
      </Row>
    </Section>
  );
}

// ---- AI ---------------------------------------------------------------------------------------------------------------

function AI({ s, set }) {
  const [got, setGot] = useState(null);
  useEffect(() => { call("/ai").then(setGot).catch(() => setGot({ providers: [], default: "claude", down: true })); }, []);
  const chosen = s.ai_navigator || (got && got.default);
  return (
    <Section title={T("AI Navigator")} sub={T("Which AI answers your questions in the Navigator. News summaries and sentiment scores use one AI for everyone, chosen by MarketNavi.")}>
      {!got ? <p className="sub">{T("Loading…")}</p> : got.down ? <p className="sub">{T("The AI choices couldn't load just now.")}</p> : (
        <Row title={T("Your Navigator AI")}>
          <Seg label={T("Your Navigator AI")} value={chosen} options={got.providers.map((p) => [p.id, p.label])} onChange={(v) => set({ ai_navigator: v })} />
        </Row>
      )}
    </Section>
  );
}

// ---- Chat & privacy -------------------------------------------------------------------------------------------------

function Privacy({ s, set }) {
  const blocked = Array.isArray(s.blocked) ? s.blocked : [];
  const names = s.blocked_names && typeof s.blocked_names === "object" ? s.blocked_names : {};
  return (
    <>
      <Section title={T("Communities")} sub={T("A community is a small private circle in the chat: its members can post to each other. Invite people with the add-person icon beside their name in the chat or comments.")}>
        <Communities />
      </Section>
      <Section title={T("Private messages")}>
        <Row title={T("Who can message me privately")} help={T("In the chat, a message to one person is private between the two of you.")}>
          <Seg label={T("Who can message me privately")} value={s.dm_from || "everyone"} options={[["everyone", T("Everyone")], ["favourites", T("Only my ⭐ favourites")], ["nobody", T("No one")]]} onChange={(v) => set({ dm_from: v })} />
        </Row>
      </Section>
      <Section title={T("Blocked people")} sub={T("You don't see their chat messages, and neither of you can message the other privately.")}>
        {!blocked.length ? <p className="sub">{T("No one blocked. Press the block icon beside a name in the chat to block someone.")}</p> : blocked.map((id) => (
          <Row key={id} title={names[id] || T("Member")}>
            <button type="button" className="ghost" onClick={() => { const n = { ...names }; delete n[id]; set({ blocked: blocked.filter((b) => b !== id), blocked_names: n }); }}>{T("Unblock")}</button>
          </Row>
        ))}
      </Section>
    </>
  );
}

// ---- Lattice -----------------------------------------------------------------------------------------------------------

function LatticeSet({ s, set }) {
  return (
    <Section title={T("Lattice")}>
      <Row title={T("Show provided starters and examples")} help={T("What MarketNavi provides (the starter Groups, the example Sets and the built-in alerts) sits in a folded “Provided by MarketNavi” section. Switch off to keep only your own. Hiding never changes anything.")}>
        <Switch label={T("Show provided starters and examples")} on={s.show_provided !== false} onChange={(v) => set({ show_provided: v })} />
      </Row>
    </Section>
  );
}
