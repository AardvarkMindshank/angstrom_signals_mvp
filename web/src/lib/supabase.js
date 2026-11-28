// The database, with the member's own sign-in (kept in this browser). The address and the public key come from the
// build (GitHub secrets SUPABASE_URL and SUPABASE_ANON_KEY): the public key only lets a signed-in member reach their
// own rows.
import { createClient } from "@supabase/supabase-js";

export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";
export const configured = Boolean(SUPABASE_URL && KEY);
// 🔑 A one-time sign-in link from an email (a beta welcome, Forgot password, a sign-up confirmation) lands here with the
// session, or an error such as an expired link, after the "#". It is read and taken out of the address before the
// client starts (the app's own pages live after the "#" too), then the session is set below. arrival.type says
// which link it was: invite and magiclink (a welcome) or recovery (Forgot password) ask for a password next.
export const arrival = (() => {
  if (typeof window === "undefined") return null;
  const h = window.location.hash.replace(/^#/, "");
  if (!/(^|&)(access_token|error_code|error)=/.test(h)) return null;
  const p = new URLSearchParams(h);
  const q = window.location.search.replace(/([?&])welcome=1(&|$)/, "$1").replace(/[?&]$/, "");
  window.history.replaceState(null, "", window.location.pathname + q + "#snapshot");
  return { access_token: p.get("access_token") || "", refresh_token: p.get("refresh_token") || "", type: p.get("type") || "",
    error: p.get("error_code") || p.get("error") || "" };
})();

export const supabase = configured
  ? createClient(SUPABASE_URL, KEY, { auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } })
  : null;
export const arrived = supabase && arrival && arrival.access_token
  ? supabase.auth.setSession({ access_token: arrival.access_token, refresh_token: arrival.refresh_token }).catch(() => null)
  : Promise.resolve(null);
// Emails that carry a sign-in link (Forgot password, confirming a new account) use links that work on any device, so
// they are asked for through a second client that keeps nothing in this browser.
export const linkAuth = configured
  ? createClient(SUPABASE_URL, KEY, { auth: { flowType: "implicit", persistSession: false, autoRefreshToken: false, detectSessionInUrl: false, storageKey: "mn-links" } })
  : null;
export const APP_HOME = typeof window !== "undefined" ? window.location.origin + import.meta.env.BASE_URL : "";
export const BETA_FORM = "https://marketnavi.ai/beta.html";
export const CLASSIC = "https://app.marketnavi.ai";
