// Day or night and the UI Colours saved on the account (user_preferences.settings), the same as the classic app.
const DEFAULTS = {
  page_day: "#d6e8f8", page_night: "#0e1117", section_day: "#ffffff", section_night: "#262730",
  card_day: "#ffffff", card_night: "#262730", border_day: "#e5e7eb", border_night: "#000000",
  field_day: "#f1f0ee", field_night: "#31333f", hover_day: "#f3f4f6", hover_night: "#31333f",
  heading_day: "#ffffff", heading_night: "#262730",
};
const hex = (v, d) => (/^#[0-9a-fA-F]{6}$/.test(String(v || "")) ? v : d);

export function applyTheme(settings) {
  const s = settings || {};
  const mode = s.ui_mode || "auto";
  const night = mode === "night" || (mode === "auto" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const c = s.colours || {};
  const pick = (k) => hex(c[`${k}_${night ? "night" : "day"}`], DEFAULTS[`${k}_${night ? "night" : "day"}`]);
  const root = document.documentElement;
  root.classList.toggle("night", night);
  root.style.setProperty("--ang-page", pick("page"));
  root.style.setProperty("--ang-surface", pick("card"));
  root.style.setProperty("--ang-header", pick("heading"));
  root.style.setProperty("--ang-border", night ? "#2b2f3a" : pick("border"));
  root.style.setProperty("--ang-field", pick("field"));
  root.style.setProperty("--ang-hover", pick("hover"));
  root.style.setProperty("--ang-track", night ? "#3f4654" : "#e5e7eb");
  root.style.setProperty("--ang-text", night ? "#f3f4f6" : "#111827");
  root.style.setProperty("--ang-muted", night ? "#9ca3af" : "#6b7280");
  root.style.setProperty("--ang-soft", night ? "#d1d5db" : "#374151");
  return night;
}
