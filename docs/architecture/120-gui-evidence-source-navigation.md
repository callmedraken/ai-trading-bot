# Architecture 120 — GUI-A13 Read-Only Evidence -> Source Page Navigation

## Status

GUI-A13 architecture contract.

GUI-A13 adds presentation-only reverse navigation from an existing Evidence
Timeline card to the already-acquired GUI page for that evidence source.

It does not add service reads, artifact readers, filesystem discovery,
production authority, credential access, scheduler access, provider/broker
calls, durable mutation, or execution effects.

## Goal

Allow an operator reviewing one Evidence Timeline entry to move directly to the
corresponding already-rendered source page without rereading or rediscovering
anything.

This is page-level navigation only. A13 does not claim that the destination page
highlights the exact identifier, proves lineage, establishes readiness, or grants
authority.

## Existing inputs

A13 may use only the existing `EvidenceTimelineEntry.source` value already
present in the accepted A10-A12 presentation state.

No additional domain object or runtime capability is permitted.

## Closed destination mapping

Evidence sources map to existing GUI page IDs exactly:

```text
EvidenceTimelineSource.RESEARCH        -> research
EvidenceTimelineSource.PAPER_OPERATION -> paper
EvidenceTimelineSource.PAPER_ACCOUNT   -> paper-account
EvidenceTimelineSource.MARKET_DATA     -> market-data
EvidenceTimelineSource.OPERATIONS      -> operations
```

No fuzzy inference or fallback destination is permitted.

## Navigation target

Introduce one immutable Qt-free presentation target:

```text
EvidenceSourcePageTarget:
  source: EvidenceTimelineSource
  page_id: EvidenceSourcePage
```

where `EvidenceSourcePage` is a closed enum whose values are the five page IDs
above.

Requirements:

- both values are exact enum members;
- source/page combinations must match the closed mapping;
- no identifiers, hashes, paths, receipts, credentials, handles, runtime
  objects, or capabilities are retained.

A pure adapter converts one `EvidenceTimelineEntry` to its exact source-page
target using only `entry.source`.

## Evidence page behavior

Each rendered Evidence card may show one visually secondary
`View source page` control.

Selecting it emits only the immutable source-page target.

It must not:

- change the Evidence entry;
- reread a service;
- read an artifact;
- discover a file;
- mutate durable state;
- invoke a runtime effect.

A11 filtering and A12 exact System -> Evidence targeting remain unchanged.

## MainWindow coordination

`MainWindow` owns the page switch.

When it receives a valid source-page target, it calls the existing
presentation-only page selection mechanism for the target page ID.

It does not rebuild the destination state, call a service again, or attempt to
reacquire the source artifact.

## Semantics

A13 guarantees only:

```text
Evidence source -> already-acquired source page
```

It does not guarantee exact row/card selection inside the source page.

This distinction must be visible in architecture/tests and must not be
reinterpreted as provenance or authority.

## Security and authority

GUI-A13 must not:

- add or change `GuiApplicationService`;
- reread any service during navigation;
- discover directories or "latest" artifacts;
- read/write artifacts;
- access production O2;
- acquire C1/C2/C3;
- read Credential Manager;
- inspect/mutate Task Scheduler;
- call providers or brokers;
- execute paper/live actions;
- settle, recover, retry, or mutate durable state;
- expose Research source paths or Paper receipt paths;
- imply that page navigation establishes production readiness or authority.

## Tests

Focused tests must prove:

1. closed Evidence-source -> page mapping;
2. target validation rejects mismatched source/page pairs;
3. every existing Evidence source maps to exactly one destination;
4. each rendered evidence card has one source-navigation control;
5. clicking Research evidence selects the Research page;
6. clicking Market Data evidence selects the Market Data page;
7. service call count remains exactly six;
8. existing A11 filtering remains intact;
9. existing A12 System -> Evidence exact targeting remains intact;
10. navigation introduces no runtime I/O/effect control;
11. 920x620 layout remains usable;
12. complete GUI regression remains green.

## Visual gate

Inspect:

- populated Evidence page at 920x620;
- Research evidence card with `View source page`;
- Market Data evidence card with `View source page`;
- resulting Research and Market Data pages after navigation.

Confirm:

- the control is visually secondary;
- navigation reads as page navigation, not execution;
- existing Evidence read-only/not-authority scope remains visible before click;
- destination page is the already-rendered source page;
- no path/receipt/credential/authority/effect data appears because of A13.

## Model routing

A13 is a bounded presentation-only milestone over accepted A8-A12 contracts.
Direct ChatGPT implementation is appropriate.

Escalate only if scope crosses into source rediscovery, runtime authority,
credentials, scheduler mutation, external effects, settlement/recovery,
brokerage, or live controls.

## Acceptance

GUI-A13 is accepted only when final evidence can state:

```text
EVIDENCE_TO_SOURCE_PAGE_PRESENTATION_ONLY=True
CLOSED_SOURCE_PAGE_MAPPING=True
SERVICE_REREADS_ON_SOURCE_NAVIGATION=0
A11_FILTERING_PRESERVED=True
A12_EXACT_TARGETING_PRESERVED=True
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
