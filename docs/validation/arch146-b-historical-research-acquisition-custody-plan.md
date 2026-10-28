# Architecture 146-B — Acquisition/Custody Validation Plan

Status: **B1-C1/C2 PUBLISHED / CI FAILED; B1-C3 STATIC PARITY CORRECTION PENDING.**

## B1 required source verification

The source checkpoint must prove with synthetic/fake dependencies that:

1. request construction is exact for SPY, 1Day, raw, SIP, USD and the frozen
   2016-01-01 through 2026-10-24 coverage;
2. bars pagination consumes every `next_page_token` exactly once and rejects
   token loops, duplicate pages, missing terminal state and response-symbol drift;
3. corporate-actions requests explicitly bind symbols=SPY, region=us,
   start/end, data_quality=complete, sort=asc and paginate to exhaustion;
4. the corporate-action `types` filter is omitted and raw page bytes are
   retained without dropping unfamiliar action groups;
5. only HTTP GET to `data.alpaca.markets` and the two reviewed endpoint families
   can be represented by the operator;
6. authentication values are injected at the effect boundary and are never
   serialized, logged, hashed into semantic identities or returned in evidence;
7. every raw page is durably represented before normalization and page ordering
   is bound into the manifest digests;
8. normalization is deterministic and exactly matches the 146-A canonical CSV
   rules;
9. bars at/after the half-open end, wrong symbols, wrong feed/adjustment,
   duplicate/unsorted bars, invalid OHLCV and missing/unexpected XNYS sessions
   fail closed;
10. OPEN and FINAL_HOLDOUT bytes are split at the exact frozen boundary and the
    full logical fingerprint reconstructs over their chronological concatenation;
11. the protected holdout destination can never be replaced with a repo,
    worktree, ordinary temp, GUI/report or production path;
12. OPEN publication is impossible until holdout persistence and complete
    146-A dataset verification succeed;
13. logs/evidence contain no holdout OHLCV, raw response bodies or credential
    values;
14. a pre-existing unexpected destination, ACL drift, partial state or ambiguous
    write classifies STOP/reconciliation rather than retry;
15. source tests perform zero real network requests, zero credential reads, zero
    real ACL mutations and zero real dataset writes;
16. Architecture 145-A and 146-A schemas, identities and serializer behavior stay
    unchanged;
17. no scheduler, production runtime, paper, broker or live module is imported or
    called by the B1 test path;
18. synthetic mixed bars pages spanning the 2024 boundary are accepted by the
    custodian path without publishing those raw bytes to OPEN;
19. no redacted or reserialized OPEN projection is ever labeled or digested as an
    original vendor page;
20. complete ordered original bars-page provenance and complete corporate-action
    provenance remain protected, while both partition manifests may bind the
    same dataset-level digest vector/sidecar digest when the source stream spans
    both partitions;
21. normal-research OPEN verification consumes only normalized OPEN CSV,
    non-price 146-A commitments, canonical custody evidence and an independently
    pinned custody-admission binding; it consumes zero raw vendor-page bytes and
    zero corporate-action sidecar bytes;
22. `verify_historical_research_open_publication` independently checks canonical
    OPEN CSV bytes, digest/size/count, first/last timestamp, physical fingerprint,
    exact bounds/session coverage and snapshot/manifest membership without
    delegating to the raw-material OPEN verifier;
23. a self-consistent manifest, custody-evidence object, caller-selected expected
    hash, report path or arbitrary admission object cannot satisfy the successor
    verifier unless the evidence bytes match the externally frozen accepted
    evidence SHA256 and exact B2 source/checkpoint/attempt/snapshot/calendar
    binding;
24. the B2 evidence model is canonical and non-price, contains no raw response
    body/OHLCV/credentials, and binds all fields required by
    `historical-research-custody-evidence/v1`;
