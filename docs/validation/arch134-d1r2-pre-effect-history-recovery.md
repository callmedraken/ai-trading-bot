# Architecture 134-D1R2 — Same-session pre-effect history recovery

Status: SOURCE ACCEPTED. Exact executable/test source:
`114608d220ab6653fcb48fc0002b6ae9497f90c9` / `b57cecd27865bda88ec104748fef55c0dcb54f34`, parent `cbcc1addfb392ca87939df0f77fe9dde10685abf`.
Terminal mapped CI #514 / 38370765607 succeeded; canonical ROBINHOOD covered
94 modules / 8,814 cases with 8,813 passed, one skipped and zero failures/errors
in 262.431 seconds. No production effect or actual recovery ran.

## Authority and identity

Normal `--arm` and explicit `--recover-history` are mutually exclusive. Recovery
requires `AUTHORIZE_ARCH134_D1R2_ONE_PRE_EFFECT_HISTORY_RECOVERY` and an explicit
predecessor execution-evidence destination, which must be absent and external.
It never reserves, deletes, reclaims or expires the existing session fence.
The same `armed_session_v1` table and `armed-paper-session/v1:SPY:<date>` key
remain. No schema/database/provisioning change is required.

The canonical `armed-paper-session/v2` BLOB adds exactly strategy_contract,
history_failure, recovery_count, recovery_reason, predecessor_evidence and
predecessor_sha256 to the retained v1 fields. New normal sessions have count zero
and null recovery lineage. A recovery has count exactly one, the entire canonical
count-zero predecessor, its SHA256, a closed reason and the current executing
source/contract. Embedded contract bytes are parsed by the strict existing
ProductionStrategyContract parser and must match current source/date/contract ID.
The predecessor contract is independently reconstructed with the same symbol,
configuration and date. Its original contract ID and original D1 UUID5 operation
ID must match. The executing contract may differ because source identity differs;
the operation ID remains the predecessor downstream idempotency/order identity.

The original predecessor retains its source HEAD/tree and any history diagnostic.
Attempt read counts belong to each lineage node, rather than fabricating a
cumulative failure ordinal. Whole evidence remains canonical compact UTF-8 JSON
with one trailing newline and the existing 32 KiB bound. Unknown/missing fields,
noncanonical bytes, invalid types, recursive recovery, changed digest, source,
contract, operation, session/history or reason are rejected. V1 remains readable
unchanged; it has no RECOVERY_STARTED state. Arbitrary v1 rows are not migrated.

## Closed eligibility

Before CAS, durable BLOCKED evidence must independently retain exact integer zero
for strategy, PREPARE, EXECUTE, all four Robinhood calls, paper mutation and broker
placement counters; all strategy/PREPARE/EXECUTE/proposal/order/fill results must
be null. No accepted snapshots/seed, execution evidence or matching operation or
symbol/session paper fill may exist. The predecessor history list must match the
successor's exact required completed NYSE sessions. Unknown or nonzero facts block.

Only one legacy v1 tuple is admitted: target 2026-10-13; source
`6bf8753b0cc8950ae27b32b6858b64d454c512f0` /
`ce3feb2ac48e7aebc23970142aafed5059c447e7`; contract
`d490a15f-2c6e-5a1c-af36-e5f233760a7b`; operation
`8e8c5102-8b52-5534-8288-b3261f65b2d4`; ordered history October 7, 8, 9, 12;
one Alpaca read; no snapshots/seed; zero downstream counters/null results;
effect_counts_complete=false; null waiting/admission observations; the fixed
five-minute October-13 admission bounds 13:35..19:55 UTC. Its reason is
FROZEN_OCTOBER_13_PRE_D1R1. There is no fabricated D1R1 failure classification.
Incomplete counts refer to the read-only history boundary and never establish
trading-effect retry authority. Every frozen mismatch blocks.

