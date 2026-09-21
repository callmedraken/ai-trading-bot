# Architecture 118 — GUI-A11 Read-Only Evidence Explorer

## Status

GUI-A11 architecture contract.

GUI-A11 improves the accepted GUI-A10 Evidence Timeline with local-only
filtering and search over the immutable evidence entries already present in
`EvidenceTimelinePageState`.

It does not add a service method, service read, artifact reader, discovery path,
runtime authority, credential access, provider/broker call, scheduler access,
or effect.

## Goal

Make the A10 timeline practical to inspect as evidence grows while preserving
the same read-only authority boundary.

The operator may:

- filter by one closed evidence source;
- search visible bounded evidence text;
- see how many entries match;
- clear filters locally.

Filtering changes presentation only. It does not reload, rediscover, verify,
mutate, settle, recover, execute, or authorize anything.

## Data flow

The allowed flow is:

```text
existing six GuiApplicationService reads
  -> existing EvidenceTimelinePageState
  -> EvidenceTimelineFilter
  -> filter_evidence_timeline_entries(...)
  -> EvidenceTimelinePage rendering
```

No new service call is permitted.

## Filter model

Add a Qt-free immutable model:

```text
EvidenceTimelineFilter:
  query: str
  source: EvidenceTimelineSource | None
```

Requirements:

- query is an exact string;
- query length is capped at 200 characters;
- unsupported control characters are rejected;
- source is either `None` or an exact `EvidenceTimelineSource`;
- an empty/whitespace-only query behaves as no text filter.

## Pure filter

Add:

```text
filter_evidence_timeline_entries(
    state: EvidenceTimelinePageState,
    filter_state: EvidenceTimelineFilter,
) -> tuple[EvidenceTimelineEntry, ...]
```

The function:

- performs no I/O;
- preserves original A10 entry order;
- never uses wall-clock time;
- source-filters exactly;
- text-searches only already-visible bounded presentation fields:
  source label, title, identifier, optional SHA-256, detail, and rendered
  timestamp;
- uses case-insensitive matching;
- never reads source paths, receipt paths, files, runtime objects, or hidden
  domain state.

## Page behavior

The existing navigation page ID remains `evidence` and the title remains
`Evidence Timeline`.

Add an `Evidence explorer` control row containing:

- a bounded search field;
- an `All sources` / per-source selector;
- a `Showing X of Y entries` summary.

The timeline cards remain read-only and selectable.

If the underlying state contains no entries, retain the accepted A10 empty
state.

If evidence exists but the active filter matches nothing, show a distinct
presentation-only no-match message.

The page remains scrollable and usable at the existing 920x620 minimum size.

## Security and authority

GUI-A11 must not:

- add a `GuiApplicationService` method;
- reread a service on filter changes;
- discover directories or "latest" files;
- open/read/write artifacts;
- access production O2;
- acquire C1/C2/C3;
- read Credential Manager;
- inspect or mutate Task Scheduler;
- call a provider or broker;
- execute paper/live actions;
- settle, recover, retry, or mutate durable state;
- expose Research source paths or Paper receipt paths.

## Tests

Focused tests must prove:

1. filter-model bounds/type validation;
2. exact source filtering;
3. case-insensitive text matching across visible evidence fields;
4. original timeline ordering is preserved;
5. empty query behaves as no query filter;
6. no-match behavior is distinct from underlying empty evidence;
7. filter changes do not call a service;
8. Evidence navigation still performs zero service rereads;
9. evidence identifier/hash fields remain read-only/selectable;
10. no effect button/control is introduced;
11. minimum-size scrolling remains usable;
12. the complete GUI suite remains green.

## Visual gate

Inspect:

- default empty startup;
- populated Research + Market Data + GENESIS;
- populated view with source filter/search active at 920x620.

Confirm:

- controls are clearly presentation-only;
- match count is understandable;
- cards retain stable A10 ordering;
- filtering does not obscure the read-only/not-authority scope;
- identifiers/hashes remain usable;
- no path/receipt/authority/effect data appears.

## Model routing

A11 is a bounded presentation-only checkpoint over a frozen A10 contract.
Direct ChatGPT implementation is appropriate.

Mechanical cleanup may use Luna Extra High if delegation becomes useful.
Escalate to Sol High only if the requested scope crosses into authority,
credentials, production discovery, external effects, scheduler mutation,
settlement/recovery, brokerage, or live controls.

## Acceptance

GUI-A11 is accepted only when final evidence can state:

```text
EXPLORER_FROM_A10_STATE_ONLY=True
SERVICE_REREADS_ON_FILTER_CHANGE=0
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
