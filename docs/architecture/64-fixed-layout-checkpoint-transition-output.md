# Fixed-layout checkpoint transition output

Milestone 2E adds only offline caller-configured genesis and one-edge transition
commands. A genesis is written to `paper-account-genesis-<checkpoint-id>/` with
its sole canonical checkpoint file. A successor transition is written to
`paper-account-transition-<application-id>/` with exactly one canonical cycle
report and one canonical successor checkpoint.

All domain work, canonical serialization, and in-memory verification complete
before output staging exists. The output parent must be an existing real
directory. Final and sibling `.<final>.staging` entries are preflighted with
case-fold collision, link, reparse-point, and parent-identity checks. Staging
uses exclusive creation, exact expected files, file flushes, reload verification,
and one no-clobber same-parent directory rename. Invocation-owned staging is
cleaned only after pre-finalization failure; pre-existing or crash-left staging
fails closed.

The run command derives the application identity from the verified predecessor
and caller request. Before execution it accepts only a complete, byte-identical
existing transition with matching request, snapshot, report, successor, and
edge proof, returning `ALREADY_APPLIED`. A different successor for the same
prior checkpoint under one output parent is `LINEAGE_CONFLICT`. No registry,
cross-directory lock, traversal, provider, broker, clock, scheduler, or retry
is introduced.
