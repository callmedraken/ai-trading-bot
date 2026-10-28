# AI Trading Bot — Project Status

## Current checkpoint

Do not freeze the mutable `develop` tip in this status file across a
documentation-only correction. Verify `origin/develop` live at every new task
startup.

The most recent integrated product/design checkpoint immediately before this
workflow-only correction is:

    HEAD 6f07e0fdaf20d335c22bc77c8cfb09a0ee47260c
    TREE b8cb3b62033a8f7f096a02a353d3dfa81d72b130

Architecture 134 R3 remains SOURCE ACCEPTED and parked. The Architecture 146-B
design/closeout fast-forward landed at the identity above. Develop Checkpoint
Source Gates #779 / run 40642547780 / attempt 1 completed SUCCESS in
`DOCS_ONLY` mode: source-static and source-gates passed; active-tests,
full-tests and certification-tests were correctly skipped.

Worktree non-regression is now explicit: no Trading Bot auxiliary worktree may
be created outside `F:\\AI\\worktrees\\...`. A tool-managed C:-drive
worktree is a workflow regression even if it is clean and unused.

## Architecture 134 host track — parked, fail closed

R3's single real-host read-only observation is consumed:

    BLOCKED / HOST / HOST_UNEXPECTED_PRIVILEGE
    diagnostic_process_starts=23
    identity_stable=true
    protected_execution=NOT_AUTHORIZED
    production_effects=NOT_RUN

Every effect counter is zero and every authority flag is false.

Evidence:

    F:\AI\temp\ai-trading-bot-checkpoints\arch134-diagnostic-r3-ee9dd40ff6504130a662ae24a85beb14\arch134-fresh-successor-readonly-deployment-admission-diagnostic-r3\preflight-20261028T051340.768951Z\report.json

SHA256:

    8af6ef68a5a7a0558b938806719a3b3837ab8a8716a852573ed39d05a7411cb4

R1 and R2 remain separately consumed and immutable. R3 is not retryable under
another shell, privilege state, command variant, worktree or evidence root. No
R4 diagnostic is currently planned. The Windows production-host admission path
is parked until a concrete deployment/runtime-identity remediation design makes
it a real dependency.

## Research/product track — active

Architecture 146-A is already in current develop ancestry. Its final C2 source is:

    HEAD 6906ba01bfb6a353029d695e584b2097587b81b9
    TREE aa1efe5057e047e0d1778f2422e45f26cbc9f5d6
    CI   #720 / run 40178730059 / attempt 1 / SUCCESS

146-A remains in the accepted integration ancestry. Do not reimplement or
republish it; verify current mutable develop separately.

The active milestone is Architecture 146-B: bounded historical-data acquisition
and custody. Published B1-C1 source is on
`feature/research-arch146-b-acquisition-custody-current` at HEAD
`2208b7e637671001b02deb56751dc7687a3cf36d`, TREE
`0b37449859b0bad78704f5324cdb19a2aa3d3475`. GitHub Checkpoint Source Gates
#782 / run `40649744489` / attempt 1 completed FAILURE and was classified
`PREPUBLICATION_COVERAGE_DEFECT`; the exact failures and C2 correction are
recorded once in the [146-B validation plan](validation/arch146-b-historical-research-acquisition-custody-plan.md).
B1-C2 is the bounded corrective candidate. It requires complete local focused
verification, clean-candidate admission and terminal mapped GitHub CI before
ChatGPT exact-source acceptance; it is not accepted or integrated.

Both real custody and historical-session admission registries remain empty.
The source-only kernel has no native B2 bindings or preflight/execute dispatcher.
B2 remains blocked on source acceptance, reviewed native bindings and an
independently frozen published historical-session authority. The accepted
146-B design boundary remains in force. No real credentials/provider call,
holdout read, custody write, ACL mutation, host effect, paper/broker/live effect
or Architecture-145 evaluation has occurred.

The working research-prototype target is admitted OPEN SPY data through
DEVELOPMENT and WALK_FORWARD research with deterministic execution stress, the
existing compact report and existing Research Results GUI. FINAL_HOLDOUT,
host remediation, paper soak, broker execution and live trading are not
prototype prerequisites.

## Foreseen roadmap

    146-B design/source operator
      -> one reviewed SPY historical acquisition + sealed holdout custody
      -> Architecture 145-B results/campaign bundle
      -> Research Results GUI
      -> large strategy/optimizer campaigns
      -> candidate selection: walk-forward, sensitivity and execution stress
      -> frozen candidate/policy
      -> separately admitted FINAL_HOLDOUT evaluation
      -> paper/operational validation and tiny live-canary eligibility review
      -> separately resume the parked production-host path when required

LIVE remains NO-GO. A source/preflight PASS never grants broker, paper or live
authority.
