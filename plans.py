"""Membership plans: what each plan includes, and how a Set or signal is graded (18 Nov 2026).

Decided with Angus (17 Nov 2026, the "Lattice simplified" mockup):
- The plan is the only level. Free, Plus, Pro, Elite. There is no separate "experience" setting.
- Anything your plan includes carries no mark. Only items above your plan get a small colour-coded PLUS or PRO
  label, with a hover note saying why.
- "Features not in my plan" (Settings > Account): Hide (the default) or Grey out.
- A Set's plan is worked out from how it is built, never chosen by hand, so provided and user-made Sets follow one
  rule (see set_level). Elite adds bigger limits, not extra features: no Set is Elite-only.
- During the free beta every account is on Pro unless the database says otherwise (BETA_PLAN).

The plan itself lives in the user_plans table (sql/2026-12-04_user_plans.sql): the owner can read it, only the
server can write it (later, from Paddle).
"""

from __future__ import annotations

PLANS = ("free", "plus", "pro", "elite")
RANK = {p: i + 1 for i, p in enumerate(PLANS)}
LABEL = {"free": "Free", "plus": "Plus", "pro": "Pro", "elite": "Elite"}
COLOUR = {"plus": "#2563eb", "pro": "#7c3aed", "elite": "#0f766e"}
BETA_PLAN = "pro"
DISPLAY_MODES = ("hide", "grey")
DEFAULT_DISPLAY = "hide"

# What each plan includes (the pricing page, website/pricing.html). Limits are starting points.
LIMITS = {
    "free": {"watchlist": 10, "groups": 0, "sets": 0, "scans": 1, "scan_schedule": False, "funnels": 0,
             "studies": 0, "navigator_per_day": 5},
    "plus": {"watchlist": 30, "groups": 5, "sets": 5, "scans": 3, "scan_schedule": True, "funnels": 1,
             "studies": 2, "navigator_per_day": 25},
    "pro": {"watchlist": 100, "groups": 25, "sets": 25, "scans": 15, "scan_schedule": True, "funnels": 6,
            "studies": 10, "navigator_per_day": 60},
    "elite": {"watchlist": 250, "groups": None, "sets": None, "scans": 50, "scan_schedule": True, "funnels": 12,
              "studies": 30, "navigator_per_day": 150},
}

# Why something sits at a plan: the hover note on a PLUS or PRO label.
WHY = {
    "plus": "Plus: two or more conditions, two timeframes, or a fixed asset such as Bitcoin",
    "pro": "Pro: a sequence (THEN box), three or more timeframes, or a Pro signal such as divergence or Sonar",
}

# The lowest plan that includes each signal (a "variant" in the signal families). Anything not listed is Plus.
SIGNAL_PLAN = {
    # Free: the plain readings a newcomer meets first
    "trend.direction": "free", "ma.line": "free", "ma.pair": "free", "ma.position": "free", "rsi.level": "free",
    "volume.relative": "free", "sentiment.asset": "free", "sentiment.market": "free", "levels.zones": "free",
    # Plus
    "mtf.alignment": "plus", "ichimoku.position": "plus", "stochastic.level": "plus", "bollinger.position": "plus",
    "volume.heavy_candle": "plus", "macd.level": "plus", "macd.acceleration": "plus", "obv.balance": "plus",
    "volume.cmf": "plus", "structure.swings": "plus", "shape.classic": "plus", "regime.state": "plus",
    "volatility.atr_trend": "plus", "regime.observation": "plus", "candle.shape": "plus", "move.seven_day": "plus", "momentum.direction": "plus",
    # Pro
    "osc.stoch_rsi": "pro", "osc.stoch_ohlc4": "pro", "structure.breaks": "pro",
    "divergence.mtf": "pro", "ta.divergence.rsi": "pro", "ta.divergence.macd": "pro", "osc.wavetrend": "pro",
    "flow.money": "pro", "sonar.markers": "pro", "options.max_pain": "pro", "positioning.funding": "pro",
    "positioning.liquidation_levels": "pro", "positioning.liquidations": "pro", "positioning.long_short": "pro",
    "positioning.oi_price": "pro", "flows.btc_etf": "pro", "flows.stablecoin_supply": "pro",
}


def normalise(plan) -> str:
    plan = str(plan or "").strip().lower()
    return plan if plan in RANK else BETA_PLAN


def includes(user_plan, needed) -> bool:
    """Does user_plan include something that needs `needed`?"""
    return RANK[normalise(user_plan)] >= RANK.get(str(needed or "free").lower(), 1)


def higher(a: str, b: str) -> str:
    return a if RANK.get(a, 1) >= RANK.get(b, 1) else b


def display_mode(settings: dict | None) -> str:
    mode = str((settings or {}).get("plan_display") or DEFAULT_DISPLAY)
    return mode if mode in DISPLAY_MODES else DEFAULT_DISPLAY


def signal_plan(signal_id: str) -> str:
    return SIGNAL_PLAN.get(str(signal_id or ""), "plus")


def _walk(obj, found: dict) -> None:
    """Collect what decides a Set's level from anywhere in its document."""
    if isinstance(obj, dict):
        ref = obj.get("ref")
        if isinstance(ref, dict) and ref.get("id"):
            found["refs"].append(ref)
        if obj.get("subject"):
            found["fixed_asset"] = True
        if "sequence" in obj or "then" in obj:
            found["sequence"] = True
        for value in obj.values():
            _walk(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _walk(value, found)


def set_level(doc: dict | None) -> str:
    """The lowest plan that includes a Set, from how it is built (Angus's rule, 17 Nov 2026):
    Free  - one line on one timeframe;
    Plus  - two or more lines, two timeframes, or a fixed asset (a line that reads e.g. Bitcoin);
    Pro   - a THEN box (a sequence), three or more timeframes;
    and never below the plan of the signals it uses directly. A Group counts as one line, and the signals inside
    a Group don't raise the level: building Groups is already a Plus feature."""
    doc = doc or {}
    groups = list(doc.get("groups") or [])
    standalone = list(doc.get("standalone") or [])
    context = list(doc.get("market_context") or [])
    lines = len(groups) + len(standalone) + len(context)

    everything = {"refs": [], "fixed_asset": False, "sequence": False}
    _walk({"groups": groups, "standalone": standalone, "market_context": context, "decision": doc.get("decision")},
          everything)
    timeframes = {str(r.get("timeframe") or "1D") for r in everything["refs"]}

    direct = {"refs": [], "fixed_asset": False, "sequence": False}
    _walk({"standalone": standalone, "market_context": context}, direct)
    level = "free"
    for ref in direct["refs"]:
        level = higher(level, signal_plan(ref.get("id")))

    if everything["sequence"] or len(timeframes) >= 3:
        level = higher(level, "pro")
    elif lines >= 2 or len(timeframes) == 2 or everything["fixed_asset"]:
        level = higher(level, "plus")
    return level


def label_html(needed: str) -> str:
    """The small colour-coded label shown only on items above the user's plan."""
    needed = str(needed or "").lower()
    if needed not in COLOUR:
        return ""
    return (f'<span class="ang-plan-tag" title="{WHY.get(needed, "")}" style="font-size:10px;font-weight:800;'
            f'letter-spacing:.06em;text-transform:uppercase;border-radius:999px;padding:2px 7px;color:#fff;'
            f'background:{COLOUR[needed]}">{LABEL[needed]}</span>')
