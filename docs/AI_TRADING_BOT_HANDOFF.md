# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Canonical repository path:** `docs/AI_TRADING_BOT_HANDOFF.md`  
**Local repository:** `F:\AI\ai-trading-bot`  
**Integration branch:** `develop`  
**Current architecture branch:** `feature/windows-effectful-market-data-capture`  
**Handoff status:** August 25, 2026 — C3-E3.4 source-certified; E3.3 fixed runtime deployed; E3.4 runtime rebuild/redeployment pending

> **Source-of-truth rule:** the Git-tracked `docs/AI_TRADING_BOT_HANDOFF.md` is the authoritative handoff. Any copy uploaded to the ChatGPT Trading Bot Project is a context mirror for easier cross-chat continuity. When the two differ, use the Git version and refresh the Project mirror from it.

---

## 1. Executive Summary

The AI Trading Bot is being developed as a **conservative, auditable automated trading platform** that progresses through increasingly effectful operating modes only after the previous mode has demonstrated deterministic behavior, recovery safety, and operational reliability.

The project is **not intended to remain a paper-trading research project**.

The long-term progression is:

**Historical research → deterministic simulation → manual paper operation → unattended paper operation → long-duration paper soak → broker-paper integration → live-readiness certification → tiny restricted live deployment → mature automated operation → polished end-user application.**

External effects—market-data acquisition, credentials, brokerage operations, and eventually real-money orders—must remain much more constrained than ordinary application logic.

Strategy code and future AI systems may propose actions, but they must never possess independent authority to bypass:

- deterministic risk controls;
- production authority;
- credential boundaries;
- brokerage/reconciliation rules;
- operating-mode controls;
- durable evidence;
- operator emergency controls.

**Production/live trading remains NO-GO.**

The current development work is C3: safely connecting the reviewed Windows production authority stack to one real Alpaca daily-snapshot capture without enabling brokerage execution or live trading.

C3 is not complete because no real provider lineage has yet produced a parent-verified selected production snapshot.

---

# 2. Ultimate Product Goal

The finished product should be a **safe, largely autonomous trading application capable of restricted real-money trading while remaining deterministic, auditable, recoverable, and operator-controllable**.

It should eventually be usable as a polished desktop-style application rather than requiring routine Python CLI commands, SQLite inspection, or manual reconstruction of state.

At full product maturity, the application should support:

- historical research and backtesting;
- multi-symbol portfolio simulation;
- strategy development and comparison;
- walk-forward testing and optimization;
- automated daily market-data acquisition;
- deterministic proposal and risk evaluation;
- simulated paper trading;
- real broker paper/sandbox operation;
- broker/account/order reconciliation;
- restricted live trading;
- monitoring, alerts, recovery, and emergency controls;
- detailed portfolio and performance analytics;
- durable audit/history inspection;
- strategy and operational configuration;
- clearly separated research, paper, broker-paper, and live modes.

The eventual GUI should expose these capabilities through the **same reviewed service and authority boundaries used by CLI, automation, and tests**.

The GUI must never become a second implementation of trading, risk, credentials, brokerage, reconciliation, or production authority.

---

# 3. Architectural North Star

The current production market-data authority chain is:

```text
ValidatedProductionAuthority
        │
        ▼
WindowsTransactionalAuthority
        │
        ▼
WindowsEffectfulDailySnapshotCapture
        │
        ▼
isolated Windows child
        │
        ▼
Windows Credential Manager
        │
        ▼
Alpaca market-data provider
```

This separation is intentional.

### C1 — `ValidatedProductionAuthority`

C1 establishes that the process is operating inside the approved production deployment boundary.

It owns or validates items such as:

- approved Trading SID;
- deployment identity;
- signed bootstrap;
- fixed production locations;
- production storage;
- output roots;
- lifecycle mutex policy;
- production configuration identity.

Possessing ordinary Python objects or filesystem paths is not enough to recreate this authority.

### C2 — `WindowsTransactionalAuthority`

C2 provides the durable transactional state machine governing external effects.

It controls:

- capture reservations;
- deterministic identities;
- durable intent;
- process-effect claims;
- resume intent;
- one-shot capabilities;
- concurrency;
- lifecycle arbitration;
- crash recovery;
- ambiguous external outcomes;
- fail-closed retry semantics.

A plain:

```python
WindowsTransactionalAuthority(authority)
```

must remain **effectfully inert**.

C2 alone must not be capable of contacting Alpaca, reading production credentials, or launching the production child.

### C3 — `WindowsEffectfulDailySnapshotCapture`

C3 is the only reviewed production bridge from C1/C2 authority into actual external market-data effects.

It introduces the controlled chain from durable authority to:

- exact provider construction;
- Credential Manager access;
- child-process creation;
- Job Object containment;
- controlled resume;
- one authorized provider attempt;
- staged snapshot creation;
- independent parent verification;
- publication and selection of the verified snapshot.

C3 authorizes **market-data capture only**.

It does not authorize brokerage operations or trading.

---

# 4. Major Foundations Already Built

A substantial amount of the platform predates the current Windows-security work.

Existing foundations include:

### Trading/domain layer

- deterministic trade proposals;
- risk evaluation;
- order lifecycle models;
- portfolio models;
- paper ledger/account state;
- deterministic fill handling;
- multi-symbol execution semantics.

