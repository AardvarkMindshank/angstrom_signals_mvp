"""The live app installs requirements.txt only: research-only packages (scipy) must not be needed to draw pages."""

import subprocess
import sys

CODE = """
import builtins
real = builtins.__import__
def block(name, *a, **k):
    if name.split('.')[0] == 'scipy':
        raise ModuleNotFoundError("No module named 'scipy'")
    return real(name, *a, **k)
builtins.__import__ = block
import perspectives, prism, prism_board, what_followed
for key, doc in prism.demo_sets().items():
    perspectives.evidence(doc, key)
print('ok')
"""


def test_prism_and_evidence_need_no_scipy():
    out = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True, cwd=".")
    assert out.stdout.strip().endswith("ok"), out.stderr[-800:]
