# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Local repository:** `F:\AI\ai-trading-bot`
**Integration branch:** `develop`  
**Current architecture branch:** `feature/windows-effectful-market-data-capture`  
**Current release-source checkpoint:** `82ba29ae2c2cc6bb3544077db0ee21868e6d5693`
**Handoff status:** August 29, 2026 — C3 is FULLY COMPLETE / ACCEPTED at final source head `82ba29ae2c2cc6bb3544077db0ee21868e6d5693` after controlled production call #6; call #5 remains permanently consumed as `FAILED / CONFIRMED` after parent artifact publication failed; call #6 is `SUCCEEDED / CONFIRMED` and `SUCCESS_SELECTED`; `/v2` is immutable historical credential-reference state; parallel GUI work remains separate from C3

> The Git-tracked `docs/AI_TRADING_BOT_HANDOFF.md` is the canonical handoff. Uploaded Project copies are mirrors only. Documentation closeout creates later docs-only commits, so always verify the live branch and use the release-source SHA above for artifact work.

---

## 1. Product goal

Build a conservative automated trading platform that progresses through:

**historical research → deterministic simulation → manual paper → unattended paper → long paper soak → broker-paper → live-readiness certification → tiny restricted live → mature automated operation → polished GUI.**

Restricted real-money trading is a long-term goal, but strategy/AI remains subordinate to deterministic risk, production authority, credentials, brokerage/reconciliation, operating-mode controls, durable evidence, and operator emergency controls.

**Production/live trading remains NO-GO.**

---

## 2. Current production architecture

```text
ValidatedProductionAuthority (C1)
        ↓
WindowsTransactionalAuthority (C2)
        ↓
WindowsEffectfulDailySnapshotCapture (C3)
        ↓
isolated suspended Windows child
        ↓
Windows Credential Manager
        ↓
Alpaca market-data API
```

C2 alone is effectfully inert. C3 is the only reviewed bridge into effectful market-data capture and does not authorize brokerage or live trading.

Core effect ordering:

```text
CreateProcessW suspended
→ durable C2 execution / PRE_RESUME_READY
→ write canonical child request
→ close request writer
→ commit ResumeIntent
→ ResumeThread exact primary thread once
→ bounded child/process observation
→ cleanup evidence
→ independent parent verification
→ terminal / publication / selection
```

`RESUME_RECORDED` is lifecycle evidence, not provider-success evidence. Ambiguous external effects fail closed and must never be retried optimistically.

---

## 3. Frozen production facts

```text
Trading account: DESKTOP-I4DOKM7\Trading
Trading SID: S-1-5-21-1397534616-3988210162-180023805-1009
Fixed runtime: F:\AITradingBot\runtime\python.exe
Runtime directory: F:\AITradingBot\runtime
TEMP/TMP: F:\AITradingBot\temp
Capture output: F:\AITradingBot\Authority\capture-output
Child: python.exe -m trading_bot.runtime.windows_effectful_capture_child
Native API: CtypesWindowsEffectfulCaptureNativeApi
Credential policy:
  windows-credential-manager-alpaca-market-data/v2
Credential targets:
  AITradingBot/MarketData/Alpaca/ApiKeyId/v2
  AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
Child env: SystemRoot,WINDIR,TEMP,TMP,PYTHONUTF8
```

Frozen production SQL:

```text
length: 118896 bytes
SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
```

---

## 4. C3 status — FULLY COMPLETE / ACCEPTED

C3 is **FULLY COMPLETE / ACCEPTED** at final source head
`82ba29ae2c2cc6bb3544077db0ee21868e6d5693`. The accepted E3.7 source repair is
`137bbe5a83d3bfe1cb62c381026c25e7fefa739a`.

The final controlled production acceptance proved the complete Architecture 82
chain: one C1-approved non-administrator Trading process, one C2-authorized
provider attempt, contained-child secret isolation, durable C2 process/resume
fences, independent parent verification and publication, durable successful
selection, and independent post-run offline verification. C3 completion is not
merely Alpaca HTTP success.

C3 has exactly six consumed real-provider effects. Historical call #5 remains
`FAILED / CONFIRMED` after parent publication failure and is permanently
non-retryable. Final call #6 is `SUCCEEDED / CONFIRMED` with durable
`SUCCESS_SELECTED` session and attempt state, `COMMITTED` claim, terminal
`SUCCEEDED`, and `PROVIDER_DISPOSITION=CONFIRMED`.

