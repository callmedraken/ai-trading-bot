# Architecture 134-D1R4 — v3 credential generation and authentication preparation

## 2026-10-13 — Architecture 134-D1R4R implemented; SOURCE ACCEPTANCE PENDING

D1R4R adds a source-owned, incident-specific pre-provider `/v3` exact-pair
cleanup protocol and protected host. This is source/fake-test work only: **the
real cleanup has NOT executed**, and authentication remains frozen. Exact
GitHub diff, mapped source-gate/ROBINHOOD CI and ChatGPT review are required
before source acceptance; canonical accepted-checkpoint closeout follows review.

The consumed incident is fixed in source: generation HEAD
`41351ade6a2434adc26b9389106339e034b53a06`, TREE
`6a6e6528c7e0bfb43835f70c620276f960f723ee`, 4865 bytes, SHA-256
`217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193`.
The supplied journal path must resolve to the original frozen incident path,
with no symlink or hardlink; copies cannot substitute for a provider-fenced
original. Both preserved witnesses have length one; this generation is not accepted for
authentication. Its original journal is read-only and remains unmodified.

Cleanup reserves one fixed incident-wide external latch:
`F:\AI\temp\qualification\arch134-d1r4r-cleanup-217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193.json`.
There is no selectable evidence destination, role, target, policy, digest,
witness or generation. Moving/copying the supplied preserved journal does not
change this latch. An existing, partial, blocked or ambiguous latch prevents
another attempt; no automatic retry or latch removal is authorized.

Under the same fixed D1R4 Global mutex and accepted security policy, cleanup
revalidates source and original incident bytes throughout observation/deletion.
Busy or abandoned ownership gives zero credential effects. Both current fixed
`/v3` records must reproduce both preserved witnesses/lengths before the first
delete. Cleanup also rejects unexpected flags, attributes, alias, username or
comment metadata; the ordinary reader's one-byte readability is retained.
Each role has a distinct durable flush/fsync intent, at most one delete,
immediate verified absence and durable confirmation. The remaining secret must
still match before its delete. Independent final absence of both records and
final durable evidence under continuous ownership are required for
`CLEANUP_EXACT_PAIR_REMOVED`. Any uncertainty after native delete entry is
`DELETE_OUTCOME_AMBIGUOUS`, stopping every later delete and preserving partial
state without restoration. Failed final publication/release cannot report success.

New interactive provisioning requires strict bounded UTF-8 values of at least
eight bytes, exact repeated hidden entry, displayed nonsecret lengths and the
fixed human confirmation
`CONFIRM_LENGTHS_MATCH_INTENDED_FRESH_DASHBOARD_GENERATION`. This local floor
only rejects truncation/placeholders; it asserts neither a provider format nor
remote authentication. Every mutable input/repeat/readback copy is cleared;
immutable Python string zeroization is not claimed. Shared/recovery readers
continue to admit the historical one-byte pair.

All predecessor Architecture-134 pin dictionaries, including D1R4, are frozen;
D1R4R is a narrow successor overlay. Actual runner inventory is FULL 173 /
ROBINHOOD 97 / LEGACY 215 / EXHAUSTIVE 388, with unchanged required baselines
and exact topology assertions. The existing branch/checkpoint mapping remains
ROBINHOOD-owned and source-only; CI never invokes cleanup or authentication.

No real Credential Manager, Alpaca/provider, production SQLite/session,
strategy, Robinhood, PREPARE/EXECUTE, paper, broker, scheduler, ACL, D1 or D2
effect occurs in this checkpoint. `/v2` is immutable historical state. After
source acceptance, the next boundary is separately guarded read-only/pre-effect
readiness and one protected incident cleanup. Only reviewed successful cleanup
can precede separately provisioned/accepted fresh credentials and a separately
reviewed one-shot authentication. D1/D2 remain disconnected; real money is NO-GO.

## 2026-10-13 — D1R4 real /v3 provisioning consumed; authentication STOPPED on input-shape anomaly

The separately protected D1R4 local provisioning operation was executed once
against exact docs-descendant source HEAD
`41351ade6a2434adc26b9389106339e034b53a06`, TREE
`6a6e6528c7e0bfb43835f70c620276f960f723ee`. The reviewed host returned
`LOCAL_EXACT_MATCH` with exit 0 and published the canonical external generation
journal:

```text
F:\AI\temp\qualification\arch134-d1r4-v3-generation-77f1e13347fb4559b07523d30c4a7fb5.json
SHA256 217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193
BYTES  4865
```