### Historical market-data layer

- historical providers;
- deterministic daily snapshots;
- strict snapshot verification;
- canonical serialization;
- offline replay and verification;
- NYSE/XNYS calendar support.

### Research/backtesting layer

- single-symbol backtesting;
- multi-symbol backtesting;
- complete-frame semantics;
- next-open execution semantics;
- baseline strategies;
- historical return scenarios;
- portfolio optimization;
- experiment grids;
- experiment ranking;
- Pareto analysis;
- walk-forward evaluation;
- stability/sensitivity analysis;
- research manifests, bundles, archives, and restoration.

### Paper-operation foundations

- simulated paper account;
- deterministic paper order/fill flow;
- checkpointed account state;
- verified snapshot paper cycles;
- restart-safe paper-operation coordination;
- durable before/after evidence;
- recovery and lineage verification.

### Production Windows authority foundations

Architectures 77–81 established and implemented:

- production authority provisioning;
- fixed production storage;
- canonical transactional SQLite schema;
- production authority validation;
- `ValidatedProductionAuthority`;
- Windows lifecycle mutex/arbitration;
- one-shot effect capabilities;
- deterministic evidence;
- `WindowsTransactionalAuthority`;
- crash/recovery semantics;
- concurrency guarantees.

C2 final certification previously completed with:

```text
Combined service + Architecture-77 suite:
775 passed

Full repository suite:
2,725 passed
13 skipped
0 failed
```

The production SQL artifact remains frozen at:

```text
length: 118,896 bytes
SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
```

---

# 5. Current Development Milestone — C3 Effectful Market-Data Capture

C3 converts the previously inert production effect boundary into a real but narrowly controlled Alpaca daily-snapshot capture path.

The objective is **not simply to make an Alpaca API call work**. The objective is to prove that a real external API call can occur without weakening the authority, crash-safety, one-shot, credential, containment, deterministic-evidence, and recovery properties established by C1 and C2.

The native Windows path, production composition, manual production invocation boundary, sealed-runtime deployment procedure, and real-provider effect path have all been exercised.

## C3 checkpoint structure and current progress

### C3-A1 — Capture planning contracts — complete

Established the immutable production capture plan and deterministic bridge between the C2 capture reservation and the existing daily-snapshot subsystem.

```text
C2 reservation
→ authorized snapshot session
→ deterministic daily-snapshot request UUID
→ canonical C2 request bytes/digest
→ immutable C3 capture plan
```

### C3-A2 — Canonical child protocol — complete

Defined the strict parent/child request and result protocol. The child receives canonical, bounded, secret-free semantic input rather than trusting command-line arguments, environment variables, filenames, PIDs, or arbitrary caller objects as authority.

### C3-A3 — C1/C2/C3 composition and verified capture authority — complete

Established the production composition boundary and the rule that child success alone cannot create production snapshot authority. Only independently verified captured content may become a `VerifiedCapturedSnapshot`.

### C3-B1 — Windows Credential Manager boundary — complete

Production credential targets are fixed:

```text
AITradingBot/MarketData/Alpaca/ApiKeyId/v1
AITradingBot/MarketData/Alpaca/ApiSecretKey/v1
```

Important properties include exact target lookup only, no enumeration, no `.env`/environment/config fallback, Trading SID verification before access, bounded native buffer handling, sanitized errors, and secrets never sent to the parent.

The production Trading account remains the non-admin account:

```text
DESKTOP-I4DOKM7\Trading
SID S-1-5-21-1397534616-3988210162-180023805-1009
```

### C3-B2 — Isolated child/provider execution core — complete

The child flow is frozen around:

```text
canonical child request
→ consume one-shot attempt
→ enter C3_PROVIDER_ATTEMPT_ENTERED fence
→ reconcile request/session/release
→ verify Trading SID
→ read exact Credential Manager entries
→ construct short-lived credential scope
→ construct exact Alpaca provider
→ perform at most one provider fetch
→ deterministic snapshot acceptance
→ close credential scope
→ canonical serialization
→ child-side offline verification
→ write candidate bytes to staging output
→ flush
→ emit sanitized structured result
```

The child result remains **evidence rather than authority**.

### Native Windows containment, lifecycle, and production composition — implemented and exercised

The production path includes the reviewed suspended-process and Job Object structure, explicit inherited handles/environment, durable C2 execution/resume ordering, bounded result/process observation, cleanup evidence, parent verification, terminal recording, and selection path.

The ordering remains:

```text
CreateProcessW suspended
→ durable C2 execution / PRE_RESUME_READY
→ write exact canonical child request
→ close request writer
→ commit ResumeIntent
→ ResumeThread exact primary thread once
→ bounded child/process observation
→ cleanup evidence
→ parent verification / terminal / selection
```

`RESUME_RECORDED` is lifecycle evidence, not provider-success evidence.

Native acceptance work has also been hardened around exact child environment, inherited-handle identity, descendant containment, hostile reparse/substitution cases, and typed device rejection.

### Manual production capture boundary — implemented

A manual one-shot CLI acquires C1 authority and delegates one `ProductionCaptureRequest` through `WindowsEffectfulDailySnapshotCapture.capture_once()`. It emits sanitized operator evidence and remains fail-closed.

### E3.2 — Sanitized Alpaca transport diagnostics — complete

