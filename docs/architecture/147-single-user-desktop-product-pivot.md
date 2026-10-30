# Architecture 147 — Single-user desktop product pivot

Status: CURRENT product roadmap; P1 accepted/integrated, P2 source bridge.

## Product contract

The product is a private, single-user Windows desktop trading bot. The trusted
machine owner, Administrator, SYSTEM, and physical owner are outside the
application threat boundary, as reaffirmed by Architecture 102. Production
quality for this product means correct deterministic decisions, reconciliation,
duplicate-effect protection, safe restart behavior, stale-data rejection,
credential isolation, paper/live separation, explicit live arming, limits,
audit, health, kill-switch, backup, recovery, and reliable long-running
operation. It does not require hostile-Administrator namespace ceremony.

The user explicitly starts and stops the application. After Start, trading and
research workers may run unattended until Stop. The application never updates
its own source or executable tree. The manual update sequence is:

    user Start -> workers run unattended -> user Stop -> reconcile/close
      -> manual update while stopped -> checks/migration -> user Start

An approved checkout or simple versioned directory may be used for a stopped
manual update. No STAGE->ACTIVE, ACTIVE->ARCHIVE, rename/promotion, junction
swap, scheduler rebind, or immutable-release publisher is a current product
prerequisite. Task Scheduler/start-at-login may be added later as convenience.
State and credentials remain outside disposable source files.

The bot owns strategy decisions, research, portfolio targets, deterministic
`RiskManager` decisions, exact order intent, operating mode, live arming, local
limits, reconciliation, audit, and the kill switch. Robinhood's official MCP /
Agentic Trading surface is the future brokerage transport and execution
boundary. It is not strategy authority and may not bypass local risk or choose
a different order. P1 enables no real mutation, OAuth, account query, order
review, order placement, paper effect, broker effect, or live effect.

## Roadmap

    P1  desktop research simplification
    P2  one real SPY acquisition + verification + freeze
    P3  real optimizer / walk-forward campaign + Research Results GUI
    P4  long-running desktop supervisor with concurrent trading + research workers and GUI Start/Stop
    P5  unattended synthetic/forward paper soak using existing Robinhood MCP review/quotes/history/account foundations
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production maturity / soak / monitoring / backup / restart / reconnect / credential rotation

Trading and research may operate concurrently after P2. Paper trading remains
the default and LIVE remains disabled until separately reviewed gates are met.
The existing Research Results GUI is reused and audited in P3; GUI rebuild is
not a P1 blocker.

## P1 desktop research profile

P1 keeps the Architecture 146-A deterministic dataset contracts and identities:

- `HistoricalResearchPartitionManifest`;
- `HistoricalResearchDatasetSnapshot`;
- `HistoricalResearchPartitionRole`;
- normalized CSV canonicalization and full historical fingerprint semantics;
- `SPY`, `XNYS`, `1Day`, `RAW`, `SIP`, `USD`, `PRICE_RETURN`;
- the existing partition boundary at `2024-01-01`;
- published session authority `nyse-published-regular-sessions-2016-2026-v1`;
- 2718 sessions, digest
  `7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1`.

Those values are not repinned because storage changes. The model's two extra
closures, 2018-12-05 and 2025-01-09, remain part of the existing historical
authority reconciliation.

The source-owned fixed production root is:

    F:\AI\ai-trading-bot\data\research\desktop-v1

Its conceptual layout is explicit and ordinary:

    desktop-v1/
      raw/bars/
      raw/corporate-actions/
      normalized/open/SPY.csv
      normalized/holdout/SPY.csv
      corporate-actions/sidecar.json
      manifests/open.json
      manifests/holdout.json
      manifests/snapshot.json
      acquisition.json

Tests inject a temporary root only through the explicit test seam. The desktop
profile creates directories/files normally, rejects arbitrary production-root
substitution, refuses to overwrite completed files, writes and fsyncs bytes
where practical, validates readback/digests and manifest membership, and keeps
incomplete or partial acquisition state visible. It performs no automatic
destructive cleanup. It has no ACL, SID, SDDL, token, elevation, `ctypes`,
`Set-Acl`, ownership, alternate-principal, protected-parent, claim-ceremony,
rename/promotion, or junction/symlink-publication dependency.

The shared acquisition kernel now receives a small profile-owned persistence
adapter. The current desktop adapter owns ordinary inspection and verification;
the preserved protected `CustodyInspection`/`CustodyPersistencePlan` remains a
separate legacy/deferred adapter. The desktop adapter never reports
Administrator/SYSTEM custody under new names and does not weaken or retry the
old protected path.

## Research data boundaries

The current OPEN loader reads only normalized OPEN bytes plus the required
non-price manifests and corporate-action sidecar. It validates exact bytes,
size, hashes, canonical CSV, snapshot/manifest membership, and the accepted
published session authority. It does not read normalized FINAL_HOLDOUT bytes,
raw full-range vendor pages, or require `ACCEPTED_CUSTODY_ADMISSIONS` or a
protected-host report.

The explicit final-holdout loader is a separate boundary. It requires the exact
existing Architecture-145 `ResearchStrategyFinalHoldoutAdmission` type and
validates its policy, dataset, and partition binding against the desktop
snapshot before returning the FINAL_HOLDOUT data. It revalidates the complete
OPEN + FINAL_HOLDOUT physical dataset and frozen fingerprint commitments. The
ordinary optimizer, walk-forward, and candidate-selection modules do not import
or call this loader. This is a software-use boundary, not a claim that the
trusted machine owner cannot inspect files.