The frozen production SQL remains 118896 bytes with SHA-256
`aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`. The
accepted wheel is `ai_trading_bot-0.1.0-py3-none-any.whl`, 674358 bytes, with
SHA-256 `b35bbe0adc8f55ea96cc9f9e1852015182d07ed32b98d86cc141129395e431d2`.
The dedicated identity is `DESKTOP-I4DOKM7\Trading`, SID
`S-1-5-21-1397534616-3988210162-180023805-1009`, non-administrator. `/v2`
credential references remain immutable historical inputs; later rotation
requires a separately reviewed `/v3` or later version.

Production brokerage and live trading remain **NO-GO**. C3 does not authorize
brokerage credentials, broker reconciliation, order submission/cancel/replace,
real-money trading, unattended scheduling, automatic retry, automatic recovery,
or paper-account mutation.

---

## 5. Historical E3.4 deployed runtime

Accepted E3.4 source:

```text
134467ecda1ffbb39f48cf68a2d3e9017d1d2f61
fix: classify Alpaca response metadata failures
```

Accepted E3.4 wheel:

```text
F:\AI\c3-e34-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl
length: 673212 bytes
SHA-256: b7fdbabeb936c311eeae3509635ec57d40fa999e421dc4e9cd5afb8bbe0848db
```

Its deployment, Trading RX republication, and non-admin zero-provider preflight were accepted. It was later replaced by E3.5 and is now historical.

---

## 6. Consumed real-provider lineages

### August 21, 2026

```text
session: 4667f0a1-8890-57b9-ae07-98ffc9633ade
attempt ordinal: 0
terminal: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_FAILED
request digest: 823e9bee88de07bbd6d3384559dd6207ad216e69d46443594f8664fff49854a7
```

Permanently consumed. Never retry.

### August 24, 2026

```text
request digest: ed4cc49dc385486ac5ca623f64e99766247e371c90f29f1ff8fd585841d6b651
session: c78b94a4-963f-5197-9a03-16017ea2203b
attempt: e1a74104-150c-5ef9-96f3-f9d6d0c8aee0
claim: 2fa4aa8b-b571-5051-b48b-19a658b4fe3b
reservation: 4d49805d-661b-53b2-a8df-ba041323da2f
execution: 5acd937c-35b4-5e68-87cd-afc781872176
terminal: b4c34eec-81d4-5dad-b01a-34d88fca05d4
terminal state: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_RESPONSE_METADATA_FAILED
selection/snapshot/artifact: none
```

Fence entered; result transport/process observation/cleanup completed; terminal reason `POST_FENCE_CHILD_FAILURE`. Exact rejected metadata condition is unrecoverable from this E3.3 lineage. Permanently consumed.

### August 25, 2026

After New York-date rollover, pure planning authorized session `2026-08-25` with fresh digest:

```text
b41a85c7b907ccd2a687d9f832d72a85cf152db46c85eaf9665809635ce9674b
```

Durable freshness before the effect was zero. Exactly one provider effect produced:

```text
session: 2420ce3f-4395-504a-8bd6-995fe87055db
attempt: 0cebdb94-0a83-5b46-ac43-979dfc98b168
claim: 7e57b5ee-5ce8-55e6-93f9-62e8f6ab4b4d
reservation: 2dfc0505-f1ad-5b07-b455-c47364e82bf7
execution: 33d5ec52-1bae-5cdb-bb20-7e707cdcf039
terminal: 96dc59fb-f393-5033-beba-ea78470d12ea
terminal state: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_FAILED
selection/snapshot/artifact: none
```

Durable inspection verified fence entered, request/result transport complete, process exited zero, parent/staging cleanup complete, artifact verification not attempted, evidence/diagnostic digests valid, and `POST_FENCE_CHILD_FAILURE`. E3.4 therefore narrowed the earlier broad metadata failure to Content-Type validation. Permanently consumed.

### August 26, 2026

After New York-date rollover, pure planning authorized session `2026-08-26` with fresh digest:

```text
cccf56d1361ee4df8cf34745f68b32b29c52efdaaa80d2a02d4a32323dedce7f
```

Read-only durable freshness before the effect was zero across all five lineage tables. Provider call #4 was then explicitly authorized for one supervised effect and produced:

