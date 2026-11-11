"""Every jump-to marker (an empty div with scroll-margin-top) is taken out of the page flow, so it never adds a gap
between sections (it happened twice: the marker sits between two sections and takes a row gap of its own)."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"


def test_every_scroll_anchor_is_out_of_the_flow():
    source = APP.read_text()
    anchors = set()
    for m in re.finditer(r"id=['\"]([a-z][a-z0-9-]*(?:\{[^}]*\}[a-z0-9-]*)?)['\"] style=['\"]scroll-margin-top", source):
        anchors.add(m.group(1))
    rule = next(line for line in source.splitlines() if ":has(#interactive-chart)" in line and "position:absolute" in line)
    expand = {"table-": ("table-crypto", "table-equity"), "market-mood-": ("market-mood-crypto", "market-mood-stock")}
    names = set()
    for a in anchors:
        if "{" in a:                       # a name filled in at run time: each known value
            prefix = a.split("{", 1)[0]
            assert prefix in expand, f"new templated marker {a!r}: list its values here"
            names |= set(expand[prefix])
        else:
            names.add(a)
    assert len(names) >= 8
    missing = sorted(n for n in names if f":has(#{n})" not in rule)
    assert not missing, f"add these markers to the out-of-flow rule in app.py: {missing}"
