# PD4 Operator Observability Parallel Plan

## Purpose

Build a read-only operator-observability surface while the armed D5 capture-only
warm-up accumulates its natural six-session selected-C3 suffix.

This work is deliberately isolated from the three operational worktrees. It
must not alter the armed D5 scheduler/runtime, the certified D7 production
boundary, or the certified D8/D9 settlement source.

Branch base:

```text
branch: feature/pd4-operator-observability
base commit: 60b0471743979479f1788311207477a37a8dd331
base tree:   7c7ab312bd4474fa7389e471087cd8216e77e70e
```

The base already contains the accepted D5, D6/D7, and D8/D9 source lineage plus
the D9 source-certification closeout documentation.

## Non-authority rule

Operator observability is a presentation and diagnostic layer only. It does not
become trading authority.

It must never:

- call a market-data provider;
- open any production effect gate;
- start, stop, install, modify, or retry Task Scheduler jobs;
- publish a D7 decision;
- provision production storage;
- execute or settle a Paper-v2 operation;
- perform receipt recovery;
- submit broker or live orders;
- read or expose secrets/credentials;
- manufacture or replace C1, P2/C3, Paper-v2, D7, D8, or D9 authority;
- treat GUI state, cached display state, or operator-selected files as authority.

Any production-backed observation must reuse an existing reviewed read-only
authority and expose only a bounded sanitized view.

## Initial product surface

The operator surface should eventually present these independent read-only
sections:

1. **D5 warm-up status**
   - classification (`WARMING_UP`, `READY`, `SESSION_GAP`, `BLOCKED`);
   - required six-session window;
   - selected sessions and `selected_count / 6`;
   - current completed XNYS session;
   - current selected snapshot identity when available.

2. **Selected-C3 market-data audit**
   - session and symbol;
   - daily raw OHLCV values;
   - provider/feed/operation identity;
   - capture/provider-as-of timestamps;
   - snapshot/selection/attempt/terminal identities;
   - canonical/source/artifact integrity hashes and byte lengths;
   - explicit read-only proof (`provider_call_performed = false`,
     `database_mutation_performed = false`).

3. **Effect-gate status**
   - all eight production gate values;
   - closed is the expected display state outside an exact reviewed effect
     boundary;
   - the display cannot alter gates.

4. **Paper-v2/account view**
   - reuse existing read-only account and operation-inspection services;
   - show current checkpoint, cash, positions, lineage/receipt status, and
     bounded diagnostics without mutation controls.

5. **Strategy readiness / explanation**
   - before six selected sessions: show insufficient-history state and the
     selected closes that are present;
   - after six selected sessions: allow a read-only deterministic preview of
     the exact source-owned MA 3/5 inputs and resulting strategy intent;
   - preview output is never D7 publication authority and cannot be passed as
     D7-C authority.

Task Scheduler health remains a separate administrator read-only inspection in
the initial observability milestone because normal non-elevated principals may
not be permitted to enumerate the protected D5 task. The GUI must not elevate
itself or weaken the task ACL to obtain display data.

## Checkpoints

### O1 — pure view models and adapters

Add Qt-free immutable observability models and pure adapters over already
verified/read-only result objects.

Requirements:

- no production I/O;
- no clocks hidden inside deterministic display adaptation;
- no provider/scheduler/storage/broker calls;
- explicit unavailable/blocked states rather than fabricated defaults;
- focused unit tests for all mappings and failure-closed behavior.

Accepted O1 checkpoint:

```text
HEAD  ee1f44022340563f94f334f897a5e88859f7c6c7
TREE  76f98eb64a3205a88dcd86a2c541feaaea9939fa
focused tests: 16 passed
Ruff check/format: PASS
diff checks: PASS
worktree: CLEAN
```

Acceptance record:

```text
docs/validation/pd4-operator-observability-o1-acceptance.md
```

### O2 — bounded Trading-principal read-only snapshot command

**Source accepted.** Real-host Trading-principal qualification is next.

```text
HEAD  70672c65c7ecf0923516da7c2b57934dc950dbc8
TREE  762dc13000f435c58f31c9750c0cd22aac582840
focused O1+O2 tests: 32 passed
Ruff check/format: PASS
diff checks: PASS
worktree: CLEAN
```

Acceptance record:

```text
docs/validation/pd4-operator-observability-o2-acceptance.md
```

Add one zero-semantic-argument source-checkout operator command that may be run
under the intended non-admin `Trading` principal.

It may:

- validate C1 through the existing production read authority;
- run effects-closed G6/read-only selected-C3 history inspection;
- read selected C3 snapshots through P2;
- read existing Paper-v2 account/operation state through existing read-only
  interfaces;
- report the eight committed/process-local gate states;
- emit one sanitized JSON snapshot for operator review.

It may not call G5, D7-C, D8-B, receipt recovery, storage provisioning, or any
other effectful boundary.