```text
session: 32b6765f-d1ae-5d11-81df-b95e82178edf
attempt: c19975b6-10b4-5893-93a2-aca92e606229
claim: fa184f7f-85bd-5830-bb96-70ae334a2d2e
reservation: 995883d2-bdc4-5909-9e35-b4e8343beab7
execution: 71ebf7dc-aaf4-504c-a15c-33c7b2afd6bb
terminal: 67defd53-e6b2-5f6e-945e-de51b5846962
terminal state: FAILED
provider disposition: CONFIRMED
child classification: HTTP_FAILED
http status: 401
provider request ID: 1a57fe61031771fc4b0f818c84f9e6e0
selection/snapshot/artifact: none
```

Durable inspection verified exact request/lineage binding, provider-call budget 1, provider fence `ENTERED`, complete result transport, child process `EXITED_ZERO`, complete parent cleanup, complete staging cleanup, valid post-resume/cleanup/terminal evidence digests, terminal evidence schema 2, `artifact_verification=NOT_ATTEMPTED`, terminal reason `POST_FENCE_CHILD_FAILURE`, zero selection rows, exactly four durable sessions total, and SQLite `total_changes=0` during the inspection.

E3.5 therefore worked as intended diagnostically: the prior Content-Type symptom is now resolved to a concrete provider authentication response. This lineage is permanently consumed. Never retry it.

At that historical checkpoint, calls #1–#5 had been consumed, with call #5 the first `/v2` lineage. The final controlled call #6 is recorded in Section 12 and brings the current total to exactly 6.

---

## 7. E3.5 source certification — accepted

Provider call #3 revealed that a safe non-200 response carrying a non-JSON Content-Type could be rejected as successful-response metadata failure before preserving the HTTP status.

Accepted source sequence:

```text
8913baf9fd56b2aa921781ab8e837ed10b63c25f
fix: preserve Alpaca HTTP failure status

034ed9bedfda698936c51e2560d79bb59694929a
fix: persist Alpaca HTTP failure evidence

b0e94240291e59ee2214d639d096b4dc5cf7e094
test: preserve historical C3 evidence compatibility
```

E3.5 contract:

- safe non-200 responses with missing/`text/plain`/`text/html` Content-Type reach `AlpacaHttpStatusError` while retaining structural, duplicate-header, encoding, framing, content-length, body-bound, and one-request protections;
- provider code is parsed only from supported JSON media types and remains optional sanitized diagnostics;
- HTTP 200 remains strict supported JSON + strict UTF-8 parsing;
- new closed success-response Content-Type classifications distinguish missing, wrong media type, unsupported charset, and unsupported parameter form;
- durable cleanup/terminal evidence-v2 stores exact non-200 integer `http_status` and optional bounded printable-ASCII `provider_request_id` only for `HTTP_FAILED`;
- these HTTP fields are bound to the immutable serialized child result and child-result SHA-256 and become visible to the operator only after terminal persistence;
- non-HTTP classifications keep HTTP evidence null;
- optional provider-code parsing cannot mask a known HTTP status on malformed/deep/oversized-number JSON;
- production SQL, provider host/query/feed, credentials, provider-call budget, native process ordering, and retry authority are unchanged;
- historical schema-1 C3 cleanup/terminal/diagnostic evidence remains accepted by current read-only production validation and is not rewritten.

Final source certification at `b0e94240291e59ee2214d639d096b4dc5cf7e094`:

```text
3171 passed, 16 skipped, 0 failed
Ruff check src tests: pass
Ruff format --check src tests: 338 files already formatted
git diff --check: pass
tracked working tree: clean
production SQL: unchanged
```

**E3.5 source certification is accepted.**

---

## 8. E3.5 frozen artifact and deployment — historical accepted checkpoint

The failed `c3-e35-production-*-v1` attempt is permanently rejected. It followed an invalid mistyped SHA and never produced a valid wheel.

Accepted artifact:

```text
source commit: b0e94240291e59ee2214d639d096b4dc5cf7e094
source tree: 8c8d360f944077a777eea529051b0bce1d7de707
source export: F:\AI\c3-e35-production-source-v2
wheel: F:\AI\c3-e35-production-wheelhouse-v2\ai_trading_bot-0.1.0-py3-none-any.whl
length: 674463 bytes
SHA-256: 7c5f44bd2ef28992334094ef46e8b2f5ddd8c502d7086bb4a44d66bf8133edb9
wheel entries: 192
RECORD rows / hashed payloads: 192 / 191
```

