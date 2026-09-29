# Token budget plan

| Stage | Model | Effort | Estimate (% of a 5-hour window) |
|---|---|---|---|
| /research, quick lookups | Haiku 4.5 | low | 3% |
| /grill-with-docs, /to-spec, /to-tickets | Opus 5.5 | high | 25% |
| /implement + /tdd (per ticket) | Sonnet 5.5 | medium | 10% |
| /code-review (per ticket) | Sonnet 5.5 | high | 5% |

## Questions

**How many 5-hour windows will the 9 tickets take?** About 3. Each ticket is roughly 15% of a window (implement plus review), so 9 tickets is about 135%, plus the grill and spec at about 25%. That is about 1.6 windows of pure work, and I will round up to 3 because I will need to wait out resets and some tickets will run long.

**How much of one week is that?** Right now my ledger shows about 17% of the weekly cap used, mostly from setup. I guess the 9 tickets will take about 40% more.

**Which stage will I cut first if I am wrong?** I will lower the effort on /code-review, then move /implement to a cheaper model. I will not cut the grill, because everything downstream depends on it.
