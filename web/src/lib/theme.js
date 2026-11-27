// Day or night from the account (user_preferences.settings.ui_mode), as in the classic app. The new app has its own
// flat palette: one background, hairline dividers and no boxed panels, so the classic UI Colours aren't used here.
const PALETTE = {
  day: { page: "#ffffff", surface: "#ffffff", raised: "#ffffff", field: "#f5f6f8", hover: "#f7f8fa", border: "#eceef2",
    track: "#eef0f4", text: "#0b1220", muted: "#6b7280", soft: "#374151" },
  night: { page: "#0d1015", surface: "#0d1015", raised: "#171b22", field: "#171b22", hover: "#151920", border: "#232833",
    track: "#262b36", text: "#f3f4f6", muted: "#9ca3af", soft: "#d1d5db" },
};

export function applyTheme(settings) {
  // The last mode is remembered on this device, so the start-up screen already has the right colours (a phone in
  // dark mode used to flash dark, then light, on every load).
  let mode = (settings || {}).ui_mode;
  try { if (mode) localStorage.setItem("mn_ui_mode", mode); else mode = localStorage.getItem("mn_ui_mode"); } catch (e) { /* private window */ }
  mode = mode || "auto";
  const night = mode === "night" || (mode === "auto" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const p = PALETTE[night ? "night" : "day"];
  const root = document.documentElement;
  root.classList.toggle("night", night);
  Object.entries(p).forEach(([k, v]) => root.style.setProperty(`--ang-${k}`, v));
  root.style.setProperty("--ang-header", p.page);
  return night;
}
