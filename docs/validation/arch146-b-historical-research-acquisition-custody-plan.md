# Architecture 146-B — Acquisition/Custody Validation Plan

Status: **DESIGN FROZEN / DOCUMENTATION ONLY.**

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
    called by the B1 test path.

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
- evidence/report destinations cannot receive holdout response bodies or OHLCV.

PASS means only READY_FOR_ONE_ARCH146_B2_ACQUISITION_ATTEMPT. It is not paper,
broker, live, holdout-evaluation or retry authority.

## B2 post-execution evidence

A successful one-shot acquisition must record at least:

- accepted source HEAD/TREE;
- attempt identity and terminal state;
- exact request descriptors excluding secret headers;
- ordered per-page SHA256 digests and counts;
- normalized OPEN/HOLDOUT byte digests and row counts;
- first/last timestamps;
- corporate-action sidecar digests;
- OPEN and FINAL_HOLDOUT manifest IDs;
- dataset snapshot ID;
- physical partition fingerprints;
- full logical historical-data fingerprint;
- XNYS coverage result;
- final custody/open root identities and ACL classification;
- zero production/paper/broker/live effects.

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
B2 success creates only the immutable research-data snapshot and OPEN research
material. It does not authorize Architecture 145 final-holdout admission,
strategy promotion, production deployment, paper trading, broker submission or
live trading.

After accepted B2 evidence, the next product milestone is Architecture 145-B
results/campaign-bundle work against DEVELOPMENT + WALK_FORWARD material, then
the Research Results GUI and large strategy campaigns.
