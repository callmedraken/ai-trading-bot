# Successor paper-account checkpoint edge validation

Run from the repository root:

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_checkpointed_paper_cycle_successor.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check --no-cache .
.venv\Scripts\ruff.exe format --check --no-cache .
git diff --check
```

The focused suite covers applied, no-action, partial-sale, and full-sale
successors; canonical report and checkpoint round trips; exact final compact
state and P&L retention; deterministic successor identities; supplied artifact
hash and length evidence; strict report and successor tampering; canonical
identity-preserving report tampering; exactly one replay invocation; and
PASS-only exposure of reconstructed state.

The complete suite retains standalone verified-snapshot report schemas, bytes,
identities, and verifier behavior, alongside existing checkpoint, ledger,
backtesting, and simulation behavior. Validation creates no tracked artifact.

## Standalone checkpoint-edge verification

A genesis-rooted edge needs the explicit successor, genesis prior, cycle report,
and snapshot:

```text
python scripts/verify_paper_account_checkpoint.py \
  --checkpoint <successor.json> \
  --prior-checkpoint <genesis.json> \
  --cycle-report <report.json> \
  --snapshot <snapshot.json>
```

A later edge whose prior is itself a `CYCLE_SUCCESSOR` additionally requires the
explicit lineage ending at that prior:

```text
python scripts/verify_paper_account_checkpoint.py \
  --checkpoint <successor.json> \
  --prior-checkpoint <prior-successor.json> \
  --cycle-report <report.json> \
  --snapshot <snapshot.json> \
  --prior-lineage-manifest <lineage-manifest.json>
```

The manifest is safely loaded and its complete explicit lineage must pass
offline verification. Its terminal checkpoint ID, SHA-256, byte length, and
exact bytes must match `--prior-checkpoint` before
`verified_prior_from_full_lineage` can authorize the requested edge. A raw
successor checkpoint is not authority by itself: sequence numbers, filenames,
timestamps, and retained claims do not prove the preceding lineage.

Omitting `--prior-lineage-manifest` preserves the genesis-rooted verifier
behavior and does not infer authority for a later checkpoint. Manifest read or
syntax failures, failed lineage verification, terminal-evidence mismatches, and
edge failures fail closed without scanning for other manifests or writing any
output.

Exit codes retain the established verifier conventions: `3` for artifact or
manifest read/syntax failure, `4` for failed lineage authority or terminal
evidence mismatch, `5` for invalid strict manifest schema, and `6` for failure
of the requested successor edge after its inputs have been authenticated.
