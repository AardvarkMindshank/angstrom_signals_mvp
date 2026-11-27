import React, { useEffect, useMemo, useRef, useState } from "react";
import { T, lang } from "../../../lib/i18n.js";
import { call } from "../../../lib/service.js";
import { supabase } from "../../../lib/supabase.js";
import { saveSettings } from "../../../lib/account.js";
import { drawingKey } from "../../../lib/assets.js";
import { mount } from "./engine.js";

// ⭐ Pro: the full classic chart. Every candle size from 5 minutes to a month, every indicator, Sonar and its
// markers, chart shapes, fair value gaps, single prints, liquidation levels, Fed/CPI/jobs days, earnings days,
// a Set's answer as bands, and the drawing tools. The choices belong to the account and are the same ones the
// classic chart keeps (settings.chart_*), so both apps open the chart the same way.
const IV_WORDS = () => ({ "5m": T("5 minutes"), "15m": T("15 minutes"), "30m": T("30 minutes"), "1h": T("1 hour"), "4h": T("4 hours"),
  "12h": T("12 hours"), "1D": T("1 day"), "1W": T("1 week"), "1Mo": T("1 month") });
const IV_SHORT = { "1Mo": "1M" };
const RANGE_WORDS = () => ({ "7D": T("7 days"), "1M": T("1 month"), "3M": T("3 months"), "1Y": T("1 year"), All: T("All") });
const SONAR_WORDS = () => ({ trend_turn_up: T("🔺 Trend turn up"), trend_turn_down: T("🔻 Trend turn down"), long_cross: T("🟢 Green dot"),
  short_cross: T("🔴 Red dot"), red_cross: T("❌ Red cross"), red_diamond: T("♦️ Red diamond"), blood_diamond: T("🩸 Blood diamond"),
  yellow_cross: T("⚠️ Yellow cross"), strength_candle: T("🔶 Strength") });