After the first real provider failure, the transport boundary was refined so the child could emit a closed sanitized stage rather than raw network/TLS/OS exception details:

```text
TRANSPORT_REQUEST_FAILED
TRANSPORT_RESPONSE_START_FAILED
TRANSPORT_RESPONSE_METADATA_FAILED
TRANSPORT_RESPONSE_BODY_FAILED
TRANSPORT_FAILED
HTTP_FAILED
```

This diagnostic refinement did not weaken the one-shot rule or permit retry of a consumed provider attempt.

### C3-E3.3 — Truthful sanitized transport-stage classification — source-certified and deployed

A Sol High review of the E3.2 transport boundary found that broad stage-local `except Exception` handling could incorrectly label programming defects as genuine network/transport-stage failures.

E3.3 narrowed those boundaries so known transport/protocol failures retain their existing sanitized stage, while unexpected programming defects escape the transport layer and are converted by the isolated child to sanitized `INTERNAL_FAILED` evidence.

E3.3 also made `AlpacaHttpStatusError` a sibling of `AlpacaTransportError` under `AlpacaDailySnapshotError`; the C3 child continues to map sanitized non-200 responses to `HTTP_FAILED`, and the standalone daily-snapshot CLI explicitly preserves its Architecture-57 exit-code-5 HTTP handling.

Accepted implementation commits:

```text
7fdbd185b4cae1d8392bb7473f40ad69a4fb967d
fix: preserve truthful Alpaca transport stages

bf88890d87ed1734a4634e4b8069ff5232a20994
fix: preserve Alpaca HTTP CLI handling
```

Full local source certification at `bf88890d87ed1734a4634e4b8069ff5232a20994`:

```text
pytest: 3094 passed, 16 skipped, 0 failed
Ruff check: passed
Ruff format --check over Git-tracked Python files: passed
```

#### Accepted E3.3 production artifact

The accepted frozen E3.3 wheel was built from the certified implementation checkpoint:

```text
path: F:\AI\c3-e33-production-wheelhouse-v2\ai_trading_bot-0.1.0-py3-none-any.whl
length: 672104 bytes
SHA-256: ed87fcce586a3b2f2477f2b99e6c404d7c42f5cc2ef29e230b12cd8ca7640b3b
wheel entries: 192
RECORD hashes verified: 191
```

The wheel retained the frozen production SQL at 118,896 bytes / SHA-256 `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`.

The earlier E3.3 v1 wheel is **unaccepted** and must never be deployed or reused.

#### E3.3 fixed-runtime deployment

The E3.3 wheel was deployed through the established sealed-runtime procedure into:

```text
F:\AITradingBot\runtime
```

Accepted deployment evidence included:

- exact artifact length/hash verification;
- runtime quiescence before replacement;
- Trading RX revoked before install;
- offline install with exit 0;
- installed RECORD reconciliation;
- installed E3.3 semantic diagnostics;
- production SQL hash unchanged;
- SQLite 3.50.4;
- C1 validation with exact Trading SID;
- Administrator ownership normalization;
- Administrator/SYSTEM-only sealed runtime after install;
- 12,453 runtime descendants / zero ACL anomalies;
- no Credential Manager read, network request, child launch, or provider effect during deployment.

Trading RX was then republished exactly once on the runtime root and inherited by all 12,453 descendants with zero anomalies.

The non-admin Trading E3.3 zero-network preflight also passed under its defined contract. The exact transcript is not available in this handoff, so do not invent line-by-line evidence; retain only the accepted fact that the preflight passed and performed no provider request.

### C3-E3.4 — Closed sanitized response-metadata classifications — source-certified

The August 24 E3.3 provider effect narrowed the failure to `TRANSPORT_RESPONSE_METADATA_FAILED`, but E3.3 intentionally retained only the broad metadata stage. The exact rejected metadata condition could not be reconstructed from durable evidence.

E3.4 therefore adds a closed sanitized metadata-reason set and maps it into durable child classifications without persisting raw headers, response bodies, provider/server text, credentials, arbitrary transport strings, or raw exception text.

Frozen child classifications include:

```text
TRANSPORT_RESPONSE_METADATA_ACQUISITION_FAILED
TRANSPORT_RESPONSE_METADATA_MALFORMED_FAILED
TRANSPORT_RESPONSE_METADATA_DUPLICATE_FAILED
TRANSPORT_RESPONSE_METADATA_CONTENT_ENCODING_FAILED
TRANSPORT_RESPONSE_METADATA_TRANSFER_ENCODING_FAILED
TRANSPORT_RESPONSE_METADATA_LENGTH_CONFLICT_FAILED
TRANSPORT_RESPONSE_METADATA_CONTENT_LENGTH_FAILED
TRANSPORT_RESPONSE_METADATA_REQUEST_ID_FAILED
TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_FAILED
TRANSPORT_RESPONSE_METADATA_FAILED
```

The accepted implementation commit is:

```text
134467ecda1ffbb39f48cf68a2d3e9017d1d2f61
fix: classify Alpaca response metadata failures
```

The certified working diff survived the E3.3 docs-only fast-forward byte-for-byte:

```text
SHA-256: 6d9232fef1f5dfaf8b1df329e28db20646d108a81b0e1410e2d2d9cd82cdbca6
```

Final broad source certification:

