# Architecture 127 — D10 Durable Wake Evidence and Stop Latch

Status: frozen source/design checkpoint. This document authorizes no production
filesystem, scheduler, provider, Paper-v2, broker, or live effect.

## Incident and scope

The first D10 activation was halted before its first natural wake after source
review found that the sealed second-stage launcher emitted
`personal-desktop-d10-wake-evidence/v1` only to inherited stdout. The
Architecture-124 guard and Task Scheduler contract supplied no durable sink, so
D10-C could not retain the exact bounded evidence required by Architecture 122.

The same review exposed a related operational requirement already implied by
Architecture 122: a D10 STOPPED wake must durably prevent a later scheduled wake
from resuming the soak automatically.

Architecture 127 closes both gaps without making scheduler history, exit codes,
or the evidence log trading authority.

## Fixed evidence namespace

The deployment owns one fixed evidence directory:

```text
F:\AITradingBot\D10\evidence
```

For one accepted activation lease with deterministic `soak_id`, the exact
current evidence file is:

```text
F:\AITradingBot\D10\evidence\wake-<soak_id>.jsonl
```

The filename is derived only from the already verified lease; no CLI,
environment, scheduler, caller, directory enumeration, newest-file selection,
or ambient path may choose it.

Historical evidence files may remain in the directory. They are operator audit
artifacts only and never enter trading identity or retry authority.

## Security contract

The evidence directory and current-soak file are provisioned by a separately
authorized Administrator deployment step before activation.

The evidence directory is:

- local NTFS, regular non-reparse directory, one fixed path;
- owner Administrators;
- protected DACL;
- Administrators and SYSTEM full access;
- Trading read/traverse only;
- no Trading create/delete/rename/WRITE_DAC/WRITE_OWNER authority.

The current-soak evidence file is:

- local NTFS, regular non-reparse single-link file;
- owner Administrators;
- protected DACL;
- Administrators and SYSTEM full access;
- Trading may read and append only, plus the minimum metadata/control reads
  needed for native verification and synchronization;
- Trading has no FILE_WRITE_DATA, DELETE, WRITE_DAC, WRITE_OWNER, or rename
  authority.

The file is pre-created empty by the protected deployment step. The Trading
principal may never create, truncate, replace, rename, delete, or choose another
evidence file.

## Guard-owned durability boundary

The sealed Architecture-124 guard remains the only process that launches the
second-stage D10 controller. It now additionally:

1. verifies the exact evidence directory and current-soak evidence file from
   native handles after verifying the signed deployment and activation lease;
2. reads and validates the complete bounded evidence log before source launch;
3. refuses source launch if the log is malformed, oversized, identity/security
   drifted, has a partial record, belongs to another soak/deployment, or its
   final durable record is terminal STOP evidence;
4. launches exactly one second-stage child with stdout captured by the guard;
5. requires stdout to contain exactly one bounded canonical D10 wake-evidence
   record when the child reaches the ordinary wake boundary;
6. appends that exact canonical record plus one LF to the pre-verified fixed
   append-only file using one native append operation;
7. flushes and independently rereads/verifies the appended suffix and native
   file identity before returning the child's outcome.

The evidence append is never authority for provider, decision, settlement,
receipt recovery, broker, or live effects. It is an audit/stop-control boundary.

## Durable stop latch

The evidence log is also the D10 stop latch.

A prior canonical wake record with `outcome == "STOPPED"` prevents the guard
from launching the second-stage controller on all later scheduler wakes for that
soak. A guard/child failure that prevents production of a valid wake record must
also durably append a bounded guard-failure record before returning whenever
native evidence append remains safely available.

A guard-failure record is operator evidence only. Its presence is terminal for
the current soak and prevents later source launch.

No source path may clear, rewrite, truncate, replace, or ignore terminal
evidence. Resuming after terminal evidence requires a new reviewed deployment
and a new activation lease/soak identity; the existing seven-day lease is never
renewed or repaired in place.

## Evidence-log grammar and bounds

Ordinary wake lines remain the exact canonical
`personal-desktop-d10-wake-evidence/v1` JSON bytes already produced by the
second-stage launcher.

Guard-only terminal lines use a separate bounded sanitized schema and contain
no credentials, raw authority objects, reusable capability, native handle,
arbitrary exception text, caller path, or environment data.

The log contract is:

