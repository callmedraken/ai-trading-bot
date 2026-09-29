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
- parse complete existing log and enforce same soak/deployment identity;
- terminal prior record prevents child launch;
- prove capacity for one maximum record;
- capture exactly one child stdout record;
- append + flush + reread/reverify;
- no shell redirection and no scheduler-contract change.

E4 — terminal failure behavior
- if ordinary child emits a canonical STOPPED record, persist it and block all
  later wakes;
- if child fails before producing valid ordinary evidence and safe append remains
  available, persist one bounded guard-terminal record;
- malformed/partial/oversized/foreign existing log blocks before source launch;
- no automatic cleanup, truncation, retry, restart, or extension.

E5 — read-only operator observation
- add a source-owned read-only verifier that can identify the exact current
  lease-derived evidence file and return sanitized first/last/count/terminal
  evidence;
- no latest-file discovery;
- no trading authority from evidence.

E6 — focused verification and certification
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
13. append short-write/flush/reread/native drift fails closed without retry;
14. source never opens evidence by caller-provided path;
15. scheduler action/arguments remain exact Architecture-124 D10 guard;
16. all existing D10 effect-budget, reconciliation, gate-finally, no-receipt-
    recovery, and no-broker/live tests remain green.
