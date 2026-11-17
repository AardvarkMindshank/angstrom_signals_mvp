"""Marks Angstrom's own product names in the website's pages (17 Nov 2026).

Each name inside <main> is wrapped in <b class="bt">…</b>, styled in styles.css (bold, blue-to-green). Links, scripts and
words already marked are left alone, so running it again changes nothing. Run after editing a page:

    python3 website/brand_terms.py
"""

import glob
import os
import re

TERMS = [
    "Angstrom Lattice", "AI Navigator", "AI Passage Plan", "Passage Plan", "Visualize History", "What followed",
    "Quick Snapshot", "Signal Groups", "Signal Group", "Signal Sets", "Signal Set", "Sonar oscillators", "Sea state",
    "Lattice", "Prism", "Tides", "Tide", "Funnels", "Funnel", "Navigator", "Sonar", "Groups", "Group", "Sets", "Set",
    "Trend", "Stretch", "Flow", "Candidates", "Candidate", "Flagged",
]
WORD = re.compile(r"(?<![\w-])(" + "|".join(re.escape(t) for t in TERMS) + r")(?![\w-])")
TAG = re.compile(r"(<[^>]+>)")
SKIP = {"a", "script", "style", "title", "b", "label", "option", "textarea", "button"}
HERE = os.path.dirname(os.path.abspath(__file__))


def mark(main: str) -> str:
    out, inside = [], []
    for piece in TAG.split(main):
        if piece.startswith("<"):
            name = re.match(r"</?\s*([a-zA-Z0-9]+)", piece)
            if name:
                tag = name.group(1).lower()
                if tag in SKIP and not piece.endswith("/>"):
                    if piece.startswith("</"):
                        if tag in inside:
                            inside.remove(tag)
                    else:
                        inside.append(tag)
            out.append(piece)
        elif inside:
            out.append(piece)
        else:
            out.append(WORD.sub(r'<b class="bt">\1</b>', piece))
    return "".join(out)


def main() -> None:
    for path in sorted(glob.glob(os.path.join(HERE, "*.html"))):
        text = open(path, encoding="utf-8").read()
        found = re.search(r"<main>(.*)</main>", text, flags=re.S)
        if not found:
            continue
        new = text[:found.start(1)] + mark(found.group(1)) + text[found.end(1):]
        if new != text:
            open(path, "w", encoding="utf-8").write(new)
            print(os.path.basename(path), new.count('class="bt"'))


if __name__ == "__main__":
    main()
