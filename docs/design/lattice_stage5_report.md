# Lattice stage 5 report: confirmations and vetoes, fixed assets (E4), open to every account

Branch `lattice-stage5`, 5 November 2026. The three "smaller additions" agreed with the owner after stage 4. Design:
`docs/design/lattice_prism.md` §3.4 (conditions), §4.4 (E4) and §8. Needs one SQL file to open scan saving to
every account.

## 1. Confirmations and vetoes in the Group editor

- The editor model gains **conditions**: each a confirmation or a veto, with a name and conditions joined by AND or
  OR, stored exactly as the accepted design's `conditions` (`groups_sets.md` §3.4).
- A **"Confirmations and vetoes"** panel under the rules: ✅ Confirmation / ⛔ Veto buttons, name, conditions,
  "+ Confirmation", "+ Veto".
- Members keep their **saved settings** (signal parameters) and saved transforms, shown as "custom settings", so
  Groups built elsewhere open without being changed. New members use the defaults. Direction readings inside a
  field (market structure up / down / mixed) can now score directly.
- **Trend Confirmation now opens and saves back exactly** (members, transforms, both confirmations and the veto).
  Reversal Evidence (counting rules and events) is still refused with the reason.
- Checks: a check with no condition, duplicate names, a reading no longer in the Group, non-numbers; a warning
  that a firing veto turns every label into Vetoed and an unknown veto marks labels qualified. A Condition member
  used only by a veto is not "unused". The description lists each confirmation and veto.
- **Sets can test them**: "Trend Confirmation · veto: Daily regime is ranging is not active", "… confirmation …
  is met".

## 2. Fixed assets in a Set (E4)

- A Group or a single signal in a Set may be read on **one fixed asset** (crypto id or share ticker), for example
  "Trend on COIN is Bullish", while the rest of the Set runs on the asset being scanned.
- **Engine** (`signal_groups/sets.py`, `validate.py`): optional `subject: {kind, id}` on Group entries and
  standalone items, validated. `evaluate_set(..., subject_context=)` reads the fixed asset with its own data
  context and its own shared results (never mixed with the scanned asset's), **at the same moment**: live for Run
  now, the same cutoff T for past moments and scheduled scans (the replay record includes both). Without a source
  the item is unavailable and its lines Unknown, never guessed. Sets without the key are unchanged (compatibility
  snapshot).
- **Prism**: Run now, past moments and scheduled scans pass the fixed asset's context automatically.
- **Set editor**: each Group or signal card has "📌 the scanned asset / fixed crypto / fixed share" and an id
  field; names show "on COIN" in lines and the description; a reminder that "A, then B within N days" needs a
  strategy, which comes later.

## 3. Open to every signed-in account

- A new **🧩 Lattice · 🔎 Prism (preview)** panel on the dashboard for every signed-in account, with a switch:
  nothing is read or drawn until it is switched on, so the dashboard costs the same for everyone else.
- Lattice and Prism moved there from the admin-only Signal Library panel (which keeps its development tabs).
- One **Run now** per account every 20 seconds (each run can read up to 40 assets).
- **SQL** `sql/2026-11-07_prism_open_to_all.sql`: replaces `prism_save_scan` without the admin-only check; every
  other rule stays (owner-only, writes through functions, one run per cutoff, at most 5 active scans per account).
  Until it is run, non-admin accounts see "Saving scans is not switched on for every account yet".

## Tests and checks

- `tests/test_lattice_stage5.py`, 13 tests: Trend Confirmation round trip, Reversal Evidence refused, condition
  checks and cleaning, Sets testing confirmation and veto states, fixed subjects validated, read on their own data
  at the same moment (one context shared by a Group and a signal on the same asset), Unknown without a source,
  Prism live and replay, Set editor round trip and wording, the panel outside the admin block and lazy, the SQL
  drops only the admin check.
- Browser checks: 20 (a veto added and turned into a confirmation; a Group read on a fixed share), with the harness
  now redrawing after every edit as Streamlit does.
- Full local suite: **781 passed, 15 skipped, 0 failed**.

## CI

To be reported before merge approval.
