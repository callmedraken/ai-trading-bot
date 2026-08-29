# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot. The canonical cross-chat handoff is `docs/AI_TRADING_BOT_HANDOFF.md`; detailed architecture documents remain authoritative for subsystem contracts and historical decisions.

## Long-term objective

Build a conservative automated trading platform that can progress safely from deterministic historical research to simulated paper trading, unattended paper operation, broker-paper operation, restricted live trading, and finally a polished end-user application.

**Production/live trading: NO-GO.** Live trading remains unavailable until separately reviewed safety, credential, brokerage, reconciliation, operator-control, and acceptance gates are complete.

## Current milestone: reliable manually invoked paper cycle

C1 `ValidatedProductionAuthority` and C2 `WindowsTransactionalAuthority` are reviewed foundations. C3 was the reviewed bridge from C1/C2 authority into real market-data credentials, native Windows child execution, Alpaca transport, staged capture, independent parent verification, publication, and snapshot selection.

C3 is **FULLY COMPLETE / ACCEPTED** at final source head `82ba29ae2c2cc6bb3544077db0ee21868e6d5693`. Controlled production acceptance proved the complete Architecture 82 authority/effect/verification/selection chain. The next product milestone is the reliable manually invoked paper cycle, which consumes the selected verified C3 snapshot without changing C3 authority.

Completed C3 foundations include:

1. immutable capture planning and deterministic request/session identity;
2. canonical bounded parent/child protocol;
3. C1/C2/C3 composition with child success treated as evidence rather than authority;
4. exact Windows Credential Manager targets and Trading-SID verification;
5. one-shot isolated provider execution with provider-call fence;
6. native suspended `CreateProcessW` + Job Object containment;
7. durable C2 process/resume ordering and conservative crash semantics;
8. bounded child/result observation and cleanup;
9. parent verification, publication, terminal, and selection path;
10. manual `production_daily_snapshot_capture` operator boundary;
11. E3.2 closed transport-stage diagnostics;
12. E3.3 truthful transport-stage handling and separate HTTP-status semantics;
13. E3.4 closed sanitized response-metadata sub-classifications;
14. E3.5 preservation of non-success HTTP status across safe Content-Type variation, durable sanitized HTTP evidence, and stricter successful-response Content-Type diagnostics;
15. E3.6 fixed `/v2` credential-reference rotation, certified/deployed runtime, and accepted pre-first-effect credential restaging under Architecture 84A;
16. E3.7 repaired and deployed the Windows final-artifact publication path.

The native ordering remains:

```text
CreateProcessW suspended
-> durable C2 execution / PRE_RESUME_READY
-> write canonical child request
-> close request writer
-> commit ResumeIntent
-> ResumeThread exact primary thread once
-> bounded child/process observation
-> cleanup evidence
-> parent verification / terminal / selection
```

`RESUME_RECORDED` is lifecycle evidence, not provider-success evidence.

## Frozen authority and runtime facts

- Production Trading account: `DESKTOP-I4DOKM7\Trading`
- Trading SID: `S-1-5-21-1397534616-3988210162-180023805-1009`
- Fixed runtime: `F:\AITradingBot\runtime\python.exe`
- Runtime directory: `F:\AITradingBot\runtime`
- Production temp: `F:\AITradingBot\temp`
- Capture output: `F:\AITradingBot\Authority\capture-output`
- Credential policy: `windows-credential-manager-alpaca-market-data/v2`
- Credential targets:
  - `AITradingBot/MarketData/Alpaca/ApiKeyId/v2`
  - `AITradingBot/MarketData/Alpaca/ApiSecretKey/v2`
- Frozen production SQL: 118,896 bytes
- SQL SHA-256: `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`

## E3.3 certification and prior deployment

E3.3 source certification completed at `bf88890d87ed1734a4634e4b8069ff5232a20994`:

- 3,094 passed, 16 skipped, 0 failed;
- Ruff check passed;
- tracked-source Ruff format check passed.

Accepted E3.3 wheel:

- 672,104 bytes;
- SHA-256 `ed87fcce586a3b2f2477f2b99e6c404d7c42f5cc2ef29e230b12cd8ca7640b3b`;
- 192 wheel entries / 191 RECORD hashes verified.

The E3.3 runtime was deployed through the sealed-runtime procedure, Trading RX was republished, and the non-admin zero-provider preflight passed.

## E3.4 source certification

Accepted implementation checkpoint:

`134467ecda1ffbb39f48cf68a2d3e9017d1d2f61` — `fix: classify Alpaca response metadata failures`

Certified diff SHA-256:

`6d9232fef1f5dfaf8b1df329e28db20646d108a81b0e1410e2d2d9cd82cdbca6`

Final source certification:

- 3,136 passed, 16 skipped, 0 failed;
- Ruff check passed;
- Ruff format check passed across 358 tracked Python files;
- final `git diff --check` passed.

E3.4 preserves existing validation and authority semantics while adding these sanitized response-metadata classifications:

