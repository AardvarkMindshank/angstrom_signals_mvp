"""The clip set check finds every clip the daily video can ask for."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video"))
import clip_audit  # noqa: E402
import daily_video as dv  # noqa: E402


def _fill(lib: Path) -> None:
    for who in dv.CHANCES:
        for line in dv.SET_LINES:
            for take in (1, 2):
                (lib / f"{who}_{line}_{take}_1.mp4").touch()
    for g in dv.GUESTS:
        for line in ("welcome", "signoff"):
            (lib / f"{g}_{line}_1_1.mp4").touch()
    for n in ["ratd_tag_1_1.mp4", "ratd_tag_2_1.mp4", dv.COOK_REVEAL, *dv.BLOOPERS]:
        (lib / n).touch()


def test_full_library_has_no_gaps(tmp_path):
    _fill(tmp_path)
    assert clip_audit.missing_clips(tmp_path) == []


def test_missing_take_two_and_guest_are_reported(tmp_path):
    _fill(tmp_path)
    (tmp_path / "mate_signoff_2_1.mp4").unlink()
    (tmp_path / "ghost_welcome_1_1.mp4").unlink()
    gaps = dict(clip_audit.missing_clips(tmp_path))
    assert set(gaps) == {"mate_signoff_2_1.mp4", "ghost_welcome_1_1.mp4"}
    assert "fails" in gaps["mate_signoff_2_1.mp4"]
