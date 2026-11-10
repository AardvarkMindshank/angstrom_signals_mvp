"""Write docs/signal_library_catalogue.md from the registry: `python signal_catalogue_doc.py`."""

from pathlib import Path

import signal_library as sl

OUT = Path(__file__).resolve().parent / "docs" / "signal_library_catalogue.md"


def entry(d: dict) -> str:
    lines = [f"### {d['name']} — `{d['key']}`", "",
             f"- **Category:** {d['category']} · **Output:** {d['output']} · **Unit:** {d['unit']} · **Scope:** {d['scope']}",
             f"- **Timeframes:** {', '.join(d['timeframes'])} · **Data:** {', '.join(d['requires'])}"]
    if d["params"]:
        lines.append("- **Parameters:** " + "; ".join(f"`{k}` = {p['default']} ({p['doc']})" for k, p in d["params"].items()))
    lines += [f"- **Calculation:** {d['calculation']}", f"- **Interpretation:** {d['interpretation']}",
              f"- **Limitations:** {d['limitations']}"]
    return "\n".join(lines)


def main() -> None:
    items = sorted((d for d in sl.REGISTRY.catalogue() if not d["id"].startswith("test.")),
                   key=lambda d: (d["category"], d["id"]))
    text = ("# Signal catalogue\n\nGenerated from the registry (`signal_library.REGISTRY.catalogue()`) by "
            "`signal_catalogue_doc.py`. Regenerate after any definition change.\n\n"
            + "\n\n".join(entry(d) for d in items) + "\n")
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(items)} signals)")


if __name__ == "__main__":
    main()
