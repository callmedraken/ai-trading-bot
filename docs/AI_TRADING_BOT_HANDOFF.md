# AI Trading Bot — Current Handoff

## Current source identity

The mutable `develop` tip must be read live at the start of each new task; do
not infer it from a previously written handoff SHA.

The most recent integrated product/design checkpoint immediately before the
current workflow-only correction is:

    HEAD 6f07e0fdaf20d335c22bc77c8cfb09a0ee47260c
    TREE b8cb3b62033a8f7f096a02a353d3dfa81d72b130

That checkpoint closed Architecture 134 R3, froze the Architecture 146-B design,
and was integrated by exact-SHA ordinary fast-forward. Develop Checkpoint Source
Gates #779 / run 40642547780 / attempt 1 completed SUCCESS in `DOCS_ONLY`
mode; source-static and source-gates passed and broad/certification jobs were
correctly skipped.

The earlier Architecture 134 R3 feature certification remains historical and
must not be rerun:

    Checkpoint Source Gates #775
    run     40633699956
    attempt 1
    result  SUCCESS
    R3 HEAD 99654f3547140dc8fd005ee1525ac9a77987b946
    R3 TREE 5b04b8d4baf70b3a936d10a5972ffcd26c03dd3c

The canonical R3 ROBINHOOD run completed 12,063 cases: 12,057 passed, 6 skipped,
0 failed/errors. Historical develop run #776 / 40635656630 / attempt 1 completed
SUCCESS using exact feature-certification reuse. Do not rerun either run.

### Worktree-root non-regression

Every Trading Bot auxiliary worktree must be created under
`F:\\AI\\worktrees\\...`. Creation under
`C:\\Users\\John\\.codex\\worktrees\\...`, any other C: location, or
any other noncanonical root is itself a workflow regression and STOP. Codex or
another tool must be given the exact F: destination before it can create a
worktree. If its automatic worktree mode cannot guarantee that destination
before creation, do not use that mode; create/select the canonical F: worktree
first and run the tool against it. Existing noncanonical worktrees are preserved
for a separate reviewed reconciliation step and are never adopted for current
work.

## Pending B1-C4 continuation

Work only in `F:\AI\worktrees\ai-trading-bot-146b1-source`, branch
`feature/research-arch146-b-acquisition-custody-current`. C4's reviewed parent is
HEAD `100d1cd0f759a7df1d31632c2f237621731017bd`, TREE
`060899aad7c9d68d2e992b139657af384a5405d4`. #782 / `40649744489`, #783 /
`40658848795` and #784 / `40689830781` are immutable failed evidence.

