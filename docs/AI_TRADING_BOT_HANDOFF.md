# AI Trading Bot — Current Handoff

## Current boundary — Architecture 147 P2 source-only bridge

Architecture 147 is the controlling current product roadmap for the private
single-user Windows desktop bot. P1 is accepted/integrated at
`e8817e0214074b03d3d9ecd73232b7a2379276b9`, tree
`6937032602b9524ee9db0ddd2056463d418c3aef`. Feature #807 / run
41022636717 / attempt 1: SUCCESS / canonical FULL. Develop #808 / run
41023791454 / attempt 1: SUCCESS, `DEVELOP_CERTIFICATION_REUSE=True`,
`REASON=exact_feature_certification`, `IDENTITY_STABLE=True`, `OVERALL=PASS`.

The current P2 source objective is the desktop interactive Alpaca research
acquisition bridge on
`feature/research-desktop-product-pivot-current`, checkpoint
`arch147-desktop-research-profile`, with `preflight=None`, `execute=None`, and
GitHub-owned canonical FULL. Its fixed production root is
`F:\AI\ai-trading-bot\data\research\desktop-v1`; implementation and tests use
only an explicit temporary-root seam and do not create that production root.

P1 uses ordinary create-only filesystem storage, preserves the Architecture
146-A dataset/session identities, exposes only validated OPEN data to ordinary
research, and requires the existing Architecture-145
`ResearchStrategyFinalHoldoutAdmission` for explicit FINAL_HOLDOUT loading.
The optimizer and walk-forward path cannot import the final-holdout loader.
P1 has no provider, credential, Robinhood, paper, broker, or live effect.
Local deterministic strategy and risk remain authoritative; official
Robinhood MCP / Agentic Trading is the future brokerage transport boundary.

P2 retains the frozen SPY request window (2016-01-01 through 2026-10-24), raw
SIP daily bars, full-range corporate actions, and published 2718-session
authority. The new one-use credential adapter binds the externally reviewed
HEAD/tree and accepted authority, then uses the existing hidden terminal input.
No token/elevation check or old B2 admission is involved. Exact local develop,
canonical root/origin, tracked/index cleanliness and origin/develop identity
precede all writes, prompts and requests. A preexisting desktop root, including
an empty or incomplete root, stops the command without cleanup or retry.

P2 source/tests/admission/CI perform zero real provider effects. Fake tests use
only temporary desktop roots. Full persisted integrity inspection reads both
partitions internally and returns immutable non-price metadata; it grants no
strategy holdout admission. Evidence is persisted as `evidence.json`.

The consumed Architecture-146 observer evidence remains historical and was not
retried. Its `HOST_UNKNOWN` result is not the current research dispatcher or
next host action. The next safe step is focused verification, exact-file
staging, one atomic P2 commit, FEATURE + PROSPECTIVE_DEVELOP admission, one push,
and one terminal mapped CI run, followed by ChatGPT exact-source review.

After acceptance/integration and develop verification, the automatic next action
is the single reviewed real SPY acquisition, with no intervening Architecture or
security/preflight checkpoint. Future command shape (not executable authority
until source acceptance/integration):

    .\.venv\Scripts\python.exe -B scripts\acquire_desktop_research.py --execute --expected-head <accepted-head> --expected-tree <accepted-tree>

Run from `F:\AI\ai-trading-bot` on exact clean develop. The user enters Alpaca
research credentials at hidden terminal prompts. Return only the compact JSON
result. SUCCESS requires `OPEN_LOADER=PASS` and `FULL_DATASET_INTEGRITY=PASS`;
ChatGPT then reviews sanitized identities/counts/hashes and continues into P3
optimizer/walk-forward work. Any failure stops; preserve any partial root and
do not retry. No Robinhood, broker, trading, ACL or scheduler effects are in P2.

Preserved P1 failure: candidate
`51c959ed80be8b658d45f8358bb73795ffab7047`, tree
`bcf8e1d0be1237bdd08a0f03b4c8c79ef6276110`; CI #806 / run 41019120148 /
attempt 1 ended FAILURE. Source-static, active-tests and FULL broad-1 through
broad-6 passed; broad-7 had 2265 passed / 2 failed. Classification is
`PREPUBLICATION_COVERAGE_DEFECT`: stale mixed-current assertions in
`tests/experiments/test_historical_research_partial_state.py`. #806 was not
rerun, and no protected or external effects occurred.

