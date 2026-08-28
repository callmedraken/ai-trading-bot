# Architecture 93 — GUI Verified Paper-Account State

## Status

GUI-A7 architecture checkpoint for bounded read-only presentation of one exact
verified simulated paper-account checkpoint state.

This architecture does not define operational account selection, lineage
traversal, paper-cycle execution, or brokerage. It defines only how already
reviewed offline checkpoint proof may be adapted into Qt-free presentation state
and later rendered by the GUI.

## Purpose

The GUI currently presents:

- read-only research results/comparison;
- one read-only paper-operation inspection;
- one offline-verified daily market-snapshot artifact.

The next operator-visible gap is account state: cash, positions, realized P&L,
checkpoint identity, and as-of time.

The repository already has two different reviewed offline proof paths:

1. GENESIS checkpoint verification through
   `verify_genesis_paper_account_checkpoint(...)`;
2. successor-edge verification through
   `verify_checkpointed_paper_cycle_successor_edge(...)`.

These proofs have different input requirements and must not be conflated. GUI-A7
creates one common presentation contract for the verified resulting account
state while preserving separate concrete verification adapters.

## Reviewed GENESIS boundary

The existing GENESIS verifier accepts exact checkpoint bytes plus optional
expected SHA-256/byte-length evidence.

A complete PASS exposes:

- reconstructed `PaperAccountCheckpoint`;
- restored compact `PaperLedger`;
- restoration evidence;
- verifier-computed checkpoint SHA-256 and byte length;
- no diagnostics.

The PASS proves strict canonical checkpoint parsing, deterministic checkpoint
identity, exact compact-state restoration, and canonical byte reconciliation.

GUI-A7b1 may consume only a complete GENESIS PASS.

## Reviewed successor boundary

A successor is not independently equivalent to a verified account state. The
existing successor verifier requires one exact checkpointed-cycle edge:

```text
prior checkpoint artifact
+ verified market-snapshot artifact
+ checkpointed-cycle report artifact
+ successor checkpoint artifact
+ identified market calendar
-> verify_checkpointed_paper_cycle_successor_edge(...)
```

A complete PASS exposes the replayed cycle result, successor checkpoint, and
restored successor ledger with no diagnostics.

The proof reconciles the successor against the replayed prior checkpoint,
verified snapshot, producing cycle report, checkpoint references, exact final
compact state, and restored ledger.

GUI-A7b2 may consume only a complete successor-edge PASS. It must never parse a
successor checkpoint alone and present it as verified account state.

## Common dependency direction

The allowed dependency direction is:

```text
Qt Paper Account page
    -> Qt-free GUI paper-account presentation models
    -> GuiApplicationService.get_paper_account_state()
    -> reviewed/injected read-only checkpoint adapter
    -> existing offline checkpoint/edge verifier
```

Qt must not import or invoke checkpoint verifiers directly.

## GUI-A7a presentation contract

GUI-A7a introduces immutable Qt-free presentation records:

```text
PaperAccountPageStatus
  VERIFIED
  UNAVAILABLE

PaperAccountCheckpointKindView
  GENESIS
  CYCLE_SUCCESSOR

PaperAccountPositionView
  symbol
  quantity
  total_cost_basis
  average_cost

VerifiedPaperAccountView
  checkpoint_kind
  sequence
  checkpoint_id
  lineage_id
  account_state_id
  compact_state_id
  as_of
  cash
  realized_profit_loss
  positions
  artifact_sha256
  artifact_byte_length

PaperAccountPageState
  status
  message
  account
```

Exact identifiers may be adjusted only by updating this architecture first;
semantics must remain equivalent.

## Common presentation semantics

`VERIFIED` means that the explicit input artifacts passed one of the reviewed
offline verification boundaries completely.

It does not mean:

- the checkpoint is operationally current;
- it is the newest checkpoint;
- it was selected by scanning a runtime directory;
- the GUI has authority to run the next paper cycle;
- the GUI has reconstructed full historical fills;
- market value or unrealized P&L is known.

