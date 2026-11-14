# Strategies — design review

9 Nov 2026 · Independent review of `docs/research/strategies_brief_2026-11-09.md`

Read against: `docs/design/groups_sets.md`, `docs/design/lattice_prism.md`, `docs/research/visual_strategy_builders.md`, `docs/research/capability_review_2026-11-07.md`, `what_followed.py`.

---

## 1. Verdict

**Sound with changes.** Keep Track → Study → Act, Set-version pinning, typical-move rungs, shares-of-plan sizing, and the honest-study discipline. Ship sequences plus tracked plans first; defer full plan studies; keep ladders and exits out of Set analysis.

## 2. Answers to questions 1–11

**1. Shape.** The five stages are the right spine. Keep Watching → Armed → Building in → Managing → Done. Name two Done reasons: Abandoned (invalidation) and Expired (time limit / Armed never filled). Name now, build later: cancel unfilled adds while keeping filled size; long and short as separate strategies; one open plan per asset per strategy.

**2. Sequences first.** Yes — sequences inside Sets before Strategies, as the capability review ranked. Prefer alert-only Waiting → Armed on the Set and Prism, not free-form re-evaluation chains. Strategies consume a Set or sequence as entry; they do not reinvent sequencing. Ship **E4** (fixed-subject Set lines) with sequences, or Coinbase→Bitcoin stays a special case.

**3. Ladders.** Rungs in typical moves and sizes as plan shares are right for Angstrom. Copy 3Commas’ clarity, not its bot: draw the spine before save; show average entry after each rung; force invalidation past the last rung; refuse illegal combos in the editor. Prefer ATR over fixed percent. No money, leverage, or “safety order” jargon.

**4. Exits (first version).** Four only: invalidation (ATR from entry or last rung), time limit, entry-Set turns No (or a named exit Set turns Yes), and one take-profit (or ≤3 out-rungs). Same-candle order, printed under the chart: (1) invalidation/stop, (2) time limit at close, (3) Set exit at close, (4) take-profit. Trails and breakeven-after-partial wait.

**5. The boundary.** Level 1 stays descriptive if alerts are facts about the user’s plan, never instructions, and Angstrom never suggests sizes, stops, or ready-made trades. Level 2 stays descriptive only if it reuses What followed wording and verdicts, reports plan-share results in typical moves, never headlines equity curves / win rate / profit factor, and studies only frozen plans. Defaults: blank ladders, no provided strategy library, a permanent “describes your plan; not advice; not an order” badge, no buy/sell colouring on stage changes.

**6. Studies.** Proposed rules are a strong base. Tighten fills: signal at close → earliest fill next open (or next close — pick one and print it); same-bar stop before target; state costs (0.1% crypto / 0.05% equity a side as assumption). Add baseline: buy-and-hold from the same entry with no ladder. Report never-filled and exit-reason shares first-class. Do not claim path realism inside a daily bar.

**7. Overfitting.** Every saved strategy version is a trial (entry, N, rung, exit, costs). Show a trial counter on the card. No auto-search. Correct across the family when many versions exist. V1 needs the counter and a recorded freeze before hold-out; CPCV-style notes can wait.

**8. Coinbase and Bitcoin.** Test the incremental claim. Baselines: BTC Yes alone; COIN Yes alone; both Yes same day; random N-candle delays after COIN Yes. Condition on market factor (BTC trend or beta side). Fresh Yes with the What followed gap rule. Report how often Bitcoin moved anyway. E4 + sequence expresses it; the study must subtract common market move.

**9. Newcomers.** Guided form first (entry → optional sequence → draw ladder → exits), not a blank canvas and not the AI advisor yet. One editable worked example beats a strategy library. Templates as blank skeletons only. AI later: draft Set/sequence from a sentence; user still places the ladder.

**10. Market practice.** Copy: stage-attached rules (TrendSpider / Option Alpha); ladder before test (3Commas clarity); labeled same-bar priority (not Kryll wire order); editor refusals (Composer / NinjaTrader). Avoid: equity-curve theatre and impossible on-close fills (TradingView pitfalls); flat rule lists; stop size that ignores partial exits; execution-bot metaphor.

