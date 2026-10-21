# Validation: Architecture 134-F1R1-A

This is a source-only validation record for the exact requested branch,
starting from `develop` HEAD `ef66dc848fd3bc031220c7e8ccd4f462d762e829` and
tree `a63fb5bdcdf3d9a38645ffa07a91e2a55099f0d3`.

## Scope

The checkpoint adds pure runtime-isolation contracts over the existing
Architecture-133 immutable-release model. It does not install or start a
release, alter a scheduler, read credentials, contact Alpaca or Robinhood,
mutate paper or broker state, invoke D1R7/D1R8, access production SQLite, or
modify the preserved F1 authority/evidence.

## Focused proof

`tests/review_paper/test_arch134_f1r1_a_runtime_isolation.py` uses only a fake
durable journal and synthetic release manifest. It verifies:

- repeated admission is deterministic and independent of development cwd;
- mutable development material does not change an installed identity;
- no live-Git, provider, credential, broker, or host capability is imported;
- pre-entry failure leaves only `INTENT` plus rejection and never calls the seam;
- `ENTRY_ADMITTED` is visible before the seam, post-entry failure is ambiguous
  and consumed, and success persists `ACK`;
- unknown diagnostic reasons and raw secret/provider/exception fields fail
  closed;
- lifecycle evidence is bounded, replay-valid, and distinguishes abrupt
  disappearance from normal return;
- frozen predecessor digests remain exact and successor overlays reject missing,
  extra, wrong-predecessor, and wrong-successor material;
- boot/login returns production to `STOPPED` and only fresh admitted manual
  start returns it to `RUNNING`.

The F1 evidence retained by this checkpoint is: the long-running supervisor
survived into the actual session window; D1R7 completed; D1R8 reached strategy
and credential preparation plus durable quote `INTENT`; provider entry is not
proven; execute attempts, paper fill mutations, broker placements, and live
effects were all zero; F1 remained fail-closed and did not grant Session 2.

## Review and stop conditions

The registered checkpoint is inactive/source-only and has no preflight, execute,
remote-head, credential, scheduler, provider, broker, paper, or live operation.
The current runner/source-pin/AST/blob consumers are audited through the focused
checkpoint tests and exact predecessor overlays. A failure that requires an
operational effect, new authority, predecessor reinterpretation, deployment,
credential/provider access, or repair of F1 evidence is outside this checkpoint
and is a stop condition.

## Operator verification

Codex runs the focused module, affected checkpoint/profile/lane tests, focused
Ruff check and format checks, `git diff --check`, and the registered source-only
verification. Full certification remains the user's local responsibility
unless the reviewed CI mapping owns that exact profile. No local protected or
operational gate is implied by this document.