```text
TRANSPORT_RESPONSE_METADATA_ACQUISITION_FAILED
TRANSPORT_RESPONSE_METADATA_MALFORMED_FAILED
TRANSPORT_RESPONSE_METADATA_DUPLICATE_FAILED
TRANSPORT_RESPONSE_METADATA_CONTENT_ENCODING_FAILED
TRANSPORT_RESPONSE_METADATA_TRANSFER_ENCODING_FAILED
TRANSPORT_RESPONSE_METADATA_LENGTH_CONFLICT_FAILED
TRANSPORT_RESPONSE_METADATA_CONTENT_LENGTH_FAILED
TRANSPORT_RESPONSE_METADATA_REQUEST_ID_FAILED
TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_FAILED
TRANSPORT_RESPONSE_METADATA_FAILED
```

## E3.4 accepted artifact and deployment

Accepted frozen E3.4 wheel:

- source commit: `134467ecda1ffbb39f48cf68a2d3e9017d1d2f61`;
- source tree: `dcead824eee27b2e93a7391578ef1b321b595c06`;
- path: `F:\AI\c3-e34-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl`;
- length: 673,212 bytes;
- SHA-256: `b7fdbabeb936c311eeae3509635ec57d40fa999e421dc4e9cd5afb8bbe0848db`;
- 192 wheel entries / 191 hashed RECORD payloads;
- production SQL unchanged;
- exact E3.4 source-file comparisons passed;
- E3.4 metadata classifications and E3.3 HTTP hierarchy checks passed.

Administrator deployment, Trading RX republication, and the non-admin E3.4 zero-provider preflight were accepted. This is now historical; the fixed runtime has been replaced by the accepted E3.5 artifact described below.

## E3.5 source certification

Provider call #3 exposed a specific real-provider failure: `TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_FAILED`. Review showed that a safe non-200 response carrying a non-JSON Content-Type could be rejected as metadata failure before preserving its HTTP status. E3.5 hardens that boundary without weakening successful-response parsing or retry authority.

Accepted E3.5 source sequence:

- `8913baf9fd56b2aa921781ab8e837ed10b63c25f` — preserve Alpaca HTTP failure status across safe non-200 Content-Type variation and add closed successful-response Content-Type sub-classifications;
- `034ed9bedfda698936c51e2560d79bb59694929a` — persist sanitized `http_status` / `provider_request_id` in canonical durable C3 evidence-v2 and expose them only after terminal persistence; harden optional provider-code extraction;
- `b0e94240291e59ee2214d639d096b4dc5cf7e094` — regression proving historical schema-1 C3 evidence remains accepted and byte-for-byte unchanged by current read-only authority validation.

E3.5 behavior:

- safe non-200 responses with missing, `text/plain`, or `text/html` Content-Type proceed to `AlpacaHttpStatusError` while retaining bounded framing/header protections;
- provider error codes are parsed only from recognized supported JSON media types and remain optional sanitized diagnostics;
- successful HTTP 200 responses still require supported JSON Content-Type and strict UTF-8 JSON parsing;
- new closed successful-response classifications are `...CONTENT_TYPE_MISSING_FAILED`, `...CONTENT_TYPE_MEDIA_TYPE_FAILED`, `...CONTENT_TYPE_CHARSET_FAILED`, and `...CONTENT_TYPE_PARAMETER_FAILED`;
- the prior broad Content-Type classification remains accepted for compatibility;
- `HTTP_FAILED` durable evidence requires exact non-200 integer status and optional bounded printable-ASCII request ID; non-HTTP classifications store those fields as null;
- cleanup/terminal evidence-v2 is stored in the existing opaque JSON+digest columns; production SQL is unchanged;
- historical schema-1 cleanup/terminal/diagnostic evidence remains valid immutable evidence under current read-only authority validation.

Final E3.5 source certification at `b0e94240291e59ee2214d639d096b4dc5cf7e094`:

- 3,171 passed, 16 skipped, 0 failed;
- Ruff check passed on `src tests`;
- Ruff format check passed across 338 tracked source/test Python files;
- final `git diff --check` passed;
- tracked working tree clean;
- frozen production SQL remains 118,896 bytes with SHA-256 `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`.

**E3.5 source certification is accepted.**

## E3.5 accepted artifact and deployment

The first attempted artifact path (`c3-e35-production-*-v1`) is rejected and must never be used. It was created after an invalid mistyped source SHA prevented a valid export; no valid v1 wheel was produced.

Accepted frozen E3.5 artifact:

- source commit: `b0e94240291e59ee2214d639d096b4dc5cf7e094`;
- source tree: `8c8d360f944077a777eea529051b0bce1d7de707`;
- source export: `F:\AI\c3-e35-production-source-v2`;
- wheel: `F:\AI\c3-e35-production-wheelhouse-v2\ai_trading_bot-0.1.0-py3-none-any.whl`;
- length: 674,463 bytes;
- SHA-256: `7c5f44bd2ef28992334094ef46e8b2f5ddd8c502d7086bb4a44d66bf8133edb9`;
- 192 wheel entries / 191 hashed RECORD payloads;
- exact `trading_bot` package payload matched the certified Git export byte-for-byte;
- wheel path/topology checks passed with zero forbidden entries;
- distribution metadata verified as `ai-trading-bot` 0.1.0, Python `>=3.12`, `py3-none-any`, runtime dependency `tzdata<2027.0,>=2024.1`, optional extras `dev` and `optimization-cpu`;
- production SQL remained 118,896 bytes with the frozen SHA-256.

