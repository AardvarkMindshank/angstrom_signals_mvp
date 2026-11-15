"""
🌐 Words kept in constants of modules that must not change for translation (15 Nov 2026).

Certified modules (signal_library/certification.py CODE_FILES: signals_v2.py, scoring.py, the signal library …) keep
English words in their constants, and editing those files would change the certified code. So instead of mark()-ing
them there, terms() collects them here, and i18n_check counts them as texts to translate. Where they are shown, they
go through t(word) as usual.
"""

from __future__ import annotations


def terms() -> list[str]:
    """Every word or sentence from those constants that the app shows, each once."""
    out: dict[str, None] = {}

    def add(*texts):
        for x in texts:
            if isinstance(x, str) and x.strip():
                out.setdefault(x, None)

    try:
        import signals_v2

        for words in signals_v2.CLUSTER_WORDS.values():
            add(*words)
    except Exception:
        pass
    try:
        import tides as td                            # Tides words (tides_view shows them through t())

        for _top, name, plain in td.SEA_BANDS:
            add(name, plain)
        for _top, word in td.BANDS:
            add(word)
        for name, _w, _icon in td.FAMILIES.values():
            add(name)
        for spec in td.SPEC.values():
            add(spec["name"], spec["measures"], spec["rising"], spec["falling"])
        for name, _keys in td.MARKETS.values():
            add(name)
        for name, plain, _icon in td.TIDE_WORDS.values():
            add(name, plain)
        add("headwind", "tailwind", "rising", "falling", "flat", "unknown", "neutral", "risk-supportive",
            "risk-defensive")
    except Exception:
        pass
    try:
        import lattice_editor as le
        import signal_library as sl

        for d in sl.REGISTRY.latest():               # the signals the Lattice editors offer: name and hint
            if le._usable(d):
                add(d.name, d.interpretation or d.calculation or "")
    except Exception:
        pass
    return list(out)
