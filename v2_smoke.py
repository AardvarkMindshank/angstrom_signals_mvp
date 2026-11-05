"""End-to-end smoke check for signals v2 on real indicator output (run in GitHub Actions).

Takes a few real assets from the frozen price files (development rows only: every file is cut at the
hold-out start as it is read, exactly as v2_overlap.py does), and runs them through every place the
product uses v2: the watchlist row, the table cells, the asset card and breakdown, the signal matrix,
the per-asset evidence record, the alert planner and the email digest. It checks the invariants (no
0-100 "score" anywhere, values bounded, missing data shown as missing, only Trend alert types) and
writes preview.html (what the pieces look like) and smoke.md (pass/fail, timings, peak memory).

This is a software check, not research: it computes no returns-based statistics beyond what the
evidence record does for one asset, and it never reads hold-out rows.

    python v2_smoke.py --prices prices --out out
"""

from __future__ import annotations

import argparse
import json
import resource
import time
from datetime import datetime, timezone
from pathlib import Path

import alerts
import digest
import evidence
import research as rs
import signal_matrix
import group_readings as gr
import signals_v2 as v2
import signals_view as view
from scoring import calculate_indicators

PICKS = {"stock": 3, "crypto": 3}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    start = rs.checked_start_from_manifest(args.prices)
    frames = rs.load_cache(args.prices, before=start)
    assert all(f.index.max() < start for f in frames.values()), "hold-out rows were read"

    checks, timings, previews = [], {}, []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), str(detail)))

    chosen = []
    for klass, count in PICKS.items():
        names = [t for t in sorted(frames) if rs.asset_class(t) == klass and t != rs.BENCHMARKS["stock"]]
        chosen += [(klass, t) for t in names[:count]]

    rows = []
    started = time.perf_counter()
    for klass, ticker in chosen:
        kind = "Crypto" if klass == "crypto" else "Stock"
        frame = frames[ticker].tail(v2.SCORING_BARS)
        row = view.row_fields(calculate_indicators(frame), kind)
        row.update({"symbol": ticker, "key": ticker, "type": kind})
        rows.append(row)
        sig = row["signals"]
        check(f"{ticker}: status ok", sig["status"] == "ok", sig.get("message", ""))
        check(f"{ticker}: no 0-100 score key", "score" not in row and "score" not in sig)
        check(f"{ticker}: readings from the starter Groups", sig["version"] == gr.VERSION and sig["fingerprint"] == gr.FINGERPRINT)
        for key in v2.CLUSTERS:
            value = row[key]
            check(f"{ticker}: {key} bounded or missing", value is None or -100 <= value <= 100, value)
        check(f"{ticker}: trend coverage full", sig["clusters"]["trend"]["coverage"][0] == 3, sig["clusters"]["trend"]["coverage"])
        if kind == "Crypto" and float(frame["volume"].fillna(0).sum()) == 0:
            check(f"{ticker}: no volume gives missing Flow", row["flow"] is None)
        cells = "".join(view.table_cell(k, row, f"{kind}|{ticker}") for k in v2.CLUSTERS)
        previews.append(f"<h3>{ticker}</h3><table><tr>{cells}</tr></table>{view.asset_card(sig)}"
                        f"<div class='ang-card'>{view.breakdown(sig)}</div>")
    timings["watchlist rows (each)"] = (time.perf_counter() - started) / max(1, len(chosen))

    # Signal matrix: replayed readings, no look-ahead (later bars changed, earlier values identical).
    klass, ticker = chosen[0]
    kind = "Crypto" if klass == "crypto" else "Stock"
    frame = frames[ticker].tail(v2.SCORING_BARS)
    started = time.perf_counter()
    full = signal_matrix.build_matrix(calculate_indicators(frame), kind, {}, 3)
    timings["signal matrix"] = time.perf_counter() - started
    shocked = frame.copy()
    shocked.iloc[-3:, shocked.columns.get_loc("close")] *= 1.5
    cut = signal_matrix.build_matrix(calculate_indicators(shocked), kind, {}, 3)
    check("matrix: five v2 rows", [r["name"] for r in full["rows"]][:5] == [n for n, _p in signal_matrix.TECHNICAL_ROWS])
    check("matrix: earlier days unchanged by later bars",
          all(a["values"][:-4] == b["values"][:-4] for a, b in zip(full["rows"], cut["rows"])))

    # Evidence record on the longest development history of one stock.
    stock = max((t for k, t in chosen if k == "stock"), key=lambda t: len(frames[t]))
    started = time.perf_counter()
    record = evidence.build_evidence(frames[stock].tail(evidence.FETCH_DAYS), kind="Stock")
    timings["evidence record (one stock)"] = time.perf_counter() - started
    check("evidence: built", record is not None)
    if record:
        check("evidence: version 2, Trend reading", record["version"] == evidence.VERSION and record["subject"] == "Trend reading")
        check("evidence: fingerprint", record["signals_fingerprint"] == v2.FINGERPRINT)
        check("evidence: text names the Trend reading", "Trend reading" in record["text"])

    # Alerts: only Trend types, judged on "trend", never on a score.
    fake = [dict(r, trend=80.0) for r in rows[:1]] + [dict(r, trend=-80.0) for r in rows[1:2]]
    actions = alerts.plan_alert_actions(fake, set(), 50.0, -50.0, describe=alerts.trend_message, field="trend",
                                        types=(alerts.TREND_UP, alerts.TREND_DOWN), rearm=alerts.TREND_REARM)
    kinds = {a[3] for a in actions if a[0] == "open"}
    check("alerts: Trend up and down opened", kinds == {alerts.TREND_UP, alerts.TREND_DOWN}, kinds)
    check("alerts: messages say not a forecast", all("not a forecast" in a[4] for a in actions if a[0] == "open"))

    # Digest: renders with the Trend readings.
    results = [dict(r, price=100.0, change=0.01, market="crypto" if r["type"] == "Crypto" else "stock") for r in rows]
    subject, html_body, text_body = digest.render_digest([], results, {"digest_watchlist": True}, "https://example.invalid")
    check("digest: shows Trend", "Trend" in html_body and "/100" not in text_body)
    (out / "digest_preview.html").write_text(html_body)

    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    style = (".ang-card{border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;margin:8px 0}"
             ".ang-kicker{color:#6b7280;font-size:.85rem} body{font-family:sans-serif;max-width:960px;margin:20px}")
    (out / "preview.html").write_text(f"<html><head><style>{style}</style></head><body>{''.join(previews)}</body></html>")

    failed = [c for c in checks if not c[1]]
    lines = [f"# Signals v2 smoke check ({'PASS' if not failed else 'FAIL'})", "",
             f"Signals {v2.VERSION}, fingerprint {v2.FINGERPRINT}, run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
             f"Development rows only (before {start.date()}). Assets: {', '.join(t for _k, t in chosen)}.", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {n} | {'pass' if ok else '**FAIL**'} | {d[:80]} |" for n, ok, d in checks]
    lines += ["", "| Timing | Seconds |", "|---|---|"]
    lines += [f"| {k} | {v:.2f} |" for k, v in timings.items()]
    lines += ["", f"Peak memory of the whole run: {peak_mb:.0f} MB."]
    (out / "smoke.md").write_text("\n".join(lines) + "\n")
    (out / "smoke.json").write_text(json.dumps({"checks": checks, "timings": timings, "peak_mb": peak_mb}, indent=1))
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