25. B1 uses only an injected synthetic historical-session authority and does not
    treat the existing 146-A `NYSEMarketCalendar` as published historical
    authority or invent exceptional closures.

B1 verification should include focused tests for success, pagination, HTTP status
failure classes, malformed JSON, byte/digest drift, crash-state classification,
path/ACL rejection and holdout-leakage guards.

## B1 publication discipline

Use one isolated feature worktree from the current reviewed develop tip, one
logical source checkpoint, one atomic commit/push and one push-triggered
Checkpoint Source Gates run.

Canonical profile: FULL, GitHub-owned.

Do not duplicate FULL locally. Local prepublication checks are focused pytest,
Ruff check/format-check, diff-check and the repository admission command required
by the current workflow.

Terminal red is preserved. Corrective ownership follows the current workflow:
mechanical in-scope correction may continue as a separately named corrective
checkpoint; any security/authority ambiguity or missing prepublication coverage
returns to ChatGPT.

## B2 pre-execution admission

Before the first real network or ACL effect, a separately reviewed operator
preflight must prove:

- exact accepted B1 HEAD/TREE and clean source;
- the expected branch/runner registration;
- current Alpaca Market Data endpoint semantics still match the frozen design;
- SIP historical entitlement is available;
- credential source/type is exact, without exposing values;
- the two target roots are absent or match an explicitly reviewed fresh-state
  classification;
- the custody parent is local NTFS/non-reparse and supports the exact protected
  DACL;
- no ordinary development process has been granted holdout access;
- evidence/report destinations cannot receive holdout response bodies or OHLCV;
- the exact published historical-session authority for the full v1 interval has
  been separately reviewed and frozen, including its immutable identity/digest
  and timezone/session-date semantics;
- B2 preflight can reconcile the operator's configured calendar authority to
  that exact frozen identity without reading holdout OHLCV.

Until the historical-session authority is accepted, B2 preflight must BLOCK and
must not dispatch a real provider request or ACL mutation.

PASS means only READY_FOR_ONE_ARCH146_B2_ACQUISITION_ATTEMPT. It is not paper,
broker, live, holdout-evaluation or retry authority.

## B2 post-execution evidence

A successful one-shot acquisition must record at least:

- evidence schema `historical-research-custody-evidence/v1`;
- accepted B1 source HEAD/TREE;
- B2 checkpoint, attempt identity and terminal success state;
- exact canonical request descriptors excluding secret headers;
- ordered original per-page SHA256 vectors and counts for bars and corporate
  actions;
- normalized OPEN/HOLDOUT byte digests, sizes and row counts;
- first/last timestamps;
- complete corporate-action sidecar digest;
- OPEN and FINAL_HOLDOUT manifest IDs;
- dataset snapshot ID;
- physical partition fingerprints;
- full logical historical-data fingerprint;
- exact historical-session-authority identity/digest and reconciliation result;
- unchanged 146-A XNYS coverage result;
- final custody/open root identities and ACL classification;
- zero production/paper/broker/live effects.

After execution, independent ChatGPT evidence review must freeze a separate
`historical-research-custody-admission/v1` binding containing at least the
canonical custody-evidence SHA256, accepted B2 source HEAD/TREE, checkpoint,
attempt identity, snapshot ID and historical-session-authority identity. This
admission artifact is not produced or self-approved by the B2 custodian.

The report must not contain raw bars, raw corporate-action bodies, credentials or
secret-derived values.

## Failure / STOP matrix

The attempt stops without blind retry on:

- 401/403 authentication or entitlement failure;
- 429/rate-limit response;
- any 5xx or transport ambiguity after request dispatch;
- malformed/unexpected response shape;
- pagination token loop or page replay;
- wrong symbol/feed/adjustment/currency;
- calendar/session mismatch;
- corporate-action continuity ambiguity requiring policy review;
- destination already present unexpectedly;
- ACL/owner/reparse/volume mismatch;
- write/fsync/readback ambiguity;
- digest, manifest, fingerprint or snapshot mismatch;
- source drift or evidence leakage.

