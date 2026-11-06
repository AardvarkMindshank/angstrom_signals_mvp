"""Getting-started checklist and tap-to-explain (the browser behaviour is checked by onboarding_check.js)."""

from __future__ import annotations

import contextlib
from pathlib import Path

import onboarding as ob

ROOT = Path(__file__).resolve().parent.parent


def test_progress_counts_manual_and_automatic_steps():
    saved = ob.state({"onboarding": {"done": ["markets", "bogus"], "hidden": False}})
    assert saved == {"done": ["markets"], "hidden": False}
    rows = ob.progress(saved, {"watchlist": True, "prism": False})
    done = {r[0]: (r[4], r[5]) for r in rows}
    assert done["markets"] == (True, False) and done["watchlist"] == (True, True) and done["prism"] == (False, False)
    assert ob.visible(saved, {})
    assert not ob.visible({"done": [k for k, *_ in ob.STEPS], "hidden": False}, {})       # all done: hides itself
    assert not ob.visible({"done": [], "hidden": True}, {})


class St:
    def __init__(self, ticks=None, hide=False):
        self.ticks, self.hide, self.shown = ticks or {}, hide, []

    def container(self, *a, **k):
        return contextlib.nullcontext()

    def columns(self, spec, **k):
        return [self, self]

    def markdown(self, text, *a, **k):
        self.shown.append(text)

    caption = markdown

    def progress(self, value):
        self.shown.append(value)

    def button(self, label, key=None, **k):
        return self.hide and key == "onboarding_hide"

    def checkbox(self, label, value=False, key=None, disabled=False, **k):
        return self.ticks.get(key, value)

    def rerun(self):
        raise RuntimeError("rerun")


def test_ticking_and_hiding_save_on_the_account():
    saved = []
    st = St(ticks={"onboarding_markets": True})
    try:
        ob.render(st, {}, {}, saved.append)
    except RuntimeError:
        pass
    assert saved == [{"onboarding": {"done": ["markets"], "hidden": False}}]
    saved.clear()
    try:
        ob.render(St(hide=True), {}, {}, saved.append)
    except RuntimeError:
        pass
    assert saved[0]["onboarding"]["hidden"] is True
    shown = St()
    ob.render(shown, {}, {"watchlist": True}, saved.append)
    assert any("1 of 5 done" in str(s) for s in shown.shown)
    ob.show_again({"onboarding": {"done": [], "hidden": True}}, saved.append)
    assert saved[-1]["onboarding"]["hidden"] is False


def test_tap_to_explain_never_presses_a_button_on_a_plain_tap_and_explain_mode_is_a_setting():
    js = ob.TAP_JS
    assert "if (n && !acts(path, n.el)) { show(n); return; }" in js         # a plain tap explains only non-actions
    assert "e.preventDefault(); e.stopPropagation(); show(n)" in js          # Explain mode explains instead of acting
    assert ".st-key-explain_mode" in js                                     # the switch itself always works
    app = (ROOT / "app.py").read_text()
    settings = app[app.index('with tracked_expander("⚙️ Settings"'):app.index("def _feedback_setting")]
    assert '"❓ Explain mode"' in settings and '"explain_mode": bool(explain_mode)' in settings
    assert '"explain_mode",' in app[app.index("_ACCOUNT_STATE_KEYS = ("):app.index("_ACCOUNT_STATE_KEYS = (") + 200]
    assert "_onboarding.tap_explain(st" in app and "_onboarding.render(" in app
