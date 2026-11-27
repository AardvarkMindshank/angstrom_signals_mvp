import React, { useEffect, useMemo, useState } from "react";
import { supabase } from "../../lib/supabase.js";
import { call } from "../../lib/service.js";
import Icon from "../../components/Icon.jsx";

// 🛡️ Admin: the classic admin panel's lists (Members, Feedback, Reported comments, Beta requests, Blacklist), shown
// only to an account whose profile role is admin. English only, as in the classic app. Everything goes through the
// admin database functions with the admin's own sign-in, and each of them checks the admin role itself, so nobody
// else can read or change these lists even by opening #admin. The welcome and barred emails go through the data
// service (service/admin_mail.py). The NDA tools, AI provider choice and page timings stay in the classic app.
export const ADMIN_ICONS = ["users", "message-square-text", "flag", "ticket", "ban", "shield", "check", "x", "trash", "image", "mail", "user-plus", "chevron-up", "chevron-down", "download", "eye", "server-cog", "external-link"];

const SECTIONS = [["members", "users", "Members"], ["feedback", "message-square-text", "Feedback"], ["reports", "flag", "Reported comments"], ["beta", "ticket", "Beta requests"], ["blacklist", "ban", "Blacklist"], ["system", "server-cog", "System"]];

const FEEDBACK_STATUS = { submitted: "Submitted", under_review: "Under review", accepted: "Accepted", in_development: "In development", in_production: "In production", rejected: "Rejected", closed: "Closed" };
const FEEDBACK_NEXT = { submitted: ["under_review"], under_review: ["accepted", "rejected"], accepted: ["in_development"], in_development: ["in_production"], in_production: ["closed"], rejected: ["closed"] };
const REPORT_STATUS = { reported: "Reported", submitted: "Reported", under_review: "Under review", rejected: "Rejected", upheld: "Upheld" };
const REPORT_NEXT = { reported: ["under_review"], submitted: ["under_review"], under_review: ["rejected", "upheld"] };
const REPORT_REASONS = { promotion: "Promoting an asset", advice: "Presented as financial advice", harassment: "Harassment or a personal attack", spam: "Spam", other: "Something else" };
const CODES = { reason: "Write a short reason first.", step: "That status change is not the next step.", missing: "That item is no longer there.", forbidden: "This account cannot change that.", exists: "That email is already on the list.", self: "That is the admin account. It stays able to log in.", email: "Enter a valid email." };
const FAILED = "That could not be saved. Run the latest supabase_rls.sql in the Supabase SQL editor, then try again.";

// A rough AI cost at list prices ($ per million tokens in, out), as the classic panel works it out.
const AI_PRICES = [["claude-sonnet", 2, 10], ["claude-opus", 5, 25], ["claude-haiku", 1, 5], ["grok", 3, 15], ["gpt", 2.5, 10], ["gemini", 1.25, 10]];
function aiCost(r, s = "") {
  const p = AI_PRICES.find(([k]) => String(r.model || "").startsWith(k)) || ["", 3, 15];
  const n = (k) => Number(r[k + s] || 0);
  return (n("input") * p[1] + n("cache_read") * p[1] * 0.1 + n("cache_write") * p[1] * 1.25 + n("output") * p[2]) / 1e6;
}

async function rows(fn) {
  const { data, error } = await supabase.rpc(fn);
  if (error) return null;
  const d = typeof data === "string" ? JSON.parse(data) : data;
  return Array.isArray(d) ? d.filter((r) => r && typeof r === "object") : [];
}
async function code(fn, args) {
  const { data, error } = await supabase.rpc(fn, args);
  if (error) return "failed";
  return String(data || "").replace(/"/g, "").trim() || "failed";
}
const mail = (kind, address, name = "") => call("/admin/email", { method: "POST", body: { kind, address, name }, timeout: 30000 }).catch(() => ({ sent: false, why: "the data service could not be reached" }));
const since = (v) => (v ? (Date.now() - new Date(v).getTime()) / 1000 : null);
const validEmail = (s) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s);