Offline artifact inspection, administrator deployment, Trading RX republication, and non-admin E3.5 zero-provider preflight were all accepted. The fixed runtime has since been replaced by the accepted E3.6 artifact below.

---

## 9. E3.6 `/v2` source, artifact, deployment, and credential proof — accepted

Architecture 84 defines the fixed `/v2` credential-reference contract. Architecture 84A permits `/v2` pair restaging only before the first `/v2` real provider effect; after that first effect, `/v2` is immutable historical credential-reference state and any later rotation requires a new version.

Accepted source:

```text
commit: 41de33d3ef8ca22a6418146a6302969e11bbacc1
tree:   44946d941f698c7290f43e47792e667443668055
```

Certification:

```text
3177 passed, 16 skipped, 0 failed
Ruff check src tests: pass
Ruff format --check src tests: 338 files already formatted
git diff --check: pass
production /v1 grep under src/trading_bot: zero matches
production SQL: unchanged
```

Accepted artifact:

```text
source export: F:\AI\c3-e36-production-source-v1
rejected wheelhouse: F:\AI\c3-e36-production-wheelhouse-v1 (zero wheel files)
wheel: F:\AI\c3-e36-production-wheelhouse-v2\ai_trading_bot-0.1.0-py3-none-any.whl
length: 674468 bytes
SHA-256: 98971acb4809fc7c5b4286771f64dee55349f083a188086ba5d2c78cd5301a21
wheel entries: 192
RECORD rows / hashed payloads: 192 / 191
package source files: 188 exact matches
```

Deployment and zero-provider preflight:

- exact accepted wheel re-proved immediately before install;
- production runtime quiescent;
- Trading RX revoked before replacement and republished only after verification;
- all 191 hashed wheel payloads reconciled;
- installed credential policy/targets are exactly `/v2`;
- installed `/v1` production fallback is absent;
- production SQL remains exact; SQLite remains 3.50.4;
- administrator authority validation remained `VALIDATED / INITIALIZED_SUPPORTED` with exact Trading SID;
- runtime owner/ACL topology is exact and all 12,453 descendants inherit Trading RX;
- corrected Trading preflight verified the signed bootstrap directly under the non-admin Trading SID, inspected the Trading-visible fixed objects, read the production database in read-only mode with zero changes, proved runtime write denial and production-temp usability;
- no Credential Manager read/network/provider request/production child launch occurred during deployment or zero-provider preflight.

Credential local proof:

- the first `/v2` staging generation was witnessed and locally matched, then superseded by a later Alpaca dashboard regeneration before any `/v2` provider effect;
- Architecture 84A classified it `SUPERSEDED_BEFORE_FIRST_PROVIDER_EFFECT`;
- the old `/v2` pair was identified by its prior nonsecret witnesses, both targets were deleted as one reviewed restaging operation, and both targets were independently proved absent;
- one replacement Alpaca **Paper** generation was entered through hidden interactive input;
- replacement key ID UTF-8 length 26 and secret UTF-8 length 44 matched exact readback lengths;
- replacement dashboard-side and `/v2` readback domain-separated fingerprints matched exactly for both roles;
- Credential type `Generic` and persistence `LOCAL_MACHINE` passed;
- dashboard-current was confirmed after restaging;
- final accepted witness state is `FRESH_GENERATED=PASSED`, `LOCAL_EXACT_MATCH=PASSED`, `DASHBOARD_CURRENT=PASSED`;
- `/v2` real-provider effect count remains zero;
- no network/provider request occurred during provisioning/restaging/readback.

At the E3.6 checkpoint, the current `/v2` Paper pair was frozen for its first future `/v2` provider effect. Call #5 subsequently used that pair and permanently closed Architecture 84A's pre-first-effect staging window. The `/v2` targets are now immutable historical credential-reference state; do not regenerate, replace, delete, restage, or modify them. Any later credential rotation requires `/v3` or a later explicitly reviewed version.

---

## 10. C3-E3.7 Windows publication repair and provider call #5 — accepted

E3.7 implementation:

```text
commit: 137bbe5a83d3bfe1cb62c381026c25e7fefa739a
message: fix: repair C3 Windows artifact publication
```

The implementation replaced the invalid `SetFileInformationByHandle` /
`FileLinkInfo` publication path with documented `CreateHardLinkW` no-clobber
publication. It preserved retained staging identity verification, casefold
collision rejection, final reopen identity verification, exact-byte
reverification, and authority issuance only after successful parent
verification. The E3.7 Windows publication acceptance gate passed: **1
passed**.

