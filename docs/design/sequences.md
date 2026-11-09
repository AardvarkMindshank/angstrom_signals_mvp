# Sequences in Sets: "A, then B within N closed candles"

Status: **draft for review, revision 1 (9 November 2026)**. Part 1 of the strategies decision recorded in the
Strategies brief ("Decision after review (9 Nov)"). Nothing here is built yet.

Inputs: the Strategies design brief and the three reviews of 9 November (ChatGPT, Gemini, Grok);
`lattice_prism.md` §4.2 (Set decisions) and §4.4 (pinned subjects); `point_in_time.md` (as-of reconstructions).

Nothing here changes Groups, the dashboard, Trend/Stretch/Flow, existing saved Sets or their hashes, or the
protected hold-out. A Set without a sequence validates, evaluates and hashes exactly as today.

## 1. What a sequence says

> "Bitcoin's Trend turned bullish, **then** within 5 closed daily candles its volume came in strong."

Two ordinary decision rules, A (**first**) and B (**then**), and a limit N (**within**). The Set answers **Yes** at a
close when B holds at that close and A held at one of the N closes before it, with nothing since that cancels it.

Everything a sequence reads is already in the Set: its Groups, its standalone condition lines and its pinned lines
(such as "Trend on COIN"). A sequence adds order and a time limit, nothing else.

## 2. The document

A new decision node, beside `all`, `any` and `not`:

```json
"decision": {"version": 1, "rule": {"all": [
  {"group": "regime", "outcome": {"in": ["trending"]}},
  {"sequence": {
     "first":  {"group": "trend", "outcome": {"eq": "bullish"}},
     "then":   {"member": "volume", "field": "ratio", "gte": 1.5},
     "within": 5,
     "cancel": {"group": "trend", "outcome": {"eq": "bearish"}}
  }}
]}}
```

| Key | Meaning |
|---|---|
| `first` | A: any decision rule (lines, `all`, `any`, `not`), no sequence inside it |
| `then` | B: the same |
| `within` | N: whole number, 1 to 20, counted in closed **daily** candles of the scanned asset |
| `cancel` | optional C: a rule that, once true after A, cancels that A (a reset) |

A sequence can sit anywhere a line can, so "regime is trending **and** (A then B)" works. At most 2 sequences per
decision; no sequence inside `first`, `then` or `cancel`. The decision `version` stays 1: the new key is additive,
and a Set that uses it is a new Set version (new hash), as with every other edit.

## 3. The clock and the readings

- **Candles counted.** Closed daily candles of the **scanned asset**: every day for coins, trading days for shares
  (weekends and holidays are not candles, so "within 5" spans a week for a share). Only the daily clock in this
  version; a 4-hour or hourly clock waits until intraday history is stored.
- **Each close is read as it was known then.** At each of the N earlier closes the Set is evaluated with the same
  as-of reconstruction Prism scans already use (`point_in_time.md`): candles closed by then, stored observations
  first seen by then. Nothing later is seen.
- **Pinned lines across calendars.** A pinned line is read at the same cutoff as the scanned asset, giving the value
  known at that moment. A share pinned in a coin Set reads Friday's close on Saturday and Sunday; a coin pinned in a
  share Set reads the coin at the share's close time. Alignment is by **time known**, never by candle number.
- **No stored state.** The answer at a close is worked out afresh from the closes before it, every time. A restart, a
  missed scan or a late check gives the same answer as an on-time one; there is no memory to lose or corrupt, and no
  duplicate is possible from state alone. (Alert duplicates are still prevented by the existing alert keys, §6.)

## 4. The answer, including Unknown

At close c0 with earlier closes c1 … cN (c1 the most recent):

1. Read B at c0. **False → No. Unknown → Unknown.** True → go on.
2. Look for A at c1 … cN. An A at ck **counts** if no `cancel` was true at any close after ck up to c0.
3. **Yes** if some A counts.
4. Otherwise **Unknown** if some close could still have given a counting A: A unknown there, or A true there but a
   later `cancel` unknown, or the close could not be read at all (too little history, a failed reconstruction).
