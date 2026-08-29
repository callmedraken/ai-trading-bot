# GUI-A7 verified paper-account state validation plan

## 1. Purpose

This plan validates Architecture 93,
`docs/architecture/93-gui-verified-paper-account-state.md`.

GUI-A7 presents one exact offline-verified simulated paper-account checkpoint
state. It does not identify the operationally current account and does not add
paper execution controls.

## 2. A7a common presentation-contract gate

Before any checkpoint adapter is implemented, freeze Qt-free models for:

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

Tests must prove:

- `VERIFIED` requires exactly one complete account view;
- `UNAVAILABLE` requires no account view;
- messages are nonblank and bounded;
- checkpoint kind is closed to GENESIS/CYCLE_SUCCESSOR;
- sequence is an exact nonnegative integer;
- identity fields are exact UUIDs;
- as-of is an exact timezone-aware datetime;
- cash/P&L/position numbers are exact finite Decimals;
- positions are bounded, unique by symbol, and preserve supplied order;
- artifact SHA-256 is exact lowercase 64-character hex;
- artifact byte length is a nonnegative exact integer.

Do not add equity, unrealized P&L, market value, or allocation fields because no
reviewed valuation boundary supplies them here.

## 3. GUI service gate

`GuiApplicationService` gains exactly one read-only method:

```text
get_paper_account_state() -> PaperAccountPageState
```

All default GUI compositions return deterministic `UNAVAILABLE` state until an
explicit checkpoint adapter is injected.

The service protocol and presentation models remain importable without PySide6,
runtime checkpoint verifiers, filesystem reads, network, credentials, or C3.

## 4. A7b1 GENESIS adapter gate

The concrete GENESIS adapter receives:

- one explicit checkpoint `Path`;
- optional expected checkpoint SHA-256;
- optional expected checkpoint byte length.

It must read only that exact file and enforce
`MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES` before verification.

It calls:

```text
verify_genesis_paper_account_checkpoint(...)
```

exactly once for one service-state acquisition.

Only a complete PASS with reconstructed checkpoint/ledger/restoration evidence
maps to `VERIFIED`.

PASS mapping tests prove exact mapping of:

- kind = GENESIS;
- sequence;
- checkpoint/lineage/account-state/compact-state UUIDs;
- as-of timestamp;
- cash;
- current cumulative realized P&L;
- ordered compact positions;
- verifier-computed checkpoint SHA-256 and byte length.

The adapter must not reconstruct alternate financial values after PASS.

## 5. A7b1 GENESIS failure/no-effect gate

The following become bounded `UNAVAILABLE`:

- missing/unreadable artifact;
- oversized artifact;
- malformed optional evidence;
- verifier FAIL;
- parser/schema/reconciliation/restoration error;
- unexpected adaptation failure.

Raw exception strings, verifier diagnostic details, and paths must not escape.

Tests must prove no directory discovery, mutation, paper execution, network,
Credential Manager, production SQLite, C1/C2/C3, or brokerage access.

## 6. A7b2 successor-edge proof gate

The successor adapter must not accept one successor path as sufficient proof.
Its composition requires the explicit proof artifacts needed by the reviewed
edge verifier:

- prior checkpoint artifact;
- verified daily-snapshot artifact;
- checkpointed-cycle report artifact;
- successor checkpoint artifact;
- identified XNYS calendar boundary;
- optional expected successor SHA-256/byte length when supplied.

Each artifact read must be bounded by its existing schema maximum.

For one service-state acquisition, call:

```text
verify_checkpointed_paper_cycle_successor_edge(...)
```

exactly once.

Only a complete edge PASS maps to `VERIFIED`.

## 7. A7b2 successor mapping gate

For edge PASS, map only the verified successor final account state:

- kind = CYCLE_SUCCESSOR;
- successor sequence;
- successor checkpoint/lineage/account-state/compact-state UUIDs;
- successor as-of timestamp;
- successor cash;
- successor final cumulative realized P&L;
- successor ordered compact positions;
- verifier-computed successor checkpoint SHA-256 and byte length.

Do not expose report/prior/snapshot raw payloads or reinterpret replay semantics.

The initial common account page does not need prior/report/snapshot references.
Those may be added later through a dedicated evidence/lineage architecture.

