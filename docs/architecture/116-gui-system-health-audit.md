# Architecture 116 — GUI-A9 Read-Only System Health and Audit

## Status

GUI-A9 architecture contract.

GUI-A9 upgrades the existing placeholder System page into a bounded read-only
System Health & Audit view. It operates only on presentation state that
`MainWindow` has already acquired through the accepted GUI service boundary.

GUI-A9 does not add a new runtime reader, production authority reader,
filesystem scanner, provider call, broker call, scheduler call, credential
reader, or effect path.

## Goal

Give the operator one consolidated read-only view of:

- the local GUI environment/mode;
- the presentation availability of Research, Paper Operation, Paper Account,
  Market Data, and Operations;
- bounded audit identities already present in those page states;
- whether any presented component is explicitly blocked.

The page is diagnostic presentation only. It is not an operational readiness
decision and it grants no authority.

## Data-flow rule

The allowed data flow is:

```text
existing GuiApplicationService
  -> MainWindow acquires existing bounded page states exactly once
  -> pure build_system_health_state(...)
  -> immutable SystemHealthPageState
  -> SystemHealthPage
```

GUI-A9 must not call the service again and must not perform I/O.

Navigation to System must remain presentation-only.

## Inputs

The pure adapter receives only exact existing GUI presentation objects:

```text
ApplicationOverview
ResearchPageState
PaperPageState
PaperAccountPageState
MarketDataPageState
OperatorOperationsPageState
```

It must not accept:

- paths;
- SQLite connections;
- C1/C2/C3 authority objects;
- credential handles;
- provider clients;
- broker clients;
- scheduler handles;
- effect gates as caller-supplied authority;
- raw runtime exceptions.

## System health model

Introduce Qt-free immutable presentation models:

```text
SystemHealthStatus:
  READ_ONLY_READY
  ATTENTION

SystemComponentHealth:
  key
  title
  status
  detail

SystemAuditEntry:
  source
  evidence_kind
  identifier
  sha256 | None

SystemHealthPageState:
  status
  message
  environment
  displayed_mode
  components
  audit_entries
```

All fields are bounded. Audit SHA-256 values, when present, must be exact
lowercase 64-character hashes.

`READ_ONLY_READY` means the already-presented local GUI state contains no
explicit blocked presentation classification. It must not be interpreted as
production readiness, trading readiness, or permission to execute.

`ATTENTION` means one or more already-presented components has an explicit
blocked/conflicting condition.

Unavailable sources are normal in the local read-only GUI and do not by
themselves make System Health `ATTENTION`.

## Component mapping

The adapter mirrors already-acquired presentation states only.

Research:

- LOADED -> AVAILABLE
- UNAVAILABLE -> UNAVAILABLE

Paper Operation:

- UNAVAILABLE -> UNAVAILABLE
- INSPECTED with BLOCKED or CONFLICTING -> BLOCKED
- other INSPECTED classifications -> AVAILABLE

Paper Account:

- VERIFIED -> AVAILABLE
- UNAVAILABLE -> UNAVAILABLE

Market Data:

- VERIFIED -> AVAILABLE
- UNAVAILABLE -> UNAVAILABLE

Operations:

- UNAVAILABLE -> UNAVAILABLE
- AVAILABLE with a blocked strategy preview -> BLOCKED
- AVAILABLE with any displayed effect gate open -> BLOCKED
- otherwise AVAILABLE

The adapter must not reinterpret domain/runtime state that is not already
present in the GUI models.

## Audit entries

GUI-A9 may copy only identities/evidence already exposed by existing
presentation models.

Allowed examples:

- Research report ID and experiment result ID;
- Paper operation ID, terminal checkpoint ID, and application ID;
- Paper Account checkpoint ID plus verified artifact SHA-256;
- Market Data snapshot ID plus verified artifact SHA-256;
- Operations selected snapshot ID and displayed account checkpoint ID.

No audit entry may contain:

