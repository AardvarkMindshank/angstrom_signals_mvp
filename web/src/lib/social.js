// The social side: members' comments on the assets you follow (and on the markets and Tides), and the chat, with
// communities and private messages. The same database functions as the classic app's social panel.
import { supabase } from "./supabase.js";

const must = ({ data, error }) => { if (error) throw error; return data; };
const uid = async () => { const { data } = await supabase.auth.getUser(); return data.user.id; };
export const LIMIT = 160;
const clean = (s) => String(s || "").split(/\s+/).filter(Boolean).join(" ").slice(0, LIMIT);

export async function stream(keys) {
  try { return must(await supabase.rpc("sentiment_comments", { asset_keys: keys })) || []; } catch (e) { return []; }
}

export async function chat() {
  let rows;
  try { rows = must(await supabase.rpc("chat_feed")) || []; } catch (e) { return null; }
  const roots = {}, out = [];
  rows.forEach((r) => { if (r.parent_id == null && r.body) { const n = { ...r, replies: [] }; roots[r.id] = n; out.push(n); } });
  rows.forEach((r) => { if (r.parent_id != null && roots[r.parent_id]) roots[r.parent_id].replies.push(r); });
  out.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  out.forEach((n) => n.replies.sort((a, b) => String(a.created_at).localeCompare(String(b.created_at))));
  return out;
}

export async function communities() {
  try { return must(await supabase.rpc("my_groups")) || []; } catch (e) { return []; }
}

export async function findPeople(typed) {
  const t = String(typed || "").trim().slice(0, 40);
  if (t.length < 2) return [];
  try { return (must(await supabase.rpc("chat_find_people", { typed: t })) || []).slice(0, 10); } catch (e) { return []; }
}

// A new chat note for everyone, one community ({kind: "group", id}) or one person ({kind: "direct", id}); a reply
// keeps the audience of the note it answers (the database sets it).
export async function post(body, to, parentId) {
  const text = clean(body);
  if (!text) return;
  const row = { user_id: await uid(), body: text };
  if (parentId) row.parent_id = parentId;
  else if (to && to.kind === "group") Object.assign(row, { audience: "group", group_id: +to.id });
  else if (to && to.kind === "direct") Object.assign(row, { audience: "direct", recipient_id: String(to.id).toLowerCase() });
  must(await supabase.from("chat_messages").insert(row));
}

export async function vote(id, v) {
  const me = await uid();
  if (v !== 1 && v !== -1) { must(await supabase.from("chat_votes").delete().eq("user_id", me).eq("message_id", id)); return; }
  must(await supabase.from("chat_votes").upsert({ user_id: me, message_id: id, vote: v }, { onConflict: "user_id,message_id" }));
}

export async function remove(id) { must(await supabase.rpc("delete_own_chat_message", { target_id: id })); }

export function realtime(onChange) {
  // New chat notes and comments arrive without a refresh, when the database publishes them; otherwise every minute.
  const ch = supabase.channel("mn-social")
    .on("postgres_changes", { event: "*", schema: "public", table: "chat_messages" }, () => onChange())
    .on("postgres_changes", { event: "*", schema: "public", table: "sentiment_comments" }, () => onChange())
    .subscribe();
  const timer = setInterval(onChange, 60000);
  return () => { clearInterval(timer); supabase.removeChannel(ch); };
}

// 👥 Communities: a leader invites people (create_group_invite makes the community on the first invite), removes
// members or deletes it; a member leaves. The same database functions as the classic app; each returns a short code.
const code = (r) => String(must(r) || "").replace(/"/g, "").trim();
export async function invite(target, name, groupId) {
  try { return code(await supabase.rpc("create_group_invite", { target, group_name: String(name || "").trim().slice(0, 40), chosen_group: groupId ? +groupId : null })); }
  catch (e) { return "error"; }
}
export async function removeMember(groupId, person) {
  try { return code(await supabase.rpc("remove_group_member", { chosen_group: +groupId, person })); } catch (e) { return "error"; }
}
export async function leaveCommunity(groupId) { must(await supabase.rpc("leave_group", { chosen_group: +groupId })); }
export async function deleteCommunity(groupId) { must(await supabase.rpc("delete_my_group", { chosen_group: +groupId })); }
