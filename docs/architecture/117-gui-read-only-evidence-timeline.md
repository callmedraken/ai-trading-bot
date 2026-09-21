# Architecture 117 — GUI-A10 Read-Only Evidence Timeline

## Status

GUI-A10 architecture contract.

GUI-A10 adds a read-only Evidence Timeline page built only from the bounded GUI
presentation states that `MainWindow` already acquired for Research, Paper
Operation, Paper Account, Market Data, and Operations.

It adds no new runtime reader, service method, filesystem discovery, provider
call, broker call, scheduler call, credential read, or effect path.

## Goal

Provide one chronological/readable audit-oriented page that answers:

- which explicit/local evidence is currently represented in the GUI;
- which identities and hashes belong to that evidence;
- when timed evidence occurred;
- which evidence is untimed presentation metadata.

The timeline is not a durable audit log, production history, or operational
readiness decision. It is a presentation-only view of already-acquired state.

## Data flow

The allowed flow is:

```text
existing GuiApplicationService
  -> MainWindow performs the existing six state reads once
  -> build_evidence_timeline_state(...)
  -> immutable EvidenceTimelinePageState
  -> EvidenceTimelinePage
```

No new `GuiApplicationService` method is permitted for A10.

Navigating to Evidence must not trigger a service reread or any I/O.

## Inputs

The pure adapter receives exactly:

```text
ResearchPageState
PaperPageState
PaperAccountPageState
MarketDataPageState
OperatorOperationsPageState
```

It must not accept paths, credentials, runtime authority objects, provider
clients, broker clients, scheduler handles, database handles, or raw exceptions.

## Timeline model

Introduce immutable Qt-free models:

```text
EvidenceTimelineSource:
  RESEARCH
  PAPER_OPERATION
  PAPER_ACCOUNT
  MARKET_DATA
  OPERATIONS

EvidenceTimelineEntry:
  source
  title
  identifier
  occurred_at | None
  sha256 | None
  detail

EvidenceTimelinePageState:
  message
  entries
```

All strings are bounded. SHA-256 text, when present, is exact lowercase
64-character text. `occurred_at`, when present, is timezone-aware.

## Evidence mapping

The adapter may copy only fields already present in reviewed GUI presentation
models.

Research LOADED:
- report ID;
- experiment result ID;
- no timestamp because the compact GUI report model exposes none.

Paper Operation INSPECTED:
- operation ID;
- terminal checkpoint ID;
- application ID;
- no receipt path;
- no timestamp because the GUI inspection model exposes none.

Paper Account VERIFIED:
- checkpoint ID;
- artifact SHA-256;
- account `as_of` timestamp;
- checkpoint kind/sequence in bounded detail.

Market Data VERIFIED:
- snapshot ID;
- artifact SHA-256;
- `captured_at` timestamp;
- target XNYS session in bounded detail.

Operations AVAILABLE:
- selected snapshot ID when already present;
- account checkpoint ID when already present;
- completed session may appear in detail but is not invented as an instant;
- no effect-gate value is represented as authority.

Unavailable states contribute no timeline entries.

## Ordering

Timeline ordering is deterministic:

1. entries with `occurred_at`, newest first;
2. untimed entries after timed entries;
3. ties and untimed entries preserve the stable source/evidence construction
   order.

The adapter must not use wall-clock time.

## Page

Add page ID `evidence` and navigation label `Evidence`.

The page title is `Evidence Timeline`.

The page shows:
- a fixed read-only scope notice;
- a count of represented evidence entries;
- zero-state text when nothing is represented;
- one card per entry;
- source/title;
- optional timestamp;
- selectable identifier;
- selectable SHA-256 when present;
- bounded detail.

There are no buttons or effect controls.

The page must be usable at the existing 920x620 minimum window size and use a
scroll area when needed.

## Overview

The normal Overview may include an informational Evidence card stating that the
timeline is derived from already-acquired read-only presentation state.

That card must not claim durable history or production readiness.

## Security and authority

GUI-A10 must not:
- discover directories or latest/current files;
- open new files;
- read production O2;
- acquire C1/C2/C3;
- read Credential Manager;
- inspect Task Scheduler;
- call providers or brokers;
- execute paper/live actions;
- settle or recover;
- expose Research source paths or Paper receipt paths.

## Tests

Focused tests must prove:

1. exact bounded model validation;
2. deterministic newest-first ordering for timed entries;
3. stable untimed ordering;
4. unavailable states produce no entries;
5. Research paths and Paper receipt paths are excluded;
6. expected IDs/hashes are copied exactly;
7. no service reread is added;
8. navigation to Evidence causes no service calls;
9. identifiers/hashes are read-only/selectable;
10. minimum-size page remains usable;
11. the full GUI suite remains green.

## Visual gate

Inspect:
- default startup;
- populated Research + Market Data + GENESIS;
- successor Paper Account at 920x620.

Confirm:
- timeline purpose is clear;
- timestamped entries appear ahead of untimed entries;
- long IDs/hashes remain selectable;
- zero-state is truthful;
- no path/receipt/authority/effect data appears;
- no effect controls exist.

## Model routing

This is a bounded presentation-only checkpoint with frozen inputs. Direct
ChatGPT implementation is appropriate. Mechanical cleanup can use Luna Extra
High if delegation becomes useful.

Escalate to Sol High if any requested change requires production discovery,
authority acquisition, credentials, scheduler inspection, provider/broker
network access, settlement/recovery, or execution.

## Acceptance

GUI-A10 is accepted only when final evidence can state:

```text
TIMELINE_FROM_PRESENTATION_ONLY=True
SERVICE_REREADS_ON_EVIDENCE_NAVIGATION=0
NEW_RUNTIME_IO=False
FILESYSTEM_DISCOVERY=False
PRODUCTION_O2_ACCESS=False
C1_C2_C3_ACCESS=False
CREDENTIAL_ACCESS=False
PROVIDER_NETWORK_ACCESS=False
SCHEDULER_ACCESS=False
PAPER_EXECUTION=False
SETTLEMENT_EFFECT=False
RECOVERY_EFFECT=False
BROKERAGE_ACCESS=False
PATH_OR_RECEIPT_DISCLOSURE=False
VISUAL_GATE=PASSED
FULL_REGRESSION=PASSED
```