## Preserved Architecture 146 historical chronology

All Architecture-146 source, token and operator requirements below describe
historical checkpoints only. They confer no current desktop prerequisite,
dispatcher, retry or effect authority.

This candidate starts exactly at docs closeout
`cbc00675da352fd205d43a6fc4452f2a7fb33e22`, tree
`9e04e944173f75d7c20e14925da5c601bada14d1`; develop #802 / run
40974659897 / attempt 1 succeeded as DOCS_ONLY.

    worktree F:\AI\worktrees\ai-trading-bot-146b-partial-state-observer-current
    branch feature/research-arch146-b-partial-state-observer-current
    checkpoint arch146-b-partial-state-readonly-observer
    preflight registered; execute=None; canonical profile FULL (GitHub only)

The observer remains source-only until independently accepted and integrated.
No host observation occurs during implementation/certification. The old direct
B2 launcher remains NOT_RUN for this continuation. Terminal CI red OR green is
STOP for independent ChatGPT exact-source/CI review; no retry, PR or merge.

## Historical helper-authority correction

    reviewed parent HEAD 84b07c225a9f550582d5df4c992b0fca5dfc748b
    reviewed parent TREE e0773a4ead9e6fa34418d819170d099356d5f5b1
    feature #803 / run 40983454094 / attempt 1: SUCCESS / canonical FULL
    source acceptance NOT_GRANTED; host observer NOT_RUN; real effects ZERO

Independent ChatGPT exact-source review identified
ARCH146_PARTIAL_STATE_READONLY_HELPER_OWNERSHIP_GAP after #803. The runtime
observer itself was not found defective. Preserve #803 unchanged; no rerun.
The new ordinary child extends current semantic ownership of the local helper
graph only, without changing observer/native runtime or dispatcher source.
The external inspect_open_authority_object authority remains with Architecture
134 runtime ACLs. No historical repin or successor ladder is introduced.

No real host observation occurred. Acquisition and OPEN-parent creation remain
NOT_AUTHORIZED. Architecture 134 R3 remains parked; LIVE remains NO-GO.
Both final child admission contexts must PASS with stable exact identity before
one ordinary push and one new mapped GitHub FULL. Admission failure, or terminal
CI red OR green, is STOP for independent review. No registered host observer
follows CI; source acceptance and develop integration remain separate.

## Preserved original prepublication evidence

    HEAD f49dd2d2ef7eb0944fdc8d91ba0c275fbb65dc40
    TREE 1da5d05c1f14c5552249f3cdc5fcf7c47a9afcd4
    FEATURE PASS; PROSPECTIVE_DEVELOP FAIL (three composed failures)
    publication NOT_RUN; remote feature ABSENT; canonical CI NOT_RUN
    real effects ZERO; source acceptance NOT_GRANTED

Accepted diagnosis: ARCH146_CURRENT_PREFLIGHT_DISPATCHER_OWNERSHIP_DEFECT.
Two stale R2/R3 predicates require R3 to remain the global outer wrapper; R3's
R2 composition produces three failures. The separately authorized ordinary
child moves that ownership into current source authority without changing
R2/R3 exact security dispatch, pins, evidence guards or observer behavior.
The ordinary dispatcher child passed FEATURE/PROSPECTIVE_DEVELOP with stable
identity and published the two-commit lineage once, followed by green #803.
Preserve both commits and the original failed admission; no amend/squash.

## Historical accepted B2 source foundation

Accepted historical source at that checkpoint:

    develop HEAD f2a78e3c82058f3aee6d3d7145bbd9a8f00e2369
    develop TREE 7d9d3898b0c802780617e9f1f397338fe0fc96d3
    feature/research-arch146-b-pre-b2-readiness-current HEAD f2a78e3c82058f3aee6d3d7145bbd9a8f00e2369
    source checkpoint arch146-b-pre-b2-readiness-source
    feature #800 / run 40971719167 / attempt 1: SUCCESS / canonical FULL
    develop #801 / run 40974190116 / attempt 1: SUCCESS / exact-feature reuse

