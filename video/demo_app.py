"""
Demo page for training videos: the real Angstrom Lattice section with made-up account data (no sign-in, no
database; everything saved lives in this browser session) and live prices. Not part of the dashboard.

Address options (all optional):
  ?section=groups | sets | prism | funnels    the part shown first (default prism)
  &seed=trend | pullback            already saved: My Trend (video 3); with pullback, also the Set from video 4
  &preset=1                         open the saved Group and Set in their editors (for quick looks)
  ?view=advisor&from=lattice|app    the ✨ Angstrom Assistant window, with example answers (DEMO_ANSWERS below)
                                    instead of a call to the AI, so a recording is the same every time
  ?view=tides                       the 🌊 Tides panel, from today's readings (worked out once per process)
  ?view=advisor&from=tides&ask=passage   Today's AI Passage Plan: an example written from the same readings by
                                    fixed templates (demo_passage below), not by an AI

With DEMO_PRICES set (a folder of saved daily prices), "Run at a past moment" reads those, cut before 30 Oct 2024.

Run: streamlit run video/demo_app.py
"""

import copy
import os
import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_panel  # noqa: E402
import seed  # noqa: E402

if os.environ.get("DEMO_PRICES"):
    # Past-moment scans read the saved daily prices, cut before the protected hold-out (saved_prices.py), instead of
    # today's providers: nothing from 30 Oct 2024 onwards is loaded.
    import saved_prices  # noqa: E402
    from signal_library import replay_display  # noqa: E402

    replay_display.live_candles = saved_prices.candles

ASSETS = [
    ("crypto", "bitcoin", "Bitcoin"), ("crypto", "ethereum", "Ethereum"), ("crypto", "solana", "Solana"),
    ("crypto", "ripple", "XRP"), ("crypto", "binancecoin", "BNB"), ("crypto", "cardano", "Cardano"),
    ("crypto", "dogecoin", "Dogecoin"), ("crypto", "avalanche-2", "Avalanche"), ("crypto", "chainlink", "Chainlink"),
    ("equity", "AAPL", "Apple (AAPL)"), ("equity", "MSFT", "Microsoft (MSFT)"), ("equity", "NVDA", "NVIDIA (NVDA)"),
    ("equity", "AMZN", "Amazon (AMZN)"), ("equity", "META", "Meta (META)"), ("equity", "GOOGL", "Alphabet (GOOGL)"),
    ("equity", "TSLA", "Tesla (TSLA)"), ("equity", "NFLX", "Netflix (NFLX)"), ("equity", "JPM", "JPMorgan (JPM)"),
]


class Query:
    """Enough of the Supabase query builder for the Lattice pages. Filters are ignored: every list is this
    session's own."""

    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return lambda *a, **k: self

    def execute(self):
        self.data = self.rows
        return self


def _store() -> dict:
    if "_demo" not in st.session_state:
        which = set(str(st.query_params.get("seed", "")).split(","))
        st.session_state["_demo"] = {"configs": {c["id"]: c for c in seed.configs(which)}, "scans": {}, "seed": which}
    return st.session_state["_demo"]


@st.cache_resource
def _set_history() -> dict:
    """Worked-out history bands, kept for the whole process (as the real table keeps them), so the recording reopens
    a history that the setup already worked out."""
    return {}


class HistoryQuery(Query):
    def __init__(self):
        super().__init__([dict(v) for v in _set_history().values()])

    def upsert(self, row, **_):
        _set_history()[(row["def_hash"], row["asset_key"])] = dict(row)
        return self


@st.cache_resource(show_spinner="Reading the macro currents…")
def _tides_snap() -> dict:
    """Today's Tides readings, worked out once for the whole process (as the worker saves one for everyone)."""
    import tides

    return tides.build(None)


DEMO_WATCHLIST = {"crypto": {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "solana": "Solana"},
                  "stock": {"AAPL": "Apple", "NVDA": "NVIDIA", "JPM": "JPMorgan"}}


