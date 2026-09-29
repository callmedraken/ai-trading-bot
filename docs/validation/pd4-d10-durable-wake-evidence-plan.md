# PD4 D10 Durable Wake Evidence Validation Plan

Status: source-only validation plan for Architecture 127. No protected host
mutation is authorized by this document.

## D10-C incident predecessor

Accepted predecessor state:

```text
first D10 activation/recovery: ARMED_VERIFIED
first natural D10 wake: never accepted
D10 task: disabled before first natural wake
halt post-task XML SHA-256:
8d592a71258529fa88cd85866b0be1e91cf407d91e9acf5891a1bd82c0bf09b0
halted activation lease SHA-256:
91106d61129dc9c11e017a7ea613ba0fd82c87fd9debfc346b265c03c49a1e84
provider/Paper-v2/broker/live during halt: NOT_RUN
```

Do not re-enable or manually start that task.

## Source checkpoints

E1 — evidence model/path
- add fixed D10 evidence-root constants;
- derive current evidence filename only from a verified activation lease soak ID;
- freeze ordinary/guard record byte and aggregate limits;
- add pure canonical validation for persisted ordinary wake records and bounded
  guard-terminal records.

E2 — native append-only evidence capability
- Windows fixed-path read/append surface only;
- native local-NTFS/non-reparse/single-link verification;
- Administrators ownership/protected DACL;
- Trading read + FILE_APPEND_DATA only beyond required metadata/control access;
- reject FILE_WRITE_DATA, delete, rename, WRITE_DAC, WRITE_OWNER capability;
- no caller path or environment selection.

E3 — sealed guard integration
- verify evidence sink before child launch;
- parse the complete existing paired log and enforce the same
  soak/deployment identity;
- terminal prior state prevents child launch;
- prove bounded capacity for both one wake-start marker and one maximum result
  record before source launch;
- durably append + flush + reread/reverify the guard-owned wake-start marker
  before source launch;
- capture exactly one child stdout record;
- append + flush + reread/reverify the ordinary or guard-terminal result;
- no shell redirection and no scheduler-contract change.

E4 — terminal failure behavior
- an unresolved final wake-start marker is terminal/incomplete and blocks every
  later source launch for that soak;
- if ordinary child emits a canonical STOPPED record, persist it after its
  wake-start marker and block all later wakes;
- if child fails before producing valid ordinary evidence and safe append remains
  available, persist one bounded guard-terminal record after its wake-start
  marker;
- if result append/flush/reread/native verification fails after source launch,
  the already-durable unresolved wake-start marker remains the stop latch;
- malformed/partial/oversized/foreign/unpaired existing log blocks before
  source launch;
- no automatic cleanup, truncation, retry, restart, or extension.

E5 — read-only operator observation
- add a source-owned read-only verifier that can identify the exact current
  lease-derived evidence file and return sanitized first/last/count/terminal
  evidence;
- no latest-file discovery;
- no trading authority from evidence.

E6-pre — nonterminal result-acceptance correction
- add a bounded guard-owned result-acceptance marker for ordinary nonterminal
  wakes;
- append it only after the preceding ordinary result has completed flush,
  native reinspection, exact reread, and grammar validation;
- bind it to deployment ID, soak ID, and SHA-256 of the exact preceding result;
- treat a complete nonterminal ordinary result without acceptance as
  terminal/unaccepted on every later wake;
- before trusting any existing accepted sequence for a new source launch, flush
  the existing fixed evidence handle and independently recheck identity,
  reread, and grammar;
- reserve capacity before source launch for start + maximum ordinary result +
  maximum acceptance marker;
- update the read-only observer so only an accepted three-record nonterminal
  sequence is reported nonterminal.

E6 — focused verification and certification
- only after E6-pre implementation passes focused review;
- focused evidence/guard/launcher/deployment tests;
- Ruff and formatting;
- PowerShell AST checks for any deployment helper changes;
- exact GitHub diff review;
- canonical three-lane repository certification once at the final reviewed tree.

## Protected work intentionally deferred

After E6 source certification, protected deployment design/review is separate.
It must provision the fixed append-only evidence object, replace the sealed
deployment, issue a new activation lease/soak ID, update/read back Task
Scheduler, and leave all broker/live authority closed.

No current authorization covers those future effects.

## Required regression cases

At minimum:

1. empty preprovisioned current-soak evidence file admits launch;
2. completed/no-action records admit the next wake;
3. STOPPED ordinary record blocks source launch;
4. guard-terminal record blocks source launch;
5. missing evidence file blocks;
6. wrong owner/DACL/reparse/link/volume/path blocks;
7. Trading FILE_WRITE_DATA or delete/WRITE_DAC/WRITE_OWNER access blocks;
8. wrong soak/deployment/source/scheduler/runtime identity blocks;
9. noncanonical JSON, blank line, missing LF, partial tail, oversize record,
   record overflow, or aggregate overflow blocks;
10. nonmonotonic observation times block;
11. child zero exit with missing/extra/malformed stdout blocks and records
    terminal guard evidence when safe;
12. child nonzero with canonical STOPPED evidence persists the exact ordinary
    record and remains terminal;
13. append short-write/flush/reread/native drift fails closed; if a nonterminal
    ordinary result was fully written before the later failure, the missing
    acceptance marker still blocks every later source launch;
14. a durably appended wake-start marker with no result is terminal/incomplete
    and prevents a later child launch;
15. result append failure after child return leaves either the prior wake-start
    marker or a complete-but-unaccepted ordinary result as the durable stop
    latch and does not retry the child;
16. source never opens evidence by caller-provided path;
17. scheduler action/arguments remain exact Architecture-124 D10 guard;
18. all existing D10 effect-budget, reconciliation, gate-finally, no-receipt-
    recovery, and no-broker/live tests remain green;
19. a nonterminal ordinary result is not launch-admissible until an immediately
    following acceptance marker binds its exact SHA-256;
20. the acceptance marker is never attempted before successful result
    flush/reinspection/reread/grammar verification;
21. a simulated full result write followed by flush/reread/native-verification
    failure leaves no acceptance marker and the next guard invocation cannot
    launch the child;
22. an existing accepted three-record sequence is launch-admissible only after
    the new invocation flushes, reinspects, rereads, and revalidates the fixed
    evidence object; partial/malformed/foreign acceptance evidence blocks.

### E6-pre native write-through correction

Before E6 certification:

- remove every Architecture-127 `FlushFileBuffers` call from the append-only
  evidence path;
- open the evidence writer with
  `FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_WRITE_THROUGH`;
- retain the exact Trading desired-access mask of read + `FILE_APPEND_DATA`;
- verify tests freeze both the desired-access mask and write-through flag;
- verify source/tests prove no broader writer handle or `FlushFileBuffers`
  dependency is introduced;
- preserve post-write exact-length/native-identity/reread/grammar verification;
- preserve the result-acceptance state machine and unaccepted stop latch;
- on later wakes, validate existing accepted evidence by pinned-handle
  read/reinspection/grammar only, with no flush attempt;
- run a disposable non-production Windows host probe that opens an NTFS test
  file with the exact append-only desired-access pattern + WRITE_THROUGH,
  appends a bounded record, closes/reopens read-only, and verifies exact bytes.
  The probe must not touch `F:\AITradingBot`, Task Scheduler, credentials,
  provider, Paper-v2, broker, or live state.

Canonical three-lane E6 certification is allowed only after that probe and the
final exact source/security review pass.