Future count-zero v2 failures embed the existing strictly parsed, sanitized
fourteen-field history diagnostic durably before any external export. The
diagnostic must bind exact source/contract/operation/date/read count and history
ordinal. TRANSPORT_FAILED may recover except RESPONSE_METADATA, whose strict
metadata rejection is treated conservatively as deterministic validation.
HTTP_FAILED may recover only for 429 or 500..599. All construction, response,
capture, acceptance, verification, history-seed, INTERNAL_FAILED, unknown and
unclassified failures block. External D1R1 diagnostics do not silently upgrade
other historical v1 reservations into recovery authority.

## Ordering and bounds

Read canonical predecessor -> validate exact zero effects and absence of
execution/fill -> validate source and current target session -> atomically CAS
the exact predecessor bytes to v2 RECOVERY_STARTED/count one -> construct Alpaca
provider -> unchanged history acquisition -> unchanged strategy/PREPARE/EXECUTE.
SQLite synchronous=FULL and exact-byte UPDATE remain the durable fence. A
concurrent stale read, lock/CAS conflict or crash after CAS cannot authorize a
second reacquisition. There is no retry loop, polling, lease or compensation.
Failed recovery durably publishes BLOCKED before fallible diagnostic/session
exports; failed publication leaves the consumed fence. A second recovery blocks.

Source/live-origin admission remains unchanged. Existing market admission applies
on the same target NYSE date, including pre-open waiting and closing buffer; no
24-hour/day wait is introduced. Expired admission returns SESSION_EXPIRED without
provider access or rewriting the predecessor. Successful history enters the sole
existing decision path with one strategy evaluation, at most one quote-only
PREPARE and one synthetic-paper EXECUTE under the original operation ID. Broker
placement remains permanently zero. Downstream failure/ambiguity is no-retry.

## Verification and next boundary

Fake-only tests extend the existing four affected modules; no inventory module
or ACTIVE checkpoint is added. Frozen armed/R1/R2 and D1R1 authority dictionaries
remain intact. Narrow D1R2 overlays own the three changed armed sources and
directly changed tests. `arch134-production-paper-runtime` maps to the recovery
branch and canonical robinhood; the split workflow and feature/robinhood-* first
push admission remain unchanged.

Focused tests use -B, -p no:cacheprovider and fresh external
`F:\AI\temp\pytest\arch134d1r2-*` roots. Run both focused non-mutating Ruff
phases and git diff --check. No local ROBINHOOD/FULL/LEGACY/EXHAUSTIVE certification.

Implementation verification covered 478 distinct focused cases across iterative
affected-module runs and necessary repairs. The final combined affected-module
run had 475 passed and two incorrect transient test fakes; those failures were
corrected to use the actual sanitized transport exception and passed in a
three-case targeted run. Subsequent recovery/authority/frozen-predecessor checks
passed 124 cases; final strict consumption/lineage recovery checks passed 66
cases, including the added recovery-start tampering regression. Both focused
Ruff phases over eight changed Python files and git diff --check passed.
All provider/credential/storage edges remained fake or external test-only.

GitHub must produce terminal source-static, active-tests, canonical ROBINHOOD and
source-gates success on the exact pushed HEAD/tree, with full-tests skipped for
the mapped route. Missing/failed CI is STOP, not acceptance.

The supplied fresh D1Q parent observation is accepted operational history only:
READY_FOR_MANUAL_PAPER_SESSION / ALREADY_PROVISIONED, paper_records=0,
session_reservations=1, both stores WRITE_READY, credential reads=2/2, persisted
OAuth=true, all provider/application/paper/scheduler/broker effects=0,
effect_counts_complete=true. Evidence:
`F:\AI\temp\qualification\arch134-d1r1-d1q-98696f7aa11b4028b60b0247906c0da7.json`.
Do not access it or `F:\AITradingBot\Arch134D1` in tests. After this source acceptance, require fresh exact-source readiness and the
separately bounded real recovery within the unexpired target market session. D2/scheduler remain
disconnected; real-money placement remains NO-GO.
