"""Sentiment inputs and outputs: duplicates, relevance, freshness, publisher repeats, model replies,
coverage, article reuse and the history record."""

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import market_store
import news_filter as nf
import sentiment as se
from sentiment_spread import coverage_badge, spread_html

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def item(title, source="Reuters", hours_ago=1.0, published=None):
    when = format_datetime(NOW - timedelta(hours=hours_ago)) if published is None else published
    return {"title": title, "source": source, "published": when, "link": "https://example.com/" + title[:8]}


def clean(items, query="Bitcoin BTC cryptocurrency", market=False, limit=8):
    terms = {} if market else nf.asset_terms(query)
    return nf.clean_headlines(items, NOW.timestamp(), terms, limit)


# ---- duplicates -----------------------------------------------------------------------------------

def test_exact_duplicates_count_once():
    kept, stats = clean([item("Bitcoin ETF sees record inflows", "Reuters", 1),
                         item("Bitcoin ETF sees record inflows", "Reuters", 2)])
    assert len(kept) == 1 and stats["duplicates"] == 1


def test_same_event_from_several_outlets_counts_once_and_notes_the_others():
    kept, stats = clean([
        item("Bitcoin ETF sees record $1.2 billion inflows", "Reuters", 1),
        item("Record $1.2 billion inflows into Bitcoin ETF", "CoinDesk", 2),
        item("Bitcoin ETFs log record inflows of $1.2 billion", "Bloomberg", 3),
        item("Bitcoin miners sell as hashprice falls", "The Block", 4),
    ])
    titles = [k["title"] for k in kept]
    assert len(kept) == 2 and "Bitcoin miners sell as hashprice falls" in titles
    first = kept[0]
    assert first["also_reported"] == 2 and set(first["also_sources"]) == {"CoinDesk", "Bloomberg"}
    assert stats["duplicates"] == 2


def test_different_stories_about_the_same_asset_are_kept():
    kept, _ = clean([item("Bitcoin falls below $60,000 as traders cut risk", "Reuters"),
                     item("El Salvador adds more Bitcoin to reserves", "CNBC")])
    assert len(kept) == 2


def test_article_id_is_stable_and_ignores_punctuation_and_case():
    a = nf.article_id({"title": "Bitcoin ETF: record inflows!", "source": "Reuters"})
    b = nf.article_id({"title": "bitcoin etf record inflows", "source": "reuters"})
    assert a == b and len(a) == 16
    assert a != nf.article_id({"title": "Bitcoin ETF record inflows", "source": "CNBC"})


# ---- relevance ------------------------------------------------------------------------------------

def test_headlines_that_do_not_name_the_asset_are_dropped():
    kept, stats = clean([item("Bitcoin rallies after Fed decision"),
                         item("Top 5 altcoins to watch this week", "Coin Blog"),
                         item("BTC funding rates turn negative", "The Block")])
    assert [k["title"] for k in kept] == ["Bitcoin rallies after Fed decision", "BTC funding rates turn negative"]
    assert stats["irrelevant"] == 1


def test_ticker_and_short_name_need_their_capitals():
    terms = nf.asset_terms("Near Protocol NEAR cryptocurrency")
    assert terms["ticker"] == "NEAR" and terms["aliases"] == ["Near"]
    assert nf.is_relevant("NEAR jumps 10% on AI news", terms)
    assert nf.is_relevant("Near Protocol unveils new chain", terms)
    assert not nf.is_relevant("Stocks near record highs", terms)
    assert not nf.is_relevant("Bitcoin nears $70,000", nf.asset_terms("Sui SUI cryptocurrency"))


def test_company_name_without_suffix_and_first_word_match():
    terms = nf.asset_terms("Microsoft Corporation MSFT stock")
    assert terms["names"] == ["microsoft"] and terms["ticker"] == "MSFT"
    assert nf.is_relevant("Microsoft beats on cloud revenue", terms)
    generic = nf.asset_terms("Bank of America Corp BAC stock")
    assert "bank" not in generic["names"]
    assert not nf.is_relevant("Bank of England holds rates", generic)
    assert nf.is_relevant("Bank of America raises dividend", generic)


def test_market_searches_are_not_filtered_for_relevance():
    kept, stats = clean([item("Fed signals two more cuts"), item("Oil climbs on supply worries", "CNBC")], market=True)
    assert len(kept) == 2 and stats["irrelevant"] == 0


# ---- freshness and junk ---------------------------------------------------------------------------

def test_stale_undated_and_future_items_are_dropped():
    kept, stats = clean([
        item("Bitcoin fresh story", hours_ago=2),
        item("Bitcoin old story", hours_ago=24 * 8),
        item("Bitcoin undated story", published=""),
        item("Bitcoin from the future", hours_ago=-5),
    ])
    assert [k["title"] for k in kept] == ["Bitcoin fresh story"]
    assert stats["stale"] == 2 and stats["undated"] == 1
    assert kept[0]["published_at"].startswith("2026-11-03T10:00")