The source-checkout launcher must select its checkout `src` explicitly and use
no caller-supplied semantic trading arguments.

### O3 — native GUI Operations page

**ACCEPTED**

```text
HEAD  fd504503d1fb468c0a2791e00d296da983afeb5a
TREE  bb2a19189dc72a939456653db2cbd745fa237822
focused tests: 71 passed
Ruff check/format: PASS
diff checks: PASS
worktree: CLEAN
```

Acceptance record:

```text
docs/validation/pd4-operator-observability-o3-acceptance.md
```

The accepted page is read-only and uses the O1/O2 presentation boundary.

The GUI must consume bounded observability state rather than import production
private helpers or implement independent trading/authority logic.

Initial sections:

- D5 warm-up progress;
- selected-C3 audit table;
- eight-gate state;
- Paper-v2/account summary;
- strategy readiness.

No buttons on this page may perform production effects.

### O4 — deterministic strategy preview

**ACCEPTED** at HEAD `2fab48301530a89df21391c047f848eb3fd97272`,
TREE `f8df06396a5203367bb9b0abdbcfd167bfa46d67`.
Operator-supplied evidence: 266 focused tests passed; Ruff check/format and both
diff checks passed; worktree clean. See
[O4 acceptance](pd4-operator-observability-o4-acceptance.md).

The following describes the accepted scope:

After O1–O3 are accepted, add a read-only strategy explanation based only on
already-verified selected-C3 history and existing source-owned strategy
configuration.

For incomplete history it reports why no production-ready strategy decision can
be formed. For complete history it displays the exact deterministic inputs and
result while remaining explicitly non-authoritative for D7 publication.

## Follow-up review escalation — 2026-09-19

O4 historical source acceptance is recorded above. Follow-up implementation is
stopped for Sol High review of inherited ambient Decimal arithmetic and
proposal-ID normalization. See
[reproduction and remaining phases](pd4-operator-observability-o4-review-escalation.md).
69 focused tests passed; this does not resolve the identity compatibility issue.
No source, gate, production composition or operational worktree was changed.

## Verification cadence

Each O1–O4 checkpoint uses focused tests and Ruff/format/diff checks only.
Do not rerun the expensive full repository suite after every observability
checkpoint.

Before integration, combine the observability branch with the accepted core PD4
line using a normal reviewed merge, then run one final integration certification
on the exact intended merged tree. The known Architecture-77 fixed repository
arbiter namespace may require the already accepted split Windows certification
procedure if the chosen integration worktree has the same repository-local ACL
condition.

## Post-6/6 core integration plan

The Git history is intentionally cumulative:

```text
develop
  -> D5 armed source
     -> D6/D7 source + D7 certification docs
        -> D8/D9 settlement source + D9 certification docs
```

Therefore D5 and D7 are not independent branches that need to be merged into
`develop` one by one. The newest accepted core descendant contains them by
ancestry.

When D5 reaches natural 6/6, do not merge merely because history is ready. The
protected operational sequence remains:

```text
6/6 selected C3 history
-> D7-A fresh Trading-principal read-only qualification
-> separately authorized D7-C first publication
-> D7-D read-only reconciliation
-> wait for execution session E to complete and selected C3(E)
-> D8-A fresh read-only settlement qualification
-> separately authorized one D8-B settlement effect
-> D9-A fresh independent read-only reconciliation
-> accept first unattended end-to-end cycle
```

Production evidence/docs created on the D7 branch after 6/6 should be merged
normally into the settlement/core descendant before the D8 production sequence.
Because the settlement line already contains D7 source, that merge is expected
to carry only later D7 operational evidence/documentation unless a reviewed
correction is required.

After the first D7/D8/D9 end-to-end cycle is accepted, freeze the exact core
integration candidate. D10 then defines the bounded unattended simulated-paper
soak and scheduler composition. Core source should be merged to `develop` only
at a reviewed integration checkpoint; merge approval remains explicit.

The operator-observability branch remains separate during those protected
production steps. Once the core PD4 candidate is accepted:

1. normally merge the latest accepted core branch into
   `feature/pd4-operator-observability` (no rebase/force-push);
2. resolve only genuine GUI/docs conflicts and re-review the exact diff;
3. run focused observability/GUI tests;
4. run one full integration certification on the exact combined tree;
5. merge the combined branch to `develop` only with explicit operator approval;
6. verify resulting `develop` HEAD/tree and preserve the old operational
   branches/worktrees until post-merge verification is complete.

This ordering keeps production authority validation independent from optional
operator presentation work while still delivering one coherent integrated
product tree.

## Current protected state

As of this plan:

```text
D5 warm-up: 3/6, WARMING_UP
D7 production: not invoked; first publication protected
D8 production settlement: not invoked; protected
D9 production reconciliation: not invoked
D8/D9 source: certified
all eight committed effect gates: false
production/live trading: NO-GO
```
