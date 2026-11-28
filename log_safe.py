"""Logs are public (the repository is), so they never show who a member is: a short tag stands in for the account,
enough to follow one member through a run's log without naming them (28 Nov 2026)."""
import hashlib


def tag(user_id) -> str:
    return "member-" + hashlib.sha256(str(user_id or "").encode()).hexdigest()[:6]
