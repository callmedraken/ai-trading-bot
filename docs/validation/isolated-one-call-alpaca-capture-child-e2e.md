# Isolated one-call Alpaca capture child: local end-to-end validation

Validation date: 2026-07-30. This validation used the approved architecture and
validation documents for the Windows credential reference, authoritative capture
attempt evidence, and isolated one-call child. It did not invoke the guarded
readiness runner, capture-attempt history, terminal or snapshot selection,
scheduler, paper operation, or lineage head.

## 1. Files changed

- `src/trading_bot/runtime/windows_credentials.py`
  - Fixed construction on this Windows host by using the exported
    `RtlZeroMemory` entry point when the Windows SDK intrinsic
    `RtlSecureZeroMemory` is not exported.
- `docs/validation/isolated-one-call-alpaca-capture-child-e2e.md`
  - This validation record.

No other production files were changed. Generated evidence remains under the
ignored `reports/local-isolated-capture-child-validation/` root and was not
staged.

## 2. Validation environment

- Windows `platform=win32`; Python `3.14.3`; pytest `8.4.2`.
- Approved non-redirecting executable:
  `C:\Program Files\Python314\python.exe`.
- Approved executable SHA-256:
  `cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b`.
- Test virtual environment executable:
  `F:\AI\ai-trading-bot\.venv\Scripts\python.exe`.
