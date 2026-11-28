import React, { useEffect, useMemo, useState } from "react";
import Icon from "./Icon.jsx";
import { ConfirmButton } from "./Confirm.jsx";
import { ReportButton, ReportBox } from "./Report.jsx";
import { T } from "../lib/i18n.js";
import * as social from "../lib/social.js";
import { watchlists, keyFor, universe } from "../lib/assets.js";
import { voteNote, deleteNote, postReply } from "../lib/assets.js";
import { signed } from "../lib/format.js";
import { assetHref } from "./Search.jsx";
import * as acct from "../lib/account.js";

const ago = (iso) => {
  if (!iso) return "";
  const m = (Date.now() - new Date(iso).getTime()) / 6e4;
  return m < 90 ? T("{n} min ago", { n: Math.max(1, Math.round(m)) }) : m < 2880 ? T("{n} hours ago", { n: Math.round(m / 60) }) : T("{n} days ago", { n: Math.round(m / 1440) });
};

// 💬 Social: members' comments on what you follow, and the chat. Lives in the side panel.
export default function Social({ visible }) {
  const [view, setView] = useState(() => { try { return localStorage.getItem("mn_social_view") || "comments"; } catch (e) { return "comments"; } });
  const pick = (v) => { setView(v); try { localStorage.setItem("mn_social_view", v); } catch (e) { /* private window */ } };
  return (
    <div className="social">
      <div className="seg full" role="tablist" aria-label={T("Social")}>
        <button type="button" role="tab" aria-selected={view === "comments"} className={view === "comments" ? "on" : ""} onClick={() => pick("comments")}>{T("Comments")}</button>
        <button type="button" role="tab" aria-selected={view === "chat"} className={view === "chat" ? "on" : ""} onClick={() => pick("chat")}>{T("Chat")}</button>
      </div>
      {view === "comments" ? <Comments visible={visible} /> : <Chat visible={visible} />}
    </div>
  );
}