```text
pytest: 3136 passed, 16 skipped, 0 failed
Ruff check over Git-tracked Python: passed
Ruff format --check: 358 files already formatted
final git diff --check: passed
```

Sol High exact-diff review confirmed:

- metadata validation rules were not loosened;
- raw metadata/exception material does not escape;
- non-200 HTTP handling remains distinct;
- unexpected programming defects still become `INTERNAL_FAILED` at the child boundary;
- exactly one provider operation maximum remains enforced;
- no retry/fallback/provider-call-budget change;
- C1/C2 semantics unchanged;
- production SQL unchanged;
- Credential Manager unchanged;
- native process/resume/cleanup ordering unchanged;
- `windows_transactional_authority.py` changed only to extend the closed C3 child-classification allowlist.

The E3.4 source is **not yet deployed**. The fixed production runtime still contains the accepted E3.3 implementation and must be rebuilt/redeployed before another provider effect.

---

# 6. Current Acceptance Checkpoint — C3 E3 Real-Provider Acceptance

C3 is at the real-provider acceptance stage.

## Consumed August 21, 2026 lineage

The first real E3 provider attempt produced:

```text
session: 4667f0a1-8890-57b9-ae07-98ffc9633ade
attempt ordinal: 0
terminal outcome: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_FAILED
```

A second CLI invocation with the exact same deterministic request was safely blocked before attempt allocation. It created:

```text
no new attempt
no claim
no reservation
no child
no provider request
no durable mutation
```

The consumed August 21 C2 request digest is:

```text
823e9bee88de07bbd6d3384559dd6207ad216e69d46443594f8664fff49854a7
```

This lineage must never be retried.

## August 24 planning preflight and corrected clock contract

The intended August 24 request was:

```text
symbol:                SPY
request-window-start:  2026-08-24
request-window-end:    2026-08-24
target-session-date:   2026-08-25
authorized snapshot:   2026-08-24
```

The first pure planner attempt failed safely before any durable/provider effect with:

```text
WindowsEffectfulCapturePlanError:
runtime clock does not reconcile with the C2-authorized snapshot session
```

Exact source inspection established the reason: `_require_clock_reconciles()` compares the authorized session to `NYSEMarketCalendar.previous_session(requested_at_utc)`, and `previous_session()` first moves backward from the **exchange-local calendar date**. The planner therefore does not mean “latest completed market session after close.”

For a completed session date `D`, the current planner reconciles once New York's calendar date has advanced to `D + 1`.

For the August 24 request:

```text
midnight EDT Aug 25 = 9:00 PM PDT Aug 24
```

The same pure planner was rerun after that boundary and passed:

```text
REQUESTED_AT_UTC=2026-08-25T04:08:44.675052+00:00
AUTHORIZED_SESSION_DATE=2026-08-24
C2_REQUEST_SHA256=ed4cc49dc385486ac5ca623f64e99766247e371c90f29f1ff8fd585841d6b651
DIGEST_DISTINCT_FROM_AUG21=True
C3_E3_NEW_SESSION_PLAN_PREFLIGHT=PASSED
PROVIDER_CALL_PERFORMED=False
```

Treat this exchange-date behavior as the current acceptance contract. Do not change it merely to match “after close + buffer.” A semantic change would be separate clock/authority architecture work and should receive Sol High review.

## Consumed August 24, 2026 lineage

A read-only freshness guard first proved:

```text
NEW_REQUEST_EXISTING_SESSION_COUNT=0
C3_E3_NEW_REQUEST_FRESH=PASSED
PROVIDER_CALL_PERFORMED=False
```

Exactly one real provider effect was then authorized for the new August 24 lineage.

The invocation produced:

```text
session_id: c78b94a4-963f-5197-9a03-16017ea2203b
attempt_id: e1a74104-150c-5ef9-96f3-f9d6d0c8aee0
claim_id: 2fa4aa8b-b571-5051-b48b-19a658b4fe3b
reservation_id: 4d49805d-661b-53b2-a8df-ba041323da2f
execution_id: 5acd937c-35b4-5e68-87cd-afc781872176
terminal_id: b4c34eec-81d4-5dad-b01a-34d88fca05d4
terminal outcome: FAILED
provider disposition: CONFIRMED
selection: none
snapshot: none
CLI exit: 6
```

A read-only durable diagnostic then proved:

```text
SESSION_STATE=OPEN
NEXT_ATTEMPT_ORDINAL=1
ATTEMPT_STATE=TERMINAL_RECORDED
RESERVATION_STATE=TERMINAL_RECORDED
EXECUTION_PHASE=TERMINAL_RECORDED
TERMINAL_STATE=FAILED
PROVIDER_CALL_DISPOSITION=CONFIRMED
TERMINAL_EVIDENCE_DIGEST_VALID=True
TERMINAL_DIAGNOSTICS_DIGEST_VALID=True
CHILD_FENCE_STATE=ENTERED
CHILD_RESULT_CLASSIFICATION=TRANSPORT_RESPONSE_METADATA_FAILED
RESULT_TRANSPORT=COMPLETE
PROCESS_OUTCOME=EXITED_ZERO
PARENT_CLEANUP=COMPLETE
ARTIFACT_VERIFICATION=NOT_ATTEMPTED
STAGING_CLEANUP=COMPLETE
TERMINAL_REASON=POST_FENCE_CHILD_FAILURE
DATABASE_OPEN_MODE=READ_ONLY
```