class DemoDb:
    def table(self, name):
        s = _store()
        if name == "tides_snapshots":
            snap = _tides_snap()
            return Query([{"body": snap, "computed_at": snap.get("computed_at")}])
        if name == "set_history":
            return HistoryQuery()
        if name == "analysis_configs":
            return Query([{k: v for k, v in c.items() if k != "versions"} for c in s["configs"].values()])
        if name == "analysis_config_versions":
            return Query([v for c in s["configs"].values() for v in c["versions"]])
        if name == "prism_scans":
            return Query(list(s["scans"].values()))
        if name == "set_studies":
            return Query(list(s.setdefault("studies", {}).values()))
        if name == "funnels":                    # the funnel video: funnels made on this page
            return Query(list(s.setdefault("funnels", {}).values()))
        return Query([])                 # run history and anything else: nothing yet

    def rpc(self, name, params=None):
        s, params = _store(), params or {}
        if name == "analysis_create_config":
            cid = f"cfg-{uuid.uuid4().hex[:8]}"
            s["configs"][cid] = seed.config(cid, params["kind"], copy.deepcopy(params["body"]))
            return Query(cid)
        if name == "analysis_save_version":
            c = s["configs"][params["cfg"]]
            if params.get("expected_version") != c["current_version"]:
                raise RuntimeError("conflict")
            c["current_version"] += 1
            c["versions"].append(seed._version(c["id"], c["current_version"], copy.deepcopy(params["body"])))
            return Query(c["current_version"])
        if name == "prism_put_scan":
            sid = params["p_id"] or str(uuid.uuid4())
            o = params["p_scan"]
            s["scans"][sid] = {"id": sid, "owner_id": seed.USER, "name": o["name"], "set_body": o["set"],
                               "set_source": o.get("source") or {}, "schedule": o["schedule"], "notify": o["notify"],
                               "paused": o["paused"], "assets": o["assets"], "snoozes": o["snoozes"],
                               "alert_mode": "change", "set_version": 1}
            return Query(sid)
        if name in ("analysis_archive_config", "analysis_restore_config"):
            s["configs"][params["cfg"]]["archived"] = name == "analysis_archive_config"
            return Query(None)
        if name == "request_set_study":          # queued, never worked out on this page
            s.setdefault("studies", {})[params["set_hash"]] = {"set_hash": params["set_hash"], "status": "queued"}
            return Query("queued")
        if name == "funnel_save":
            fid = params.get("p_id") or str(uuid.uuid4())
            s.setdefault("funnels", {})[fid] = {
                "id": fid, "owner_id": seed.USER, "name": params["p_name"], "direction": params["p_direction"],
                "market": params.get("p_market") or "crypto", "stages": copy.deepcopy(params["p_stages"]),
                "flicker": params["p_flicker"], "alerts": params["p_alerts"], "paused": params["p_paused"],
                "pool": params.get("p_pool") or {}, "stages_version": 1, "created_at": str(len(s["funnels"]))}
            return Query(fid)
        if name == "funnel_delete":
            s.setdefault("funnels", {}).pop(params["p_id"], None)
            return Query(None)
        if name == "prism_delete_scan":
            s["scans"].pop(params["p_id"], None)
            return Query(None)
        return Query([])


# Example answers for the Assistant video, in the Assistant's own style (its rules are advisor.RULES). The video says
# they are examples. Matched on words in the question; anything else gets the last one.
DEMO_ANSWERS = [
    ("breakout", """Good idea to test. Build it as a Set with a **THEN box**:

1. In **Signal Sets**, add the **Recent structure break** Group and the **Relative volume** signal.
2. Tap **+ ⏭ THEN box**. Under **1 · First**: *An upward break in the last 3 daily candles is met*, and *Relative volume is at least 1.5*.
3. Under **2 · Then, within** 5 daily closes: *Relative volume is at most 1.5*.
4. Save it, then tap **🔬 Study this Set**. It compares what happened after each fading breakout with comparable ordinary days, and says plainly if there was no clear difference.

The worked example shows every step: [🎬 Breakout fading: a THEN box](?view=video&v=w4-breakout-fading)"""),
    ("", """That's **Prism Scan**. On the left are your Sets and the ones **Provided by Angstrom Signals**: the small icons say what each looks at, and the last mark is its study (⚖️ means it was studied and showed no clear difference from comparable days).

- Tap **+** on a Set, or drag it onto the board, to start a scan.
- **▶** runs it now on your watchlist; **⏪** rebuilds a past moment.
- Each scan can run on a schedule and alert you when an asset turns Yes.

It describes conditions; it isn't a forecast. More in [🎬 Prism Scan](?view=video&v=05-prism-scan)"""),
]


