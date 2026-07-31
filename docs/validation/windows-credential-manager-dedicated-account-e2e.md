# Windows Credential Manager dedicated-account end-to-end validation

Validation date: 2026-07-30. This validation used only harmless, test-only
generic credentials. It did not contact a brokerage, use production
credentials, enumerate Credential Manager, place orders, install a scheduled
task, or modify production code.

## 1. File changed

- `docs/validation/windows-credential-manager-dedicated-account-e2e.md`

## 2. Dedicated account

- Observed account: `DESKTOP-I4DOKM7\Trading`.
- Previously recorded SID:
  `S-1-5-21-1397534616-3988210162-180023805-1009`.
- The validation ran under this dedicated non-administrator account.

## 3. Lifecycle evidence

The dedicated account successfully:

1. Provisioned exactly two harmless `CRED_TYPE_GENERIC` test entries using
   `CRED_PERSIST_LOCAL_MACHINE`.
2. Read both exact test targets through the production
   `WindowsCredentialManagerReader`.
3. Passed
   `test_real_credential_manager_reads_only_dedicated_test_targets`.
4. Deleted both exact test targets successfully.
5. Logged off and back on.
6. Repeated provisioning and the production-adapter integration test
   successfully after the logon transition.
7. Confirmed `CRED_PERSIST_LOCAL_MACHINE` behavior across the required logoff
   and logon lifecycle.
8. Cleaned up all test-only Credential Manager entries and opt-in environment
   variables.

The validation used exact-target operations only. No credential enumeration,
production target access, or secret material was recorded.

## 4. GO/NO-GO recommendation

- **GO** for manually invoked guarded capture-runner integration development
  and fault-injection validation.
- **NO-GO** for unattended provider invocation or Task Scheduler deployment
  until the remaining ACL, market-hours, monitoring, backup, and operational
  gates are approved.

## 5. Quality gate

- `git diff --check`: passed.
