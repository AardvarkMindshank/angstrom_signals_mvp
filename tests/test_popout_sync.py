import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")


def test_main_page_follows_popout_picks_quietly():
    ast.parse(SOURCE)
    assert '_asset_follow(key="asset_follow", data={"quiet": True})' in SOURCE   # main page listens
    assert '_asset_follow(key="asset_follow", data={"quiet": False})' in SOURCE  # pop-outs as before
    assert 'raw.endswith("|quiet")' in SOURCE
    start = SOURCE.index('quiet = raw.endswith("|quiet")', SOURCE.index("def _take_alert_pick"))
    body = SOURCE[start: start + 1600]
    # A quiet pick sets the chart and stops before it scrolls or opens a section.
    assert body.index("if quiet:") < body.index('scroll_target = "interactive-chart"')


def test_main_page_does_not_ask_other_tabs_for_their_asset():
    js = SOURCE[SOURCE.index("_ASSET_FOLLOW_JS"): SOURCE.index("_asset_follow = st.components")]
    assert 'if (!quiet) channel.postMessage({ type: "hello" })' in js


def test_lattice_popout_sends_visualize_history_to_the_main_window():
    js = SOURCE[SOURCE.index("_ASSET_FOLLOW_JS"): SOURCE.index("_asset_follow = st.components")]
    assert 'msg.type === "chart_jump"' in js and "quiet)" in js           # only the main page takes it
    pick = SOURCE[SOURCE.index("def _take_alert_pick"):]
    assert 'raw.startswith("jump|")' in pick[:2500] and 'st.session_state["_chart_jump"]' in pick[:2500]
    pop = SOURCE[SOURCE.index('if _POPOUT_VIEW == "lattice_panel":'):]
    assert pop.index('_chart_send(key="chart_send"') < pop.index("st.stop()")
