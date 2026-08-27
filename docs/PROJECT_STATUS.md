# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot. The canonical cross-chat handoff is `docs/AI_TRADING_BOT_HANDOFF.md`; detailed architecture documents remain authoritative for subsystem contracts and historical decisions.

## Long-term objective

Build a conservative automated trading platform that can progress safely from deterministic historical research to simulated paper trading, unattended paper operation, broker-paper operation, restricted live trading, and finally a polished end-user application.

**Production/live trading: NO-GO.** Live trading remains unavailable until separately reviewed safety, credential, brokerage, reconciliation, operator-control, and acceptance gates are complete.

## Current milestone: C3 effectful market-data capture

C1 `ValidatedProductionAuthority` and C2 `WindowsTransactionalAuthority` are reviewed foundations. C3 is the only reviewed bridge from C1/C2 authority into real market-data credentials, native Windows child execution, Alpaca transport, staged capture, independent parent verification, publication, and snapshot selection.

C3 is **not yet complete** because no real provider lineage has produced a parent-verified selected production snapshot.

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
14. E3.5 preservation of non-success HTTP status across safe Content-Type variation, durable sanitized HTTP evidence, and stricter successful-response Content-Type diagnostics.

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
- Credential targets:
  - `AITradingBot/MarketData/Alpaca/ApiKeyId/v1`
  - `AITradingBot/MarketData/Alpaca/ApiSecretKey/v1`
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

## Parallel GUI track: GUI-A5b2 paper inspection rendering accepted

The GUI remains isolated on `feature/gui-foundation` and separate from the frozen C3 production branch. GUI-A1 through GUI-A4 and GUI-I1 remain integration-certified; GUI-A5 extends the Paper page through a strictly read-only inspection boundary and bounded native Qt rendering.

Accepted GUI-A5 sequence:

- `26833e8326f6cffef2c638543fb3174f1984e85f` — define Architecture 91 and the Qt-free paper-operation presentation/service contracts;
- `b3cdce458a1f884f6d25b6fa82039cc1b31e1015` — Ruff-only formatting correction for GUI-A5a;
- `bb057bc6864c4f340fa05651a4a63245ee491854` — add the Qt-free concrete `PaperOperationInspectionService` adapter;
- `fbf8fcb8068fff394bb1b144d1fdddbf3c50e06f` — render the bounded Paper inspection state in the native Qt page.

GUI-A5 acceptance facts:

- Architecture 91 preserves the existing reviewed `inspect_paper_operation_root(...)` scope: one exact operation only, not history/account/fill/order discovery;
- presentation classification is limited to `PENDING`, `ALREADY_APPLIED`, `CONFLICTING`, or `BLOCKED`, and mirrors the closed reviewed diagnostic vocabulary exactly;
- `GuiApplicationService.get_paper_state()` is Qt-free and presentation-only;
- the concrete adapter receives one explicit operation-root `Path` and already-verified `VerifiedPaperOperationInputs`; GUI code does not construct or derive those inputs;
- the adapter calls the reviewed inspector exactly once, preserves operation/checkpoint/application UUIDs and optional receipt path, and maps classification/diagnostic by exact enum value;
- unexpected result types, unknown future enum values, oversized receipt-path presentation, and inspection/adaptation exceptions fail to a bounded sanitized `UNAVAILABLE` state without raw exception text;
- the Qt Paper page obtains one bounded state during `MainWindow` construction; navigation away/back performs no reinspection or other effect;
- inspected fields render classification, diagnostic, operation/checkpoint/application UUIDs, and optional receipt path only; absent receipt path is represented neutrally as `Not retained`;
- all service/model-derived labels are forced to `Qt.TextFormat.PlainText`, including HTML-looking message/path values;
- the Paper page contains no execute/run/retry/resume/recover/cancel/refresh/open-receipt or other mutation/effect controls;
- no paper execution, filesystem history scan, production SQLite, C1/C2/C3, Credential Manager, Alpaca, brokerage, scheduler, or production-child path is connected;
- GUI-A5a focused gate: 9 passed; Ruff check/format and `git diff --check` passed after the formatting-only follow-up;
- GUI-A5b1 focused GUI-A5a/A5b1 gate: 35 passed; Ruff check/format and `git diff --check` passed;
- GUI-A5b2 final focused gate: 47 passed; Ruff check/format and `git diff --check` passed;
- GitHub exact-diff review confirmed the A5b2 four-file Qt change including the inspected-detail panel construction.

**GUI-A5a, GUI-A5b1, and GUI-A5b2 are accepted.** The next GUI checkpoint is the GUI-A5 integration/visual gate, followed by the full repository regression. That broader GUI certification remains deferred while C3 resumes.

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

Total real Alpaca provider effects: **exactly 3**.

## Planner clock contract and August 26 pre-effect gate

The planner contract is exchange-local **calendar-date** based. For completed session date `D`, planning reconciles only after the New York calendar date has advanced to `D + 1`. Merely waiting until market close plus a buffer is insufficient.

The August 26 pure-planning gate was run from the exact non-administrator Trading account after rollover at `2026-08-27T00:46:09.792299-04:00` New York time. It reproduced the consumed August 25 request digest exactly, then authorized the August 26 XNYS session and produced the fresh deterministic request digest:

`cccf56d1361ee4df8cf34745f68b32b29c52efdaaa80d2a02d4a32323dedce7f`

Independent read-only durable freshness validation found zero rows for that digest in `sessions`, `attempts`, `provider_call_claims`, `launch_reservations`, and `terminals`. Each of the three consumed request digests appeared exactly once in `sessions`, total durable session count remained 3, and SQLite `total_changes` remained 0. No Credential Manager read, network operation, production child launch, authority mutation, or provider request occurred.

**The August 26 pure planner + durable freshness gate is accepted.** The candidate digest is genuinely fresh relative to all three consumed lineages.

**Provider call #4 is still NOT authorized.** The pre-effect planner/freshness prerequisite is satisfied, but the external effect requires a separate explicit authorization decision.

## Immediate deep-review status

Completed deep reviews found no unsafe automatic retry path. E3.5 improves operator diagnosis for future HTTP failures by durably preserving sanitized non-200 status/request ID after terminal persistence. Follow-up work before unattended operation remains:

- some proven pre-effect continuation states are not directly resumable through the one-shot facade;
- production `close()` / concurrent admission-drain behavior;
- secret/transport-object lifetime;
- artifact verification/publication TOCTOU;
- SQL invariant mutation testing;
- clock/calendar authority for unattended scheduling;
- selected-snapshot to paper-operation bridge.

Any change to native Windows authority, credential lifetime, external-effect ordering, crash/recovery ambiguity, publication/selection authority, retry semantics, or planner clock semantics requires Sol High architecture review.

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