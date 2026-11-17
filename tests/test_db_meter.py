"""📏 db_meter counts Supabase requests and the bytes they return, per table or function (17 Nov 2026)."""

import httpx

import db_meter


def test_counts_requests_and_bytes_by_table():
    db_meter.install()
    db_meter.install()                       # twice is harmless
    before = db_meter.snapshot()
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 2048)))
    client.get("https://abc.supabase.co/rest/v1/asset_market?select=prices")
    client.get("https://abc.supabase.co/rest/v1/asset_market?select=closes")
    client.post("https://abc.supabase.co/rest/v1/rpc/chat_feed")
    client.get("https://example.com/not-the-database")
    used = db_meter.since(before)
    assert used["GET asset_market"] == (2, 4096)
    assert used["POST rpc chat_feed"] == (1, 2048)
    assert not any("example" in key or "other" in key for key in used)
    assert db_meter.totals(used) == (3, 6144)
    assert db_meter.lines(used)[0].startswith("GET asset_market: 2 requests, 4 KB")
