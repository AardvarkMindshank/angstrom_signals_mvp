"""
Getting started: a short checklist at the top of the dashboard for new testers, and tap-to-explain for touch screens.

Checklist. Five first steps; two tick themselves (3+ assets on the watchlists, a saved Prism Scan), the rest are
ticked by the person. Progress is saved on the account (settings["onboarding"]); it is optional: the card hides itself when
every step is done, or when the person presses Skip, and the Help guide can bring it back.

Tap to explain. Explanations in the app are hover notes, which phones and tablets never show. One page-wide script
(tap_explain.js below) makes them appear on a tap, with nothing new drawn on the page: a tap on an icon, reading or
label that has a note and does nothing else shows the note in a small bubble; a long press shows it on anything,
including buttons, without pressing them. ❓ Explain mode (⚙️ Settings) makes every tap or click explain instead of
act, on any device, until it is switched off.
"""

from __future__ import annotations

STEPS = (
    ("markets", "⚙️", "Choose the markets you trade",
     "In ⚙️ Settings in the sidebar: cryptos, equities or both. The other market's sections hide."),
    ("watchlist", "📌", "Add a few assets you follow",
     "In the sidebar's Watchlists. This ticks itself once you have 3 or more."),
    ("reading", "📈", "Tap a 📈 Trend reading",
     "In the signal tables, tap any reading or icon to see what it means; click a reading for its Signals Breakdown."),
    ("alerts", "🔔", "Choose how alerts reach you",
     "Notifications → Configure Alert Rules: instant emails, a daily summary, or both."),
    ("prism", "🔎", "Try a Prism scan",
     "Angstrom Lattice → Prism Scan: tap + on an example Set, then ▶. This ticks itself once you have a scan."),
)
AUTO = ("watchlist", "prism")


def state(settings: dict) -> dict:
    raw = (settings or {}).get("onboarding")
    raw = raw if isinstance(raw, dict) else {}
    return {"done": [k for k in raw.get("done") or [] if k in dict((s[0], 1) for s in STEPS)],
            "hidden": bool(raw.get("hidden"))}


def progress(saved: dict, auto: dict) -> list[tuple[str, str, str, str, bool, bool]]:
    """(key, icon, title, hint, done, ticks_itself) per step."""
    done = set(saved["done"])
    return [(k, icon, title, hint, bool(auto.get(k)) or k in done, k in AUTO and bool(auto.get(k)))
            for k, icon, title, hint in STEPS]


def visible(saved: dict, auto: dict) -> bool:
    return not saved["hidden"] and not all(p[4] for p in progress(saved, auto))


def render(st, settings: dict, auto: dict, save) -> None:
    """The checklist card. `save(updates)` stores account settings."""
    saved = state(settings)
    if not visible(saved, auto):
        return
    rows = progress(saved, auto)
    count = sum(1 for r in rows if r[4])
    with st.container(border=True, key="onboarding_card"):
        head = st.columns([6, 1.4], vertical_alignment="center")
        head[0].markdown(f"**🚀 Getting started** (optional) · {count} of {len(rows)} done")
        if head[1].button("Skip", key="onboarding_hide",
                          help="Optional: skip this guide. Nothing depends on it; Help and guides → Start here brings it "
                               "back."):
            save({"onboarding": {**saved, "hidden": True}})
            st.rerun()
        st.progress(count / len(rows))
        for key, icon, title, hint, done, auto_done in rows:
            ticked = st.checkbox(f"{icon} {title}", value=done, key=f"onboarding_{key}", help=hint,
                                 disabled=auto_done)
            if not auto_done and ticked != (key in saved["done"]):
                done_now = [k for k in saved["done"] if k != key] + ([key] if ticked else [])
                save({"onboarding": {**saved, "done": done_now}})
                st.rerun()
        st.caption("Tip: tap any icon or reading to see what it means. ❓ Explain mode in ⚙️ Settings explains every "
                   "tap instead of acting on it.")


def show_again(settings: dict, save) -> None:
    saved = state(settings)
    save({"onboarding": {**saved, "hidden": False}})


# ----------------------------------------------------------------------------------------------- tap to explain

