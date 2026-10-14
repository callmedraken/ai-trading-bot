# Architecture 134-D1R4 — v3 credential generation and authentication preparation

## 2026-10-14 — D1R4 one-shot Alpaca authentication qualification PASS

The separately reviewed one-shot D1R4 authentication qualification executed
once against exact operational source HEAD
`234614a21d68680f5b1e0ccdb5854347a6a8d090`, TREE
`f70459d91c393c6ea7a4a6358f02a2073b246574`.

Canonical external evidence:

```text
F:\AI\temp\qualification\arch134-d1r4-auth-234614a21d68680f5b1e0ccd.json
BYTES   635
SHA256  100e3590543b8ba36002d50d890578533100035b9f618434dd2c9adc2f3505c4
```

Accepted canonical result:

```text
schema                          alpaca-authentication-qualification/v1
status                          PASS
reason                          PASS
credential_pair_read_attempts   1
credential_pair_read_succeeded  true
alpaca_request_attempts         1
http_status                     200
provider_code                   null
source_readmitted               true
```

The evidence source HEAD/tree exactly match the admitted operational source.
The host read the fixed staged pair once, reproduced the preserved witnesses,
durably appended `V3_PROVIDER_EFFECT_INTENT` before the provider attempt, made
exactly one Alpaca HTTPS request, received the compatible fixed-probe HTTP 200
response, and re-admitted the source afterward. No retry is authorized.

The preserved generation journal remains canonical and accepted, is not
truncated, and remains pair-accepted. Its post-auth SHA-256 is:

`344f64a1c421c41174142aa4f30f2574537bb26e70901dd77cf56ec930ec7434`.

That changed digest records the irreversible provider-effect fence. The
generation can never authorize another authentication qualification regardless
of any later credential/provider state.

This establishes only remote Alpaca authentication readiness for the fixed
qualification probe and source observation. It authorizes no fresh D1 session,
PREPARE, EXECUTE, Robinhood paper mutation, broker placement, scheduler/ACL
effect, D2 invocation, or live trading.

The next required Architecture 134 milestone is the pre-market start /
`WAITING_FOR_MARKET` / wake qualification before a fresh D1 session can be
authorized. Real-money trading remains **NO-GO**.

## 2026-10-13 — Second hardened fresh v3 input attempt blocked pre-effect

A second separately reviewed fresh provisioning invocation at source `6b42a65e9b8849e1c7affa20c9fb2bae0f11a1e0` / `09df0e02528fbbd0e7d5689c8e80106b2946170e` ended `INPUT_OR_ADMISSION_FAILED` with exit 1. Evidence is `F:\AI\temp\qualification\arch134-d1r4-v3-generation-6eeaddebcbbf4cca8fc812da2e525674.json`, 926 bytes, SHA-256 `6bdd54624a124244e38b0fef29522d00e3f05e7f172521449159e1722d0ab047`.

Its journal again contains only `PROVISIONING_RESERVED`, `LOCK_ACQUIRED`, and `FINAL / INPUT_OR_ADMISSION_FAILED`. There is no `EXPECTED_GENERATION`, fixed-target state observation, mutation fence, pair acceptance, cleanup, or provider fence. Preserve this consumed attempt and do not rerun the same invocation. Authentication remains blocked.

Because two fresh attempts have now failed at the identical pre-length interactive stage, do not authorize another unchanged protected attempt until the Windows hidden-input transport is independently diagnosed with nonsecret dummy input.


## 2026-10-13 — Hardened fresh v3 input attempt blocked pre-effect

A guarded fresh provisioning attempt at source `c4c2126de19e3b35f54f407cd0b8b8c54dc7d861` / `dd8e24281dd370bdd1e4ebaf243d73e961869fd5` ended `INPUT_OR_ADMISSION_FAILED` before `EXPECTED_GENERATION`. Evidence is `F:\AI\temp\qualification\arch134-d1r4-v3-generation-2c37092fed0545538c148ec6fe9c2800.json`, 926 bytes, SHA-256 `19ee1f33d9327fa30ab064bcb3e0d6c7a029fac20470b6009b5f322e5bd300e4`.

