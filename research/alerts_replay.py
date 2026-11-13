"""Replay of the proposed border-crossing alerts on saved daily prices, 30 Oct 2023 to 29 Oct 2024 (before the
protected hold-out). Prints how often each kind of crossing happens per asset."""
import glob, json, os, sys
from collections import Counter, defaultdict
import pandas as pd

sys.path.insert(0, "/root/angstrom_signals_mvp")
import scoring, signals_v2 as sv

PRICES = sys.argv[1]
START, END = pd.Timestamp("2023-10-30"), pd.Timestamp("2024-10-29")
STRONG, BAND = sv.DEFINITIONS["label_band_strong"], sv.DEFINITIONS["label_band"]

def zone(v):
    if v is None: return None
    return 2 if v >= STRONG else 1 if v >= BAND else 0 if v > -BAND else -1 if v > -STRONG else -2

def events(prev, cur):
    out = []
    if prev is None or cur is None or prev == cur: return out
    if (prev >= 1 and cur <= -1) or (prev <= -1 and cur >= 1):
        out.append("flip")
        if abs(cur) == 2: out.append("strong_up" if cur > 0 else "strong_down")
        return out
    if prev == 0: out.append("leaves_neutral")
    if cur == 2 and prev < 2: out.append("strong_up")
    if cur == -2 and prev > -2: out.append("strong_down")
    if abs(prev) == 2 and abs(cur) < 2: out.append("fades_from_extreme")
    if cur == 0 and prev != 0: out.append("back_to_neutral")
    return out

def old_rule(series, line, rearm=20):
    """Today's alert: crossing +line (or -line) after re-arming 20 points back."""
    n, armed_up, armed_dn = 0, True, True
    for v in series:
        p = v * 100
        if armed_up and p >= line: n += 1; armed_up = False
        elif not armed_up and p <= line - rearm: armed_up = True
        if armed_dn and p <= -line: n += 1; armed_dn = False
        elif not armed_dn and p >= -line + rearm: armed_dn = True
    return n

counts = {m: defaultdict(Counter) for m in ("crypto", "equity")}
confirmed = {m: defaultdict(Counter) for m in ("crypto", "equity")}
old = {m: defaultdict(Counter) for m in ("crypto", "equity")}
assets = Counter()
for path in sorted(glob.glob(os.path.join(PRICES, "*.csv.gz"))):
    sym = os.path.basename(path)[:-7]
    market = "crypto" if sym.endswith("-USD") else "equity"
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    df = df.loc[:END]
    if len(df.loc[START:]) < 200: continue
    frame = scoring.calculate_indicators(df)
    vals = defaultdict(list)
    for pos in range(len(frame)):
        if frame.index[pos] < START: continue
        comps, _ = sv._components(frame.iloc[pos], frame.iloc[: pos + 1])
        for key, spec in sv.CLUSTERS.items():
            present = [comps[m] for m in spec["components"] if comps.get(m) is not None]
            vals[key].append(sum(present) / len(present) if present else None)
    assets[market] += 1
    for key, series in vals.items():
        zs = [zone(v) for v in series]
        for a, b in zip(zs, zs[1:]):
            for e in events(a, b): counts[market][key][e] += 1
        # confirmed: a new zone counts only once it holds at the next close
        held = [zs[0]]
        for i in range(1, len(zs)):
            nxt = zs[i + 1] if i + 1 < len(zs) else zs[i]
            held.append(zs[i] if zs[i] == nxt else held[-1])
        for a, b in zip(held, held[1:]):
            for e in events(a, b): confirmed[market][key][e] += 1
        clean = [v for v in series if v is not None]
        for line in (30, 50): old[market][key][f"line_{line}"] += old_rule(clean, line)

print(json.dumps({"assets": assets, "raw": counts, "confirmed": confirmed, "today": old}, default=dict))
