"""Browser check page for the provided library (library_check.js): the training-video demo page (real Lattice and
Prism, made-up account, no database)."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("video") / "demo_app.py"), run_name="__main__")
