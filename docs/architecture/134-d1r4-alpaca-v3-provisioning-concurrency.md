# Architecture 134-D1R4 — `/v3` provisioning concurrency and reconciliation contract

## 2026-10-13 — Architecture 134-D1R4R SOURCE ACCEPTED

Architecture 134-D1R4R — incident-specific pre-provider `/v3` exact-pair
staging cleanup recovery and fresh-input anti-truncation hardening — is
**SOURCE ACCEPTED** on
`feature/robinhood-production-paper-alpaca-auth-qualification`.

Accepted executable/test source:

```text
HEAD             a847ce6d9ab65e7cfc7983cd19c3378abb5c8851
TREE             9c3de40cc6c4e42f5a9fe62389d7558ce2d38ba0
CI               #529 / 38493263422 / attempt 1 / SUCCESS
CERT ARTIFACT    11863061550
ARTIFACT SHA256  7f0bf5dd5e26a712b55e3186b9ed4fbee7f3daf9c3c9469075bdb138610fe97a
ROBINHOOD        97 modules
CASES            9,066
PASSED           9,065
SKIPPED          1
FAILED/ERRORS    0 / 0
WALL             276.064 s
```

The accepted recovery is intentionally bound to the single consumed D1R4
generation: source HEAD `41351ade6a2434adc26b9389106339e034b53a06`,
TREE `6a6e6528c7e0bfb43835f70c620276f960f723ee`, exactly 4865 bytes,
SHA-256
`217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193`,
at the original fixed external journal path. Both preserved witnesses have
UTF-8 length one, so that generation remains rejected for authentication.

D1R4R owns one fixed incident-wide cleanup latch:
`F:\AI\temp\qualification\arch134-d1r4r-cleanup-217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193.json`.
There is no caller-selected latch/evidence destination, credential role, target,
policy, digest, witness or generation. Existing/partial/blocked/ambiguous latch
state permanently prevents another destructive attempt unless a later separately
reviewed source checkpoint explicitly establishes otherwise.

Under the existing fixed Global D1R4 mutex, cleanup makes zero credential writes
and permits deletion only after both exact current `/v3` records reproduce the
frozen witnesses and strict metadata. Each delete has a distinct durable
flush/fsync intent, at most one native call, immediate absence proof and durable
confirmation. The remaining secret is re-proven before its delete and final
success requires independent pair absence. Any uncertainty after native delete
entry is `DELETE_OUTCOME_AMBIGUOUS`; no later delete, restoration, repair or
automatic retry is permitted. Busy or abandoned ownership performs zero
credential effects.

Fresh interactive provisioning now has a local anti-truncation/placeholder floor
of eight UTF-8 bytes, requires exact repeated hidden entry, displays only
nonsecret lengths and requires the fixed human length confirmation before
credential state inspection/mutation. This is not a claimed Alpaca credential
format or remote-authentication proof. The shared/recovery reader deliberately
continues to read the historical one-byte incident pair for exact recovery.

All predecessor Architecture-134 source-pin dictionaries, including the accepted
D1R4 overlay, remain frozen; D1R4R is a separate successor overlay. Current
inventory is FULL 173 / ROBINHOOD 97 / LEGACY 215 / EXHAUSTIVE 388 with the
required baseline tuples unchanged. The existing mapped checkpoint remains
ROBINHOOD-owned and source-only: it exposes no registered preflight or protected
execute hook.

Checkpoint Source Gates #529 is terminal SUCCESS on the exact accepted source:
source-static, active-tests, canonical ROBINHOOD certification and source-gates
all passed; full-tests was intentionally skipped. Static evidence records
`GIT_DIFF_CHECK=PASS`, `RUFF_CHECK=PASS`, `RUFF_FORMAT=PASS`,
`AUTHORITY=PASS` and stable source identity. Canonical certification completed
under the 300-second hygiene threshold.