C4 is a source-only timing/topology correction pending one clean-candidate
FEATURE/PROSPECTIVE_DEVELOP admission, ordinary atomic commit/push and terminal
mapped canonical FULL. Do not run FULL locally. Functionally green wall <300s
permits ChatGPT exact-source acceptance review; wall >=300s is STOP, with no
unchanged rerun or automatic eight-lane change. The [C4 validation record](validation/arch146-b-historical-research-acquisition-custody-plan.md#146-b1-c4--current-full-timing-capacity-correction)
owns timing provenance and exact review bounds. B-E implementation remains gated
on terminal-green B1; publication additionally requires base acceptance/integration.
R3 remains parked; all protected effects remain unavailable and LIVE is NO-GO.

## Consumed Architecture 134 diagnostics

R1, R2 and R3 are independent consumed historical observations. Never rerun,
repoint, reinterpret or replace them.

R1:

    BLOCKED / HOST / HOST_FORBIDDEN_IDENTITY
    diagnostic_process_starts=23
    identity_stable=true
    report SHA256 c6b7be3660bcb3b2f30c2cc29a3160fab6621c31f8287b3e352885a214fb424d

R2:

    HEAD b70ca1ade95f122a014c45c9a2f64de900b685f5
    TREE 1c836cf17ea5887b669db1867d0b116ac02559da
    BLOCKED / HOST / HOST_TOKEN_POLICY
    diagnostic_process_starts=23
    identity_stable=true
    report SHA256 4fee1762e080de1d4e20eab844185b30480efcb7192ab5b8d0c1c65ca1d26677

R3:

    HEAD 99654f3547140dc8fd005ee1525ac9a77987b946
    TREE 5b04b8d4baf70b3a936d10a5972ffcd26c03dd3c
    BLOCKED / HOST / HOST_UNEXPECTED_PRIVILEGE
    diagnostic_process_starts=23
    identity_stable=true
    protected_execution=NOT_AUTHORIZED
    production_effects=NOT_RUN

R3 evidence:

    F:\AI\temp\ai-trading-bot-checkpoints\arch134-diagnostic-r3-ee9dd40ff6504130a662ae24a85beb14\arch134-fresh-successor-readonly-deployment-admission-diagnostic-r3\preflight-20261028T051340.768951Z\report.json

R3 report SHA256:

    8af6ef68a5a7a0558b938806719a3b3837ab8a8716a852573ed39d05a7411cb4

Every R3 effect counter is zero and every authority flag is false. The security
policy and collector were not weakened. The result identifies the closed
privilege-policy family but intentionally does not serialize raw privilege rows,
so it does not justify changing privilege state or elevation.

## Roadmap pivot

The Architecture 134 Windows host-admission path is now PARKED, not repaired or
waived. No R4 diagnostic is planned merely to obtain a finer label. Resume this
track only when a concrete production runtime/deployment identity is again a
direct dependency.

This is an organizational critical-path pivot, not a safety-policy relaxation:
the parked boundary remains fail closed and LIVE remains NO-GO.

## Architecture 146-A is already landed

The final 146-A C2 source is:

    HEAD 6906ba01bfb6a353029d695e584b2097587b81b9
    TREE aa1efe5057e047e0d1778f2422e45f26cbc9f5d6
    branch feature/research-arch146-a-historical-research-dataset-enforcement-current
    Checkpoint Source Gates #720 / run 40178730059 / attempt 1 / SUCCESS

The accepted integration ancestry contains that exact commit; resolve the
mutable develop tip separately at startup.
The source module `trading_bot.experiments.historical_research_dataset` and its
synthetic verification surface are therefore current product source. Do not
restart 146-A.

Preserve the two earlier red attempts:

    #718 / 40176547184 / 472d5698435313e531fe2afd201959869b113f12
    #719 / 40177945971 / 83318d00b18264dfdf7d06725ee660383578c92f

They remain immutable correction evidence.

## Active next boundary — Architecture 146-B

The next milestone is a bounded historical-data acquisition/custody path for the
already frozen SPY v1 dataset contract.

Architecture 146-B is split operationally:

1. B1 source checkpoint: implement the bounded acquisition/custody operator,
   deterministic vendor-response normalization, exact persistence plan, evidence
   model and synthetic/fake verification. B1 performs no real provider call,
   credential read, directory creation, ACL mutation or holdout read.
2. B2 reviewed execution: after B1 exact-source acceptance/integration, perform
   one separately authorized acquisition/custody attempt. B2 is the first point
   that may read the reviewed Alpaca credentials, call the two reviewed market
   data GET endpoints, create/protect the holdout custody root and persist the
   immutable v1 snapshot.

No provider or host effect follows automatically from this documentation
closeout or from B1 source acceptance.

## Product roadmap after 146-B

    admitted OPEN SPY data
      -> DEVELOPMENT + WALK_FORWARD research with deterministic execution stress
      -> existing compact experiment report
      -> existing Research Results GUI

This is the working prototype path. FINAL_HOLDOUT evaluation, production-host
remediation, paper soak, broker execution and live money are not prerequisites.
They remain separate later decisions; LIVE remains NO-GO.

Paper trading remains useful for integration/operational evidence, but research
quality is driven by deterministic historical robustness evidence. No final
holdout is used for parameter selection.

## Automatic continuation rule

After every accepted checkpoint, ChatGPT must review the current status/handoff,
state whether the parked Architecture 134 boundary remains unchanged, choose the
next roadmap milestone/model, and provide the exact next prompt or operator
command plus expected evidence and STOP conditions without requiring an
authorization-only turn.

## Pending 146-B1 source continuation

Canonical source worktree:

    F:\AI\worktrees\ai-trading-bot-146b1-source
    feature/research-arch146-b-acquisition-custody-current

The worktree was fast-forwarded from reviewed base b4e9fb1 to the accepted
additive-design checkpoint c33608b3c6b56021582007a87a44d45a2c3f3972,
tree afff9fbbebfe92de21a688cd2258cf4d45c36c7d. Its design source gate
#781 / 40645519417 / attempt 1 is terminal SUCCESS.

B1 source now supplies the injected acquisition kernel, protected persistence
plan, canonical non-price evidence/admission, empty source-owned real-admission
registries and successor OPEN-only verifier. No existing 145-A/146-A source
changes. The original untracked implementation-review proposal is preserved as
local discovery evidence and is not part of the intended source checkpoint.

B1-C1 was published but is not accepted or integrated. Its exact source
identity and immutable push-triggered Checkpoint Source Gates #782 / run
`40649744489` / attempt 1 evidence are recorded in the [146-B validation plan](validation/arch146-b-historical-research-acquisition-custody-plan.md).
B1-C2 was published at HEAD `2ec59d6a8f409d469485815106c5087125b977be`,
TREE `17c2985af56076d9aef8ec4c1b5abe2d623a7e69`. Preserve failed #783 /
`40658848795` / attempt 1 and #782 unchanged. B1-C3 corrects static-toolchain/
file-universe parity; require focused verification and complete clean-candidate
FEATURE and PROSPECTIVE_DEVELOP admission before its one ordinary push. Wait for
terminal mapped GitHub CI and STOP for ChatGPT timing review if canonical wall
remains >=300 seconds. Do not run canonical FULL locally or treat C3 as accepted
or integrated. The validation plan owns the failure details and exact C3 scope.

B2 has no native bindings or registered host dispatcher here. Before any real
attempt, separately review its native source/host binding and exact published
historical-session authority. After B2 materialization, independently accept
its immutable evidence and freeze the source-owned custody admission before
normal OPEN research. The current raw-material OPEN verifier must not receive
mixed acquired pages. R3 remains consumed/parked; LIVE remains NO-GO.

### Preserved 146-B1-C2 correction

Published C2 repaired historical workflow reconstruction and separated frozen
Architecture-143 pin/object checks from current mutable test bytes. Its local
coherence bundle remains in force and C3 adds the affected result/source tests.
The next publication boundary is C3 above; C2 is not accepted or integrated.
No real B2 acquisition, credentials, holdout/custody, ACL, provider, host, paper,
broker or live effect has occurred.
