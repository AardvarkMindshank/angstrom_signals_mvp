# AI Advisor — design brief for review

9 Nov 2026 · Angstrom Signals

## Purpose

We want an AI advisor inside Angstrom Signals that helps a newcomer do two things. First, turn an idea in plain words into a working setup. Second, understand what the results say, and what they do not. It must never become a tipster: it explains readings and evidence, it never tells anyone to buy or sell.

It is designed in phases: first for what exists today (Groups, Sets, Prism scans and studies), then extended to Strategies once that layer is built. Strategies have their own brief, reviewed before this one is built: [strategies_brief_2026-11-09.md](strategies_brief_2026-11-09.md).

We ask you, as a reviewer, to:

1. Critique the design below: what to keep, change or drop.
2. Name the risks we have missed, especially ways it could mislead a newcomer.
3. Propose simpler or better designs, including how comparable products do this.
4. Recommend one small first version that is worth building and easy to check.

## Context

Angstrom Signals is a dashboard for crypto and US shares (Streamlit on Render, Supabase). Repo: [github.com/AardvarkMindshank/angstrom_signals_mvp](https://github.com/AardvarkMindshank/angstrom_signals_mvp). Its design runs Signals → Groups → Sets → Prism.

- **Signals:** 31 in a library. Each has a plain description, its fields with types, units and ranges, and certification records saying whether it can be replayed without look-ahead.
- **Groups:** several signals combined into a score from −100 to +100 with a label.
- **Sets:** a Yes / No / Unknown answer built from Groups and signals.
- **Prism:** scans Sets across assets on a schedule and can send alerts. Visualize History shows a Set's daily answers as bands under the price.
- **Why panel:** for one asset, each table column part by part, with a 30-day line and a plain sentence.
- **What followed:** a study of what happened after a Set turned Yes, against comparable days, before a protected hold-out (30 Oct 2024). It ends in one of four verdicts: Too few to judge, No clear difference, Some difference not established, Consistent difference.

The building blocks are strict documents with validators: a Group or Set either validates or is refused with a reason. The app already pays for one AI model (xAI Grok, for headline sentiment).

The user is a newcomer to trading, reads mostly on an iPhone, and is learning as they go. The owner's own words: the advisor should "interpret the requirement into a setup in our system and then explain the results".

## What the advisor does

Two halves, one conversation.

**1. From an idea to a setup.** The user describes what they want in their own words, for example: "warn me when a coin's futures traders are unusually crowded on the long side while its trend is turning down". The advisor:

1. Restates the idea in plain words and asks one question where the idea is ambiguous (which coins? daily or weekly?).
2. Looks for something that already does the job (next section) and offers that first.
3. Otherwise proposes the Groups and Set that capture it, line by line in plain words, with the thresholds it chose and why.
4. Shows what the proposal would have said on recent days (Visualize History bands), so the user sees it in action before saving.
5. Saves, scans or alerts only after the user approves each step.

**2. From results to understanding.** On any asset, column, Set or study, the user can ask "what does this mean?". The advisor reads the same numbers the screen shows (the Why panel parts, the history bands, the What followed card) and explains them, including what they do not show. Example: "This Set has turned Yes 40 times since 2020; afterwards prices did about the same as on ordinary days, so it describes a situation, it does not predict one."

## Reuse first

The owner's rule: if a setup that does the job already exists, the advisor uses it. It does not build a duplicate Group or Set, and it updates an existing scan rather than starting a new one.

| What exists | How the advisor finds it | What it does |
| --- | --- | --- |
| A Set with the same logic | Fingerprint of what the Set checks, ignoring its name (already used to share studies and history) | Offers that Set, with its study if it has one |
| A close Set (same parts, different thresholds) | Same signals and Groups, compared line by line | Offers it and names the difference; a change becomes a new version of it, not a copy |
| A Group that fits a part of the idea | Same members and weights (fingerprint of its logic) | Reuses it inside the new Set |
| A provided Group or Set | The library list, with plain explanations | Offers it first, as the tested starting point |
| A scan already running that Set | Scans store the Set they run | Adds the new assets or alert to that scan instead of a second scan |

Only when nothing fits does it propose something new, and it says so: "Nothing you have does this yet; here is a new Set."

## How it works

The AI model never writes to the database or code directly. It can only call a fixed set of tools that the app provides, and every tool goes through the same validators the screens use. Anything that changes the user's setup waits for a tap on "Approve".

| Tool | What it does | Changes anything? |
| --- | --- | --- |
| Search the signal library | Signals with their plain descriptions, fields, units and ranges | No |
| Find existing setups | The user's and the provided Groups, Sets and scans, matched by logic | No |
| Draft a Group or Set | Builds the document and runs the validator; refused drafts come back with the reason | No (a draft only) |
| Show recent history | Daily answers of a draft or saved Set on chosen assets (Visualize History) | No |
| Read the screen's numbers | Why panel parts, history bands, What followed card for an asset or Set | No |
| Save a Group or Set | Saves version 1, or the next version of an existing one | Yes: approval |
| Start a study | Queues "Study this Set" | Yes: approval |
| Add to a scan | Adds assets or an alert to an existing scan, or creates one if none runs the Set | Yes: approval |

Every approval shows exactly what will change, in plain words, with Cancel beside it. Nothing is deleted by the advisor.

## Honesty rules

The gap we saw in a competitor's AI summary (confident sentences such as "raises the chance of a sudden rise" with nothing behind them) is what this advisor must avoid.

1. **Numbers come from tools, never from the model.** Every figure in an answer is one a tool returned. The app checks the answer and removes or flags any number it cannot trace.
2. **Evidence words are fixed.** It may only describe a Set's track record with the What followed verdict and its numbers. Without a study it says "not yet studied" and offers to start one.
3. **Describe, never advise.** No "buy", "sell", "good entry" or price targets; no "will", "likely to rise" or similar forecasts. When asked "should I buy?" it explains what the readings say and that the decision is the user's.
4. **Say what is missing.** Stale or Unknown readings, coins without futures data, Sets that cannot be studied: it names the gap rather than filling it.
5. **Plain words, short answers.** Newcomer language, one idea per sentence, the ⓘ-style explanation available on request.
6. **Show its working.** Each answer lists the readings it used, so the user can open them on screen.

## Cost, model choice and privacy

- **Model.** The app already holds an xAI (Grok) key for headline sentiment, so the first version could use it. Other models with reliable tool calling (Anthropic, OpenAI, Google) are options. The choice should rest on how well the model follows tool-only rules, not on price alone.
- **Cost.** Each advisor turn is one or a few model calls. A setup conversation might be 5 to 15 turns. Prices change, so we would measure real cost per conversation in testing before launch, set a monthly cap, and show the user a daily limit rather than surprise bills.
- **Privacy.** The model sees the user's Groups, Sets, scans and the readings on screen. It never sees passwords or keys. Conversations are kept only if the user saves them.
- **Account.** The owner approves any new paid subscription or increased spend before it starts.

**Switching models (owner's request).** The owner would like the model to be a setting, with a key stored for each provider. The plan: one small adapter per provider behind the same tool list (or a library that already does this, such as LiteLLM), so the advisor's code does not change. Providers format tool calls slightly differently, and models follow rules differently, so a model only appears in the setting after it passes the same test set. The answer shows which model wrote it.

## Risks we already see

- **Sounding like advice.** A friendly explanation can read as a recommendation, especially to a newcomer. Fixed evidence words and a ban on forecast verbs help, but tone matters too.
- **Made-up numbers or signals.** Models invent plausible figures. Tool-only numbers and a check that every figure is traceable are the main guard.
- **Overfitting by conversation.** "Make it stricter until the history looks good" is tuning on the past. The advisor should warn when thresholds are changed after looking at results, and studies stay on data before the hold-out.
- **Wrong translation of the idea.** "Crowded longs" could mean funding, the long/short ratio or open interest. The advisor must state its reading and ask when unsure, not guess silently.
- **Duplicates and clutter.** Without the reuse-first rule, every conversation leaves a new Group and Set behind.
- **Cost creep.** Long conversations and repeated history previews add up.
- **Over-trust.** A fluent assistant can feel more authoritative than the evidence behind it.

## Phases: Sets first, then strategies

The advisor grows with the product. Each phase uses only building blocks that already exist and have been tested, so it never describes a capability the app does not have.

| Phase | Covers | Explain (reads only) | Find or build (with approval) |
| --- | --- | --- | --- |
| 1 | Sets, as today | Explains a Why panel reading, a Set's history bands and its What followed card | Turns an idea into Groups and a Set, reuse first; adds it to a Prism scan; starts a study |
| 2 | Sequences in Sets | Explains why a sequence is Armed or met ("Coinbase turned bullish 3 candles ago; Bitcoin has not yet") | Builds "A, then B within N candles", including across two assets |
| 3 | Strategies, tracked | Explains which stage each asset is in and why, and what the plan says happens next | Turns a described plan ("buy in three steps, take profit in two, give up below X") into a strategy draft with its ladder drawn on the chart, for approval |
| 4 | Strategies, studied | Explains a plan study in the fixed verdict wording, including how many variations were tried | Proposes a study and warns when a change looks like tuning to the past |

The honesty rules apply in every phase, and strategies add three: the advisor never suggests sizes, stops or targets of its own (it only restates the user's plan); it never turns a stage change into an instruction; and it counts every variation of a plan it builds as a test.

Version 1 is phase 1: an ✨ "Explain this" button first, then "Find or build a setup" for Sets. Phases 2 to 4 follow the strategy work.

Before launch of each phase, a set of test questions (including traps such as "should I buy?", "make it work better on the past" and, from phase 3, "how much should I put in?") is run against the advisor, and its answers are checked by hand and by rules for invented numbers, forecast words and advice.

## Questions for reviewers

1. **Order:** Is explaining first, building second the right order within each phase? And is the phase order (Sets, sequences, tracked strategies, strategy studies) right?
2. **Tools:** Is the tool list complete and small enough? What would you add, merge or remove?
3. **Reuse first:** Is matching by logic fingerprint plus "close match" comparison enough? How should the advisor present an existing setup versus a new one so the user is not confused?
4. **Approvals:** Which steps truly need approval, and which would only add friction?
5. **Honesty:** Are the rules enough to stop advice-like or forecast-like answers? How would you check traceability of numbers in practice?
6. **Overfitting:** How should the advisor handle a user who keeps adjusting thresholds after seeing history?
7. **Model:** Which model family would you choose for strict tool use and plain-language explanation, and why? Is reusing the existing Grok key sensible, and is a user setting to switch models worth the extra testing?
8. **Cost:** What cost per conversation and monthly cap are reasonable for a small product? How would you keep it predictable?
9. **Evaluation:** What should the pre-launch test set contain, and what pass mark would you use?
10. **Market practice:** How do comparable products (TradingView, TrendSpider, Koyfin, eToro's AI summary, broker assistants) do this, and what should we copy or avoid?
11. **Simplify:** What can be cut from version 1 without losing its value?

## Reply format

Please reply in this order, in plain words, under about 1,500 words:

1. **Verdict on the approach:** sound, sound with changes, or rethink, in one or two sentences.
2. **Answers to questions 1–11,** numbered to match.
3. **Risks we missed,** most serious first.
4. **Your recommended first version:** what it does, its tools, its rules, and how it is tested.
5. **Sources:** links to any products or methods you cite.

If you can read the repository, the relevant code is in `lattice_sets.py` and `signal_groups/` (Set and Group documents and validators), `signal_library/` (signals and field descriptions), `what_followed.py` (studies) and `why_panel.py` (the Why panel).
