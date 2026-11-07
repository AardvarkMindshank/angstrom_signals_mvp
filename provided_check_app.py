"""The training-video demo page, for the 🔰 provided-items browser check (provided_check.js). Not the app."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "video" / "demo_app.py"), run_name="__main__")