- credentials or secret-store values;
- raw exception text;
- environment dumps;
- filesystem discovery results;
- reusable authority;
- private keys/tokens;
- raw C1 evidence;
- provider response bodies.

Audit entries are display evidence only and carry no authority.

## Qt page

Introduce `SystemHealthPage`.

The page must show:

- title: `System Health & Audit`;
- fixed read-only/no-authority notice;
- overall read-only status;
- environment and displayed mode;
- component health rows/cards;
- bounded audit evidence.

Long IDs and hashes must remain selectable. Read-only text fields may be used;
there must be no effect button.

The page must remain usable at the existing 920x620 minimum window size.

## MainWindow integration

`MainWindow` continues to acquire each service state once at construction.

After acquiring the existing states, it calls the pure system-health adapter and
constructs `SystemHealthPage` from the returned immutable state.

No new method is added to `GuiApplicationService` for A9. This deliberately
prevents System navigation from becoming a second service/runtime read path.

Stable page IDs remain:

```text
home
research
paper
paper-account
market-data
operations
system
```

## Failure behavior

The pure adapter uses exact-type validation.

If malformed presentation state is supplied, construction fails during the
existing GUI composition boundary rather than attempting runtime recovery.

GUI-A9 must not catch arbitrary runtime errors because it performs no runtime
operation.

## Testing

Focused tests must prove:

1. exact model bounds and validation;
2. pure mapping for all existing page statuses;
3. unavailable sources do not create `ATTENTION`;
4. Paper BLOCKED/CONFLICTING produces `ATTENTION`;
5. Operations blocked preview/open displayed gate produces `ATTENTION`;
6. audit records copy only allowed IDs/hashes;
7. no source path, receipt path, exception text, credentials, or authority is
   retained;
8. MainWindow acquires each service state exactly once;
9. System navigation adds no service calls;
10. minimum-size Qt view keeps IDs/hashes selectable;
11. the full GUI suite remains green.

## Visual gate

Inspect at minimum:

- default local read-only startup;
- A8 combined Research + Market Data + GENESIS Paper Account;
- successor Paper Account startup;
- 920x620 minimum window.

Confirm:

- System title/scope is clear;
- unavailable sources look neutral rather than failed;
- blocked status is visually distinct when tested;
- audit IDs/hashes remain selectable;
- no effect controls appear;
- no production-readiness claim appears.

## Model routing

This checkpoint is local presentation composition with a frozen boundary and
known files. Direct ChatGPT implementation is appropriate; Luna Extra High would
also be sufficient for mechanical follow-up changes.

Escalate to Sol High if any requested implementation requires production
observability acquisition, C1/C2/C3 access, scheduler inspection/mutation,
Credential Manager, provider/network access, settlement/recovery, brokerage, or
live-state discovery.

## Explicit non-goals

GUI-A9 does not:

- connect normal GUI startup to production O2;
- inspect Task Scheduler;
- read production SQLite;
- read Credential Manager;
- discover latest/current artifacts;
- enumerate operation directories;
- run D8-A/D8-B/D9-A;
- recover or retry anything;
- infer production readiness;
- authorize paper or live execution.

## Acceptance

GUI-A9 is accepted only when final evidence can state:

```text
SYSTEM_HEALTH_FROM_PRESENTATION_ONLY=True
SERVICE_REREADS=0
NEW_RUNTIME_IO=False
PRODUCTION_O2_ACCESS=False
C1_C2_C3_ACCESS=False
CREDENTIAL_ACCESS=False
PROVIDER_NETWORK_ACCESS=False
SCHEDULER_ACCESS=False
PAPER_EXECUTION=False
SETTLEMENT_EFFECT=False
RECOVERY_EFFECT=False
BROKERAGE_ACCESS=False
AUDIT_EVIDENCE_BOUNDED=True
VISUAL_GATE=PASSED
FULL_REGRESSION=PASSED
```
