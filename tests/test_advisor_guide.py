"""The Advisor's hand-written guide (advisor.RULES) must not drift from the app.

Every "quoted" button or field name in the guide has to appear somewhere in the app's code, so renaming a button
without updating the guide fails here. The lists of signals, provided Groups and Sets, and the person's own items
are built from the code and their saved items on every question, so they cannot drift.
"""

import re
from pathlib import Path

import advisor

ROOT = Path(__file__).resolve().parent.parent
NOT_UI = {"past patterns, before costs; not a forecast"}      # wording the Advisor is told to use, not a button


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_quoted_names_in_the_guide_exist_in_the_app():
    src = "".join(_flat(p.read_text(encoding="utf-8")) for p in ROOT.glob("**/*.py")
                  if p.name != "advisor.py" and "tests" not in p.parts and ".venv" not in p.parts)
    src += "".join(_flat(re.sub(r'"\s*\n\s*"', "", p.read_text(encoding="utf-8"))) for p in ROOT.glob("*.py"))
    missing = [q for q in re.findall(r'"([^"]{3,})"', _flat(advisor.RULES)) if q not in NOT_UI and q not in src]
    assert not missing, f"advisor.RULES names things the app no longer shows: {missing}"


def test_built_lists_are_included():
    prompt = advisor.system_prompt([], "u")
    assert "Signals (name, readings" in prompt and "Provided Sets" in prompt and "(none saved yet)" in prompt


def test_the_app_help_and_videos_are_in_the_briefing():
    shared, mine = advisor.system_parts([], "u", "app")
    assert "Help tabs:" in shared and "One scale for every score" in shared        # read from app.py's Help section
    assert "Overextended rally" in shared                                          # the training videos
    assert "top bar" in mine and "top bar" not in advisor.system_parts([], "u", "lattice")[1]


def test_the_shared_part_is_cached():
    sent = {}

    class Reply:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text": "ok"}]}

    import json as _json

    def post(url, timeout, headers, data):
        sent.update(_json.loads(data))
        return Reply()

    advisor.os.environ["ANTHROPIC_API_KEY"] = "test"
    try:
        assert advisor.ask([], "hi", ("shared", "mine"), post=post) == "ok"
    finally:
        del advisor.os.environ["ANTHROPIC_API_KEY"]
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"} and sent["system"][1]["text"] == "mine"
