# Guarded capture-readiness dry-run validation

## Scope

Focused tests cover canonical schedule, policy, and decision artifacts; strict
configuration; capture-only pure readiness; guarded orchestration; immutable
publication; release behavior; and thin-script import. Tests use explicit
timestamps and deterministic local evidence. They do not contact a provider,
read credentials, open a network connection, create a snapshot, run a paper
operation, advance a head, invoke Task Scheduler, retry, wait, or start a
background process.

## Deterministic evidence coverage

The reviewed schema-1 decision vector is:

| Field | Value |
| --- | --- |
| decision UUID | `28768732-f993-512c-a995-6c62d9662f83` |
| canonical byte length | `1606` |
| canonical SHA-256 | `7c9e4ae977eee583817744b6bf1fc92a824b4ef26f60ccd9b805814f415965d3` |

Tests prove strict schedule and policy round trips, compact sorted JSON with one
final newline, decision UUID recomputation, noncanonical rejection,
observation-time sensitivity, exact evidence binding, and rejection of
provider permission without `READY` plus complete proposed-attempt evidence.

## Configuration coverage

Tests prove exact schema-1 fields and fixed phase; canonical UUID, hash,
timestamp, date, enum, SID, symbol, policy, and bounded integer validation;
duplicate, unknown, missing, float, BOM, and noncanonical-time rejection;
ordered artifact references; nullable selection; and path-independent session
and launch identities.

The loader opens only the configuration file. Referenced inputs remain unopened
until after mutex acquisition and verified lease-start publication.

## Readiness coverage

The scheduled-readiness suite covers first-attempt `READY`, too-early and
backoff `NOT_READY`, expired and exhausted policy, manual disable, health gates,
valid selected-snapshot completion, terminal chronology, future skew,
staleness, conflicting ordinals, duplicate eligibility, and selection
mismatch. It also proves operation target, receipt, and coordinator inputs are
not capture-only gates and that the pure evaluator performs no filesystem,
environment, socket, or clock access.

## Orchestration and publication coverage

Injected mutex and publisher tests prove:

- normal acquisition publishes start evidence before head or readiness work;
- `READY` records `CAPTURE_ATTEMPT_ALLOWED` without provider invocation or
  attempt allocation;
- identical repeated runs reuse byte-identical start, decision, and release
  evidence;
- `ALREADY_HELD` performs no head, readiness, or audit-root filesystem work;
- abandoned ownership publishes start and release without evaluator work;
- head and lease-start failures prevent readiness;
- decision failure still produces a release attempt;
- release-publication failure still performs native release and close;
- native release failure is surfaced;
- manual disable publishes verified blocked evidence;
- conflicting existing decision bytes fail closed;
- successful layouts contain only canonical final lock and decision artifacts.

Existing platform-gated Windows launch-guard integration proves the real
`Global\` mutex returns `ALREADY_HELD` to a contender and
`ABANDONED_ACQUIRED` after owner termination. Non-Windows platforms skip those
tests; no fallback exists.

## No-side-effect guarantees

The runner does not import the Alpaca adapter, credential loader, snapshot
capture function, broker, paper coordinator, lineage mutation APIs, subprocess
launcher, scheduler, retry, sleep, daemon, or notification integration. Its
only writes are immutable lease and dry-run decision evidence under the
explicit audit root. Proposed attempt evidence is never allocated as an
attempt record or snapshot.

## Required commands

```text
.venv\Scripts\python.exe -m pytest tests\runtime\test_guarded_capture_readiness.py tests\cli\test_guarded_capture_readiness_config.py tests\cli\test_guarded_capture_readiness.py tests\scripts\test_evaluate_guarded_capture_readiness.py -q
.venv\Scripts\python.exe -m pytest tests\runtime\test_scheduled_readiness.py tests\runtime\test_launch_guard.py tests\cli\test_windows_launch_guard.py tests\cli\test_windows_launch_guard_integration.py tests\runtime\test_local_lineage_head.py tests\cli\test_local_lineage_head.py tests\cli\test_daily_snapshot_config.py tests\cli\test_daily_snapshot_capture.py -q
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
```

CLI smoke:

```text
.venv\Scripts\python.exe scripts\evaluate_guarded_capture_readiness.py --help
```
