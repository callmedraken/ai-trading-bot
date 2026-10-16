# Architecture 134-D1R1 — Bounded history failure observability

## 2026-10-13 — D1R2 real recovery consumed; Alpaca authentication blocked

The separately authorized Architecture 134-D1R2 real recovery was executed once
against exact current docs-descendant source HEAD
`aa2e843e9954435ba9e9bcf55b2bdde23ab93fb9`, TREE
`5453d008116c8719ce1d024c7c1f3d9bb45e3674`. Final pre-effect
reconciliation passed before the boundary. The supplied frozen predecessor
artifact retained SHA-256
`ae4b85b657810ff7701323934af9c5013805230a772094e6259e3b9a75870f4c`.

The one permitted recovery CAS was consumed and the durable session advanced to
`armed-paper-session/v2` with `recovery_count=1`,
`recovery_reason=FROZEN_OCTOBER_13_PRE_D1R1`, successor contract
`93091b0e-a1a6-52fd-930f-f88eb2009c05`, and the original downstream operation
ID `8e8c5102-8b52-5534-8288-b3261f65b2d4` preserved.

The first recovered Alpaca history fetch, for 2026-10-07, returned the closed
diagnostic classification `HTTP_FAILED` with HTTP status **401** and no provider
code. The session durably published `BLOCKED` with `alpaca_reads=1`,
`effect_counts_complete=false`, no accepted snapshots/history seed,
`strategy_evaluations=0`, PREPARE=0, EXECUTE=0, all Robinhood application-call
counters zero, `paper_mutations=0`, and `broker_placement_count=0`.
No proposal/order/fill or execution evidence was created.

External evidence paths from the terminal attempt are:

```text
SESSION
F:\AI\temp\arch134-d1r2-recovery-b01a29c0a03842de949748fcbbedb2e3.json

HISTORY FAILURE
F:\AI\temp\arch134-d1r2-recovery-b01a29c0a03842de949748fcbbedb2e3.json.history-failure.json

EXECUTE DESTINATION (must remain absent for this failure)
F:\AI\temp\arch134-d1r2-recovery-b01a29c0a03842de949748fcbbedb2e3.json.execute.json
```

This is a terminal consumed D1R2 outcome. The accepted recovery policy permits a
future count-zero v2 retry only for eligible transport failures or HTTP 429/5xx.
HTTP 401 is intentionally not recovery-eligible, and this row already has
`recovery_count=1`. **Do not retry the October-13 session by ARM, recovery,
reclaim, reservation replacement, or a second provider read.**

D1R2 therefore proved the intended same-session lineage, one-shot CAS,
classified diagnostic, and fail-closed downstream isolation, but did not
establish successful history acquisition or strategy/paper execution.

The operational finding also exposes a readiness gap: the existing D1Q
credential check proves that the two fixed Windows Credential Manager records are
present/readable/canonical, but it does not prove that Alpaca currently accepts
the stored key/secret pair. The next production milestone is
**Architecture 134-D1R3 — bounded Alpaca authentication-validity qualification**.
D1R3 must validate the fixed current-product credential pair against the fixed
Alpaca historical-data boundary under separately bounded read-only provider
authority *before* any future one-shot session reservation/recovery authority is
consumed. It must retain only sanitized nonsecret evidence and must grant no
strategy, Robinhood, paper, broker, scheduler or D2 authority.

After D1R3 is source-accepted and a fresh protected authentication qualification
passes, use a fresh future NYSE session for the still-required pre-market
start/WAITING_FOR_MARKET/wake/re-admission qualification. Architecture D2 remains
disconnected until those production proving steps complete. Real-money placement
remains **NO-GO**.

This document preserves the historical D1R1 acceptance/no-retry contract.
Current-product recovery behavior is superseded only within the
[D1R2 contract](arch134-d1r2-pre-effect-history-recovery.md), which is SOURCE
ACCEPTED at `114608d220ab6653fcb48fc0002b6ae9497f90c9` /
`b57cecd27865bda88ec104748fef55c0dcb54f34` after terminal mapped CI #514 and
exact ChatGPT GitHub review.
The fresh D1Q next step recorded below has completed on the docs-only parent;
the supplied result is serialized in the current status/handoff. D1R1 did not
authorize recovery, and its historical conclusions are not rewritten.

## 2026-10-13 — SOURCE ACCEPTED

Exact accepted source:

```text
HEAD 2154cb53017cccbd3908d2174bb0943d4657c451
TREE 9b9718353aa7ad51dbfa5d21f54e11b0f8fa9b58
BASE 6e2081a1278f579ca0cee5a00e2bd83632bc2856
```