Implementation, fake/temp tests and CI performed zero real Windows Credential
Manager reads/writes/deletes, zero Alpaca/provider requests, zero production
SQLite/session/strategy/Robinhood/PREPARE/EXECUTE/paper/broker/scheduler/ACL
effects and zero D1/D2 invocations. The real D1R4R cleanup has NOT executed.

**Next protected sequence:** synchronize the exact docs-only acceptance
descendant; run a separately guarded read-only/pre-effect readiness gate that
does not enter Credential Manager; then, only if that passes and the fixed latch
is still absent, invoke the reviewed D1R4R cleanup host exactly once. A successful
cleanup authorizes neither authentication nor D1/D2. Authentication remains
blocked until a new fresh `/v3` generation is separately provisioned, reviewed
and accepted. Real-money trading remains NO-GO.

## 1. Scope

This amendment resolves the Windows Credential Manager concurrency problem for Architecture 134-D1R4.

Windows `CredWriteW` does not provide create-only or compare-and-swap semantics. `CredDeleteW` deletes by target name and does not condition deletion on the credential contents still belonging to the caller.

D1R4 therefore does **not** claim atomicity from Credential Manager itself.

Instead, D1R4 defines:

1. a fixed machine-wide cooperating-writer exclusion boundary;
2. durable pre-effect evidence fences;
3. post-write exact readback confirmation;
4. conservative ambiguity classification;
5. separate read-only reconciliation;
6. separately reviewed conditional cleanup only when ownership can still be proven under the exclusion boundary.

No real credential or provider operation is authorized by this design.

---

## 2. Fixed credential generation

Current-product D1R4 uses exactly:

```text
credential policy:
windows-credential-manager-alpaca-market-data/v3

key target:
AITradingBot/MarketData/Alpaca/ApiKeyId/v3

secret target:
AITradingBot/MarketData/Alpaca/ApiSecretKey/v3
```

The existing `/v2` records are immutable historical credential-reference state.

The D1R4 provisioning, reconciliation and cleanup paths:

- never read `/v2`;
- never write `/v2`;
- never delete `/v2`;
- never use `/v2` as fallback;
- never compare `/v2` values with `/v3`;
- never alias either version.

Any future provider use of `/v3`, successful or otherwise, permanently closes `/v3` staging and cleanup authority. A subsequent credential rotation would require `/v4`.

---

## 3. Accepted exclusion boundary

D1R4 provisioning uses one fixed, non-caller-selectable, machine-wide Windows named mutex:

```text
Global\AITradingBot-Arch134-D1R4-AlpacaV3-Provision-v1
```

There is:

```text
NO Local\ fallback
NO alternate mutex name
NO caller-selected namespace
NO timeout takeover
NO lock stealing
NO lease expiration
NO heartbeat-based takeover
```

The object follows the repository's existing Architecture-77 machine-wide named-mutex discipline: unexpected object type, ownership, DACL/security state or namespace is fail-closed.

The mutex is **not** a credential, authority token or durable indication that provisioning succeeded.

It provides exclusion only among authorized D1R4 provisioning/reconciliation/cleanup implementations that obey this contract.

Manual Credential Manager editing or another unreviewed writer while a D1R4 operation is active is prohibited. Such out-of-band mutation is not made safe by the mutex and is treated as external state interference if detected.

---

## 4. Exact exclusion interval

Source admission and fresh evidence-file reservation occur before acquiring the mutex because they perform no credential effect.

The mutex is then acquired **before any `/v3` Credential Manager read or mutation** and remains continuously owned through:

```text
interactive local witness input
-> initial /v3 absence/state observation
-> every CredWriteW intent fence
-> every CredWriteW invocation
-> every post-write readback
-> final pair readback
-> any non-ambiguous same-invocation cleanup permitted below
-> final credential-state classification
-> final evidence publication
```

Only after the final classification/evidence publication is complete is the mutex released.

No credential mutation may occur outside that interval.

No operation may release and reacquire the mutex and claim continuity of ownership.

---

## 5. Mutex acquisition outcomes

### Normal acquisition

The operator may proceed to credential-state inspection.

### Mutex currently owned