def demo_passage(snap: dict, watchlist: dict) -> str:
    """An example passage plan in the Navigator's layout, written from the readings by fixed templates (the video
    says it is an example)."""
    from datetime import datetime, timezone

    import macro_calendar as mc
    import tides as td

    now = datetime.now(timezone.utc)
    t, sea = snap["tide"], snap.get("sea") or {}
    name, plain, _ = td.TIDE_WORDS[t["label"]]
    fams = ", ".join(f"{td.FAMILIES[f][0].lower()} {v:+.2f}" for f, v in (t.get("families") or {}).items())
    out = ["**⚓ Conditions**", "",
           f"{name} ({plain}), score {t['score']:+.2f}, held {t['held_days']} trading days. Sea "
           f"{sea.get('state', 'unknown')} ({sea.get('plain', '')}). Family pulls: {fams}.", "",
           "**🌦️ Weather on the route**", ""]
    week = [e for e in mc.upcoming(now, days=7) if e["at"] >= now]
    out += [f"- {e['short']} ({e['reference']}), {mc.when_words(e['at'], now)}: tends to move rates, the dollar "
            "and fear." for e in week] or ["- No major scheduled release in the next 7 days."]
    out += ["", "**⛵ Your vessels**", ""]
    wind_words = {"tailwind": "tailwind", "headwind": "headwind"}
    for market, names in (("crypto", ", ".join(watchlist["crypto"].values())),
                          ("equity", ", ".join(watchlist["stock"].values()))):
        w = (snap.get("winds") or {}).get(market)
        if w:
            out.append(f"- {w['name']} ({names}): {wind_words.get(w['wind'], 'no clear wind')}, led by "
                       + ", ".join(td.SPEC[k]["name"] for k in w["drivers"]) + ".")
    extreme = [c for c in (snap.get("currents") or {}).values()
               if c.get("status") == "ok" and c.get("band") in ("very high", "very low")]
    out += ["", "**🪨 Hazards**", ""]
    out += [f"- {c['name']} is {c['band']} against its last 5 years ({c['score']:.0f}/100)." for c in extreme[:3]] \
        or ["- No current is at an extreme band."]
    out += ["", "**🔭 Things to watch**", "",
            f"- Expectation: the Tide stays at \"{name.lower()}\" for the next 5 closes. A score back across the "
            "±0.20 line would show it wrong (5 trading days)."]
    return "\n".join(out)


def _demo_ask(history, question, system, post=None, images=None, **kwargs):
    if "Passage Plan" in question:
        return demo_passage(_tides_snap(), DEMO_WATCHLIST)
    q = question.lower()
    return next(a for key, a in DEMO_ANSWERS if key in q)


st.set_page_config(page_title="Angstrom Signals", layout="wide")
st.markdown("<style>header[data-testid='stHeader'],[data-testid='stToolbar'],[data-testid='stDecoration']"
            "{display:none!important} .block-container{padding-top:1.2rem!important}"
            "</style>", unsafe_allow_html=True)
if st.query_params.get("view") == "advisor":
    import advisor  # noqa: E402
    import ai_providers  # noqa: E402

    advisor.available = lambda: True
    ai_providers.available = lambda provider: True       # no AI is called: the answers are the examples above
    ai_providers.pick = lambda use, chosen: "claude"
    advisor.ask = _demo_ask
    lattice_panel.render_popout(st, DemoDb(), seed.USER, str(st.query_params.get("from") or "lattice"),
                                watchlist=DEMO_WATCHLIST, auto=str(st.query_params.get("ask") or ""))
    st.stop()
if st.query_params.get("view") == "tides":
    import tides_view  # noqa: E402

    st.markdown("<div class='tides-demo'></div>", unsafe_allow_html=True)
    st.subheader("🌊 Tides (preview)")

    def _buttons():
        lattice_panel.advisor_button(st, "tides", key="tides_navigator", label="AI Navigator")
        lattice_panel.advisor_button(st, "tides", key="tides_passage", label="Today's AI Passage Plan",
                                     ask="passage", tip=tides_view.PASSAGE_TIP)

    tides_view.render_panel(st, _tides_snap(), "1Y", lambda picked: None, _buttons)
    st.stop()
store = _store()
if "show_provided" not in st.session_state:
    st.session_state["show_provided"] = st.query_params.get("provided", "1") != "0"
if "lattice_section" not in st.session_state:
    st.session_state["lattice_section"] = st.query_params.get("section", "prism")
    if st.query_params.get("preset"):
        if seed.MY_TREND in store["configs"]:
            st.session_state["lattice_start"] = f"saved:{seed.MY_TREND}"
        if seed.PULLBACK in store["configs"]:
            st.session_state["lattice_set_start"] = f"saved:{seed.PULLBACK}"
lattice_panel.render(st, DemoDb(), ASSETS, user_id=seed.USER)
