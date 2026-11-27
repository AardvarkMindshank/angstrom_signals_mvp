// The account's own settings, stored where the classic app keeps them, so a change here shows there too:
// user_preferences.settings (merged, other keys kept), alert_preferences (alerts and emails) and profiles.
import { supabase } from "./supabase.js";

const must = ({ data, error }) => { if (error) throw error; return data; };
const uid = async () => { const { data } = await supabase.auth.getUser(); return data.user.id; };

export async function preferences() {
  const id = await uid();
  const rows = must(await supabase.from("user_preferences").select("settings,crypto_watchlist,stock_watchlist").eq("user_id", id).limit(1)) || [];
  const r = rows[0] || {};
  return { settings: r.settings || {}, crypto: r.crypto_watchlist || {}, equity: r.stock_watchlist || {} };
}

// Merge into the settings: read the row as it is now, change only these keys, write it back.
export async function saveSettings(updates) {
  const id = await uid();
  const rows = must(await supabase.from("user_preferences").select("settings").eq("user_id", id).limit(1)) || [];
  const merged = { ...((rows[0] && rows[0].settings) || {}), ...updates };
  must(await supabase.from("user_preferences").update({ settings: merged }).eq("user_id", id));
  return merged;
}

export async function saveWatchlist(kind, list) {
  const id = await uid();
  must(await supabase.from("user_preferences").update({ [kind === "crypto" ? "crypto_watchlist" : "stock_watchlist"]: list }).eq("user_id", id));
}

export async function alertPrefs() {
  const id = await uid();
  try { return (must(await supabase.from("alert_preferences").select("*").eq("user_id", id).limit(1)) || [])[0] || null; } catch (e) { return null; }
}

export async function saveAlertPrefs(updates) {
  const id = await uid();
  must(await supabase.from("alert_preferences").update(updates).eq("user_id", id));
}

export async function profile() {
  const id = await uid();
  try { return (must(await supabase.from("profiles").select("*").eq("user_id", id).limit(1)) || [])[0] || {}; } catch (e) { return {}; }
}

export async function saveProfile(updates) {
  const id = await uid();
  must(await supabase.from("profiles").upsert({ user_id: id, updated_at: new Date().toISOString(), ...updates }));
}

// A profile photo, made 512 px square-ish JPEG in the browser first, into the same storage the classic app uses.
export async function uploadAvatar(file) {
  if (file.size > 5e6) throw new Error("big");
  const img = await createImageBitmap(file);
  const k = Math.min(1, 512 / Math.max(img.width, img.height));
  const c = document.createElement("canvas"); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  const blob = await new Promise((ok) => c.toBlob(ok, "image/jpeg", 0.85));
  const id = await uid();
  const path = `${id}/avatar.jpg`;
  const bucket = supabase.storage.from("avatars");
  const up = await bucket.upload(path, blob, { contentType: "image/jpeg", upsert: true });
  if (up.error) throw up.error;
  return `${bucket.getPublicUrl(path).data.publicUrl}?v=${Date.now()}`;
}

export async function names(ids) {
  if (!ids.length) return {};
  try {
    const rows = must(await supabase.from("profiles").select("user_id,display_name").in("user_id", ids)) || [];
    return Object.fromEntries(rows.map((r) => [String(r.user_id).toLowerCase(), r.display_name || "Member"]));
  } catch (e) { return {}; }
}

let metaP = null;
export const meta = () => (metaP = metaP || fetch(import.meta.env.BASE_URL + "data/meta.json").then((r) => r.json()).catch(() => ({ languages: [], zones: ["UTC"], voices: {} })));
