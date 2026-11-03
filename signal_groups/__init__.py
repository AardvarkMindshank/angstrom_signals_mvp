"""Signal Groups and Signal Sets (design: docs/design/groups_sets.md).

Validator, evaluator and starter templates. Evaluation is on demand (live mode only) through the Signal Library
engine; nothing runs in the background. Storage and sharing live in sql/2026-11-04_signal_groups.sql.
"""

import json
from pathlib import Path

from .evaluate import evaluate_group  # noqa: F401
from .validate import validate_group, validate_set  # noqa: F401

STARTERS_DIR = Path(__file__).resolve().parent / "starters"
STARTERS = {
    "starter:trend-confirmation": "trend_confirmation.json",
    "starter:reversal-evidence": "reversal_evidence.json",
}


def starter(alias: str) -> dict:
    return json.loads((STARTERS_DIR / STARTERS[alias]).read_text(encoding="utf-8"))