P2 uses fake transport/credentials in tests. Its source bridge and integrity
inspection are described below; the one real acquisition follows source
acceptance/integration and is never executed by implementation, admission or CI.

## P2 desktop interactive acquisition bridge

P1 is accepted/integrated at `e8817e0214074b03d3d9ecd73232b7a2379276b9`:
feature #807 canonical FULL and develop #808 succeeded; develop reused the
exact feature certification. Failed #806 remains immutable and was not rerun.

`scripts/acquire_desktop_research.py` requires `--execute`, `--expected-head`
and `--expected-tree`. No request/root/partition override exists. Before any
write or prompt it verifies the canonical project root, develop branch, exact
reviewed HEAD/tree, `git status --porcelain=v1 --untracked-files=no`, canonical
origin URL, and local origin/develop equality. It then verifies the accepted
published authority and requires the fixed desktop root absent. Ordinary
exclusive root creation and `DesktopResearchStorage` preparation precede input.

`DesktopInteractiveResearchCredentialSource` is one-use, binds exact expected
HEAD/tree and accepted authority through the shared kernel's bind hook, and
uses only the reviewed `interactive_research_credentials()` hidden prompts.
It has no persistence, environment/config/file fallback, token/SID/elevation
observer or Credential Manager requirement. The historical
`EphemeralHistoricalResearchCredentialSource` and `AcceptedB2Preflight` remain
unchanged and are not used by this path.

The shared `HistoricalResearchAcquisitionOperator` and existing
`HttpsHistoricalResearchTransport` own the frozen requests, pagination,
normalization and deterministic identities. Alpaca historical Market Data is
the research-data source only; Robinhood MCP / Agentic Trading remains the
future brokerage execution/account boundary. No brokerage/order adapter is
introduced. Requests remain SPY, 1Day, 2016-01-01T00:00:00Z through
2026-10-24T00:00:00Z, raw/SIP/USD/ascending/10000 bars and the existing full-range
US complete corporate-actions request with ascending/1000 pagination.

After acquisition the bridge saves the kernel evidence as `evidence.json`.
`inspect_desktop_dataset_integrity()` verifies COMPLETE, reconstructs canonical
evidence, manifests and snapshot, reads OPEN/FINAL_HOLDOUT physical bytes and
bars raw digest vector, checks corporate raw pages against the original sidecar
and commitments, and invokes `verify_desktop_published_dataset()` against the
accepted 2718-session authority and full fingerprint. It returns an immutable
summary of profile, source/attempt/dataset/manifest/authority identities,
row counts/endpoints and SHA256 values, never OHLCV or bars. This read-only
inspection is not strategy holdout admission. Normal research continues through
`load_desktop_open_research()`; strategy FINAL_HOLDOUT access still requires
`ResearchStrategyFinalHoldoutAdmission`.

Success prints compact sanitized JSON including both integrity and OPEN-loader
PASS. Failure prints only stage/classification, never exception text, response
bodies, credentials or lengths. Authentication/entitlement, rate-limit, server,
transport, response-shape, pagination/replay, validation, persistence,
preexisting destination and source mismatch failures remain distinct. No retry
or SIP fallback occurs. Any existing root, including partial/empty state, stops
a later invocation; recovery is deferred to a later reviewed action.

After P2 source acceptance/integration and develop verification, automatically
provide the single reviewed real acquisition command pinned to that HEAD/tree.
No Architecture-146 B2 or observer gate intervenes. Review sanitized evidence
after the user-run acquisition and continue to P3 optimizer/walk-forward work
if integrity passes.

## Deferred Architecture 146 and high-assurance machinery

Architecture 125 rename machinery, Architecture 128 protected redeployment,
Architecture 133 publication/scheduler/install experiments, the Architecture
134 successor-host/release/ACL chain, protected immutable-release publication,
Architecture 146 Administrator/SYSTEM research custody, cross-principal
custody, protected parent provisioning, OPEN-parent ceremony, privileged
observers, and protected attempt claims are LEGACY/DEFERRED. Their source,
tests, and immutable evidence are preserved where they certify historical
behavior; they are not current readiness gates or next actions.

The consumed Architecture 146 observation is preserved exactly at:

    F:\AI\temp\ai-trading-bot-checkpoints\operator-b957c4f6bec54413887316ab17929207\arch146-b-partial-state-readonly-observer\preflight-20261030T053329.017181Z\report.json

It recorded `IDENTITY_STABLE=True`, `OVERALL=BLOCKED`,
`classification=HOST_UNKNOWN`, `stable_repetitions=2`, zero operational
counters, `acquisition_authorized=false`,
`open_parent_creation_authorized=false`, and
`protected_execution=NOT_AUTHORIZED`. It is consumed evidence. There is no
retry, repair, or current observer dispatch.

## Current checkpoint

The registered source checkpoint is `arch147-desktop-research-profile` on
`feature/research-desktop-product-pivot-current`, with `preflight=None`,
`execute=None`, and GitHub-owned canonical FULL. The normal development route
is focused implementation -> focused tests -> one atomic candidate -> FEATURE +
PROSPECTIVE_DEVELOP admission -> one push -> one CI -> exact review ->
fast-forward `develop`. Source PASS grants no provider or live effect.
