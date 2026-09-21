# Architecture 119 — GUI-A12 Read-Only System / Evidence Cross-Navigation

## Status

GUI-A12 architecture contract.

GUI-A12 adds presentation-only cross-navigation from bounded System Health &
Audit evidence entries to matching entries already present in the accepted A11
Evidence Timeline / Explorer.

It does not add any service method, service reread, filesystem discovery,
artifact reader, runtime authority, credential access, scheduler access,
provider/broker call, durable write, or execution effect.

## Goal

Allow an operator reviewing one bounded System audit identity to jump directly
to the matching Evidence Timeline presentation without reloading or rediscovering
anything.

The cross-navigation is convenience only. It does not establish provenance,
authority, readiness, settlement status, or execution permission.

## Existing inputs

A12 may use only the already-built objects that `MainWindow` constructs from
its existing six service reads:

```text
SystemHealthPageState
EvidenceTimelinePageState
```

No seventh service read is permitted.

## Closed source mapping

System audit source labels map to Evidence sources exactly:

```text
Research        -> EvidenceTimelineSource.RESEARCH
Paper Operation -> EvidenceTimelineSource.PAPER_OPERATION
Paper Account   -> EvidenceTimelineSource.PAPER_ACCOUNT
Market Data     -> EvidenceTimelineSource.MARKET_DATA
Operations      -> EvidenceTimelineSource.OPERATIONS
```

No fuzzy source inference is permitted.

## Navigation target

Introduce one immutable Qt-free presentation target:

```text
EvidenceNavigationTarget:
  source: EvidenceTimelineSource
  identifier: str
```

Requirements:

- source is an exact `EvidenceTimelineSource`;
- identifier is canonical non-empty bounded text;
- identifier bound is the accepted A10 evidence identifier bound;
- no paths, hashes, runtime objects, handles, credentials, or capabilities are
  retained.

A pure adapter may convert one `SystemAuditEntryView` to an
`EvidenceNavigationTarget` using only the closed source mapping and the already
displayed identifier.

Unknown source labels must fail closed by returning no navigation target.

## System page behavior

Each bounded System audit card may show one presentation-only
`View in Evidence` control when its source can be mapped by the closed mapping.

Selecting it emits only the corresponding bounded navigation target.

It must not:

- reread a service;
- read a file;
- inspect production state;
- mutate the System state;
- invoke any runtime effect.

## MainWindow coordination

`MainWindow` owns page coordination.

When it receives one valid Evidence navigation target, it:

1. switches to the existing `evidence` page;
2. applies the target source to the existing A11 source filter;
3. sets the existing A11 search field to the exact identifier;
4. resets the Evidence scroll position to the top.

The Evidence page may expose one bounded presentation method for this purpose,
for example:

```text
show_navigation_target(target: EvidenceNavigationTarget) -> None
```

That method may update only the existing A11 filter controls and visible cards.
It performs no service call or I/O.

## Matching semantics

Cross-navigation means exact source plus exact identifier filtering.

If the target no longer matches the immutable Evidence state, the accepted A11
no-match state is shown. A12 must not search other files, broaden source scope,
or infer an alternative identity.

## Security and authority

GUI-A12 must not:

- add or change `GuiApplicationService`;
- reread any GUI service for navigation;
- discover directories or "latest" artifacts;
- read/write artifacts;
- access production O2;
- acquire C1/C2/C3;
- read Credential Manager;
- inspect or mutate Task Scheduler;
- call providers or brokers;
- execute paper/live actions;
- settle, recover, retry, or mutate durable state;
- expose Research source paths or Paper receipt paths;
- create a new authority or readiness interpretation.

## Tests

Focused tests must prove:

1. closed source mapping is exact and fail-closed;
2. navigation target validation is bounded/exact;
3. System audit controls exist only for mappable bounded entries;
4. selecting one target switches to Evidence;
5. source filter becomes the exact mapped Evidence source;
6. search becomes the exact identifier;
7. matching cards are the expected source/identifier only;
8. navigation causes zero service rereads;
9. no runtime I/O or effect control is introduced;
10. unknown/unmappable source does not navigate;
11. minimum-size 920x620 layout remains usable;
12. the complete GUI suite remains green.

## Visual gate

Inspect:

- populated System Health & Audit;
- one `View in Evidence` navigation from Research;
- one navigation from Market Data or Paper Account;
- resulting Evidence page at 920x620.

Confirm:

- navigation intent is clear and visually secondary;
- read-only/not-authority scope remains visible;
- exact source and identifier filters are visibly applied;
- matching identifier/hash fields remain selectable;
- no execution/authority meaning is implied;
- no path/receipt data appears.

## Model routing

A12 is a bounded presentation-only milestone over accepted A9-A11 contracts.
Direct ChatGPT implementation is appropriate.

Mechanical cleanup may use Luna Extra High if useful. Escalate to Sol High only
if scope crosses into production discovery, authority, credentials, scheduler
mutation, external effects, settlement/recovery, brokerage, or live controls.

## Acceptance

GUI-A12 is accepted only when final evidence can state:

```text
CROSS_NAV_FROM_PRESENTATION_ONLY=True
SYSTEM_TO_EVIDENCE_EXACT_SOURCE_IDENTIFIER=True
SERVICE_REREADS_ON_CROSS_NAVIGATION=0
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
