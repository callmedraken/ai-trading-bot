# Architecture 134 — Production strategy and AI-research authority

## 2026-10-13 — D1R3 real authentication qualification BLOCKED / HTTP 401

The separately authorized Architecture 134-D1R3 real authentication
qualification was executed once against the accepted docs-descendant operational
source HEAD `5dd510a73e9eb15ade4a4fa7ed90152d2ac85b3b`, TREE
`df8f208224ae8646e79d4d5ce92a70bb18e900d3`, after a zero-effect preflight
proved the exact source/import/probe/evidence boundary.

The preflight performed zero credential reads and zero Alpaca HTTPS requests.
The real qualification then crossed exactly one D1R3 authority boundary and
published canonical external evidence at:

```text
F:\AI\temp\qualification\arch134-d1r3-auth-bb7ebdbb0669479d82b13f2ff9171781.json
```

Canonical outcome:

```text
schema                           alpaca-authentication-qualification/v1
status                           BLOCKED
reason                           HTTP_REJECTED
http_status                      401
provider_code                    null
credential_pair_read_attempts    1
credential_pair_read_succeeded   true
alpaca_request_attempts          1
source_readmitted                true
probe_session                    2026-10-07
probe_method                     GET
probe_host                       data.alpaca.markets
```

Because pair readiness succeeded, the accepted reader consumed the two fixed
Windows Credential Manager records exactly once each. Exactly one Alpaca HTTPS
request was attempted. The qualification made no production SQLite access,
session reservation/recovery, strategy evaluation, Robinhood call,
PREPARE/EXECUTE, paper mutation, broker placement, scheduler/ACL mutation, D1
launch or D2 invocation. The accepted source was re-admitted after the external
read. The result is definitive and non-ambiguous: the current fixed credential
pair is locally readable but rejected by Alpaca.

The D1R3 invocation is consumed. **Do not rerun D1R3 unchanged.**

The current reader is hard-coded to the accepted Architecture-84 `/v2` targets:

```text
AITradingBot/MarketData/Alpaca/ApiKeyId/v2
AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
```

Architecture 84A already freezes the post-first-provider-effect immutability
rule: once a real provider effect has used `/v2`, those two targets are
historical credential-reference state and must not be overwritten, deleted for
replacement, or silently rebound to another Alpaca pair. D1R2 had already used
the `/v2` pair; D1R3 now independently confirms remote rejection. Therefore
manual replacement of either existing `/v2` entry is **not authorized**.

The next production milestone is **Architecture 134-D1R4 — versioned Alpaca
credential rotation to `/v3` plus fresh authentication requalification
authority**. It must freeze a new credential policy and exact new target names,
preserve `/v2` as immutable historical evidence, reuse the existing
secret-free local witness discipline, prohibit fallback, update the D1R3
qualification path to the new fixed pair, and keep actual generation/provisioning
and the later real authentication probe as separately reviewed protected
operator boundaries.

Until D1R4 source/deployment/provisioning is accepted and a fresh `/v3`
authentication qualification passes, no fresh D1 session is authorized.
The still-required pre-market start/WAITING_FOR_MARKET/wake qualification remains
after remote Alpaca authentication is proven. D2 remains disconnected and
real-money trading remains **NO-GO**.

## 2026-10-13 — Architecture 134-D1R3 SOURCE ACCEPTED

Architecture 134-D1R3 — bounded Alpaca authentication-validity qualification —
is **SOURCE ACCEPTED** on
`feature/robinhood-production-paper-alpaca-auth-qualification`.

Exact source history:

```text
BASE HEAD        d595450daa029f37e2f69bbb6b20263dc7e0e987
BASE TREE        4822a6723b10fd223a138df580aa7a3daf2ee5bc

IMPLEMENTATION
HEAD             0cfd621ab3d91c349df4394e5d757d98d25f5ba1
TREE             f24fd9321a71ce982f05c4b7bd883c47f6fbd47a

ACCEPTED FINAL
HEAD             2a106c10178efa38eb7a24c7d97866201e0d2b76
TREE             03be6ef612542f204b4d5d80924473b5274aa25d

CI               #520 / 38462482959 / attempt 2 / SUCCESS
CERT ARTIFACT    11848066370
```

The original implementation is one ordinary commit / 14 paths. It adds the
separate noninteractive D1R3 host and strict
`alpaca-authentication-qualification/v1` evidence contract without changing the
accepted D1/D1R1/D1R2 production session, CAS, recovery, strategy, paper or
broker source. The exact fixed probe reuses the accepted Alpaca historical-bars
transport/request/parser for SPY on completed XNYS session 2026-10-07. Successful
pair readiness reads only the two fixed Windows Credential Manager records and
permits at most one HTTPS request; there is no retry, environment/config secret
fallback, D1 launch or session reservation.

The exact correction commit
`2a106c10178efa38eb7a24c7d97866201e0d2b76` /
`03be6ef612542f204b4d5d80924473b5274aa25d`, subject
`test: reconcile D1R3 source topology and recovery concurrency`, changes only
the D1R3 validation document, source-authority runner metadata and retained tests.
It changes no D1R3 production module and no frozen D1/D1R2 executable source.

The retained D1R2 stale-CAS test was corrected to distinguish two independent
facts that the previous uncontrolled contention test conflated. A controlled
two-caller stale-read test barriers identical predecessor bytes, deterministically
orders either caller's real exact-byte CAS first, requires the other stale UPDATE
to reject, and proves exactly one history reacquisition/strategy evaluation with
zero PREPARE/EXECUTE/paper/broker effects. A separate disposable
`BEGIN EXCLUSIVE` test deterministically produces `SQLITE_BUSY` and proves BUSY
returns BLOCKED without consuming predecessor bytes or issuing a provider request.
No production timeout, wait, mutex, retry or CAS behavior changed.

The ten retained topology assertions remain exact: ACTIVE is 63 checkpoints, the
new D1R3 checkpoint is exactly position -7 before the retained Architecture-134
six-checkpoint suffix, and historical exact predecessor pairs shift explicitly.
No tuple assertion was weakened to subset/membership-only semantics. Canonical
inventory is FULL 171 / ROBINHOOD 95 / LEGACY 215 / EXHAUSTIVE 386. Initial D1R3
source/test pins remain frozen. The correction adds exactly one narrow correction
test pin, for
`tests/review_paper/test_armed_production_paper_session.py`, whose committed Git
blob is `4e06e2d922f6ca784681cffe8ccda6b4806bc14f`.

Checkpoint Source Gates #520 first certification attempt was not a semantic test
failure: on the exact accepted source it produced 8,899 passed / 1 optional SDK
skip / 0 failed / 0 errors, but the canonical wall was 331.725 seconds and
therefore failed only the <300-second hygiene gate. The single certification
retry used the unchanged exact HEAD/tree. Attempt 2 passed 8,900 cases total:
8,899 passed / 1 optional SDK skip / 0 failed / 0 errors, with lane counts
5,248 and 3,651+1 skip and canonical wall 255.502 seconds. Successful artifact
11848066370 independently records exact source before/after tests, 95 selected
ROBINHOOD modules, git diff/Ruff check/Ruff format exit 0 and stable source
identity. source-static and active-tests were already successful; terminal
source-gates then passed and full-tests remained skipped as intended.

The accepted D1R3 artifact is strictly nonsecret and fail-closed. PASS requires
fixed credential-pair readiness, exactly one request, HTTP 200, accepted bounded
response metadata/body, strict existing Alpaca JSON parsing, exact SPY/session
probe compatibility and final unchanged source readmission. 401/403/429/5xx,
transport failure, incompatible 200 response or source drift are BLOCKED and
never retry. Parsing/canonical evidence contains no credential, auth header,
response body, provider request ID or provider free text.

Implementation, correction, tests and CI performed zero real operational effects:
no Windows Alpaca credential reads, no Alpaca HTTPS request, no production SQLite
read/write, no reservation/recovery, no strategy evaluation, no Robinhood call,
no PREPARE/EXECUTE, no paper/broker/scheduler/ACL effect and no D1/D2 invocation.
The consumed October-13 D1R2 row remains untouched and HTTP 401 remains
non-recovery-eligible.

**Next protected boundary:** one separately reviewed real D1R3 authentication
qualification against this exact accepted source. Source acceptance alone grants
no credential/provider read. A PASS means only
`REMOTE_ALPACA_AUTH_READY` for the exact fixed probe at the observation time; it
does not reserve a session, launch D1, authorize paper execution, connect D2 or
grant live trading.

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

## 2026-10-13 — Architecture 134-D1R2 SOURCE ACCEPTED

Architecture 134-D1R2 is **SOURCE ACCEPTED** on
`feature/robinhood-production-paper-history-recovery` at the exact executable/test source:

```text
HEAD 114608d220ab6653fcb48fc0002b6ae9497f90c9
TREE b57cecd27865bda88ec104748fef55c0dcb54f34
BASE cbcc1addfb392ca87939df0f77fe9dde10685abf
CI   #514 / 38370765607 / SUCCESS
```

The exact delta is one implementation commit / 14 paths. Exact GitHub review
accepted the same-session pre-effect recovery contract: one existing reservation,
the predecessor operation identity, strict v2 predecessor/digest/source/contract
lineage, exact frozen October-13 legacy admission, one durable recovery CAS before
Alpaca construction/reacquisition, and no second ARM. Recovery remains closed
after any strategy/PREPARE/Robinhood/EXECUTE/paper/broker effect or ambiguity.
Future eligibility is closed to non-metadata transport failures and HTTP 429/5xx;
deterministic/unknown/internal failures remain blocked.