**11. Simplify.** Cut from first Strategies ship: multi-rung ladder out, plan studies, shorts, portfolio budget, intraday fills, brokers, provided packs, trails. Keep: sequences (+ E4), tracked plans with ladder-in, invalidation, time limit, Set exit, stage alerts, ladder drawn before save.

## 3. Risks we missed (most serious first)

1. **Advice by UI chrome** — colours, pushes and a drawn stop read as “trade now” despite careful copy.
2. **Common-factor as edge** — lead-lag and dip ladders flatter beta without market-conditioned baselines.
3. **Correlated open plans** — many assets Armed the same day are one macro event.
4. **ATR look-ahead / instability** — typical move for rungs must be fixed at the Armed close.
5. **Equity gap risk** — daily “fill at level” understates open-through-stop damage.
6. **Trial laundering** — renames and copies without a counter defeat multiple-test discipline.
7. **Hold-out gaming** — freeze must be a recorded product action, not informal chart peeks.
8. **Listing bias** — watchlists overweight survivors; failed names never stress dip ladders.
9. **Remainder bugs** — after partial exit, stop size must be the remaining plan share.
10. **Scope creep to Act** — broker connect will be asked for as soon as Track ships; keep Act a hard no.

## 4. Recommended first version

**Two slices:**

1. **Sequences in Sets (+ E4).** Waiting → Armed; A then B within N closed candles; B may pin another asset. Prism and alerts show state. Fixtures cover Unknown, gap, cross-asset cutoff, no re-run action.

2. **Tracked plans only (level 1).** Entry = Set or sequence; ≤3 ATR ladder-in rungs; exits = invalidation past last rung, time limit, Set exit, one take-profit; fixed same-candle priority; stage strip + alerts; spine before save; plan-share sizes; pinned Set versions. No money, broker, or study card.

**Leave out:** level 2 studies, ladder-out grids, shorts, portfolio rules, intraday paths, provided strategies, AI-built plans.

**How tested:** golden stage and same-candle fixtures; replay using only data known at each close; alert copy without order verbs; editor refuses stop inside the ladder; walkthrough of Drew’s four examples on one coin and one share. Add plan studies only after Track is solid, reusing `what_followed.py` hold-out, block resampling, Holm and four verdicts.

## 5. Sources

- TradingView strategies / emulator / Bar Magnifier: https://www.tradingview.com/pine-script-docs/concepts/strategies/ · https://www.tradingview.com/support/solutions/43000786181-broker-emulator/ · https://www.tradingview.com/blog/en/accurate-backtesting-with-bar-magnifier-31746/
- TrendSpider Strategy Tester: https://help.trendspider.com/kb/strategy-tester/understanding-strategy-tester-from-trendspider
- Composer: https://help.composer.trade/article/54-create-tutorial · https://help.composer.trade/article/67-backtest-basics
- 3Commas DCA / stop beyond grid: https://help.3commas.io/en/articles/16307077-3commas-dca-bot-for-tradingview-setup-parameter-guide · https://help.3commas.io/en/articles/9464682-dca-bot-stop-loss-breakeven
- Kryll priority: https://blog.kryll.io/priority-of-blocks-in-the-kryll-strategy-editor/
- NinjaTrader Builder: https://ninjatrader.com/support/helpGuides/nt8/builder_screens.htm
- Option Alpha Exit Options: https://docs.optionalpha.com/tools/managing-positions/exit-options
- `what_followed.py`; López de Prado multiple testing https://doi.org/10.3905/jfds.2019.1.099 · https://doi.org/10.1080/14697688.2019.1622311; CPCV overview https://thequanthackers.com/methodology/cpcv
- Repo: `groups_sets.md`, `lattice_prism.md` §4.4 / §5.5, `visual_strategy_builders.md`, `capability_review_2026-11-07.md`
