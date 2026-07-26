# Canonical walk-forward research-archive validation

Create an archive from an existing completed bundle:

```text
python -m scripts.create_walk_forward_research_bundle_archive \
  --bundle reports/bundles/session \
  --destination reports/bundles
```

The command derives:

```text
walk-forward-research-bundle-<manifest-id>.tar
```

It reports exact archive byte length and SHA-256. Verify the archive without
extracting it:

```text
python -m scripts.verify_walk_forward_research_bundle_archive \
  --archive reports/bundles/walk-forward-research-bundle-<manifest-id>.tar \
  --expected-byte-length LENGTH \
  --expected-sha256 SHA256
```

Quiet successful creation and verification use `--quiet`. Failures remain
visible. Existing archives and deterministic sibling staging files are never
overwritten or removed.

The archive contains only `manifest.json` and fixed artifact paths in retained
manifest order. It uses canonical uncompressed USTAR headers, exact bundle
payload bytes, zero block padding, and exactly two terminal zero blocks.

Focused automated validation is:

```text
.\.venv\Scripts\python.exe -m pytest \
  tests/cli/test_research_session_archive.py \
  tests/cli/test_research_session_archive_cli.py \
  tests/scripts/test_research_session_archive_scripts.py \
  tests/integration/test_walk_forward_research_archive_e2e.py
```

Coverage includes golden archive length and SHA-256, repeated creation in
different directories, strict paths, canonical headers and checksums, exact
metadata, standard-library read compatibility, source layout and mutation
failures, outer evidence, payload tampering, zero padding and terminators,
unsupported entries, staging cleanup, CLI exit classifications, and streaming
verification without extraction.
