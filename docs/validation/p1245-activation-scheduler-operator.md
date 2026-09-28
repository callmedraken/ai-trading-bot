# P124-5A activation and scheduler operator — source checkpoint

Status: implementation candidate for exact source review. This document and
this branch authorize no protected execution, scheduler change, activation
lease, provider call, Paper-v2 effect, broker effect, or live effect.

The operator lives in `scripts/d10_activation_scheduler_operator.py`, outside
the signed S5-R10 executable inventory. Governed source and launch-guard bytes
are unchanged. Architectures 122, 124, and 126 control its behavior.

## Authority and ordering

The public entry points are zero-input `preflight()` and `reconcile()`, plus
`execute(execute_p1245=True)`. The CLI requires both `execute` and the explicit
`--execute-p1245` switch for the protected boundary. Read-only modes reject that
switch. There are no caller identity, task, SID, path, timestamp, credential,
scheduler definition, retry, or rollback options. Import performs no protected
host observation or mutation. Fake dependencies exist only on the private test
composition; the host entry points construct the fixed native transports.

Admission proves elevated Administrator membership, the protected parent and
canonical signed S5-R10 deployment, exact manifest/source bytes and native
identities, and the exact guard. It pins deployment
`9f3d111b-25bb-5ee4-9abf-f5215a32b826`, attestation
`4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2`,
certified HEAD `c5cc0b01301600daf17f1114f4451dca2c9d7a1f`, and tree
`bfacfadaa14315d2d378abcc0f1e4bc7c42034f1`.

The historical retired root, replacement staging, all lease names, cache,
installing trust/source names, and unexpected reserved siblings must be absent.
All protected files/directories satisfy the existing native owner/DACL,
non-reparse, single-link, fixed-local-NTFS and same-volume policies. Complete
signed inventory and native identity observations must agree across two reads.

The accepted zero-argument Architecture-126 D5 COM observer independently
qualifies the predecessor. The additional P124-5 COM observer checks its empty
end boundary and the Pacific host timezone, and supplies independent D10
readback. Every semantic field and exact type is validated. XML length/digest
must be stable between fresh COM reads; historical XML bytes are diagnostic.

Protected execution follows this sequence:

1. Complete read-only admission.
2. Acquire the Trading password interactively without echo. Repeat admission
   after that pause; any changed fact blocks before registration.
3. Freeze one source-clock UTC activation instant at whole-second precision.
   Derive the canonical lease and existing D10 deployment spec from it. Both
   ends equal activation plus exactly seven days, including DST transitions.
4. Invoke the fixed PowerShell Task Scheduler transport once. It independently
   derives the same start/end from the private operator record, rechecks the D5
   predecessor, and uses COM `RegisterTaskDefinition` with **TASK_UPDATE=4** on
   the existing fixed task. It never creates an alternative task or calls Run.
5. Independently reread COM and require the exact D10 semantics. Reread signed
   deployment and absent lease facts before staging anything.
6. Create the fixed `.tmp` lease with CREATE_NEW, the protected publication ACL,
   write-through and flush; reopen and verify exact bytes and native policy.
   Atomically move it without replacement to `.installing` and reverify the
   same file identity. Recheck signed deployment and COM before final arming.
7. Atomically publish `.installing` to the absent final lease without
   replacement. This is the final arming action. Reopen the final file and
   verify bytes, same native identity, owner/DACL, non-reparse, single-link and
   local-NTFS facts.
8. Independently reread signed deployment, COM, and final lease. Return execute
   PASS only when all facts agree and the frozen window is still active.

The fixed task retains Trading SID
`S-1-5-21-1397534616-3988210162-180023805-1009`, Password/LUA, daily 01:30 Pacific,
StartWhenAvailable, IgnoreNew, power/wake, priority 7, PT1H and zero retry. Its
only action is the exact production Python and Architecture-124 guard argument
vector. The seven-day end is represented with its explicit Pacific UTC offset;
the start remains the exact first future 01:30 from the existing spec.

The reviewed native create/flush/ACL primitives are reused without broadening
`WindowsDeploymentBackend`, P124-2, or P124-3 path authority. The separate lease
subclass permits only fixed staging creates and same-directory no-replace
moves. Its literal native allowlist and inherited ACL masks are checked against
the frozen `D10ActivationLeasePublicationContract` in focused tests.

