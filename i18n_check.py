"""
🌐 Which on-screen texts still need translating (15 Nov 2026).

Finds every text the app passes to t("…") or marks with i18n.mark("…") in its Python files, and compares them with
each language's file in locales/. Lists what is missing (shows in English for now) and what is left over (text that
changed or went away, so its translation is no longer used).

    python i18n_check.py            a summary per language
    python i18n_check.py th         the missing texts for Thai, one per line
    python i18n_check.py th --json  the missing texts as a JSON object ready to fill in
"""

from __future__ import annotations

import ast
import json
import os
import sys

import i18n

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {"tests", "research", "video", "__pycache__", ".git", "node_modules", "data"}


def _python_files() -> list[str]:
    out = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        out += [os.path.join(root, f) for f in files if f.endswith(".py")]
    return sorted(out)


def texts_in(source: str) -> list[str]:
    """The literal texts given to t(…) / mark(…) / i18n.t(…) / i18n.mark(…) in one file's code."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else "")
        if name in ("t", "mark") and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            found.append(node.args[0].value)
    return found


def all_texts() -> list[str]:
    """Every translatable text in the app, each once, in the order first met."""
    seen: dict[str, None] = {}
    for path in _python_files():
        try:
            with open(path, encoding="utf-8") as fh:
                for text in texts_in(fh.read()):
                    seen.setdefault(text, None)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
    return list(seen)


def report(code: str, texts: list[str] | None = None) -> dict:
    """{missing: [...], unused: [...], done: n, total: n} for one language."""
    texts = all_texts() if texts is None else texts
    have = i18n.catalogue(code)
    missing = [x for x in texts if x not in have]
    wanted = set(texts)
    return {"missing": missing, "unused": sorted(k for k in have if k not in wanted),
            "done": len(texts) - len(missing), "total": len(texts)}


def main(argv: list[str]) -> int:
    texts = all_texts()
    if argv and argv[0] in i18n.BY_CODE:
        r = report(argv[0], texts)
        if "--json" in argv:
            print(json.dumps({x: "" for x in r["missing"]}, ensure_ascii=False, indent=2))
        else:
            print("\n".join(r["missing"]))
        return 0
    print(f"{len(texts)} texts go through t() so far.")
    for lang in i18n.LANGUAGES:
        if lang["code"] == i18n.BASE or lang["status"] == "planned":
            continue
        r = report(lang["code"], texts)
        print(f"{lang['english']} ({lang['code']}, {lang['status']}): {r['done']}/{r['total']} translated, "
              f"{len(r['missing'])} missing, {len(r['unused'])} no longer used")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