Terminal mapped CI #514 passed on the exact HEAD: source-static SUCCESS,
active-tests SUCCESS, certification-tests SUCCESS, full-tests SKIPPED and
source-gates SUCCESS. Canonical ROBINHOOD covered 94 modules / 8,814 cases:
8,813 passed, one skipped, zero failures/errors; wall 262.431 seconds. No
duplicate local ROBINHOOD certification is required.

The supplied parent D1Q qualification remains accepted operational history only.
No real recovery occurred during source acceptance. Fresh exact-source runtime/
credential readiness is required before the separately bounded real recovery.
An expired target session remains expired; D2 stays disconnected and real-money
placement remains **NO-GO**.

Any later documentation-only descendant does not replace the accepted D1R2
executable/test identity above.

The accepted authority remains source-only until a fresh exact-source readiness
gate passes and the bounded recovery interlock is invoked. Historical D1R1
no-retry facts remain historical rather than rewritten.

## 2026-10-13 — Architecture 134-D1R1 SOURCE ACCEPTED

Architecture 134-D1R1 — bounded Alpaca history-failure observability and runtime
successor — is **SOURCE ACCEPTED** on
`feature/robinhood-production-paper-history-diagnostics` at the exact
executable/test source:

```text
HEAD 2154cb53017cccbd3908d2174bb0943d4657c451
TREE 9b9718353aa7ad51dbfa5d21f54e11b0f8fa9b58
BASE 6e2081a1278f579ca0cee5a00e2bd83632bc2856
```

The exact delta is one commit / 14 paths. D1R1 adds the separate bounded
`armed-paper-history-failure/v1` artifact without changing
`armed-paper-session/v1`, retry ownership, production strategy semantics or
paper/broker authority.

The accepted diagnostic contains exactly fourteen closed fields: schema, source
HEAD/tree, contract/operation IDs, target/history sessions, read ordinal,
classification, transport stage, metadata reason, HTTP status, provider code and
Alpaca-read count. Serialization is exact canonical compact UTF-8 plus one trailing
newline, bounded to 4096 bytes, duplicate/unknown/missing/noncanonical input is
rejected, and external writes are exclusive `xb` with flush/fsync.

The closed classification set is PROVIDER_CONSTRUCTION_FAILED,
TRANSPORT_FAILED, HTTP_FAILED, PROVIDER_RESPONSE_INVALID,
CAPTURE_OBSERVATION_REJECTED, SNAPSHOT_ACCEPTANCE_REJECTED,
SNAPSHOT_VERIFICATION_REJECTED, VERIFIED_HISTORY_REJECTED,
HISTORY_SEED_REJECTED and INTERNAL_FAILED. Transport/metadata classification
reuses the already-sanitized Alpaca enums; safe HTTP status/provider code may be
retained, while request ID, raw exception, credentials, headers, URL/body,
filesystem paths and provider free text are excluded.

Failure ordering is accepted: the durable one-session fence remains authoritative;
HISTORY_STARTED is published before each provider fetch; classified acquisition
failure publishes durable BLOCKED before fallible diagnostic export; diagnostic
export failure cannot retry or suppress the ordinary final session export; no
failure path advances to strategy evaluation, Robinhood PREPARE, synthetic
EXECUTE, paper mutation or broker placement. Focused tests prove one failed fetch
is never reacquired and raw sensitive material is absent from durable/exported
evidence and stdout/stderr.

The accepted source also preserves the consumed New York 2026-10-13 v1 row
unchanged and unretryable. That incident remains BLOCKED with alpaca_reads=1,
zero accepted snapshots, zero strategy evaluations, zero Robinhood calls,
PREPARE=0, EXECUTE=0, paper_mutations=0 and broker placement=0. The preceding
`python -m trading_bot.review_paper.armed_session_host` import-only invocation
remains a zero-effect no-op, not a consumed D1 attempt. Canonical Windows operator
guidance remains stdin-fed Python explicitly calling `main()`.

Historical authority material was independently reviewed against the admitted
base and is exactly unchanged: armed-MVP source pins/imports, historical R1
runtime source pins/imports, and R2 source/import/AST pins. D1R1 uses exact
successor overlays for the three changed inherited armed files and the current
runtime diagnostic/test material. The older armed-MVP authority is
successor-aware while retaining its historical branch/spec. The existing
`arch134-production-paper-runtime` checkpoint alone maps to the diagnostics
branch and retains canonical `robinhood` certification. ACTIVE membership/order
remains 62 and reviewed digest remains
`06a3101a319f6b268404deb67299d87d484fd238212131074c5f86cfea9a6440`.

Focused local verification passed **999** tests: 320
history/controller/provider, 121 runtime/host and 558 checkpoint/routing/profile.
Focused Ruff check, Ruff format --check and git diff --check passed. No local
broad certification or protected operation ran.