The August 24 lineage is consumed and must never be retried.

Actual real Alpaca provider-effect count is now exactly **2**:

```text
Aug 21: FAILED / CONFIRMED / TRANSPORT_FAILED
Aug 24: FAILED / CONFIRMED / TRANSPORT_RESPONSE_METADATA_FAILED
```

No real provider effect has occurred during E3.4 implementation, testing, review, certification, commit, push, or documentation closeout.

## Correct continuation

Provider call #3 is **not authorized**.

Before another real effect can be considered:

```text
E3.4 implementation commit 134467ec...
→ build new fixed-runtime wheel from that exact implementation checkpoint
→ inspect source binding / exact files / SQL / wheel RECORD / hash / byte length
→ confirm E3.4 closed metadata classifications in the artifact
→ revoke Trading RX
→ replace sealed production runtime offline
→ verify installed E3.4 semantics with zero network/credential/child effect
→ normalize/seal ACLs
→ republish exact Trading RX
→ non-admin Trading zero-provider preflight
→ wait for a genuinely new completed XNYS session
→ wait until the New York calendar date advances to the following day
→ pure planning preflight
→ verify fresh digest and no durable existing session
→ only after explicit review decide whether to authorize exactly one provider effect
```

Never manufacture a fresh digest by changing irrelevant fields. Never automatically retry a `CONFIRMED` or `MAY_HAVE_OCCURRED` lineage.

---

# 7. Pending C3 Work and Deep-Review Priorities

The primary remaining C3 gate is successful real-provider acceptance through the complete production path:

```text
validated production authority
+ transactional authority
+ exact Credential Manager boundary
+ native isolated child
+ one Alpaca fetch
+ staged candidate
+ parent verification
+ controlled publication
+ terminal/selection evidence
```

C3 still does **not** authorize unattended scheduling, brokerage execution, or live trading.

## Completed deep-review findings

The first Sol High recovery/crash-window review found no unsafe automatic retry path. It identified two follow-up architecture concerns before unattended operation:

1. **Operator diagnosis/recovery routing is too opaque.** The production CLI fails closed but collapses many safe recovery states into a generic block; a future diagnostic/classification interface should be read-only, derived from durable C2/C3 state, sanitized, and incapable of granting retry authority.
2. **Some proven pre-effect/safe-continuation states are not directly resumable through the one-shot facade.** Any continuation design must distinguish exact proven-safe durable reuse from a retry of a consumed `CONFIRMED` lineage.

The Alpaca HTTP interoperability/security review led to E3.3 and E3.4:

- E3.3 separated expected transport failures from unexpected programming defects.
- E3.4 adds precise closed metadata-failure classifications without loosening metadata validation or exposing raw provider material.

Additional deep reviews before unattended operation remain:

- production `close()` and concurrent admission/drain behavior;
- secret lifetime from Credential Manager through transport construction/use/cleanup;
- artifact verification/publication TOCTOU;
- transactional SQL invariant/mutation testing;
- clock/calendar authority for unattended scheduling;
- selected-snapshot → paper-operation bridge.

A future read-only durable inspection/classification interface remains a candidate, but it must never itself grant retry authority.

---

# 8. Roadmap After C3

| Phase | Objective | Exit condition |
|---|---|---|
| **C3 — Effectful market-data capture** | Safely obtain one real verified Alpaca daily snapshot through C1/C2-controlled Windows isolation | Real-provider capture, independent verification, containment, durable terminal/selection evidence, recovery/acceptance gates, and final certification pass |
| **Reliable manual paper cycle** | Connect selected verified production snapshot → strategy → proposal → deterministic risk → paper execution → durable result | One operator-invoked cycle completes without hidden/manual state repair |
| **Unattended paper operation** | Safely run the paper cycle without a person driving each session | Scheduling, startup reconciliation, recovery, health status, alerts, and stale-data handling are proven |
| **Long paper soak** | Operate unattended long enough to expose real operational problems | Extended clean operation with successful recovery from expected failures |
| **Broker-paper integration** | Replace simulated execution with a real brokerage sandbox/paper API | Orders, fills, cancels, rejects, partial fills, IDs, reconciliation, and ambiguous-submit recovery work |
| **Live-readiness certification** | Build every control required before real money is permitted | Account verification, live credentials, operating-mode authority, strict limits, kill switch, outage handling, and reconciliation are accepted |
| **Tiny restricted live** | Begin deliberately small real-money operation | Stable long-only execution under extremely conservative exposure and frequency limits |
| **Mature operations** | Expand reliability and operational capability | Proven monitoring, reconciliation, incident recovery, evidence, and safe automation |
| **Deepen strategies / AI** | Add more sophisticated models after operational safety is established | New intelligence remains subordinate to deterministic authority and risk |
| **Final polished GUI** | Turn the reviewed system into a user-friendly product | Full research, operational, audit, risk, and trading workflows available through the shared service boundaries |

---

# 9. Reliable Manual Paper Cycle

Once C3 is certified, the next major product-level goal is to join already-existing components into one trustworthy manual production-style paper cycle:

```text
selected parent-verified market snapshot
→ strategy
→ proposals
→ deterministic risk
→ paper execution
→ portfolio/ledger transition
→ durable evidence
→ human-readable report
```

