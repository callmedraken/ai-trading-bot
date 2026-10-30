# AI Trading Bot — Project Status

## Current checkpoint — Architecture 147 P2 acquisition bridge source

Architecture 147 is the controlling current product roadmap for the private
single-user Windows desktop bot. P1 is accepted and integrated at
`e8817e0214074b03d3d9ecd73232b7a2379276b9`, tree
`6937032602b9524ee9db0ddd2056463d418c3aef`. Feature #807 / run
41022636717 / attempt 1 succeeded with canonical FULL. Develop #808 / run
41023791454 / attempt 1 succeeded with `DEVELOP_CERTIFICATION_REUSE=True`,
`REASON=exact_feature_certification`, `IDENTITY_STABLE=True`, `OVERALL=PASS`.
P1 provides
ordinary create-only local research storage, an OPEN-only loader, and an
explicit final-holdout loader gated by the existing Architecture-145
`ResearchStrategyFinalHoldoutAdmission`. The current checkpoint is
`arch147-desktop-research-profile` on
`feature/research-desktop-product-pivot-current`; it has no preflight and no
execute dispatcher and maps to GitHub-owned FULL.

The desktop research root is the source-owned fixed path
`F:\AI\ai-trading-bot\data\research\desktop-v1`. P1 tests use only an
explicit temporary-root seam. No production root is created by implementation
or tests. The storage profile has no ACL, identity, elevation or protected
custody requirement, never overwrites a completed file, validates exact bytes
and readback, leaves incomplete state visible, and has no namespace-promotion
operation.

P2 feature CI #809 is preserved green pre-correction source evidence, but exact
source review rejected that candidate as
`ARCH147_P2_PREMATURE_COMPLETE_MARKER_DEFECT`: `COMPLETE` could be recorded
before `evidence.json` was durably materialized. This bounded corrective child
moves evidence into the desktop OPEN materialization before the kernel records
completion. Real acquisition is `NOT_RUN`; no Architecture-146 preflight is
restored.

P2 adds the desktop interactive Alpaca research acquisition bridge as another
atomic source milestone of the same checkpoint, branch, and GitHub-owned FULL
mapping. This source checkpoint performs zero real provider effects. It reuses
the frozen SPY/SIP historical Market Data requests and acquisition kernel;
Alpaca is solely the research-data source. Robinhood MCP / Agentic Trading
remains the future brokerage execution/account boundary.

The future explicit command verifies canonical develop/source/origin and
tracked/index cleanliness, accepts the published 2718-session authority, and
requires the desktop root absent before creating ordinary storage and hidden
interactive credentials. It never retries a partial root or falls back from
SIP. A completed dataset receives read-only full integrity verification and an
OPEN-loader check; the result contains non-price metadata only. Strategy
FINAL_HOLDOUT access retains the Architecture-145 admission gate.

The normal product update model is user Start -> unattended trading/research
workers -> user Stop -> reconcile/close -> manual update while stopped ->
checks/migration -> user Start. The running application never self-updates;
Task Scheduler/start-at-login and old release/install machinery are optional
future convenience or deferred hardening, not current readiness gates.

P1 has no provider, credential, Robinhood, paper, broker or live effect. LIVE
remains disabled. The consumed Architecture-146 observer and its
`HOST_UNKNOWN` evidence remain historical evidence only and were not retried;
the observer is not the current research dispatcher or next host action.

P1 candidate `51c959ed80be8b658d45f8358bb73795ffab7047`, tree
`bcf8e1d0be1237bdd08a0f03b4c8c79ef6276110`, remains preserved failed
evidence: CI #806 / run 41019120148 / attempt 1 ended FAILURE. Source-static,
active-tests and FULL broad-1 through broad-6 passed; broad-7 had 2265 passed
and 2 failed. Classification: `PREPUBLICATION_COVERAGE_DEFECT`, caused by
stale mixed-current assertions in
`tests/experiments/test_historical_research_partial_state.py`. #806 was not
rerun; no protected or external effects occurred.

