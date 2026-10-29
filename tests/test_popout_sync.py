import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")


def test_main_page_follows_popout_picks_quietly():
    ast.parse(SOURCE)
    assert '_asset_follow(key="asset_follow", data={"quiet": True})' in SOURCE   # main page listens
    assert '_asset_follow(key="asset_follow", data={"quiet": False})' in SOURCE  # pop-outs as before
    assert 'raw.endswith("|quiet")' in SOURCE
    body = SOURCE[SOURCE.index("def _take_alert_pick"): SOURCE.index("def _take_alert_pick") + 1600]
    # A quiet pick sets the chart and stops before it scrolls or opens a section.
    assert body.index("if quiet:") < body.index('scroll_target = "interactive-chart"')


def test_main_page_does_not_ask_other_tabs_for_their_asset():
    js = SOURCE[SOURCE.index("_ASSET_FOLLOW_JS"): SOURCE.index("_asset_follow = st.components")]
    assert 'if (!quiet) channel.postMessage({ type: "hello" })' in js