Return a sanitized blocked result such as:

```text
BLOCKED / CONCURRENT_PROVISIONER
```

Credential reads:

```text
0
```

Credential writes:

```text
0
```

Credential deletes:

```text
0
```

No wait/retry loop is authorized.

### `WAIT_ABANDONED`

`WAIT_ABANDONED` means only that the previous owner process died while holding the provisioning exclusion boundary.

It does **not** reveal whether the prior owner:

- had not started a write;
- was inside `CredWriteW`;
- had completed one write;
- had completed both writes;
- was performing readback;
- was attempting cleanup;
- had successfully cleaned;
- had published final evidence.

The new process retains the mutex but may perform **read-only reconciliation only**.

It must not call `CredWriteW` or `CredDeleteW` in that invocation.

Result:

```text
RECONCILIATION_REQUIRED / ABANDONED_OWNER
```

No automatic retry follows.

---

## 6. Durable effect fencing

Provisioning uses an external canonical append/journal or equivalent durable evidence contract.

Before each credential mutation, the operator must durably flush/fsync an intent record.

Example conceptual ordering:

```text
PROVISIONING_RESERVED
LOCK_ACQUIRED
INITIAL_STATE_ACCEPTED

KEY_WRITE_INTENT
-> CredWriteW(key)
-> key readback
KEY_WRITE_CONFIRMED

SECRET_WRITE_INTENT
-> CredWriteW(secret)
-> secret readback
SECRET_WRITE_CONFIRMED

PAIR_CONFIRMED
```

Evidence contains no credential value.

The Architecture-84 witness remains:

```text
SHA256(
    UTF8("AITradingBot/C3CredentialWitness/v1\0")
    || role
    || UTF8("\0")
    || exact credential bytes
)
```

with role exactly:

```text
api_key_id
api_secret_key
```

The nonsecret expected witness and UTF-8 byte length may be retained as bounded evidence.

Raw values, command-line material, environment variables, exception strings, native buffers and credential representations are excluded.

Failure to durably publish a required pre-effect fence prevents the corresponding credential call.

---

## 7. Fresh provisioning admission

A fresh provisioning operation requires both exact `/v3` targets to be absent while the mutex is held.

Possible initial states:

```text
ABSENT / ABSENT
    -> eligible for fresh provisioning

PRESENT / ABSENT
ABSENT / PRESENT
PRESENT / PRESENT
UNKNOWN / any
    -> BLOCKED_EXISTING_V3_STATE
```

A normal provisioning invocation does not overwrite an existing `/v3` target even if the current value happens to match the supplied pair.

Existing state is handled through reconciliation, not `CredWriteW`.

This converts the intended create-only requirement into:

```text
exclusive state admission
+ no-existing-target requirement
+ one write
+ exact readback
```

rather than pretending `CredWriteW` itself is create-only.

---

## 8. Write-confirmation rule

A credential write is classified `WRITE_CONFIRMED` only when all of the following hold:

1. the mutex has remained continuously owned;
2. the durable write-intent fence was completed;
3. exactly one `CredWriteW` was invoked for that role;
4. the native call returned successful completion;
5. an immediate exact fixed-target `CredReadW` succeeded;
6. the readback has the expected credential type/persistence/UTF-8 invariants;
7. its domain-separated witness equals the expected witness;
8. its exact UTF-8 byte length equals the expected length.

Anything less is **not a confirmed write**.

In particular, these are ambiguous:

```text
process termination during/after CredWriteW
native exception after entering CredWriteW
native return state that cannot be classified
successful CredWriteW followed by absent readback
successful CredWriteW followed by mismatched readback
readback failure after CredWriteW
source/evidence failure after CredWriteW before confirmation
mutex continuity loss
```

Classification:

```text
WRITE_OUTCOME_AMBIGUOUS
```

The operation stops credential mutation immediately.

---

## 9. No cleanup after an ambiguous write

This is the central D1R4 concurrency rule.

Once any credential write becomes `WRITE_OUTCOME_AMBIGUOUS`:

```text
NO further CredWriteW
NO CredDeleteW
NO overwrite
NO repair
NO second provisioning attempt
NO automatic retry
```

This remains true even if another target had previously been confirmed as written by the same invocation.

Example:

```text
key write confirmed
secret write becomes ambiguous
```

Result:

```text
PARTIAL_OR_AMBIGUOUS_V3_STATE
RECONCILIATION_REQUIRED
```

The key is **not** automatically deleted.

This avoids using unconditional `CredDeleteW` when ownership of the overall pair operation is no longer provable.

---

## 10. Narrow same-invocation cleanup

Automatic cleanup is permitted only before any ambiguous write has occurred and only while uninterrupted mutex ownership continues.

The primary useful case is:

```text
key WRITE_CONFIRMED
then
failure occurs before SECRET_WRITE_INTENT / before any secret CredWriteW
```

The implementation may attempt to restore the original:

```text
ABSENT / ABSENT
```

state.

Before deleting the confirmed key it must:

1. durably publish `KEY_DELETE_INTENT`;
2. re-read the exact key target while retaining the mutex;
3. prove the current witness and byte length still equal the value this invocation confirmed;
4. invoke `CredDeleteW` exactly once;
5. re-read and prove the target is absent.

Only then is cleanup:

```text
CLEANUP_CONFIRMED
```

If the pre-delete readback differs, cleanup is prohibited.

If `CredDeleteW`, post-delete readback, evidence publication or process lifetime becomes uncertain:

```text
CLEANUP_OUTCOME_AMBIGUOUS
```

and all further credential mutation stops.

The delete is therefore conditional at the **reviewed protocol level under exclusive ownership**, not conditionally atomic inside the Windows API.

---

## 11. Out-of-band interference

The mutex establishes the closed cooperating-writer set for reviewed D1R4 tooling.

It cannot prevent an unrelated process or a human from modifying Credential Manager without acquiring the mutex.

Therefore, while a protected D1R4 operation is in progress:

```text
manual Credential Manager edits are prohibited
other credential tooling is prohibited
other D1R4 operator processes must use the same mutex
```

Detected unexpected value/state drift is:

```text
EXTERNAL_STATE_INTERFERENCE
RECONCILIATION_REQUIRED
```

It never authorizes overwrite or deletion.

The architecture does not claim protection against malicious privileged software that deliberately violates the exclusion contract.

---

## 12. Separate read-only reconciliation

Any of these require reconciliation:

```text
ABANDONED_OWNER
WRITE_OUTCOME_AMBIGUOUS
CLEANUP_OUTCOME_AMBIGUOUS
partial/truncated post-effect evidence
process crash after a write-intent fence
unexpected existing /v3 state after a prior attempted provision
```

Reconciliation is a distinct operator mode.

It:

- acquires the same global mutex;
- reads only the two fixed `/v3` targets;
- performs zero writes;
- performs zero deletes;
- performs zero provider/network requests;
- reads preserved nonsecret witness metadata from the ambiguous operation;
- computes local readback witnesses without exposing raw values.

It classifies the current state exactly.

### A. Both absent

```text
RECONCILED_ABSENT
```

The previous ambiguous attempt remains historical evidence.

A future fresh provisioning attempt may be separately reviewed/authorized because current `/v3` staging state is absent and no `/v3` provider effect has occurred.

This is not an automatic retry.

### B. Both present and both exactly match the expected generation

```text
RECONCILED_PAIR_MATCH
```

No rewrite occurs.

This state may satisfy local `LOCAL_EXACT_MATCH` after the required dashboard-current generation check is independently re-established.

A crash after successful provisioning therefore does not require destructive reprovisioning.

### C. Exactly one matching target present

```text
RECONCILED_PARTIAL_MATCH
```

No cleanup occurs in reconciliation mode.

A separately reviewed cleanup operation is required.

### D. Any present target does not match the preserved generation

```text
RECONCILED_UNKNOWN_OR_FOREIGN_STATE
```

