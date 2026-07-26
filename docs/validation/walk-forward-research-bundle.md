# Portable walk-forward research-bundle validation

Create a bundle only from an existing manifest whose artifacts pass offline
verification:

```text
python -m scripts.create_walk_forward_research_bundle \
  --manifest reports/walk-forward-session-manifest.json \
  --destination reports/bundles/session
```

Quiet successful creation emits no output:

```text
python -m scripts.create_walk_forward_research_bundle \
  --manifest reports/walk-forward-session-manifest.json \
  --destination reports/bundles/session \
  --quiet
```

The destination parent must already exist. The destination and deterministic
sibling staging entry must not exist. Repository-local bundles belong below the
already ignored `reports/bundles/` directory.

The resulting fixed layout is:

```text
reports/bundles/session/
  manifest.json
  artifacts/
    01-walk-forward.json
    02-walk-forward.csv
    ...
```

Only retained formats are present. Positions are contiguous copied-artifact
positions; retained manifest ordinals remain unchanged.

Verify the copied bundle without access to the source tree:

```text
python -m scripts.verify_walk_forward_research_session_manifest \
  --manifest reports/bundles/session/manifest.json
```

The bundle command reuses source-verification exit codes 3 through 8.
Destination planning, staging, copying, staged verification, cleanup, and
finalization failures use exit code 9. Existing destination and staging entries
are never overwritten or deleted.

Focused automated validation is:

```text
.\.venv\Scripts\python.exe -m pytest \
  tests/cli/test_research_session_manifest.py \
  tests/cli/test_verify_research_session_manifest.py \
  tests/cli/test_research_session_bundle.py \
  tests/cli/test_create_research_session_bundle.py \
  tests/scripts/test_create_walk_forward_research_bundle.py
```

The tests cover pure relocation, identity preservation, fixed filename
positions, omitted formats, exact opaque-byte copies, source revalidation,
staged reloading and verification, destination and staging rejection, cleanup,
source-verifier exit classifications, quiet behavior, and offline verification
after source removal.

Canonical uncompressed archive creation and no-extraction verification are
covered by `docs/validation/walk-forward-research-archive.md`.
