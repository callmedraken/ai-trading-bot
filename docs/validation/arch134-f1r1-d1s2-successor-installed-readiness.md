# Validation — Architecture 134-F1R1-D1S2

Checkpoint: `arch134-f1r1-d1s2-successor-installed-readiness`

This is a source-only ROBINHOOD-mapped checkpoint. It has no preflight,
execute, remote-head environment, installation, publication, scheduler,
credential, provider, paper, broker, D1, D2, or live effect surface.

## Accepted predecessor and current boundary

D1S1 SOURCE ACCEPTED at HEAD
`88d6a4ba11a77ca4a7b04b102b914e9e4ea9bd96`, tree
`eae9ad713620f1a030a981f27e0a2672d0222fa0`, feature CI
`39754184070` attempt 1 SUCCESS. The preserved failed first source attempt is
`39751885721`; post-merge develop CI is `39756068943` attempt 1 SUCCESS.
Original F1 remains FINAL / INDETERMINATE / CONSUMED and C2 remains consumed
immutable evidence. D1 successor execution is unauthorized. Architecture 145
is separate/offline and live is NO-GO.

## Required source proof

The D1S2 proof must show:

1. exact accepted source remote/ref/HEAD/tree policy is explicit and no future
   SHA is guessed;
2. `VerifiedRelease`, complete source inventory bytes, canonical
   `RuntimeBinding`, and installed evidence are replayed through accepted
   Architecture-133 primitives;
3. mutable checkout code is rejected, and only
   `F:\AITradingBot\releases\<release-id>` with
   `F:\AITradingBot\runtime\python.exe` under `-I -S -B` is admitted;
4. final and `.installing` paths classify separately as
   `INSTALL_REQUIRED`, `ALREADY_INSTALLED_EXACT`, `BLOCKED`, or
   `INDETERMINATE`, without creating, deleting, repairing, or retrying;
5. the exact successor root policy rejects C2, old-F1, aliases/reparse
   points, non-NTFS/foreign parents, wrong ACL/owner, replaced identities,
   consumed evidence, and malformed evidence;
6. the exact D1 `STORE_IDENTITY`, namespace, lineage, process evidence, and
   repeated no-drift observations are required;
7. the observed order is Architecture-133 -> F1R1-A -> F1R1-B -> D1;
8. manual start remains STOP after reboot/login and requires explicit start;
9. no scheduler, logon/boot trigger, service, `--resume`, retry, catch-up, or
   automatic recovery surface exists; and
10. positive readiness is
    `READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT` only, with all
    protected effects zero and no provider/paper authority.

The launcher remains unchanged and inert/fail-closed. The runtime-host gap is
classified rather than silently converted into operational capability.

## R3A semantics and R3 phase/date verification

The [D1S2 architecture refinement](../architecture/134-f1r1-d1s2-successor-installed-readiness.md#r3a-root-state-refinement-and-r3-session-binding)
defines the reviewed phase semantics. Child reservations remain permanently
consumed per attempt; root-level `consumed` describes remaining legal
continuation/fixed-ordinal progression, and `evidence_complete` is phase-complete
replay. `ALREADY_BOUND_EXACT` is only quiescent parent + session 01.
`ACTIVE_CURRENT_EXACT` maps to `BLOCKED / CURRENT_MANUAL_START_ACTIVE`.

The exact next-date matrix is mandatory in pure composition and the positive
result invariant: empty + session 01 and progression + session 02 are READY;
the other two pairs are `BLOCKED / MANUAL_START_SESSION_MISMATCH`, preserve
the exact observed root/process, and confer no manual-start transition.
Tests retain active, consumed, indeterminate, malformed, replacement/drift,
historical-namespace rejection, and zero-effect behavior.

The corrected pre-native focused boundary passed 123 D1S2/D1S1 cases, with
eight publication-authority cases deferred until the combined R3 pin update.
R3 reconciles those exact source/AST/blob consumers before its single push;
no deferred source-authority assertion is presented as source acceptance.
No local canonical ROBINHOOD, FULL, protected preflight, or execute is run.

## Focused verification

The new D1S2 tests use injected fakes and a fresh external pytest basetemp
under `F:\AI\temp\pytest\...`. They cover positive composition, install
classification, exact paths/substrate, successor-root classifications,
identity drift, source-policy/bundle completeness, C2 and old-F1 rejection,
launcher inertness, no-effect imports/capabilities, predecessor pins, and
manual STOP/start semantics. Retained Architecture-133, F1R1-A, F1R1-B,
F1R1-C1, and D1S1 tests remain in the checkpoint test tuple.

The runner uses an additive D1S2 successor overlay. D1S1 predecessor
dictionaries/digests remain unchanged; current status/handoff, active
inventory, runner AST, and D1S1 test consumers resolve through the exact D1S2
overlay. Removing the D1S2 overlay restores D1S1 resolution.

Also remove or update any tests and docs that referenced the old behavior.