Mapped Checkpoint Source Gates #511 / 38359252324 completed SUCCESS on that
exact HEAD. The route selected `arch134-production-paper-runtime`; source-static
and active-tests passed; canonical ROBINHOOD passed 94 modules / 8,738 cases /
8,737 passed / 1 skipped / 0 failed / 0 errors in 136.46 seconds; full-tests
were skipped as designed for the mapped certification route; terminal
source-gates passed.

Focused fake-only verification passed 999 tests plus Ruff check, format --check
and git diff --check. Historical armed/R1/R2 dictionaries and frozen branches,
ACTIVE membership/order/digest, checkpoint names and canonical ROBINHOOD mapping
remain as documented. No implementation/CI protected effect occurred.

D1R1 does not grant retry or same-session recovery authority. The consumed
2026-10-13 row remains no-retry. Fresh protected D1Q qualification is the next
operational step and must use canonical stdin-fed Python.

Status: SOURCE ACCEPTED; terminal mapped CI and exact ChatGPT review complete.

## 2026-10-12 — Architecture 134-D1R1 history diagnostics / review pending

Current operational descendant: `feature/robinhood-production-paper-history-diagnostics`.
Base HEAD `6e2081a1278f579ca0cee5a00e2bd83632bc2856`, TREE
`5858cc644d78eab9bbe58d1332f02c1b56aa5c65`. This entry supersedes earlier
current-runtime branch and next-D1-attempt guidance. ChatGPT owns source
acceptance after exact GitHub review and terminal mapped ROBINHOOD CI.

The earlier `python -m trading_bot.review_paper.armed_session_host` returned zero
without JSON/evidence because the module defines `main()` without invoking it.
This import-only no-op caused zero reservation, provider access and paper effects;
it was not a D1 attempt or consumed session. Canonical Windows operator execution
is stdin-fed Python explicitly calling `main()`. The existing script launcher
already calls `main()`; no module guard or generic runner is added.

The actual New York **2026-10-13** attempt is **consumed / BLOCKED / no retry**.
Contract `d490a15f-2c6e-5a1c-af36-e5f233760a7b`; operation
`8e8c5102-8b52-5534-8288-b3261f65b2d4`. Required history: 2026-10-07,
2026-10-08, 2026-10-09, 2026-10-12. Source/runtime admission, runtime write
readiness, fixed provider construction and durable reservation succeeded.
The first history-read fence was crossed: alpaca_reads=1, first required session
2026-10-07; snapshot_sha256=[], history_seed_sha256=null,
strategy_evaluations=0, strategy_outcome=null, PREPARE=0, EXECUTE=0,
all Robinhood calls=0, paper_mutations=0, broker placement=0,
effect_counts_complete=false. No execute evidence file exists. Current incident
evidence cannot identify the exact Alpaca failure stage. No transport, HTTP,
schema, capture, acceptance or verification cause is inferred.

D1R1 preserves `armed-paper-session/v1` and the one-shot fences. The separate
bounded external `armed-paper-history-failure/v1` artifact retains only closed
sanitized session/read/stage facts and grants no retry. Durable BLOCKED precedes
diagnostic export; ordinary session export is attempted even if diagnostic export
fails. No existing reservation is migrated, rewritten, cleaned or reclaimed.
R1 stays frozen at `6bf8753b0cc8950ae27b32b6858b64d454c512f0` /
`ce3feb2ac48e7aebc23970142aafed5059c447e7`; R2 stays frozen at
`2f122958366d1db282fea51abbd461b83fa893d9` /
`c3fb82add37bdbea12ebad9836ca10000b924fe1`.

`arch134-production-paper-runtime` maps to the successor branch and retains
canonical `robinhood` certification. Frozen armed/R1 pin/import dictionaries
remain predecessor evidence; exact successor overlays validate current source.
R2 pin/import/structural material, branch mapping, ACTIVE tuple/order/digest and
workflow remain unchanged. Tests extend existing modules without inventory
expansion. Implementation effects are fake-only; production effects are zero.

Focused verification PASS: 999 cases (320 history/controller/provider, 121
runtime/host, 558 checkpoint/routing/profile). Focused Ruff check, format --check,
git diff --check and all armed/runtime/ACL authority checks PASS. Computed current
inventory: ACTIVE 62 / FULL 170 / ROBINHOOD 94 / LEGACY 215 / EXHAUSTIVE 385.
No local broad certification or protected effect occurred.

Next: terminal mapped CI, then ChatGPT exact-source review. After acceptance,
fresh protected D1Q qualification must use the new exact source and canonical
stdin-fed Python. Only a future separately admitted NYSE target may become
eligible for D1 after READY_FOR_MANUAL_PAPER_SESSION. Never retry 2026-10-13.
D2 stays disconnected; real-money placement remains **NO-GO**.

See `docs/validation/arch134-d1r1-history-failure-observability.md` for the
closed diagnostic contract and verification evidence.

## Closed external artifact

