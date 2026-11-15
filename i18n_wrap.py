"""
🌐 Puts on-screen text through t() in bulk (15 Nov 2026): the labels, captions, messages and help of Streamlit calls.

    python i18n_wrap.py app.py tides_view.py …     rewrites the files in place, prints how many texts it wrapped
    python i18n_wrap.py --display tides_view.py   also the sentences inside functions (HTML, hover text, notes)

What it wraps: the first argument (the label or the text) and help= / placeholder= of the calls in UI, when that is a
plain string or an f-string with real words in it. An f-string becomes a template with named values, so the
translation can move them: f"From {n} coins" → t("From {n} coins", n=n). Format specs stay in the template
({price:,.2f}).

What it leaves alone, on purpose:
* option lists (radio, selectbox …): code often compares the choice with the English words, so those are converted
  by hand, with format_func;
* markup without words (style blocks, scripts, layout HTML);
* anything inside a function whose name says admin (the admin panel stays in English);
* text already in t().
"""

from __future__ import annotations

import ast
import re
import sys

UI = {"markdown", "caption", "write", "button", "checkbox", "radio", "selectbox", "multiselect", "info", "warning",
      "error", "success", "subheader", "header", "title", "toggle", "text_input", "text_area", "number_input",
      "slider", "select_slider", "expander", "popover", "metric", "toast", "download_button", "link_button",
      "form_submit_button", "pills", "segmented_control", "date_input", "time_input", "color_picker",
      "file_uploader", "tracked_expander", "section_expander", "spinner", "status"}
KEYWORDS = ("help", "placeholder", "label")
_TAG = re.compile(r"<[^>]+>")


def _words(text: str) -> bool:
    """Real words outside any markup (at least one 3-letter word)."""
    if "<style" in text or "<script" in text or "@keyframes" in text:
        return False
    return bool(re.search(r"[A-Za-z]{3}", _TAG.sub(" ", text)))


def _admin(stack: list[str]) -> bool:
    return any("admin" in name.lower() for name in stack)


def _ident(src: str, used: set) -> str:
    """A value's name in the template: the variable's own name when it is one, else a short name from it."""
    base = re.sub(r"[^A-Za-z0-9_]+", "_", src).strip("_").lower()
    base = re.sub(r"_+", "_", base)[:24] or "value"
    if base[0].isdigit():
        base = "v_" + base
    name, k = base, 2
    while name in used:
        name, k = f"{base}_{k}", k + 1
    used.add(name)
    return name


def template(node: ast.JoinedStr, source: str):
    """(template, [(name, expression source)…]) for an f-string, or None when it cannot be made safely."""
    parts, values, used, seen = [], [], set(), {}
    for piece in node.values:
        if isinstance(piece, ast.Constant):
            parts.append(str(piece.value).replace("{", "{{").replace("}", "}}"))
            continue
        if not isinstance(piece, ast.FormattedValue):
            return None
        expr = ast.get_source_segment(source, piece.value)
        if expr is None:
            return None
        spec = ""
        if piece.format_spec is not None:
            if not all(isinstance(v, ast.Constant) for v in piece.format_spec.values):
                return None
            spec = ":" + "".join(str(v.value) for v in piece.format_spec.values)
        conv = {-1: "", 115: "!s", 114: "!r", 97: "!a"}.get(piece.conversion, "")
        if expr in seen:
            name = seen[expr]
        else:
            name = expr if expr.isidentifier() and expr not in used else _ident(expr, used)
            used.add(name)
            seen[expr] = name
            values.append((name, expr))
        parts.append("{" + name + conv + spec + "}")
    return "".join(parts), values


def _replacement(node, source: str) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if not _words(node.value):
            return None
        return f"t({ast.get_source_segment(source, node)})"
    if isinstance(node, ast.JoinedStr):
        made = template(node, source)
        if made is None:
            return None
        text, values = made
        plain = "".join(str(v.value) for v in node.values if isinstance(v, ast.Constant))
        if not _words(plain):
            return None
        args = "".join(f", {name}={expr}" for name, expr in values)
        return f"t({text!r}{args})"
    return None