A key architecture review comes first: prove that the paper engine consumes **only the selected, parent-verified C3 snapshot**, never a caller-selected path or merely child-produced file.

The bridge should also freeze exactly-once paper-cycle identity and restart behavior before automation.

The operational requirement is:

> An operator must be able to run the entire cycle and verify its result without repairing hidden application state manually.

---

# 10. Unattended Paper Operation

After the manual cycle is reliable, automation may be introduced.

Required capabilities include:

- authoritative XNYS-session scheduling;
- Windows Task Scheduler or reviewed service integration;
- startup reconciliation;
- restart/crash recovery;
- durable run state;
- health monitoring;
- notifications/alerts;
- stale-data rejection;
- missing-data rejection;
- fail-closed behavior when required dependencies are unavailable.

Clock/calendar authority must be explicitly designed before unattended capture is enabled, including exchange close, post-close delay, DST, holidays, early closes, machine sleep/resume, and clock jumps.

Automation must call the same reviewed runtime interfaces rather than introducing alternate execution paths.

---

# 11. Long Paper Soak

The unattended system should operate long enough to expose problems involving:

- scheduling;
- market holidays;
- machine reboots;
- process crashes;
- stale market data;
- provider outages;
- partial state;
- duplicate execution attempts;
- storage problems;
- reconciliation;
- long-running operational assumptions.

This stage is intended to discover failures while the consequences are still simulated.

---

# 12. Broker-Paper Integration

Only after unattended paper operation demonstrates reliability should a real brokerage transport be added.

The first brokerage integration remains **paper/sandbox only**.

Required functionality includes:

```text
account reads
position reads
order submission
order cancellation
order replacement
broker order IDs
fill IDs
partial fills
rejections
durable reconciliation
idempotency
ambiguous-submit recovery
startup reconciliation
```

The brokerage adapter must remain downstream of:

```text
strategy
→ proposal
→ deterministic risk
→ operating-mode authority
→ brokerage boundary
```

A brokerage adapter must never become an alternate route around application risk or authority.

---

# 13. Live-Readiness Gate

Real-money trading must remain impossible until a dedicated live-readiness milestone is reviewed and accepted.

At minimum this milestone requires:

- explicit operating-mode authority;
- separately controlled live credentials;
- exact brokerage-account verification;
- startup brokerage reconciliation;
- strict maximum exposure;
- strict maximum order sizes;
- strict trading-frequency limits;
- restricted symbols/universe;
- kill switch/emergency stop;
- stale-data handling;
- market-halt handling;
- provider-outage handling;
- brokerage-outage handling;
- ambiguous-submit recovery;
- operator-visible health;
- operator-visible reconciliation state;
- documented recovery procedures.

Passing unit tests alone is not sufficient evidence for this gate.

---

# 14. Tiny Restricted Live Deployment

Initial live trading should deliberately be unambitious.

Expected characteristics include:

```text
long-only
small capital
small order sizes
small approved symbol universe
low trading frequency
explicit live-mode enablement
strict deterministic limits
fail closed on uncertainty
```

The purpose of the first live deployment is to validate operational behavior against a real brokerage account, not maximize returns.

Limits can be relaxed only after evidence supports doing so.

---

# 15. Mature Operations and AI Expansion

More sophisticated strategies and AI should be expanded **after**, not before, the operational platform is trustworthy.

AI may eventually assist with:

- feature research;
- strategy discovery;
- market regime analysis;
- parameter exploration;
- signal generation;
- proposal generation;
- portfolio research;
- anomaly detection;
- operator explanation.

AI must never receive independent authority to:

```text
bypass deterministic risk
bypass production authority
choose alternate credentials
select arbitrary brokerage accounts
ignore reconciliation
disable operating-mode controls
place unrestricted orders
override emergency controls
```

The correct relationship is:

```text
AI / strategy
    │
    ▼
proposal
    │
    ▼
deterministic validation and risk
    │
    ▼
reviewed production authority
    │
    ▼
reviewed brokerage boundary
```

---

# 16. Stable Initial Product Constraints

Unless a future architecture milestone explicitly changes them, the conservative production target remains:

- US stocks and ETFs;
- long-only;
- no margin;
- no leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability of decisions and transactions.

---

# 17. Final GUI Milestone

The final user-facing product should no longer require routine command-line or database interaction.

The GUI should eventually expose:

### Portfolio

- portfolio value;
- cash;
- positions;
- allocation;
- realized/unrealized P&L;
- exposure.

### Market/system state

- current market/session status;
- provider state;
- last verified snapshot;
- scheduler status;
- capture status;
- brokerage status;
- system-health status.

### Research

- strategy selection;
- strategy parameters;
- backtests;
- walk-forward runs;
- optimization;
- experiment comparison;
- charts and analytics.

### Trading operations

- proposals;
- risk decisions;
- orders;
- fills;
- rejects;
- partial fills;
- positions;
- reconciliation.

### Auditability

A user should be able to trace:

```text
market data
→ strategy input
→ proposal
→ risk decision
→ order
→ brokerage result
→ fill
→ portfolio transition
```

### Operations and recovery

The GUI should provide:

- human-readable errors;
- recovery instructions;
- durable run history;
- reconciliation state;
- emergency controls;
- explicit operating-mode indicators;
- future live-account identity;
- future live limits;
- kill switch state.

The GUI remains a **presentation/operator-control layer**.