Provider call #5 was the first real `/v2` provider effect. Calls #1–#4 are
historical `/v1` lineages. Its accepted lineage and terminal evidence are:

```text
target session date: 2026-08-28
request window: 2026-08-27 through 2026-08-27
request digest: c33949931607552c6f06503fadf818972fb4fe153dd2a65a21970e5e879a435e
session: 7bdad286-c378-5ac9-a1be-05bb685739a8
attempt: c70afb4c-921b-509e-9231-4d85bb334ca5
claim: 9edd75a1-38d3-5043-a522-edb034730a24
reservation: ff1cb0a3-b0f4-5908-812c-a1c4a8a14ed0
execution: 67400d7e-153f-5c03-a821-4d955b291c2a
terminal: 736c9432-d374-5cd1-a708-b2e008fa811b
terminal state: FAILED
provider disposition: CONFIRMED
process exit: 6
child provider classification: SUCCEEDED
child provider fence: ENTERED
child process observation: EXITED_ZERO
result transport: complete
parent cleanup: complete
staging cleanup: complete
artifact verification: PUBLICATION_FAILED
parent terminal reason: PARENT_ARTIFACT_VERIFICATION_FAILED
snapshot authority: none issued
snapshot: null
selection: none
capture-output after failure: empty
```

The `/v2` credentials and authenticated Alpaca path were remotely accepted;
the child successfully obtained the daily snapshot. The failure occurred
after the confirmed provider effect during local parent artifact publication.
Call #5 is permanently consumed and must never be retried. The repaired E3.7
publication path was then deployed and verified.

E3.7 final source certification was accepted:

```text
3186 passed
17 skipped
0 failed
Ruff check src tests: passed
Ruff format --check: 358 tracked Python files already formatted
git diff --check: passed
final source tree: clean
frozen production SQL length: 118896
frozen production SQL SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
```

Accepted E3.7 release artifact:

```text
source export: F:\AI\c3-e37-production-source-v1
wheel: F:\AI\c3-e37-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl
wheel length: 674358
wheel SHA-256: b35bbe0adc8f55ea96cc9f9e1852015182d07ed32b98d86cc141129395e431d2
wheel entries: 192
RECORD rows: 192
hashed payloads: 191
package source files: 188 exact matches
package source exact-match gate: passed
production SQL exact: passed
offline wheel verification: passed
```

E3.7 administrator deployment was accepted after the exact wheel was
re-proved before installation. The runtime was quiescent, Trading RX was
revoked before replacement, the offline/no-index/no-deps/no-cache force
reinstall succeeded, all 191 hashed payloads matched, the installed
`CreateHardLinkW` publication implementation was verified, the obsolete
`FileLinkInfo` path was absent, production SQL remained exact, SQLite remained
3.50.4, and production authority validation returned
`VALIDATED / INITIALIZED_SUPPORTED`. The bootstrap digest was
`53b8b72ab18b1c477c5eab50857e4dc2d47efc6e74030e380ed6a53387922ae4`; the
exact Trading SID remained approved. Ownership normalization processed 12,454
files with zero failures; 12,453 descendants were inspected; ACL anomalies
were zero; and the sealed runtime before RX publication contained only SYSTEM
and Administrators.

Trading RX republication was accepted with the runtime quiescent, the root
owner still Administrators, the root DACL protected, exact inheritable Trading
Read & Execute restored, all 12,453 descendants passing RX topology, and zero
Trading RX anomalies.

The non-admin Trading E3.7 zero-provider preflight was accepted for
`DESKTOP-I4DOKM7\Trading`, SID
`S-1-5-21-1397534616-3988210162-180023805-1009`, with administrator `False`.
The installed contract was exactly
`windows-credential-manager-alpaca-market-data/v2` with the exact `/v2` key
and secret targets; `/v1` fallback was absent; E3.7 publication runtime proof
and signed bootstrap verification passed; the production database was
inspected read-only; durable session count was 5; call #5's digest mapped
exactly to its expected session; SQLite `total_changes` was 0; runtime write
was blocked; and production temp read/write/delete passed.

The deployment/preflight zero-effect proof was:

