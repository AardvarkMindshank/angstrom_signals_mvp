"""
Training videos in Help and guides: a small 🎬 link beside each topic opens the video in a player in its own window
(?view=video&v=<name>), so it never covers the page you are following along on. The player has buttons to go back,
go on, or start the series again, and a list of every video in the series. Without the window script (or with
pop-ups blocked) the link opens the player in a new tab.

The videos live on the website (angstromsignals.com/videos/training/<name>.mp4), made by the pipeline in video/.
Captions are part of the picture, so nothing else needs loading. Adding a video: record it, publish it, and add a
line to SERIES below.
"""

from __future__ import annotations

import i18n
from i18n import t

BASE_URL = "https://www.angstromsignals.com/videos/training/"
ICON = ":material/smart_display:"

# series key -> (series name, [(video name, title, length)]), in viewing order
SERIES = {
    "lattice": ("Angstrom Lattice: the series", [
        ("01-angstrom-lattice-at-a-glance", "Angstrom Lattice at a glance", "1:29"),
        ("02-signals", "Signals", "1:44"),
        ("03-signal-groups", "Signal Groups", "1:39"),
        ("04-signal-sets", "Signal Sets", "1:21"),
        ("05-prism-scan", "Prism Scan", "1:58"),
    ]),
    "examples": ("Worked examples", [
        ("w1-trend-with-volume", "Trend with volume behind it", "1:10"),
        ("w2-overextended-rally", "Overextended rally", "1:05"),
        ("w3-breakout-with-volume", "Breakout with volume", "1:08"),
        ("w4-breakout-fading", "Breakout fading: a THEN box", "1:38"),
    ]),
    "evidence": ("Reading the evidence", [
        ("06-provided-library", "The provided library", "1:31"),
        ("07-visualize-history", "Visualize History", "0:59"),
        ("08-what-followed", "What followed", "2:13"),
    ]),
    "funnels": ("Funnels", [
        ("f1-funnels", "Funnels", "1:29"),
    ]),
    "tides": ("Tides", [
        ("t1-tides", "Tides", "1:47"),
    ]),
    "help": ("Getting help", [
        ("a1-angstrom-assistant", "The AI Navigator (recorded as the Angstrom Assistant)", "1:03"),
    ]),
}
STATE = "training_video"


def find(name: str) -> tuple[str, int]:
    """(series key, position) of a video."""
    for key, (_, videos) in SERIES.items():
        for n, (slug, _, _) in enumerate(videos):
            if slug == name:
                return key, n
    raise KeyError(name)


def info(name: str) -> dict:
    key, n = find(name)
    series, videos = SERIES[key]
    slug, title, length = videos[n]
    return {"name": slug, "title": title, "length": length, "url": BASE_URL + slug + ".mp4", "series": key,
            "series_name": series, "position": n + 1, "count": len(videos),
            "label": (f"{n + 1} · {title}" if key == "lattice" else title)}


def neighbours(name: str) -> dict:
    """The first, previous and next videos in the same series (None at either end)."""
    key, n = find(name)
    videos = SERIES[key][1]
    return {"first": videos[0][0],
            "previous": videos[n - 1][0] if n > 0 else None,
            "next": videos[n + 1][0] if n + 1 < len(videos) else None}


# ----------------------------------------------------------------------------------------------- on the page

VIEW = "video"
WINDOW = "ang_video"

