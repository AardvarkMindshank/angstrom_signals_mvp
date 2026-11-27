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
        {/* The full MarketNavi logo (compass, name and line), as on the classic sign-in page; night has its own. */}
        <img className="logo-full day" src={import.meta.env.BASE_URL + "brand/full-light.png"} alt="MarketNavi" width="1003" height="800" />
        <img className="logo-full night" src={import.meta.env.BASE_URL + "brand/full-dark.png"} alt="MarketNavi" width="1003" height="800" />
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
