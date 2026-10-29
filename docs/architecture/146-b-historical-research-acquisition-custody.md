# Architecture 146-B — Historical Research Acquisition and Custody

Status: **B1/C1-C6 CLOSED AND INTEGRATED; CONSOLIDATED PRE-B2 SOURCE CHECKPOINT.** No provider, credential,
filesystem, ACL, holdout, backtest, paper, broker, production or live effect is
authorized by this document.

## Purpose

Architecture 146-A already supplies the immutable SPY v1 manifest/snapshot
contracts and pure verification over caller-supplied material. 146-B adds the
bounded path that can eventually acquire the real vendor bytes, normalize them,
separate OPEN from FINAL_HOLDOUT custody, and produce one externally verifiable
v1 snapshot without exposing holdout OHLCV to normal research tooling.

The production-host Architecture 134 blocker is independent and remains parked.

## Frozen predecessor

Current planning base:

    develop HEAD 99654f3547140dc8fd005ee1525ac9a77987b946
    develop TREE 5b04b8d4baf70b3a936d10a5972ffcd26c03dd3c

Architecture 146-A C2 is an exact ancestor:

    HEAD 6906ba01bfb6a353029d695e584b2097587b81b9
    TREE aa1efe5057e047e0d1778f2422e45f26cbc9f5d6
    CI   #720 / 40178730059 / attempt 1 / SUCCESS

146-B must reuse the accepted
`trading_bot.experiments.historical_research_dataset` contracts. It may add
successor acquisition/custody source, but it must not reinterpret 146-A IDs,
partition bounds, schemas, fingerprints or 145-A identities.

