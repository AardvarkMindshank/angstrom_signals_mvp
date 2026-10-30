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
    assert 'st.session_state["_keep_write_pending"] = True' in SOURCE
    assert '_keep_cookie_write("", pref="0")' in SOURCE


def test_the_choice_is_remembered_but_never_a_token():
    assert "angstrom_keep_pref=1" in SOURCE
    assert 'st.session_state["login_keep"] = _keep_pref_read()' in SOURCE
    js = SOURCE[SOURCE.index("_KEEP_COOKIE_JS"): SOURCE.index("_keep_cookie = st.components")]
    pref_part = js[js.index('pref === "1"'):]
    assert "encodeURIComponent(value)" not in pref_part
    # logging out clears the sign-in cookie only, so the remembered choice survives it
    assert 'st.session_state.pop("_keep_clear", False):\n        _keep_cookie_write("")' in SOURCE


def test_a_token_swapped_on_page_load_also_updates_the_saved_copy():
    # An idle page's sign-in runs out; set_session then hands back a new refresh token.
    # That new token must go through _store_session_tokens, which rewrites the cookie.
    start = SOURCE.index("restored = client.auth.set_session(access, refresh)")
    block = SOURCE[start:start + 700]
    assert "if fresh.refresh_token != refresh:" in block
    assert "_store_session_tokens(fresh.access_token, fresh.refresh_token)" in block
    store = SOURCE[SOURCE.index("def _store_session_tokens"):][:400]
    assert "_keep_cookie_write(refresh)" in store