Administrator deployment is accepted:

- elevated identity `DESKTOP-I4DOKM7\John` confirmed administrator;
- exact accepted wheel length/SHA re-proved immediately before install;
- production runtime quiescent: zero fixed-runtime Python processes;
- runtime root owner remained Administrators and the prior exact Trading RX publication was present;
- Trading RX was removed and no Trading ACE remained anywhere in the runtime during replacement;
- offline/no-index/no-deps/no-cache force-reinstall succeeded;
- all 191 hashed wheel payloads matched the accepted wheel after installation;
- installed RECORD topology remained 380 rows: 192 wheel rows plus 188 pip extras, consisting of 185 `.pyc`, `INSTALLER`, `REQUESTED`, and `direct_url.json`;
- package imported from `F:\AITradingBot\runtime\Lib\site-packages\trading_bot`;
- E3.3 HTTP exception hierarchy, E3.5 safe provider-code extraction, E3.5 operator HTTP evidence fields, and `HTTP_FAILED` child classification passed installed-runtime smoke checks;
- production SQL remained frozen at 118,896 bytes / `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`;
- SQLite remained 3.50.4;
- read-only production authority validation returned `VALIDATED`, `INITIALIZED_SUPPORTED`, and exact Trading SID `S-1-5-21-1397534616-3988210162-180023805-1009`;
- owner normalization processed 12,454 files with zero failures;
- final runtime root owner is Administrators SID `S-1-5-32-544`;
- final sealed root ACL contains only SYSTEM and Administrators, both inheritable Full Control;
- 12,453 descendants inspected with zero ACL anomalies and no Trading ACE remaining;
- no network operation, Credential Manager read, production child launch, or provider request occurred.

Trading RX republication is accepted:

- runtime remained quiescent with zero fixed-runtime Python processes;
- pre-publication root remained protected and owned by Administrators;
- exact pre-publication root ACE set was SYSTEM + Administrators only;
- root publication became exactly three ACEs: SYSTEM Full Control, Administrators Full Control, Trading inheritable Read & Execute;
- root owner remained Administrators SID `S-1-5-32-544`;
- all 12,453 descendants inherited exactly one Trading RX ACE;
- zero RX topology anomalies were found;
- no provider request occurred.

The non-admin Trading E3.5 zero-provider preflight is accepted:

- identity exactly `DESKTOP-I4DOKM7\Trading` / expected SID;
- token non-administrator;
- fixed runtime Python and installed package location verified;
- E3.3 HTTP exception hierarchy preserved;
- non-200 missing/`text/plain`/`text/html` Content-Type handling accepted without losing the known HTTP-status path;
- HTTP 200 Content-Type diagnostics verified for missing Content-Type, unsupported media type, unsupported charset, invalid parameter form, plus a valid JSON positive control;
- safe optional provider-code extraction passed malformed/type/range cases;
- operator `http_status` / `provider_request_id` fields and `HTTP_FAILED` classification verified;
- production SQL remained frozen at 118,896 bytes / exact SHA-256;
- runtime write was blocked under Trading;
- production temp write/read/delete probe passed and cleaned;
- no Credential Manager read;
- no network operation;
- no production child launch;
- no authority database mutation;
- no provider request.

**The complete E3.5 deployment + Trading zero-provider preflight checkpoint is accepted.**

## E3.6 `/v2` credential-reference rotation — accepted through local credential proof

Architecture 84 moved new C3 production credential references from `/v1` to fixed `/v2` targets with no runtime selector or fallback. Architecture 84A narrowly permits pairwise `/v2` restaging only before the first `/v2` provider effect; after the first `/v2` provider effect, `/v2` becomes immutable and later rotation requires a new credential-reference version.

Accepted E3.6 source:

- commit: `41de33d3ef8ca22a6418146a6302969e11bbacc1`;
- tree: `44946d941f698c7290f43e47792e667443668055`;
- final regression: 3,177 passed, 16 skipped, 0 failed;
- Ruff check passed on `src tests`;
- Ruff format check passed across 338 source/test Python files;
- `git diff --check` passed;
- production `/v1` credential references under `src/trading_bot` were absent;
- frozen production SQL remained exact.

Accepted E3.6 artifact:

- source export: `F:\AI\c3-e36-production-source-v1`;
- rejected failed build wheelhouse: `F:\AI\c3-e36-production-wheelhouse-v1` with zero wheel files;
- accepted wheel: `F:\AI\c3-e36-production-wheelhouse-v2\ai_trading_bot-0.1.0-py3-none-any.whl`;
- length: 674,468 bytes;
- SHA-256: `98971acb4809fc7c5b4286771f64dee55349f083a188086ba5d2c78cd5301a21`;
- 192 wheel entries / 192 RECORD rows / 191 hashed payloads;
- 188 package source files matched the certified export exactly;
- zero forbidden entries;
- installed production credential contract contains only `/v2` values.

