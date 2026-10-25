# AI Trading Bot — Project Status

## Current checkpoint

D1S4 source plus C1 was accepted/integrated at
`30a410d9023324ebe5c23e6a8ff128353b9ebf1f`, tree
`cf50b0b7b84428d9e502ed5bd85307001bc866ed`. The one-shot direct installation
completed PASS / DIRECT_INSTALL_VERIFIED / CONFIRMED / IDENTITY_STABLE=True for
`release-18d5d329c1d458558e98d7effe523c3b`. Its installation attempt is permanently
consumed and must never be retried.

A later fresh registered read-only preflight was BLOCKED /
READ_ONLY_ADMISSION_REJECTED. Localization found external John FullControl CI/OI
ACL drift on F:\AITradingBot and its releases directory. Source, Administrator,
replay inputs and the consumed installation latch remained valid. Runtime and
production Python were outside the drift set. The compromised FINAL and both
historical .installing roots remain preserved incident evidence, never repair
or runtime-admission targets.

Architecture **134-F1R1-D1S4-R1 — Shared Namespace ACL Recovery** is implemented
as source only, pending publication, canonical CI and ChatGPT exact-source review.
Focused verification covers 1,878 unique green affected cases (124 R1 / 135
D1S4); whole-repository Ruff lint/format and diff checks pass.
It admits only the two frozen identities/pre-descriptor hashes/ACE tuples and
removes only the exact reviewed John ACE by applying ADMIN_ACES / IMAGE_ACES.
Read-only preflight, reviewed-plan digest, independent durable one-shot latch,
private exclusive-handle DACL-only mutation and repeated non-target readback are
separate gates. Repair never restores trust in the compromised FINAL.

Active branch:
`feature/robinhood-production-paper-134f1r1-d1s4-r1-shared-namespace-acl-recovery-current`.
Final source identity: PENDING FINAL COMMIT.
Terminal CI: PENDING FIRST/ONLY PUSH.

Detailed frozen incident/contract:
[Architecture R1](architecture/134-f1r1-d1s4-r1-shared-namespace-acl-recovery.md)
and [validation](validation/arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery-plan.md).
Earlier architecture/validation records describe their historical checkpoints;
this current document supersedes their pending acceptance/host wording.

## Production boundary

Reconciliation remains blocked on external shared-namespace ACL drift. No real
R1 production preflight or recovery ran during implementation. D1S4 execute,
D1S3/R5 publication, cleanup/re-ACL/reuse of incident releases, runtime start,
scheduler changes, credentials/provider, paper/broker and D1/D2 effects are not
part of R1 source work. Original F1 is FINAL / INDETERMINATE / CONSUMED; C2
remains consumed and immutable. Live remains **NO-GO**.

## Next step

Complete the one atomic R1 commit/one push and wait for terminal CI-owned
ROBINHOOD; do not duplicate it locally. On red preserve evidence and stop for
ChatGPT classification. On green ChatGPT reviews the exact commit/diff/evidence.
Codex stops at IMPLEMENTED / ONE ATOMIC COMMIT / ONE PUSH /
PENDING CHATGPT EXACT-SOURCE REVIEW, without integration or host operations.

    exact-source review -> reviewed develop integration -> develop CI
    -> registered read-only R1 production preflight
    -> separate one-shot protected ACL-recovery review/execute
    -> registered read-only reconciliation
    -> only if recovered: fresh successor source/new HEAD/TREE/release ID/path
    -> exact deployment admission -> successor-root write-authority/ACL review
    -> fresh manual-start F1 successor soak -> 145-B
    -> Research Results GUI -> large strategy campaigns