## 8. A7b2 proof-integrity/no-effect gate

Tests must prove that all of the following fail closed to `UNAVAILABLE`:

- missing prior checkpoint;
- missing snapshot;
- missing producing report;
- missing successor;
- mismatched prior/report/snapshot/successor references;
- edge verifier FAIL;
- malformed successor expected evidence;
- adaptation error.

Tests must also prove the adapter does not:

- enumerate directories;
- find a predecessor by filename;
- choose a highest/latest sequence;
- recurse through lineage;
- execute or recover a paper cycle;
- mutate/repair any artifact;
- access network, credentials, production SQLite, C1/C2/C3, or brokerage.

Because this boundary preserves multi-artifact replay and lineage semantics, its
implementation/review requires Sol High.

## 9. A7b3 Qt rendering gate

Add a dedicated Paper Account page only after adapter semantics are accepted.

`MainWindow` obtains `get_paper_account_state()` exactly once during
construction. Navigation away/back must not reacquire or reverify account state.

For `UNAVAILABLE`, render bounded status/message only.

For `VERIFIED`, render:

- checkpoint kind and sequence;
- checkpoint/lineage/account-state/compact-state IDs;
- as-of;
- cash;
- realized P&L;
- checkpoint artifact digest/size;
- read-only ordered positions table with symbol, quantity, total cost basis, and
  average cost.

All service/model-derived strings must use `Qt.TextFormat.PlainText`.

No buttons or controls may imply:

```text
run
execute
resume
retry
recover
refresh
select latest
repair
publish
open production database
open credential manager
```

## 10. Regression compatibility gate

Expanding `GuiApplicationService` requires the entire `tests/gui` suite before
visual/final certification. Any stale fake service that fails solely because it
lacks `get_paper_account_state()` should be updated to return deterministic
unavailable state. Do not add a production fallback to `MainWindow`.

## 11. Focused development sequence

Recommended sequence:

1. A7a pure model/service tests;
2. A7b1 GENESIS adapter tests;
3. A7b2 successor-edge adapter tests;
4. A7b3 offscreen Qt tests;
5. complete `tests/gui` integration suite;
6. Ruff check/format on touched GUI/tests;
7. `git diff --check`.

Run the complete repository suite only once after the final visual gate and final
accepted source tree.

## 12. Visual gate

Inspect at least:

- deterministic unavailable Paper Account page;
- verified GENESIS state with multiple positions;
- verified successor state with multiple positions.

Verify:

- long UUIDs/digests are readable/selectable;
- exact Decimal values are formatted consistently and truthfully;
- the positions table remains usable within supported bounds;
- kind/sequence/as-of/status make it clear that the page shows an
  offline-verified checkpoint state rather than an operational current account;
- no action/effect controls appear;
- navigation does not visibly reacquire state;
- existing pages have no layout regressions.

## 13. Final certification

After visual PASS and the final accepted source tree:

1. run complete repository pytest once;
2. run Ruff check on `src tests`;
3. run Ruff format check on `src tests`;
4. run `git diff --check`;
5. inspect `git status --short` and preserve unrelated generated/untracked
   artifacts;
6. perform exact GitHub diff review from the accepted GUI-A6 checkpoint.

## 14. Acceptance statement

GUI-A7 is accepted only if final evidence can state:

```text
COMMON_VERIFIED_ACCOUNT_CONTRACT=True
GENESIS_OFFLINE_VERIFIER_REUSED=True
SUCCESSOR_EDGE_VERIFIER_REUSED=True
SUCCESSOR_ALONE_TREATED_AS_SUFFICIENT=False
DIRECTORY_DISCOVERY=False
LATEST_ACCOUNT_SELECTION=False
LINEAGE_TRAVERSAL=False
PAPER_EXECUTION=False
PRODUCTION_SQLITE_ACCESS=False
C3_AUTHORITY_ACCESS=False
CREDENTIAL_MANAGER_ACCESS=False
NETWORK_ACCESS=False
GUI_INTEGRATION=PASSED
VISUAL_GATE=PASSED
FULL_REGRESSION=PASSED
```