The page therefore must label the state as an offline-verified checkpoint state,
not as a live/current account unless a future reviewed operational-selection
boundary proves that separately.

## Common bounded fields

### Identity

The presentation may expose only retained/reconciled nonsecret identity:

- checkpoint kind;
- checkpoint sequence;
- checkpoint UUID;
- lineage UUID;
- account-state UUID;
- compact-state UUID.

### Financial state

The presentation may expose:

- exact checkpoint as-of timestamp;
- exact cash;
- exact cumulative realized P&L represented by the verified final account state;
- ordered positions, each with symbol, quantity, total cost basis, and average
  cost.

All monetary/quantity values remain exact finite `Decimal` values in the Qt-free
contract. Formatting for display occurs only in the presentation layer using a
closed deterministic formatter.

GUI-A7 does not calculate:

- portfolio market value;
- equity;
- unrealized P&L;
- allocation percentages;
- mark-to-market prices.

Those values require an explicit valuation/price boundary and are deferred.

### Artifact evidence

The presentation may expose the verifier-computed SHA-256 and byte length for
the exact checkpoint artifact whose final account state is being presented.

For successor verification, this means the successor checkpoint artifact's
verifier-computed digest/length. The prior/report/snapshot artifact digests are
not part of the initial common account-state page; they remain proof inputs and
may be exposed later through a dedicated lineage/evidence view.

## Position bounds and order

The GUI presentation must preserve the verified compact-state position order.
It must not sort, deduplicate, merge, or recalculate positions.

Position count is bounded by the existing compact paper-ledger schema bound.
Presentation models must reject duplicate symbols, invalid symbols, nonfinite
Decimals, contradictory cost-basis/average-cost values that violate the
underlying verified model, or position counts above the existing bound.

The adapter should copy already-verified model values rather than independently
rederive financial state.

## Service contract

`GuiApplicationService` gains:

```text
get_paper_account_state() -> PaperAccountPageState
```

Default GUI startup remains deterministic and effect-free. Mock/research-only
services return one bounded `UNAVAILABLE` paper-account state explaining that no
verified checkpoint is connected.

No startup CLI flag or concrete adapter is added in A7a.

## GUI-A7b1 — GENESIS explicit-artifact adapter

A future `VerifiedGenesisPaperAccountInspectionService` may receive:

- one explicit GENESIS checkpoint `Path`;
- optional expected checkpoint SHA-256;
- optional expected checkpoint byte length.

It may:

1. read only that exact path once, bounded by
   `MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES`;
2. call `verify_genesis_paper_account_checkpoint(...)` exactly once;
3. map only a complete PASS to `VerifiedPaperAccountView`;
4. collapse any read/verification/adaptation failure to bounded `UNAVAILABLE`.

It must not scan directories, select a latest artifact, traverse lineage, write
files, or expose raw verifier diagnostic detail.

Because this is structurally analogous to accepted GUI-A6b1 after the common
contract is frozen, the implementation is suitable for Luna Extra High.

## GUI-A7b2 — successor-edge adapter

A successor adapter must receive explicit inputs for one complete reviewed edge.
At minimum these are the exact artifact paths required by
`verify_checkpointed_paper_cycle_successor_edge(...)` plus any frozen expected
artifact evidence required by the composition layer.

The adapter must:

1. read each explicitly supplied proof artifact within its existing schema bound;
2. construct/use the existing identified XNYS calendar boundary;
3. call the reviewed successor-edge verifier exactly once per state acquisition;
4. map only a complete PASS successor final compact state;
5. preserve exact successor sequence/identity/state values;
6. collapse every incomplete/failed edge to bounded `UNAVAILABLE`.

It must not:

- parse a successor checkpoint alone and treat that as sufficient proof;
- discover a predecessor or producing report by filename/directory scan;
- walk lineage recursively;
- repair missing proof artifacts;
- invoke a paper cycle to recreate evidence;
- weaken reference reconciliation because an artifact appears locally valid.

