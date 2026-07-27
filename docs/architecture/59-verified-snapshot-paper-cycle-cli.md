# Verified-snapshot paper-cycle CLI

The run command consumes a caller-authored strict JSON configuration and a
separate canonical daily-snapshot artifact. It verifies the snapshot before
preparation, runs the existing one-shot paper-cycle adapter, builds canonical
report bytes, verifies them in memory, and exposes a derived no-clobber report
name under the supplied existing real directory.

The verify command consumes only a snapshot artifact and a report artifact. It
performs the existing complete offline verifier, including one disposable
in-memory runtime replay. Neither command contacts a provider or broker, reads
a clock, schedules work, selects a strategy, or persists runtime state.

Configuration schema 1 requires every account, target, asserted-open,
timestamp, policy, snapshot-reference, and ordered-metadata field. Decimal
values are exponent-free canonical strings; UUIDs and timestamps are canonical;
unknown fields, duplicates, JSON floats/constants, comments, BOM, and malformed
or trailing JSON are rejected.

Run output is named verified-snapshot-paper-cycle-result-id.json, with a
deterministic sibling staging name. Existing and case-fold-colliding final or
staging entries, links, reparse points, changed destinations, and replacement
behavior are rejected. The staged report is flushed, fsynced, reopened, fully
replayed, and installed using a no-clobber hard link. Generated reports belong
under the ignored reports/paper-cycles path.

Exit codes are 0 success, 2 argument usage, 3 input read/JSON failure, 4
snapshot verification, 5 configuration/preparation for run or report
verification for verify, 6 run execution/reconciliation, and 7 run report
serialization/output/finalization.