export default function Admin({ section, account }) {
  const on = SECTIONS.some(([k]) => k === section) ? section : "members";
  const cur = SECTIONS.find(([k]) => k === on);
  const zone = (account && account.zone) || "UTC";
  const when = (v) => {
    if (!v) return "—";
    try { return new Intl.DateTimeFormat("en-GB", { timeZone: zone, day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(v)); } catch (e) { return String(v).replace("T", " ").slice(0, 16); }
  };
  return (
    <div className="settings admin">
      <nav className="snav" aria-label="Admin">
        <h1>Admin</h1>
        {SECTIONS.map(([k, ic, l]) => <a key={k} href={`#admin/${k}`} className={on === k ? "on" : ""} aria-current={on === k ? "page" : undefined}><Icon n={ic} /> {l}</a>)}
      </nav>
      <div className="sbody">
        <h2 className="helph"><Icon n={cur[1]} /> {cur[2]}</h2>
        {on === "members" && <Members when={when} />}
        {on === "feedback" && <Feedback when={when} />}
        {on === "reports" && <Reports when={when} />}
        {on === "beta" && <Beta when={when} nda={account && account.nda} />}
        {on === "blacklist" && <Blacklist when={when} />}
        {on === "system" && <System when={when} />}
      </div>
    </div>
  );
}

// One table you sort by clicking a column title (again to reverse). cols: [key, title, value(row), cell(row), num].
function SortTable({ cols, list, first, desc = true, rowKey = (r) => r.id, extra, lead }) {
  const [sort, setSort] = useState([first, desc]);
  const col = cols.find((c) => c[0] === sort[0]) || cols[0];
  const sorted = useMemo(() => {
    const v = col[2];
    return [...list].sort((a, b) => {
      const x = v(a), y = v(b);
      const nx = x == null || x === "", ny = y == null || y === "";
      if (nx || ny) return nx === ny ? 0 : nx ? 1 : -1;                         // blanks last either way
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return sort[1] ? -c : c;
    });
  }, [list, sort[0], sort[1]]);
  return (
    <div className="admscroll">
      <table className="t sig adm">
        <thead><tr>{lead && <th>{lead}</th>}{cols.map(([k, l, , , num]) => (
          <th key={k} className={num ? "r" : ""} aria-sort={sort[0] === k ? (sort[1] ? "descending" : "ascending") : undefined}>
            <button type="button" onClick={() => setSort([k, sort[0] === k ? !sort[1] : !!num])} title={`Sort by ${l}`}>
              {l}{sort[0] === k && <Icon n={sort[1] ? "chevron-down" : "chevron-up"} size={13} />}
            </button>
          </th>))}{extra && !lead && <th />}</tr></thead>
        <tbody>{sorted.map((r) => (
          <tr key={rowKey(r)}>{lead && <td>{extra(r)}</td>}{cols.map(([k, , v, cell, num]) => <td key={k} className={num ? "r" : ""}>{cell ? cell(r) : (v(r) ?? "—")}</td>)}{extra && !lead && <td className="r">{extra(r)}</td>}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function Face({ name, avatar, extra }) {
  const ok = /^https:\/\/[^\s"'<>\\]+$/.test(String(avatar || ""));
  const label = String(name || "Member").trim() || "Member";
  return <span className="admface">{ok ? <img src={avatar} alt="" /> : <i>{label[0].toUpperCase()}</i>}{label}{extra && <span className="m">{extra}</span>}</span>;
}

function Find({ value, set, place, children }) {
  return (
    <div className="admtools">
      <label className="admfind"><Icon n="search" size={15} /><input type="search" value={value} onChange={(e) => set(e.target.value)} placeholder={place} aria-label={place} /></label>
      {children}
    </div>
  );
}

function Note({ note }) {
  if (!note) return null;
  return <p className={"note " + (note[0] === "ok" ? "good" : "bad")}>{note[1]}</p>;
}

function useRows(fn) {
  const [list, setList] = useState(undefined);
  const load = () => rows(fn).then(setList);
  useEffect(() => { load(); }, [fn]);
  return [list, load];
}

function Loading({ list, missing }) {
  if (list === undefined) return <div className="empty" style={{ height: 200 }}>Loading…</div>;
  if (list === null) return <p className="sub">{missing}</p>;
  return null;
}

// 👥 Every account: when it joined and was last seen, how much it uses the app, and its AI use.
function Members({ when }) {
  const [list] = useRows("admin_members");
  const [q, setQ] = useState("");
  const [plan, setPlan] = useState("");
  if (!list) return <Loading list={list} missing="The Members list isn't switched on yet: run sql/2026-12-06_member_activity.sql in the Supabase SQL editor." />;
  const seen = list.map((r) => since(r.last_seen_at));
  const within = (s) => seen.filter((x) => x != null && x < s).length;
  const cost30 = list.reduce((a, r) => a + (r.ai || []).reduce((b, x) => b + aiCost(x, "_30d"), 0), 0);
  const find = q.trim().toLowerCase();
  const shown = list.filter((r) => (!find || `${r.name || ""} ${r.email || ""}`.toLowerCase().includes(find)) && (!plan || (r.plan || "pro") === plan));
  const state = (r) => { const s = since(r.last_seen_at); return s == null ? ["off", "Not seen yet"] : s < 300 ? ["now", "Active now"] : s < 86400 ? ["day", "Last 24 hours"] : s < 7 * 86400 ? ["week", "Last 7 days"] : ["off", "Earlier"]; };
  const ai = (r, s) => (r.ai || []).reduce((a, x) => a + aiCost(x, s), 0);
  const calls = (r, s) => (r.ai || []).reduce((a, x) => a + Number(x["calls" + s] || 0), 0);
  const num = (k) => (r) => Number(r[k] || 0);
  return (
    <>
      <div className="tiles admtiles">
        <div className="tile"><div className="l">Accounts</div><div className="v">{list.length}</div></div>
        <div className="tile" title="The app open in the last 5 minutes"><div className="l">Active now</div><div className="v">{within(300)}</div></div>
        <div className="tile"><div className="l">Last 24 hours</div><div className="v">{within(86400)}</div></div>
        <div className="tile"><div className="l">Last 7 days</div><div className="v">{within(7 * 86400)}</div></div>
        <div className="tile" title="A rough cost at list prices; the bill is on each AI maker's console"><div className="l">AI, 30 days</div><div className="v">${cost30.toFixed(2)}</div></div>
      </div>
      <Find value={q} set={setQ} place="Name or email">
        <select value={plan} onChange={(e) => setPlan(e.target.value)} aria-label="Plan">
          <option value="">All plans</option>{["free", "plus", "pro", "elite"].map((p) => <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>)}
        </select>
      </Find>
      <p className="sub">Click a column title to sort. Times are in your own time zone. AI cost is a rough figure at list prices.</p>
      <SortTable list={shown} first="seen" cols={[
        ["name", "Member", (r) => String(r.name || "").toLowerCase(), (r) => <span className="admwho"><i className={"dot " + state(r)[0]} title={state(r)[1]} /><Face name={r.name} avatar={r.avatar} />{r.role === "admin" && <span title="Admin"><Icon n="shield" size={14} /></span>}</span>],
        ["email", "Email", (r) => r.email || ""],
        ["plan", "Plan", (r) => r.plan || "pro", (r) => <span className={"plan " + (r.plan || "pro")}>{(r.plan || "pro")[0].toUpperCase() + (r.plan || "pro").slice(1)}</span>],
        ["joined", "Joined", (r) => r.created_at || "", (r) => when(r.created_at)],
        ["signin", "Last sign-in", (r) => r.last_sign_in_at || "", (r) => when(r.last_sign_in_at)],
        ["seen", "Last seen", (r) => r.last_seen_at || "", (r) => when(r.last_seen_at)],
        ["hours", "Hours", (r) => Number(r.seconds || 0) / 3600, (r) => (Number(r.seconds || 0) / 3600).toFixed(1), true],
        ["visits", "Visits", num("visits"), null, true],
        ["days", "Days", num("active_days"), null, true],
        ["sets", "Sets", num("sets"), null, true],
        ["scans", "Scans", num("scans"), null, true],
        ["funnels", "Funnels", num("funnels"), null, true],
        ["points", "Points", num("social_points"), null, true],
        ["chat", "Chat", num("chat_messages"), null, true],
        ["comments", "Comments", num("comments"), null, true],
        ["feedback", "Feedback", num("feedback"), null, true],
        ["ai30", "AI calls, 30 d", (r) => calls(r, "_30d"), null, true],
        ["ai", "AI calls", (r) => calls(r, ""), null, true],
        ["cost30", "AI $, 30 d", (r) => ai(r, "_30d"), (r) => ai(r, "_30d").toFixed(2), true],
        ["cost", "AI $", (r) => ai(r, ""), (r) => ai(r, "").toFixed(2), true],
        ["via", "Sign-in", (r) => ({ google: "Google", email: "Email" })[r.sign_in] || r.sign_in || ""],
      ]} />
    </>
  );
}

// A status you move one step at a time: pick the next step, then Save (a rejection needs a short reason).
function Step({ status, labels, next, onSave, confirmWord, needsReason }) {
  const [pick, setPick] = useState(status);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const opts = [status, ...(next[status] || [])];
  const save = async () => { setBusy(true); const ok = await onSave(pick, reason.trim()); setBusy(false); if (!ok) setPick(status); };
  return (
    <div className="admstep">
      <select value={pick} onChange={(e) => setPick(e.target.value)} disabled={opts.length < 2} aria-label="Status">
        {opts.map((s) => <option key={s} value={s}>{labels[s] || s}</option>)}
      </select>
      {pick !== status && (
        <>
          {needsReason === pick && <input type="text" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (shown to the member)" aria-label="Rejection reason" />}
          <span className="admrow">
            <button type="button" className="primary sm" disabled={busy || (needsReason === pick && reason.trim().length < 4)} onClick={save}>{(confirmWord && confirmWord[pick]) || "Save"}</button>
            <button type="button" className="ghost sm" onClick={() => setPick(status)}>Cancel</button>
          </span>
        </>
      )}
    </div>
  );
}

const why = (c) => CODES[c] || FAILED;

// 💬 Feedback from the Feedback box, moved through its steps (the member is told at each step).
function Feedback({ when }) {
  const [list, load] = useRows("admin_feedback");
  const [q, setQ] = useState("");
  const [closed, setClosed] = useState(false);
  const [note, setNote] = useState(null);
  const [shots, setShots] = useState({});
  useEffect(() => {
    const paths = (list || []).flatMap((r) => r.images || []).filter((p) => p && !shots[p]);
    if (!paths.length) return;
    supabase.storage.from("feedback").createSignedUrls(paths, 3600).then(({ data }) => {
      const m = {}; (data || []).forEach((x) => { if (x.signedUrl) m[x.path] = x.signedUrl; });
      setShots((s) => ({ ...s, ...m }));
    }).catch(() => {});
  }, [list]);
  if (!list) return <Loading list={list} missing="Feedback isn't ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor." />;
  const user = (r) => String(r.username || "").trim() || String(r.email || "").split("@")[0] || "Member";
  const find = q.trim().toLowerCase();
  const shown = list.filter((r) => (closed || r.status !== "closed") && (!find || [r.kind === "enhancement" ? "enhancement" : "issue", r.body, user(r), r.email, FEEDBACK_STATUS[r.status]].join(" ").toLowerCase().includes(find)));
  const open = list.filter((r) => r.status !== "closed").length;
  const save = (r) => async (next, reason) => {
    const c = await code("review_feedback", { note_id: Number(r.id), next_status: next, reason });
    if (c !== "ok") { setNote(["bad", why(c)]); return false; }
    setNote(["ok", `Moved to ${FEEDBACK_STATUS[next]}.`]); load(); return true;
  };
  return (
    <>
      <p className="sub">{open} open. Move each note one step at a time; the member is told at each step. A rejection needs a short reason.</p>
      <Find value={q} set={setQ} place="Search feedback"><label className="ptog"><input type="checkbox" checked={closed} onChange={(e) => setClosed(e.target.checked)} /> <span>Show closed</span></label></Find>
      <Note note={note} />
      {!shown.length ? <p className="sub">{find ? "No feedback matches that search." : "No open feedback."}</p> : (
        <SortTable list={shown} first="date" rowKey={(r) => `${r.id}-${r.status}`} cols={[
          ["type", "Type", (r) => (r.kind === "enhancement" ? "Enhancement" : "Issue")],
          ["comment", "Comment", (r) => String(r.body || "").toLowerCase(), (r) => (
            <div className="admtext">{String(r.body || "").trim() || "—"}
              {(r.images || []).length > 0 && <div className="admshots">{r.images.map((p, i) => shots[p] ? <a key={p} href={shots[p]} target="_blank" rel="noopener noreferrer" title="Open full size"><img src={shots[p]} alt="" /></a> : <span key={p} className="m"><Icon n="image" size={14} /> {i + 1}</span>)}</div>}
            </div>)],
          ["date", "Submitted", (r) => r.created_at || "", (r) => when(r.created_at)],
          ["user", "Member", (r) => user(r).toLowerCase(), (r) => <Face name={user(r)} avatar={r.avatar} />],
          ["email", "Email", (r) => r.email || ""],
          ["status", "Status", (r) => FEEDBACK_STATUS[r.status] || "", (r) => <Step status={FEEDBACK_STATUS[r.status] ? r.status : "submitted"} labels={FEEDBACK_STATUS} next={FEEDBACK_NEXT} needsReason="rejected" onSave={save(r)} />],
        ]} />
      )}
    </>
  );
}

// 🚩 Comments members reported: review, then reject the report or uphold it (which removes the comment).
function Reports({ when }) {
  const [list, load] = useRows("admin_reports");
  const [q, setQ] = useState("");
  const [decided, setDecided] = useState(false);
  const [note, setNote] = useState(null);
  if (!list) return <Loading list={list} missing="Reports aren't ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor." />;
  const where = (r) => `${r.place === "chat" ? "General chat" : "Social signals"} ${r.message_kind === "reply" ? "reply" : "comment"}${r.asset_key ? ` · ${String(r.asset_key).trim().replace("|", " · ")}` : ""}`;
  const person = (name, email) => String(name || "").trim() || String(email || "").split("@")[0] || "Member";
  const reason = (r) => REPORT_REASONS[r.reason] || r.reason || "";
  const find = q.trim().toLowerCase();
  const shown = list.filter((r) => (decided || !["rejected", "upheld"].includes(r.status)) && (!find || [r.comment_body, where(r), reason(r), r.note, person(r.author_name), person(r.reporter_name, r.reporter_email), r.reporter_email, REPORT_STATUS[r.status]].join(" ").toLowerCase().includes(find)));
  const open = list.filter((r) => !["rejected", "upheld"].includes(r.status)).length;
  const save = (r) => async (next) => {
    const c = await code("review_comment_report", { report_id: Number(r.id), next_status: next });
    if (c !== "ok") { setNote(["bad", why(c)]); return false; }
    setNote(["ok", next === "upheld" ? "Report upheld: the comment was removed." : `Moved to ${REPORT_STATUS[next]}.`]); load(); return true;
  };
  return (
    <>
      <p className="sub">{open} open. Mark a report under review, then reject it or uphold it. Upholding removes the comment and counts a warning against its author.</p>
      <Find value={q} set={setQ} place="Search reports"><label className="ptog"><input type="checkbox" checked={decided} onChange={(e) => setDecided(e.target.checked)} /> <span>Show decided</span></label></Find>
      <Note note={note} />
      {!shown.length ? <p className="sub">{find ? "No reports match that search." : "No open reports."}</p> : (
        <SortTable list={shown} first="date" rowKey={(r) => `${r.id}-${r.status}`} cols={[
          ["comment", "Comment", (r) => String(r.comment_body || "").toLowerCase(), (r) => <div className="admtext">{String(r.comment_body || "").trim() || "—"}<div className="m">{where(r)}</div></div>],
          ["reason", "Reason", (r) => reason(r).toLowerCase(), (r) => <div className="admtext">{reason(r) || "—"}{r.note && <div className="m">{r.note}</div>}</div>],
          ["date", "Reported", (r) => r.created_at || "", (r) => when(r.created_at)],
          ["author", "Author", (r) => person(r.author_name).toLowerCase(), (r) => <Face name={person(r.author_name)} avatar={r.author_avatar} extra={Number(r.warnings || 0) ? ` · ${r.warnings} warning${Number(r.warnings) === 1 ? "" : "s"}` : ""} />],
          ["reporter", "Reporter", (r) => person(r.reporter_name, r.reporter_email).toLowerCase(), (r) => <Face name={person(r.reporter_name, r.reporter_email)} avatar={r.reporter_avatar} />],
          ["status", "Status", (r) => REPORT_STATUS[r.status] || "", (r) => <Step status={REPORT_STATUS[r.status] ? r.status : "reported"} labels={{ ...REPORT_STATUS, rejected: "Reject the report", upheld: "Uphold and remove the comment" }} next={REPORT_NEXT} confirmWord={{ upheld: "Remove comment" }} onSave={save(r)} />],
        ]} />
      )}
    </>
  );
}

// 🎟️ Beta requests from the website form. Choose Approve or Decline on any rows, then Apply: nothing changes (and
// no email goes) until Apply. Approving lets that email create an account and sends the welcome email.
// The NDA column (nda.admin_cell): whether an approved tester has signed the current version.
function ndaCell(r, nda) {
  if (!nda || !nda.version) return ["—", "No NDA is set up yet.", ""];
  if (r.account_admin) return ["Admin", "Admins don't sign the NDA.", ""];
  if (r.status !== "approved") return ["—", "Asked to sign after approval.", ""];
  const from = String(nda.applies_from || "").slice(0, 10);
  if ((nda.exempt || []).includes(String(r.email || "").trim().toLowerCase()) || (from && r.created_at && String(r.created_at).slice(0, 10) < from))
    return ["Not asked", `Not asked: on the exempt list, or joined before ${from} when version ${nda.version} began to apply.`, ""];
  if (r.nda_version === nda.version && r.nda_signed_at) return [`Signed ${String(r.nda_signed_at).slice(0, 10)}`, `Signed version ${nda.version}.`, "good"];
  if (r.nda_version) return ["Older version", `Signed version ${r.nda_version}; asked to sign ${nda.version} at next sign-in.`, "warn"];
  if (!r.has_account) return ["No account yet", "Approved; signs when they first sign in.", "warn"];
  return ["Waiting", "Has an account but has not signed yet; asked at every sign-in.", "warn"];
}

async function ndaCopy(id) {
  const { data, error } = await supabase.rpc("admin_nda_copy", { p_id: Number(id) });
  if (error || !data || !data.pdf) return false;
  const bytes = Uint8Array.from(atob(data.pdf), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  const a = document.createElement("a"); a.href = url; a.download = `NDA-signed-${data.email || "tester"}-v${data.nda_version}.pdf`;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 5000);
  return true;
}

function Beta({ when, nda }) {
  const [list, load] = useRows("admin_beta_requests");
  const [open, setOpen] = useState(null);
  const [asking, setAsking] = useState(false);
  const [email, setEmail] = useState("");
  const [q, setQ] = useState("");
  const [decided, setDecided] = useState(false);
  const [picks, setPicks] = useState({});
  const [note, setNote] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { supabase.rpc("admin_signup_open").then(({ data }) => setOpen(data === true || data === "true")).catch(() => setOpen(false)); }, []);
  if (!list) return <Loading list={list} missing="Beta access is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor." />;
  const setSignup = async (v) => {
    setAsking(false);
    const { error } = await supabase.rpc("set_signup_open", { open_now: v });
    if (error) { setNote(["bad", FAILED]); return; }
    setOpen(v); setNote(["ok", v ? "Sign-up is open to everyone." : "Sign-up is closed: the closed beta is back."]);
  };
  const welcome = async (address, name, lead) => {
    const r = await mail("welcome", address, name);
    return r.sent ? `${lead} The welcome email was sent.` : `${lead} The welcome email was not sent: ${r.why}. Tell them yourself.`;
  };
  const approveEmail = async () => {
    const clean = email.trim().toLowerCase();
    if (!validEmail(clean)) { setNote(["bad", "Enter a valid email."]); return; }
    setBusy(true);
    const c = await code("add_beta_email", { address: clean });
    if (c !== "ok") { setBusy(false); setNote(["bad", c === "exists" ? "That email is already approved." : why(c)]); return; }
    const text = await welcome(clean, "", `${clean} is approved.`);
    setBusy(false); setEmail(""); setNote([text.includes("not sent") ? "bad" : "ok", text]);
  };
  const apply = async () => {
    setBusy(true);
    const notes = []; let bad = false;
    for (const [id, decision] of Object.entries(picks)) {
      const r = list.find((x) => String(x.id) === id);
      if (!r) continue;
      const c = await code("review_beta_request", { request_id: Number(id), decision });
      if (c !== "ok") { bad = true; notes.push(`${r.email}: ${c === "missing" ? "That request is no longer there." : why(c)}`); continue; }
      if (decision === "approved") { const t = await welcome(r.email, r.name, `${r.email} is approved.`); bad = bad || t.includes("not sent"); notes.push(t); }
      else notes.push(`${r.email} is declined. No email was sent, and they cannot create an account.`);
    }
    setPicks({}); setBusy(false); setNote([bad ? "bad" : "ok", notes.join(" ")]); load();
  };
  const find = q.trim().toLowerCase();
  const shown = list.filter((r) => (decided || r.status === "pending") && (!find || ["name", "email", "phone", "markets", "years_trading", "activity", "tools", "why", "country"].map((k) => r[k] || "").join(" ").toLowerCase().includes(find)));
  const pending = list.filter((r) => r.status === "pending").length;
  const choose = (r, d) => setPicks((p) => { const n = { ...p }; if (n[r.id] === d || r.status === d) delete n[r.id]; else n[r.id] = d; return n; });
  const count = Object.keys(picks).length;
  const STATUS = { pending: "Pending", approved: "Approved", declined: "Declined" };
  return (
    <>
      <p className="sub">{pending} pending. Requests arrive from the website form. Approve lets that email create an account and sends a welcome email; Decline (or taking approval back) sends none. People who already have an account keep it either way.</p>
      <div className="admsignup">
        <label className="ptog"><input type="checkbox" checked={!!open} disabled={open === null} onChange={() => setAsking(true)} /> <span>Open sign-up to everyone (public launch)</span></label>
        {asking && (
          <span className="admrow">
            <span className="m">{open ? "Close sign-up and go back to the closed beta?" : "Let anyone create an account?"}</span>
            <button type="button" className="primary sm" onClick={() => setSignup(!open)}>{open ? "Close sign-up" : "Open sign-up"}</button>
            <button type="button" className="ghost sm" onClick={() => setAsking(false)}>Cancel</button>
          </span>
        )}
      </div>
      <div className="admtools">
        <label className="admfind"><Icon n="user-plus" size={15} /><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} onKeyDown={(e) => e.key === "Enter" && approveEmail()} placeholder="Approve an email directly: name@example.com" aria-label="Email to approve" /></label>
        <button type="button" className="primary" disabled={busy || !email.trim()} onClick={approveEmail}>Approve email</button>
      </div>
      {nda && nda.version && (
        <div className="admsignup">
          <span className="m">{nda.enforce ? `NDA version ${nda.version}: ${list.filter((r) => r.nda_version === nda.version && r.nda_signed_at).length} signed. Testers sign at their first sign-in after approval; a signed copy is emailed to them and to admins.` : `NDA version ${nda.version} is set up but switched off: testers are not asked to sign yet.`}</span>
          <a className="ghost bordered btnlink" href="#ndapreview" title="See and try the signing page testers get. Nothing is recorded."><Icon n="eye" size={15} /> Preview the NDA page</a>
        </div>
      )}
      <Find value={q} set={setQ} place="Search names, emails, tools or reasons"><label className="ptog"><input type="checkbox" checked={decided} onChange={(e) => setDecided(e.target.checked)} /> <span>Show decided</span></label></Find>
      <Note note={note} />
      {count > 0 && <div className="admapply"><button type="button" className="primary" disabled={busy} onClick={apply}>{busy ? "Applying…" : `Apply ${count} decision${count === 1 ? "" : "s"}`}</button><button type="button" className="ghost" onClick={() => setPicks({})}>Clear</button></div>}
      {!shown.length ? <p className="sub">{decided || find ? "No request matches that search." : "Nothing pending."}</p> : (
        <SortTable list={shown} first="date" lead="Decide" cols={[
          ["date", "Applied", (r) => r.created_at || "", (r) => when(r.created_at)],
          ["name", "Name", (r) => r.name || ""],
          ["email", "Email", (r) => r.email || ""],
          ["phone", "Phone", (r) => r.phone || ""],
          ["country", "Country", (r) => r.country || ""],
          ["markets", "Markets", (r) => r.markets || ""],
          ["years", "Years", (r) => r.years_trading || ""],
          ["active", "Active", (r) => r.activity || ""],
          ["tools", "Tools", (r) => r.tools || "", (r) => <div className="admtext">{r.tools || "—"}</div>],
          ["why", "Why", (r) => r.why || "", (r) => <div className="admtext wide">{r.why || "—"}</div>],
          ["nda", "NDA", (r) => ndaCell(r, nda)[0], (r) => { const [t, tip, tone] = ndaCell(r, nda); return (
            <span className={"admstat " + tone} title={tip}>{t}{r.nda_id ? <button type="button" className="ghost icon sm" onClick={async () => { if (!(await ndaCopy(r.nda_id))) setNote(["bad", "The signed copy could not be read."]); }} title="Download the signed copy" aria-label="Download the signed copy"><Icon n="download" size={15} /></button> : null}</span>); }],
          ["status", "Status", (r) => r.status || "", (r) => <span className={"admstat " + r.status}>{STATUS[r.status] || r.status}{r.has_account ? <span className="m"> · has an account</span> : null}</span>],
        ]} extra={(r) => (
          <span className="admrow nowrap">
            <button type="button" className={"ghost icon" + (picks[r.id] === "approved" ? " on good" : "")} disabled={r.status === "approved"} aria-pressed={picks[r.id] === "approved"} onClick={() => choose(r, "approved")} title="Approve (sends the welcome email when you press Apply)" aria-label="Approve"><Icon n="check" /></button>
            <button type="button" className={"ghost icon" + (picks[r.id] === "declined" ? " on bad" : "")} disabled={r.status === "declined"} aria-pressed={picks[r.id] === "declined"} onClick={() => choose(r, "declined")} title={r.status === "approved" ? "Take approval back (no email) when you press Apply" : "Decline (no email) when you press Apply"} aria-label="Decline"><Icon n="x" /></button>
          </span>
        )} />
      )}
    </>
  );
}

// ⛔ Barred emails: a barred email can't log in or sign up, an open session is closed, and that address is emailed.
function Blacklist({ when }) {
  const [list, load] = useRows("admin_blacklist");
  const [email, setEmail] = useState("");
  const [q, setQ] = useState("");
  const [note, setNote] = useState(null);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState("");
  if (!list) return <Loading list={list} missing="The blacklist is not ready yet. Run the latest supabase_rls.sql in the Supabase SQL editor." />;
  const add = async () => {
    const clean = email.trim().toLowerCase();
    if (!validEmail(clean)) { setNote(["bad", "Enter a valid email."]); return; }
    setBusy(true);
    const c = await code("add_blacklist_email", { address: clean });
    if (c !== "ok") { setBusy(false); setNote(["bad", c === "forbidden" ? "This account cannot change the blacklist." : why(c)]); return; }
    const r = await mail("barred", clean);
    setBusy(false); setEmail(""); load();
    setNote(r.sent ? ["ok", `${clean} is barred. The email was sent.`] : ["bad", `${clean} is barred. The email was not sent: ${r.why}.`]);
  };
  const remove = async (address) => {
    setRemoving("");
    const c = await code("remove_blacklist_email", { address });
    setNote(c === "ok" ? ["ok", `${address} was removed.`] : ["bad", c === "missing" ? "That email is no longer on the list." : "That could not be removed."]);
    load();
  };
  const find = q.trim().toLowerCase();
  const shown = list.filter((r) => !find || String(r.email || "").toLowerCase().includes(find));
  return (
    <>
      <p className="sub">A barred email cannot log in or sign up. An open session is closed, and that address is emailed. Removing an email lets that person log in again.</p>
      <div className="admtools">
        <label className="admfind"><Icon n="ban" size={15} /><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} placeholder="Email to bar: name@example.com" aria-label="Email to bar" /></label>
        <button type="button" className="primary" disabled={busy || !email.trim()} onClick={add}>Add to blacklist</button>
      </div>
      <Find value={q} set={setQ} place="Search the blacklist" />
      <Note note={note} />
      {!shown.length ? <p className="sub">{find ? "No email matches that search." : "Nobody is barred."}</p> : (
        <SortTable list={shown} first="date" rowKey={(r) => r.email} cols={[
          ["email", "Email", (r) => String(r.email || "").toLowerCase(), (r) => r.email],
          ["date", "Barred", (r) => r.created_at || "", (r) => when(r.created_at)],
        ]} extra={(r) => removing === r.email ? (
          <span className="admrow nowrap"><button type="button" className="primary sm" onClick={() => remove(r.email)}>Remove</button><button type="button" className="ghost sm" onClick={() => setRemoving("")}>Cancel</button></span>
        ) : <button type="button" className="ghost icon" onClick={() => setRemoving(r.email)} title="Remove from the blacklist (lets this person log in again)" aria-label="Remove"><Icon n="trash" /></button>} />
      )}
    </>
  );
}

// 🛠️ System: which AI writes the shared news scores and the spoken briefings (for everyone), where each AI key goes,
// and whether the background lookups (earnings dates, the market overview strip) are working. Page timings and the
// push-key maker stay in the classic app: they are about the classic server itself.
const PROVIDERS = [["claude", "Claude (Anthropic)", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "https://console.anthropic.com/settings/keys"],
  ["grok", "Grok (xAI)", "XAI_API_KEY", "XAI_CHAT_MODEL", "https://console.x.ai"],
  ["chatgpt", "ChatGPT (OpenAI)", "OPENAI_API_KEY", "OPENAI_MODEL", "https://platform.openai.com/api-keys"],
  ["gemini", "Gemini (Google)", "GEMINI_API_KEY", "GEMINI_MODEL", "https://aistudio.google.com/apikey"]];
const USES = [["sentiment", "News sentiment scores", "Scores the headlines for every asset and both markets. Shared by everyone, so an admin picks it for the whole app; new scores use it from their next refresh (every 12 hours)."],
  ["briefing", "Spoken briefing scripts", "Writes the shared Morning Outlook, and the Passage Plans the background worker writes for the spoken plan when the member hasn't written one yet. Runs on the background worker, which has the Claude, Grok, ChatGPT and Gemini keys."]];
const ago = (s) => (s == null ? "never" : s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`);

function System() {
  const [ai, setAi] = useState(null);
  const [st, setSt] = useState(undefined);
  const [note, setNote] = useState(null);
  useEffect(() => {
    supabase.from("app_settings").select("value").eq("key", "ai").limit(1).then(({ data }) => setAi((data && data[0] && data[0].value) || {})).catch(() => setAi({}));
    call("/admin/status", { timeout: 60000 }).then((r) => setSt(r.ok ? r : null)).catch(() => setSt(null));
  }, []);
  const pick = async (use, p) => {
    const { error } = await supabase.rpc("app_setting_set", { p_key: "ai", p_patch: { [use]: p } });
    if (error) { setNote(["bad", /not allowed/.test(error.message || "") ? "Only an admin can change this." : "Could not save it. Run sql/2026-11-25_app_settings.sql in the Supabase SQL editor if it hasn't been run."]); return; }
    setAi({ ...ai, [use]: p });
    const name = (PROVIDERS.find((x) => x[0] === p) || [, p])[1];
    setNote(["ok", use === "sentiment" ? `News sentiment will be scored by ${name} from its next refresh.` : `Morning briefings will be written by ${name} from the next one.`]);
  };
  const e = st && st.earnings, o = st && st.overview;
  return (
    <>
      <section className="admsec">
        <h3>AI, for everyone</h3>
        {ai === null ? <p className="sub">Loading…</p> : USES.map(([use, label, tip]) => (
          <label key={use} className="admai" title={tip}>
            <span><b>{label}</b><span className="m">{tip}</span></span>
            <select value={ai[use] || "grok"} onChange={(ev) => pick(use, ev.target.value)} aria-label={label}>
              {PROVIDERS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
            </select>
          </label>
        ))}
        <Note note={note} />
        <p className="sub">Each AI needs its key where it runs: in Render (Environment) for the app and data service, and in GitHub (Settings › Secrets and variables › Actions) for the background worker. Add keys there yourself; never paste a key into a chat or a file.</p>
        <div className="admscroll"><table className="t adm" style={{ minWidth: 640 }}>
          <thead><tr><th>AI</th><th>Secret name</th><th>Model (secret to change it)</th><th>Get a key</th></tr></thead>
          <tbody>{PROVIDERS.map(([k, n, env, menv, at]) => <tr key={k}><td>{n}</td><td><code>{env}</code></td><td><code>{menv}</code></td><td><a href={at} target="_blank" rel="noopener noreferrer">{at.replace("https://", "")} <Icon n="external-link" size={13} /></a></td></tr>)}</tbody>
        </table></div>
      </section>
      <section className="admsec">
        <h3>Market overview strip</h3>
        {st === undefined ? <p className="sub">Loading…</p> : !o ? <p className="sub">The status could not be read just now.</p> : (
          <>
            <p className={"note " + (o.ago != null && o.ago < o.stale ? "good" : "bad")}>{o.readings ? `${o.readings} readings, saved by the background worker ${ago(o.ago)}.` : "Nothing saved yet."} The worker refreshes it about every {Math.round(o.refresh / 60)} minutes{o.ago != null && o.ago >= o.stale ? "; it looks stale, so check the worker's runs in GitHub Actions." : "."}</p>
            {o.errors.map((x, i) => <p key={i} className="m">{x}</p>)}
          </>
        )}
      </section>
      <section className="admsec">
        <h3>Earnings dates</h3>
        {st === undefined ? <p className="sub">Loading…</p> : !e ? <p className="sub">The saved earnings dates could not be read.</p> : !e.stocks ? <p className="sub">No stocks have been saved yet.</p> : (
          <>
            <p className="sub">{e.stocks} stocks: {e.with_date} with a date, {e.none_known} with none known, {e.never_checked} never checked. Last check: {ago(e.newest_check_ago)}. Oldest check: {ago(e.oldest_check_ago)}. A lookup runs about every 12 hours.</p>
            {e.with_date === 0 && e.stocks >= 3 && <p className="note bad">No stock has a date. The lookups may be failing, so check the Finnhub key and the worker's log.</p>}
            <SortTable list={e.lines} first="state" desc={false} rowKey={(r) => r.ticker} cols={[
              ["ticker", "Stock", (r) => r.ticker],
              ["next", "Next report", (r) => r.next_earnings || ""],
              ["state", "State", (r) => r.state],
              ["checked", "Checked", (r) => r.checked_ago, (r) => ago(r.checked_ago), true],
            ]} />
          </>
        )}
      </section>
    </>
  );
}