The journal is complete and canonical through sequence 9:
`PROVISIONING_RESERVED`, `LOCK_ACQUIRED`, `EXPECTED_GENERATION`,
`INITIAL_STATE_ACCEPTED`, key write intent/confirmation, secret write
intent/confirmation, `PAIR_CONFIRMED`, then
`FINAL / LOCAL_EXACT_MATCH`. It contains no
`V3_PROVIDER_EFFECT_INTENT`, no ambiguity classification, no cleanup event and
no abandoned-owner classification. No Alpaca HTTPS request, D1 invocation or D2
invocation occurred.

However, the nonsecret witness metadata records `utf8_length=1` for both the
API-key role and secret-key role. The accepted source currently admits any
non-empty bounded UTF-8 credential satisfying its whitespace/control-character
rules, so this one-byte pair can pass local exact readback. That is not accepted
as proof of the intended full dashboard credential pair. **Remote authentication
must not run from this generation.**

The provisioning operation is consumed and MUST NOT be rerun. The current
`/v3` records now exist, so ordinary fresh provisioning would correctly block
on existing state. Manual overwrite/delete and out-of-band Credential Manager
repair remain unauthorized. Because no `V3_PROVIDER_EFFECT_INTENT` exists and
no provider request occurred, the `/v3` staging window is not yet permanently
closed by provider use.

Next safe milestone: a source-only, separately reviewed D1R4 recovery checkpoint
for pre-provider exact-pair staging reset. It must bind the preserved journal and
digest, acquire the same fixed mutex, independently reproduce the exact current
witnesses/lengths, durably fence each delete before `CredDeleteW`, verify exact
absence, make zero provider requests, and stop on any mismatch or delete
ambiguity. After that source is accepted and one protected cleanup succeeds, a
fresh generation can be separately provisioned. Authentication remains blocked
until a new generation is accepted.

Status: **SOURCE ACCEPTED** at executable/test HEAD
`c49ab6413b2713c249f1b878edd67a92ce2b6bbd` / TREE
`e3f5d09040d6e8764c00854f7fdcd2cf987edffd`; Checkpoint Source Gates
#525 / 38478403817 is superseded operationally by the consumed real D1R4
provisioning record above. No Alpaca provider request has run under `/v3`;
authentication is stopped pending exact-pair staging recovery.

## Accepted predecessor D1R4 source contract (historical; D1R4R above supersedes fresh input/cleanup)

The current policy is `windows-credential-manager-alpaca-market-data/v3`, with
only `AITradingBot/MarketData/Alpaca/ApiKeyId/v3` and
`AITradingBot/MarketData/Alpaca/ApiSecretKey/v3`. The shared reader retains strict
Generic Credential/local-machine/UTF-8/size/whitespace/CR/LF/NUL admission,
native buffer clearing/freeing, mutable-copy clearing and redacted scopes.
No environment/config/CLI target selection or v2 fallback exists.

The reviewed [concurrency amendment](../architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md)
is the provisioning authority. Its fixed Global mutex uses Architecture-77
protected kernel-object owner/DACL discipline, bound to the current token SID,
without importing Trading-SID/C1/C3 operational authority. Admission checks run
before evidence reservation; exclusive evidence is reserved before the zero-wait
mutex acquisition. Busy ownership permits no credentials/input. Abandonment
permits only fixed-target read-only reconciliation; no writes/deletes/prompt.
Final durable classification precedes mutex release. Release uncertainty poisons
subsequent admissions in the same process.

`alpaca_credential_host` exposes only protected `--provision-v3` and
`--reconcile-v3`. Provisioning requires a real local interactive terminal and
the exact human staging/exclusion statement
`NO_V3_PROVIDER_EFFECT_AND_NO_OUT_OF_BAND_CREDENTIAL_WRITERS`. At the predecessor checkpoint both dashboard
values were entered without echo; D1R4R now requires repeated hidden entry,
the local byte floor and fixed lengths confirmation described above. Getpass's echo fallback is rejected. Raw
credentials never enter argv, environment, journal, stdout, stderr or errors.
Immutable Python-string zeroization is not claimed.

Both absent targets are required. Each mutation has a canonical durable
flush/fsync intent before the native call. A successful return, immediate strict
readback, exact Architecture-84 fingerprint/byte length, source readmission and
durable confirmation are all required. The pair passes only after final exact
pair readback under continuous ownership. Entered-but-unconfirmed writes stop
all further mutations; a native failure return is conservatively ambiguous.

Only a failure before the secret write is entered may clean an already-confirmed
key. Durable delete intent, fresh matching key/absent secret observation, one
delete and verified pair absence are required. Mismatch prevents deletion.
Delete/evidence/readback uncertainty stops cleanup. Interrupted/truncated
post-effect artifacts remain preserved and require reconciliation.