```text
CREDENTIAL_MANAGER_READ=False
NETWORK_OPERATION_PERFORMED=False
PRODUCTION_CHILD_LAUNCHED=False
AUTHORITY_DATABASE_MUTATION=False
PROVIDER_REQUEST_PERFORMED=False
```

The first `/v2` provider effect has now occurred. The `/v2` staging/restaging
window is permanently closed, and the current `/v2` targets are immutable
historical credential-reference state. Do not regenerate, replace, delete,
restage, or modify `/v2`; any later credential rotation requires `/v3` or a
later explicitly reviewed version.

---

## 11. Historical pre-call #6 planner state (superseded)

The pre-call #6 planner/freshness gate was pure and read-only. It performed no
Credential Manager read, network/provider request, production child launch, or
authority mutation. It was superseded by the separately authorized final call
#6 recorded below.

Call #5 used request window `2026-08-27` for target session `2026-08-28`; that
lineage remains consumed and is not retryable. Final call #6 used the distinct
request digest and exact session mapping recorded in the controlled acceptance
section.

---

## 12. Final controlled C3 acceptance

Dedicated production identity:

```text
identity: DESKTOP-I4DOKM7\Trading
SID: S-1-5-21-1397534616-3988210162-180023805-1009
administrator: False
```

Final call #6 request and lineage:

```text
ordered universe: SPY
request window: 2026-08-28 through 2026-08-28
target session date: 2026-08-29
authorized XNYS snapshot session: 2026-08-28
request digest: 67c8e2c81da2467aa0c67328af191038d00858fe153dd0850f59ef786612efad
session_id: f787e4f6-c3ca-58fe-802b-f068dd474b41
attempt_id: e809f393-b557-5c6b-8665-78d66822fee8
claim_id: 487618c1-a5a5-5dd9-971d-a1ea843194c5
reservation_id: fa5b4538-e475-5a13-9cb2-0d7936232c84
execution_id: d85a8085-137b-55c2-9679-cddade4a5907
terminal_id: b4c76e5f-44bb-54ce-a917-3e3223b84107
selection_id: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot_id: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
status: COMPLETED
terminal_state: SUCCEEDED
provider_call_disposition: CONFIRMED
exit code: 0
```

Final read-only durable proof:

```text
DURABLE_ROW_FOUND=True
SESSION_STATE=SUCCESS_SELECTED
ATTEMPT_STATE=SUCCESS_SELECTED
CLAIM_STATE=COMMITTED
RESERVATION_STATE=TERMINAL_RECORDED
EXECUTION_PHASE=TERMINAL_RECORDED
TERMINAL_STATE=SUCCEEDED
PROVIDER_DISPOSITION=CONFIRMED
REQUEST_SHA256=67c8e2c81da2467aa0c67328af191038d00858fe153dd0850f59ef786612efad
TERMINAL_SNAPSHOT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
SELECTION_SNAPSHOT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
DURABLE_MATCH=True
```

Final artifact/offline proof:

```text
ARTIFACT_EXISTS=True
ARTIFACT_BYTES=1291
ARTIFACT_SHA256=31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
OFFLINE_VERIFY_STATUS=PASS
SNAPSHOT_ID=eba46838-44ae-5bec-97bf-98c6639ae6a7
SNAPSHOT_SESSION_DATE=2026-08-28
SNAPSHOT_SYMBOLS=['SPY']
ARTIFACT_EVIDENCE_MATCH=True
OFFLINE_SNAPSHOT_MATCH=True
C3_COMPLETION_EVIDENCE=True
```

Pre-effect evidence confirmed the exact production runtime, validated authority
and frozen schema digest, immutable `/v2` credential entries readable under the
Trading SID, corrected E3.7 `CreateHardLinkW` publication, absence of obsolete
`FileLinkInfo`, a passing same-filesystem publication canary, empty capture
output, zero durable lineage, and no provider/network operation during
preflight.

Architecture 82's stronger completion criterion is therefore satisfied. Total
actual C3 real-provider effects are **exactly 6**, all six are consumed, call #6
is successful and consumed, and no provider call #7 is authorized.

The next product milestone is the reliable manually invoked paper cycle:

```text
verified C3 snapshot
-> strategy
-> proposals
-> deterministic risk
-> paper execution
-> durable before/after evidence
```

---

## 13. Crash/recovery posture

No unsafe automatic retry path has been found. Conservative categories remain:

