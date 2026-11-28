import React, { useEffect, useState } from "react";
import { T } from "../lib/i18n.js";
import * as social from "../lib/social.js";
import Icon, { Tile } from "./Icon.jsx";
import { ConfirmButton } from "./Confirm.jsx";

// 👥 Communities, as the classic app: a community is a small private circle (up to 50 people) whose members can post
// to each other in the chat. It starts with the first invite: press the add-person icon beside a name in the chat or
// comments, type a new community name (or pick one you lead), and they get an invite under the bell to accept.
// Settings › Chat & privacy lists the communities you lead (members, remove, invite by name, delete) and the ones
// you belong to (members, leave). Removing, leaving and deleting ask first, in place.

export const INVITE_NOTE = (c) => ({
  ok: T("Invite sent."),
  member: T("They are already in that community."),
  pending: T("They already have an invite to that community."),
  limit: T("You already lead 20 communities."),
  full: T("That community already has 50 members."),
  name: T("Enter a community name of up to 40 characters."),
  missing: T("Choose a community you lead, or enter a new name."),
  self: T("That invite couldn't be sent. Please try again."),
}[c] || T("That invite couldn't be sent. Please try again."));

// The box under a name: a new community, or one you lead.
export function InviteBox({ person, groups, onClose, onSent }) {
  const led = (groups || []).filter((g) => g.is_leader);
  const [pick, setPick] = useState(led.length ? String(led[0].id) : "new");
  const [name, setName] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (pick === "new" && !name.trim()) { setMsg(["bad", INVITE_NOTE("name")]); return; }
    setBusy(true);
    const c = await social.invite(person.id, pick === "new" ? name : "", pick === "new" ? null : pick);
    setBusy(false);
    setMsg([c === "ok" ? "ok" : "bad", INVITE_NOTE(c)]);
    if (c === "ok") { onSent && onSent(); setTimeout(onClose, 2000); }
  };
  return (
    <div className="reportbox invitebox" role="group" aria-label={T("Invite {name} to a community", { name: person.name })}>
      <b>{T("Invite {name} to a community", { name: person.name })}</b>
      <select value={pick} onChange={(e) => { setPick(e.target.value); setMsg(null); }} aria-label={T("Community")}>
        {led.map((g) => <option key={g.id} value={String(g.id)}>{g.name}</option>)}
        <option value="new">{T("A new community…")}</option>
      </select>
      {pick === "new" && <input type="text" maxLength={40} value={name} onChange={(e) => setName(e.target.value)} placeholder={T("New community name")} aria-label={T("New community name")} autoFocus />}
      {msg && <p className={"note " + (msg[0] === "ok" ? "good" : "bad")}>{msg[1]}</p>}
      <div className="row">
        <button type="button" className="primary sm" disabled={busy || (msg && msg[0] === "ok")} onClick={send}><Icon n="user-plus" size={15} /> {T("Invite")}</button>
        <button type="button" className="ghost sm" onClick={onClose}>{T("Cancel")}</button>
      </div>
      <span className="m">{T("They get an invite under the bell, and join when they accept it.")}</span>
    </div>
  );
}

const Face = ({ p }) => <span className="cav" aria-hidden="true">{p.avatar ? <img src={p.avatar} alt="" /> : String(p.name || "M").slice(0, 1).toUpperCase()}</span>;