Administrator deployment, Trading RX republication, and corrected non-admin zero-provider preflight are accepted:

- fixed runtime now contains `windows-credential-manager-alpaca-market-data/v2` and the exact two `/v2` targets;
- `/v1` production fallback is absent and public credential override parameters are absent;
- production SQL remains 118,896 bytes with the frozen SHA-256;
- SQLite remains 3.50.4;
- authority validation remained `VALIDATED / INITIALIZED_SUPPORTED` under the administrator gate;
- Trading RX topology is exact across all 12,453 descendants;
- Trading-side signed bootstrap verification binds the exact approved SID;
- Trading-side production database inspection was read-only with `total_changes=0`;
- runtime writes were blocked under Trading and production temp remained usable;
- no Credential Manager read, network request, production child launch, authority mutation, or provider request occurred during deployment/preflight.

Credential staging under the exact non-admin Trading SID then produced one superseded `/v2` pair before any `/v2` provider effect. Architecture 84A classified that first pair `SUPERSEDED_BEFORE_FIRST_PROVIDER_EFFECT`, required both targets to be deleted together, and required all witness gates to be repeated. Restaging subsequently passed:

- superseded key and secret fingerprints matched the known abandoned pair before deletion;
- both `/v2` targets were deleted and independently proved absent;
- one replacement Alpaca **Paper** key generation was captured through interactive hidden input;
- replacement key ID and secret readback reproduced the dashboard-side domain-separated fingerprints and UTF-8 lengths exactly;
- credential type `Generic` and persistence `LOCAL_MACHINE` passed;
- dashboard was refreshed/revisited and the replacement key remained current;
- `FRESH_GENERATED=PASSED`;
- `LOCAL_EXACT_MATCH=PASSED`;
- `DASHBOARD_CURRENT=PASSED`;
- `/v2` real-provider effect count remains zero;
- no provider/network request occurred during staging/restaging.

**The E3.6 source/artifact/deployment/zero-provider/credential-local-proof checkpoint is accepted.** At that checkpoint the current `/v2` pair was frozen for its first future `/v2` provider effect. Call #5 subsequently used that pair; the first `/v2` effect permanently closed the Architecture 84A staging/restaging window. The `/v2` targets are now immutable historical credential-reference state and must not be regenerated, replaced, deleted, restaged, or modified. Any later credential rotation requires `/v3` or a later explicitly reviewed version.

## C3-E3.7 Windows publication repair and provider call #5 — accepted

E3.7 implementation:

```text
commit: 137bbe5a83d3bfe1cb62c381026c25e7fefa739a
message: fix: repair C3 Windows artifact publication
```

The implementation replaced the invalid `SetFileInformationByHandle` /
`FileLinkInfo` publication path with documented `CreateHardLinkW` no-clobber
publication while preserving retained staging identity verification, casefold
collision rejection, final reopen identity verification, exact-byte
reverification, and authority issuance only after successful parent
verification. The E3.7 Windows publication acceptance gate passed: **1
passed**.

Provider call #5 was the first real `/v2` provider effect. Calls #1–#4 are
historical `/v1` lineages. The accepted call-#5 lineage and terminal evidence
are:

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
the child successfully obtained the daily snapshot. Failure occurred after
the confirmed provider effect during local parent artifact publication. Call
#5 is permanently consumed and must never be retried. E3.7 repaired and
deployed the publication defect exposed by this lineage.

Final repository source certification was accepted:

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
re-proved before installation. The production runtime Python process count
was 0; Trading RX was revoked before replacement; the offline/no-index/no-
deps/no-cache force reinstall succeeded; all 191 hashed wheel payloads
matched; the installed E3.7 `CreateHardLinkW` publication implementation was
verified; the obsolete `FileLinkInfo` path was absent; production SQL
remained exact; SQLite remained 3.50.4; and production authority validation
returned `VALIDATED / INITIALIZED_SUPPORTED`. The bootstrap digest was
`53b8b72ab18b1c477c5eab50857e4dc2d47efc6e74030e380ed6a53387922ae4`; the
exact Trading SID remained approved. Ownership normalization processed
12,454 files with 0 failures; 12,453 descendants were inspected; ACL
anomalies were 0; and the sealed runtime before RX publication contained only
SYSTEM and Administrators.

Trading RX republication was accepted with the runtime quiescent, the root
owner still Administrators, the root DACL protected, exact inheritable Trading
Read & Execute restored, all 12,453 descendants passing RX topology, and
Trading RX anomalies at 0.

The non-admin Trading E3.7 zero-provider preflight was accepted:

