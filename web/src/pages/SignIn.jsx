import React, { useState } from "react";
import { supabase, CLASSIC } from "../lib/supabase.js";
import { T } from "../lib/i18n.js";

// Sign in with the same account as the classic app: Google, or email and password.
export default function SignIn() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const google = () => supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin + import.meta.env.BASE_URL } });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    setBusy(false);
    if (error) setErr(T("That email and password didn't match an account."));
  };
  return (
    <div className="signin">
      <div className="card signbox">
        <img src="/logo.png" alt="" width="56" height="56" style={{ alignSelf: "center", borderRadius: 12 }} />
        <h1 style={{ margin: 0, textAlign: "center", fontFamily: "Montserrat, Inter, sans-serif", fontSize: 24 }}>MarketNavi</h1>
        <p className="sub">{T("The new MarketNavi app (beta). Log in with your usual account.")}</p>
        <button type="button" className="google" onClick={google}>{T("Continue with Google")}</button>
        <div className="or">{T("Or continue with")}</div>
        <form className="form" onSubmit={submit}>
          <label>{T("Email")}<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          <label>{T("Password")}<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          {err && <div className="note bad">{err}</div>}
          <button type="submit" className="primary" disabled={busy}>{T("Log In")}</button>
        </form>
        <a className="back" href={CLASSIC}>{T("Back to the classic app")}</a>
      </div>
    </div>
  );
}
