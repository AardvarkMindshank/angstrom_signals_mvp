"""
Training videos in Help and guides: a small 🎬 link beside each topic opens the video in a pop-up player, with
buttons to go back, go on, or start the series again, and a list of every video in the series.

The videos live on the website (angstromsignals.com/videos/training/<name>.mp4), made by the pipeline in video/.
Captions are part of the picture, so nothing else needs loading. Adding a video: record it, publish it, and add a
line to SERIES below.
"""

from __future__ import annotations

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
    ]),
    "evidence": ("Reading the evidence", [
        ("06-provided-library", "The provided library", "1:18"),
        ("07-visualize-history", "Visualize History", "0:59"),
        ("08-what-followed", "What followed", "1:35"),
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

_PLAYER = None


def _player():
    """The pop-up player (one per page). It redraws only itself when you move through the series."""
    global _PLAYER
    if _PLAYER is None:
        import streamlit as st

        @st.dialog("🎬 Training video", width="medium")
        def player():
            _draw_player(st)

        _PLAYER = player
    return _PLAYER


def _go(st, name: str) -> None:
    st.session_state[STATE] = name
    try:
        st.rerun(scope="fragment")         # stay in the pop-up
    except Exception:
        st.rerun()


def _draw_player(st) -> None:
    name = st.session_state.get(STATE) or SERIES["lattice"][1][0][0]
    v, near = info(name), neighbours(name)
    st.markdown(f"**{v['label']}** · {v['length']}")
    st.caption(f"{v['series_name']} · {v['position']} of {v['count']}")
    row = st.container(horizontal=True, horizontal_alignment="center", gap="small")   # one row, even on a phone
    if row.button("Start", icon=":material/first_page:", key="tv_first", disabled=near["previous"] is None,
                  help="Back to the first video of this series"):
        _go(st, near["first"])
    if row.button("Back", icon=":material/chevron_left:", key="tv_prev", disabled=near["previous"] is None,
                  help=("Previous: " + info(near["previous"])["label"]) if near["previous"] else "This is the first video"):
        _go(st, near["previous"])
    if row.button("Next", icon=":material/chevron_right:", key="tv_next", disabled=near["next"] is None,
                  help=("Next: " + info(near["next"])["label"]) if near["next"] else "This is the last video"):
        _go(st, near["next"])
    st.video(v["url"], autoplay=True)
    with st.expander("All videos", icon=ICON):
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


def link(st, name: str, key: str | None = None) -> None:
    """A small 🎬 link: the video's title and length; it opens the player at that video."""
    v = info(name)
    if st.button(f"Watch: {v['label']} · {v['length']}", icon=ICON, key=key or f"tv_link_{name}", type="tertiary",
                 help=f"Training video, {v['series_name']} ({v['position']} of {v['count']}). Opens a player with "
                      "Back, Next and Start, to move through the series."):
        st.session_state[STATE] = name
        _player()()


def all_links(st, key: str) -> None:
    """Every series, one 🎬 link per video; the series side by side on a wide screen."""
    cols = st.columns(len(SERIES))
    for col, (series_key, (series, videos)) in zip(cols, SERIES.items()):
        with col:
            st.markdown(f"**{series}**")
            for slug, _, _ in videos:
                link(st, slug, key=f"tv_{key}_{slug}")