_WINDOW_JS = """
export default function(component) {
  const { parentElement } = component;
  const shell = parentElement.closest(".stBidiComponent") || parentElement;
  shell.style.display = "none";
  const holder = shell.closest('[data-testid="stElementContainer"]');
  if (holder) holder.style.display = "none";
  window.__angstromVideoWords = { close: T("Close") };     // the words follow a language switch
  if (window.__angstromVideoLinks) return;
  window.__angstromVideoLinks = true;
  // The player page in a full-screen sheet with ✕ to close (a frame of this signed-in page, like the ✨ AI panel).
  const openSheet = (href, label) => {
    let sheet = document.getElementById("ang-video-sheet");
    if (!sheet) {
      sheet = document.createElement("div");
      sheet.id = "ang-video-sheet";
      sheet.setAttribute("role", "dialog");
      sheet.innerHTML = "<div class='vs-head'><span class='vs-title'></span><button type='button' class='vs-close'></button></div><div class='vs-body'></div>";
      document.body.appendChild(sheet);
      sheet.querySelector(".vs-close").addEventListener("click", () => {
        sheet.classList.remove("is-open");
        sheet.querySelector(".vs-body").innerHTML = "";        // stops the video
        document.documentElement.style.overflow = "";
      });
    }
    const words = window.__angstromVideoWords || { close: "Close" };
    sheet.querySelector(".vs-title").textContent = "🎬 " + label.replace(/^Watch:\s*/, "");
    sheet.querySelector(".vs-close").textContent = "✕ " + words.close;
    sheet.querySelector(".vs-close").setAttribute("aria-label", words.close);
    const frame = document.createElement("iframe");
    frame.title = label;
    frame.setAttribute("allow", "autoplay; fullscreen; picture-in-picture");
    frame.setAttribute("allowfullscreen", "");
    frame.src = href + (href.includes("?") ? "&" : "?") + "inpanel=1";
    const body = sheet.querySelector(".vs-body");
    body.innerHTML = "";
    body.appendChild(frame);
    sheet.classList.add("is-open");
    document.documentElement.style.overflow = "hidden";
  };
  // Every 🎬 link opens the player in one small window of its own beside the app (reused for the next video).
  document.addEventListener("click", (event) => {
    // 🎬 links, and links to a video written by the Angstrom Assistant (…?view=video&v=…)
    const a = event.target.closest ? event.target.closest("a.ang-tv-link, a[href*='view=video&v=']") : null;
    if (!a) return;
    event.preventDefault();
    event.stopPropagation();
    // A phone, or a web app on the home screen: no second window to switch to, so the player opens over the page.
    const phone = window.matchMedia("(max-width: 640px), (display-mode: standalone) and (pointer: coarse)").matches
      || window.navigator.standalone === true;
    if (phone) { openSheet(a.href, (a.textContent || "").trim()); return; }
    const left = Math.max(0, (window.screenX || 0) + (window.outerWidth || 1200) - 940);
    const opened = window.open(a.href, "ang_video", "popup=yes,width=900,height=720,top=60,left=" + left);
    if (opened) opened.focus(); else window.open(a.href, "_blank");
  }, true);
}
"""
_WINDOW = []

_SHEET_CSS = """
#ang-video-sheet{position:fixed;inset:0;z-index:10000002;display:none;flex-direction:column;background:var(--ang-section,#fff);
  padding-top:env(safe-area-inset-top, 0px);}
#ang-video-sheet.is-open{display:flex;}
#ang-video-sheet .vs-head{flex:none;display:flex;align-items:center;gap:8px;padding:10px 12px 8px 16px;
  border-bottom:1px solid rgba(127,127,127,.25);}
#ang-video-sheet .vs-title{font-weight:650;font-size:1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
#ang-video-sheet .vs-close{margin-left:auto;flex:none;background:rgba(127,127,127,.15);border:0;border-radius:999px;
  padding:6px 12px;font:inherit;font-weight:600;cursor:pointer;color:inherit;}
#ang-video-sheet .vs-body{flex:1;min-height:0;position:relative;}
#ang-video-sheet iframe{position:absolute;inset:0;width:100%;height:100%;border:0;}
html.angstrom-night #ang-video-sheet{background:#0e1117;color:#fafafa;}
"""

_LINK_CSS = (".ang-tv-link{display:inline-flex;align-items:center;gap:6px;text-decoration:none;color:inherit;"
             "padding:2px 0;font-size:.95rem}.ang-tv-link:hover{color:var(--st-primary-color,#ff4b4b)}"
             ".ang-tv-link svg{flex:none}")
_ICON_SVG = ("<svg viewBox='0 0 24 24' width='18' height='18' fill='currentColor' aria-hidden='true'><path d='M21 3H3"
             "c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h5v2h8v-2h5c1.1 0 1.99-.9 1.99-2L23 5c0-1.1-.9-2-2-2zm0 14H3V5h18v12z"
             "M16 11l-7 4V7z'/></svg>")


def install(st) -> None:
    """The small script that makes 🎬 links open the player in its own window (over the page on a phone). Draw it once
    per page."""
    if not _WINDOW:
        _WINDOW.append(i18n.with_words(st.components.v2.component(
            "training_video_window", js=i18n.js_ready(_WINDOW_JS), css=_SHEET_CSS, isolate_styles=False), _WINDOW_JS))
    _WINDOW[0](key="training_video_window", data={})


def address(name: str) -> str:
    return f"?view={VIEW}&v={name}"


def _go(st, name: str) -> None:
    st.session_state[STATE] = name
    try:
        st.query_params["v"] = name          # a refresh of the window keeps this video
    except Exception:
        pass
    st.rerun()


