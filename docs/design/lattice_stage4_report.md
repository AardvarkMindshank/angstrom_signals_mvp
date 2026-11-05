# Lattice stage 4 report: the Group and Set editors (admin preview)

Branch `lattice-stage4`, 5 November 2026. Design: `docs/design/lattice_prism.md` §4.2, §7 and §8 stage 4. Part 1 is
the Group editor, part 2 the Set editor. Admin only: a new 🧩 Lattice tab in the 🧪 Signal Library panel with
📁 Group editor and 🗂️ Set editor views. Nothing changes for other accounts. No SQL.

## What was built

| Part | File | What it does |
|---|---|---|
| Logic | `lattice_editor.py` | The editor model ↔ `angstrom.group/1`: members with roles and their own timeframes, Score members through their standard score (or the up/down map for direction signals), ordered label rules (first match wins, Unknown stops, `otherwise`). Blocks and warnings in plain words, using the engine's own validator plus the mockup's checks (overlapping measures, price-only scores, mixed timeframes, unused Condition, reused evidence, OR overlap, sentiment history, Context in a rule, non-numbers, out-of-scale thresholds shown on the −100..+100 screen scale). Auto-written description. Everything the browser sends back is cleaned against the signal list before use. |
| Screen component | `lattice_component.py` | Signal panel (search, categories, hover explanations, "condition only" for signals without a standard score), drag and drop **and** tap +, role buttons, timeframe picker and source tag per member, rule rows with typed readings (#, Y/N, Aa), comparisons by type, scale next to every value, ↑↓ order, AND/OR, fixed Unknown and otherwise rows. Draws only; text is inserted as text, never HTML. |
| Page | `lattice_view.py`, `signal_inspector.py` | Start from a new Group, a copy of a starter, or one of your saved Groups (Groups with confirmations or vetoes are refused with the reason). Checks, "what this Group returns" and the description under the editor. **Save as a new Group** or **Save as the next version**, through the existing storage functions. **Try it** on one Watchlist asset. If the component cannot load, the page shows a short notice instead of failing. |

### Part 2: the Set editor

| Part | File | What it does |
|---|---|---|
| Logic | `lattice_sets.py` | Set model ↔ `angstrom.set/1`. Saved Group versions (yours, shared and the database starters) embedded exactly with their provenance, as the storage re-checks; single signals as Condition or Context items. The decision is an ALL box of lines with optional ANY boxes; a line tests a Group's label (is / is not), score (shown −100..+100) or status, or a Condition signal's field. Blocks (nothing added, unreadable Group, line testing something removed or a Context item, non-numbers, out-of-scale scores, everything the engine's validator refuses) and warnings (no decision yet, so not scannable; Groups and signals reading the same signal; unused Condition; sentiment history). Auto-written description. Saved Sets reload into the editor when it can show them. |
| Screen component | `lattice_component.py` (`SET_JS`) | Groups and signals panel (labels or "score only" shown for each Group), drag and drop and tap +, Group and signal cards, timeframe and role for signals, decision lines with typed readings and comparisons, ANY (OR) boxes, the fixed explanation of Yes / No / Unknown. Removing a Group or signal also removes the lines that tested it. |
| Page | `lattice_set_view.py` | Start from a new Set or one of yours; checks, what a Set returns, description; Save as a new Set or the next version. A saved Set with a decision appears in 🔎 Prism straight away. |

## Tests and checks

- `tests/test_lattice_editor.py`, 16 tests (4 for the Set editor: exact embedding and provenance, ANY boxes,
  `not` and scores round trip, blocks and warnings including an unreadable Group, cleaning of browser input). Group
  editor: catalogue, starter round trips (with and without labels), refused
  documents, cleaning of whatever the browser sends, 9 blocks and 7 warnings, a saved Group evaluates and can be
  scanned in a Set, description and source tags, harness built from the real component, the tab inside Streamlit.
- **In a real browser** (`lattice_component_check.js`, new required CI step): tap +, role buttons, rule reordering,
  drag and drop, search, no HTML injection, no browser errors, iPad width without sideways scrolling; and for the Set
  editor: the saved line shown, tap + for Groups and signals, ANY boxes, lines, removing a Group removes its lines,
  iPad width. 17 checks, desktop and iPad screenshots.
- **Inside a real Streamlit server** (`lattice_streamlit_app.py`, `lattice_streamlit_check.js`, new required CI
  step): an edit goes to Python and comes back checked: the empty Group is blocked, tap + adds RSI and rewrites the
  description, a rule can be added, an out-of-scale threshold blocks saving; the Set editor takes a signal and a
  line and returns the written decision. (Part 1 passed this inside Streamlit in CI run on commit 88bf5f6.)
- Full local suite: **770 passed, 15 skipped, 0 failed**.

## Not in this stage

Confirmations and vetoes in the Group editor, weights other than equal, market context and fixed-subject lines (E4)
in the Set editor, counting operators in decisions, opening Lattice to all accounts.

## CI

Run 42048487889 on commit 3bc6d1d: **tests, chart (with the browser and Streamlit editor checks), overlap and replay all
passed**. Results on the reports branch under `ci/v2/`.
