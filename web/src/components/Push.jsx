import React, { useEffect, useState } from "react";
import { T } from "../lib/i18n.js";
import { supabase } from "../lib/supabase.js";
import Icon from "./Icon.jsx";

// 📱 Notifications on THIS phone or computer, as the classic app: turn on, send a test, turn off. Each device that
// turns them on is a row in push_subscriptions; the alert worker pushes every new notification to them, once. On an
// iPhone or iPad they only work in MarketNavi opened from the Home Screen (iOS 16.4 or later).
const KEY = (import.meta.env.VITE_VAPID_PUBLIC_KEY || "").trim();
const SW = `${import.meta.env.BASE_URL}sw.js`;
const ua = typeof navigator !== "undefined" ? navigator.userAgent || "" : "";
const apple = /iPhone|iPad|iPod/.test(ua) || (typeof navigator !== "undefined" && navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const standalone = typeof window !== "undefined" && (window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true);
const DEVICE = apple ? (/iPad/.test(ua) || (navigator.maxTouchPoints > 1 && !/iPhone/.test(ua)) ? "iPad" : "iPhone")
  : /Android/.test(ua) ? "Android device" : /Windows/.test(ua) ? "Windows computer" : /Mac/.test(ua) ? "Mac" : "computer";
const supported = typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
const Html = ({ s }) => <span dangerouslySetInnerHTML={{ __html: s }} />;   // our own translations, with <b> marks

const keyBytes = (b64) => {
  const raw = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};
async function worker() {
  const reg = await navigator.serviceWorker.register(SW, { scope: import.meta.env.BASE_URL });
  if (reg.active) return reg;
  const w = reg.installing || reg.waiting;
  if (w) await new Promise((ok) => { w.addEventListener("statechange", () => w.state === "activated" && ok()); setTimeout(ok, 4000); });
  return reg;
}
const save = (sub) => { const j = sub.toJSON(); return supabase.rpc("push_subscribe", { p_endpoint: j.endpoint, p_p256dh: j.keys.p256dh, p_auth: j.keys.auth, p_device: DEVICE }); };

export default function Push() {
  const shown = T(DEVICE);
  const [state, setState] = useState("checking");      // checking | off | on | failed
  const [sub, setSub] = useState(null);
  const [note, setNote] = useState(null);
  const [busy, setBusy] = useState(false);
  const ready = supported && KEY && !(apple && !standalone) && (typeof Notification === "undefined" || Notification.permission !== "denied");
  useEffect(() => {
    if (!ready) return;
    (async () => {
      try {
        const reg = await worker();
        const s = await reg.pushManager.getSubscription();
        if (s) {
          // On this device already: make sure the database has it for this account (it may have been another account).
          const { data } = await supabase.from("push_subscriptions").select("endpoint").eq("endpoint", s.endpoint).limit(1);
          if (!data || !data.length) await save(s);
          setSub(s); setState("on");
        } else setState("off");
      } catch (e) { setState("failed"); }
    })();
  }, [ready]);
  if (apple && !standalone) return (
    <div className="pushbox">
      <p><Html s={T("On an {device}, notifications work in the <b>MarketNavi app on your Home Screen</b>:", { device: shown })} /></p>
      <ol>
        <li><Html s={T("Open this site in <b>Safari</b>.")} /></li>
        <li><Html s={T("Tap <b>Share</b> (the square with an arrow), then <b>Add to Home Screen</b>.")} /></li>
        <li>{T("Open MarketNavi from its new icon, sign in, and turn notifications on here.")}</li>
      </ol>
      <p className="m">{T("Needs iOS 16.4 or later.")}</p>
    </div>
  );
  if (!supported) return <p className="sub">{T("This browser can't show notifications from websites. Try Chrome, Edge, Firefox or Safari.")}</p>;
  if (!KEY) return <p className="sub">{T("Notifications aren't set up on the server yet.")}</p>;
  if (Notification.permission === "denied") return <p className="sub"><Html s={T("Notifications are <b>blocked</b> for this site in your browser's settings. Allow them there, then reload.")} /></p>;
  const turnOn = async () => {
    setBusy(true); setNote(null);
    try {
      if (await Notification.requestPermission() !== "granted") { setNote(["bad", T("Notifications weren't allowed, so nothing changed.")]); return; }
      const reg = await worker();
      const s = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(KEY) });
      const { error } = await save(s);
      if (error) throw error;
      setSub(s); setState("on"); setNote(["ok", T("Notifications are on for this device.")]);
    } catch (e) { setNote(["bad", T("Notifications couldn't start on this device.")]); } finally { setBusy(false); }
  };
  const turnOff = async () => {
    setBusy(true);
    try { if (sub) { await supabase.rpc("push_unsubscribe", { p_endpoint: sub.endpoint }); await sub.unsubscribe(); } } catch (e) { /* already gone */ }
    setSub(null); setState("off"); setBusy(false); setNote(["ok", T("Notifications are off for this device.")]);
  };
  const test = async () => {
    setBusy(true);
    const { data, error } = await supabase.rpc("push_test");
    const c = String(data || "").replace(/"/g, "");
    setNote(error || !["ok", "recent"].includes(c) ? ["bad", T("That didn't work. Please try again.")]
      : ["ok", c === "recent" ? T("A test is already on its way.") : T("Test on its way: it arrives within about five minutes.")]);
    setBusy(false);
  };
  return (
    <div className="pushbox">
      {state === "checking" && <p className="sub">{T("Checking this device…")}</p>}
      {state === "failed" && <p className="sub">{T("Notifications couldn't start on this device.")}</p>}
      {state === "off" && (
        <>
          <p className="sub"><Html s={T("Get your alerts, funnel Candidates and shared charts as notifications on this {device}.", { device: shown })} /></p>
          <div><button type="button" className="primary" disabled={busy} onClick={turnOn} title={T("Your browser will ask to allow notifications")}><Icon n="bell-ring" size={16} /> {busy ? T("Turning on…") : T("Turn on for this device")}</button></div>
        </>
      )}
      {state === "on" && (
        <>
          <p className="pushon"><Icon n="circle-check" size={17} tone="green" /> <Html s={T("Notifications are <b>on</b> for this {device}.", { device: shown })} /></p>
          <div className="row">
            <button type="button" className="ghost bordered" disabled={busy} onClick={test} title={T("Send a test notification to your devices")}><Icon n="send" size={15} /> {T("Send a test")}</button>
            <button type="button" className="ghost" disabled={busy} onClick={turnOff} title={T("Stop notifications on this device")}>{T("Turn off")}</button>
          </div>
        </>
      )}
      {note && <p className={"note " + (note[0] === "ok" ? "good" : "bad")}>{note[1]}</p>}
    </div>
  );
}