The journal has only `PROVISIONING_RESERVED`, `LOCK_ACQUIRED`, and `FINAL / INPUT_OR_ADMISSION_FAILED`. No `EXPECTED_GENERATION`, initial state observation, mutation fence, pair acceptance, cleanup, or provider fence occurred. Preserve this consumed attempt. Since no write was entered, a new separately reviewed fresh attempt with a new evidence destination remains eligible; authentication stays blocked until a later `LOCAL_EXACT_MATCH` generation is separately reviewed and accepted.


## 2026-10-13 — D1R4R real pre-provider /v3 cleanup SUCCEEDED

The separately guarded, one-shot Architecture 134-D1R4R cleanup was executed
once against the accepted docs-descendant source:

```text
SOURCE HEAD  3e2c901c13fcbebf5ff309e3dd878cce0932c24f
SOURCE TREE  021884731ed58d7459b0366f0b46b833da10e14a
```

The fixed consumed D1R4 generation remained bound to the original external
journal:

```text
F:\AI\temp\qualification\arch134-d1r4-v3-generation-77f1e13347fb4559b07523d30c4a7fb5.json
BYTES   4865
SHA256  217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193
```

The D1R4R cleanup host returned `CLEANUP_EXACT_PAIR_REMOVED` with exit 0 and
published the fixed incident-wide durable cleanup latch:

```text
F:\AI\temp\qualification\arch134-d1r4r-cleanup-217f3e05f3b456d8e83de7e2f6c2708b6b2b027b5ceb615065551b92ae138193.json
BYTES   5089
SHA256  73dcbc73d94a49af2b8ab086a13bb7d756db45ae8914a17cca835976521f1433
```

The canonical cleanup sequence is complete through sequence 9:
`CLEANUP_RESERVED`, `LOCK_ACQUIRED`,
`PRESERVED_GENERATION_ACCEPTED`, `PAIR_MATCH_CONFIRMED`,
`KEY_DELETE_INTENT`, `KEY_DELETE_CONFIRMED`,
`SECRET_DELETE_INTENT`, `SECRET_DELETE_CONFIRMED`,
`PAIR_ABSENCE_CONFIRMED`, then
`FINAL / CLEANUP_EXACT_PAIR_REMOVED`.

This proves the exact preserved one-byte staging pair matched before deletion,
the key deletion was durably fenced and confirmed absent, the remaining secret
was re-proven before its separately fenced deletion, and both fixed `/v3`
targets were independently confirmed absent under continuous accepted mutex
ownership before the final success record. There is no ambiguity, abandoned
owner, partial cleanup or retry authority. The incident cleanup latch is now
permanently consumed and MUST NOT be deleted, reset or reused to obtain another
cleanup attempt.

The wrapper's post-effect source guard remained exact at the same HEAD/tree.
The cleanup performed no credential writes, no `/v2` mutation, no Alpaca
HTTPS request, no authentication request, no production SQLite/session/strategy/
Robinhood/PREPARE/EXECUTE/paper/broker/scheduler/ACL effect and no D1/D2
invocation.

The bad D1R4 generation remains historical consumed evidence and is not
authentication authority. The current `/v3` staging targets are now absent.
Authentication remains **BLOCKED**. The next permitted sequence is a separately
guarded fresh dashboard generation plus hardened fresh `/v3` provisioning,
followed by review/acceptance of that new generation evidence. Only after that
separate acceptance may the one-shot authentication qualification be considered.
Real-money trading remains NO-GO.


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

## 2026-10-13 — D1R4 Windows hidden-input transport diagnosis CONFIRMED

A nonsecret local diagnostic reproduced the D1R4 hidden-input failure mechanism
without reading, writing or deleting Credential Manager state and without any
Alpaca/provider request. The diagnostic file completed with exit 0 and SHA-256
`a63b2fe0b1796c069bd278bc06d5aa0981de03ef5be579dcdf5f858376b9333c`.

Observed exact input behavior:

- expected dummy value: 19 characters / 19 UTF-8 bytes;
- ordinary `Ctrl+V` at Python `getpass()`: exactly one character / one UTF-8
  byte, `U+0016` (SYN);
- manual hidden entry: exact 19-character / 19-byte dummy value;
- right-click paste: multi-character input rather than `U+0016`, but the
  pasted value was not the dummy value and is intentionally redacted from the
  repository.

