import ast
import pathlib

SOURCE = pathlib.Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")


def test_the_pieces_are_wired():
    ast.parse(SOURCE)
    for needle in (
        '"Keep me signed in on this device"',      # the tickbox on the login form
        "refresh_session(_saved_login)",           # restore from the cookie on a fresh load
        '_keep_cookie_write("")',                  # clear on logout or a dead cookie
        "on_failure=_session_failed",              # a tab that lost its login signs out
        "Max-Age=2592000",                         # 30 days
    ):
        assert needle in SOURCE, needle


def test_pop_outs_never_touch_the_cookie():
    body = SOURCE[SOURCE.index("def _keep_cookie_write"): SOURCE.index("def _keep_cookie_write") + 400]
    assert "if _POPOUT_VIEW:" in body
    restore = SOURCE[SOURCE.index("not _POPOUT_VIEW and not st.session_state.get(\"_keep_tried\")"):][:200]
    assert "_keep_tried" in restore


def test_logout_clears_and_nothing_is_saved_without_the_tick():
    clear = SOURCE[SOURCE.index("def clear_session():"): SOURCE.index("def clear_session():") + 200]
    assert '"_keep_clear"' in clear and '"_keep_signed_in"' in clear
    assert 'st.session_state["_keep_write_pending"] = bool(keep_me)' in SOURCE