- Dedicated validation roots were created only below
  `F:\AI\ai-trading-bot\reports\local-isolated-capture-child-validation\`.
- `real_provider_used=false`; `production_credentials_used=false`.

The child and launcher `--help` commands both completed successfully and
exposed only their nonsecret request/configuration arguments.

## 3. Baseline evidence

The manual baseline used one exact allocation and reconciled the canonical child
request, allocation, credential reference, and capture configuration before any
credential read. Evidence was written only to the dedicated ignored root.

| Evidence | Artifact ID | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Allocation | `9fbf963e-39b7-5231-8d0f-2f8eb8334650` | 2921 | `ce28558cb8f9586deae28b9baa6220cd358ddda0a72acf36f0aa976f134dc78d` |
| Child request | `7dff0b51-1be2-570e-b227-6885fe016c24` | 2592 | `ea1912b6cef02760d77368d5fbb070f1a4fe46e350dc980f70d925f5234bc4e2` |
| Credential reference | `aff0d3ef-acfb-5ee3-85f6-a7b5f1e90d03` | 770 | `dc521cbea64d7c46f08af7caa2c66998f02744a7886ef7c91b090cdb8931eb20` |

Release evidence ID was `a4d451ec-2346-3726-f72c-43d64c710968`; destination
evidence ID was `b5c755aa-ab10-38b3-d562-7bbde7f47ca8`. Reconciliation passed.

## 4. Credential Manager validation

The fake Credential Manager suite passed success, exact SID-before-read,
missing key/secret, wrong type, wrong persistence, empty, oversized, malformed,
cleanup, and redaction cases. A child-level missing-credential run returned
`CREDENTIAL_NOT_FOUND`, made zero provider calls, and published no snapshot.

The real read gate was attempted with two uniquely named, test-only generic
targets and synthetic values. Direct `CredWriteW` provisioning with
`CRED_PERSIST_LOCAL_MACHINE` returned Win32 error `1312`
(`ERROR_NO_SUCH_LOGON_SESSION`) on this host before the production adapter could
read the entries. `cmdkey` can create only session-persisted entries here, and
the production adapter correctly rejects that persistence. Any temporary probe
entries were removed; no production target was enumerated, rotated, or deleted.

The adapter construction defect discovered during this attempt was the missing
`ntdll.RtlSecureZeroMemory` export. The compatibility fallback was applied and a
native zeroization probe then passed. Because local-machine test credentials
could not be provisioned, the opt-in real Credential Manager integration remains
skipped; no successful real credential read is claimed.

## 5. Environment and process-isolation results

- The child environment contained exactly `SystemRoot`, `WINDIR`, `TEMP`,
  `TMP`, and `PYTHONUTF8`; injected `PATH`, `PYTHONPATH`, proxy, certificate,
  profile, developer, and secret-like variables were absent.
- Parent ambient `APCA_API_KEY_ID` and case-variant
  `apca_api_secret_key` were each rejected before process creation; the parent
  mapping remained unchanged.
- Fake suspended-launch instrumentation recorded one Job assignment, one
  resume, three process evidence files, and closure of process, thread, and Job
  handles.
- The opt-in real `CreateProcessW`/Job test passed (`1 passed`); the Credential
  Manager test was skipped for the provisioning limitation above.
- Launching with the virtual-environment redirector failed closed with a stable
  launcher error and three process evidence files, matching the documented
  active-process-limit constraint. The approved base interpreter succeeded.

## 6. One-call and provider-result scenarios

- Counting-fake transport: exactly one provider call; a second invocation was
  rejected before transport; no retry, fallback, or second provider was made.
- Successful fake SPY/QQQ capture: `SUCCEEDED`, disposition
  `RESPONSE_CONFIRMED`, snapshot verification `PASS`, and one independently
  verified snapshot publication. Result bytes contained no credential values.
- Fake provider classifications matched the closed contract:

  | Scenario | Classification | Disposition |
  | --- | --- | --- |
  | Authentication | `AUTHENTICATION_FAILED` | `RESPONSE_CONFIRMED` |
  | Permanent rejection | `PROVIDER_REJECTED` | `RESPONSE_CONFIRMED` |
  | Network before transport | `NETWORK_FAILED` | `MAY_HAVE_STARTED` |
  | Network after transport | `NETWORK_FAILED` | `MAY_HAVE_STARTED` |
  | Provider timeout | `TIMEOUT` | `MAY_HAVE_STARTED` |
  | Incomplete response | `INCOMPLETE_RESPONSE` | `RESPONSE_CONFIRMED` |
  | Snapshot publication failure | `SNAPSHOT_OUTPUT_FAILED` | secret-free result |
  | Internal child failure | `INTERNAL_FAILED` | `NOT_STARTED` |

## 7. Timeout and ambiguity results

The controlled timeout fired, attempted one Job termination, confirmed process
tree termination, and recorded `WALL_TIMEOUT`, `PROCESS_TREE_TERMINATED`,
`STDOUT_LIMIT_EXCEEDED`, and `STDERR_LIMIT_EXCEEDED`. The result remained
ambiguous; no zero-call proof or retry authority was claimed.

An isolated parent-crash injector called `os._exit` immediately after resume.
The pre-existing child-result artifact remained, only creation/resume evidence
was present, and no cleanup, repair, or relaunch was performed.

## 8. Redaction and resource-cleanup results

The dedicated validation root contains no fake credential sentinel, prefix, or
provider exception value. Fake Credential Manager entries were released and
their native bytearrays cleared; process, thread, and Job handles closed on
success, timeout, and resume-failure paths. Child stdout/stderr were not
persisted; the bounded-stream test retained only stable overflow diagnostics.

## 9. No-side-effect inventory

Before and after validation, the production authority, guarded-readiness,
lineage-head, paper-operation, and production snapshot roots were not used by
the manual commands. No history pointer advanced, terminal or snapshot was
selected, lineage changed, paper operation ran, or scheduler was installed.
Only the explicitly dedicated validation child/process/snapshot artifacts were
created.

## 10. Test and quality-gate results

- Focused isolated child/launcher/CLI/script tests: **44 passed, 1 skipped**.
- Related capture-attempt and snapshot tests: **135 passed, 2 skipped**.
- Additional readiness, snapshot, and safe-output regression tests: **151
  passed**.
- Full suite: **1956 passed, 12 skipped**.
- `.venv\Scripts\ruff.exe check .`: **passed**.
- `.venv\Scripts\ruff.exe format --check .`: **368 files already formatted**.
- `git diff --check`: **passed** (only the expected CRLF warning for the edited
  Python file).

## 11. Defects or deviations

1. The native zeroization export assumption was a concrete Windows defect and
   was fixed with an exported `RtlZeroMemory` fallback.
2. This host cannot provision `CRED_PERSIST_LOCAL_MACHINE` test credentials
   (`ERROR_NO_SUCH_LOGON_SESSION`); the real read gate is therefore unverified
   and remains opt-in/skipped.
3. No production provider call, production credential, retry, or authority-side
   effect was used.

## 12. GO/NO-GO recommendation for guarded-runner integration

**NO-GO.** Fake transport, artifact, isolation, timeout, ambiguity, redaction,
and cleanup behavior passed, but guarded-runner integration must remain disabled
until a dedicated account can provision and successfully read the exact
local-machine Credential Manager contract under an explicitly approved,
data-only validation procedure.
