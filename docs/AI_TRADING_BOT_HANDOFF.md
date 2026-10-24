# AI Trading Bot — Current Handoff

## Verified transition

The rename-free pivot is integrated into `develop` at:

    HEAD  1e9b6a0638f00ddb009bdb7934039b7a9047e678
    TREE  1ef95f954cfce509a6b90639b8bb9599e2e9206f
    CI    #705 / 40083293598 / attempt 1 / SUCCESS

All four broad develop shards and terminal source-gates passed.

The consumed D1S3/R5 publication incident remains preserved. Do not rerun either
operator, rename the preserved staging directory, or clean/repair that namespace.

## Active next checkpoint

Architecture:

    134-F1R1-D1S4 — Rename-Free Direct Immutable Release Installation

Branch:

    feature/robinhood-production-paper-134f1r1-d1s4-rename-free-immutable-release-current

Recommended local worktree for implementation:

    F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-d1s4-rename-free-immutable-release-current

Base is exact current develop `1e9b6a0638f00ddb009bdb7934039b7a9047e678`.

Read first:

- `AGENTS.md`;
- `docs/AI_DEVELOPMENT_WORKFLOW.md`;
- `docs/architecture/134-f1r1-rename-free-immutable-release-pivot.md`;
- `docs/architecture/134-f1r1-d1s4-rename-free-immutable-release-installation.md`;
- `docs/validation/arch134-f1r1-d1s4-rename-free-immutable-release-installation-plan.md`.

## Frozen D1S4 model

Keep the existing release manifest, deterministic release ID and RuntimeBinding.
The exact final path remains:

    F:\AITradingBot\releases\<release-id>

Materialize directly into that exact path after a separate D1S4 latch is durably
consumed. Verify that same path twice. Never rename it.

There is no D1S4 staging path and no publication phase.

The new native writer must be narrow create/write/flush/close only. No
publish/rename/move/delete/cleanup/rollback/replacement/alias capability and no
retired writer imports.

The new D1S4 attempt is separate from D1S3/R5 and is derived from the exact
release ID. Same-source ambiguity is terminal/no-retry; a later reviewed source
identity naturally yields a new release ID/path.

The registered read-only state machine must distinguish:

    AVAILABLE + final absent
      -> READY_FOR_RENAME_FREE_MATERIALIZATION

    CONSUMED + exact verified final
      -> DIRECT_INSTALL_VERIFIED

    CONSUMED + final absent
      -> CONSUMED_ATTEMPT_NO_IMAGE

    CONSUMED + partial/conflicting final
      -> PARTIAL_OR_CONFLICTING_DEPLOYMENT

    AVAILABLE + any final present
      -> UNOWNED_FINAL_PRESENT

No state renews authority.

## Implementation workflow

Recommended model: **Sol High**.

The implementation agent may perform source/test/docs/runner changes, focused
verification, one normal atomic commit and one ordinary feature-branch push.
The checkpoint must be mapped to canonical ROBINHOOD CI so the human does not
duplicate certification locally.

No merge, rebase, amend, force-push, PR mutation, protected D1S4 preflight,
production materialization, root provisioning, runtime start, scheduler,
credentials/provider, paper/broker, D1/D2 or live effect is part of the
implementation task.

After terminal CI, hand the exact source identity/diff/results to ChatGPT. ChatGPT
will independently review it and automatically provide the next safe step.

## Roadmap

    D1S4 source implementation
    -> ChatGPT exact-source acceptance/integration
    -> registered read-only production preflight
    -> separate protected one-shot direct installation review
    -> exact deployment admission
    -> successor-root ACL/write-authority review
    -> fresh manual-start successor soak
    -> 145-B
    -> Research Results GUI
    -> large strategy campaigns

Live remains NO-GO.
