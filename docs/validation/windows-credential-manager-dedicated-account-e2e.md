# Windows Credential Manager dedicated-account investigation

Validation date: 2026-07-30. This was a read/write probe only; it did not call
Alpaca, use production credentials, enumerate credentials, advance capture
authority, install a scheduled task, or modify production code.

## 1. Files changed

- `docs/validation/windows-credential-manager-dedicated-account-e2e.md`

This investigation added only this document. The existing zeroization fallback
in `src/trading_bot/runtime/windows_credentials.py` was reviewed and left
unchanged.

## 2. Account and logon-session environment

- Process token account: `DESKTOP-I4DOKM7\CodexSandboxOffline`.
- Process SID: `S-1-5-21-1397534616-3988210162-180023805-1007`.
- Shell environment account: `DESKTOP-I4DOKM7\John` (a different account).
- Token account: enabled local account (`PrincipalSource=Local`), not a member
  of the local Administrators group.
- Shell environment account: enabled (`PrincipalSource=MicrosoftAccount`).
- Token elevation: `false`.
- Logon type: `2 (Interactive)`; token session ID `1`; the active console session
  is session `1`.
- `VaultSvc`: running; an exact missing-target `CredReadW` returned `1168`, so
  Credential Manager is available.
- The approved base Python and virtual-environment Python both received the
  same token SID, interactive logon type, and token session ID.
- No RDP, service, or scheduled-task logon was observed. An elevated comparison
  and a separate dedicated-account run were unavailable without an additional
  interactive user session.

The shell's `John` environment/profile is not proof of the process account. The
child and launcher run under the `CodexSandboxOffline` token boundary.

## 3. Minimal probe results

The probe used unique, nonsecret generic targets and dummy UTF-8 bytes. It called
only `CredWriteW`, `CredReadW`, `CredFree`, and exact-target `CredDeleteW`; it did
not enumerate existing credentials. `GetLastError` was captured immediately
after each failed native call.

`CREDENTIALW` matched the production definition: size `80` bytes, with
`TargetName` offset `8`, `CredentialBlob` offset `40`, `Persist` offset `48`,
and `UserName` offset `72`. Both the base interpreter
(`C:\Program Files\Python314\python.exe`) and the virtual environment produced
the same results:

| Persistence | CredWriteW | CredReadW | Read type/persistence/blob | CredDeleteW |
| --- | --- | --- | --- | --- |
| `CRED_PERSIST_SESSION` | success | success | generic / session / 38 bytes | success |
| `CRED_PERSIST_LOCAL_MACHINE` | failed, `1312` | failed, `1168` | not present | failed, `1168` |
| `CRED_PERSIST_ENTERPRISE` (diagnostic only) | failed, `1312` | failed, `1168` | not present | failed, `1168` |

Changing the optional `UserName` from null to a harmless non-null value did not
change the local-machine result: both writes returned `1312`.

## 4. Root cause of error 1312

`net helpmsg 1312` reports: “A specified logon session does not exist. It may
already have been terminated.” The probe isolates the cause to the current
managed token/session boundary, not the native structure or Python executable:

1. The exact production layout, pointer lifetime, Unicode target, UTF-8 blob,
   type, and immediate error capture are correct; session persistence writes,
   reads, and deletes successfully.
2. Base Python and virtual-environment Python behave identically.
3. Local-machine and enterprise persistence fail at `CredWriteW` before any
   read, while session persistence works.
4. The process token is the local `CodexSandboxOffline` account, but the shell
   environment is the separate `John` Microsoft account/profile. This managed
   sandbox token does not expose a usable persistent Credential Manager logon
   session for `CRED_PERSIST_LOCAL_MACHINE`.

Therefore `1312` is a token/account/profile-context limitation of this managed
execution environment. It is not a reason to weaken the production adapter to
session persistence or add another secret store.

## 5. Dedicated-account provisioning procedure

The supported runbook for a real validation is:

1. Select or create a dedicated non-administrator local Windows account for the
   capture child; do not use a Microsoft account, the Codex sandbox account, or
   a production operator account.
2. Log on interactively once as that account so the intended profile and logon
   session exist.
3. From a manually launched, non-elevated process under that same account,
   run the provisioning probe with the approved base Python runtime.
4. Generate a unique lowercase stage and exactly two versioned targets:
   `AITradingBot/AlpacaMarketData/v1/<stage>/KeyId/1` and
   `AITradingBot/AlpacaMarketData/v1/<stage>/SecretKey/1`.
5. Write harmless dummy values with `CRED_TYPE_GENERIC` and
   `CRED_PERSIST_LOCAL_MACHINE`; verify the write result, owner SID, type,
   persistence, and bounded UTF-8 value through exact `CredReadW` calls.
6. Build a reference using the same SID and target names, then read it through
   `WindowsCredentialManagerReader`. Verify only the two provider mapping keys,
   redacted representations, and native cleanup. Do not contact Alpaca.
7. Delete only the two exact test targets with `CredDeleteW`; verify each exact
   read returns `1168`. Never enumerate, rotate, or delete unrelated targets.
8. Log off the dedicated account safely. Repeat a read-only lifecycle check only
   if the account is explicitly approved for that purpose.

`cmdkey` is not a substitute for this runbook on this host because it creates
session-persisted entries and cannot establish the required local-machine
persistence contract.

## 6. Real production-adapter read result

No successful local-machine production-adapter read is claimed. With two unique
session-persisted synthetic entries, the production adapter verified the current
SID and then failed closed with `WindowsCredentialInvalidError` for unsupported
persistence; exception text did not contain either dummy value.

The opt-in integration test was run with
`RUN_WINDOWS_CREDENTIAL_MANAGER_TESTS=1` and failed at the expected missing
dedicated test target (`WindowsCredentialNotFoundError`). No production target
or credential was used.

## 7. Cross-account and redaction results

- Cross-account read denial could not be exercised because the dedicated account
  is not provisioned in this environment.
- Elevated execution was not required for the available probe, but an elevated
  comparison was not attempted because no approved elevated session was
  available.
- Fake and child tests confirm exact-target reads, no enumeration, SID-before-
  read, native release, redacted `repr`/`str`, sanitized exceptions, and no
  secret values in result or output artifacts.
- No plaintext file, environment, command-line, `.env`, machine-scope DPAPI, or
  alternate-account fallback was added.

## 8. Tests and quality gates

- Focused Windows credential and isolated-child tests: **21 passed, 1 skipped**.
- Opt-in real Credential Manager integration: **1 failed as expected** because
  dedicated targets were absent; the failure was `WindowsCredentialNotFoundError`.
- Full suite: **1956 passed, 12 skipped**.
- `.venv\Scripts\ruff.exe check .`: **passed**.
- `.venv\Scripts\ruff.exe format --check .`: **368 files already formatted**.
- `git diff --check`: **passed**.

## 9. Defects or deviations

1. No production code was changed during this investigation.
2. The managed Codex token is not the shell's `John` account and cannot create
   local-machine Credential Manager entries; the dedicated-account runbook was
   therefore not executable here.
3. Elevated, cross-account, and post-logoff lifecycle checks remain unverified.
4. Enterprise persistence was probed only to diagnose `1312`; it is not an
   approved storage choice.

## 10. GO/NO-GO recommendation for guarded-runner integration

**NO-GO.** Keep guarded-runner integration disabled until the exact dedicated,
non-administrator account can provision, read, delete, and lifecycle-verify the
two local-machine test targets through the production adapter. If that account
also returns `1312`, perform an architecture review rather than weakening the
persistence, ownership, or secret-isolation contract.