## Accepted integrated foundation

Architecture 146's custody ACE multiset and tracked-only B2 source-binding
corrections are accepted and integrated on `develop` at
`f2a78e3c82058f3aee6d3d7145bbd9a8f00e2369`, tree
`7d9d3898b0c802780617e9f1f397338fe0fc96d3`.

The first tracked-only successor candidate,
`d346c6d13f2292c4c6b421a0abe29f284da2675c`, tree
`e074bfed3c8b528d4c8e9bcf7441aa4f45f0b314`, remains immutable failed
evidence. Feature CI #799 / run 40954098370 / attempt 1 failed only because the
new fake runtime-seam test retained the fixed production `SOURCE_WORKTREE`
while GitHub ran from `D:\a\...`. It was not rerun or rewritten.

The bounded portability child `f2a78e3c82058f3aee6d3d7145bbd9a8f00e2369` / tree
`7d9d3898b0c802780617e9f1f397338fe0fc96d3` changed only the fake test seam and coordination/validation
docs. Feature CI #800 / run 40971719167 / attempt 1 was terminal SUCCESS:
source-static, active-tests, source-gates and FULL broad-1 through broad-7 all
passed. Develop CI #801 / run 40974190116 / attempt 1 was terminal SUCCESS on
the exact same SHA and used
`DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`; active tests
and FULL lanes were correctly skipped.

The production B2 source-cleanliness rule is exactly tracked/index-only:

    git status --porcelain=v1 --untracked-files=no

Permitted unrelated generated/untracked artifacts and historical pytest
permission-warning directories remain preserved state and are not a
source-cleanliness failure.

No new host observation occurred during either correction, certification or
integration. The previously observed partial host state remains evidence only
and has not been re-inspected.

## Preserved research foundations

Published authority remains exactly 2718 sessions:
`nyse-published-regular-sessions-2016-2026-v1`, digest
`7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1`.
Model minus published remains exactly 2018-12-05 and 2025-01-09; reverse delta
is empty. Architecture 146-A behavior, global modeled calendar, request
descriptors and custody roots remain unchanged. `ACCEPTED_CUSTODY_ADMISSIONS`
is empty.

PRE-B2 #1/#2/#3 and the parent-provisioning/binary-ACL chronology remain
immutable consumed evidence. Architecture 134 R3 remains parked at
`BLOCKED / HOST / HOST_UNEXPECTED_PRIVILEGE`; no retry or R4. LIVE remains
NO-GO.

## Current roadmap

    P1  desktop research simplification
    P2  one real SPY acquisition + verification + freeze
    P3  real optimizer / walk-forward campaign + Research Results GUI
    P4  long-running desktop supervisor with concurrent trading + research workers and GUI Start/Stop
    P5  unattended synthetic/forward paper soak using existing Robinhood MCP review/quotes/history/account foundations
    P6  explicitly armed tiny restricted live through official Robinhood MCP / Agentic Trading
    P7  production maturity / soak / monitoring / backup / restart / reconnect / credential rotation

Trading and research may operate concurrently after P2. Local deterministic
strategy and risk remain authoritative; Robinhood MCP is the future brokerage
transport/execution boundary, not strategy authority. P1 does not enable real
mutation, OAuth, account queries, order review or order placement.

The immediate next step is ChatGPT exact-source review of the P2 committed
candidate and terminal mapped CI result. After source acceptance, fast-forward
integration and develop verification, automatically provide the single reviewed
real SPY acquisition command pinned to the accepted HEAD/tree. The user enters
hidden Alpaca research credentials locally. No Architecture-146 observer or B2
preflight is a prerequisite. Review sanitized dataset evidence immediately after
that one run, then continue to P3 optimizer/walk-forward work if integrity passes.
Do not run real acquisition during P2 implementation, admission or CI.
