# Lattice stage 4 report, part 1: the Group editor (admin preview)

Branch `lattice-stage4`, 5 November 2026. Design: `docs/design/lattice_prism.md` §7 and §8 stage 4. Part 1 is the
Group editor; part 2 (the Set editor) follows after feedback on this draft. Admin only: a new 🧩 Lattice tab in the
🧪 Signal Library panel. Nothing changes for other accounts. No SQL.

## What was built

| Part | File | What it does |
|---|---|---|
| Logic | `lattice_editor.py` | The editor model ↔ `angstrom.group/1`: members with roles and their own timeframes, Score members through their standard score (or the up/down map for direction signals), ordered label rules (first match wins, Unknown stops, `otherwise`). Blocks and warnings in plain words, using the engine's own validator plus the mockup's checks (overlapping measures, price-only scores, mixed timeframes, unused Condition, reused evidence, OR overlap, sentiment history, Context in a rule, non-numbers, out-of-scale thresholds shown on the −100..+100 screen scale). Auto-written description. Everything the browser sends back is cleaned against the signal list before use. |
| Screen component | `lattice_component.py` | Signal panel (search, categories, hover explanations, "condition only" for signals without a standard score), drag and drop **and** tap +, role buttons, timeframe picker and source tag per member, rule rows with typed readings (#, Y/N, Aa), comparisons by type, scale next to every value, ↑↓ order, AND/OR, fixed Unknown and otherwise rows. Draws only; text is inserted as text, never HTML. |
| Page | `lattice_view.py`, `signal_inspector.py` | Start from a new Group, a copy of a starter, or one of your saved Groups (Groups with confirmations or vetoes are refused with the reason). Checks, "what this Group returns" and the description under the editor. **Save as a new Group** or **Save as the next version**, through the existing storage functions. **Try it** on one Watchlist asset. If the component cannot load, the page shows a short notice instead of failing. |

## Tests and checks

- `tests/test_lattice_editor.py`, 12 tests: catalogue, starter round trips (with and without labels), refused
  documents, cleaning of whatever the browser sends, 9 blocks and 7 warnings, a saved Group evaluates and can be
  scanned in a Set, description and source tags, harness built from the real component, the tab inside Streamlit.
- **In a real browser** (`lattice_component_check.js`, new required CI step): tap +, role buttons, rule reordering,
  drag and drop, search, no HTML injection, no browser errors, iPad width without sideways scrolling; desktop and
  iPad screenshots.
- **Inside a real Streamlit server** (`lattice_streamlit_app.py`, `lattice_streamlit_check.js`, new required CI
  step): an edit goes to Python and comes back checked: the empty Group is blocked, tap + adds RSI and rewrites the
  description, a rule can be added, an out-of-scale threshold blocks saving.
- Full local suite: **766 passed, 15 skipped, 0 failed**.

## Not in part 1

The Set editor (part 2), confirmations and vetoes in the editor, weights other than equal, opening Lattice to all
accounts.

## CI

To be reported before merge approval.