A7 acceptance means the GUI can truthfully present one explicitly supplied,
completely offline-verified paper-account checkpoint state. It does not mean the
GUI knows which checkpoint is operationally current.

## 15. Final GUI-A7 acceptance and results

The frozen validation contract above is fully satisfied. GUI-A7 is fully ACCEPTED at final head `7fb2e0b014938215e9ab4fbdb1cddde2651fad92`.

### Accepted checkpoint sequence

- `7b9067d204954ceef16531cff669dee43d1c094b` - Architecture 93;
- `17deebb5a47995629925d0890eda49b41a6ab6f7` - GUI-A7 validation plan;
- `6a333ff16f289990bbb870d857496cec17c0e847` - A7a final common presentation contract;
- `2bcb2d8770cbd80b801d54cb71e3013b14da4f79` - A7b1 GENESIS inspection adapter;
- `8bb1ebab1d28d337460c41549dfaa2d757317f0a2` - A7b2 successor-edge inspection adapter;
- `b108a039251fbd37baeb0b6931e1fdd4b1c8877c` - A7b3 Qt Paper Account page;
- `91dad3cbe98c9d02097adba7a0cd8ab2d4736e9a` - A7b3 visual-table refinement;
- `7fb2e0b014938215e9ab4fbdb1cddde2651fad92` - final Ruff-format-only follow-up and accepted head.

### Accepted behavior

- one common Qt-free paper-account presentation contract supports completely verified GENESIS and CYCLE_SUCCESSOR states;
- the GENESIS adapter reads one explicit checkpoint artifact within its existing schema bound and calls `verify_genesis_paper_account_checkpoint(...)` exactly once per acquisition;
- the successor adapter requires the exact explicit prior checkpoint, verified snapshot, checkpointed-cycle report, and successor checkpoint proof set and calls `verify_checkpointed_paper_cycle_successor_edge(...)` exactly once;
- a successor checkpoint alone is never sufficient;
- only complete diagnostic-free exact PASS results become VERIFIED, and all failures collapse to deterministic sanitized UNAVAILABLE;
- the mapped fields are checkpoint kind/sequence, checkpoint/lineage/account/compact IDs, as-of, cash, cumulative realized P&L, ordered positions, and verifier artifact SHA/byte length;
- positions preserve verified order and exact Decimal values;
- Qt receives one immutable `PaperAccountPageState`; `MainWindow` acquires paper-account state exactly once during construction, and navigation does not reacquire or reverify;
- Paper Account is a dedicated read-only navigation page; presentation states explicitly say Verified Offline and do not claim operational/current-account selection;
- the positions table is read-only, non-sortable, four-column, uses a hidden vertical row header, and has balanced deterministic column sizing;
- no execution, resume, retry, recover, refresh, latest-selection, repair, publication, credential, network, brokerage, production SQLite, C1/C2/C3, or artifact-mutation controls or dependencies were added.

### Final certification evidence

- combined A7a/A7b1/A7b2 focused gate: 73 passed;
- A7b3 focused Qt/regression gate: 36 passed;
- complete GUI suite before final visual polish: 199 passed;
- post-polish focused Paper Account Qt gate: 12 passed;
- manual visual gate: PASSED for verified GENESIS presentation at normal and minimum-size layouts after table refinement;
- complete repository regression on the final semantic source tree: 2,928 passed, 13 skipped, 0 failed;
- all full-suite skips were expected repository Windows opt-in/symlink environment skips;
- Ruff check on `src/tests` after final formatting: passed;
- Ruff format check on `src/tests`: 356 files already formatted;
- `git diff --check`: clean;
- the final formatting-only commit changed exactly one long raise statement into Ruff multiline form;
- AST comparison of pre/post-format `paper_account_models.py`: `AST_EQUIVALENT=True`;
- focused A7 contract after formatting with explicit basetemp: 15 passed;
- an earlier focused rerun encountered WinError 5 only while pytest attempted to scan `C:\Users\John\AppData\Local\Temp\pytest-of-John`; this was an environment setup failure, not a source/test regression;
- known unrelated generated/untracked artifacts and historical permission-warning directories remained untouched.

No GUI-A8 architecture is selected by this documentation closeout; any subsequent GUI milestone requires a separate architecture/planning decision.
