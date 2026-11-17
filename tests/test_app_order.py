"""Streamlit runs app.py from top to bottom, so code that runs at page level must only call functions defined above
it (17 Nov 2026: the Account section called _chat_blocked before its definition, and signing in failed)."""

import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _page_level_calls(node, out):
    """Calls made while the page runs: everything outside function and class bodies."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            out.append((child.func.id, child.lineno))
        _page_level_calls(child, out)


def test_page_level_code_only_calls_functions_defined_above_it():
    tree = ast.parse(open(os.path.join(ROOT, "app.py"), encoding="utf-8").read())
    defined_at = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_at.setdefault(node.name, node.lineno)
    calls = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _page_level_calls(node, calls)
    early = sorted({(name, line) for name, line in calls if name in defined_at and defined_at[name] > line})
    assert not early, f"called before defined (name, line): {early[:10]}"
