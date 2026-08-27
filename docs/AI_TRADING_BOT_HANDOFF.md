# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Local repository:** `F:\AI\ai-trading-bot`  
**Integration branch:** `develop`  
**Current architecture branch:** `feature/windows-effectful-market-data-capture`  
**Current release-source checkpoint:** `b0e94240291e59ee2214d639d096b4dc5cf7e094`  
**Handoff status:** August 27, 2026 — C3-E3.5 deployment and August 26 planner/freshness accepted; provider call #4 consumed as `FAILED / CONFIRMED / HTTP_FAILED / 401` with durable evidence; next C3 task is zero-provider credential/authentication diagnosis; provider call #5 is not authorized; parallel GUI-A5b2 read-only Paper rendering is accepted

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
Credential targets:
  AITradingBot/MarketData/Alpaca/ApiKeyId/v1
  AITradingBot/MarketData/Alpaca/ApiSecretKey/v1
Child env: SystemRoot,WINDIR,TEMP,TMP,PYTHONUTF8
```

Frozen production SQL:

```text
length: 118896 bytes
SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
```

---

## 4. C3 status

Completed foundations include immutable planning/identity, bounded parent/child protocol, exact Credential Manager/SID boundary, one-shot child/provider execution, suspended Windows process + Job Object containment, durable process/resume ordering, parent verification/publication/selection, manual production CLI, and E3.2–E3.5 transport diagnostics/hardening.

C3 is **not complete** because no real provider lineage has yet produced a parent-verified selected production snapshot.

E3.5 has now been exercised by a real provider failure and successfully converted the prior opaque Content-Type failure into durable sanitized HTTP evidence (`401` plus provider request ID) without creating a snapshot or selection.

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

Its deployment, Trading RX republication, and non-admin zero-provider preflight were accepted. It has now been replaced by the accepted E3.5 runtime described below.

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

**Total actual real-provider effects: exactly 4.**

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

## 8. E3.5 frozen artifact and full deployment — accepted

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

Offline artifact inspection accepted:

- exact `trading_bot` package payload matched the certified source export byte-for-byte;
- zero forbidden wheel entries;
- production SQL retained exact frozen bytes/digest;
- metadata verified as package `ai-trading-bot` version 0.1.0, Python `>=3.12`, `py3-none-any`, runtime dependency `tzdata<2027.0,>=2024.1`, optional extras `dev` / `optimization-cpu`.

Administrator deployment accepted:

- elevated administrator identity confirmed;
- exact accepted wheel length/SHA rechecked before installation;
- fixed runtime quiescent;
- exact prior Trading RX publication found, then fully revoked before install;
- zero Trading ACEs remained anywhere under the runtime during replacement;
- offline/no-index/no-deps/no-cache force-reinstall succeeded;
- all 191 accepted wheel payloads reconciled after installation;
- installed RECORD: 380 rows total, 188 accepted pip extras, 185 `.pyc`, plus `INSTALLER`, `REQUESTED`, `direct_url.json`;
- installed package imported from the fixed runtime;
- E3.3 HTTP hierarchy, E3.5 safe provider-code behavior, operator HTTP evidence fields, and `HTTP_FAILED` classification verified;
- production SQL remained 118896 bytes / frozen SHA-256;
- SQLite remained 3.50.4;
- read-only production authority validation returned `VALIDATED`, `INITIALIZED_SUPPORTED`, exact Trading SID;
- ownership normalization processed 12,454 files with zero failures;
- runtime owner is Administrators SID `S-1-5-32-544`;
- sealed root ACL initially contained only SYSTEM + Administrators, both inheritable Full Control;
- 12,453 descendants inspected with zero ACL anomalies;
- no network operation, Credential Manager read, production child launch, authority mutation, or provider request occurred.

Trading RX republication accepted:

- fixed runtime remained quiescent;
- pre-publication root remained protected and owned by Administrators;
- exact pre-publication ACE set was SYSTEM + Administrators only;
- final root ACL contains exactly SYSTEM Full Control, Administrators Full Control, and Trading inheritable Read & Execute;
- root owner remained Administrators SID `S-1-5-32-544`;
- all 12,453 descendants inherited exactly one Trading RX ACE;
- zero RX topology anomalies;
- no provider request occurred.

Non-admin Trading E3.5 zero-provider preflight accepted:

- identity exactly `DESKTOP-I4DOKM7\Trading` / SID `S-1-5-21-1397534616-3988210162-180023805-1009`;
- token non-administrator;
- fixed runtime Python and installed package location verified;
- E3.3 HTTP exception hierarchy preserved;
- E3.5 non-200 missing/`text/plain`/`text/html` Content-Type handling passed;
- successful-response Content-Type reason checks passed for missing Content-Type, unsupported media type, unsupported charset, and invalid parameters, with a valid JSON positive control;
- safe provider-code extraction passed bounded, malformed, type, and range cases;
- operator `http_status` / `provider_request_id` fields and `HTTP_FAILED` classification verified;
- production SQL remained exactly 118896 bytes with the frozen SHA-256;
- Trading runtime write probe was blocked;
- production temp write/read/delete probe passed and cleaned;
- Credential Manager read: false;
- network operation: false;
- production child launch: false;
- authority database mutation: false;
- provider request: false.

**The complete E3.5 deployment + Trading zero-provider preflight checkpoint is accepted.**

---

## 9. Planner clock contract and August 26 pre-effect gate

The planner uses exchange-local **calendar-date** reconciliation. For completed session date `D`, planning passes only once New York date has advanced to `D + 1`; market close plus an arbitrary buffer is not enough.

The August 26 pure-planning gate was executed from the exact non-administrator Trading account at:

```text
requested UTC:      2026-08-27T04:46:09.792299+00:00
requested New York: 2026-08-27T00:46:09.792299-04:00
authorized session: 2026-08-26
```

The historical August 25 request shape reproduced its consumed digest exactly:

```text
b41a85c7b907ccd2a687d9f832d72a85cf152db46c85eaf9665809635ce9674b
```

The fresh August 26 request digest was:

```text
cccf56d1361ee4df8cf34745f68b32b29c52efdaaa80d2a02d4a32323dedce7f
```

Independent read-only durable freshness validation found zero rows for that digest in all five lineage tables before call #4: `sessions`, `attempts`, `provider_call_claims`, `launch_reservations`, and `terminals`. Each of the three earlier consumed request digests appeared exactly once in `sessions`; total durable session count remained 3; SQLite `total_changes` was 0.

No Credential Manager read, network operation, production child launch, authority database mutation, or provider request occurred during the planner/freshness gate.

**The August 26 pure planner + durable freshness gate is accepted.** Changing the planner clock semantic still requires Sol High architecture review.

---

## 10. Current resume point / next acceptance gate

Provider call #4 is consumed and its durable inspection is accepted.

Current exact C3 effect state:

```text
actual real-provider effects: exactly 4
latest request digest: cccf56d1361ee4df8cf34745f68b32b29c52efdaaa80d2a02d4a32323dedce7f
latest terminal: FAILED
latest provider disposition: CONFIRMED
latest child classification: HTTP_FAILED
latest HTTP status: 401
latest provider request ID: 1a57fe61031771fc4b0f818c84f9e6e0
latest selection/snapshot/artifact: none
```

The durable evidence proves this was not ambiguous: provider fence entered, result transport completed, child process exited zero, parent/staging cleanup completed, evidence digests validated, and no selection exists.

The immediate next sequence is:

```text
zero-provider credential/authentication diagnosis
→ determine whether the provisioned Alpaca key pair is stale/revoked/mismatched or whether account/provider authorization is the issue
→ do not overwrite the existing /v1 Credential Manager entries in place
→ if rotation is required, review a versioned credential-reference/cutover design under Sol High
→ only after a reviewed cutover and a genuinely new session/digest may another provider effect be considered
```

The child credential reader already proved the two fixed `/v1` entries exist, are readable by the exact approved Trading SID, decode as accepted UTF-8 credential strings, and can be passed to the transport. The transport sent them in the exact `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` request headers to `data.alpaca.markets`; Alpaca then returned 401. This shifts the active investigation from transport framing/Content-Type to credential/account authorization.

**Provider call #5 is NOT authorized.** Do not retry the August 26 lineage.

Parallel GUI status: GUI-A5a/A5b1/A5b2 are accepted through `fbf8fcb8068fff394bb1b144d1fdddbf3c50e06f`. The native Paper page renders only the bounded read-only inspection state, uses plain-text presentation for service-derived data, contains no mutation/recovery controls, and does not re-inspect on navigation. The next GUI checkpoint is the GUI-A5 integration/visual gate followed by the full repository regression; it remains deferred while C3 authentication diagnosis is active.

---

## 11. Crash/recovery posture

No unsafe automatic retry path has been found. Conservative categories remain:

- pre-session/pre-attempt: no provider effect;
- process-intent around `CreateProcessW`: potentially ambiguous; manual classification required;
- proven NOT_CREATED: provider definitely not started but continuation remains explicit;
- PRE_RESUME_READY: child suspended, no provider effect;
- resume ambiguity: provider may have occurred; never retry automatically;
- post-resume durable states: manual durable recovery only;
- verified snapshot before terminal / terminal before selection: recover from durable authority without repeating provider effect.

E3.5 has now demonstrated in the real call #4 lineage that an `HTTP_FAILED` terminal retains sanitized non-200 status/request ID durably after terminal commit. These fields are diagnostic only and never grant retry authority.

The August 26 session remains `OPEN` with `next_attempt_ordinal=1`, but this is not provider-effect authorization. The normal one-shot CLI starts by creating the deterministic session; a same-request rerun encounters the already-existing deterministic session before normal attempt allocation. Any explicit recovery/continuation path remains separately reviewed authority and is not authorized here.

---

## 12. Remaining C3 / pre-unattended reviews

Before unattended production operation, continue review of:

- credential/account authorization and, if required, versioned credential rotation/cutover;
- production `close()` / concurrent admission and drain;
- secret and transport-object lifetime;
- artifact verification/publication TOCTOU;
- SQL invariant mutation testing;
- authoritative clock/calendar scheduling;
- selected-snapshot → paper-operation bridge;
- systematic top-level crash/fault matrix.

Native Windows authority, credential lifetime/reference version, external-effect ordering, crash/recovery ambiguity, publication/selection authority, retry semantics, and clock semantics require Sol High architecture review. Localized frozen-contract implementation may use Luna Extra High; subtle bounded implementation may use Sol Medium.

---

## 13. Roadmap after successful C3 acceptance

1. Reliable manual paper cycle — selected parent-verified snapshot → strategy → proposal → deterministic risk → paper execution → durable result.
2. Unattended paper operation — XNYS scheduling, startup reconciliation, recovery, health/alerts, stale/missing-data handling.
3. Long paper soak.
4. Broker-paper integration — account/positions, submit/cancel/replace, broker/fill IDs, partial fills/rejects, reconciliation, idempotency, ambiguous-submit recovery.
5. Live-readiness certification — explicit mode authority, separate live credentials, exact account verification, strict limits, kill switch, outage/halt handling, startup reconciliation, operator-visible state.
6. Tiny restricted live deployment.
7. Mature operations, deeper AI, polished GUI.

Stable initial live constraints: US stocks/ETFs, long-only, no margin/leverage/options/shorts/crypto, deterministic risk approval for every order, paper mode by default, complete auditability.

---

## 14. Development workflow

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

## 15. Files to read when resuming

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
```

Before any future provider effect, inspect the latest durable E3 lineage evidence and prove the candidate session/digest is genuinely new.

---

## 16. Definition of project success

The project succeeds when it can research deterministically, acquire trusted market data safely, make portfolio decisions under deterministic risk, interact safely with a brokerage, reconcile ambiguous outcomes, run unattended for long periods, fail closed on uncertainty, expose durable evidence and operator controls, operate under strict live limits, and present the same reviewed capabilities through a polished GUI.

The final system is a **safety-oriented automated trading platform in which AI is one replaceable decision-making component inside a deterministic operational and authority framework**.