Mapped Checkpoint Source Gates
[38359252324](https://github.com/callmedraken/ai-trading-bot/actions/runs/38359252324) (#511) completed SUCCESS on the exact accepted HEAD.
source-static passed the mapped `arch134-production-paper-runtime` authority;
active-tests passed with stable identity; canonical ROBINHOOD certification
passed **94 modules / 8,738 cases / 8,737 passed / 1 skipped / 0 failed /
0 errors** in **136.46 seconds**; full-tests were correctly skipped because the
mapped certification profile owns breadth; terminal source-gates passed.

Current inventory remains ACTIVE 62 / FULL 170 / ROBINHOOD 94 / LEGACY 215 /
EXHAUSTIVE 385. Historical R1 remains
`6bf8753b0cc8950ae27b32b6858b64d454c512f0` /
`ce3feb2ac48e7aebc23970142aafed5059c447e7`; R2 remains
`2f122958366d1db282fea51abbd461b83fa893d9` /
`c3fb82add37bdbea12ebad9836ca10000b924fe1`.

Implementation/CI effects are all zero: production SQLite reads/writes,
credential reads, Alpaca/Robinhood/broker/scheduler calls, ACL/paper mutations,
D1 reservations and D1 executions. Real-money broker placement remains **NO-GO**.

Any later documentation-only descendant does not replace the accepted D1R1
executable/test identity above.

**Next operational step:** fresh protected D1Q qualification against this exact
accepted D1R1 source using canonical stdin-fed Python. Qualification may inspect
the fixed runtime stores and fixed Windows credentials according to the already
accepted D1Q authority, but it must not ARM a session, contact Alpaca/Robinhood
application APIs, mutate paper state, scheduler or ACLs, or retry the consumed
2026-10-13 session. D1R2 same-session/pre-effect recovery remains a subsequent
source-design milestone; it is not authority granted by D1R1.

## 2026-10-12 — Architecture 137 / RCL-1 implemented, exact review pending

Architecture 137 adds the pure in-memory canonical research artifact
`research-strategy-candidate/v1` on
`feature/research-candidate-lifecycle-foundation`, based on GUI-A15 docs-closeout
HEAD `778151fe8f91632a1af66384a3ab0a85d8d65069`, TREE
`03c50482427b04ebfc6ed061d048bb95e86edeae`. It is implementation evidence
pending terminal repository CI and ChatGPT exact GitHub review, not source acceptance.

GUI-A15 accepted executable/test source remains HEAD
`1dd46169deb69d7a381687b6ba835af9d6c12e5a`, TREE
`383b237aebfc553b10c7a5ef121a0191559c3f11`; dedicated GUI CI
[38343026765](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343026765)
and repository CI
[38343142780](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343142780)
are terminal SUCCESS. Earlier dated inventories remain historical provenance.

The exact conceptual order is EXPERIMENTAL -> BACKTESTED -> WALK_FORWARD_PASSED
-> SHADOW -> PAPER_CANDIDATE -> AWAITING_HUMAN_PROMOTION. EXPERIMENTAL is
pre-canonical hypothesis state. Only BACKTESTED is materialized in 137; all later
stages remain reserved for separately reviewed evidence/policy gates. Awaiting
human promotion means eligibility for review, without approval or promotion.
There is no generic stage setter/advance API.

The builder requires explicit selection from one completed exact
HistoricalExperimentReport, revalidates its invariants and retains all report/
row identity and rank facts. Rank is evidence: rank-1, rank-2 and unranked explicit
selection are supported, with no automatic rank selection. Strict JSON parsing
establishes canonical self-consistency only; independent report reconciliation
must be invoked to verify external evidence.

There is no WALK_FORWARD_PASSED policy yet. Architecture 138 must separately
freeze ResearchCandidateWalkForwardQualificationPolicy; existence of a
walk-forward result grants no passed stage. Broad historical portfolio variants
are not equivalent to the current production moving-average strategy. No
research-to-production compatibility claim, production contract, approval,
promotion or execution material is introduced. Compatibility and human promotion
remain separate future reviewed boundaries.

Canonical current inventory is ACTIVE 62 / FULL 170 / ROBINHOOD 94 / LEGACY 215 /
EXHAUSTIVE 385 / tests/gui 44. No ACTIVE production checkpoint is added. Current
inventory assertions and only three directly affected retained test-file blob
pins are reconciled; executable/native/AST pins, ACTIVE tuple/digest, historical
publication-recovery pins and production push allowlist remain unchanged.

R1 `6bf8753b0cc8950ae27b32b6858b64d454c512f0` and R2
`2f122958366d1db282fea51abbd461b83fa893d9` remain frozen. D1 proving remains
independent/protected; D2 is disconnected. No production SQLite, credentials,
provider, broker, scheduler, ACL, paper, research execution, walk-forward
execution, strategy promotion or production contract effect occurred.
Real-money broker placement remains **NO-GO**.

Immediate handoff: Codex completes focused checks and ordinary commit/push, then
dispatches Checkpoint Source Gates on this exact research branch and waits for
source-static plus four full-tests shards and terminal source-gates success
(active-tests/certification-tests skipped). No GUI run or local broad profile is
requested. ChatGPT then reviews the exact final GitHub HEAD/tree/diff and CI and
owns acceptance/closeout. The next research design boundary after acceptance is
Architecture 138; D1 remains an independent operational milestone.

See `docs/architecture/137-research-candidate-lifecycle-foundation.md` and
`docs/validation/arch137-research-candidate-lifecycle-plan.md` for the frozen
contract, focused evidence, exact verification commands and stop conditions.

## 2026-10-12 — Current D1Q-R2 operational state / GUI-A14 checkpoint

This current entry supersedes pending/failed R2 wording in the dated historical
entries below. Architecture 134-D1Q-R2 source is accepted on
`feature/robinhood-production-paper-runtime-acl`:

```text
HEAD 2f122958366d1db282fea51abbd461b83fa893d9
TREE c3fb82add37bdbea12ebad9836ca10000b924fe1
CI #504 / 38305872664 SUCCESS
ROBINHOOD 8644 cases / 8643 passed / 1 skipped / 0 failed / 0 errors
wall 222.459 s
```

The accepted protected ACL operation recorded PROVISIONED / PASS, three apply
attempts and three verified applies. Parent, recursive, credential, provider,
paper, session, scheduler and broker mutation/call counts were all zero.
Independent non-elevated postcheck recorded ALREADY_PROVISIONED / PASS.

Hardened D1Q-R1 qualification remains bound to the unchanged runtime source:
HEAD `6bf8753b0cc8950ae27b32b6858b64d454c512f0`, TREE
`ce3feb2ac48e7aebc23970142aafed5059c447e7`. Read-only preflight recorded
PRESENT_COMPATIBLE, paper_records=0 and session_reservations=0. Protected
qualification recorded READY_FOR_MANUAL_PAPER_SESSION,
runtime_status=ALREADY_PROVISIONED, both paper/session-store write readiness
WRITE_READY, alpaca_credential_reads=2, robinhood_credential_reads=2 and
persisted_oauth_available=true. Alpaca HTTP calls, Robinhood application calls,
paper trade mutations, scheduler mutations and broker mutations were all zero.

Current operator authorization follows the standing reviewed-bounds rule in
AGENTS.md and AI_DEVELOPMENT_WORKFLOW.md, with all prerequisite/interlock and
STOP/reconciliation conditions retained. Older separate-message narratives do
not impose another authorization-only turn for a reviewed bounded command.

These are accepted recorded operational facts supplied for serialization, not
new qualification performed by GUI-A14. No real evidence is read by source
tests. The first D1 manual production-paper session remains the next operational
proving step and has not been accepted. B3Q remains consumed/no-retry.
Real-money broker placement remains **NO-GO**.

GUI-A14 is implemented on `feature/gui-production-runtime-status` from the
exact R2 parent above, in
`F:\AI\worktrees\ai-trading-bot-gui-production-runtime-status`. It presents only
explicit ACL/qualification/session JSON through bounded immutable GUI models.
Runtime, System and Evidence navigation add zero reads. Complete real-PySide6
offscreen GUI verification passes; exact results are in
`docs/validation/gui-a14-production-runtime-status.md`. Accepted R1/R2 execution
source, source pins and branches are unchanged. GUI-A14 is SOURCE ACCEPTED:
HEAD `c29bb678dd7c64a317de602b81ba9df0aa8e1bd8`, TREE
`921b7b32bbfecbb454acc8916faa4362464b19d3`; dedicated GUI CI 38325919046
SUCCESS and repository source gate 38326059553 SUCCESS.

The earlier local-only bootstrap decision is historical and resolved by the
accepted A14 CI chain. Current GUI-A15 is presentation-only: an explicitly
selected canonical production contract may be inspected read-only. A historical
research report is evidence, not research process liveness. A15 introduces no
canonical candidate/promotion artifact. Automatic promotion remains disabled;
human promotion remains required; promotion authority and D2 supervisor are
not connected. No D2 effects are implemented. R1/R2 source remains frozen;
ChatGPT owns exact source/CI acceptance. See Architecture 136.

### Current D2 end-state — ON/OFF, arbitrary-time startup

This standing design supersedes any current D2 requirement to wake a sleeping
PC. The PC is either ON or OFF and is never intentionally asleep while bot
operation is expected. D2 must not require WakeToRun, wake timers, sleep-resume
state or wake-from-sleep qualification. This is a design serialization only;
GUI-A14 adds no D2 executable behavior.

PC OFF: the bot is not running. PC ON: a runtime supervisor runs/reconciles,
deriving legal state from current authoritative time, published market-session
authority and durable state. Arbitrary-time startup is required. Conceptual
trading states are RECONCILE, PREMARKET_WAIT, TRADING, NEXT_SESSION_WAIT and
BLOCKED; exact names can be frozen later.

Startup during an admitted session qualifies/reconciles and trades only if
otherwise permitted. Startup before a published session waits for admission;
startup after today's session, on weekends or holidays resolves the next
published session and waits instead of terminating on an expired date. Restart
recomputes current reality from time/durable state and never trusts an old sleep
duration. Task Scheduler, if retained, supplies only automatic start/restart
while the PC is ON, never wake authority or trading-session authority.

The AI research/strategy-testing plane remains operational while the overall
process runs, independently of trading-plane waiting/admission. Research
candidates never silently replace the production strategy. Promotion remains
versioned, reviewed and certified. Manual D1 proving still precedes D2 effects.

## 2026-10-11 — Architecture 134-C CERTIFIED/CLOSED

Architecture **134-C — Human-started production live-paper cycle** is
**CERTIFIED/CLOSED** at this exact source-certification boundary:

~~~text
BRANCH      feature/robinhood-production-strategy-live-paper
HEAD        bcda794f8b371b097143a331d678009143cb91b1
TREE        96a36cf38133ae3547175fe75547a4e16f1deb48
CI          #471 / 38133206242 SUCCESS
CHECKPOINT  arch134-production-strategy-live-paper
CORRECTION  bcda794f8b371b097143a331d678009143cb91b1
SUBJECT     test: stabilize checkpoint topology assertions
~~~

### Preserved failed FULL and bounded source correction

The first FULL attempt on prior source
`144a66928d9f3fb3d7ff5396059c998839e17a99` /
`04f7ade45d5fdf1e4e6969db8a9b1db5484fa8b2` found 22 stale historical
test-topology assertions after the active inventory grew to 60 checkpoints.
Its failed evidence is preserved and must not be overwritten or reused:

~~~text
F:\AI\temp\certification\arch134c-full-e210ffcf373748d593a2df83f7b39512
~~~

The bounded test-only correction:

- replaced fragile end-relative checkpoint slices with named/local adjacency;
- removed historical tests' unowned repository-wide eventual-count assumptions;
- confined generic registration mutations to their intended `CheckpointSpec`;
- preserved the dedicated canonical full-topology expectation;
- preserved production behavior, authority, registration, workflow and source
  pins.

The separately approved publication-recovery test expectation proves that only
the historical whole-registry pin differs after later registrations and that
the unchanged protected authority rejects that drift exactly. It does not
refresh a pin or reopen historical recovery authority.

Source gate [#471](https://github.com/callmedraken/ai-trading-bot/actions/runs/38133206242)
is terminal green:

| Job | Conclusion |
| --- | --- |
| source-static | SUCCESS |
| active-tests | SUCCESS |
| full-tests | SKIPPED, correct active-branch behavior |
| source-gates | SUCCESS |

### Final cheap gates before FULL

Exact source/FULL topology plan, `git diff --check`, Ruff check and Ruff
format check all passed before the expensive suite. Ruff format check reported
919 files already formatted. The plan evidence is:

~~~text
F:\AI\temp\certification\arch134c-final-full-plan-ae24aee5c593433683993fbccafa70d7
~~~

### Final FULL certification

| Lane | Modules | Cases | Passed | Skipped | Failed | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| broad-1 | 80 | 4,764 | 4,764 | 0 | 0 | 0 |
| broad-2 | 81 | 4,320 | 4,320 | 0 | 0 | 0 |
| Total | 161 | 9,084 | 9,084 | 0 | 0 | 0 |

~~~text
profile full PASS
wall 446.814 s
evidence F:\AI\temp\certification\arch134c-final-full-e971d0c5bfda496ebde97a6fc04d1afb
~~~

No separate ROBINHOOD run was required: ROBINHOOD is a strict subset of FULL,
and this selected FULL certification satisfies the narrower source-certification
obligation on the same source. No LEGACY/EXHAUSTIVE run was required. No
provider/OAuth/paper/scheduler/broker/protected effect occurred.

At the historical 134-C closeout, inventories were active **60**, FULL **161**, ROBINHOOD **86**,
LEGACY **205**, EXHAUSTIVE **366**. The executable/test source is unchanged by
this six-file docs-only closeout. **Do not rerun FULL on that unchanged source.**

### Immediate next boundary: separately authorized SHADOW PREPARE

The next step is a **human-started 134-C SHADOW PREPARE**, using the already
accepted Architecture-131 provider-read path. It requires fresh explicit
authorization because a trade proposal performs real Robinhood/provider/OAuth
read activity. No effectful command is ordinary verification, and this closeout
stops at that protected authorization boundary.

PREPARE is shadow/live-data preview only; it performs no paper fill.
`NO_SIGNAL` has zero provider/paper effects. **`READY_TO_PROCEED` is evidence,
not execution authorization.** Only after a separately authorized PREPARE
returns and ChatGPT reviews its evidence may a separate paper EXECUTE
authorization be considered if the retained result is `READY_TO_PROCEED` and
Architecture-131 revalidation still passes. Real broker placement remains
impossible. 134-C certification does not authorize 134-D scheduling/arming;
134-D remains later.

### Docs-only closeout and repository rules

This atomic checkpoint changes exactly the six approved `docs/**` files and
uses the existing docs-only classifier's cheap validation path. It changes no
Python, tests, scripts, workflow YAML, checkpoint registration or runtime
behavior and manufactures no test rerun.

`AGENTS.md` was reviewed and remains compatible: it already forbids repeated
expensive full-suite runs and delegates detailed certification behavior to
Architecture 132 and the workflow document. It remains unchanged because it is
outside `docs/**`. A future naturally necessary non-docs workflow checkpoint
may mirror the detailed wording there without creating a standalone duplicate-
test event.

## 2026-10-11 — Architecture 134-B SOURCE ACCEPTED

Architecture **134-B — Production Strategy Decision Bridge** is source accepted.

~~~text
BRANCH  feature/robinhood-production-strategy-decision
HEAD    695fa6195b2d8cc1437ba87f5d48c527afa28da7
TREE    00871d80bc9ae0a3f60906d23c92b30e42c670c4
CI      #465 / 38128865894 SUCCESS
~~~

The accepted bridge consumes the exact 134-A production contract plus the
existing Architecture-94 verified strategy-decision request/calendar boundary.
It checks contract config and verified seed symbol/config before the builder,
invokes `build_manual_paper_strategy_decision(...)` exactly once, then requires
the prepared config/symbol/intended session to remain inside the production
contract.

Closed outcomes are exactly `NO_SIGNAL` or `TRADE_PROPOSAL`; a proposal is the
exact Architecture-94 proposal object by identity, not a newly generated or
research-selected proposal.

Source gate #465 passed static diff/Ruff/format/authority, focused pytest, stable
identity and terminal source-gates. The earlier #462/#464 failures were
mechanical Ruff formatting only and are superseded.

Current exact inventories are active **59**, FULL **160**, ROBINHOOD **85**,
LEGACY **205**, EXHAUSTIVE **365**. Broad certification remains deferred until
the first coherent live-paper integration boundary.

134-B owns no Robinhood/provider/OAuth, paper-store mutation, risk execution,
scheduler, clock/sleep, research/AI promotion or broker placement authority.

Next milestone is **134-C — Human-started production live-paper cycle**.
`PREPARE` will serve as the shadow/live-data preview: for a `TRADE_PROPOSAL`,
reuse the accepted Architecture-131 supervised PREPARE path to obtain one live
Robinhood quote, session admission and deterministic risk preview with no paper
mutation. `NO_SIGNAL` performs no provider call. A separate explicit EXECUTE
may then reuse the accepted Architecture-131 review-paper execution path to
record one synthetic local paper fill; real broker placement remains impossible.

## Product goal

The bot is operator-armed before an NYSE session, waits until the admitted
regular-session window, and trades a **single session-locked production
strategy** through the review-paper path while an independent AI/research lane
may develop and evaluate candidate strategies.

Production and research are intentionally asymmetric:

- production is boring, deterministic, bounded, and session-locked;
- research is exploratory and may create many candidates;
- research can never promote itself, change production risk, or write the
  production paper account;
- only an explicit human promotion can select a candidate for a future session.

Real-money order placement remains outside Architecture 134. The first target is
Robinhood-backed **live-data synthetic paper trading**: provider quotes/order
review are real reads; fills/accounting remain local synthetic paper effects.

## Reused accepted foundations

Architecture 134 reuses rather than replaces:

- `MovingAverageCrossoverStrategy` and `MovingAverageCrossoverConfig`;
- Architecture-94 verified daily-history strategy planning lessons;
- deterministic `TradeProposal` and risk manager contracts;
- Architecture-131 session admission, live quote acquisition, risk preview,
  PREPARE/EXECUTE and Robinhood review-paper pipeline;
- durable `ReviewPaperStore` and performance/account reconstruction;
- published XNYS/NYSE session authority;
- existing backtest, analytics, optimization and walk-forward research tools.

## Non-negotiable production/research separation

A production strategy selection is immutable for its target session once armed.
Research may observe copies/read-only evidence and write only research-owned
artifacts. Research must not:

- rewrite or select the armed production contract;
- change production strategy parameters mid-session;
- change production risk limits or trading-enabled state;
- mutate the production paper store;
- invoke the production provider/review execution path;
- enable/start/alter the production scheduler;
- mint execution, retry, wake or broker authority;
- place/cancel equity, options or crypto orders.

Promotion is always a future-session transition. Candidate quality, confidence,
backtest performance or AI recommendation is evidence only, never authority.

## 134-A — Production Strategy Contract

### Purpose

134-A creates the smallest pure object needed to answer: **what exact strategy
is production allowed to evaluate for this session?**

Expected public model:

~~~text
ProductionStrategyContract
  schema
  contract_id
  target_session_date
  source_head
  source_tree
  strategy_id
  strategy_version
  symbol
  strategy_config
~~~

V1 constraints:

- `schema == production-strategy-contract/v1`;
- exactly one `Symbol`;
- exactly one explicit `date` target session (calendar validity is checked by a
  later session-aware composition, not by this pure model);
- source HEAD/TREE are lowercase 40-hex reviewed identities;
- strategy is exactly `MovingAverageCrossoverStrategy` / `1.0.0`;
- config is exactly the existing validated `MovingAverageCrossoverConfig`;
- semantic ID is deterministic UUID5 over versioned, length-framed/canonical
  semantic material; serialized bytes/hash/path are not semantic authority;
- canonical JSON has exact fields, no duplicates/unknown fields, canonical
  decimals, and strict byte-for-byte round-trip;
- helper construction may return the existing
  `MovingAverageCrossoverStrategy(config)` only.

### Explicit exclusions

134-A has no filesystem, environment, subprocess, Git, network, MCP/OAuth,
market-data, clock, sleep, scheduler, SQLite, paper-store, risk, execution,
broker, AI/model, optimization, experiment, dynamic import, plugin loading or
arbitrary-code capability.

It does not decide whether the target date is an NYSE session, evaluate a
strategy, produce a proposal, arm a bot, or persist an approval. It is inert
contract material only.

### Source checkpoint

~~~text
branch      feature/robinhood-production-strategy-contract
checkpoint  arch134-production-strategy-contract
preflight   None
execute     None
~~~

The checkpoint's authority check pins the production model and its focused test
surface. It is source-only and gains no protected runtime capability.

## Subsequent production lane

### 134-C — Human-started production live-paper cycle

134-C composes the accepted 134-B decision with Architecture-131 supervised
review-paper PREPARE/EXECUTE. It does not reimplement strategy, quote, risk or
paper accounting logic.

`NO_SIGNAL` is a true zero-provider/zero-paper outcome. A trade proposal must
match the exact 134-B retained proposal and target session before PREPARE can
reach Architecture 131.

134-C is CERTIFIED/CLOSED at the source identity recorded above. PREPARE is
the shadow boundary: at most one quote acquisition and risk preview, with no
review order and no synthetic fill. `READY_TO_PROCEED` grants no execution
authorization. EXECUTE is separately authorized and is a distinct explicit
call allowed only from exact `READY_TO_PROCEED` preparation; it additionally
binds expected source HEAD/TREE to the production strategy contract and delegates
once to Architecture-131 execution.

Real broker order placement remains impossible and out of scope.

## 134-B — Production Strategy Decision Bridge

Consume an exact 134-A contract plus verified daily history/current bar and
authoritative paper-account state. Reuse existing strategy evaluation exactly
once and emit a closed result: `NO_SIGNAL` or the exact strategy
`TradeProposal`. No provider or paper mutation.

### 134-C — Human-started live-paper cycle

Compose 134-B with the accepted Architecture-131 live quote/risk/review-paper
path. Support a read-only shadow mode and one explicit paper mode. Paper mode
may call the already-qualified non-placement Robinhood review path and create
one local synthetic paper result. Broker placement remains impossible.

### 134-D — Armed session mode

Introduce `ARMED -> SESSION_OPEN -> RUNNING -> TERMINAL` control around one
target NYSE session. Operator arms before market; no early execution is
possible. Session timing is derived from published session authority, not a
hard-coded 06:30 offset. DST therefore follows the exchange calendar.

### 134-E/F — unattended proof

First qualify one unattended integration session, then a fresh multi-session
paper soak. These validate scheduling/restart/idempotency and operational
behavior, not strategy promotion.

## Research lane

Research is a later parallel source family. It should define explicit candidate
artifacts and lifecycle states such as:

~~~text
EXPERIMENTAL
BACKTESTED
WALK_FORWARD_PASSED
SHADOW
PAPER_CANDIDATE
AWAITING_HUMAN_PROMOTION
~~~

Research reuses existing historical experiments, optimization, backtesting,
analytics and walk-forward machinery. It can rank/recommend candidates but has
no API that returns or writes an armed production contract. Human promotion
creates a new production selection for a future session through a separately
reviewed boundary.

## Deployment

The simplified fixed-worktree deployment model remains in force. Architecture
134 does not revive STAGING/FINAL publication, AG/AJ retry, automatic code
deployment or self-modification.


## 134-B — Production Strategy Decision Bridge

134-B's original source-accepted entry point remains a **legacy compatibility
adapter** for Architecture-94 callers. It still accepts an exact
`ManualPaperStrategyDecisionRequest`, requires a genuine construction-protected
`VerifiedPriorCheckpoint`, and returns the same closed
`ProductionStrategyDecision` outcomes. That compatibility path is retained so
historical Architecture-94 plan/replay behavior does not regress.

It is **not** the current Robinhood production materialization path.

The accepted current-product path is Architecture 134-B2 below. Both the
historical adapter and the current Robinhood adapter enter the same extracted
pure daily-decision core, which evaluates the existing
`MovingAverageCrossoverStrategy` exactly once.

The closed production output remains exactly:

~~~text
NO_SIGNAL
TRADE_PROPOSAL
~~~

No adapter may substitute a research candidate, create broker authority, or
perform provider/OAuth/network/scheduler execution.

## 134-B2 — Current-product production-decision materialization

The original 134-B compatibility adapter accepts an Architecture-94
`ManualPaperStrategyDecisionRequest`; Architecture 134-B2 does **not** require
that legacy request or its protected prior authority. Retaining the compatibility
adapter does not make the historical personal-desktop Paper-v2/C3 runtime part
of Architecture 134 production authority.

Architecture 134-B2 is source accepted on the production live-paper branch. The
current Robinhood lane now materializes decisions from current-product evidence:

- exact 134-A production contract;
- verified daily snapshot/history evidence for the contract symbol/session;
- current synthetic-paper prior/account state derived from
  `ReviewPaperStore`;
- explicit deterministic planning/idempotency/policy inputs.

Architecture-94's `VerifiedPriorCheckpoint` is construction-protected authority
from the historical checkpoint-lineage system. The Robinhood adapter must
**never fabricate or synthesize that capability** from ReviewPaperStore.

134-B2 extracted/reuses the already-reviewed pure strategy-decision core beneath
the Architecture-94 request adapter. The existing Architecture-94 entry point
continues to validate/translate its legacy `VerifiedPriorCheckpoint`; the new
Robinhood entry point validates/translates independently verified
`ReviewPaperStore` state into a construction-protected current-product prior.
Both paths call the same pure decision core, which performs exactly one existing
strategy evaluation. The accepted 134-B closed `NO_SIGNAL` / `TRADE_PROPOSAL` contract
remains the production output boundary. It must not read
or repair D10/Windows/Paper-v2/C1/C3 personal-desktop state, use historical
Alpaca operational authority, or infer missing market history.

The materializer itself is source/provider-free. Real current market-history
acquisition/persistence remains the next source checkpoint and is separately
reviewed; it cannot be silently folded into SHADOW PREPARE.

A 2026-10-11 read-only diagnostic found a DACL mismatch only on
`F:\AITradingBot\Paper-v2` while its relevant descendants remained exact.
That legacy drift is not an Architecture-134 blocker and grants no ACL-repair
authority.


### 134-B2 accepted source

~~~text
BRANCH feature/robinhood-production-strategy-live-paper
HEAD   1e3c74649aeb6f0f90881b1495fec0350c22ae5e
TREE   b9ac7a11a39d07252ab85fd7b197b31590a825b9
CI     #478 / 38175971808 SUCCESS
~~~

The accepted implementation adds a current-product
`build_current_production_strategy_decision(...)` adapter, a read-only
`ReviewPaperStrategyPrior`, shared pure `daily_decision` logic, and provider-
free strategy-history primitives. The historical runtime history module is now
a compatibility export rather than the owner of the reusable history model.

Current profile inventory at this source is FULL **163**, ROBINHOOD **88**,
LEGACY **205**, EXHAUSTIVE **368**.

No separate broad certification is run at 134-B2. The pending ROBINHOOD
certification obligation is deliberately batched with the next current-history
acquisition/materialization checkpoint so that one coherent current-decision
source is certified exactly once before any protected SHADOW PREPARE.

## 134-B3 — Current Robinhood market-history evidence (CERTIFIED/CLOSED)

The current source checkpoint remains `arch134-production-strategy-live-paper`
on `feature/robinhood-production-strategy-live-paper`, with no preflight/execute
registration. B3 adds two owned test modules to that existing source gate;
active count stays 60. FULL/ROBINHOOD/LEGACY/EXHAUSTIVE inventory is now
165/90/205/370. Frozen required baselines remain 122/49.

B3 source/certification closeout:

~~~text
BRANCH      feature/robinhood-production-strategy-live-paper
HEAD        7ef32ec87dbcfeea4d5436c424cdbb0eb16e1058
TREE        738f078722337903ba7daf950bf19078167a75e4
CHECKPOINT  arch134-production-strategy-live-paper
CI          #482 / 38181823892 SUCCESS
~~~

The first ROBINHOOD certification on
`fde8cb35256e4448fef20e666f00b0d687b3f423` ran 8,269 cases and failed only
three stale current-profile inventory assertions. Its failed evidence is
preserved at:

~~~text
F:\AI\temp\certification\arch134b3-robinhood-4eaa0b0201cf43a19c420d00d5bbced5
~~~

The bounded test-only correction changed no production behavior, authority,
classification, topology or baselines. Final ROBINHOOD certification on the
exact HEAD/TREE above passed **8,269/8,269** cases across **90** modules:
robinhood-1 3,865/3,865 and robinhood-2 4,404/4,404, zero
skips/failures/errors, wall 325.912 s. Evidence:

~~~text
F:\AI\temp\certification\arch134b3-robinhood-b14f5add0e5040599b093c7238b01a54
~~~

No FULL/LEGACY/EXHAUSTIVE rerun and no protected provider/OAuth/paper/scheduler/
broker effect was required for B3 closure.


`RobinhoodDailyHistoryRequest` derives exactly `long_window + 1` consecutive
sessions through the exact bound XNYS calendar, checks them against the existing
NYSE published regular-session authority, and admits only completed sessions.
Published coverage remains 2026-2028; requests requiring earlier history fail
closed. The MCP range runs from the first regular open through the last regular
close. The only request is `get_equity_historicals` with one exact contract
symbol, explicit UTC bounds, `interval=day`, `bounds=regular`, and
`adjustment_type=none`. No interval/adjustment defaults, pagination, retries,
interpolation, alternate provider, CSV, quotes-as-history or inferred bars.

The strict parser requires the documented structured `data/results/bars` and
`guide` shape, one exact result, exact symbol/daily/regular semantics, all
required bar fields, explicit `session=reg` and `interpolated=false`, positive
integer traded volume and bounded positive decimal OHLC. Unknown fields,
missing/unresolved symbols, malformed/non-UTC timestamps, unknown/midnight
labels, duplicate/missing/out-of-order/nonconsecutive sessions, extra bars,
invalid OHLCV, split/dividend adjustment echoes or insufficient history fail
closed. Optional adjustment echo must be `none` if present. Bars must have
left-edge labels equal to the published regular opens; DST and early closes
are calendar-bound. No transformation or invented daily aggregation occurs.

`materialize_production_strategy_history` replays retained canonical structured
response bytes and checks exact contract symbol/config/session and capture time.
The prior completed session goes through existing snapshot acceptance,
serialization and `verify_daily_snapshot` to obtain
`DailySnapshotVerificationResult`. The snapshot audit hashes the canonical
structured response (not purported raw HTTP bytes). The preceding configured
consecutive bars go through `create_strategy_history_seed`, canonical
serialization and `verify_strategy_history_seed` to obtain
`VerifiedStrategyHistorySeed`. Existing history-seed schema, IDs, verifier,
`OFFLINE_SEED` classification and `authoritative=false` remain unchanged.
Provider provenance belongs to an outer `robinhood-strategy-history-evidence/v1`
envelope retaining request, structured response, XNYS session sequence and times.
Hashes are audit evidence only, never deterministic semantic identity material.
Canonical snapshot, seed and outer bytes are returned in memory; this checkpoint
adds no filesystem persistence or paper-store mutation boundary.

`acquire_production_strategy_history` permits exactly one adapter historical
read and one caller-injected capture-time observation. Production invocation
is separately protected; source tests inject fakes. The pure
`build_production_strategy_decision_from_history` replays all evidence and
delegates exactly once to accepted 134-B2. No legacy Paper-v2/D10/C1/C3/Alpaca
authority, `VerifiedPriorCheckpoint`, new evaluator, research promotion,
SHADOW PREPARE or paper execution is introduced.

The exact application read/review allowlist is now four public tools:
`review_equity_order`, `get_equity_quotes`, `get_equity_orders`, and
`get_equity_historicals`; `get_accounts` is private/internal. Capability
enumeration requires all four; extra advertised broker tools never become
application capabilities. Placement/cancel/options/crypto remain excluded.

B3 source/certification is closed. Real-server qualification remains the next
separately protected boundary. The published tool metadata documents raw
`none` request semantics but no required response adjustment echo; request
honoring must be qualified. Daily regular-open left-edge labels and explicit
false interpolation/regular-session flags must also be qualified. `close_price`
means the last trade in the regular daily bar, not an official settled close.
Any mismatch blocks materialization rather than weakening the parser. The
qualification may perform only the explicitly authorized read-only provider/OAuth
effect; persistence/operator wiring, SHADOW PREPARE, paper execution, scheduler
mutation and broker placement remain outside this closure.


## 134-B3Q — Source-owned historical qualification operator (SOURCE ACCEPTED / ROBINHOOD CERTIFIED)

B3's accepted parser, request, four-tool transport allowlist and materializer
remain unchanged. B3Q prepares the already scoped single read-only qualification;
source implementation/CI uses fakes only. This section is the current operator
path; earlier B3 closure statements describe the pre-operator source boundary.
It does not certify the live server or consume provider authorization.

The reviewed entry point is `scripts/qualify_robinhood_history.py`. Its only
operator inputs are exact expected source HEAD/TREE, an external fresh evidence
file, and a mode/interlock. There are no symbol/window/time/interval/bounds/
adjustment/account/provider arguments. Frozen v1 inputs are **SPY**,
**long_window=3** (four completed sessions), and a 2/3 moving-average config
used only for existing B3 materialization validation, never strategy evaluation.
The desired quantity `1` is a required config field, not an order or risk input.

One actual UTC clock observation supplies `requested_at`. The current New York
session date must be published by existing XNYS authority; weekends, holidays,
missing published coverage and insufficient predecessor coverage block before
OAuth. The request selects exactly the three predecessors plus the prior
completed session through `RobinhoodDailyHistoryRequest`. The resulting range
is first regular open through last regular close, with exactly `interval=day`,
`bounds=regular`, `adjustment_type=none` and `symbols=["SPY"]`. A pre-open
observation on a published session date is permitted. Capture must remain on
that same session date and follow both request and call-start observations.

Before OAuth, require exact clean tracked/untracked/index source, fixed feature
branch, fixed origin, local remote HEAD/TREE and live remote HEAD. Reject mixed
`trading_bot` import roots. Re-admit exact source after the response. No fetching,
branch repair or repository mutation belongs to the operator. Evidence must be
an absolute fresh path outside every repository worktree with an existing
parent. Exclusive creation rejects collision before OAuth/provider access.

`--preflight` is provider/OAuth/credential-free and writes no evidence. It checks
source/calendar/output readiness and reports the derived request; it grants no
call authority. Protected execution requires the exact interlock
`AUTHORIZE_ARCH134_B3Q_ONE_HISTORICAL_READ`. OAuth uses the accepted Windows
factory with source-owned `http://127.0.0.1:8765/callback` and a browser handler
that refuses interactive renewal. Persisted OAuth/session establishment and
MCP capability enumeration remain the accepted transport's responsibilities.

An enclosing transport exposes only `get_equity_historicals`, validates exact
request arguments, and delegates at most once. No `get_accounts`, quotes,
orders, review, placement, cancel, options, crypto, SHADOW PREPARE, store access,
paper fill, scheduler/runtime mutation or broker execution is invoked.
The four-tool allowlist and capability enumeration are not broadened. The raw
structured response goes through the unchanged `RobinhoodReviewReadAdapter`
and strict B3 parser, then unchanged `materialize_production_strategy_history`.
Missing explicit flags, timestamp labeling, adjustment/schema drift, gaps,
duplicates, reordering, extras and insufficient history remain failures.
No transformation, alternate parser, fallback provider or retry can make a
rejected live response pass.

Evidence is a canonical JSONL journal bounded to **64 KiB**. Each complete
record is flushed and fsynced. Reservation records `BLOCKED`/zero attempts;
before transport control, a durable `CALL_STARTED` record carries
`AMBIGUOUS_PROVIDER_EFFECT`/one attempt and the call-start timestamp. A
terminal record reports `PASS`, `BLOCKED`, `FAIL` or
`AMBIGUOUS_PROVIDER_EFFECT`, fixed reason, exact source HEAD/TREE/branch,
arguments, ordered session dates, request/capture timestamps, tool and attempt
count. Counts describe attempted transport-boundary calls, not proof that an
HTTP application request was sent. Any unclassified transport failure is
conservatively ambiguous, including a failure that may have occurred before
sending. Returned structured data rejected by B3 is `FAIL`. All failures stop;
none grants retry. Interruption or terminal publication failure leaves the
pre-call ambiguity fence. Partial/truncated evidence must never be called PASS.
Preserve it for read-only reconciliation and human review.

Only strict-parser-validated historical `data` is retained, plus `guide_present`
and hashes. Arbitrary `guide` text, malformed payloads, OAuth errors, credential
material, URLs/auth capabilities and account identifiers are never persisted;
provider stdout/stderr/logs/warnings are discarded. The SHA256 of the original
canonical complete response is audit-only. A separate digest binds the retained
canonical historical data. PASS evidence can be replayed with `--replay` through
the same parser/materializer without any provider/OAuth call. Since the free-form
guide is deliberately omitted, replay supplies a fixed nonblank disclosure only
after checking canonical PASS evidence, source identity, ordered journal,
arguments, sessions, capture ordering and retained-data digest. It neither
reconstructs the original guide/snapshot audit bytes nor claims to verify the
original full-response hash. All historical fields remain exact; this sanitized
evidence replay cannot serve as a live-response fallback or strategy authority.

B3Q belongs to existing `arch134-production-strategy-live-paper` registration.
The registered source gate includes the new fake-only test module, CLI/operator
Ruff paths and source/AST authority pins. `preflight=None`, `execute=None` stay
unchanged: the CLI is the explicit separately reviewed protected surface, never
an `ops.ps1 execute` effect. No workflow/topology/checkpoint-family change is
needed. Active inventory stays **60**; FULL/ROBINHOOD/LEGACY/EXHAUSTIVE now
**166/91/205/371**, required baselines unchanged **122/49**. Implementation runs
focused checks only; no broad profile certification or real call is performed.

Exact GitHub review accepts B3Q source at
`2a11a2597a2edad8351e50a25d9454420318089f` /
`80b16dd877c0c5a56f5572922d3fa4c77e940f4d`; push-triggered source gate
#484 / 38190487015 is terminal SUCCESS. No source correction is required.

The selected ROBINHOOD certification passed on the exact final
docs-only source `473b18ce4cbc2ff9c7d4f793d7ae4e316e585471` /
`f7ffc107f9f9206e857049dd9ea178ec612a0c26`: robinhood-1 passed
4,027/4,027 across 45 modules; robinhood-2 passed 4,310/4,310 across
46 modules; total **8,337/8,337**, zero skips/failures/errors, wall
272.922 s. Evidence is preserved at:

~~~text
F:\AI\temp\certification\arch134b3q-robinhood-1a7d9742efd3439797c3ed713837e29c
~~~

No FULL, LEGACY or EXHAUSTIVE run is selected.

The previously granted user authorization for exactly one read-only
`get_equity_historicals` qualification remains valid and unconsumed. The next
action is the provider/OAuth-free B3Q preflight on this exact final source. If
preflight passes on a published XNYS session date, ChatGPT may consume the
existing one-read authorization without another approval round because the
reviewed effect scope is unchanged. Any preflight failure, live FAIL or
AMBIGUOUS_PROVIDER_EFFECT is a STOP with no automatic retry and no later SHADOW
PREPARE, paper execution, scheduler mutation or broker authority.

### B3Q real-server qualification result — AMBIGUOUS / NO RETRY

The single authorized live qualification was consumed on
`5f2728bb409ef479475619100cba3fb1fdac18f5` /
`a51c7aed8a1697b88dbdbc732b863eb5932c4ef9` after provider-free preflight
PASS. Preserved evidence:

~~~text
F:\AI\temp\qualification\arch134b3q-history-19c8c572a3d8447f9488cb5d3a11f4db.jsonl
~~~

The journal reached the durable `CALL_STARTED` fence and then terminated
`AMBIGUOUS_PROVIDER_EFFECT / CALL_RESULT_UNCLASSIFIED` with one
transport-boundary attempt. No structured response returned to the B3Q wrapper:
`captured_at`, retained response and both response/data digests are null.
Accordingly, the observed failure is below the strict B3 parser/materializer
boundary. It remains impossible from this evidence to prove whether an MCP
application request was actually sent or received.

The authorization is consumed and no retry is permitted. Do not manufacture a
new evidence destination, repeat `get_equity_historicals`, downgrade the
ambiguity to FAIL, or weaken accepted parsing semantics. The next safe source
checkpoint is a provider-free/read-only reconciliation diagnostic for preserved
evidence plus local dependency/OAuth readiness. Any actual credential access or
provider call remains outside that source-only checkpoint and must use its own
reviewed authority. 134-D Armed Session Mode design/source work may proceed
independently on a separate branch.


## 134-D1 - Current-product Alpaca bridge and manually armed paper session

This section records the historical D1 source contract. D1Q below supersedes
its deliberate credential-binding stop, host branch and next-step sequence;
the preserved D1-only descriptions are historical provenance.

This is the current MVP source direction and supersedes the product dependency
on B3 historical acquisition, without changing retained B3/B3Q authority or
retrying its ambiguous incident. Historical docs remain historical. Source
acceptance, broad certification and protected native qualification are separate.

Historical authority is the existing immutable Alpaca raw/USD/SIP/1Day/no-asof
provider and one-attempt HTTPS/strict JSON implementation, composed by
`review_paper/alpaca_strategy_history.py`. Derive exactly `long_window + 1`
predecessors from the exact ProductionStrategyContract and source-owned XNYS
calendar, and require every date plus the target date to exist in the published
NYSE manifest. The MVP bounds long_window to 252. Fetch each predecessor exactly
once in caller-visible chronological order. Each request has exactly the
contract symbol, one session, limit=1, adjustment=raw and no pagination follow-up.
Older request timestamps are explicit calendar-selector anchors (midnight on the
following local calendar date); they are not actual acquisition observations.
Every retained audit captured_at is the real post-response provider observation,
nondecreasing and within the armed target date. The final request uses actual
acquisition requested_at. No verification object or legacy prior capability is
fabricated: all bars pass acceptance, canonical serialization/offline verification
and the unchanged strict history-seed verifier. The seed remains OFFLINE_SEED and
non-authoritative; provenance belongs to the verified Alpaca snapshots.

The lifecycle is closed: ADMITTED, HISTORY_STARTED, HISTORY_READY, NO_SIGNAL,
WAITING_FOR_MARKET, PREPARING, READY_TO_PROCEED, EXECUTE_STARTED, PAPER_EXECUTED,
RISK_REJECTED, SESSION_NOT_ADMITTED, SESSION_EXPIRED, BLOCKED, ALREADY_COMPLETED.
The initial atomic reservation precedes history. Every read gets a durable
HISTORY_STARTED fence; PREPARING precedes quote composition/control and
EXECUTE_STARTED precedes execution control. SQLite uses synchronous=FULL,
timeout=0 and compare-and-swap publication. No persistence conflict is retried.
There is no ownership lease, expiration/reclaim or automatically resumed attempt.

A new ARM interlock authorizes one combined session under its exact contract and
source; it is not inferred from READY_TO_PROCEED. It consumes its in-memory ARM
before one EXECUTE attempt. The durable symbol/session key prevents another ARM,
including another contract/source version, from executing that same session.
The result/order UUID5 uses versioned length-framed contract semantic material;
filesystem identities/artifact bytes/clocks are not result-identity material.
An interrupted fence remains blocked, even when the process failed before a
provider request was proven sent. A matching NO_SIGNAL/PAPER_EXECUTED may report
ALREADY_COMPLETED; the latter also requires its exact durable order/fill.
An existing symbol fill on the target session date blocks a new reservation's
provider path. No multi-session catch-up or historical-ID reconstruction exists.

The clock/sleeper and inert provider factories are injected/testable seams owned
by the host. There is one sleep to published open plus buffer, no busy loop, no
CLI semantic time and no second sleep if the wake is early. Source drift blocks;
wrong-date/late wake expires. PREPARE's non-READY outcomes never call EXECUTE.
The unchanged Architecture-131 path retains quote freshness, source/session/risk/
predecessor revalidation, review echo, bounded account/order-history reads and
local synthetic ReviewPaperStore fill. D1 owns no second order/risk engine and
no additional quote after PREPARE. No broker placement/cancel/options/crypto,
margin/short/live, research-selected strategy or historical operational authority
is admitted.

Budgets per fresh admitted attempt: Alpaca exactly long_window+1 on a successful
history path (stop at first rejected/ambiguous read), one B2 evaluation, one
SHADOW PREPARE with at most one quote read, at most one paper EXECUTE. EXECUTE
retains the accepted account resolution budget of one, one review, and at most
100 successful pages on each side of review (the accepted 101st-page stop can
consume a failing attempt; conservative total attempt bound is 202). Paper fill
budget is one. Robinhood historical and broker-mutation budgets are zero.
Counts are attempted boundary invocations, not proof an application request was
sent. Incomplete execution counts remain marked unknown, never inferred zero.

The source-owned `scripts/run_production_paper_session.py` accepts only expected
HEAD/TREE, a fresh external evidence destination, --preflight or the exact ARM
interlock. The operator selects no symbol/window/provider/endpoint/price/side/
quantity/session/time. V1 host configuration is SPY, crossover 2/3, quantity 1,
$10,000 synthetic starting cash, existing RiskLimits defaults, five-minute
opening/closing buffers and one-minute quote freshness. Its fixed runtime root
is `F:\AITradingBot\Arch134D1`; existing qualified paper.sqlite is required.
Source admission requires exact clean source/import roots/origin/cached and live
remote identity. It never repairs source. An absent dedicated bytecode namespace
prevents reading ignored cached trading code. Preflight is provider/credential/
paper-write free and cannot grant runtime authority.

The retained native Alpaca credential reader cannot be reused without importing
C1/C3 operational authority. Therefore `create_current_product_alpaca_provider`
is deliberately a narrow fail-closed seam for later reviewed native binding;
it currently raises ALPACA_CREDENTIAL_BINDING_NOT_QUALIFIED. No generic plugin,
environment credential reader, filesystem history substitution or alternate
provider is supplied. D1 source does not represent a qualified production launch.
Do not work around this stop with legacy credentials/authority. Native secret
binding and existing runtime/store qualification remain explicit later boundaries.

The 32-KiB canonical terminal export and full-synchronous durable state use a
closed field set: source/contract/session, exact historical dates/provider,
strategy/proposal, wait/admission, PREPARE/EXECUTE, operation/order/fill identities and canonical snapshot/seed digests,
provider/tool attempt counts, mutation count and terminal classification. Unknown
fields/free-form text, credentials/OAuth URLs, arbitrary exceptions and reusable
capabilities are rejected. Interrupted publication preserves the last pre-effect
state. Exports are exclusively created and fsynced; state is authoritative if an
export cannot be published.

Registration is arch134-armed-paper-mvp on
feature/robinhood-production-paper-mvp; preflight/execute remain None. D1 is
inserted before the frozen final 134-A/B/C batch tail, preserving those exact
assertions. The existing reviewed feature/robinhood-* trigger provides first-push
bootstrap. D2 now follows the ON/OFF supervisor end-state frozen above, with
arbitrary-time startup and no wake-from-sleep requirement. Protected
credential/runtime/manual-session acceptance precedes any scheduled effect.


## 134-D1Q - Fixed current-product runtime and credential qualification

D1Q supersedes D1's deliberate Alpaca binding stop, preserving SPY, MA 2/3,
10000 synthetic starting cash and the existing four historical reads,
reservation-before-composition fence, quote-only PREPARE and local synthetic
EXECUTE. The controller is unchanged. The host pins
`feature/robinhood-production-paper-runtime`.

The standalone `review_paper/alpaca_windows_credentials.py` uses only
CredReadW/CredFree for two fixed generic/local-machine records:

- `AITradingBot/MarketData/Alpaca/ApiKeyId/v2`
- `AITradingBot/MarketData/Alpaca/ApiSecretKey/v2`

Strict nonempty UTF-8 is bounded to 1024 bytes with no surrounding whitespace,
CR/LF/NUL. Native memory is zeroed before freeing within the validated Windows
2560-byte range; temporary bytearrays are cleared on all pair paths. Cleanup
failure blocks. Errors and scope repr/str are redacted. Immutable Python strings
cannot be guaranteed zeroized; scope references are dropped on exit and only
the existing provider retains credentials for its short-lived history use.
The existing factory's `environment` parameter receives only the two validated
in-process values; no process environment is consulted. No legacy C1/C3 import,
arbitrary target, alternative HTTP client or fallback is admitted.

`production_paper_runtime.py` owns exactly `F:\AITradingBot\Arch134D1` and
`paper.sqlite` / `armed-sessions.sqlite`. Preflight validates nonsecret metadata
and read-only SQLite schema/integrity, schema version 2, exact cash 10000,
canonical paper reconstruction and canonical session evidence. It reports
ABSENT / PRESENT_COMPATIBLE / BLOCKED without writes. Symlink/reparse metadata,
hardlinked stores, extra files including SQLite sidecars, incomplete stores and
incompatible state block. Fresh provisioning exclusively creates the root and
stores, with full SQLite synchronous durability and writable-handle file flush.
The parent `F:\AITradingBot` must already exist; no parent provisioning or
fallback is introduced. Failed/partial material is preserved and blocks repeat
attempts until separately reviewed. Compatible nonempty stores are preserved
and report bounded paper/reservation counts. No durable probe reservation is inserted.
ReviewPaperStore adds read-only opening with unchanged default behavior;
ArmedSessionStore exposes initialize/qualify without reserving.

`scripts/qualify_production_paper_runtime.py` accepts only exact HEAD/TREE and
`--preflight`, or `--qualify` with the exact interlock
`QUALIFY_ARCH134_D1Q_RUNTIME_AND_FIXED_CREDENTIAL_READINESS` plus a fresh external
`--evidence`. Exact source/import/origin/cached and live remote admission precede
runtime/credential effects. Preflight has zero credential/provider/paper/runtime
write/scheduler/broker effects and writes no evidence. Protected qualification
exclusively reserves bounded sanitized evidence, provisions/validates stores,
proves rollback-only native write readiness on both fixed stores as specified
by D1Q-R1 below, reads exactly two Alpaca records, and reuses the reviewed Architecture-133
`persisted_oauth_availability()` (two fixed read-only records, no SDK/client,
refresh/browser/MCP composition). Success requires both stores to report
WRITE_READY and reports READY_FOR_MANUAL_PAPER_SESSION,
two Alpaca and two OAuth reads, and zero HTTP/application/fill/scheduler/broker
calls. Read failures retain uncertain counts as null with incomplete evidence.
Qualification is evidence only and grants no manual-session authority.

Registration is `arch134-production-paper-runtime`, appended once with
preflight=None and execute=None. Its exact source/import closure includes
credentials, runtime, CLI, host/controller/stores, existing Alpaca provider/HTTP,
OAuth verifier, strategy/PREPARE/EXECUTE dependencies and focused tests.
Forbidden environment/credential mutations, legacy/research imports, provider
expansion, historical Robinhood/MCP calls, broker and scheduler expansion fail
closed. The explicit CI mapping is robinhood; feature/robinhood-* supplies
first-push bootstrap. Source-discovered normative inventory is ACTIVE 62, FULL
168, ROBINHOOD 93, LEGACY 205, EXHAUSTIVE 373. The active tuple AST digest is
refrozen deliberately. CI owns canonical ROBINHOOD; full-tests and local profile
reruns are excluded on this mapped path. Real qualification and the subsequent
manual session each require fresh authorization. D2 follows only after manual
session acceptance; B3Q remains consumed/no-retry.

### 134-D1Q-R1 - Native runtime write-readiness hardening

Readable, compatible schemas are insufficient readiness evidence. Native Windows
qualification discovered that BEGIN IMMEDIATE could succeed while the first
INSERT returned SQLITE_READONLY. That earlier READY result is superseded and
does not authorize a manual session.

Protected qualification now opens each fixed database with SQLite mode=rw,
timeout=0 and synchronous=FULL under the exact current process/account. No
impersonation, elevation, alternate VFS, migration or repair is admitted. The
existing DELETE journal mode is required without changing it. Each probe performs
BEGIN IMMEDIATE, a harmless INSERT, exact readback and explicit ROLLBACK. The
paper probe inserts only a nonsemantic sentinel into existing metadata, never a
paper trade. The session probe inserts a non-session sentinel key and bounded
nonsemantic blob into the existing reservation table. Neither sentinel is
committed; no persistent schema is created. Existing probe-key collisions block.

After close, a separate ordinary mode=ro connection verifies the exact schema,
schema version, semantic count, sentinel absence and integrity. Fixed path/content
admission and both canonical store reconstructions/counts are checked again.
Read-only handles, journal/write denial, lock contention, readback failure,
rollback/close failure, leftover sidecars or changed inventory fail closed.
Partial/incompatible material is preserved, including unexpected SQLite sidecars;
qualification never cleans or repairs it.

Sanitized evidence adds paper_store_write_readiness and
session_store_write_readiness, each NOT_CHECKED, BLOCKED or WRITE_READY. Both
must equal WRITE_READY before credential readiness or READY. Evidence contains
no ACLs, principal/SID/user data, arbitrary paths or native exception strings.
Transient native journal writes are qualification effects, not paper fills or
durable reservations. Credential/provider boundaries and fixed cash, strategy
and paths are unchanged.

Read-only runtime and host preflight remain compatibility observations and report
NOT_CHECKED for write readiness. Armed host startup repeats both rollback probes
under its own process/account before store construction, durable reservation or
provider composition. A prior qualifier's privileges or evidence never transfer
write authority to a later process. Probe success is a point-in-time observation;
later drift still fails through the existing store/controller boundaries.

The qualifier has no Windows security-mutation authority. Fixed-store file write
and parent-directory journal creation/removal rights must be provisioned for the
intended runtime principal by a separately reviewed administrator/operator design.
Read/execute rights or directory creation by a privileged process alone do not
establish that authority. No existing production ACL, ownership or file attribute
is changed by this checkpoint. Real qualification and ARM remain separately
authorized; source tests use only isolated temporary stores and fake credentials
and providers. Canonical ROBINHOOD runs once through the existing mapped CI path.


### 134-D1Q-R2 - Fixed current-product runtime-principal ACL provisioning

The accepted R1 source is HEAD 6bf8753b0cc8950ae27b32b6858b64d454c512f0,
TREE ce3feb2ac48e7aebc23970142aafed5059c447e7, on the unchanged runtime branch.
R2 is a new isolated branch/checkpoint, not a qualifier/host security-mutation
extension. R1 rollback-only native probes and their authority prohibitions remain
unchanged. `production_paper_runtime_acl.py` and its standalone source-owned CLI
are inert on import; diagnosis performs only source/token/object observations.

Exactly three security targets are admitted:
`F:\AITradingBot\Arch134D1`, its `paper.sqlite` and `armed-sessions.sqlite`.
The native helper's old fixed-authority opener retains its prior allowlist and
sharing behavior. A separate fixed-three-target opener reuses the same native
CreateFileW implementation with OPEN_EXISTING, OPEN_REPARSE_POINT and directory
BACKUP_SEMANTICS. Root handles deny delete sharing; database handles deny write
and delete sharing. All three are pinned before admission/mutation. Inspection
reuses final-path/reparse/kind/NTFS/security primitives and adds local-fixed-drive,
same-volume serial/file-index identity and single-link database checks.
Only a bounded nonrecursive inventory of the root is observed; extra children,
sidecars or inventory ambiguity block. No parent/sibling/ancestor is opened for
security mutation or enumerated. The deliberately inaccessible parent remains
untouched; no traverse permission is provisioned there.

Owner must be Administrators. Diagnosed state is unprotected with exactly the
ordered explicit allow ACEs Administrators FILE_ALL_ACCESS, SYSTEM
FILE_ALL_ACCESS, and a structural S-1-5-5-X-Y logon-session SID with exactly
0x001200A9 RX/synchronize and zero ACE flags. All three objects must share that
diagnosed class/logon SID, or all must match the exact target policy for the
current token user SID. Additional ACEs, inherited flags, a different owner,
wrong path/kind/volume/link state, duplicate identity, or a mixed/partial state
block without reconciliation/repair. No ephemeral logon SID or machine-specific
user SID is embedded in source.

Both database target policies are Administrators-owned, DACL-protected, with
exact ordered explicit allow ACEs Administrators/SYSTEM FILE_ALL_ACCESS and
runtime user `sqlite_trading_file_rights()` (0x0012019F), zero flags. Runtime
DELETE/WRITE_DAC/WRITE_OWNER are absent. Each protected file excludes the root's
journal-delete inheritance.

Root policy is Administrators-owned and DACL-protected, with Administrators and
SYSTEM FILE_ALL_ACCESS. Its runtime-effective ACE is exactly 0x001200AB:
FILE_TRAVERSE, FILE_LIST_DIRECTORY, FILE_ADD_FILE, FILE_READ_EA,
FILE_READ_ATTRIBUTES, READ_CONTROL, SYNCHRONIZE. It contains no DELETE,
FILE_DELETE_CHILD, FILE_ADD_SUBDIRECTORY, WRITE_DAC or WRITE_OWNER.
A distinct runtime ACE has sqlite file rights | DELETE (0x0013019F), flags
OBJECT_INHERIT_ACE (0x01) | INHERIT_ONLY_ACE (0x08). No CONTAINER_INHERIT_ACE
is granted. It is ineffective on the root and becomes effective on new child
files. The shared descriptor builder admits only its prior zero flags or this
specific 0x09 combination; deny/other inheritance flag combinations still block.
Constants and behavior use the reviewed AddAccessAllowedAceEx/GetAce helpers and
[Microsoft ACE inheritance rules](https://learn.microsoft.com/en-us/windows/win32/secauthz/ace-inheritance-rules).
Protected child files prevent SetSecurityInfo's inheritable-ACE propagation from
adding journal DELETE rights to existing databases.

CLI accepts exact expected source HEAD/TREE and either `--diagnose` (no elevation,
no evidence, no expected SID argument) or `--execute` with exact interlock
`PROVISION_ARCH134_D1_RUNTIME_ACL_FOR_CURRENT_TOKEN`, fresh external `--evidence`
and explicit `--expected-runtime-sid`. Protected execution first requires an
already elevated administrator-authorized token and equality with the reviewed
`resolve_current_token_sid()`. Alternate-administrator elevation blocks. User
SIDs must have the Windows account SID class S-1-5-21-...; no display-name lookup,
impersonation, arbitrary-principal grant or self-elevation is supplied.
Source admission proves exact clean branch/head/tree/origin/cached and live
remote plus tracked imports from one source root, with no Git optional-lock
index refresh. The standalone launcher uses the existing absent no-pycache
namespace and disables bytecode writes/reads from normal ignored caches.

After immediate repeated before-state observation, the only apply order is
paper.sqlite -> armed-sessions.sqlite -> root LAST. A policy is applied once,
then checked on the SAME pinned handle with unchanged identity. Before root
apply, both database DACLs are already protected. Failure before root completion
therefore leaves the runtime without newly granted journal-create authority.
After all applies, every handle is deterministically closed once, all three
targets are freshly reopened, and exact policies/identities are independently
verified. Already-exact state returns ALREADY_PROVISIONED/PASS with zero applies.
Any failure after even the first attempted native apply is conservatively
STOPPED_AFTER_APPLY. Close ambiguity is terminal. No rollback, retry, second
SetSecurityInfo on a target, deletion, schema write or repair is attempted.

Evidence is exclusively reserved outside source worktrees and F:\AITradingBot,
validated against redirection, flushed before native work, and fsynced with a
conservative STOPPED_AFTER_APPLY marker before each attempt. A crash/interrupted
or missing final publication is incomplete evidence and requires reconciliation.
Only fixed statuses/result, versioned bounded SHA256 runtime SID digest, apply
attempt/verified counts and zero non-ACL-effect counters are retained. No raw
SID, username, ACL dump, arbitrary path or raw native error reaches evidence.

`arch134-production-paper-runtime-acl` is source-only (runner preflight/execute
None), mapped explicitly to canonical robinhood CI and bootstrapped by the
existing feature/robinhood-* push family. Exact source/import closure includes
the native helper's inert reviewed transitive imports, fixed CLI/operator and
test module; independent AST pins protect target restrictions, token binding,
masks/order/flags and effect confinement even when a blob pin is refreshed.
Security mutation remains prohibited in production_paper_runtime.py and
armed_session_host.py; no provider/network/credential/scheduler/broker or SQLite
semantic-write authority is added. Current active/profile inventory is
63/169/94/205/374 (ACTIVE/FULL/ROBINHOOD/LEGACY/EXHAUSTIVE).

After source acceptance the protected operator sequence is diagnosis, separately
authorized elevated ACL provisioning under the same account, separately
authorized non-elevated R1 qualification, then separately authorized manual
session. This checkpoint performs none of those production effects, qualification,
ARM, scheduler installation, source deployment or broker placement. Native fixed
root/elevated acceptance and non-elevated real SQLite readiness remain pending.


R2 CI #503 at f496116 / 290af91 passed source-static/active tests but failed
canonical ROBINHOOD on twelve stale topology assertions. The bounded local
correction adds COMMON_TESTS and affected strategy inventory modules to the
dedicated source-only test selection and updates exact current count/order/branch
test assertions and test pins. ACL policy, token binding, native mutation and
R1 executable authority are unchanged. R2 has no source acceptance yet. Another
normal correction commit/push received fresh explicit user authorization after
the task's one-commit/push allowance was consumed. Require terminal fresh mapped
CI and exact GitHub review on the corrected source before any protected operator
acceptance; source publication never grants that protected effect authority.
