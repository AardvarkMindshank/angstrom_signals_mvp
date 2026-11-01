# Hold-out validation specification: sign-off record

Recorded 2026-11-01 11:18 (Asia/Bangkok, UTC+07:00) at the owner's instruction, by Claude (research assistant).

## Owner sign-off: GIVEN

Angus (repository owner, AardvarkMindshank) approved the hold-out validation specification, section 12:

> I approve the hold-out validation specification in section 12, fingerprint:
> 38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61
> The approved research code commit is:
> ac2373b71efc18fab163f8695aef7a63c474ad7f
> I accept the documented primary hypotheses, decision thresholds, exploratory-only diagnostics and limitations.

## Independent review by Drew: NOT GIVEN

Drew was unavailable. He has **not** independently reviewed or approved the specification. The owner proceeded with owner-only sign-off. Any later review by Drew will be added to this file as a dated entry. Earlier text will not be changed.

## What was approved

| Item | Value |
| --- | --- |
| Specification | "Hold-out validation specification", section 12, doc revision 28 (https://claude.ai/artifact/EPyGhevdwatNgQY6bCFqio) |
| Spec fingerprint (HOLDOUT_SPEC hash) | 38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61 |
| Research code commit | ac2373b71efc18fab163f8695aef7a63c474ad7f (branch research-v2) |
| Package lock, SHA-256 of requirements-research.lock | ebde66466f0a441a69f333ae181c3b41714fd01d206ffb2589abf8a204f93e10 |
| Price checksum list, SHA-256 of price_checksums.lock (88 files) | a65419a19d002705ae8507392c1e1724dbdcf8b0a760f907d56c3f909bc8fdac |
| Primary hypotheses | B (crypto Trend ranking), C1 (ATR% stocks), C2 (ATR% crypto); Holm at 5%; A1 and A2 dropped at the development gate |
| Preflight 2 | research/2026-11-01_0402_preflight (all checks passed) |

## Repository protections (verified by the GitHub API, 2026-11-01)

| Ruleset | ID | Target | Enforcement | Rules |
| --- | --- | --- | --- | --- |
| Protect research reports | 26300334 | refs/heads/reports | active | no deletion, no force-push (non-fast-forward) |
| Protect holdout tags | 26300455 | refs/tags/holdout-* | active | no deletion, no force-push, no update (a tag cannot be moved); creation allowed |

## Status

- Tag holdout-spec-v1: **not created.** It needs the owner's explicit approval.
- Hold-out evaluation: **not run.** It needs the owner's explicit approval after the tag.