def edits(source: str) -> list[tuple[int, int, str]]:
    """(start offset, end offset, new text) for every text to wrap, in the file."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def offset(lineno, col):
        return starts[lineno - 1] + len(lines[lineno - 1].encode("utf-8")[:col].decode("utf-8", "ignore"))

    out = []

    def visit(node, stack):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            stack = stack + [node.name]
        if isinstance(node, ast.Call) and not _admin(stack):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else "")
            if name in UI:
                targets = list(node.args[:1]) + [k.value for k in node.keywords if k.arg in KEYWORDS]
                for target in targets:
                    new = _replacement(target, source)
                    if new:
                        out.append((offset(target.lineno, target.col_offset),
                                    offset(target.end_lineno, target.end_col_offset), new))
        for child in ast.iter_child_nodes(node):
            visit(child, stack)

    visit(tree, [])
    return sorted(set(out), reverse=True)


SKIP_CALLS = {"print", "getattr", "setattr", "hasattr", "isinstance", "get", "pop", "setdefault", "startswith",
              "endswith", "split", "rsplit", "replace", "strip", "lstrip", "rstrip", "join", "format", "strftime",
              "strptime", "rpc", "table", "select", "eq", "order", "execute", "upsert", "insert", "update", "delete",
              "mark", "t", "info", "debug", "warning", "exception", "log", "compile", "match", "search", "sub",
              "findall", "fullmatch", "html", "component", "markdown_to", "encode", "decode", "loads", "dumps",
              "read_text", "open", "Path", "query_params", "secrets", "environ", "getenv", "translate", "Timestamp",
              "to_datetime", "date_range", "fromisoformat", "rename", "astype", "agg", "groupby", "sort_values"}
SKIP_KEYWORDS = {"key", "data", "type", "kind", "format", "unsafe_allow_html", "language", "mime", "file_name",
                 "icon", "color", "anchor", "help_key", "on_change", "orient", "how", "errors", "name", "id"}


def _many_words(text: str) -> bool:
    """At least three real words outside markup: short words are often codes or labels that code compares."""
    if not _words(text):
        return False
    plain = _TAG.sub(" ", text).strip()
    if not plain or plain[0] in ",;:.)" or plain[0].islower():   # a piece of a sentence glued to another
        return False
    words = [w for w in plain.split() if re.search(r"[A-Za-z]{2}", w) and not re.fullmatch(r"[\w.@/-]+_[\w.@/-]*", w)]
    return len(words) >= 3


def display_edits(source: str) -> list[tuple[int, int, str]]:
    """Every display text inside functions (not only Streamlit calls): sentences of three words or more, left alone
    when they are compared, used as keys, given to a database or string method, or are docstrings."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def offset(lineno, col):
        return starts[lineno - 1] + len(lines[lineno - 1].encode("utf-8")[:col].decode("utf-8", "ignore"))

    parent: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    out = []

    def skipped(node) -> bool:
        up = parent.get(node)
        if isinstance(up, ast.JoinedStr) or isinstance(up, ast.FormattedValue):
            return True
        if isinstance(up, ast.Expr):                       # a docstring or a bare string
            return True
        if isinstance(up, (ast.Compare, ast.Subscript, ast.Assert, ast.Raise)):
            return True
        if isinstance(up, ast.Dict) and node in up.keys:
            return True
        if isinstance(up, ast.keyword) and up.arg in SKIP_KEYWORDS:
            return True
        if isinstance(up, ast.Call):
            name = up.func.attr if isinstance(up.func, ast.Attribute) else (
                up.func.id if isinstance(up.func, ast.Name) else "")
            if name in SKIP_CALLS or name in UI:
                return True
        if isinstance(up, ast.Attribute):                  # "…".join(...)
            return True
        if isinstance(up, ast.BinOp):                      # glued to other text: translate the whole by hand
            return True
        if isinstance(up, (ast.Tuple, ast.List, ast.Set)) and isinstance(parent.get(up), ast.Compare):
            return True
        return False

    def visit(node, stack, inside):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack, inside = stack + [node.name], True
        if inside and not _admin(stack) and isinstance(node, (ast.Constant, ast.JoinedStr)) and not skipped(node):
            text = node.value if isinstance(node, ast.Constant) else "".join(
                str(v.value) for v in node.values if isinstance(v, ast.Constant))
            if isinstance(text, str) and _many_words(text):
                new = _replacement(node, source)
                if new:
                    out.append((offset(node.lineno, node.col_offset), offset(node.end_lineno, node.end_col_offset), new))
            return
        for child in ast.iter_child_nodes(node):
            visit(child, stack, inside)

    visit(tree, [], False)
    return sorted(set(out), reverse=True)


def wrap(source: str, display: bool = False) -> tuple[str, int]:
    changes = display_edits(source) if display else edits(source)
    for start, end, new in changes:
        source = source[:start] + new + source[end:]
    return source, len(changes)


def main(paths: list[str]) -> int:
    display = "--display" in paths
    for path in [p for p in paths if not p.startswith("--")]:
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        after, n = wrap(before, display)
        if n:
            if "from i18n import t" not in after and "import i18n" not in after:
                after = _add_import(after)
            ast.parse(after)                               # never write a file that no longer parses
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(after)
        print(f"{path}: {n} texts wrapped")
    return 0


def _add_import(source: str) -> str:
    """`from i18n import t` after the module's __future__ import (or its docstring)."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    at = 0
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            at = node.end_lineno
        elif isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and at == 0:
            at = node.end_lineno
    lines.insert(at, "\nfrom i18n import t\n")
    return "".join(lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