- UTF-8/ASCII-safe canonical JSON, one record per line;
- LF terminator required for every committed record;
- no blank lines;
- maximum 512 records;
- maximum ordinary record size remains 16,384 bytes;
- fixed aggregate byte bound derived from the per-record and record-count
  limits;
- ordinary records must bind the exact current deployment ID, attestation,
  source HEAD/TREE, soak ID, activation/end interval, Trading SID, scheduler
  schema/task, and production Python identity already verified by the guard;
- ordinary record observation times must be nondecreasing;
- every ordinary record must prove all eight effect gates closed at final exit.

Malformed or partial evidence is terminal fail-closed state; it is never skipped
or repaired automatically.

## Ordering relative to effects

Before any second-stage effect can occur, the guard must prove enough remaining
evidence-file capacity for one maximum bounded record and must prove the prior
log is nonterminal.

The second stage preserves Architecture-122 ordering and still restores all
effect gates closed before it constructs ordinary wake evidence.

The guard appends evidence only after the second stage returns its canonical
record. Failure to durably append after a wake may make the operational result
indeterminate, so the guard must not treat process exit status as success or
allow automatic continuation based on it.

## Scheduler contract

Task Scheduler remains a zero-semantic-argument wake source. No redirection,
shell wrapper, evidence path, soak ID, or log argument is added to the task.

The exact scheduler action remains the sealed launch guard. The evidence sink is
source-owned and lease-derived behind that guard.

## Deployment consequence

Architecture 127 changes governed executable source and the pre-source guard.
Therefore the halted S5-R10 deployment cannot simply be re-enabled.

A later clean D10 retry requires:

- fresh exact-tree source certification;
- fresh executable manifest and signed deployment attestation;
- protected deployment replacement of the sealed source/guard;
- protected provisioning and verification of the evidence directory/current
  evidence file;
- a new non-renewed activation lease and new soak ID;
- exact scheduler mutation/readback for the new activation;
- first natural wake observation.

The halted activation lease is retained as incident evidence until a separately
reviewed replacement/retirement checkpoint handles it.

## Non-authority

Neither evidence contents nor scheduler history may:

- authorize retry;
- synthesize a missed decision;
- select a trading session;
- authorize receipt recovery;
- permit provider or Paper-v2 effects;
- extend the lease;
- graduate to broker-paper or live.

## Acceptance

Source certification must prove:

- fixed lease-derived evidence path only;
- exact append-only ACL and native-object contract;
- no create/truncate/replace/delete/rename authority under Trading;
- malformed/partial/oversized/foreign log blocks before child launch;
- terminal wake/guard record blocks all later source launch;
- exact ordinary child stdout is durably appended and reread;
- child output ambiguity cannot be retried automatically;
- capacity is proven before child launch;
- scheduler action remains unchanged and zero-semantic-argument;
- existing Architecture-122 effect budgets/order/gate closure remain unchanged;
- broker/live calls remain impossible.


## E4 correction — durable pre-launch wake-start marker

Adversarial E4 review found one remaining continuation ambiguity in the initial
E2/E3 implementation: if the second-stage child returned after crossing a
permitted D10 effect but the guard then could not durably append the ordinary
wake record or a guard-terminal record, the evidence log could remain
nonterminal and a later scheduler wake could launch source again.

The frozen correction is a durable **pre-launch wake-start marker**.

Before launching the second-stage child, the guard must append, flush, reread,
and verify one bounded canonical wake-start record to the same fixed
current-soak evidence file. The wake-start record is bound to the exact
deployment and soak and contains only a guard timestamp plus those identities.

Evidence-log state is now paired:

```text
WAKE_START -> ordinary COMPLETED/NO_ACTION   = completed nonterminal wake
WAKE_START -> ordinary STOPPED               = terminal soak
WAKE_START -> guard-terminal failure         = terminal soak
WAKE_START as final record                    = terminal/incomplete soak
```

A wake-start record may never appear while another start is unresolved.
An ordinary or guard-terminal result may never appear without one immediately
preceding unresolved wake-start. Once a terminal result is present, no later
record is valid.

The guard must reserve capacity for both the start record and the maximum
possible result record **before** appending the start marker. Only after the
start marker is durably verified may source launch occur.

This ordering means:

- failure to append the start marker causes no source launch and may safely be
  retried by a later scheduler wake;
- after the start marker is durable, any child launch/output/result-append
  failure leaves either a durable explicit terminal record or the unresolved
  start marker itself;