This directly explains the original one-byte dashboard-key and secret
observation and the two later hardened attempts that failed before
`Fresh UTF-8 lengths` / `EXPECTED_GENERATION`: ordinary `Ctrl+V` must not
be used for D1R4 hidden credential prompts on this Windows terminal path.

The right-click probe also revealed a credential-looking value that was not the
dummy. That value is not trusted provisioning material and is not recorded here.
If it was a real Alpaca credential identifier, its pair must be treated as
exposed and replaced before any later protected provisioning attempt.

The two hardened provisioning attempts remain consumed pre-effect evidence.
This diagnostic does not retroactively authorize a retry and does not alter
their zero-read / zero-write / zero-delete / zero-Alpaca-request classification.

Next safe boundary:

1. preserve the two consumed journals unchanged;
2. admit the exact reviewed branch/worktree/source state;
3. use a fresh external generation-evidence path;
4. use only a known-good non-`Ctrl+V` hidden-input method;
5. do not reuse any credential material exposed by the diagnostic/chat;
6. execute at most one newly reviewed protected D1R4 provisioning invocation;
7. stop for journal/digest review before any D1R4 authentication request.

Authentication remains blocked until a later generation is independently
reviewed as the exact local `/v3` pair and its witness journal is accepted.
The diagnostic is local nonsecret evidence only; it is not a provisioning journal and cannot satisfy generation-witness or authentication-fence admission.

## 2026-10-13 — D1R4 fresh /v3 provisioning ACCEPTED / LOCAL_EXACT_MATCH

The separately reviewed post-diagnostic fresh D1R4 provisioning invocation at
source `ae19cc933f00445d00f196f7b7963bf01b5433ae` /
`b361c153035ec1dca3ffacc5c819398239f55da6` completed with exit 0 and
`FINAL / LOCAL_EXACT_MATCH`.

Preserved generation evidence:

- path:
  `F:\AI\temp\qualification\arch134-d1r4-v3-generation-b206df8a30964c4c9a807d306b54c0b9.json`;
- bytes: 4881;
- SHA-256:
  `3cb18e50b821c4f7361b213f2095d148dd18a172f60cdf72255e36838eaa7ce3`;
- schema: `alpaca-v3-credential-generation-journal/v1`;
- policy: `windows-credential-manager-alpaca-market-data/v3`;
- expected UTF-8 lengths: key 26, secret 44.

The complete ten-record journal is:

`PROVISIONING_RESERVED` ->
`LOCK_ACQUIRED` ->
`EXPECTED_GENERATION` ->
`INITIAL_STATE_ACCEPTED` ->
`KEY_WRITE_INTENT` ->
`KEY_WRITE_CONFIRMED` ->
`SECRET_WRITE_INTENT` ->
`SECRET_WRITE_CONFIRMED` ->
`PAIR_CONFIRMED` ->
`FINAL / LOCAL_EXACT_MATCH`.

There is no ambiguity classification, cleanup event or
`V3_PROVIDER_EFFECT_INTENT`. No Alpaca/provider request occurred during this
provisioning invocation. The later shell parse error from entering a detached
PowerShell `else` occurred only after the host had returned success and after
the preserved evidence file had been sized, hashed and printed; it does not
alter the generation journal or provisioning classification.

This checkpoint therefore establishes only:

`LOCAL_V3_PAIR_EXACTLY_PROVISIONED`.

It does not establish remote Alpaca authentication, D1 readiness, paper
readiness, D2 readiness, broker readiness or live-trading authority.

The provisioning invocation is consumed and MUST NOT be rerun. Ordinary fresh
`/v3` provisioning must now block because both staging targets are present.
The preserved generation journal and exact digest above are the authority input
for the next separately reviewed one-shot D1R4 authentication qualification.

Before that provider boundary, the authentication host must re-admit exact
source, read the same local pair under the fixed mutex, reproduce the journal
witnesses, and durably append `V3_PROVIDER_EFFECT_INTENT` before any possible
Alpaca request. Once that fence is appended, the journal can never authorize a
second qualification regardless of HTTP result, transport outcome or process
interruption. Real-money trading remains NO-GO.
The preserved journal is now an accepted generation-evidence input for one separately reviewed authentication qualification; it is not itself authentication proof.
