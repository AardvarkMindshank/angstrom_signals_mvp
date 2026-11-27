// The database, with the member's own sign-in (kept in this browser). The address and the public key come from the
// build (GitHub secrets SUPABASE_URL and SUPABASE_ANON_KEY): the public key only lets a signed-in member reach their
// own rows.
import { createClient } from "@supabase/supabase-js";

export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";
export const configured = Boolean(SUPABASE_URL && KEY);
export const supabase = configured
  ? createClient(SUPABASE_URL, KEY, { auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } })
  : null;
export const CLASSIC = "https://app.marketnavi.ai";