function FindToInvite({ group, onSent }) {
  const [who, setWho] = useState(""), [people, setPeople] = useState([]), [msg, setMsg] = useState(null);
  useEffect(() => { let live = true; social.findPeople(who).then((p) => live && setPeople(p)); return () => { live = false; }; }, [who]);
  const inGroup = new Set((group.people || []).map((p) => String(p.id)));
  const send = async (p) => {
    const c = await social.invite(p.id, "", group.id);
    setMsg([c === "ok" ? "ok" : "bad", INVITE_NOTE(c)]); setWho("");
    if (c === "ok") onSent();
  };
  return (
    <div className="cmfind">
      <div className="wladd">
        <Icon n="user-plus" size={16} />
        <input type="search" value={who} onChange={(e) => { setWho(e.target.value); setMsg(null); }} placeholder={T("Invite someone: find a member by name")} aria-label={T("Invite someone: find a member by name")} />
        {who.trim().length >= 2 && <div className="wlhits">{people.filter((p) => !inGroup.has(String(p.id))).map((p) => <button key={p.id} type="button" onClick={() => send(p)}><b>{p.name}</b></button>)}
          {!people.filter((p) => !inGroup.has(String(p.id))).length && <span className="m" style={{ padding: "8px 12px" }}>{T("No match.")}</span>}</div>}
      </div>
      {msg && <p className={"note " + (msg[0] === "ok" ? "good" : "bad")}>{msg[1]}</p>}
    </div>
  );
}

function Community({ g, reload }) {
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");
  const people = g.people || [];
  const count = (g.members || []).length || people.length;
  const act = async (fn) => { setErr(""); try { await fn(); } catch (e) { setErr(T("That didn't work. Please try again.")); } reload(); };
  const remove = async (p) => {
    const c = await social.removeMember(g.id, p.id);
    if (c === "self") setErr(T("The leader stays until the community is deleted."));
    else if (c !== "ok") setErr(T("That person couldn't be removed. Please try again."));
    reload();
  };
  return (
    <div className={"cmty" + (open ? " open" : "")}>
      <div className="cmhead">
        <button type="button" className="cmname" onClick={() => setOpen(!open)} aria-expanded={open}>
          <Tile n="users" size={16} />
          <span><b>{g.name}</b><span className="m">{g.is_leader ? (count === 1 ? T("1 member") : T("{n} members", { n: count })) : g.leader_name}</span></span>
          <Icon n={open ? "chevron-down" : "chevron-right"} size={16} />
        </button>
        {g.is_leader
          ? <ConfirmButton className="ghost icon" title={T("Delete this community")} ask={T("Delete this community? Members will lose it.")} yes={T("Delete community")} onYes={() => act(() => social.deleteCommunity(g.id))}><Icon n="trash" size={16} /></ConfirmButton>
          : <ConfirmButton className="ghost sm" title={T("Leave community")} ask={T("Leave this community?")} yes={T("Leave community")} onYes={() => act(() => social.leaveCommunity(g.id))}><Icon n="log-out" size={15} /> {T("Leave")}</ConfirmButton>}
      </div>
      {err && <p className="note bad">{err}</p>}
      {open && (
        <div className="cmbody">
          {people.map((p) => (
            <div key={p.id} className="cmperson">
              <Face p={p} /><span className="cmpname">{p.name}</span>
              {String(p.id) === String(g.leader_id) ? <span className="tag">{T("Leader")}</span>
                : g.is_leader && <ConfirmButton className="ghost icon" title={T("Remove from the community")} ask={T("Remove {name}?", { name: p.name })} yes={T("Remove")} onYes={() => remove(p)}><Icon n="x" size={15} /></ConfirmButton>}
            </div>
          ))}
          {g.is_leader && <FindToInvite group={g} onSent={reload} />}
        </div>
      )}
    </div>
  );
}

export default function Communities() {
  const [groups, setGroups] = useState(undefined);
  const load = () => social.communities().then(setGroups);
  useEffect(() => { load(); }, []);
  if (groups === undefined) return <p className="sub">{T("Loading…")}</p>;
  const led = groups.filter((g) => g.is_leader), joined = groups.filter((g) => !g.is_leader);
  if (!groups.length) return <p className="sub">{T("You have no communities yet. Press the add-person icon beside a name in the chat or comments to start one.")}</p>;
  return (
    <div className="cmlist">
      {led.length > 0 && <div className="rowtitle">{T("Communities you lead")}</div>}
      {led.map((g) => <Community key={g.id} g={g} reload={load} />)}
      {joined.length > 0 && <div className="rowtitle">{T("Communities you belong to")}</div>}
      {joined.map((g) => <Community key={g.id} g={g} reload={load} />)}
    </div>
  );
}