const PRICE_MIN = 220, PRICE_MAX = 1100, PRICE_DEFAULT = 460;
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export default function Pro({ assetKey, who, title, account }) {
  const crypto = assetKey.startsWith("Crypto|");
  const saved = (account && account.settings) || {};
  const [opts, setOpts] = useState(null);
  const [pick, setPick] = useState(() => {
    const inds = Array.isArray(saved.chart_indicators) ? saved.chart_indicators.slice() : ["cipher", "sonar_marks"];
    if (saved.chart_fvg) inds.push("fvg");
    if (saved.chart_single_prints) inds.push("single_prints");
    if (saved.chart_liq) inds.push("liq");
    return {
      interval: saved.chart_interval || "1D", range: saved.chart_range || "3M", indicators: inds,
      overlay: !!saved.chart_overlay, earnings: saved.chart_earnings !== false, events: saved.chart_events !== false,
      sonar_marks: Array.isArray(saved.chart_sonar_marks) ? saved.chart_sonar_marks : null, dot_buildup: !!saved.chart_dot_buildup,
      band: "", band_no: false,
    };
  });
  const [px, setPx] = useState(() => Math.max(PRICE_MIN, Math.min(PRICE_MAX, Number(saved.chart_price_px) || PRICE_DEFAULT)));
  const [got, setGot] = useState(null);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [more, setMore] = useState(false);
  const [ink, setInk] = useState(0);              // bumps when day/night changes, to redraw in the new colours
  const host = useRef(null);
  const drawRec = useRef(null);
  const [drawReady, setDrawReady] = useState(0);

  useEffect(() => { call(`/chart/options?key=${encodeURIComponent(assetKey)}&lang=${lang}`).then(setOpts).catch(() => setOpts({ down: true })); }, [assetKey]);
  useEffect(() => {
    const m = new MutationObserver(() => setInk((n) => n + 1));
    m.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "style"] });
    return () => m.disconnect();
  }, []);

  // The member's drawings on this asset, read once per asset (the chart keeps unsaved work while the page is open).
  useEffect(() => {
    drawRec.current = null;
    (async () => {
      try {
        const { data: u } = await supabase.auth.getUser();
        const { data } = await supabase.from("chart_drawings").select("items, updated_at").eq("user_id", u.user.id).eq("asset_key", drawingKey(who.kind, who.id)).limit(1);
        drawRec.current = { items: (data && data[0] && data[0].items) || [], updated: data && data[0] ? data[0].updated_at : null, user: u.user.id };
      } catch (e) { drawRec.current = { items: [], updated: null, user: null }; }
      setDrawReady((n) => n + 1);
    })();
  }, [assetKey]);

  const ask = useMemo(() => ({ ...pick, band: pick.band || null }), [pick]);
  useEffect(() => {
    let live = true;
    setBusy(true); setErr("");
    const t = setTimeout(async () => {
      try {
        const dark = document.documentElement.classList.contains("night");
        const out = await call("/chart", { method: "POST", timeout: 60000, body: { key: assetKey, ...ask, dark, price_px: px, lang, title: title || "" } });
        if (!live) return;
        if (out.error) { setErr(out.error); setGot(null); if (out.nearest) setPick((p) => ({ ...p, range: out.nearest })); }
        else setGot(out);
      } catch (e) {
        if (live) setErr(e.status === 0 ? T("The chart service isn't reachable just now. Please try again in a minute.") : T("The chart couldn't load just now. Please try again."));
      }
      if (live) setBusy(false);
    }, 120);
    return () => { live = false; clearTimeout(t); };
  }, [assetKey, ask, px, ink]);

  // Draw it (again) when the data, the colours or the drawings change.
  useEffect(() => {
    if (!got || !got.payload || !host.current || !drawRec.current) return;
    const data = { ...got.payload };
    data.theme = { ...data.theme, bg: css("--ang-page") || data.theme.bg, ink: css("--ang-text") || data.theme.ink,
      muted: css("--ang-muted") || data.theme.muted, grid: css("--ang-border") || data.theme.grid };
    const rec = drawRec.current;
    const key = drawingKey(who.kind, who.id);
    data.draw = { asset: key, items: rec ? rec.items : [], updated: rec ? rec.updated : null, share: false,
      save: async (items) => {
        const { data: u } = await supabase.auth.getUser();
        const { error } = await supabase.from("chart_drawings").upsert({ user_id: u.user.id, asset_key: key, items, updated_at: new Date().toISOString() }, { onConflict: "user_id,asset_key" });
        if (!error && drawRec.current) { drawRec.current.items = items; drawRec.current.updated = new Date().toISOString(); }
        return !error;
      } };
    return mount(host.current, data);
  }, [got, drawReady]);

  const set = (patch, store) => { setPick((p) => ({ ...p, ...patch })); if (store) saveSettings(store).catch(() => {}); };
  const has = (k) => pick.indicators.includes(k);
  const flip = (k) => {
    const next = has(k) ? pick.indicators.filter((x) => x !== k) : [...pick.indicators, k];
    set({ indicators: next }, {
      chart_indicators: next.filter((x) => !["fvg", "single_prints", "liq"].includes(x)),
      chart_fvg: next.includes("fvg"), chart_single_prints: next.includes("single_prints"), ...(crypto ? { chart_liq: next.includes("liq") } : {}),
    });
  };
  const iv = IV_WORDS(), rw = RANGE_WORDS(), sw = SONAR_WORDS();
  const inds = (opts && opts.indicators ? opts.indicators : []).filter(([k]) => k !== "single_prints" || (opts.single_print_intervals || []).includes(pick.interval));
  const marks = pick.sonar_marks || (opts && opts.sonar_default) || [];

  // Drag the bar under the chart to make the price chart taller or shorter (kept for the account, as in classic).
  const drag = (e) => {
    e.preventDefault();
    const y0 = e.clientY, h0 = px;
    let last = h0;
    const move = (ev) => { last = Math.max(PRICE_MIN, Math.min(PRICE_MAX, Math.round(h0 + ev.clientY - y0))); if (host.current) host.current.style.minHeight = ""; setPxLive(last); };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); setPxLive(null); setPx(last); saveSettings({ chart_price_px: last }).catch(() => {}); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const [pxLive, setPxLive] = useState(null);

  return (
    <div className="pro">
      <div className="bar" style={{ marginBottom: 8, flexWrap: "wrap", gap: 10 }}>
        <div className="chips" role="group" aria-label={T("Candle size")}>
          {(opts && opts.intervals ? opts.intervals : ["15m", "1h", "4h", "1D", "1W"]).map((k) => (
            <button key={k} type="button" className={pick.interval === k ? "on" : ""} aria-pressed={pick.interval === k} title={iv[k]}
              onClick={() => set({ interval: k }, { chart_interval: k })}>{IV_SHORT[k] || k}</button>
          ))}
        </div>
        <div className="chips right" role="group" aria-label={T("Period")}>
          {(opts && opts.ranges ? opts.ranges : ["7D", "1M", "3M", "1Y", "All"]).map((k) => (
            <button key={k} type="button" className={pick.range === k ? "on" : ""} aria-pressed={pick.range === k} title={rw[k]}
              onClick={() => set({ range: k }, { chart_range: k })}>{k === "All" ? rw.All : k}</button>
          ))}
        </div>
      </div>
      {opts && !opts.down && (
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 4, marginBottom: 6 }}>
          <div className="chips ind" role="group" aria-label={T("Indicators")}>
            {inds.map(([k, l]) => <button key={k} type="button" className={has(k) ? "on" : ""} aria-pressed={has(k)} onClick={() => flip(k)}>{l}</button>)}
          </div>
          <button type="button" className="linkish promorebtn" aria-expanded={more} onClick={() => setMore(!more)}>
            {more ? T("Fewer options") : T("More options")} {more ? "▴" : "▾"}
          </button>
        </div>
      )}
      {more && opts && !opts.down && (
        <div className="promore">
          <label className="ptog"><input type="checkbox" checked={pick.overlay} onChange={(e) => set({ overlay: e.target.checked }, { chart_overlay: e.target.checked })} />
            <span>{T("Overlay RSI, Stochastic, Stoch RSI and ADX on the price chart")}</span></label>
          <label className="ptog"><input type="checkbox" checked={pick.events} onChange={(e) => set({ events: e.target.checked }, { chart_events: e.target.checked })} />
            <span>{T("Show Fed, CPI and jobs days")}</span></label>
          {!crypto && <label className="ptog"><input type="checkbox" checked={pick.earnings} onChange={(e) => set({ earnings: e.target.checked }, { chart_earnings: e.target.checked })} />
            <span>{T("Show earnings report dates")}</span></label>}
          {has("cipher") && <label className="ptog"><input type="checkbox" checked={pick.dot_buildup} onChange={(e) => set({ dot_buildup: e.target.checked }, { chart_dot_buildup: e.target.checked })} />
            <span>{"🔆 " + T("Dot build-up")}</span></label>}
          {has("sonar_marks") && (
            <div className="psub">
              <span className="m">{T("🛰️ Markers shown")}</span>
              <div className="chips ind">
                {(opts.sonar_marks || []).map(([k, _l, words]) => {
                  const on = marks.includes(k);
                  return <button key={k} type="button" className={on ? "on" : ""} aria-pressed={on} title={words}
                    onClick={() => { const next = on ? marks.filter((x) => x !== k) : [...marks, k]; set({ sonar_marks: next }, { chart_sonar_marks: next }); }}>{sw[k] || k}</button>;
                })}
              </div>
            </div>
          )}
          <div className="psub">
            <span className="m">{T("Show a Set on the chart")}</span>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <select value={pick.band} onChange={(e) => set({ band: e.target.value })} aria-label={T("Show a Set on the chart")} style={{ maxWidth: 360 }}>
                <option value="">{T("⊘ No Set")}</option>
                {(opts.sets || []).map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
              </select>
              {pick.band && <label className="ptog" style={{ margin: 0 }}><input type="checkbox" checked={pick.band_no} onChange={(e) => set({ band_no: e.target.checked })} /><span>{T("Show No as faint red")}</span></label>}
            </div>
          </div>
        </div>
      )}
      {err && <p className="sub">{err}</p>}
      {got && got.note && <p className="sub">{got.note}</p>}
      <div className="prochart" style={{ opacity: busy && got ? 0.55 : 1 }}>
        {!got && !err && <div className="empty" style={{ height: px + 120 }}>{busy ? T("Loading…") : ""}</div>}
        <div ref={host} />
        {pxLive != null && <div className="proguide" style={{ top: pxLive }} />}
      </div>
      {got && <div className="prodrag" onPointerDown={drag} title={T("Drag to make the price chart taller or shorter")} role="separator" aria-orientation="horizontal" />}
    </div>
  );
}