This adapter requires Sol High implementation/review because its correctness
depends on preserving multi-artifact replay, reference, and lineage semantics.

## GUI-A7b3 — Qt rendering

After A7a/A7b1/A7b2 semantics are accepted, the Paper Account page may render
one immutable `PaperAccountPageState` obtained once during `MainWindow`
construction.

The page may render:

- verified/unavailable status and bounded message;
- checkpoint kind/sequence and IDs;
- as-of timestamp;
- cash and realized P&L;
- a bounded read-only positions table;
- checkpoint artifact SHA-256 and byte length.

All model/service-derived strings must use `Qt.TextFormat.PlainText`.

Navigation away and back must not reread/reverify artifacts.

No action buttons are added.

Mechanical Qt work is suitable for Luna Extra High once the contract is frozen.

## Failure behavior

Any inability to obtain a complete reviewed verification PASS becomes a generic
bounded `UNAVAILABLE` state.

The GUI must not surface:

- raw parser/runtime exception text;
- verifier diagnostic detail strings;
- arbitrary filesystem paths;
- raw checkpoint/report/snapshot JSON;
- order/fill history reconstructed outside reviewed proof.

A later architecture may expose a closed diagnostic vocabulary if operator needs
justify it.

## Explicit non-goals

GUI-A7 does not:

- determine the current/latest paper account;
- discover checkpoint artifacts;
- traverse checkpoint lineage;
- display fill/order history;
- run, retry, resume, or recover a paper cycle;
- create proposals, risk decisions, orders, or fills;
- value positions at current market prices;
- calculate equity/unrealized P&L/allocation;
- mutate checkpoints or reports;
- open production SQLite;
- access C1/C2/C3 authority;
- access Windows Credential Manager;
- contact Alpaca or brokerage;
- add scheduler/recovery/operator-effect controls.

## Future operational account selection

A future GUI milestone may show an operationally current account only after a
reviewed application/runtime boundary can prove which checkpoint is current.
That design must not be implemented as Qt-side directory enumeration or "highest
sequence wins" logic.

If it requires durable runtime lineage traversal, authority state, recovery
state, or automatic artifact selection, the architecture and implementation
require Sol High review.

## Testing contract

### A7a

Pure-Python tests prove:

- verified/unavailable state invariants;
- exact UUID/int/datetime/Decimal types;
- exact finite Decimal enforcement;
- bounded unique ordered positions;
- strict lowercase SHA-256 and nonnegative byte length;
- deterministic unavailable state from default GUI services;
- Qt-free imports;
- no runtime verifier, filesystem, network, credential, or authority dependency
  in presentation models.

### A7b1

Focused tests prove:

- one explicit GENESIS artifact read only;
- existing artifact-size bound enforced before verification;
- exactly one GENESIS verifier call;
- complete PASS mapping;
- expected hash/length support;
- failure sanitization;
- no directory discovery or mutation.

### A7b2

Focused tests prove:

- all successor proof inputs are explicit;
- each read obeys the existing artifact bound;
- exactly one successor-edge verifier call;
- complete PASS mapping of the successor final state only;
- incomplete/mismatched prior/report/snapshot/successor evidence cannot produce
  VERIFIED state;
- no directory discovery, lineage traversal, paper execution, or mutation;
- failure sanitization.

### A7b3

Qt tests prove:

- unavailable/verified rendering;
- exact identity/financial/artifact fields;
- bounded read-only positions table;
- literal plain-text handling;
- no action controls;
- one service acquisition at `MainWindow` construction and no reinspection on
  navigation.

## Model routing

- Architecture 93 / A7a contract: Sol Medium.
- A7b1 GENESIS adapter: Luna Extra High after A7a acceptance.
- A7b2 successor-edge adapter: Sol High.
- A7b3 Qt rendering: Luna Extra High after adapter acceptance.
- Any operational current-account selection or durable lineage traversal: Sol
  High.
