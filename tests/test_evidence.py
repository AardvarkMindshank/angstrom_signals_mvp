import numpy as np
import pandas as pd

import evidence as ev


def planted(n=900, seed=5, strength=0.01):
    """Prices where a known factor really leads the return that follows the trade lag."""
    rng = np.random.default_rng(seed)
    signal = rng.normal(0, 1, n)
    returns = rng.normal(0, 0.01, n)
    returns[2:] += strength * signal[:-2]
    close = 100 * np.exp(np.cumsum(returns))
    index = pd.date_range("2018-01-01", periods=n)
    data = pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1.0}, index=index
    )
    lookup = dict(zip(index, signal))

    def detail(window):
        value = lookup[window.index[-1]]
        return {"score": 50 + 10 * value, "contributions": {"RSI": value}}

    return data, detail


def test_a_real_signal_is_found_and_marked_as_holding():
    data, detail = planted(strength=0.01)
    record = ev.build_evidence(data, detail_fn=detail, warmup=50)
    verdict = record["verdict"]
    assert verdict["level"] == "holds" and not verdict["reverse"]
    assert len(verdict["horizons"]) >= 2
    assert "RSI" in verdict["factors"]


def test_a_backwards_signal_is_flagged_as_reverse():
    data, detail = planted(strength=-0.01)
    record = ev.build_evidence(data, detail_fn=detail, warmup=50)
    assert record["verdict"]["level"] == "holds" and record["verdict"]["reverse"]


def test_pure_noise_gets_no_evidence():
    levels = []
    for seed in range(6):
        data, detail = planted(seed=seed, strength=0.0)
        levels.append(ev.build_evidence(data, detail_fn=detail, warmup=50)["verdict"]["level"])
    # at most a stray hint by luck; never "holds" on all of them
    assert levels.count("none") >= 4
    assert "holds" not in levels


def test_too_little_history_returns_none():
    data, detail = planted(n=200)
    assert ev.build_evidence(data, detail_fn=detail, warmup=50) is None


def test_plain_text_for_none_says_so_and_never_promises():
    data, detail = planted(seed=1, strength=0.0)
    record = ev.build_evidence(data, detail_fn=detail, warmup=50)
    record["verdict"] = {"level": "none", "reverse": False, "horizons": [], "factors": []}
    text = ev.plain_text(record)
    assert "no evidence" in text
    assert "not a forecast" in text


def test_record_is_small_and_json_safe():
    import json

    data, detail = planted()
    record = ev.build_evidence(data, detail_fn=detail, warmup=50)
    encoded = json.dumps(record)
    assert len(encoded) < 20000


FACTS = "Years tested: 4.4\n3-day horizon: rank correlation +0.01, noise band ±0.08"


def test_ai_text_accepts_known_numbers_only():
    good = "There is no evidence the score helped over the 4.4 years tested; the 3-day link of 0.01 sits inside the 0.08 noise band."
    assert ev.ai_text_ok(good, FACTS, "none")
    invented = good.replace("0.01", "0.31")
    assert not ev.ai_text_ok(invented, FACTS, "none")


def test_ai_text_rejects_promises_and_overselling():
    base = "There is no evidence the score helped over the 4.4 years tested, and you should buy now."
    assert not ev.ai_text_ok(base, FACTS, "none")
    upbeat = "This is a strong signal over the 4.4 years tested, with plenty of meaning in the 3-day link."
    assert not ev.ai_text_ok(upbeat, FACTS, "none")
    assert not ev.ai_text_ok("ok", FACTS, "none")


def test_ai_text_for_none_must_say_there_is_no_evidence():
    vague = "The score was looked at over the 4.4 years tested and the 3-day link was examined closely."
    assert not ev.ai_text_ok(vague, FACTS, "none")


def test_evidence_due():
    assert ev.evidence_due(None)
    assert not ev.evidence_due(1000.0, now=1000.0 + 3600)
    assert ev.evidence_due(1000.0, now=1000.0 + ev.REFRESH_SECONDS)


class _Query:
    def __init__(self, store, name):
        self.store, self.name, self.rows = store, name, None

    def select(self, *_):
        return self

    def eq(self, column, value):
        self.rows = [r for r in self.store.get(self.name, []) if r.get(column) == value]
        return self

    def in_(self, column, values):
        self.rows = [r for r in self.store.get(self.name, []) if r.get(column) in values]
        return self

    def upsert(self, row, on_conflict=None):
        rows = self.store.setdefault(self.name, [])
        rows[:] = [r for r in rows if r["asset_key"] != row["asset_key"]] + [row]
        self.rows = [row]
        return self

    def execute(self):
        class Result:
            pass

        result = Result()
        result.data = self.rows if self.rows is not None else self.store.get(self.name, [])
        return result


class FakeSupabase:
    def __init__(self):
        self.store = {}

    def table(self, name):
        return _Query(self.store, name)


def test_save_and_load_round_trip():
    client = FakeSupabase()
    assert ev.load_evidence(client, "Crypto|btc") is None
    assert ev.save_evidence(client, "Crypto|btc", {"version": 1, "text": "hello"})
    loaded = ev.load_evidence(client, "Crypto|btc")
    assert loaded["text"] == "hello" and loaded["computed_at"]


def test_worker_evaluates_oldest_first_and_respects_the_batch():
    client = FakeSupabase()
    data, detail = planted()
    calls = []
    original = (ev.fetch_long_history, ev.build_evidence, ev.ai_summary)
    try:
        ev.fetch_long_history = lambda kind, asset_id: (calls.append(asset_id) or data, None)
        ev.build_evidence = lambda frame: original[1](frame, detail_fn=detail, warmup=50)
        ev.ai_summary = lambda record, label: None
        catalog = {("Stock", "AAA"): "A", ("Stock", "BBB"): "B", ("Stock", "CCC"): "C"}
        ev.refresh_due_evidence(client, catalog, batch=2)
        assert len(calls) == 2
        ev.refresh_due_evidence(client, catalog, batch=2)
        assert sorted(set(calls)) == ["AAA", "BBB", "CCC"]  # the third got its turn
        stored = {row["asset_key"] for row in client.store["asset_evidence"]}
        assert len(stored) == 3
    finally:
        ev.fetch_long_history, ev.build_evidence, ev.ai_summary = original