A consumed ambiguous attempt requires a later read-only reconciliation design.
It does not automatically authorize cleanup or retry.

## Acceptance boundary

B1 source acceptance authorizes no effects.
B2 success creates only the immutable research-data snapshot, protected
provenance/custody material and a not-yet-self-authorizing OPEN publication
package. It does not by itself authorize normal research consumption.

Normal research consumption requires independent acceptance of the exact B2
custody evidence and the additive successor
`verify_historical_research_open_publication` path. Neither B2 success nor that
OPEN admission authorizes Architecture 145 final-holdout admission, strategy
promotion, production deployment, paper trading, broker submission or live
trading.

Only after accepted B2 custody evidence/admission may the next product milestone
advance to Architecture 145-B results/campaign-bundle work against DEVELOPMENT +
WALK_FORWARD material, then the Research Results GUI and large strategy
campaigns.

## Implemented B1 verification surface

Focused source modules:

- `tests/experiments/test_historical_research_acquisition_custody.py`;
- unchanged `tests/experiments/test_historical_research_dataset.py`;
- affected `tests/runtime/checkpoint_runner/test_core.py`, `test_ci.py` and
  `test_source_authority.py`.

The kernel has no native bindings or real B2 dispatcher. Synthetic persistence
receipts and inspections test the contract and ordering, not actual Windows ACL,
NTFS/fsync, HTTP entitlement or credential-store behavior. Native B2 bindings
require a later reviewed source/host boundary before the one real attempt.

Public evidence carries frozen request descriptors, ordered page digests/counts,
complete non-price manifests/snapshot, operational source/attempt identities,
calendar identity/digest, exact roots/DACL and terminal state/effect ceilings.
Calendar digest material includes full coverage, exchange timezone, canonical
session dates and the supplied publication source digest. No arbitrary supplied
calendar becomes published authority without a source-owned accepted entry.

Exact clean FEATURE/PROSPECTIVE_DEVELOP admission and canonical FULL follow only
after an explicitly authorized atomic candidate commit and publication. Neither
local synthetic verification nor this document reports source acceptance.

## 146-B1-C1 — prepublication certification-inventory correction

Initial unpublished candidate a0d7050c52957abab292ce98d4d3a7265d9f4d63,
tree f6145307daec6c1765443bd819a69e6f046f2861, failed its local required
prepublication test gate: 867 passed, two failed. Both FEATURE and
PROSPECTIVE_DEVELOP authority passed, as did Ruff/diff checks; source identity
remained stable. No push or GitHub run occurred for that failed candidate.

Preserved report:

    F:\AI\temp\ai-trading-bot-checkpoints\arch146-b1-admission-d9448ee44a22443ebf77ebfb5493470f\arch132-r3n-prepublication-admission\source-gate-20261028T071014.640864Z\report.json

SHA256:

    41149073dcd83011e6e99aa194a192ebb9ad8c45b64dbda8d95be21ab3844d1c

Classification: bounded stale test-inventory expectations exercised and caught
by the required prepublication gate, not PREPUBLICATION_COVERAGE_DEFECT.
C1 adds the new supported acquisition test module to the exact current FULL
inventory/count expectation (209 FULL / 431 EXHAUSTIVE, with ROBINHOOD 117 and
LEGACY 222 unchanged), preserves the historical timing sample, and proves the
new module appears exactly once in current six-lane FULL using fallback weight.
The required 122/49 baselines, certification implementation and lane policy do
not change. Preserve the original unpublished commit and report; require a new
normal corrective commit, complete admission on its exact clean source, and
one first publication only after PASS. No amend/rebase/force or CI rerun.

## 146-B1-C2 - prepublication coverage correction