def test_filler_and_fund_filing_notices_are_dropped():
    kept, stats = clean([item("Apple Inc. $AAPL Stock: Birch Hill Investment Advisors LLC Decreases Stake"),
                         item("NVIDIA Corporation $NVDA Stock Holdings Increased by Wedmont Private Capital"),
                         item("NVIDIA (NVDA) Stock Price Today, Live Chart & News"),
                         item("Apple earnings beat estimates")], query="Apple Inc. AAPL stock")
    assert [k["title"] for k in kept] == ["Apple earnings beat estimates"] and stats["junk"] == 3


def test_promotional_items_are_dropped():
    kept, stats = clean([item("Bitcoin price prediction: could reach $500k"), item("New Bitcoin presale live"),
                         item("Bitcoin news", "openPR")])
    assert kept == [] and stats["junk"] == 3


# ---- diversity and coverage -----------------------------------------------------------------------

def test_one_publisher_supplies_at_most_two_headlines():
    stories = ["ETF inflows climb", "miners sell coins", "options expiry looms", "whales accumulate", "fees spike"]
    kept, stats = clean([item(f"Bitcoin {s}", "Same Outlet", i + 1) for i, s in enumerate(stories)])
    assert len(kept) == 2 and stats["same_source_cap"] == 3


def test_coverage_levels():
    assert nf.coverage([])["level"] == "none"
    thin = [{"source": "A"}, {"source": "A"}, {"source": "B"}]
    assert nf.coverage(thin) == {"events": 3, "sources": 2, "level": "thin"}
    ok = [{"source": s} for s in "ABCD"]
    assert nf.coverage(ok)["level"] == "ok"


def test_thin_news_badge_shows_only_when_thin():
    report = {"headlines": [{"score": 60}, {"score": 40}], "coverage": {"events": 2, "sources": 1, "level": "thin"}}
    assert "thin news" in coverage_badge(report) and "thin news" in spread_html(report)
    report["coverage"]["level"] = "ok"
    assert coverage_badge(report) == "" and "thin news" not in spread_html(report)
    assert coverage_badge({}) == ""


# ---- model replies ---------------------------------------------------------------------------------

class _Reply:
    status_code = 200

    def __init__(self, content):
        self.payload = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}

    def json(self):
        return self.payload


HEADS = [{"title": f"Bitcoin story {i}", "source": "S", "id": f"id{i}"} for i in range(1, 5)]


def test_out_of_range_article_scores_are_rejected_not_clamped():
    parsed = se._read_model_text(_Reply(json.dumps({"articles": [
        {"index": 1, "score": 250}, {"index": 2, "score": -5}, {"index": 3, "score": 70}, {"index": 4, "score": "x"}]})), 4)
    assert parsed["scores"] == {3: 70.0}


def test_incomplete_reply_is_not_used():
    parsed = se._read_model_text(_Reply(json.dumps({"articles": [{"index": 1, "score": 80}]})), 4)
    assert se._scored_report(parsed, HEADS) is None          # 1 of 4 scored: try the next model
    parsed = se._read_model_text(_Reply(json.dumps({"articles": [
        {"index": 1, "score": 80}, {"index": 2, "score": 60}]})), 4)
    report = se._scored_report(parsed, HEADS)
    assert report["score"] == 70 and report["scored"] == 2


def test_reply_without_json_fails_cleanly():
    assert se._read_model_text(_Reply("I cannot help with that."), 4) == {"ok": False, "reason": "model_error"}


def test_summarize_tries_the_next_model_after_an_incomplete_reply(monkeypatch):
    replies = iter([_Reply(json.dumps({"articles": [{"index": 1, "score": 90}]})),
                    _Reply(json.dumps({"articles": [{"index": i, "score": 40} for i in range(1, 5)]}))])
    monkeypatch.setattr(se, "_api_key", lambda: "k")
    monkeypatch.setattr(se, "_KEY_REJECTED", False)
    monkeypatch.setattr(se, "_post_grok", lambda *a, **k: next(replies))
    report = se._summarize("q-incomplete", HEADS)
    assert report["ok"] and report["score"] == 40 and report["model"] == se._MODELS[1]["model"]


# ---- reuse ------------------------------------------------------------------------------------------

def test_known_articles_keep_their_previous_score():
    previous = {"ok": True, "model": "m", "headlines": [{"id": "id1", "score": 80, "note": "old note"}]}
    report = {"ok": True, "model": "m", "score": 50,
              "headlines": [{"id": "id1", "score": 30}, {"id": "id2", "score": 50}]}
    se.reuse_scores(report, previous)
    assert report["headlines"][0]["score"] == 80 and report["headlines"][0]["note"] == "old note"
    assert report["score"] == 65 and report["reused_articles"] == 1


def test_scores_from_another_model_are_not_reused():
    previous = {"ok": True, "model": "old", "headlines": [{"id": "id1", "score": 80}]}
    report = {"ok": True, "model": "new", "score": 30, "headlines": [{"id": "id1", "score": 30}]}
    assert se.reuse_scores(report, previous)["score"] == 30