TAP_JS = r"""
export default function(component) {
  const on = !!((component.data || {}).on);
  window.__explainOn = on;
  document.documentElement.classList.toggle("explain-mode", on);
  if (window.__tapExplainReady) return;
  window.__tapExplainReady = true;

  const touch = window.matchMedia && window.matchMedia("(hover: none)").matches;
  const ACTIVE = "a[href],button,input,select,textarea,label,summary,[role=button],[role=tab],[role=link],[onclick]";
  let bubble = null, timer = null, start = null, swallow = false;

  function close() { if (bubble) { bubble.remove(); bubble = null; } }
  function noteOf(path, anyLabel) {
    for (const n of path) {
      if (!(n instanceof Element)) continue;
      if (n.closest && n.closest(".st-key-explain_mode, .explain-bubble")) return null;
      const t = n.getAttribute("data-explain") || n.getAttribute("title") ||
                (anyLabel ? n.getAttribute("aria-label") : null);
      if (t && t.trim()) return { el: n, text: t.trim() };
      if (n === document.body) break;
    }
    return null;
  }
  function acts(path, upto) {
    for (const n of path) {
      if (!(n instanceof Element)) continue;
      if (n.matches(ACTIVE)) return true;
      try { if (getComputedStyle(n).cursor === "pointer") return true; } catch (e) {}
      if (n === upto) break;
    }
    return false;
  }
  function show(note) {
    close();
    const r = note.el.getBoundingClientRect();
    bubble = document.createElement("div");
    bubble.className = "explain-bubble";
    bubble.setAttribute("role", "tooltip");
    bubble.textContent = note.text;
    Object.assign(bubble.style, {position: "fixed", zIndex: 2147483000, maxWidth: "min(300px, calc(100vw - 24px))",
      background: "#1f2937", color: "#fff", font: "14px/1.4 system-ui,-apple-system,sans-serif", padding: "8px 11px",
      borderRadius: "10px", boxShadow: "0 6px 20px rgba(0,0,0,.28)", whiteSpace: "pre-line", pointerEvents: "none"});
    document.body.appendChild(bubble);
    const b = bubble.getBoundingClientRect();
    let top = r.bottom + 8;
    if (top + b.height > window.innerHeight - 8) top = Math.max(8, r.top - b.height - 8);
    const left = Math.min(Math.max(8, r.left + r.width / 2 - b.width / 2), window.innerWidth - b.width - 8);
    bubble.style.top = top + "px";
    bubble.style.left = left + "px";
  }

  // Long press (touch): explain anything with a note, without pressing it.
  document.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "touch") return;
    start = [e.clientX, e.clientY];
    const path = e.composedPath();
    clearTimeout(timer);
    timer = setTimeout(() => { const n = noteOf(path, true); if (n) { show(n); swallow = true; } }, 480);
  }, true);
  document.addEventListener("pointermove", (e) => {
    if (start && Math.hypot(e.clientX - start[0], e.clientY - start[1]) > 10) clearTimeout(timer);
  }, true);
  document.addEventListener("pointerup", () => clearTimeout(timer), true);

  document.addEventListener("click", (e) => {
    const path = e.composedPath();
    if (swallow) { swallow = false; e.preventDefault(); e.stopPropagation(); return; }
    if (window.__explainOn) {
      const n = noteOf(path, true);
      if (n) { e.preventDefault(); e.stopPropagation(); show(n); return; }
      close();
      return;
    }
    if (touch) {
      const n = noteOf(path, false);
      if (n && !acts(path, n.el)) { show(n); return; }
    }
    close();
  }, true);
  window.addEventListener("scroll", close, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
}
"""
TAP_CSS = """
html.explain-mode [title], html.explain-mode [aria-label], html.explain-mode [data-explain] { cursor: help !important; }
"""

_TAP = None


def tap_explain(st, on: bool) -> None:
    """Mount the page-wide tap-to-explain script once per page (cheap on every run)."""
    global _TAP
    try:
        if _TAP is None:
            _TAP = st.components.v2.component("tap_explain", js=TAP_JS, css=TAP_CSS, isolate_styles=False)
        _TAP(key="tap_explain", data={"on": bool(on)})
    except Exception:
        pass
