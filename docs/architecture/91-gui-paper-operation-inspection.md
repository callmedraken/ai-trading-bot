# Architecture 91 — GUI Paper-Operation Inspection

## Status

GUI-A5a architecture and Qt-free presentation-contract checkpoint.

This checkpoint extends the reviewed GUI foundation with bounded read-only presentation of one exact paper-operation inspection result. It does not add paper execution, discovery/history scanning, brokerage, scheduling, recovery actions, production authority, C3 access, Credential Manager access, or network access.

## Reviewed source boundary

The existing paper-operation inspection boundary is `inspect_paper_operation_root(...)` in `trading_bot.cli.paper_operation_inspection`.

That reviewed function classifies one exact paper operation without writing or executing a paper cycle. Its result contains:

- one closed classification: `PENDING`, `ALREADY_APPLIED`, `CONFLICTING`, or `BLOCKED`;
- exact operation, terminal-checkpoint, and application UUIDs;
- an optional retained receipt path;
- exactly one closed `PaperOperationInspectionCode` diagnostic.

GUI-A5 must preserve that scope. The current inspected service is not a general paper-history, fill-history, order-history, or account-state query. The GUI must not infer or invent those views from filesystem enumeration.

## Dependency direction

The allowed direction is:

```text
Qt Paper page
    -> Qt-free GUI paper presentation models
    -> GuiApplicationService.get_paper_state()
    -> reviewed/injected read-only paper inspection adapter
    -> inspect_paper_operation_root(...)
```

The Qt layer must not import or call `paper_operation_inspection` directly.

A future concrete adapter may call the reviewed inspector only when the composition layer supplies an explicit operation root and already-verified paper-operation inputs. Widgets must not construct `VerifiedPaperOperationInputs`, derive operation authority, enumerate arbitrary roots, or execute a paper cycle.

## GUI-A5a presentation contract

GUI-A5a introduces immutable Qt-free presentation records:

- `PaperPageStatus`: `INSPECTED` or `UNAVAILABLE`;
- `PaperInspectionClassification`: exact presentation equivalents of the four reviewed inspection classifications;
- `PaperInspectionDiagnostic`: exact closed presentation equivalents of all reviewed inspection diagnostic codes;
- `PaperOperationInspectionView`: classification, exact UUID identities, optional bounded receipt path, and one diagnostic;
- `PaperPageState`: either one inspected view or a bounded unavailable state.

These are presentation values only. `PENDING` does not authorize execution, `ALREADY_APPLIED` does not authorize mutation, and `BLOCKED`/`CONFLICTING` are displayed states rather than recovery controls.

Receipt paths are bounded presentation strings and remain optional. Raw exceptions, arbitrary filesystem text, provider text, credentials, and native error text must not flow into these models.

## Service contract

`GuiApplicationService` gains:

```text
get_paper_state() -> PaperPageState
```

GUI-A5a keeps the default shell deterministic and effect-free: the mock-backed application service returns a bounded `UNAVAILABLE` paper state explaining that no inspected operation is connected.

A concrete read-only paper inspection adapter is intentionally deferred to GUI-A5b so adapter input acquisition and failure sanitization can be reviewed separately from the presentation model.

## Failure behavior

A later adapter must convert any inability to obtain a reviewed inspection result into a bounded `UNAVAILABLE` state. It must not expose raw exception strings or turn malformed/unsafe filesystem state into an operator action.

An `INSPECTED` state must contain exactly one `PaperOperationInspectionView`. An `UNAVAILABLE` state must contain no inspection payload.

## Explicit non-goals

GUI-A5a does not:

- execute `run_paper_operation` or any paper-cycle path;
- construct strategy/risk/order requests;
- read or write brokerage state;
- enumerate or summarize arbitrary paper-operation history;
- invent recent fills, orders, P&L, or account balances;
- mutate paper-operation receipts, transitions, or checkpoints;
- access production SQLite, C1/C2/C3, Credential Manager, or Alpaca;
- add scheduler, recovery, cancel, retry, or resume controls;
- add Qt wiring beyond the existing placeholder Paper page.

## Testing contract

GUI-A5a tests remain pure Python and must prove:

1. paper presentation enums exactly preserve the reviewed closed vocabulary;
2. inspected/unavailable state invariants reject contradictory payloads;
3. receipt-path presentation is bounded;
4. both GUI application-service implementations return the deterministic unavailable paper state;
5. the public GUI contract remains Qt-free.

No production effect, filesystem inspection, Credential Manager read, provider call, broker call, or Qt dependency is required for GUI-A5a tests.

## Follow-up

GUI-A5b may implement the concrete read-only adapter and Paper-page rendering after this contract is accepted. It must preserve explicit inputs, bounded failures, and the dependency direction above. Any execution or recovery control requires a separate architecture checkpoint.