def test_same_articles_reuse_the_whole_report_without_asking_the_model(monkeypatch):
    heads = [dict(h) for h in HEADS]
    previous = {"ok": True, "model": "m", "score": 55, "headlines": [dict(h, score=55) for h in heads]}
    monkeypatch.setattr(se, "gather_headlines", lambda q, market=False, limit=8: ([dict(h) for h in heads], {}))
    monkeypatch.setattr(se, "_summarize", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model called")))
    report = se.analyze_market_sentiment("q-reuse", True, force=True, previous=previous)
    assert report["reused_report"] and report["score"] == 55 and report["coverage"]["events"] == 4


def test_no_relevant_headlines_gives_no_score(monkeypatch):
    monkeypatch.setattr(se, "gather_headlines", lambda q, market=False, limit=8: ([], {"irrelevant": 6}))
    report = se.analyze_market_sentiment("q-empty", True, force=True)
    assert report["ok"] is False and report["reason"] == "no_headlines"


# ---- history record ---------------------------------------------------------------------------------

class _RPC:
    def __init__(self, fail_full=False):
        self.calls, self.fail_full = [], fail_full

    def rpc(self, name, payload):
        rpc = self

        class Call:
            def execute(self):
                rpc.calls.append(dict(payload))
                if rpc.fail_full and "model" in payload:
                    raise RuntimeError("function record_sentiment_score(... model ...) does not exist")
        return Call()


REPORT = {"ok": True, "model": "grok-4.3", "score": 61.0,
          "coverage": {"events": 5, "sources": 4, "level": "ok"},
          "headlines": [{"id": f"id{i}", "title": f"t{i}", "source": "S", "score": 60 + i, "link": "https://x",
                         "published_at": "2026-11-03T10:00:00+00:00", "also_sources": ["X"]} for i in range(40)]}


def test_history_payload_carries_model_coverage_and_article_refs():
    payload = market_store.history_payload("Crypto|btc", 61.0, NOW.timestamp(), REPORT)
    assert payload["model"] == "grok-4.3" and payload["coverage"] == "ok" and payload["events"] == 5
    assert len(payload["articles"]) == market_store.HISTORY_ARTICLES_MAX
    assert set(payload["articles"][0]) == {"id", "title", "source", "link", "published_at", "score"}
    assert payload["recorded_at"].startswith("2026-11-03T12:00")


def test_history_falls_back_to_the_old_call_until_the_sql_is_run():
    client = _RPC(fail_full=True)
    market_store._record_sentiment_history(client, "Crypto|btc", 61.0, NOW.timestamp(), REPORT)
    assert len(client.calls) == 2 and set(client.calls[1]) == {"subject_key", "score", "recorded_at"}
    client = _RPC()
    market_store._record_sentiment_history(client, "Crypto|btc", 61.0, NOW.timestamp(), REPORT)
    assert len(client.calls) == 1 and client.calls[0]["articles"]


# ---- name and ticker searches ----------------------------------------------------------------------

def test_query_always_carries_the_ticker():
    assert se.sentiment_query("Crypto", "Ethereum", "ETH") == "Ethereum ETH cryptocurrency"
    assert se.sentiment_query("Crypto", "Sui", "SUI") == "Sui SUI cryptocurrency"
    assert se.sentiment_query("Stock", "Apple (AAPL)", "AAPL") == "Apple AAPL stock"
    assert se.sentiment_query("Stock", "TSM", "TSM") == "TSM stock"


def test_asset_is_searched_by_name_and_by_ticker():
    assert se.asset_searches("Ethereum ETH cryptocurrency") == ["Ethereum cryptocurrency", "ETH cryptocurrency"]
    assert se.asset_searches("Apple Inc. AAPL stock") == ["Apple Inc. stock", "AAPL stock"]
    assert se.asset_searches("TSM stock") == ["TSM stock"]
    assert se.asset_searches("crypto market outlook regulation ETF liquidity") == ["crypto market outlook regulation ETF liquidity"]


def test_an_article_found_by_both_searches_counts_once(monkeypatch):
    shared = item("Ethereum ETF approval lifts ETH", "Reuters", 1)
    feeds = {"Ethereum cryptocurrency": [shared, item("Ethereum upgrade goes live", "CoinDesk", 2)],
             "ETH cryptocurrency": [dict(shared), item("ETH staking yields climb", "The Block", 3)]}
    monkeypatch.setattr(se, "_fetch_raw", lambda q: [dict(x) for x in feeds[q]])
    monkeypatch.setattr(se.time, "time", lambda: NOW.timestamp())
    kept, stats = se.gather_headlines("Ethereum ETH cryptocurrency")
    assert len(kept) == 3 and stats["candidates"] == 4 and stats["duplicates"] == 1


def test_one_failed_search_does_not_lose_the_other(monkeypatch):
    def fetch(q):
        if q.startswith("ETH"):
            raise RuntimeError("feed down")
        return [item("Ethereum upgrade goes live", "CoinDesk", 2)]
    monkeypatch.setattr(se, "_fetch_raw", fetch)
    monkeypatch.setattr(se.time, "time", lambda: NOW.timestamp())
    assert len(se.gather_headlines("Ethereum ETH cryptocurrency")[0]) == 1
