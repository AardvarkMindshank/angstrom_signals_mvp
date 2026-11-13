"""
Display wording for signal definitions (13 Nov 2026): "Market Cipher" is a trademark, so the app shows our own name,
🛰️ Sonar, instead. The definitions in signals_oscillators.py keep their original wording because that file is part
of the replay certification (certification.CODE_FILES): editing it would switch off history replays until the suite
re-ran. The text is rewritten as each definition is registered, so it never reaches a page. No calculation changes.
"""

from __future__ import annotations

import dataclasses

# Longest phrases first, so a short one never cuts into a longer one.
REPLACE = (
    ("open-source \"Market Cipher B\"\nrecreation (VuManChu Cipher B)", "open-source recreation"),
    ("(Market Cipher's green dot)", "(Sonar's green ping)"),
    ("Market Cipher's green dot", "Sonar's green ping"),
    ("the mirror (red dot)", "the mirror (red ping)"),
    ("Market Cipher's ", "Sonar's "),
    ("Defaults are Market Cipher B's.", "Defaults are the published open-source ones."),
    ("Market Cipher B recreation", "open-source recreation"),
    ("VuManChu Cipher B's money-flow area", "the published open-source money-flow area"),
    ("(and VuManChu Cipher B)", "(and its open-source recreation)"),
    ("VuManChu Cipher B", "the open-source recreation"),
    ("Market Cipher B: ", "default "),
    ("(Market Cipher style)", "(Sonar)"),
    ("Market Cipher style", "Sonar"),
    ("Market Cipher B", "Sonar"),
    ("Market Cipher", "Sonar"),
)

FIELDS = ("name", "calculation", "interpretation", "limitations", "polarity")


def clean(text):
    if not isinstance(text, str):
        return text
    for old, new in REPLACE:
        text = text.replace(old, new)
    return text


def renamed(definition):
    """The same definition with display wording cleaned (compute and every number unchanged)."""
    changes = {f: clean(getattr(definition, f)) for f in FIELDS if isinstance(getattr(definition, f, None), str)}
    params = getattr(definition, "params", None) or {}
    new_params = {k: dataclasses.replace(p, doc=clean(p.doc)) if isinstance(getattr(p, "doc", None), str) else p
                  for k, p in params.items()}
    if any(changes[f] != getattr(definition, f) for f in changes) or any(
            new_params[k] is not params[k] and new_params[k].doc != params[k].doc for k in params):
        return dataclasses.replace(definition, **changes, params=new_params)
    return definition


def install(registry) -> None:
    """Clean the wording of every definition registered from now on (and any already registered)."""
    if getattr(registry, "_display_names", False):
        return
    original = registry.register

    def register(definition):
        return original(renamed(definition))

    registry.register = register
    registry._display_names = True
    for key, definition in list(getattr(registry, "_defs", {}).items()):
        registry._defs[key] = renamed(definition)
