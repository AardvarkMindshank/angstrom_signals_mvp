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

## Entry added 2026-11-01: tag created

The owner created and pushed the annotated tag from his own computer. This session cannot push tags, because its access policy returned HTTP 403. Claude verified the tag independently, read-only, from GitHub:

| Item | Value |
| --- | --- |
| Tag | holdout-spec-v1 (annotated; the only tag in the repository) |
| Tag object SHA | 86c1388e48e0bdbe0db69421ec02dd6bdfbe32c9 |
| Target commit | ac2373b71efc18fab163f8695aef7a63c474ad7f, the approved commit |
| Tagger, time | Angus, 2026-11-01 11:30:07 (UTC+07:00) |
| Tag message | Hold-out spec v1: spec hash 38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61; owner sign-off 2026-11-01; Drew review pending. |
| HOLDOUT_SPEC_HASH recomputed from research.py at the tag | 38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61 (matches) |
| requirements-research.lock at the tag | ebde66466f0a441a69f333ae181c3b41714fd01d206ffb2589abf8a204f93e10 (matches) |
| price_checksums.lock at the tag | a65419a19d002705ae8507392c1e1724dbdcf8b0a760f907d56c3f909bc8fdac (matches) |

The ChatGPT check reported by the owner gives the same tag object and target.

Status: the tag is protected by ruleset 26300455 (no deletion, no force-push, no update). Drew's independent review: still not given. Hold-out evaluation: **not run**; it needs the owner's separate explicit authorisation.