Core functionality must remain testable and usable independently of it.

---

# 18. Safety and Architecture Invariants

The following rules should be preserved unless a new architecture document explicitly supersedes them.

### External effects require authority

Ordinary application objects must not gain production effect authority merely because they know a path, provider, credential name, PID, filename, or digest.

### Durable state outranks process-local state

Crash/restart behavior must derive from durable evidence rather than reconstructing authority from PIDs, files, or assumptions.

### Ambiguous external effects fail closed

If the application cannot prove whether an irreversible/one-shot external effect happened, it must assume it may have happened rather than retrying optimistically.

### Secrets stay narrow

Production Alpaca credentials belong only inside the isolated child credential boundary.

The parent remains secret-free.

### Child evidence is untrusted

A child claiming success does not make its artifact authoritative.

The parent independently verifies the captured bytes.

### No hidden alternate production paths

No debug adapter, test injection point, environment variable, arbitrary callback, alternate provider, or convenience CLI may accidentally provide a second route into production effects.

### Deterministic risk remains mandatory

Neither strategies, AI, GUI actions, schedulers, nor brokerage adapters may bypass risk approval.

---

# 19. Development and AI/Codex Workflow

Use ChatGPT/Sol primarily for:

- architecture;
- debugging strategy;
- authority/security reasoning;
- GitHub/diff review;
- test-gate decisions;
- merge-readiness decisions;
- milestone planning.

Delegate bounded implementation to Codex when appropriate.

Preferred implementation-model selection:

```text
Localized/mechanical/frozen-contract change
→ Luna Extra High

Subtle but bounded implementation
→ Sol Medium

Native Windows/security/authority/order/crash/recovery
or architecture-changing implementation
→ Sol High
```

Do not use subagents unless explicitly requested.

For Codex implementation work:

1. Point Codex to `AGENTS.md` and the relevant architecture documents instead of restating the repository.
2. Keep the implementation scope tightly bounded.
3. Have Codex run focused tests/checks related to its changes.
4. Do not repeatedly run the entire repository suite during iteration.
5. Have Codex report the exact commands required for final local verification.
6. Run broad/full verification as the final certification step unless the change is broad enough to require earlier full validation.
7. If the user's full-suite verification exposes a failure, diagnose/fix it and rerun only the affected focused tests before asking for full verification again.

For the current fixed-runtime release/deployment sequence, prefer the proven directly supervised PowerShell procedure. Do not introduce Codex for wheel build/inspection, ACL publication, runtime replacement, or preflight unless an implementation defect is discovered.

Preserve unrelated generated/untracked reports.

### Automatic checkpoint documentation closeout

After **every completed and accepted development checkpoint**, documentation closeout is part of the checkpoint itself rather than an optional follow-up. ChatGPT should perform this closeout automatically without waiting for a separate reminder.

The authoritative documentation pair is:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

Before treating a checkpoint as closed or moving to the next checkpoint:

1. Update this Git-tracked handoff with the newly completed checkpoint, material architecture or workflow changes, verification/certification evidence, the active branch and latest implementation checkpoint when known, and the next recommended checkpoint. Do not try to embed the handoff commit's own SHA as a self-referential “current HEAD”; verify live branch HEAD when resuming.
2. Update `docs/PROJECT_STATUS.md` so its current/completed milestone state and roadmap accurately reflect the repository after the checkpoint.
3. Review both Git documents even when the checkpoint is small. If no material wording change is required in one of them, explicitly record in the checkpoint report that it was reviewed and remains current.
4. Treat the Git pair as the source of truth. A handoff file uploaded to the ChatGPT Trading Bot Project is a **context mirror**, not an independent canonical copy.
5. After a material checkpoint, refresh the ChatGPT Project mirror from the canonical Git handoff when the product/tooling permits it. If direct Project-file replacement is unavailable, provide/export the current canonical Markdown for manual replacement; do not let the mirror override newer Git state.
6. Keep detailed architecture documents historical and subsystem-specific; do not rewrite prior decisions merely to make them appear current.
7. Treat these documentation updates/reviews as a **checkpoint completion gate**: a checkpoint is not fully closed until both Git documents have been brought current or explicitly confirmed current. The Project mirror may lag temporarily without changing the repository source of truth, but its staleness should be called out when relevant to a new-chat handoff.

This is a standing authorization for the narrowly scoped documentation edits/commits needed to keep these two Git project-status documents current at checkpoint closeout. It does **not** authorize merging, rebasing, force-pushing, amending unrelated commits, resolving review threads, changing PR metadata, or modifying unrelated files.

Without explicit approval, do not:

- merge;
- rebase;
- force-push;
- amend commits;
- resolve review threads;
- change PR metadata;
- modify unrelated files.

---

# 20. Current Resume Point

Current development branch:

```text
feature/windows-effectful-market-data-capture
```

Latest accepted implementation checkpoint before documentation closeout:

```text
134467ecda1ffbb39f48cf68a2d3e9017d1d2f61
fix: classify Alpaca response metadata failures
```

Important preceding implementation checkpoints:

```text
bf88890d87ed1734a4634e4b8069ff5232a20994
fix: preserve Alpaca HTTP CLI handling

7fdbd185b4cae1d8392bb7473f40ad69a4fb967d
fix: preserve truthful Alpaca transport stages
```