```text
identity: DESKTOP-I4DOKM7\Trading
SID: S-1-5-21-1397534616-3988210162-180023805-1009
administrator: False
credential policy: windows-credential-manager-alpaca-market-data/v2
key target: AITradingBot/MarketData/Alpaca/ApiKeyId/v2
secret target: AITradingBot/MarketData/Alpaca/ApiSecretKey/v2
/v1 fallback: absent
E3.7 publication runtime proof: passed
signed bootstrap verification: passed
production database inspection: read-only
durable session count: 5
call #5 digest mapped exactly to its expected session
SQLite total_changes: 0
runtime write: blocked
production temp read/write/delete: passed
```

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

## C3 final controlled production acceptance — COMPLETE / ACCEPTED

C3 is **FULLY COMPLETE / ACCEPTED** at final source head
`82ba29ae2c2cc6bb3544077db0ee21868e6d5693`. This closeout records the final
controlled production evidence without changing Architecture 82 or any source,
test, schema, credential, deployment, or runtime artifact.

The accepted source/release context is:

- accepted E3.7 source repair: `137bbe5a83d3bfe1cb62c381026c25e7fefa739a`;
- frozen production SQL: 118896 bytes, SHA-256
  `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`;
- accepted production wheel: `ai_trading_bot-0.1.0-py3-none-any.whl`,
  674358 bytes, SHA-256
  `b35bbe0adc8f55ea96cc9f9e1852015182d07ed32b98d86cc141129395e431d2`;
- broad source regression: 3186 passed, 17 skipped;
- Ruff, format, and diff checks were accepted.

The dedicated production identity was `DESKTOP-I4DOKM7\Trading`, SID
`S-1-5-21-1397534616-3988210162-180023805-1009`, and it was non-administrator.
The `/v2` credential references are immutable historical production inputs. They
must not be deleted, overwritten, restaged, or rotated in place; a future
credential rotation requires a separately reviewed `/v3` or later version.

Historical call #5 remains permanently consumed historical evidence. Its request
digest was
`c33949931607552c6f06503fadf818972fb4fe153dd2a65a21970e5e879a435e`; its durable
terminal remains `FAILED / CONFIRMED` after parent publication failed following a
successful child/provider path. It is not successful and is not retryable.