- an unresolved final start marker blocks all later source launch;
- no scheduler mutation or in-process retry is needed to preserve stop
  semantics.

The start marker is audit/stop-control evidence only. It grants no provider,
settlement, publication, receipt-recovery, broker, live, retry, or lease
authority.

E4 acceptance must specifically prove that post-child append failure leaves the
durable start marker as a terminal latch and that a subsequent guard invocation
cannot launch the child.

## E6 pre-certification correction — nonterminal result acceptance

The exact pre-E6 source/security review found a remaining crash/durability
ambiguity in the E4 pair grammar.

The native append sequence necessarily performs `WriteFile` before the later
`FlushFileBuffers`, native reinspection, reread, and parser verification.
Therefore a nonterminal ordinary result can be fully written to the evidence
file and then encounter a later flush/reread/reinspection failure. The current
two-record grammar would leave durable bytes shaped like:

```text
WAKE_START -> ordinary nonterminal result
```

A later guard invocation can parse those complete bytes as a successful
nonterminal wake even though the guard that produced them never completed the
post-write durability proof. That permits automatic source relaunch after an
indeterminate result-persistence boundary and does not satisfy E4.

The frozen correction adds a third, guard-owned **result-acceptance marker** for
nonterminal ordinary wakes.

The marker uses a separate bounded canonical schema:

```text
personal-desktop-d10-guard-accept/v1
```

It contains only:

- the schema;
- a trusted guard acceptance timestamp;
- deployment ID;
- soak ID;
- SHA-256 of the exact preceding canonical ordinary result bytes.

The guard may attempt this marker **only after** the ordinary nonterminal result
append has completed its flush, native identity/security reinspection, exact
reread, and full evidence-log validation successfully.

The durable grammar becomes:

```text
WAKE_START -> ordinary nonterminal -> ACCEPT = completed nonterminal wake
WAKE_START -> ordinary nonterminal          = terminal/unaccepted wake
WAKE_START -> ordinary STOPPED              = terminal soak
WAKE_START -> guard-terminal failure        = terminal soak
WAKE_START as final record                  = terminal/incomplete soak
```

An acceptance marker:

- may appear only immediately after one nonterminal ordinary result;
- must bind the SHA-256 of that exact preceding result;
- may never follow STOPPED or guard-terminal evidence;
- may never be duplicated or appear without the matching start/result pair;
- is audit/stop-control evidence only and grants no provider, settlement,
  publication, receipt-recovery, broker, live, retry, or lease authority.

Before any later source launch, the guard must independently stabilize the
already-existing evidence log through the pinned current-soak file handle:
flush the existing file, recheck native identity/security, reread the exact
bytes, and validate the complete grammar. This is required before trusting an
existing ACCEPT marker. A fully present ACCEPT marker whose own earlier
post-write verification was interrupted may therefore be trusted only after
this new pre-source stabilization succeeds.

A nonterminal ordinary result without ACCEPT remains terminal for that soak.
The guard must not synthesize or append ACCEPT on a later scheduler wake and
must not launch source. Recovery requires a new reviewed deployment/soak just as
for other terminal evidence. Partial or malformed ACCEPT evidence is likewise
terminal and is never repaired.

Capacity must be proven before source launch for all three possible nonterminal
records: one maximum wake-start marker, one maximum ordinary result, and one
maximum result-acceptance marker. STOPPED and guard-terminal paths remain
two-record terminal paths but use the same conservative pre-launch reservation.

The read-only observer must report a nonterminal wake only for an accepted
three-record sequence. A complete nonterminal result lacking ACCEPT must report
a distinct terminal/unaccepted state.

This correction changes source/design only. It authorizes no production
filesystem, scheduler, source launch, provider, Paper-v2, broker, or live
effect. E6 certification remains blocked until this correction is implemented,
focused-tested, and exact-diff reviewed.

## E6 pre-certification native durability correction — append-only write-through

The final E6-pre native review found that the earlier durability mechanism used
`FlushFileBuffers` on the Trading evidence handle even though that handle is
deliberately opened with only read + `FILE_APPEND_DATA`. The Win32
`FlushFileBuffers` contract requires a handle with `GENERIC_WRITE`, while
granting `GENERIC_WRITE` would map to broader write rights including
`FILE_WRITE_DATA` and would violate the append-only evidence policy.