## Credential transport

Only the final protected Python invocation may prompt on an interactive console.
Redirected/non-interactive input blocks. There is no CLI/environment/file/evidence
credential source. The acquired password is marshaled once to the fixed child
through an anonymous stdin pipe, never a command argument or file. The child
passes it to the Password-logon COM registration and releases its references.
Temporary in-process strings cannot be guaranteed to be zeroed by Python or
PowerShell; they are never deliberately persisted, logged, or serialized into
evidence. Raw child output and exception text are never emitted. Unknown CLI
arguments also produce a sanitized error instead of echoing supplied values.

The pipe's activation value is internal transport from the protected operator,
not a public timestamp input. The child accepts no task semantics or paths and
independently derives both boundaries. Reconciliation can derive a diagnostic
plan from observed scheduler end time when no lease exists; that plan never
becomes execute, publication, retry, or recovery authority.

## Failure and reconciliation

- A proven pre-call scheduler failure reports NOT_CALLED. A native call failure,
  timeout, malformed response, or uncertain result reports INDETERMINATE.
  Neither disposition permits lease publication or another scheduler attempt.
- A returned scheduler call still requires independent exact semantic readback.
  Drift blocks lease creation.
- After verified D10 registration, a lease staging failure leaves the truthful
  D10-scheduler/lease-absent state. Staging remnants are preserved. No rollback,
  cleanup, renewal, or automatic retry occurs.
- Once final publication is attempted, any failure or disagreement is an
  indeterminate protected state, even if a read-only diagnostic subsequently
  observes a valid final file. Diagnostic success never upgrades the failed
  execute result or authorizes retry.
- Duplicate executions are blocked by fresh predecessor/lease admission. The
  same in-process operator also rejects reuse.

Independent reconciliation reports D5_UNARMED, D10_SCHEDULER_LEASE_ABSENT,
ARMED_VERIFIED, NOT_YET_ACTIVE_VERIFIED, EXPIRED_VERIFIED, partial-publication
reconciliation required, or INDETERMINATE. Incomplete states cannot report an
execute PASS. Evidence is capped, uses source-owned stage/disposition values,
and includes exact admitted semantic state, native identity digests, the plan,
publication state, and explicit source/provider/Paper-v2/broker/live NOT_RUN.

## Source verification and next gate

Focused tests use fake native readers/writers, a fake credential, a fake COM
transport, and bounded-process mocks. Static PowerShell parsing does not execute
either helper. No real operator mode, scheduler COM read/update, lease write,
credential prompt, guard/source launch or trading effect is part of this source
checkpoint. Full certification and host qualification remain deferred.

From the source worktree, using the existing development environment:

```powershell
$P1245Python = 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe'
& $P1245Python -B -m pytest -q tests/runtime/test_d10_activation_scheduler_operator.py tests/runtime/test_d10_protected_replacement_windows.py tests/runtime/test_d10_protected_deployment.py tests/runtime/test_personal_desktop_d10_activation_lease.py --basetemp (Join-Path $PWD ('.pytest-p1245-review-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))) --tb=short
& $P1245Python -B -m ruff check --no-cache scripts/d10_activation_scheduler_operator.py scripts/d10_protected_deployment_windows.py scripts/d10_protected_replacement_windows.py tests/runtime/test_d10_activation_scheduler_operator.py
& $P1245Python -B -m ruff format --no-cache --check scripts/d10_activation_scheduler_operator.py scripts/d10_protected_deployment_windows.py scripts/d10_protected_replacement_windows.py tests/runtime/test_d10_activation_scheduler_operator.py
git diff 2db185a703f9b4f85ca0a581d330afff25f34a7f..HEAD --check
```

Next: exact commit/diff review, then the separately selected source-certification
and read-only host gates. A protected scheduler/lease invocation requires fresh
explicit human authorization after those gates. No execution authorization is
conveyed by this source commit or its push.

`docs/PROJECT_STATUS.md` and `docs/AI_TRADING_BOT_HANDOFF.md` were reviewed. They
remain current for the accepted P124-4 checkpoint and the unapproved P124-5
protected boundary; source acceptance/closeout remains a later review step.