No delete and no overwrite are authorized.

This requires human/operator investigation and possibly abandonment of that `/v3` generation after the state is safely resolved.

---

## 13. Separately reviewed cleanup after reconciliation

Post-crash cleanup is not part of read-only reconciliation.

A separate cleanup operation may be authorized only when reconciliation has already proven that one or more exact current targets match the preserved ambiguous-operation witness.

The cleanup operation:

1. acquires the same fixed mutex;
2. verifies the exact preserved reconciliation artifact;
3. re-reads every proposed cleanup target;
4. requires exact witness and byte-length equality with the generation being cleaned;
5. makes zero changes if any target differs;
6. durably publishes delete intent before each delete;
7. invokes `CredDeleteW` at most once per authorized role;
8. verifies absence immediately after each delete;
9. stops on the first ambiguous delete.

It must never delete an unknown or mismatched credential merely because the target name is `/v3`.

This is the only accepted substitute for native compare-and-delete semantics.

---

## 14. Pair acceptance

Fresh provisioning reaches:

```text
LOCAL_EXACT_MATCH
```

only after:

```text
key WRITE_CONFIRMED
secret WRITE_CONFIRMED
final key readback exact
final secret readback exact
same expected generation witnesses
same expected byte lengths
continuous mutex ownership
canonical final evidence published
```

The pair is one generation.

A mixed generation never passes.

A partial generation never passes.

---

## 15. Provider-effect freeze

Before the first `/v3` provider effect, `/v3` is staging state governed by this provisioning/reconciliation contract.

The **first real authenticated Alpaca request using `/v3` permanently closes the staging window**, regardless of whether the result is:

```text
HTTP 200
HTTP 401
HTTP 403
HTTP 429
HTTP 5xx
transport failure
ambiguous transport outcome
process interruption after the request fence
```

After that point:

```text
NO /v3 overwrite
NO /v3 delete-for-replacement
NO /v3 cleanup
NO /v3 reprovision
```

Any further rotation requires `/v4`.

Thus the future D1R4 authentication qualification is also the `/v3` immutability boundary.

---

## 16. Secret discipline

Unchanged:

```text
no raw credential in Git
no raw credential in ChatGPT
no raw credential in argv
no raw credential in environment
no raw credential in evidence
no raw credential in logs
no raw credential in exceptions
no raw credential in screenshots requested for review
```

Mutable native/Python temporary buffers retain the existing clearing rules where technically possible.

Immutable Python string zeroization is not claimed.

Witness fingerprints and lengths are non-authentication comparison evidence only.

---

## 17. Prohibited effects during source implementation

Implementation/tests/CI remain:

```text
WINDOWS_ALPACA_CREDENTIAL_READS=0
WINDOWS_ALPACA_CREDENTIAL_WRITES=0
WINDOWS_ALPACA_CREDENTIAL_DELETES=0
ALPACA_HTTPS_REQUESTS=0

PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
SESSION_RESERVATIONS=0
SESSION_RECOVERIES=0
STRATEGY_EVALUATIONS=0

ROBINHOOD_CALLS=0
PREPARE=0
EXECUTE=0
PAPER_MUTATIONS=0
BROKER_PLACEMENTS=0

SCHEDULER_CALLS=0
ACL_MUTATIONS=0
D1_OPERATIONS=0
D2_OPERATIONS=0
```

All credential and mutex behavior during source testing uses fakes or disposable test-owned Windows objects that do not touch the real `/v3` Credential Manager targets.

---

## 18. Required focused concurrency tests

D1R4 source tests must prove at minimum:

