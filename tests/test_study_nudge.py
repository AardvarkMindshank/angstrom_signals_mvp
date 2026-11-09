import study_nudge as sn


class R:
    def __init__(self, code):
        self.status_code = code


def test_no_token_does_nothing(monkeypatch):
    monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
    assert sn.nudge(post=lambda *a, **k: (_ for _ in ()).throw(AssertionError("called"))) is False


def test_nudge_asks_github_and_keeps_quiet_between(monkeypatch):
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "t")
    calls = []

    def post(url, **kw):
        calls.append((url, kw))
        return R(204)

    sn._last[0] = 0
    assert sn.nudge(post=post, now=lambda: 1000)
    assert calls[0][0].endswith("/actions/workflows/set-studies.yml/dispatches") and calls[0][1]["json"] == {"ref": "main"}
    assert calls[0][1]["headers"]["Authorization"] == "Bearer t"
    assert sn.nudge(force=False, post=post, now=lambda: 1100) is False          # a page view soon after: quiet
    assert sn.nudge(force=False, post=post, now=lambda: 1000 + sn.QUIET + 1)
    assert sn.nudge(post=lambda *a, **k: (_ for _ in ()).throw(OSError("down")), now=lambda: 5000) is False