Develop #801 reported
`DEVELOP_CERTIFICATION_REUSE=True REASON=exact_feature_certification`; active
tests and FULL lanes were skipped. Failed predecessor #799 / run 40954098370 /
attempt 1 remains immutable and was not rerun or rewritten.

The accepted source uses exact order-insensitive ACE multiset semantics while
preserving SID/mask/type/flags, multiplicity, owner and protected-DACL
requirements. B2 exact-source cleanliness uses exactly
`status --porcelain=v1 --untracked-files=no`; unrelated generated/untracked
artifacts and historical pytest permission-warning directories remain preserved.

Ordinary research authority remains a primary non-impersonating Windows user
token, non-elevated and without effective Administrator authority. Ephemeral
hidden terminal input remains the sole later credential source with persistence
NONE. Production Trading identity and Credential Manager/environment/config/file
fallbacks remain excluded.

## Preserved historical consumed state and effect boundary

Preserve the consumed observations in order:

1. PRE-B2 #1: `BLOCKED_CREDENTIAL_ACCOUNT_SID_MISMATCH`; effects zero.
2. PRE-B2 #2: `BLOCKED_RESEARCH_OPERATOR_TOKEN`;
   operator_elevated=false, operator_administrator=true; effects zero.
3. PRE-B2 #3: `BLOCKED_HOST_FRESHNESS_OR_POLICY_UNPROVEN`;
   operator_elevated=false, operator_administrator=false,
   fresh_state=UNPROVEN_STOP; effects zero.
4. Bounded parent provisioning created only `F:\AI\research-holdout` with one
   directory creation and one ACL mutation.
5. The exact binary diagnostic observed Administrators ownership, protected
   DACL, non-reparse, and SYSTEM/Administrators FullControl OI/CI ACEs in the
   semantically accepted reverse order; diagnostic effects zero.

Last accepted reported partial state:

    F:\AI\research-holdout exists
    F:\AI\research-holdout\arch146-v1 absent
    F:\AI\research-holdout\.arch146-v1-attempt.json absent
    F:\AI\ai-trading-bot\data\research absent
    F:\AI\ai-trading-bot\data\research\arch146-v1 absent

No host state was re-observed during the tracked-only correction, feature #800,
fast-forward integration, or develop #801. Those facts remain preserved evidence,
not a new observation.

Published session authority remains
`nyse-published-regular-sessions-2016-2026-v1`, 2718 sessions, digest
`7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1`.
`ACCEPTED_CUSTODY_ADMISSIONS` remains empty.

Architecture 134 R3 remains consumed/parked at
`BLOCKED / HOST / HOST_UNEXPECTED_PRIVILEGE`, report SHA256
`8af6ef68a5a7a0558b938806719a3b3837ab8a8716a852573ed39d05a7411cb4`.
No retry or R4. LIVE remains NO-GO.

## Preserved historical observer boundary

Repository review after #801 found no registered Architecture 146 partial-state
observer. The current `arch146-b-pre-b2-readiness-source` checkpoint is
source-only: its `CheckpointSpec` has current authority and remote-branch
binding but no preflight function. The existing
`scripts.arch146_b2_readonly_preflight` launcher is retained historical/direct
preflight machinery and is not accepted as the next registered partial-state
observer.

That historical candidate added a dedicated registration without changing the
source-only predecessor or its direct B2 launcher. Its narrow native method
held the protected parent chain, inspected the exact parent policy, and probed
claim/protected-root/OPEN-parent/OPEN-root absence using read attributes,
OPEN_EXISTING and no-follow. It did not require the OPEN parent to exist.
Those details remain historical evidence only and are not part of the current
desktop research path.

The direct B2 launcher, `observe_fresh()`, Set-Acl, OPEN-parent creation,
credential reads, provider invocation, acquisition, and holdout reads remain
outside P1 and P2 source implementation and were not retried. The new desktop
bridge adds future interactive acquisition only after source acceptance.

The current immediate action is the Architecture-147 source candidate review
described above. No registered host observer follows its CI, and no observer
PASS or old B2 readiness state is required for desktop research.
