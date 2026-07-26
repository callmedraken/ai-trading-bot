# Canonical archive-to-bundle restoration validation

Restore an existing canonical archive into one new fixed-layout bundle:

```text
python -m scripts.restore_walk_forward_research_bundle_archive \
  --archive reports/bundles/walk-forward-research-bundle-<manifest-id>.tar \
  --destination reports/bundles/restored-session \
  --expected-byte-length LENGTH \
  --expected-sha256 SHA256
```

Quiet successful restoration uses `--quiet`. The destination parent must
already exist. Neither the final destination nor deterministic sibling staging
entry may exist. Repository-local restored bundles belong below the ignored
`reports/bundles/` directory.

Verify the finalized restored bundle without the source bundle:

```text
python -m scripts.verify_walk_forward_research_session_manifest \
  --manifest reports/bundles/restored-session/manifest.json
```

Archive argument, read, structure, byte-length, and SHA-256 failures retain the
existing archive-verifier exit classifications. Destination preflight,
staging, output, staged verification, cleanup, and finalization failures use
exit code 9. Existing final and staging entries are never overwritten or
deleted.

Focused automated validation is:

```text
.\.venv\Scripts\python.exe -m pytest \
  tests/cli/test_research_session_archive.py \
  tests/cli/test_research_session_restore.py \
  tests/cli/test_restore_research_session_archive.py \
  tests/scripts/test_research_session_archive_scripts.py \
  tests/integration/test_walk_forward_research_restore_e2e.py
```

Coverage includes the shared public streaming reader, unchanged archive
verification and golden evidence, exact manifest and artifact bytes, manifest
identity preservation, two-pass mutation detection, fixed layout, expected
outer evidence, existing destination and staging rejection, cleanup failure,
CLI classifications, script delegation, and offline verification after the
source bundle is removed.
