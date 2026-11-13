"""A saved funnel is checked straight away (GitHub's funnel job for that one funnel), not at the next hourly run."""

import pandas as pd

import funnel_runner as fr
import study_nudge


class _Resp:
    status_code = 204


def test_run_funnel_now_asks_github_for_that_funnel(monkeypatch):
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "x")
    sent = {}

    def post(url, **kw):
        sent.update(url=url, **kw)
        return _Resp()

    assert study_nudge.run_funnel_now("abc", post=post)
    assert sent["url"].endswith("/actions/workflows/funnel.yml/dispatches")
    assert sent["json"] == {"ref": "main", "inputs": {"funnel_id": "abc"}}


def test_no_token_no_call(monkeypatch):
    monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
    assert not study_nudge.run_funnel_now("abc", post=lambda *a, **k: 1 / 0)
    assert not study_nudge.run_funnel_now("", post=lambda *a, **k: 1 / 0)


def test_run_all_only_one(monkeypatch):
    ran = []

    class Store:
        def active_funnels(self):
            return [{"id": "a", "name": "A", "owner_id": "u1", "stages": []},
                    {"id": "b", "name": "B", "owner_id": "u2", "stages": []}]

        def universe(self, market):
            return {"btc": {"symbol": "BTC", "name": "Bitcoin"}}

    monkeypatch.setattr(fr, "run_funnel", lambda store, f, *a, **k: ran.append(f["id"]) or {})
    out = fr.run_all(Store(), evaluate=None, now=pd.Timestamp("2026-11-13 10:20", tz="UTC"), log=lambda m: None,
                     only="b")
    assert ran == ["b"] and out["funnels"] == 1
