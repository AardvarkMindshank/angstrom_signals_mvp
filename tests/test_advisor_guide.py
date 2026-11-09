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
