# Offline walk-forward manifest verification

Run the verifier against an existing manifest and its retained artifacts:

```text
python -m scripts.verify_walk_forward_research_session_manifest \
  --manifest reports/walk-forward-session-manifest.json
```

A successful run exits zero and reports every retained artifact in manifest
order. Quiet validation emits no output:

```text
python -m scripts.verify_walk_forward_research_session_manifest \
  --manifest reports/walk-forward-session-manifest.json --quiet
```

The verifier resolves artifact paths only from the manifest parent. Referenced
JSON and CSV files are read as opaque bytes; invalid JSON or arbitrary binary
artifact bytes pass when their exact retained length and SHA-256 digest match.

Removing an artifact produces `MISSING_OR_NONREGULAR` and exit code 5. Changing
its byte length produces `BYTE_LENGTH_MISMATCH` and exit code 6. Replacing bytes
without changing the length produces `SHA256_MISMATCH` and exit code 7. Failure
reports remain visible in quiet mode.

Focused automated validation is:

```text
.\.venv\Scripts\python.exe -m pytest \
  tests/cli/test_research_session_manifest.py \
  tests/cli/test_verify_research_session_manifest.py
```

The tests cover strict bytes-to-model parsing, the 4 MiB limit, BOM and malformed
JSON rejection, exact field and type handling, identity reconstruction,
duplicate retained paths, opaque streaming verification, stable statuses,
symlink rejection where the test platform permits symlink creation, exit codes,
quiet behavior, and repeatable terminal output.