Exactly fourteen fields: schema, source_head, source_tree, contract_id,
target_session, operation_id, history_session, read_ordinal, classification,
transport_stage, metadata_reason, http_status, provider_code, alpaca_reads.
The immutable closed model validates exact SHA-1/UUID/date material, numeric
types/bounds and relationships. Sorted compact UTF-8 JSON has one trailing
newline, matching session evidence, and is bounded to 4096 bytes. Parsing rejects
duplicate/unknown/missing fields and noncanonical reserialization. Exclusive xb
writes flush and fsync without replacement or retry.

Closed classifications: PROVIDER_CONSTRUCTION_FAILED, TRANSPORT_FAILED,
HTTP_FAILED, PROVIDER_RESPONSE_INVALID, CAPTURE_OBSERVATION_REJECTED,
SNAPSHOT_ACCEPTANCE_REJECTED, SNAPSHOT_VERIFICATION_REJECTED,
VERIFIED_HISTORY_REJECTED, HISTORY_SEED_REJECTED, INTERNAL_FAILED.

Transport values reuse REQUEST, RESPONSE_START, RESPONSE_METADATA, RESPONSE_BODY
and UNKNOWN. Existing metadata-reason values are retained only for
RESPONSE_METADATA. HTTP values retain exact-int status 100..599 and exact-int
provider code 0..2**63-1, matching the existing sanitizer; unsafe values become
null. Non-HTTP failures have null HTTP fields. Request IDs are discarded.
Construction failures retain null history session, ordinal zero and zero reads.
Unattributed internal failures do not guess a session/stage.

ProductionHistoryAcquisitionFailure retains immutable closed semantic facts and
a fixed classification in args/repr/str. Stage wrapping raises outside the raw
exception handler with suppressed chaining, discarding underlying context. No
exception strings are parsed. No v1 reservation/final-session field changes.

## Safety ordering and paths

The durable reservation owns retry prevention. HISTORY_STARTED remains before
each fetch. Classified failure publishes BLOCKED, attempts one diagnostic export,
then attempts ordinary session export. Diagnostic failure cannot advance strategy,
PREPARE or EXECUTE or cause an extra provider request. If durable publication
fails, the preceding reservation/read fence survives without retry authority.

The only derived sibling is `<session-evidence>.history-failure.json`. Host
startup rejects existing ordinary/execute/diagnostic destinations before runtime,
credential or store access. The diagnostic follows the same external-evidence
boundary, outside every repository worktree and `F:\AITradingBot\Arch134D1`.
No timestamp, filesystem path, credential, header, URL, body, provider message,
request ID, traceback, raw exception or Robinhood material is retained.

## Canonical stdin operator convention

This shape explicitly calls main. It illustrates invocation only and grants no
production preflight/session authority:

```powershell
@'
from trading_bot.review_paper.armed_session_host import main
raise SystemExit(main())
'@ | & $PythonExe -B - --expected-head $ExpectedHead `
    --expected-tree $ExpectedTree --evidence $FreshExternalEvidence --preflight
```

The old module-only invocation is documented as a no-op incident, never current
operator guidance. The reviewed script launcher already invokes main.

## Exact successor authority and verification

Armed pin/import override keys are exactly alpaca_strategy_history.py,
armed_session.py and armed_session_host.py under src/trading_bot/review_paper/.
All three import sets change. Runtime successor pins add armed_history_failure.py
and override only those three sources plus directly changed armed/runtime/CI/core
tests. Predecessor dictionaries remain frozen. Unreviewed keys, changed pins or
imports, and overrides of unchanged inherited files fail closed. Forbidden calls
and exact fetch/accept/verify/seed/decision/PREPARE/EXECUTE composition remain.

Focused fake-only tests cover strict parsing/serialization/bounds, every transport
stage/metadata reason, HTTP 401/403/429 and unsafe fields, schema, capture
regression/date, acceptance, snapshot verification/replay, verified-history
contract, seed, construction and internal failures, startup collisions,
durable-before-export ordering, failed export, no retry, zero downstream effects,
and historical consumed v1 compatibility. Authority tests freeze predecessor
digests, ACTIVE topology, branch mapping and successor drift rejection.

Use fresh external pytest storage, focused Ruff check and format --check, and
git diff --check. No local FULL/ROBINHOOD certification. The existing
feature/robinhood-* workflow must select arch134-production-paper-runtime and
pass source-static, active-tests, canonical ROBINHOOD and terminal source-gates.
Broad full-tests are skipped because mapped certification owns breadth. Missing
CI is not PASS. Terminal mapped CI and exact ChatGPT source review are complete; D1R1 is SOURCE ACCEPTED.

No production database, credential, provider, ARM, scheduler, ACL or paper effect
is authorized by implementation/CI. Fresh protected D1Q qualification follows
source acceptance; the consumed October 13 session is never retried.
