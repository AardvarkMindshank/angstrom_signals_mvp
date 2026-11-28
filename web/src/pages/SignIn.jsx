import React, { useEffect, useState } from "react";
import { supabase, linkAuth, arrival, APP_HOME, BETA_FORM } from "../lib/supabase.js";
import { T } from "../lib/i18n.js";

// Sign in with the same account as the classic app: Google, or email and password; Forgot password sends a link that
// opens the app ready to choose a new one. While the beta is closed there is no sign-up form: an approved person's
// welcome email carries their own link to set a password (beta_worker.py), and "Apply for the closed beta" goes to
// the website form. When an admin opens sign-up to everyone, a plain Sign up form appears instead.
const BARRED = "This account is barred at this time. You can email support@marketnavi.ai.";
const CLOSED = "MarketNavi is in closed beta, and that email has not been approved yet. Use the email you applied with, or request access at marketnavi.ai.";

export default function SignIn() {
  const [view, setView] = useState(arrival && arrival.error ? "forgot" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(arrival && arrival.error ? T("That reset link has expired. Request a new one.") : "");
  const [ok, setOk] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => { supabase.rpc("signup_is_open").then(({ data }) => setOpen(data === true)).catch(() => {}); }, []);
  const go = (v) => { setView(v); setErr(""); setOk(""); };
  const google = () => supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: APP_HOME } });

  const login = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    setBusy(false);
    if (error) setErr(T("That email and password didn't match an account."));
  };
  const forgot = async (e) => {
    e.preventDefault(); setBusy(true); setErr(""); setOk("");
    const { error } = await linkAuth.auth.resetPasswordForEmail(email.trim(), { redirectTo: APP_HOME });
    setBusy(false);
    if (!error) setOk(T("If that email has an account, the reset link is on its way.") + " " + T("We'll email a link. Check junk mail if it does not arrive."));
    else setErr(/rate|limit|seconds/i.test(error.message || "") ? T("The reset mail is limited for a while. Wait a few minutes and try again.") : T("The reset mail could not be sent. Try again in a few minutes."));
  };
  const signup = async (e) => {
    e.preventDefault(); setErr(""); setOk("");
    if (password.length < 6) { setErr(T("Use at least 6 characters.")); return; }
    setBusy(true);
    try {
      const { data: barred } = await supabase.rpc("email_is_barred", { address: email.trim() });
      if (barred === true) { setErr(T(BARRED)); setBusy(false); return; }
    } catch (x) { /* checked again when the account is made */ }
    const { error } = await linkAuth.auth.signUp({ email: email.trim(), password, options: { emailRedirectTo: APP_HOME } });
    setBusy(false);
    if (!error) { setOk(T("Account created for {email}. Open the email we've sent to confirm it (check junk mail too), and you're in.", { email: email.trim() })); return; }
    const m = String(error.message || "").toLowerCase();
    setErr(m.includes("banned") ? T(BARRED) : m.includes("closed beta") ? T(CLOSED) : T("Sign up failed. Try a different email, or a longer password."));
  };

  return (
    <div className="signin">
      <div className="card signbox">
        {/* The full MarketNavi logo (compass, name and line), as on the classic sign-in page; night has its own. */}
        <img className="logo-full day" src={import.meta.env.BASE_URL + "brand/full-light.png"} alt="MarketNavi" width="1003" height="800" />
        <img className="logo-full night" src={import.meta.env.BASE_URL + "brand/full-dark.png"} alt="MarketNavi" width="1003" height="800" />
        {view === "forgot" ? (
          <>
            <p className="sub">{T("Enter the email on the account.")}</p>
            <form className="form" onSubmit={forgot}>
              <label>{T("Email")}<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
              {err && <div className="note bad">{err}</div>}
              {ok && <div className="note good">{ok}</div>}
              <button type="submit" className="primary" disabled={busy}>{T("Send reset link")}</button>
            </form>
            <button type="button" className="linkish back" onClick={() => go("login")}>{T("Back to log in")}</button>
          </>
        ) : view === "signup" && open ? (
          <>
            <button type="button" className="google" onClick={google}>{T("Continue with Google")}</button>
            <div className="or">{T("Or continue with")}</div>
            <form className="form" onSubmit={signup}>
              <label>{T("Email")}<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
              <label>{T("Password")}<input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
              {err && <div className="note bad">{err}</div>}
              {ok && <div className="note good">{ok}</div>}
              <button type="submit" className="primary" disabled={busy}>{T("Create my account")}</button>
            </form>
            <button type="button" className="linkish back" onClick={() => go("login")}>{T("Back to log in")}</button>
          </>
        ) : (
          <>
            <button type="button" className="google" onClick={google}>{T("Continue with Google")}</button>
            <div className="or">{T("Or continue with")}</div>
            <form className="form" onSubmit={login}>
              <label>{T("Email")}<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
              <label>{T("Password")}<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
              {err && <div className="note bad">{err}</div>}
              <button type="submit" className="primary" disabled={busy}>{T("Log In")}</button>
            </form>
            <button type="button" className="linkish forgot" onClick={() => go("forgot")}>{T("Forgot password?")}</button>
            <div className="signfoot">
              {open ? <>{T("New to MarketNavi?")} <button type="button" className="linkish" onClick={() => go("signup")}>{T("Sign Up")}</button></>
                : <>{T("New to MarketNavi?")} <a className="linkish" href={BETA_FORM}>{T("Apply for the closed beta")}</a></>}
            </div>
          </>
        )}
        <div className="signlegal">
          <a href="https://marketnavi.ai/terms.html" target="_blank" rel="noopener noreferrer">{T("Terms of use")}</a> · <a href="https://marketnavi.ai/privacy.html" target="_blank" rel="noopener noreferrer">{T("Privacy")}</a>
        </div>
      </div>
    </div>
  );
}

// After a one-time link: choose a password, then straight in. A welcome for someone who already signs in with Google
// can skip it.
export function SetPassword({ type, email, onDone }) {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const welcome = type !== "recovery";
  const save = async (e) => {
    e.preventDefault(); setErr("");
    if (a.length < 6) { setErr(T("Use at least 6 characters.")); return; }
    if (a !== b) { setErr(T("Those passwords do not match.")); return; }
    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password: a });
    setBusy(false);
    if (error) { setErr(T("That didn't work just now. Please try again.")); return; }
    onDone();
  };
  return (
    <div className="signin">
      <div className="card signbox">
        <img className="logo-full day" src={import.meta.env.BASE_URL + "brand/full-light.png"} alt="MarketNavi" width="1003" height="800" />
        <img className="logo-full night" src={import.meta.env.BASE_URL + "brand/full-dark.png"} alt="MarketNavi" width="1003" height="800" />
        <h2 className="signh">{welcome ? T("Welcome to MarketNavi") : T("Choose a new password")}</h2>
        {welcome && <p className="sub">{T("Choose a password for {email}, and you're in.", { email })}</p>}
        <form className="form" onSubmit={save}>
          <input type="email" autoComplete="username" value={email} readOnly hidden />
          <label>{T("New password")}<input type="password" autoComplete="new-password" value={a} onChange={(e) => setA(e.target.value)} required autoFocus /></label>
          <label>{T("Repeat the new password")}<input type="password" autoComplete="new-password" value={b} onChange={(e) => setB(e.target.value)} required /></label>
          {err && <div className="note bad">{err}</div>}
          <button type="submit" className="primary" disabled={busy}>{T("Save password")}</button>
        </form>
        {type === "magiclink" && <button type="button" className="linkish back" onClick={onDone}>{T("Skip: I'll use Google")}</button>}
      </div>
    </div>
  );
}