def _draw_player(st, on_top: bool = False) -> None:
    name = st.session_state.get(STATE) or SERIES["lattice"][1][0][0]
    v, near = info(name), neighbours(name)
    st.markdown(f"**{v['label']}** · {v['length']}")
    st.caption(f"{v['series_name']} · {v['position']} of {v['count']}")
    row = st.container(horizontal=True, horizontal_alignment="center", gap="small")   # one row, even on a phone
    if row.button(t("Start"), icon=":material/first_page:", key="tv_first", disabled=near["previous"] is None,
                  help=t("Back to the first video of this series")):
        _go(st, near["first"])
    if row.button(t("Back"), icon=":material/chevron_left:", key="tv_prev", disabled=near["previous"] is None,
                  help=("Previous: " + info(near["previous"])["label"]) if near["previous"] else "This is the first video"):
        _go(st, near["previous"])
    if row.button(t("Next"), icon=":material/chevron_right:", key="tv_next", disabled=near["next"] is None,
                  help=("Next: " + info(near["next"])["label"]) if near["next"] else "This is the last video"):
        _go(st, near["next"])
    if on_top and hasattr(st, "components") and hasattr(st.components, "v2"):
        with row:
            _keep_on_top(st)
    st.video(v["url"], autoplay=True)
    with st.expander(t("All videos"), icon=ICON):
        for key, (series, videos) in SERIES.items():
            st.markdown(f"**{series}**")
            for slug, _, length in videos:
                w = info(slug)
                if st.button(f"{w['label']} · {length}", icon=":material/play_arrow:" if slug == name else ICON,
                             key=f"tv_pick_{slug}", type="tertiary", disabled=slug == name,
                             help="Playing now" if slug == name else "Watch this video"):
                    _go(st, slug)
    st.caption("[Open the video on its own page](%s) (full screen, or to share). Descriptive readings, not "
               "financial advice." % v["url"])


_ON_TOP_JS = """
export default function(component) {
  const { parentElement } = component;
  const button = parentElement.querySelector("button");
  if (!button) return;
  if (!document.pictureInPictureEnabled) { button.style.display = "none"; return; }
  if (button.dataset.ready) return;
  button.dataset.ready = "1";
  // Picture in picture: the browser's own small video window that stays on top of every other window.
  button.addEventListener("click", async () => {
    const video = document.querySelector("video");
    if (!video) return;
    try {
      if (document.pictureInPictureElement) await document.exitPictureInPicture();
      else { await video.requestPictureInPicture(); if (video.paused) video.play().catch(() => {}); }
    } catch (e) { button.title = "This browser would not keep the video on top: " + e.message; }
  });
}
"""
_ON_TOP_HTML = ("<button type='button' class='ang-ontop' title='Keep on top: the video moves to a small window that "
                "stays above every other window while you work in the app (picture in picture). Click again to bring "
                "it back.'><svg viewBox='0 0 24 24' width='16' height='16' fill='currentColor' aria-hidden='true'>"
                "<path d='M19 11h-8v6h8v-6zm4 8V4.98C23 3.88 22.1 3 21 3H3c-1.1 0-2 .88-2 1.98V19c0 1.1.9 2 2 2h18"
                "c1.1 0 2-.9 2-2zm-2 .02H3V4.97h18v14.05z'/></svg><span>Keep on top</span></button>")
_ON_TOP_CSS = (".ang-ontop{display:inline-flex;align-items:center;gap:6px;height:2.5rem;padding:0 12px;"
               "border-radius:.5rem;border:1px solid rgba(128,128,128,.35);background:transparent;color:inherit;"
               "font:inherit;cursor:pointer}.ang-ontop:hover{border-color:#f5a524}")
_ON_TOP = []


def _keep_on_top(st) -> None:
    if not _ON_TOP:
        _ON_TOP.append(st.components.v2.component("training_video_on_top", html=_ON_TOP_HTML, css=_ON_TOP_CSS,
                                                  js=_ON_TOP_JS, isolate_styles=False))
    _ON_TOP[0](key="tv_on_top")


def render_popout(st, name: str | None) -> None:
    """The player alone in its own window (?view=video&v=<name>)."""
    if STATE not in st.session_state:
        try:
            find(name or "")
            st.session_state[STATE] = name
        except KeyError:
            pass
    st.markdown(t("#### 🎬 Training video"))
    _draw_player(st, on_top=True)


def link(st, name: str, key: str | None = None) -> None:
    """A small 🎬 link: the video's title and length; it opens the player, in its own window, at that video."""
    import html

    v = info(name)
    tip = (f"Training video, {v['series_name']} ({v['position']} of {v['count']}). Opens in its own window, with "
           "Back, Next and Start to move through the series.")
    st.markdown(f"<style>{_LINK_CSS}</style><a class='ang-tv-link' href='{address(name)}' target='{WINDOW}' "
                f"title='{html.escape(tip, quote=True)}'>{_ICON_SVG}<span>Watch: {html.escape(v['label'])} · "
                f"{v['length']}</span></a>", unsafe_allow_html=True)


def all_links(st, key: str) -> None:
    """Every series, one 🎬 link per video; the series side by side on a wide screen."""
    cols = st.columns(len(SERIES))
    for col, (series_key, (series, videos)) in zip(cols, SERIES.items()):
        with col:
            st.markdown(f"**{series}**")
            for slug, _, _ in videos:
                link(st, slug, key=f"tv_{key}_{slug}")