function Comments({ visible }) {
  const [rows, setRows] = useState(null);
  const [scope, setScope] = useState("all");
  const [names, setNames] = useState({});
  const [keys, setKeys] = useState([]);
  useEffect(() => {
    watchlists().then((w) => setKeys([...Object.keys(w.crypto || {}).map((id) => keyFor("crypto", id)), ...Object.keys(w.equity || {}).map((id) => keyFor("equity", id)), "Mood|crypto", "Mood|stock", "Tides|macro"])).catch(() => {});
    universe().then((u) => setNames(Object.fromEntries(u.map((a) => [a.key, a.symbol])))).catch(() => {});
  }, []);
  const load = () => keys.length && social.stream(keys).then((r) => setRows(r.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))));
  useEffect(() => { if (visible && keys.length) { load(); return social.realtime(load); } }, [visible, keys.join(",")]);
  const label = (k) => (k === "Mood|crypto" ? T("Crypto market") : k === "Mood|stock" ? T("Stock market") : k === "Tides|macro" ? T("Tides") : names[k] || k.split("|")[1]);
  const shown = (rows || []).filter((r) => scope === "all" || (scope === "crypto" ? /^(Crypto|Mood\|crypto)/.test(r.asset_key) : /^(Stock|Mood\|stock)/.test(r.asset_key)));
  const act = async (fn) => { try { await fn(); } catch (e) { /* the row rules said no */ } load(); };
  return (
    <>
      <div className="chips" role="group" aria-label={T("Show")} style={{ margin: "10px 0 4px" }}>
        {[["all", T("All")], ["crypto", T("Crypto")], ["equity", T("Equities")]].map(([k, l]) => <button key={k} type="button" className={scope === k ? "on" : ""} aria-pressed={scope === k} onClick={() => setScope(k)}>{l}</button>)}
      </div>
      <p className="sub" style={{ margin: "4px 0 10px" }}>{T("Members' comments on your watchlist, the markets and the Tides. Comments last 12 hours; on the Tides, until the Tide changes. Open an asset's Community tab to add yours.")}</p>
      {rows === null ? <p className="sub">{T("Loading…")}</p> : !shown.length ? <p className="sub">{T("No comments in the last 12 hours.")}</p> : (
        <ol className="comments compact">
          {shown.map((n) => (
            <li key={n.id}>
              <Note n={n} kind="comment" act={act}
                head={n.asset_key.includes("|") && /^(Crypto|Stock)/.test(n.asset_key) ? <a className="tag" href={assetHref(n.asset_key, "community")}>{label(n.asset_key)}</a> : <span className="tag">{label(n.asset_key)}</span>} />
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

function Chat({ visible }) {
  const [rows, setRows] = useState(undefined);
  const [groups, setGroups] = useState([]);
  const [to, setTo] = useState({ kind: "public" });
  const [text, setText] = useState("");
  const [who, setWho] = useState(""), [people, setPeople] = useState([]);
  const [err, setErr] = useState("");
  const [mine, setMine] = useState({ favourites: [], blocked: [], blocked_names: {} });
  const load = () => social.chat().then(setRows);
  useEffect(() => {
    social.communities().then(setGroups);
    acct.preferences().then((p) => { const s = p.settings || {}; setMine({ favourites: (s.favourites || []).map(String), blocked: (s.blocked || []).map(String), blocked_names: s.blocked_names || {} }); }).catch(() => {});
  }, []);
  // ⭐ a favourite (they can message you when "Only my favourites" is chosen) or 🚫 block (their messages disappear).
  const person = {
    fav: (id) => mine.favourites.includes(String(id)),
    star: (id) => act(async () => { const f = mine.favourites.includes(String(id)) ? mine.favourites.filter((x) => x !== String(id)) : [...mine.favourites, String(id)]; setMine({ ...mine, favourites: f }); await acct.saveSettings({ favourites: f }); }),
    block: (id, name) => act(async () => { const b = [...new Set([...mine.blocked, String(id)])], n = { ...mine.blocked_names, [id]: name }; setMine({ ...mine, blocked: b, blocked_names: n }); await acct.saveSettings({ blocked: b, blocked_names: n }); }),
  };
  useEffect(() => { if (visible) { load(); return social.realtime(load); } }, [visible]);
  useEffect(() => { let live = true; social.findPeople(who).then((p) => live && setPeople(p)); return () => { live = false; }; }, [who]);
  const act = async (fn) => { setErr(""); try { await fn(); } catch (e) { setErr(T("That didn't send. Please try again.")); } load(); };
  const audience = to.kind === "group" ? (groups.find((g) => +g.id === +to.id) || {}).name : to.kind === "direct" ? to.name : T("Everyone");
  return (
    <>
      <form className="chatform" onSubmit={(e) => { e.preventDefault(); if (text.trim()) act(async () => { await social.post(text, to); setText(""); }); }}>
        <div className="chatto">
          <span className="m">{T("To")}</span>
          <select value={to.kind === "group" ? `g${to.id}` : to.kind === "direct" ? "d" : "public"} aria-label={T("Who it's for")}
            onChange={(e) => { const v = e.target.value; setTo(v === "public" ? { kind: "public" } : v === "d" ? { kind: "direct", id: "", name: "" } : { kind: "group", id: v.slice(1) }); }}>
            <option value="public">{T("Everyone")}</option>
            {groups.map((g) => <option key={g.id} value={`g${g.id}`}>{g.name}</option>)}
            <option value="d">{T("One person (private)")}</option>
          </select>
        </div>
        {to.kind === "direct" && !to.id && (
          <div className="wladd" style={{ margin: "6px 0" }}>
            <input type="search" value={who} onChange={(e) => setWho(e.target.value)} placeholder={T("Find a member by name")} aria-label={T("Find a member by name")} />
            {who.trim().length >= 2 && <div className="wlhits">{people.map((p) => <button key={p.id} type="button" onClick={() => { setTo({ kind: "direct", id: p.id, name: p.name }); setWho(""); }}><b>{p.name}</b></button>)}
              {!people.length && <span className="m" style={{ padding: "8px 12px" }}>{T("No match.")}</span>}</div>}
          </div>
        )}
        <div className="cform" style={{ margin: "6px 0 0" }}>
          <input type="text" maxLength={social.LIMIT} value={text} onChange={(e) => setText(e.target.value)} placeholder={T("Message {who}…", { who: audience || "" })} aria-label={T("Your message")} disabled={to.kind === "direct" && !to.id} />
          <button type="submit" className="primary" disabled={!text.trim() || (to.kind === "direct" && !to.id)}>{T("Send")}</button>
        </div>
      </form>
      {err && <p className="note bad">{err}</p>}
      {rows === undefined ? <p className="sub">{T("Loading…")}</p> : rows === null ? <p className="sub">{T("The chat isn't available just now.")}</p> : !rows.length ? <p className="sub">{T("No messages yet. Say hello.")}</p> : (
        <ol className="comments compact">
          {rows.map((n) => (
            <li key={n.id}>
              <Note n={n} kind="chat" act={act} person={person} head={n.audience === "group" ? <span className="tag"><Icon n="users" size={13} /> {n.group_name}</span> : n.audience === "direct" ? <span className="tag"><Icon n="lock" size={13} /> {n.mine ? T("to {name}", { name: n.recipient_name || T("Member") }) : T("private")}</span> : null} />
              {n.replies.map((r) => <div key={r.id} className="reply"><Note n={r} kind="chat" act={act} person={person} reply /></div>)}
              <ReplyBox onSend={(t) => act(() => social.post(t, null, n.id))} />
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

function Note({ n, kind, act, head, person, reply }) {
  const v = n.my_vote == null ? 0 : +n.my_vote;
  const [reporting, setReporting] = useState(false);
  const thumb = (x) => (kind === "chat" ? social.vote(n.id, x) : voteNote(n.id, kind, x));
  const del = () => (kind === "chat" ? social.remove(n.id) : deleteNote(n.id, kind));
  return (
    <div className="cnote">
      <span className="cav" aria-hidden="true">{n.avatar_url ? <img src={n.avatar_url} alt="" /> : String(n.author_name || "M").slice(0, 1)}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="chead"><b>{n.author_name || T("Member")}</b>{head}<span className="m">{ago(n.created_at)}</span></div>
        <div className="cbody">{n.body}</div>
        <div className="cacts">
          <button type="button" className={"linkish" + (v === 1 ? " on" : "")} onClick={() => act(() => thumb(v === 1 ? 0 : 1))} aria-label={T("Thumbs up")}><Icon n="thumbs-up" size={15} /> {+n.thumbs_up || 0}</button>
          <button type="button" className={"linkish" + (v === -1 ? " on" : "")} onClick={() => act(() => thumb(v === -1 ? 0 : -1))} aria-label={T("Thumbs down")}><Icon n="thumbs-down" size={15} /> {+n.thumbs_down || 0}</button>
          {n.responded_score != null && kind === "comment" && <span className="m">{T("on a mood of {s}", { s: signed(n.responded_score) })}</span>}
          {n.mine && <ConfirmButton onYes={() => act(del)}>{T("Delete")}</ConfirmButton>}
          {!n.mine && <ReportButton onOpen={() => setReporting(true)} />}
          {person && !n.mine && n.author_id && (
            <>
              <button type="button" className={"linkish" + (person.fav(n.author_id) ? " on" : "")} aria-pressed={person.fav(n.author_id)} onClick={() => person.star(n.author_id)}
                title={person.fav(n.author_id) ? T("Remove from favourites") : T("Add to favourites")}><Icon n="star" size={15} className={person.fav(n.author_id) ? "filled" : ""} /></button>
              <ConfirmButton title={T("Block: hide their messages and stop private messages both ways")} ask={T("Block {name}?", { name: n.author_name || T("Member") })} yes={T("Block")} onYes={() => person.block(n.author_id, n.author_name || "")}><Icon n="ban" size={15} /></ConfirmButton>
            </>
          )}
        </div>
        {reporting && <ReportBox n={n} place={kind === "chat" ? "chat" : "signal"} kind={reply ? "reply" : "comment"} onClose={() => setReporting(false)} />}
      </div>
    </div>
  );
}

function ReplyBox({ onSend }) {
  const [open, setOpen] = useState(false), [t, setT] = useState("");
  if (!open) return <button type="button" className="linkish reply-open" onClick={() => setOpen(true)}>{T("Reply")}</button>;
  return (
    <form className="cform reply" onSubmit={(e) => { e.preventDefault(); if (t.trim()) { onSend(t); setT(""); setOpen(false); } }}>
      <input type="text" maxLength={social.LIMIT} value={t} onChange={(e) => setT(e.target.value)} placeholder={T("Write a reply…")} aria-label={T("Your reply")} autoFocus />
      <button type="submit" className="primary" disabled={!t.trim()}>{T("Reply")}</button>
    </form>
  );
}