- pre-session/pre-attempt: no provider effect;
- process-intent around `CreateProcessW`: potentially ambiguous; manual classification required;
- proven NOT_CREATED: provider definitely not started but continuation remains explicit;
- PRE_RESUME_READY: child suspended, no provider effect;
- resume ambiguity: provider may have occurred; never retry automatically;
- post-resume durable states: manual durable recovery only;
- verified snapshot before terminal / terminal before selection: recover from durable authority without repeating provider effect.

E3.5 demonstrated in the real call #4 lineage that an `HTTP_FAILED` terminal retains sanitized non-200 status/request ID durably after terminal commit. These fields are diagnostic only and never grant retry authority.

Call #5's terminal is durably consumed as `FAILED / CONFIRMED` after the
provider fence, with no snapshot authority and no selection. It is not
retryable. Any future recovery or continuation path remains separately
reviewed authority and cannot reuse the consumed call-#5 lineage.

---

## 14. Post-C3 boundaries and downstream reviews

C3 is accepted, but the following downstream boundaries remain outside C3 and
must be separately reviewed before unattended operation:

- authoritative clock/calendar scheduling;
- selected-snapshot to paper-operation bridge;
- startup reconciliation, health/alerts, and stale/missing-data handling;
- paper-operation recovery and durable before/after evidence.

C3 does not authorize unattended scheduling, automatic retry or recovery,
brokerage, or paper-account mutation.

---

## 15. Next product milestone after successful C3 acceptance

1. Reliable manual paper cycle — selected parent-verified snapshot → strategy → proposal → deterministic risk → paper execution → durable result.
2. Unattended paper operation — XNYS scheduling, startup reconciliation, recovery, health/alerts, stale/missing-data handling.
3. Long paper soak.
4. Broker-paper integration — account/positions, submit/cancel/replace, broker/fill IDs, partial fills/rejects, reconciliation, idempotency, ambiguous-submit recovery.
5. Live-readiness certification — explicit mode authority, separate live credentials, exact account verification, strict limits, kill switch, outage/halt handling, startup reconciliation, operator-visible state.
6. Tiny restricted live deployment.
7. Mature operations, deeper AI, polished GUI.

Stable initial live constraints: US stocks/ETFs, long-only, no margin/leverage/options/shorts/crypto, deterministic risk approval for every order, paper mode by default, complete auditability.

---

## 16. Development workflow

Use ChatGPT/Sol for architecture, debugging strategy, GitHub/diff review, test-gate decisions, release gating, and next-step planning.

```text
localized/mechanical/frozen contract → Luna Extra High
subtle bounded implementation       → Sol Medium
native Windows/security/authority/
ordering/crash/recovery/architecture → Sol High
```

Codex implementation prompts should reference `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff, and only relevant architecture documents. Use focused tests during implementation and one broad suite at final certification. Preserve unrelated generated/untracked artifacts.

For wheel build/inspection/deployment/ACL/preflight/provider-call procedure, use directly supervised PowerShell rather than Codex unless a code change is actually required.

Without explicit approval, do not merge, resolve review threads, change PR metadata, force-push, rebase, amend, or modify unrelated files.

After accepted checkpoints, review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

---

## 17. Files to read when resuming

```text
AGENTS.md
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
docs/architecture/57-alpaca-daily-snapshot-capture.md
docs/architecture/77-windows-transactional-capture-authority.md
docs/architecture/80-windows-production-authority-capability.md
docs/architecture/81-windows-production-transactional-authority-service.md
docs/architecture/82-windows-production-effectful-market-data-capture.md
docs/architecture/83-c3-isolated-child-provider-execution.md
docs/architecture/84-c3-versioned-alpaca-credential-rotation.md
docs/architecture/84a-c3-pre-first-effect-credential-staging.md
docs/validation/c3-versioned-alpaca-credential-rotation.md
docs/validation/c3-pre-first-effect-credential-staging.md
```

No further provider effect is authorized. Any future change to C3 provider-effect authority requires a new reviewed milestone.

---

## 18. Definition of project success

The project succeeds when it can research deterministically, acquire trusted market data safely, make portfolio decisions under deterministic risk, interact safely with a brokerage, reconcile ambiguous outcomes, run unattended for long periods, fail closed on uncertainty, expose durable evidence and operator controls, operate under strict live limits, and present the same reviewed capabilities through a polished GUI.

The final system is a **safety-oriented automated trading platform in which AI is one replaceable decision-making component inside a deterministic operational and authority framework**.