Because every documentation closeout creates newer commits, **do not treat an implementation SHA written inside this document as the live branch HEAD**. Verify local/remote HEAD when resuming. For the next fixed-runtime wheel, use the exact E3.4 implementation checkpoint above unless a later reviewed implementation commit supersedes it.

### Current operational state

- Native Windows containment and production composition are implemented and have real acceptance coverage.
- A manual one-shot production capture command exists.
- E3.3 fixed-runtime wheel `ed87fcce...640b3b` was built, inspected, and successfully deployed.
- Trading RX was republished with zero ACL anomalies.
- Non-admin Trading E3.3 zero-provider preflight passed.
- August 21 real provider lineage: `FAILED / CONFIRMED / TRANSPORT_FAILED`, consumed.
- August 24 real provider lineage: `FAILED / CONFIRMED / TRANSPORT_RESPONSE_METADATA_FAILED`, consumed.
- August 24 durable diagnostic proved entered provider fence, clean child exit, complete result transport/cleanup, no artifact authority, and valid evidence hashes.
- Actual real-provider effect count is exactly **2**.
- No verified production market-data snapshot has yet been selected from E3.
- C3-E3.4 closed metadata classification is source-certified at `134467ec...`: 3,136 passed, 16 skipped; Ruff check/format and final diff check passed.
- E3.4 is not yet deployed; fixed runtime currently contains E3.3.
- Current planner clock rule is exchange-date based: session `D` reconciles only after New York's calendar date advances to `D + 1`.
- Provider call #3 is **not authorized**.
- Production/live trading remains **NO-GO**.

Relevant architecture/status material to read when resuming:

```text
AGENTS.md
docs/PROJECT_STATUS.md
docs/architecture/57-alpaca-daily-snapshot-capture.md
docs/architecture/77-windows-transactional-capture-authority.md
docs/architecture/80-windows-production-authority-capability.md
docs/architecture/81-windows-production-transactional-authority-service.md
docs/architecture/82-windows-production-effectful-market-data-capture.md
docs/architecture/83-c3-isolated-child-provider-execution.md
```

Also review the latest validation evidence and the two consumed E3 lineages before authorizing another provider effect.

---

# 21. Recommended Next Development Sequence

Resume from the **E3.4-certified source / E3.3-deployed fixed runtime** state.

Recommended sequence:

```text
NOW
build a new fixed-runtime wheel from exact implementation commit
134467ecda1ffbb39f48cf68a2d3e9017d1d2f61

→ inspect exact wheel contents + source binding + SHA-256 + byte length

→ verify production SQL remains frozen

→ verify all E3.4 metadata classifications and HTTP hierarchy in the wheel

→ redeploy through the established sealed-runtime procedure
(no provider effect)

→ temporarily revoke Trading RX during install

→ verify installed E3.4 semantics
(no network / credential read / production child)

→ normalize/seal runtime ACLs

→ republish exact Trading RX

→ non-admin Trading zero-provider preflight

→ wait for a genuinely new completed XNYS session

→ wait until New York's calendar date advances to the following day

→ pure planning preflight
(no provider effect)

→ verify authorized session + fresh C2 request digest
+ no existing durable session for that digest

→ only after review, explicitly decide whether to authorize
exactly one provider effect

→ if successful
parent verification / publication / selection evidence
remaining C3 acceptance closeout
C3 final certification
checkpoint documentation closeout

→ if failed
record exact E3.4 closed classification + durable disposition
do not retry a consumed CONFIRMED/MAY_HAVE_OCCURRED lineage
diagnose/fix only the proven failure class
use a genuinely new eligible session for any later real effect

→ after C3 certification
selected verified snapshot → reliable manual paper-cycle bridge
```

Before unattended operation, continue the remaining deep reviews for production close/admission, secret lifetime, artifact TOCTOU, SQL invariant mutation tests, and clock/calendar authority.

The first product-level architecture review after successful C3 acceptance should be the **selected-snapshot → paper-operation bridge**, including exactly-once paper-cycle identity and restart behavior.

Unattended scheduling remains later and should not be introduced until manual production-style paper operation and its recovery semantics are trustworthy.

Any change involving native Windows process authority, credential lifetime, external-effect ordering, crash/recovery ambiguity, publication/selection authority, retry semantics, or planner clock semantics should continue to receive **Sol High** architecture review. Localized changes under an already-frozen contract may be delegated according to the standing Luna/Sol model-selection rules.

---

# 22. Definition of Project Success

The project is not complete merely when it can place trades.

It is complete when the system can:

1. research strategies deterministically;
2. prove historical results reproducibly;
3. acquire trusted market data safely;
4. make portfolio decisions;
5. apply deterministic risk;
6. interact safely with a real brokerage;
7. reconcile external outcomes after failures or restarts;
8. run unattended for long periods;
9. fail closed when authority or state is uncertain;
10. expose complete durable evidence;
11. operate under strict real-money controls;
12. recover predictably from realistic failures;
13. allow an operator to understand and stop it;
14. expose all of this through a polished, user-friendly application;
15. evolve toward more sophisticated AI without weakening any of the above guarantees.

The final system should therefore be viewed not simply as an **AI strategy that happens to place trades**, but as a **safety-oriented automated trading platform in which AI is one replaceable decision-making component inside a deterministic operational and authority framework**.

That architecture is the primary long-term objective of the project.
