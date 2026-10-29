import base64
import json

from session_guard import FreshClient, needs_refresh, token_expiry


def make_token(exp):
    def part(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    return f"{part({'alg': 'HS256'})}.{part({'exp': exp})}.sig"


class Session:
    def __init__(self, access, refresh):
        self.access_token, self.refresh_token = access, refresh


class Restored:
    def __init__(self, access, refresh):
        self.session = Session(access, refresh)


class Auth:
    def __init__(self):
        self.calls = []

    def set_session(self, access, refresh):
        self.calls.append((access, refresh))
        return Restored(make_token(10_000), "new-refresh")


class Postgrest:
    def __init__(self):
        self.tokens = []

    def auth(self, token):
        self.tokens.append(token)


class Client:
    def __init__(self):
        self.auth, self.postgrest = Auth(), Postgrest()
        self.asked = []

    def table(self, name):
        self.asked.append(name)
        return name


def build(access, in_page=True, skip=False):
    client = Client()
    state = {"tokens": (access, "old-refresh")}
    fresh = FreshClient(
        client,
        get_tokens=lambda: state["tokens"],
        store_tokens=lambda a, r: state.update(tokens=(a, r)),
        in_page_thread=lambda: in_page,
        skip_refresh=lambda r: skip,
    )
    return fresh, client, state


def test_expiry_reading():
    assert token_expiry(make_token(123)) == 123
    assert token_expiry("not a token") is None
    assert needs_refresh(make_token(1000), now=950)
    assert not needs_refresh(make_token(1000), now=100)
    assert not needs_refresh("junk", now=0)


def test_a_token_that_ran_out_is_replaced_and_stored():
    fresh, client, state = build(make_token(1))
    assert fresh.table("asset_market") == "asset_market"
    assert len(client.auth.calls) == 1
    assert state["tokens"][1] == "new-refresh"
    assert client.postgrest.tokens == [state["tokens"][0]]


def test_a_good_token_is_left_alone():
    fresh, client, state = build(make_token(9_999_999_999))
    fresh.table("asset_market")
    assert client.auth.calls == []


def test_background_threads_and_popouts_never_refresh():
    fresh, client, _ = build(make_token(1), in_page=False)
    fresh.table("x")
    assert client.auth.calls == []
    fresh, client, _ = build(make_token(1), skip=True)
    fresh.table("x")
    assert client.auth.calls == []


def test_other_attributes_pass_through_and_failures_do_not_break_queries():
    fresh, client, _ = build(make_token(1))
    assert fresh.auth is client.auth

    class Broken(Auth):
        def set_session(self, a, r):
            raise RuntimeError("boom")

    client.auth = Broken()
    assert fresh.table("asset_market") == "asset_market"