Architecture 127 therefore forbids `FlushFileBuffers` on the Trading evidence
handle.

The frozen replacement is:

- keep the evidence ACL unchanged: Trading receives read + `FILE_APPEND_DATA`
  only, never `FILE_WRITE_DATA`, delete, rename, `WRITE_DAC`, or
  `WRITE_OWNER`;
- open the existing evidence file with the same exact desired-access mask,
  `OPEN_EXISTING`, and `FILE_FLAG_OPEN_REPARSE_POINT`, plus
  `FILE_FLAG_WRITE_THROUGH`;
- every guard-owned append uses that synchronous write-through handle;
- after `WriteFile` returns successfully, continue to verify exact byte count,
  native object identity/security, resulting length, exact reread bytes, and the
  complete evidence grammar;
- do not call `FlushFileBuffers` before, during, or after evidence append;
- do not add a broader write-capable second handle merely to flush.

For NTFS on the fixed local volume, `FILE_FLAG_WRITE_THROUGH` is the durability
primitive for Architecture 127. A successfully completed write-through
`WriteFile` is the persistence boundary before the later reread/grammar proof.

The E6-pre result-acceptance state machine remains unchanged:

```text
WAKE_START -> ordinary nonterminal -> ACCEPT = completed nonterminal wake
WAKE_START -> ordinary nonterminal          = terminal/unaccepted wake
WAKE_START -> ordinary STOPPED              = terminal soak
WAKE_START -> guard-terminal failure        = terminal soak
WAKE_START as final record                  = terminal/incomplete soak
```

Because ACCEPT itself is appended through the write-through handle, a later
scheduler wake does not attempt an illegal flush of the existing file. Instead
it opens the fixed current-soak object, verifies its exact native identity and
security, reads the bounded bytes, validates the complete grammar and hash
binding, reinspects the pinned root/file objects, and only then may a
nonterminal accepted sequence permit another source launch.

A crash or exception before a complete valid ACCEPT remains terminal:
- start only -> terminal/incomplete;
- complete nonterminal result without ACCEPT -> terminal/unaccepted;
- partial/malformed ACCEPT -> parse failure / no source launch.

If a complete ACCEPT is present after an interrupted producer process, the
write-through contract plus the marker's exact canonical/hash binding and the
next wake's pinned-handle read/reinspection are the recovery proof. No repair,
retroactive ACCEPT append, or source retry is allowed for incomplete evidence.

E6 remains blocked until this native write-through correction is implemented,
focused-tested, exact-diff reviewed, and—because it depends on Win32 caching
semantics—validated with a disposable non-production host probe before the
canonical three-lane certification.

## Architecture 127 E6 canonical certification — ACCEPTED

Architecture 127 source certification is accepted at the exact final reviewed
repository identity:

```text
HEAD: 0f9551e13486ef65b35a5a9633da19081571144b
TREE: 1186e92669af100542c055368c1b72495c36bc11
origin/develop at admission:
0024ad86767c76116094688d13ecff6ebf0aa438

broad-1:
  modules: 138
  cases: 4260
  passed: 4257
  skipped: 3
  failed: 0
  errors: 0

broad-2:
  modules: 137
  cases: 3983
  passed: 3978
  skipped: 5
  failed: 0
  errors: 0

serial:
  modules: 5
  cases: 935
  passed: 926
  skipped: 9
  failed: 0
  errors: 0

totals:
  cases: 9178
  passed: 9161
  skipped: 17
  failed: 0
  errors: 0

certification status: passed
certification exit: 0
wall seconds: 396.97
evidence:
F:\AI\temp\pytest\arch127-e6-certification-20260929-010726
```

The canonical certification runner also completed its exact source-identity
checks before/after testing and its repository-wide Ruff check, Ruff
`format --check`, and `git diff --check` gates. Final HEAD/tree remained
unchanged and the worktree remained clean.

Architecture 127 is therefore source-certified. This certification does not
authorize production deployment replacement, evidence provisioning, activation
lease creation, Task Scheduler mutation/enabling/manual start, provider calls,
Paper-v2 mutation, broker-paper, or live trading.

The halted first D10 soak remains historical incident evidence and must never be
resumed. Any new D10 attempt requires a new signed deployment for the certified
Architecture-127 executable bytes, a new activation lease and soak ID, a new
empty lease-derived evidence file, and a separately reviewed scheduler
reactivation path.

