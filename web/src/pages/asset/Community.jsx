import React, { useEffect, useState } from "react";
import Icon from "../../components/Icon.jsx";
import { T } from "../../lib/i18n.js";
import { crowd, vote, comments, replies, postComment, deleteNote, voteNote, postReply, COMMENT_LIMIT } from "../../lib/assets.js";
import { signed, tone } from "../../lib/format.js";
import { COVERAGE } from "./words.js";

const ago = (iso) => {
  if (!iso) return "";
  const m = (Date.now() - new Date(iso).getTime()) / 6e4;
  return m < 90 ? T("{n} min ago", { n: Math.max(1, Math.round(m)) }) : m < 2880 ? T("{n} hours ago", { n: Math.round(m / 60) }) : T("{n} days ago", { n: Math.round(m / 1440) });
};

// What members make of this asset's news mood: agree or disagree, short comments (kept 12 hours) and replies.
// `votes` (optional): {crowd(), vote(v)} for a take kept somewhere else, as the market moods are (market_mood_votes).
export default function Community({ row, score, votes, about }) {
  const key = row.asset_key, at = row.sentiment_updated_at;
  const [c, setC] = useState(null);
  const [notes, setNotes] = useState(null);
  const [reps, setReps] = useState({});
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const load = async () => {
    const [cr, cs, rs] = await Promise.all([votes ? votes.crowd() : crowd(key), comments(key), replies()]);
    setC(cr);
    setNotes(cs.filter((n) => n.asset_key === key).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))));
    const by = {}; rs.forEach((r) => { (by[r.comment_id] = by[r.comment_id] || []).push(r); });
    Object.values(by).forEach((l) => l.sort((a, b) => String(a.created_at).localeCompare(String(b.created_at))));
    setReps(by);
  };
  useEffect(() => { load(); }, [key]);
  const act = async (fn) => { setMsg(""); try { await fn(); await load(); } catch (e) { setMsg(T("That didn't save. Please try again.")); } };
  const mine = (notes || []).find((n) => n.mine);
  const report = row.sentiment_report || {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <section className="card">
        <h2>{T("Your take on the news mood")}</h2>
        <p className="sub">{score == null ? (about || T("The news for this asset hasn't been scored yet.")) : T("MarketNavi's reading of the news: {mood} ({s}). Do you agree?", { mood: COVERAGE(score), s: signed(score) })}</p>
        {score != null && c && (
          <div className="bar">
            <button type="button" className={"ghost" + (c.mine === 1 ? " on" : "")} aria-pressed={c.mine === 1} onClick={() => act(() => (votes ? votes.vote(c.mine === 1 ? 0 : 1) : vote(key, at, c.mine === 1 ? 0 : 1)))}><Icon n="thumbs-up" size={16} /> {T("Agree")} · {c.up}</button>
            <button type="button" className={"ghost" + (c.mine === -1 ? " on" : "")} aria-pressed={c.mine === -1} onClick={() => act(() => (votes ? votes.vote(c.mine === -1 ? 0 : -1) : vote(key, at, c.mine === -1 ? 0 : -1)))}><Icon n="thumbs-down" size={16} /> {T("Disagree")} · {c.down}</button>
          </div>
        )}
      </section>

      <section className="card">
        <h2>{T("Comments")}</h2>
        <p className="sub">{T("Short notes from members about this asset. Each stays for 12 hours.")}</p>
        {score != null && (
          <form className="cform" onSubmit={(e) => { e.preventDefault(); if (text.trim()) act(async () => { await postComment(key, at, text, score, report.summary); setText(""); }); }}>
            <input type="text" maxLength={COMMENT_LIMIT} value={text} onChange={(e) => setText(e.target.value)}
              placeholder={mine ? T("Replace your comment…") : T("Add a comment…")} aria-label={T("Your comment")} />
            <button type="submit" className="primary" disabled={!text.trim()}>{T("Post")}</button>
          </form>
        )}
        {msg && <p className="note bad">{msg}</p>}
        {notes === null ? <p className="sub">{T("Loading…")}</p> : !notes.length ? <p className="sub">{T("No comments in the last 12 hours. Be the first.")}</p> : (
          <ol className="comments">
            {notes.map((n) => (
              <li key={n.id}>
                <Note n={n} kind="comment" act={act} />
                {(reps[n.id] || []).map((r) => <div key={r.id} className="reply"><Note n={r} kind="reply" act={act} /></div>)}
                <ReplyBox onSend={(t) => act(() => postReply(n.id, t))} />
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function Note({ n, kind, act }) {
  const v = n.my_vote == null ? 0 : +n.my_vote;
  return (
    <div className="cnote">
      <span className="cav" aria-hidden="true">{n.avatar_url ? <img src={n.avatar_url} alt="" /> : String(n.author_name || "M").slice(0, 1)}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div><b>{n.author_name || T("Member")}</b> <span className="m">· {ago(n.created_at)}</span>
          {n.responded_score != null && kind === "comment" && <span className="m"> · {T("on a mood of {s}", { s: signed(n.responded_score) })}</span>}</div>
        <div>{n.body}</div>
        <div className="cacts">
          <button type="button" className={"linkish" + (v === 1 ? " on" : "")} onClick={() => act(() => voteNote(n.id, kind, v === 1 ? 0 : 1))} aria-label={T("Thumbs up")}><Icon n="thumbs-up" size={15} /> {+n.thumbs_up || 0}</button>
          <button type="button" className={"linkish" + (v === -1 ? " on" : "")} onClick={() => act(() => voteNote(n.id, kind, v === -1 ? 0 : -1))} aria-label={T("Thumbs down")}><Icon n="thumbs-down" size={15} /> {+n.thumbs_down || 0}</button>
          {n.mine && <button type="button" className="linkish" onClick={() => act(() => deleteNote(n.id, kind))}>{T("Delete")}</button>}
        </div>
      </div>
    </div>
  );
}

function ReplyBox({ onSend }) {
  const [open, setOpen] = useState(false), [t, setT] = useState("");
  if (!open) return <button type="button" className="linkish reply-open" onClick={() => setOpen(true)}>{T("Reply")}</button>;
  return (
    <form className="cform reply" onSubmit={(e) => { e.preventDefault(); if (t.trim()) { onSend(t); setT(""); setOpen(false); } }}>
      <input type="text" maxLength={COMMENT_LIMIT} value={t} onChange={(e) => setT(e.target.value)} placeholder={T("Write a reply…")} aria-label={T("Your reply")} autoFocus />
      <button type="submit" className="primary" disabled={!t.trim()}>{T("Reply")}</button>
    </form>
  );
}
