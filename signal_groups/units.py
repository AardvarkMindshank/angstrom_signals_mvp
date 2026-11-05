"""Display units for Group scores (docs/design/lattice_prism.md §4.3).

A Group score is stored on −1..+1 and shown on −100..+100, as the dashboard shows Trend, Stretch and Flow. The editor
takes thresholds in display units and stores them exactly: "+30" -> 0.3.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction


def score_from_display(text) -> float:
    """"+30", "−30", "30", 30 -> 0.3, -0.3. Refuses anything outside −100..+100 or not a number."""
    raw = str(text).strip().replace("−", "-").replace("+", "")
    try:
        shown = Fraction(Decimal(raw))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{text!r} is not a number") from None
    if not -100 <= shown <= 100:
        raise ValueError(f"{text!r} is outside the Group score scale −100 to +100")
    return float(shown / 100)


def score_to_display(value: float) -> str:
    shown = round(float(value) * 100, 2)
    text = f"{shown:+g}"
    return text.replace("-", "−")