Published B1-C1 source was HEAD
`2208b7e637671001b02deb56751dc7687a3cf36d`, TREE
`0b37449859b0bad78704f5324cdb19a2aa3d3475`. Its push-triggered Checkpoint
Source Gates #782 / run `40649744489` / attempt 1 is terminal FAILURE. Canonical
FULL reported 14,697 cases: 14,689 passed, 6 skipped, 2 failed and 0 errors.
The exact failures were:

1. `tests.review_paper.test_arch134_readonly_deployment_admission_diagnostic::test_diagnostic_current_authority_does_not_rebind_historical_entrypoints`
2. `tests.experiments.test_research_strategy_production_compatibility::test_arch143_inventory_overlay_exact_predecessor_and_blobs`

Classification: `PREPUBLICATION_COVERAGE_DEFECT`. Preserve #782 unchanged; do
not rerun or overwrite its evidence.

The bounded C2 correction reconstructs the historical R3M workflow input after
removing later current checkpoint registrations, including B1, while preserving
the predecessor predicate. Architecture-143 pin semantics are verified against
the immutable historical object catalog; current test bytes remain owned by the
current test/authority path. A path-triggered local admission bundle runs both
regression modules when the workflow, runner, certification, current-authority,
or affected test surfaces change. Ordinary source-only changes retain the
smaller existing bundle. C2 does not run canonical FULL locally and does not
change frozen historical pin values.

This corrective candidate requires focused tests, Ruff/diff checks, clean-candidate
FEATURE and PROSPECTIVE_DEVELOP admission, then one ordinary push and terminal
mapped GitHub CI before exact-source review. It grants no source acceptance or
integration. No B2 credential, network, filesystem, custody, ACL, holdout, host,
paper, broker or live effect occurred.

## 146-B1-C3 - static-toolchain/file-universe parity correction

Preserve #782 and #783 / run `40658848795` / attempt 1 unchanged. C2 source
HEAD `2ec59d6a8f409d469485815106c5087125b977be`, TREE
`17c2985af56076d9aef8ec4c1b5abe2d623a7e69` passed all canonical test cases:
14,700 total, 14,694 passed, 6 skipped, 0 failed/errors. Canonical Ruff check
passed; Ruff format failed on this document's preexisting non-UTF-8 byte.
The canonical FULL wall was 354.487 seconds, above the unchanged 300-second
hygiene ceiling. This remains an immutable timing observation, not authority
to change topology, timing maps, pins, weights, dependencies or test inventory.

Classification:
`PREPUBLICATION_COVERAGE_DEFECT / STATIC_TOOLCHAIN_FILE_UNIVERSE_PARITY`.
Local Ruff 0.15.21 and CI Ruff 0.17.3 came from the prior open dependency range;
their formatter file universes differed. C3 normalizes the single Windows-1252
0x97 heading byte to UTF-8 U+2014, preserving the prose, and freezes Ruff 0.17.3
for development, admission and every relevant workflow install. The current
certification owner validates dependency/install parity; the old pyproject pin
reconstructs its immutable historical object instead of pinning today's tools.
Local admission and canonical certification share exact version expectations and whole-root
non-mutating commands. Markdown remains in the canonical formatter universe.

Canonical static checks now precede certification children; version/static
failure persists evidence without launching pytest. Source identity, lane
topology, inventory, timeouts and result accounting remain in force. Admission
adds the affected certification result/source regressions to the C2 coherence
bundle. No canonical FULL runs locally.

C3 requires complete focused verification, combined static checks, exact clean
candidate FEATURE/PROSPECTIVE_DEVELOP admission, one atomic normal commit/push
and one terminal mapped CI result. If fresh canonical wall remains at or above
300 seconds, preserve it and STOP for ChatGPT timing review without an unchanged
rerun or automatic topology correction. Terminal-green C3 is required before
B-E implementation; publication additionally requires base acceptance/integration.
No source acceptance, integration or B2 credential/network/custody/ACL authority
is granted here. R3 remains parked and LIVE remains NO-GO.
