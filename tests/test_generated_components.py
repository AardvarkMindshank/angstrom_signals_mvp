"""The classic editors copied into the new app (web/src/generated/) must match the classic app's own code."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_generated_components_are_up_to_date():
    gen = os.path.join(ROOT, "web", "src", "generated")
    before = {f: open(os.path.join(gen, f), encoding="utf-8").read() for f in os.listdir(gen)}
    subprocess.run([sys.executable, os.path.join(ROOT, "web", "scripts", "components.py")], check=True, capture_output=True)
    after = {f: open(os.path.join(gen, f), encoding="utf-8").read() for f in os.listdir(gen)}
    assert before == after, "Run python web/scripts/components.py and commit web/src/generated/."