5. Otherwise **No**.

So Unknown is never treated as met, and never silently as not met either: a gap in the window that could have
mattered makes the answer Unknown, as everywhere else in Sets.

**A and B on the same candle** do not make a sequence ("then" means a later close). Use `all` for "both at once".

**While B stays true.** Yes holds on each close while B stays true and the A that started it is still within N closes.
After that the sequence has **expired** and answers No until a new A comes along.

## 5. Armed

Between A and B the asset is **Armed**: A counts at one of c0 … c(N−1), so B can still arrive in time, and B is not
true now. The Set answer is still **No** (Armed is not a match), but the result carries it:

```json
"sequences": [{"path": "decision.rule.all[1]", "state": "armed", "since": 2, "left": 3,
               "first_at": "2026-11-06", "text": "Trend bullish 2 closes ago; volume strong not yet (3 closes left)"}]
```

States: `met` (Yes from this sequence), `armed`, `expired` (an A was seen but N has passed with no B), `cancelled`,
`waiting` (no A in the window), `unknown`. Here A at c0 itself also arms (it was just seen; B must come later).

## 6. Where it shows

- **Set editor.** A "Then, within N days" block: pick lines for First, pick lines for Then, choose N, optional
  "Cancel if". The sentence it builds is shown under it, in plain words.
- **Run now and Prism results.** Yes rows say "A 3 closes ago, then B today". No rows that are Armed show
  **Armed · 3 left** (an icon with hover text), so a scan also shows what is close to happening.
- **Scheduled scans and alerts.** As today, an alert fires when a row turns Yes. A new optional setting per scan,
  "Also tell me when an asset becomes Armed", off by default. Both use the existing alert keys (scan, asset, cutoff),
  so a re-run of the same cutoff never sends twice.
- **History bands and What followed.** Work unchanged: the daily answers simply include the sequence. Armed days are
  not Yes days.
- **Wording.** Facts about the Set only ("Trend turned bullish 2 closes ago"); never "get ready to buy". Armed uses
  a neutral colour, not green.

## 7. Cost

A sequence reads the Set at up to N+1 closes instead of 1. To keep scans quick:

- only the Groups and lines that `first`, `then` and `cancel` name are read at the earlier closes;
- earlier closes reuse the reconstruction's frame cache (the same candles cut at a different close);
- `within` is capped at 20; Prism keeps its asset limit for Run now.

The real time per asset is measured on the 86 saved assets before release, and reported.

## 8. Tests (before release)

- **Truth table** for §4: every mix of true / false / unknown for B, A at each close, and cancel.
- **Expiry and cancel**: A at exactly N closes ago counts; at N+1 does not; a cancel between A and c0 removes it; a
  cancel before A does not.
- **Same candle**: A and B both only at c0 is No (Armed), never Yes.
- **No look-ahead**: poisoned data after c0 changes nothing (the existing future-data tests, run on a sequence Set).
- **Restart / late check**: the answer at a past close is the same whether worked out then or a week later from the
  same data.
- **Mixed calendars**: a share Set with a pinned coin line, and a coin Set with a pinned share line, across a
  weekend and a US holiday.
- **Missing data**: a window shorter than N (new listing) gives Unknown only when the missing closes could matter.
- **Many at once**: 86 assets turning Armed on one day send one alert email, as today's batched alerts do.
- **Hashes**: every existing Set keeps its hash and answers (golden tests).

## 9. What it leaves out

Chains of three steps (A, then B, then C), clocks other than daily, "A must stay true until B", counting ("A on 3
of the last 5 closes"), and anything about entering, exiting or sizing (that is part 2, tracked plans).

## 10. Questions for review

1. Is "B true now, A within the N closes before" the right reading, or should Yes fire only on the close B **first**
   turns true after A?
2. Is the Unknown rule (§4 step 4) right: a window gap gives Unknown only if it could have produced a counting A?
3. Daily clock only for now: acceptable?
4. Should Armed be off by default for alerts (proposed), or on?
5. Anything in the tests (§8) missing for a feature people may later rely on?