- two provisioning processes cannot both enter the credential boundary;
- fixed global mutex only;
- no `Local\` fallback;
- no timeout takeover or lock stealing;
- concurrent owner causes zero credential effects;
- `WAIT_ABANDONED` performs reconciliation only;
- initial present `/v3` blocks fresh provisioning;
- no `CredWriteW` occurs before durable intent;
- one exact write call per role;
- exact readback required for confirmation;
- write-call crash/failure/readback mismatch becomes ambiguous;
- no automatic cleanup after ambiguous write;
- failure before second write may clean the first confirmed role only under uninterrupted ownership;
- cleanup rechecks the exact witness before delete;
- mismatched pre-delete readback prevents `CredDeleteW`;
- ambiguous delete stops all further cleanup;
- reconciliation is read-only;
- matching pair can be recovered without rewrite;
- absent pair does not automatically retry;
- exact partial pair requires separate cleanup;
- unknown/mismatched state is never deleted;
- `/v2` is never read, written or deleted;
- secrets never enter output/evidence/error representations.

No real host qualification occurs during source testing.

---

## 19. Authority meaning

A successful provisioning result means only:

```text
LOCAL_V3_PAIR_EXACTLY_PROVISIONED
```

It does not mean:

```text
REMOTE_ALPACA_AUTH_READY
D1_READY
PAPER_READY
D2_READY
BROKER_READY
```

The next real authenticated Alpaca qualification remains a separately reviewed one-request protected boundary.

Real-money trading remains NO-GO.
## 20. D1R4R incident cleanup state machine and operational boundary

Section 13's conceptual cleanup authority is implemented only for the exact
complete consumed one-byte generation recorded above. D1R4R requires the full
pair initially; it does not authorize section 13's general partial-generation
cleanup or adoption of any other generation/reconciliation artifact.

The separate bounded canonical newline-JSON schema is
`alpaca-v3-staging-cleanup/v1` (16384-byte bound). Every record binds current
cleanup HEAD/TREE, fixed v3 policy and incident digest/length/source identity.
The digest binds the preserved witnesses without storing raw credentials.
The closed successful sequence is:

```text
CLEANUP_RESERVED
LOCK_ACQUIRED
PRESERVED_GENERATION_ACCEPTED
PAIR_MATCH_CONFIRMED
KEY_DELETE_INTENT
KEY_DELETE_CONFIRMED
SECRET_DELETE_INTENT
SECRET_DELETE_CONFIRMED
PAIR_ABSENCE_CONFIRMED
FINAL / CLEANUP_EXACT_PAIR_REMOVED
```

Every record is flushed/fsynced. Before each native delete, both fixed records
are reobserved after durable intent: MATCH/MATCH for key, ABSENT/MATCH for
secret. Immediate readback precedes each confirmation. Any missing/foreign/
unreadable record, source drift, incident drift/provider fence or lost ownership
before first delete produces zero deletes. After any native delete entry,
uncertainty is DELETE_OUTCOME_AMBIGUOUS with no further deletion. Busy ownership
is CONCURRENT_PROVISIONER; WAIT_ABANDONED is ABANDONED_OWNER, with zero reads,
writes or deletes. Failure before deletion is CLEANUP_ADMISSION_BLOCKED.
All terminal states consume the fixed latch. Damaged/partial evidence or failed
final fsync/release requires review; a complete success record cannot override
a failed host outcome. No retry, restore, replacement or reprovision is included.

The host is `trading_bot.review_paper.alpaca_credential_cleanup_host`; import and
`--help` are inert. Its protected surface takes exact admitted current HEAD/TREE,
a preserved-journal path and the fixed cleanup interlock. It accepts no arbitrary
output path. The existing auth source/evidence admission helpers constrain the
named worktree/live branch, package roots and external non-reparse ancestors.
The original incident is opened only in rb mode and checked before acquisition
and repeatedly under the mutex. The latch is exclusively created before mutex
acquisition and any credential effect, preserving crashes and reservation failure.

Later effect budget: fixed v3 reads, at most one key and one secret CredDeleteW,
external latch writes/fsync, fixed mutex operations and read-only Git admission.
Always zero CredWriteW, v2 access, Alpaca HTTPS, production/session/paper/strategy/
Robinhood/broker/scheduler/ACL/PREPARE/EXECUTE/D1/D2 effects. Source tests are fake
or disposable-temp-only; actual Windows cleanup qualification is still pending.
