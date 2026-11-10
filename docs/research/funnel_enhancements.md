# Funnel: enhancement list (10 Nov 2026)

Agreed direction with the owner; to be put to ChatGPT, Gemini and Grok as a brief before building (major design).

1. **Funnel editor.** Provided funnels are a starting point, as Groups and Sets are: change any stage's Set (own or
   provided), add or remove stages, change timeframes, direction, the "fails twice" rule and alerts. Funnels become
   the next layer: Signals → Groups → Sets → Funnels → Prism/alerts; a 🔻 Funnels section in Lattice next to Prism.
2. **Shared answers.** A Set's answer for an asset at a close is the same for everyone: work it out once per
   (Set logic hash × asset × close) and reuse it, as studies are shared by logic hash. Cost grows with the number of
   different Sets, not users. Needed before many users.
3. **Own pool.** Narrow the universe (top 100, no meme coins, sectors, minimum volume) or run a funnel over the
   person's own watchlist.
4. **Funnel studies.** What followed coins becoming Candidates. Mind survivorship and multi-stage selection
   (reviewers: not in version 1).
1b. **Funnel notifications open the funnel** in the 🔻 Funnels tab (as Study finished notes open their Set). The
   notes already carry the funnel id (asset_symbol "funnel:<id>"). Until the tab exists, they are not clickable.
5. **Sharing funnels.** A trader publishes a funnel for others to copy; must never read as trade recommendations.

Done:
- A new Candidate gets a fresh news-sentiment reading (only Candidates; at most 10 per funnel pass), so its
  sentiment is current when the alert arrives (funnel_runner.SupabaseStore.refresh_sentiment).
