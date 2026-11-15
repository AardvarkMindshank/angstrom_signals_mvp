"""Every piece of browser code (component JavaScript) parses (16 Nov 2026).

A Python-style '# comment' typed into the CSS list inside the brand script broke the whole page header and sidebar
on the live site ("BidiComponent Error: Invalid character '#'"); the Python tests could not see it. This parses
each module-level *_JS string (as the page gets it, with the translation helper put in) and each shipped .js file
with Node. Skipped when Node is not installed."""

import ast
import glob
import os
import shutil
import subprocess
import tempfile

import pytest

import i18n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")


def _scripts():
    found = []
    for path in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
        if path.endswith(("i18n_wrap.py",)):
            continue
        source = open(path, encoding="utf-8").read()
        if "_JS" not in source:
            continue
        for node in ast.parse(source).body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id.endswith("_JS")):
                try:
                    value = ast.literal_eval(node.value)
                except Exception:
                    continue                           # built from other values at run time
                if isinstance(value, str) and value.strip():
                    found.append((f"{os.path.basename(path)}:{node.targets[0].id}", i18n.js_ready(value)))
    for path in sorted(glob.glob(os.path.join(ROOT, "*.js"))):
        if not path.endswith("_check.js"):
            found.append((os.path.basename(path), open(path, encoding="utf-8").read()))
    return found


@pytest.mark.skipif(NODE is None, reason="Node is not installed")
def test_every_component_script_parses():
    scripts = _scripts()
    assert len(scripts) > 20
    broken = []
    with tempfile.TemporaryDirectory() as folder:
        for name, code in scripts:
            module = "export default" in code or "import " in code.split("\n", 1)[0]
            target = os.path.join(folder, "s.mjs" if module else "s.js")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(code)
            result = subprocess.run([NODE, "--check", target], capture_output=True, text=True, timeout=60)
            if result.returncode:
                first = next((line for line in result.stderr.splitlines() if "Error" in line), result.stderr[:200])
                broken.append(f"{name}: {first}")
    assert not broken, broken
