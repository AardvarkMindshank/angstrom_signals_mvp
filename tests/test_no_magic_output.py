"""Nothing in app.py is printed onto the page by accident (16 Nov 2026).

Streamlit's "magic" writes any bare value on a line of its own (a tuple, a name, a list …) onto the page. A tuple of
i18n.mark(...) column names, there only for the translation check, showed the asset tables' column titles as loose
text above the table. This fails on any such line in the main script."""

import ast
import os

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
SHOWN = (ast.Tuple, ast.List, ast.Name, ast.Attribute, ast.BinOp, ast.Subscript, ast.Compare, ast.BoolOp,
         ast.JoinedStr, ast.Dict, ast.Set)


def test_no_bare_values_in_the_main_script():
    source = open(APP, encoding="utf-8").read()
    found = []
    for node in ast.walk(ast.parse(source)):
        for field in ("body", "orelse", "finalbody"):
            body = getattr(node, field, None)
            if not isinstance(body, list):
                continue
            for index, stmt in enumerate(body):
                if not isinstance(stmt, ast.Expr):
                    continue
                value = stmt.value
                if isinstance(value, SHOWN):
                    found.append(f"line {stmt.lineno}: {ast.get_source_segment(source, stmt)[:60]}")
                elif isinstance(value, ast.Constant) and isinstance(value.value, str) and index > 0:
                    found.append(f"line {stmt.lineno}: a loose string (not a docstring)")
    assert not found, found