Final controlled production call #6:

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
artifact_sha256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact_byte_length: 1291
status: COMPLETED
terminal_state: SUCCEEDED
provider_call_disposition: CONFIRMED
exit_code: 0
```

The final read-only durable proof was:

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

The final artifact/offline proof was:

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

Pre-effect evidence for call #6 confirmed the exact production runtime,
validated production authority and frozen schema digest, immutable `/v2`
credential entries readable under the Trading SID, the corrected E3.7
`CreateHardLinkW` implementation, absence of the obsolete `FileLinkInfo` path,
a passing same-filesystem publication canary, empty capture output, zero prior
durable lineage, and no provider/network operation during preflight.

This satisfies Architecture 82's stronger completion criterion: one C1-approved
Trading process caused at most one C2-authorized provider attempt; secrets
remained in the contained child on the production effect path; C2 durable
process/resume fences governed the effect; the parent independently verified and
published the canonical artifact; the successful terminal was durably selected;
and independent post-run offline verification passed. C3 completion is not
merely that Alpaca HTTP worked.

Total actual C3 real-provider effects are now **exactly 6**. All six are
consumed, call #6 is successful and consumed, and no provider call #7 is
authorized.

C3 authorizes only the reviewed market-data capture path. It does not authorize
brokerage credentials, broker reconciliation, order submission/cancel/replace,
real-money trading, unattended scheduling, automatic retry, automatic recovery,
or paper-account mutation. Production brokerage and live trading remain
**NO-GO**.

The next product milestone is the reliable manually invoked paper cycle:

```text
verified C3 snapshot
-> strategy
-> proposals
-> deterministic risk
-> paper execution
-> durable before/after evidence
```

This closeout does not design that milestone in detail and does not select a new
architecture for it.

## GUI track status

The GUI track is integrated through GUI-A7 in this combined source tree. It
remains a presentation/operator layer that must consume reviewed
application/service boundaries rather than becoming an alternative trading,
authority, credential, or recovery engine.

### GUI-A1 through GUI-A4

Accepted GUI foundations include:

- native PySide6 application shell and stable navigation;
- Qt-free presentation/service contracts;
- explicit read-only local research-report loading;
- bounded research result table presentation;
- deterministic sorting/filtering and report replacement behavior;
- read-only comparison of two to four research variants;
- bounded comparison tables/charts with truthful return/drawdown/turnover semantics.

### GUI-A5 — paper-operation inspection: ACCEPTED

Architecture 91 defines a strictly read-only GUI boundary for one exact
paper-operation inspection result.

Accepted implementation sequence:

- `26833e8326f6cffef2c638543fb3174f1984e85f` — define Architecture 91 and Qt-free paper presentation/service contracts;
- `b3cdce458a1f884f6d25b6fa82039cc1b31e1015` — formatting-only follow-up;
- `bb057bc6864c4f340fa05651a4a63245ee491854` — add the concrete Qt-free read-only paper inspection adapter;
- `fbf8fcb8068fff394bb1b144d1fdddbf3c50e06f` — render the bounded Paper page in Qt;
- `86f1308dad98e763856fcf5c8504bff26804baf9` — update the older GUI-A2 research test fixture for the expanded GUI service contract;
- `6f1945172a6e8dad46327a0212c6bce0fac68256` — update the older GUI-A4 comparison test fixture for the expanded GUI service contract.

GUI-A5 accepted behavior:

- presentation scope is exactly one explicit inspected paper-operation root, not history/account/fill/order discovery;
- classifications are limited to `PENDING`, `ALREADY_APPLIED`, `CONFLICTING`, and `BLOCKED`;
- the presentation diagnostic vocabulary mirrors the reviewed closed inspection codes;
- the concrete adapter receives one explicit operation root and already-verified `VerifiedPaperOperationInputs`;
- GUI widgets do not construct paper-operation authority or enumerate arbitrary roots;
- inspection/adaptation failures collapse to bounded sanitized `UNAVAILABLE` state without raw exception text;
- `MainWindow` obtains the paper state once during construction; navigation does not reinspect;
- the Paper page renders classification, diagnostic, operation/checkpoint/application UUIDs, and optional bounded receipt path only;
- service-derived text is forced to literal Qt plain text;
- there are no execute/run/retry/resume/recover/cancel/refresh/open-receipt or other mutation/effect controls;
- no paper execution, filesystem history scan, production SQLite, C1/C2/C3, Credential Manager, Alpaca, brokerage, scheduler, or production-child path is connected.

Final GUI-A5 acceptance evidence at
`6f1945172a6e8dad46327a0212c6bce0fac68256`:

- targeted compatibility regression: 2 passed;
- complete GUI suite: 93 passed;
- manual visual gate: PASSED for both unavailable and populated read-only Paper presentation;
- complete repository regression: 2,822 passed, 13 skipped, 0 failed;
- Ruff check on `src tests`: passed;
- Ruff format check on `src tests`: 342 files already formatted;
- `git diff --check`: clean;
- final GitHub compare from A5b2 to accepted head: exactly 2 commits, 2 test files, 8 added lines, zero production-source changes;
- known unrelated generated/untracked artifacts and historical permission-warning directories remained untouched.

**GUI-A5 is fully ACCEPTED.**

### GUI-A6 — offline-verified market-snapshot inspection: ACCEPTED

Architecture 92 defines a strictly read-only Market Data presentation boundary
for one exact local daily-snapshot artifact that has passed the existing offline
snapshot verifier. The GUI does not claim that this artifact is the active
production C3-selected snapshot.

Accepted checkpoint sequence:

- `994fa3b6f452cb004d842aaa7f59166c6b1c4d4b` — define Architecture 92;
- `fd04e40cb1fa9af294e8fe1181446b66f614a715` — add the GUI-A6 validation plan;
- `3885e0c6e4e576e647e656401891c1a25e7c2d54` — accepted A6a Qt-free presentation/service contract;
- `e98b84bdb42066ef03593f3134b42dadf520f200` — accepted A6b1 explicit-path offline verification adapter;
- `f4015e4adefba123c7f3c1f1ee5df70158f6a9db` — accepted A6b2 native Qt Market Data rendering source.

GUI-A6 accepted behavior:

- presentation scope is exactly one explicitly supplied local daily-snapshot artifact;
- the adapter performs one bounded read of that exact artifact and calls the existing `verify_daily_snapshot(...)` verifier exactly once per state acquisition;
- only a complete verifier `PASS` becomes `VERIFIED` GUI state;
- verifier PASS proves canonical snapshot serialization, XNYS calendar/session consistency, complete requested-symbol coverage, canonical accepted-bar evidence, audit hash, deterministic snapshot identity, and optional artifact SHA-256/byte-length evidence;
- the bounded presentation exposes only snapshot/session identity, retained symbol order, provider identity/operation/feed, artifact digest/size, capture/provider-as-of timestamps, and retained source-payload digest/size/media type;
- read, parse, verification, model, calendar, or adaptation failures collapse to sanitized `UNAVAILABLE` state without raw exception or diagnostic-detail text;
- the adapter does not enumerate directories or choose a "latest" artifact;
- `MainWindow` obtains Market Data state once during construction; navigation does not reread or reverify;
- service/model-derived Qt text is forced to literal plain text;
- there are no Capture/Refresh/Retry/Reverify/Select/Publish/Recover/database/credential/provider controls;
- no network, Alpaca transport, environment credential, Windows Credential Manager, production SQLite, C1/C2/C3 capability, capture, paper execution, strategy, risk, or artifact mutation path is connected;
- `VERIFIED` means offline verification of the supplied artifact only; it does not mean C3 selected the artifact, that it is newest, or that a capture is authorized.

Final GUI-A6 acceptance evidence at
`f4015e4adefba123c7f3c1f1ee5df70158f6a9db`:

- A6a contract gate: 8 passed;
- A6a+A6b1 focused gate: 16 passed;
- A6b2 focused Qt gate: 24 passed;
- complete GUI integration suite: 114 passed;
- manual visual gate: PASSED for both unavailable and populated verified Market Data presentations;
- complete repository regression: 2,843 passed, 13 skipped, 0 failed;
- all 13 skips are the repository's expected Windows opt-in/symlink environment skips;
- Ruff check on `src tests`: passed;
- Ruff format check on `src tests`: 348 files already formatted;
- `git diff --check`: clean;
- final GitHub compare from accepted A5 closeout `a5f5b91efe855e5b2e4e11898e950733001ff10f` to A6 source head: 24 commits, 16 files, all within Architecture 92/A6 presentation, adapter, Qt rendering, validation, and stale GUI test-fixture compatibility scope;
- no C3/runtime authority, provider credential, production SQLite, strategy, risk, order, or brokerage source changed;
- known unrelated generated/untracked artifacts and historical permission-warning directories remained untouched.

**GUI-A6 is fully ACCEPTED.**

### GUI-A7 — offline-verified paper-account state: ACCEPTED

Architecture 93 defines a common, strictly read-only presentation boundary for one explicitly supplied, completely offline-verified simulated paper-account checkpoint. The page does not identify the operationally current account, select a latest checkpoint, or add an operational account-selection boundary. The GUI-A7 validation plan is the frozen contract at the validation checkpoint below.

Accepted checkpoint sequence:

- `7b9067d204954ceef16531cff669dee43d1c094b` - Architecture 93;
- `17deebb5a47995629925d0890eda49b41a6ab6f7` - GUI-A7 validation plan;
- `6a333ff16f289990bbb870d857496cec17c0e847` - A7a final common presentation contract;
- `2bcb2d8770cbd80b801d54cb71e3013b14da4f79` - A7b1 GENESIS inspection adapter;
- `8bb1ebab1d28d337460c41549dfaa2d757317f0a` - A7b2 successor-edge inspection adapter;
- `b108a039251fbd37baeb0b6931e1fdd4b1c8877c` - A7b3 Qt Paper Account page;
- `91dad3cbe98c9d02097adba7a0cd8ab2d4736e9a` - A7b3 visual-table refinement;
- `7fb2e0b014938215e9ab4fbdb1cddde2651fad92` - final Ruff-format-only follow-up and accepted head.

Accepted architecture and behavior:

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

Final GUI-A7 acceptance evidence at `7fb2e0b014938215e9ab4fbdb1cddde2651fad92`:

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

GUI-A7 is fully ACCEPTED at final head `7fb2e0b014938215e9ab4fbdb1cddde2651fad92`. Any subsequent GUI milestone remains a separate architecture/planning decision; this closeout selects no GUI-A8 architecture.

## Consumed real-provider lineages

### August 21, 2026

- session: `4667f0a1-8890-57b9-ae07-98ffc9633ade`
- attempt ordinal: 0
- terminal: `FAILED`
- provider disposition: `CONFIRMED`
- child classification: `TRANSPORT_FAILED`
- consumed request digest: `823e9bee88de07bbd6d3384559dd6207ad216e69d46443594f8664fff49854a7`

The duplicate deterministic invocation was blocked before new attempt allocation. This lineage must never be retried.

### August 24, 2026

Fresh request digest:

`ed4cc49dc385486ac5ca623f64e99766247e371c90f29f1ff8fd585841d6b651`

Lineage:

- session: `c78b94a4-963f-5197-9a03-16017ea2203b`
- attempt: `e1a74104-150c-5ef9-96f3-f9d6d0c8aee0`
- claim: `2fa4aa8b-b571-5051-b48b-19a658b4fe3b`
- reservation: `4d49805d-661b-53b2-a8df-ba041323da2f`
- execution: `5acd937c-35b4-5e68-87cd-afc781872176`
- terminal: `b4c34eec-81d4-5dad-b01a-34d88fca05d4`
- terminal state: `FAILED`
- provider disposition: `CONFIRMED`
- child classification: `TRANSPORT_RESPONSE_METADATA_FAILED`
- selection/snapshot/artifact: none

Read-only diagnostics confirmed provider fence entered, complete result transport, process exited zero, complete parent/staging cleanup, valid evidence/diagnostics digests, and `POST_FENCE_CHILD_FAILURE`. The exact rejected metadata condition is not recoverable from the consumed E3.3 lineage. This lineage must never be retried.

### August 25, 2026

Pure planning after the New York-date rollover authorized session `2026-08-25` with fresh request digest:

`b41a85c7b907ccd2a687d9f832d72a85cf152db46c85eaf9665809635ce9674b`

Pre-effect durable freshness was zero. Exactly one real provider effect then produced:

- session: `2420ce3f-4395-504a-8bd6-995fe87055db`
- attempt: `0cebdb94-0a83-5b46-ac43-979dfc98b168`
- claim: `7e57b5ee-5ce8-55e6-93f9-62e8f6ab4b4d`
- reservation: `2dfc0505-f1ad-5b07-b455-c47364e82bf7`
- execution: `33d5ec52-1bae-5cdb-bb20-7e707cdcf039`
- terminal: `96dc59fb-f393-5033-beba-ea78470d12ea`
- terminal state: `FAILED`
- provider disposition: `CONFIRMED`
- child classification: `TRANSPORT_RESPONSE_METADATA_CONTENT_TYPE_FAILED`
- selection/snapshot/artifact: none

Read-only durable diagnostics confirmed provider fence entered, child request/result transport complete, process exited zero, parent/staging cleanup complete, artifact verification not attempted, evidence/diagnostics digests valid, and terminal reason `POST_FENCE_CHILD_FAILURE`. E3.4 therefore succeeded in narrowing the prior broad metadata failure to Content-Type validation. This lineage is permanently consumed and must never be retried.

### August 26, 2026

Pure planning after the New York-date rollover authorized session `2026-08-26` with fresh request digest:

`cccf56d1361ee4df8cf34745f68b32b29c52efdaaa80d2a02d4a32323dedce7f`

Pre-effect durable freshness was zero across `sessions`, `attempts`, `provider_call_claims`, `launch_reservations`, and `terminals`. Exactly one explicitly authorized provider effect then produced:

- session: `32b6765f-d1ae-5d11-81df-b95e82178edf`
- attempt: `c19975b6-10b4-5893-93a2-aca92e606229`
- claim: `fa184f7f-85bd-5830-bb96-70ae334a2d2e`
- reservation: `995883d2-bdc4-5909-9e35-b4e8343beab7`
- execution: `71ebf7dc-aaf4-504c-a15c-33c7b2afd6bb`
- terminal: `67defd53-e6b2-5f6e-945e-de51b5846962`
- terminal state: `FAILED`
- provider disposition: `CONFIRMED`
- child classification: `HTTP_FAILED`
- HTTP status: `401`
- provider request ID: `1a57fe61031771fc4b0f818c84f9e6e0`
- selection/snapshot/artifact: none

Read-only durable inspection verified the exact lineage and request digest, attempt/reservation/execution terminal states, provider-call budget 1, provider fence `ENTERED`, complete result transport, `EXITED_ZERO`, complete parent and staging cleanup, valid post-resume/cleanup/terminal evidence digests, terminal evidence schema 2, `artifact_verification=NOT_ATTEMPTED`, terminal reason `POST_FENCE_CHILD_FAILURE`, zero selection rows, exactly four durable sessions total, and SQLite `total_changes=0` during inspection. E3.5 therefore succeeded in preserving the concrete provider HTTP failure that E3.4 previously exposed only as a Content-Type metadata classification. This historical lineage is permanently consumed and must never be retried.

The August 26 provider-effect count was historical evidence for calls #1-#4.
Call #5 was then consumed as the first `/v2` effect. The final controlled call #6
is recorded in the C3 acceptance section above, and the current total is now
exactly 6.

## Historical pre-call #6 planner and review state (superseded)

The planner used exchange-local **calendar-date** reconciliation. Its freshness
check was pure and read-only, with no Credential Manager read, network/provider
request, production child launch, or authority mutation. That historical gate
was superseded by the separately authorized final call #6 documented above.

Call #5 used the fresh XNYS request window `2026-08-27` and target session date
`2026-08-28`; that failure lineage remains consumed and is not a retry
candidate. The final call #6 used a distinct request digest, exact session
mapping, and zero durable lineage before effect.

## Post-C3 boundaries and next product milestone

C3 completion does not authorize unattended operation. Follow-up boundaries
outside C3 include authoritative scheduling, startup reconciliation, crash
recovery, health/alerts, stale or missing-data handling, and the selected
verified snapshot to paper-operation bridge. The next product milestone is the
reliable manually invoked paper cycle shown above; it must remain separately
reviewed and does not mutate C3 authority or paper-account state in this
closeout.

---
## Roadmap after C3

1. **Reliable manual paper cycle** — selected parent-verified snapshot -> strategy -> proposals -> deterministic risk -> paper execution -> durable evidence.
2. **Unattended paper operation** — authoritative scheduling, startup reconciliation, crash recovery, health/alerts, stale/missing-data fail-closed behavior.
3. **Long paper soak** — extended unattended operation to expose real operational problems while consequences remain simulated.
4. **Broker-paper integration** — account/position reads, submit/cancel/replace, broker/fill IDs, partial fills/rejects, reconciliation, idempotency, ambiguous-submit recovery.
5. **Live-readiness certification** — explicit mode authority, separate live credentials, exact account verification, strict limits, kill switch, outage/halt handling, startup reconciliation, operator-visible state.
6. **Tiny restricted live** — deliberately small long-only real-money deployment only after live-readiness acceptance.
7. **Mature operations / deeper AI / polished GUI** — AI remains subordinate to deterministic validation, authority, risk, brokerage, reconciliation, and operator controls.

## Stable product constraints

- US stocks and ETFs;
- long-only;
- no margin or leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability.

## Documentation workflow

At every accepted development checkpoint, review and update both:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

The Git-tracked pair is authoritative. Project-uploaded copies are context mirrors only. Documentation closeout does not authorize merging, rebasing, force-pushing, amending, resolving review threads, changing PR metadata, or modifying unrelated files.