## Dataset remains frozen

    symbol           SPY
    calendar         XNYS
    timeframe        1Day / 1D
    adjustment       raw
    feed             sip
    currency         USD
    price semantics  PRICE_RETURN

    FULL COVERAGE
    [2016-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

    DEVELOPMENT
    [2016-01-01T00:00:00Z, 2020-01-01T00:00:00Z)

    WALK_FORWARD
    [2020-01-01T00:00:00Z, 2024-01-01T00:00:00Z)

    FINAL_HOLDOUT
    [2024-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

No extension, QQQ/multi-symbol expansion, total-return adjustment or holdout
boundary change is part of 146-B.

## Vendor contract reverified for this design

Public Alpaca Market Data documentation was rechecked on 2026-10-27.

Bars remain:

    GET https://data.alpaca.markets/v2/stocks/SPY/bars
    timeframe=1Day
    start=2016-01-01T00:00:00Z
    end=2026-10-24T00:00:00Z
    adjustment=raw
    feed=sip
    currency=USD
    sort=asc
    limit=10000
    page_token=<returned token until absent>

The API documents the end parameter as inclusive. 146-B therefore must reject,
not silently filter, any returned bar whose normalized timestamp is at or after
the frozen half-open dataset end. The expected dataset contains only admitted
XNYS regular sessions.

Corporate-action provenance remains:

    GET https://data.alpaca.markets/v1/corporate-actions
    symbols=SPY
    region=us
    start=2016-01-01
    end=2026-10-24
    data_quality=complete
    sort=asc
    limit=1000
    page_token=<returned token until absent>

The `types` filter is deliberately omitted so every type supported by the
endpoint is returned. The current endpoint includes additional types introduced
after the original 146 design, including partial_call, reorganization and
capital_gains_distribution. Raw response pages are preserved byte-for-byte, so
future or unfamiliar returned action groups cannot be silently dropped.

Alpaca documents that corporate-action availability may be delayed. Therefore
the sidecar is provenance observed at the frozen acquisition, not a guarantee
that the vendor has disclosed every future correction. Any continuity-changing
event found in the returned material blocks downstream admissibility until
reviewed.

A change to endpoint semantics, entitlement, authentication method, feed access
or permitted use before B2 execution is a STOP/review condition.

## Architecture review correction — mixed-page provenance and OPEN publication

Architecture review base:

    develop HEAD b4e9fb173bcfe0edee473dd12640e4305012f4a5
    develop TREE 15bded7d020fee60d399b1914f68b1b6a6bc86fb
    Checkpoint Source Gates #780 / 40643221998 / attempt 1 / SUCCESS

Reviewed B1 source worktree:

    F:\AI\worktrees\ai-trading-bot-146b1-source
    feature/research-arch146-b-acquisition-custody-current

The frozen full-range request plan is retained. The architecture does **not**
switch to partition-scoped vendor requests merely to make raw-page custody easier.

A returned bars page may contain rows from both sides of the
2024-01-01T00:00:00Z OPEN/FINAL_HOLDOUT boundary. Likewise, the complete
corporate-action response stream is dataset-level provenance and may describe
events on either side of that boundary. Vendor page boundaries are therefore
not custody boundaries.

Architecture 146-A intentionally treats raw vendor pages and the corporate-action
sidecar as opaque integrity provenance. Its
`verify_historical_research_partition` requires the exact supplied raw-page
tuple and sidecar bytes to match the partition manifest, and
`verify_historical_research_open_commitment` delegates to that verifier. That
existing interface remains valid for synthetic/privileged verification, but it
is **not** the normal-research verification interface for a real 146-B
acquisition whose protected provenance bytes may contain FINAL_HOLDOUT material.

The following successor rules are frozen:

1. Every original bars response page and every original corporate-action
   response page is persisted byte-for-byte under protected custody before
   normalization. No redaction, partition reserialization or OPEN projection is
   labeled as an original vendor page.
2. For the v1 full-range acquisition, both 146-A partition manifests may bind the
   same complete ordered bars-page digest vector when mixed pages contribute to
   both partitions. Both may bind the same complete corporate-action sidecar
   digest. This is dataset-level acquisition provenance, not a claim that the
   protected raw bytes are partition-local.
3. Custodian-side complete verification supplies exact protected provenance
   bytes to the additive 146-B published-session verifier, reusing all 146-A
   physical checks. Existing 146-A public verifier behavior is unchanged.
   Normal research supplies **none** of those protected bytes.
4. The real OPEN publication contains normalized OPEN CSV plus non-price
   manifests/commitments and accepted non-price custody evidence only. It does
   not contain original full-range raw pages, the complete corporate-action
   body, or any other byte object capable of disclosing FINAL_HOLDOUT prices.
5. Normal research must not call
   `verify_historical_research_open_commitment` on real acquired v1 material.
   B1 adds an additive successor interface,
   `verify_historical_research_open_publication`, without changing 146-A
   schemas, IDs, serializers or existing verifier behavior.
6. The successor verifier directly validates the complete OPEN normalized CSV:
   canonical parsing, exact OPEN bounds, SHA256/byte size, row count,
   first/last timestamp, physical historical-data fingerprint and session
   coverage. It reconciles snapshot/manifest membership using public 146-A
   contract fields but never opens raw vendor pages or the corporate-action
   sidecar.
7. Raw-page truth, normalization truth, complete snapshot truth and custody truth
   are not inferred from a self-consistent manifest. They are established by
   the separately reviewed B2 custodian execution and then bound into normal
   research by an **externally accepted immutable non-price evidence artifact**.
8. The serialized B2 evidence schema is additive:
   `historical-research-custody-evidence/v1`. At minimum it binds exact B2
   source HEAD/TREE, checkpoint and attempt identity, terminal success state,
   canonical request descriptors, ordered raw-page SHA256 vectors/counts for
   both endpoint families, normalized OPEN/HOLDOUT digests/sizes/counts and
   first/last timestamps, corporate-action sidecar digest, both partition
   manifest IDs, dataset snapshot ID, physical fingerprints, full logical
   fingerprint, historical-session-authority identity/result, custody/open-root
   classifications and zero production/paper/broker/live effects. It contains
   no raw response body, OHLCV value, credential or secret-derived value.
9. B2 evidence is **not self-authenticating**. After the real attempt, ChatGPT
   must independently review the exact accepted B2 source and immutable evidence
   bytes and freeze at least: evidence SHA256, B2 source HEAD/TREE, checkpoint,
   attempt identity, snapshot ID and historical-session-authority identity. The
   resulting external acceptance binding uses additive schema
   `historical-research-custody-admission/v1`.
10. `verify_historical_research_open_publication` may accept custody evidence
    only when its canonical bytes hash to that independently frozen evidence
    SHA256 and every frozen source/attempt/snapshot/calendar field matches. A
    caller-supplied receipt, arbitrary expected hash, self-consistent admission
    object or report path is not custody authority.
11. Successful B2 execution may materialize OPEN bytes only after complete
    custodian-side 146-A verification, but normal research consumption remains
    blocked until the separate B2 evidence/admission review above is accepted.
    The successor verifier is the required real-data OPEN admission surface.

This decision supersedes any earlier design-era implication that
`vendor-raw\open\...` or the complete corporate-action sidecar belongs in the
normal development OPEN root for real 146-B v1 acquisition. Those protected
bytes remain under custody.

### Historical-session authority remains an independent B2 prerequisite

The accepted 146-A `NYSEMarketCalendar` check remains a repository consistency
check; Architecture 146 explicitly did not certify it as published historical
session authority or grant exceptional-closure authority. B1 therefore uses an
injected historical-session-authority boundary in synthetic tests and must not
claim that 146-A calendar success alone makes B2 ready.

Before any real B2 network/ACL effect, a separate reviewed decision must freeze
the exact published historical-session authority, coverage interval,
timezone/session-date semantics and immutable identity/digest used for v1. B2
must reconcile normalized bars against both the unchanged 146-A check and that
accepted external authority. Any disagreement is STOP before OPEN publication.
No real attempt is consumed merely to discover this predictable prerequisite.

## Two-step authority boundary

### 146-B1 — source checkpoint

B1 implements the operator and tests it entirely with injected transports,
synthetic response pages and disposable test filesystem/ACL adapters.

B1 may add:

- exact request construction and pagination state;
- raw-page digesting and persistence plans;
- deterministic bar normalization into the existing 146-A CSV format;
- corporate-action sidecar preservation;
- OPEN/FINAL_HOLDOUT split planning;
- snapshot/manifest construction through 146-A public contracts;
- the additive `historical-research-custody-evidence/v1` non-price evidence
  model and externally pinned `historical-research-custody-admission/v1`
  consistency boundary;
- the additive `verify_historical_research_open_publication` real-data OPEN
  verification interface, which consumes no protected raw page or sidecar bytes;
- an injected historical-session-authority boundary for synthetic B1 testing;
- bounded evidence/report models;
- crash/reconciliation state classification;
- Windows custody ACL code that is unreachable from tests without an injected
  explicit effect adapter.

B1 may not:

- read real credentials;
- make a real HTTP request;
- create either real dataset root;
- mutate a real ACL;
- read or write real holdout bytes;
- run 145-B or any strategy/backtest;
- touch production/runtime/scheduler/paper/broker/live state.

Expected implementation checkpoint:

    arch146-b1-historical-research-acquisition-custody-source

Expected branch:

    feature/research-arch146-b-acquisition-custody-current

Because the operator crosses credential/network/Windows-custody boundaries when
later executed, implementation/review model is Sol High. GitHub owns canonical
FULL certification. Local work uses focused tests, Ruff and diff-check only.

### 146-B2 — one reviewed acquisition/custody execution

B2 is separate from source acceptance. It may run only after exact B1
source/CI/integration review.

B2 may perform exactly one manually initiated attempt that:

1. proves exact source and clean state;
2. verifies current Alpaca endpoint/entitlement/credential prerequisites without
   exposing secret values;
3. creates a fresh protected holdout acquisition root with the reviewed DACL;
4. fetches every bars page and every corporate-action page by GET only;
5. persists raw response bytes before normalization;
6. normalizes and validates the complete dataset;
7. writes FINAL_HOLDOUT material and all original full-range vendor/corporate-
   action provenance only under protected custody;
8. reconstructs and verifies the full 146-A snapshot/manifest chain inside the
   protected custodian boundary using the exact original provenance bytes;
9. admits session coverage against the independently accepted published-session
   authority. The old 146-A/global modeled calendar remains historical
   repository behavior. Its reconciliation delta is frozen to exactly
   2018-12-05 and 2025-01-09 (model minus published), with no published-minus-
   model dates. Any additional delta is STOP; no fabricated closure bars;
10. materializes only normalized OPEN CSV plus non-price manifests/commitments to
    the development root after complete custodian verification;
11. emits canonical `historical-research-custody-evidence/v1` containing only
    identities, digests, counts, request metadata, calendar-authority binding and
    final state, never raw bodies, holdout OHLCV or credential values;
12. leaves normal research consumption blocked until ChatGPT independently
    accepts the exact B2 evidence bytes/source binding and freezes
    `historical-research-custody-admission/v1` material for the successor OPEN
    verifier.

A network error, authentication/entitlement rejection, ambiguous persistence,
ACL mismatch, unexpected pre-existing destination, malformed vendor response,
calendar mismatch or crash is terminal for that attempt. No blind retry or
cleanup may make an ambiguous attempt look fresh. Reconciliation, if needed, is
a later reviewed read-only checkpoint.

## Storage boundary

Development OPEN root remains:

    F:\AI\ai-trading-bot\data\research\arch146-v1

Protected custody root remains:

    F:\AI\research-holdout\arch146-v1

Normal development/research processes must not be able to enumerate or open
FINAL_HOLDOUT content. All original full-range bars pages, all original
corporate-action pages/complete sidecar bytes, holdout normalized CSV and
protected temporary persistence remain under custody and never enter the
repository, worktrees, ordinary `F:\AI\temp`, GUI/report directories or test
fixtures.

The development OPEN root may contain only normalized OPEN CSV, the non-price
146-A manifests/snapshot commitments, canonical non-price custody evidence and
the separately accepted non-price custody-admission binding. It contains no
`vendor-raw\open` publication for real v1 acquisition.

The protected root DACL remains the Architecture 146 design:

- BUILTIN\Administrators: FullControl;
- NT AUTHORITY\SYSTEM: FullControl;
- protected inheritance;
- no ordinary-user, Trading-service or broad inherited allow ACE.

B2 may use a fresh protected acquisition child under the custody root while the
attempt is incomplete. Any attempt/evidence record outside that root contains
non-price metadata only.

## Publication rule

OPEN material is the only dataset content available to normal research.
Materialization to the development root is allowed only after protected
custodian verification of the complete dataset. **Research admission is a
separate step:** the exact B2 evidence must then receive independent external
acceptance, and real-data consumers must use
`verify_historical_research_open_publication` with that frozen evidence/source
binding. Presence of files in the OPEN root alone is not admission.

No B2 result or custody-admission record authorizes opening FINAL_HOLDOUT for
model/parameter selection. Architecture 145's later explicit final-holdout
admission remains separate.

## Explicit non-scope

146-B does not:

- change Architecture 145 policy thresholds;
- select a strategy or parameters;
- run 145-B campaigns;
- build the Results GUI;
- promote a strategy;
- modify Architecture 134 host admission;
- schedule unattended production;
- authorize paper, broker or live trading.

LIVE remains NO-GO.

## B1 source implementation and retained effect boundary

The additive public modules are
`trading_bot.experiments.historical_research_acquisition` and
`trading_bot.experiments.historical_research_custody`. The former is a one-use
kernel whose credential, transport, custody, persistence and terminal-record
ports are all injected. The latter owns canonical non-price evidence/admission,
historical-session commitments and the successor OPEN verification interface.
146-A schemas, identities, serializers and public verifier behavior are unchanged.
The pre-B2 source extracts shared physical helpers only; 145-A is unchanged.

The original B1 checkpoint left both registries empty. The consolidated pre-B2
source now populates `ACCEPTED_HISTORICAL_SESSION_AUTHORITIES` with exactly the
independently accepted 2718-session published authority;
`ACCEPTED_CUSTODY_ADMISSIONS` remains empty. Parsing or supplying a hash never
adds authority. There is no runtime registration API. See the
[pre-B2 source record](../validation/arch146-b-pre-b2-readiness.md).

All original bars/corporate-action pages and the complete sidecar stay behind
the protected persistence port. Both partition manifests bind the same original
bars-page digest vector and complete sidecar digest. Only normalized OPEN CSV,
non-price manifests/snapshot and evidence can reach the OPEN materializer.
OPEN file presence remains unadmitted. Success is named
`MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION`; partial/ambiguous state is terminal
`STOP_RECONCILIATION_REQUIRED` and is never cleaned or retried by the kernel.

The fixed persistence plan requires the exact two roots, Administrator ownership,
protected Administrator/SYSTEM DACL, local NTFS, no reparse traversal and
exclusive fresh destinations. Injected ports must provide create-only durable
writes and verified readback receipts; the kernel checks custody inspection
before/after protected writes and OPEN materialization. Limits are 1000 pages,
4 MiB per response and 64 MiB per stream; out-of-bound input stops without retry.
Numeric/timestamp bounds reject unsupported precision instead of truncating it.

The registered B1 checkpoint has no preflight or execute dispatcher. Native
bindings and a separately executable read-only preflight are additive pre-B2
source; neither the B1 kernel nor fake tests establish real-host readiness.


## Consolidated pre-B2 source boundary

B1/C1-C6 is accepted/integrated at d2e9cbcb08c06eb050ee6d131ba3719d5c82ac42;
#788 is accepted and #789 is develop reuse SUCCESS. #787 remains cancelled
immutable evidence. The published historical source is recovered and accepted.
The global modeled calendar and Architecture 56/57/111/paper identities remain
unchanged. No global calendar repin is permitted by this checkpoint.

Native adapters are defined only by the dedicated pre-B2 modules. Custody uses
fixed roots, exact protected owner/DACL, explicit OPEN read policy, a create-only
claim under the protected existing parent, no-follow held parent handles,
local NTFS, create-only file writes, file/volume flush, same-handle readback and
terminal preservation. No rename/promotion/cleanup path exists. The B2 credential
account now reuses the retained approved source-owned Trading
SID and exact current /v3 scoped reader; current token SID equality precedes
any secret read. That identity reuse grants no provider or deployment authority.
Fresh parent provisioning and custody security remain closed host prerequisites;
no missing/unproven parent is repaired by the adapter.

The real-host preflight is read-only, separate from acquisition, and is not run
by source gates. Source tests cannot emit real-host READY. No real B2 effects are
authorized here. D/E remain post-B2, GUI source is not required pre-B2, v1 report
is unchanged, R3 remains parked and LIVE remains NO-GO.