Separate read-only reconciliation requires the preserved external journal and
its exact SHA-256 digest. It classifies absent, exact pair, exact partial and
unknown/foreign state without writes, deletes or retries. Partial/foreign state
cannot authorize provisioning or authentication. At that predecessor checkpoint, post-crash destructive cleanup
was intentionally not exposed. D1R4R implements section 13 only for the
frozen consumed pre-provider exact pair, with the separate latch above. Reconciliation alone
grants no cleanup authority.

## Evidence and authentication evolution

The independent provisioning journal schema is
`alpaca-v3-credential-generation-journal/v1`, bounded to 32768 bytes. Each
canonical sorted compact UTF-8 JSON record ends in one newline and contains only
schema, sequence, closed event/classification, source HEAD/tree, fixed policy and
optional exact two-role nonsecret witnesses. Unknown/noncanonical/incoherent
witness metadata fails closed. Only complete records can supply witnesses after
a truncated final record; truncation conservatively closes provider staging.

The D1R4 authentication host retains `alpaca-authentication-qualification/v1`
unchanged, the exact SPY completed-session 2026-10-07 probe and accepted provider
request/feed/query/transport/parser semantics. Its interlock is now
`AUTHORIZE_ARCH134_D1R4_ONE_ALPACA_AUTH_QUALIFICATION`. It additionally requires
`--generation-evidence` and `--generation-sha256`: a complete accepted provision
or exact-pair reconciliation journal. Under the same mutex, one pair read must
reproduce the expected witnesses. It appends/fsyncs `V3_PROVIDER_EFFECT_INTENT`
to that original journal before any possible provider request. This conservative
irreversible fence prohibits another qualification from that journal even after
source drift, transport failure, HTTP rejection, crash or publication failure.
Reconciliation propagates the fence, and never reopens staging.

This adds no field or semantic relaxation to authentication v1. PASS still needs
exact source, pair readiness, one request, compatible HTTP 200 and final source
readmission. Host failures never retry. Witness/fence readiness failures cannot
produce a provider request. Existing record-body/header/free-text redaction and
exclusive external authentication evidence rules remain intact.

## Historical replacement classification

Current shared reader/operator names are v3/D1R4. Frozen predecessor dictionaries
remain untouched; a thirteen-path current overlay owns the six evolved/new
source files and seven affected tests/profile assertions. This includes four
retained current-product exact inventory assertions exposed by canonical CI;
their expected FULL/ROBINHOOD/EXHAUSTIVE counts are updated without weakening the
assertions. The existing
branch maps once to `arch134-alpaca-authentication-qualification`, still
ROBINHOOD, source-only with no runner preflight/execute hook. ACTIVE remains 63;
inventory becomes FULL 172 / ROBINHOOD 96 / LEGACY 215 / EXHAUSTIVE 387. Required
122/49 baseline tuples remain frozen; the new supported test is automatically
owned by the review_paper family.

Intentional v2 history: consumed D1R2/D1R3 records in status/handoff/Architecture
134, the D1R3 validation snapshot, Architecture 84/84A and matching validation,
and retired `runtime/windows_effectful_capture.py` protocol tests. These describe
their original authority, not current provisioning. Alpaca `/v2/stocks/bars` is
an unchanged provider API route, not a credential version.

## Historical D1R4 verification/acceptance and next boundary (superseded by incident recovery above)

Use Python `-B`, pytest `-p no:cacheprovider` and fresh
`F:\AI\temp\pytest\arch134d1r4-*` basetemp roots. Cover credential strictness,
runtime/host composition, auth transport/parser/evidence, generation witnesses,
mutex security/concurrency/abandonment, durable fencing, ambiguity/no cleanup,
conditional cleanup, read-only reconciliation, frozen pin overlays and exact
profile/routing inventory. Run focused Ruff check/format and `git diff --check`.

Ordinary exact-file commit/push is authorized; mapped GitHub CI owns canonical
ROBINHOOD. No local broad certification is required. All source tests use fakes;
the two-process exclusion test uses a disposable test-only synchronization object.

Exact GitHub review is complete. The accepted source preserves all 14 predecessor
Architecture-134 pin dictionaries byte-for-byte and adds the D1R4 successor
overlay. Checkpoint Source Gates #525 is terminal green; canonical ROBINHOOD
selected 96 modules and 8,981 cases, with 8,980 passed, one optional skip and
zero failures/errors in 281.659 seconds. The documented Architecture-77
repository-local Windows cache-path condition remains a separate pre-existing
LEGACY compatibility issue and is not a D1R4 acceptance blocker.

The next protected step is exact docs-descendant host/evidence readiness and one
fresh v3 dashboard generation/provisioning/witness operation; then, only after
review of the preserved journal and digest, a distinct one-shot D1R4
authentication invocation. Neither protected effect has executed here. The D1R3
401 is consumed. D1 launch, D2 and real-money trading remain NO-GO.
