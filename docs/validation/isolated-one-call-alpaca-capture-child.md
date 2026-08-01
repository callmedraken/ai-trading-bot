# Isolated one-call Alpaca capture child validation

## Scope

Normal tests use fake Credential Manager, provider transport, and native
process adapters. They use dedicated temporary roots and no real Alpaca
credentials or provider connection. The real Windows process test is opt-in
and requires no Credential Manager or Alpaca access. The read-only Credential
Manager integration is separately opt-in and uses only dedicated
`integration-test` target names.

## Reviewed canonical vectors

| Artifact | UUID | bytes | SHA-256 |
| --- | --- | ---: | --- |
| child request | `7dff0b51-1be2-570e-b227-6885fe016c24` | 2086 | `04a5d93444594eff1273f0f0fba87548746cef5ae20eba65787098365e5b07f7` |
| child result | `6938ae49-771a-5a68-894f-3d729a58e3e2` | 810 | `2cf07bf1633d88d1d8b213e8cdb5cbe8cc9c2bbdcc976fba24c22462d9dede0b` |
| process creation | `1e32841c-b00e-5a92-83f7-a36009f6b220` | 1061 | `53a82f1a2f528a941bbbb1273774582cb3b2e1d9f462608d8f4c0f17ccf8eeb7` |
| resume authorization | `d70f2c8d-79f8-5231-b429-5d8d97e51daa` | 800 | `6da75aae77126fbf901dbdfbc3bde9e8e32b078aecab90048f45bbd7e35422f4` |
| termination | `dec05d87-7be5-502e-842d-622c4ee7ead1` | 1025 | `7d6e17cdfb59a91a974889b8c6d7bd792158e07e07e14dad4912c68e93bdf054` |

The child-request byte vector uses fixed reviewed Windows transport paths.
Changing those paths changes serialized bytes but not the child-request UUID.

## Coverage

Focused tests cover:

- strict request/result/process canonical parsing and hostile JSON;
- path-independent request identity and exact allocation reconciliation;
- fake Credential Manager success, missing/invalid values, type,
  persistence, size, SID-before-read, full native-blob cleanup before
  `CredFree`, native cleanup on rejection/decoding/exception paths, the
  `CRED_MAX_CREDENTIAL_BLOB_SIZE` 2,560-byte native bound, valid 1,025- and
  2,560-byte oversized ranges, invalid 2,561-byte, null, and overflowing
  ranges, one-time `CredFree`, the 1,024-byte application copy bound, and
  redaction;
- unchanged `os.environ` and a private two-key provider mapping;
- exactly one provider/transport call and a pre-transport second-call fence;
- canonical snapshot success, authentication/provider/network/incomplete/output
  and internal failures;
- secret-bearing exception reduction and absence from result/output bytes;
- parent Alpaca-variable rejection and the exact environment allowlist;
- suspended creation, Job limits/assignment, evidence-before-resume, timeout,
  termination confirmation, active-process limit, disabled handle inheritance,
  stable stream overflow diagnostics, and handle closure;
- strict nonsecret launcher configuration and thin CLI imports; and
- an opt-in real `CreateProcessW`/Job Object test with no provider credentials.

No test allocates attempts, advances history or lineage, selects a terminal or
snapshot, invokes paper operation, installs a schedule, retries, falls back,
or continues pagination.

## Commands

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_isolated_capture_artifacts.py tests\runtime\test_windows_credentials.py tests\runtime\test_isolated_capture_child.py tests\runtime\test_isolated_capture_process_and_launcher.py tests\cli\test_isolated_capture_cli.py tests\scripts\test_isolated_capture_scripts.py -q
set RUN_WINDOWS_ISOLATED_PROCESS_TESTS=1
.venv\Scripts\python.exe -m pytest tests\integration\test_windows_isolated_capture.py -q
.venv\Scripts\python.exe -m pytest tests\runtime\test_capture_attempt_authority.py tests\market_data\test_alpaca_daily_snapshot.py tests\market_data\test_alpaca_http.py tests\cli\test_daily_snapshot_capture.py tests\cli\test_daily_snapshot_config.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

The real Credential Manager test additionally requires
`RUN_WINDOWS_CREDENTIAL_MANAGER_TESTS=1` and pre-existing, dedicated test-only
generic credentials. It never creates, updates, enumerates, rotates, or
deletes them.
