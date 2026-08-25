# AI Trading Bot — Project Development Roadmap & Handoff

**Repository:** `callmedraken/ai-trading-bot`  
**Local repository:** `F:\AI\ai-trading-bot`  
**Integration branch:** `develop`  
**Current architecture branch:** `feature/windows-effectful-market-data-capture`  
**Current release-source checkpoint:** `134467ecda1ffbb39f48cf68a2d3e9017d1d2f61`  
**Handoff status:** August 25, 2026 — C3-E3.4 source-certified, frozen wheel accepted, fixed runtime deployed, Trading RX and non-admin zero-provider preflight accepted

> The Git-tracked `docs/AI_TRADING_BOT_HANDOFF.md` is the canonical handoff. Any uploaded Project copy is only a mirror. Because documentation closeout creates later docs-only commits, do not treat this file's commit SHA as the release-source SHA; verify live branch HEAD when resuming.

---

## 1. Product goal

Build a conservative automated trading platform that progresses through:

**historical research → deterministic simulation → manual paper → unattended paper → long paper soak → broker-paper → live-readiness certification → tiny restricted live → mature automated operation → polished GUI.**

The project is not intended to remain paper-only. Restricted real-money trading is a long-term goal, but strategy/AI must always remain subordinate to deterministic risk, production authority, credentials, brokerage/reconciliation, operating-mode controls, durable evidence, and operator emergency controls.

**Production/live trading remains NO-GO.**

---

## 2. Current architecture

Production market-data authority chain:

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

C2 alone remains effectfully inert. C3 is the only reviewed bridge into effectful market-data capture and does not authorize brokerage or live trading.

Core production ordering:

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
Trading account:
DESKTOP-I4DOKM7\Trading

Trading SID:
S-1-5-21-1397534616-3988210162-180023805-1009

Fixed runtime:
F:\AITradingBot\runtime\python.exe

Runtime directory:
F:\AITradingBot\runtime

TEMP/TMP:
F:\AITradingBot\temp

Capture output:
F:\AITradingBot\Authority\capture-output

Child command:
python.exe -m trading_bot.runtime.windows_effectful_capture_child

Credential targets:
AITradingBot/MarketData/Alpaca/ApiKeyId/v1
AITradingBot/MarketData/Alpaca/ApiSecretKey/v1
```

Child environment is fixed to `SystemRoot,WINDIR,TEMP,TMP,PYTHONUTF8`. Native API remains `CtypesWindowsEffectfulCaptureNativeApi`.

Frozen production SQL:

```text
length: 118896 bytes
SHA-256: aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58
```

---

## 4. C2 foundation

C2 final historical certification:

```text
combined service + Architecture-77: 775 passed
full repository: 2725 passed, 13 skipped, 0 failed
```

Architecture 77 and related Windows authority documents define durable claims/reservations/executions, one-shot capabilities, recovery semantics, ambiguous-effect handling, and fail-closed retry rules.

---

## 5. C3 implementation status

Completed C3 areas include:

- A1 immutable capture planning and deterministic identity;
- A2 canonical bounded child protocol;
- A3 C1/C2/C3 composition and verified capture authority;
- B1 exact Windows Credential Manager boundary;
- B2 isolated child/provider core;
- native suspended process + Job Object containment;
- exact inherited handles/environment;
- C2 process/resume ordering;
- bounded child result/process observation and cleanup;
- parent verification/publication/selection path;
- native acceptance probes;
- manual `production_daily_snapshot_capture` operator boundary;
- E3.2 closed sanitized transport-stage diagnostics;
- E3.3 truthful stage classification and separate HTTP-status semantics;
- E3.4 closed sanitized response-metadata sub-classifications.

C3 is **not complete** because no real provider lineage has yet produced a parent-verified selected production snapshot.

---

## 6. E3.3 checkpoint

E3.3 corrected broad transport catches so unexpected Python/programming defects escape expected transport boundaries and become sanitized child `INTERNAL_FAILED` evidence. `AlpacaHttpStatusError` remains a sibling of `AlpacaTransportError` under `AlpacaDailySnapshotError`.

Accepted source checkpoint:

```text
bf88890d87ed1734a4634e4b8069ff5232a20994
```

Certification:

```text
3094 passed, 16 skipped, 0 failed
Ruff check: pass
Ruff tracked-source format check: pass
```

Accepted E3.3 wheel:

```text
length: 672104
SHA-256: ed87fcce586a3b2f2477f2b99e6c404d7c42f5cc2ef29e230b12cd8ca7640b3b
RECORD: 192 rows / 191 hashes verified
```

The E3.3 runtime was deployed successfully before the August 24 provider effect. Trading RX and the non-admin zero-provider preflight passed. The earlier E3.3 v1 wheel is unaccepted and must never be reused.

---

## 7. Consumed real-provider lineages

### August 21, 2026 — permanently consumed

Exactly one real Alpaca effect:

```text
session: 4667f0a1-8890-57b9-ae07-98ffc9633ade
attempt ordinal: 0
terminal: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_FAILED
```

Consumed request digest:

```text
823e9bee88de07bbd6d3384559dd6207ad216e69d46443594f8664fff49854a7
```

The second identical CLI invocation was blocked before new attempt allocation and caused no provider effect or durable mutation. Never retry this lineage or manufacture a new digest by changing irrelevant fields.

### August 24, 2026 — permanently consumed

Pure planner eventually authorized snapshot `2026-08-24` with fresh digest:

```text
ed4cc49dc385486ac5ca623f64e99766247e371c90f29f1ff8fd585841d6b651
```

Exactly one real provider effect then produced:

```text
session:     c78b94a4-963f-5197-9a03-16017ea2203b
attempt:     e1a74104-150c-5ef9-96f3-f9d6d0c8aee0
claim:       2fa4aa8b-b571-5051-b48b-19a658b4fe3b
reservation: 4d49805d-661b-53b2-a8df-ba041323da2f
execution:   5acd937c-35b4-5e68-87cd-afc781872176
terminal:    b4c34eec-81d4-5dad-b01a-34d88fca05d4
terminal state: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_RESPONSE_METADATA_FAILED
selection: none
snapshot: none
artifact: none
```

Read-only durable diagnostics confirmed:

```text
child fence state: ENTERED
result transport: COMPLETE
process outcome: EXITED_ZERO
parent cleanup: COMPLETE
artifact verification: NOT_ATTEMPTED
staging cleanup: COMPLETE
terminal reason: POST_FENCE_CHILD_FAILURE
evidence digest: valid
diagnostics digest: valid
```

The exact rejected response-metadata condition is not recoverable from this consumed E3.3 lineage because E3.3 persisted only the broad metadata stage. Never retry this lineage.

**Total actual real-provider effects: exactly 2.**

---

## 8. E3.4 checkpoint — source certification

Purpose: retain all existing strict response/framing validation while making response-metadata failures decisively diagnosable through a closed sanitized reason set.

Frozen child classifications:

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

Accepted implementation commit:

```text
134467ecda1ffbb39f48cf68a2d3e9017d1d2f61
fix: classify Alpaca response metadata failures
```

Certified diff SHA-256:

```text
6d9232fef1f5dfaf8b1df329e28db20646d108a81b0e1410e2d2d9cd82cdbca6
```

Final certification:

```text
3136 passed, 16 skipped, 0 failed
Ruff check: pass
Ruff format --check: 358 files already formatted
final git diff --check: pass
```

Sol High exact-diff review found no production-code blocker. A final test-only follow-up proved validator-internal programming defects escape unchanged, the metadata-reason enum is closed, and arbitrary metadata-reason text sanitizes to `GENERIC`.

E3.4 does not change C1/C2 semantics, production SQL, Credential Manager behavior, endpoint/feed/query policy, one-shot provider budget, native process ordering, or retry authority.

---

## 9. E3.4 accepted frozen artifact

Frozen source export:

```text
source commit: 134467ecda1ffbb39f48cf68a2d3e9017d1d2f61
source tree: dcead824eee27b2e93a7391578ef1b321b595c06
```

Accepted wheel:

```text
F:\AI\c3-e34-production-wheelhouse-v1\ai_trading_bot-0.1.0-py3-none-any.whl
length: 673212 bytes
SHA-256: b7fdbabeb936c311eeae3509635ec57d40fa999e421dc4e9cd5afb8bbe0848db
```

Offline inspection passed:

- 192 wheel entries;
- only `trading_bot` and dist-info roots;
- zero forbidden entries;
- runtime dependency only `tzdata>=2024.1,<2027.0` plus declared optional extras;
- 192 RECORD rows / 191 hashed payload files;
- frozen production SQL unchanged;
- exact relevant source-file matches;
- exact E3.4 metadata reason/classification set;
- E3.3 HTTP hierarchy and standalone CLI handling preserved;
- no network, credential, child, or production-runtime effect.

---

## 10. E3.4 fixed-runtime deployment — accepted

Administrator deployment evidence:

```text
wheel identity: exact accepted E3.4 wheel
production runtime quiescent: yes
Trading RX revoked before install: yes
offline uninstall/install: success
package under fixed runtime: yes
```

Installed payload verification:

```text
accepted wheel RECORD rows: 192
verified wheel payload files: 191
installed RECORD rows: 380
installed extras: 188
  185 .pyc
  1 INSTALLER
  1 REQUESTED
  1 direct_url.json
```

All 191 accepted-wheel payloads matched their wheel digests and sizes. Extras were confined to the accepted pip bookkeeping/bytecode set.

Installed semantics:

- exact E3.4 metadata mapping passed;
- arbitrary metadata text sanitizes correctly;
- E3.3 HTTP hierarchy preserved;
- standalone CLI HTTP handling present;
- SQL still 118,896 bytes with frozen SHA-256;
- SQLite 3.50.4;
- no network, Credential Manager read, or production child launch.

Read-only authority validation returned `VALIDATED`, the expected authority root, initialized supported DB state, and the exact Trading SID.

Sealed Administrator/SYSTEM-only runtime after install:

```text
root owner SID: S-1-5-32-544
root ACE count: 2
descendants: 12453
ACL anomalies: 0
```

Trading RX was then republished:

```text
SYSTEM: Full Control
BUILTIN\Administrators: Full Control
DESKTOP-I4DOKM7\Trading: inheritable Read & Execute
root ACE count: 3
descendants: 12453
RX anomalies: 0
```

Non-admin Trading E3.4 zero-provider preflight passed:

- identity exactly `DESKTOP-I4DOKM7\Trading` / expected SID;
- token non-administrator;
- fixed runtime Python and package location verified;
- exact E3.4 reason/classification mapping verified;
- arbitrary metadata-reason text sanitizes to `GENERIC`;
- E3.3 HTTP hierarchy verified;
- production capture module importable without invoking capture;
- fixed runtime write blocked;
- fixed temp write/read/delete probe passed and cleaned;
- Credential Manager read: false;
- network operation: false;
- production child launch: false;
- authority database mutation: false;
- provider request: false.

**E3.4 deployment checkpoint is accepted.**

---

## 11. Planner clock contract

The current planner uses an exchange-local calendar-date reconciliation rule rather than a market-close timestamp rule.

For completed session date `D`, planning reconciles only once the New York calendar date has advanced to `D + 1`. Merely waiting until regular market close plus an operational buffer is insufficient.

This was demonstrated for the August 24 session: the first pure-plan attempt failed safely while New York date was still August 24; the planner passed only after midnight EDT on August 25 (9 PM PDT August 24).

Changing this clock semantic is separate authority architecture work and requires **Sol High** review.

---

## 12. Current resume point / next acceptance gate

Both August 21 and August 24 lineages are consumed.

The next genuinely new XNYS session is **August 25, 2026**. At the current checkpoint it is not yet a completed eligible session.

Under the current planner contract, the earliest pure planning gate for the August 25 session is after:

```text
2026-08-26 00:00 EDT
2026-08-25 21:00 PDT
```

After that rollover, perform **pure planning only** for August 25. The gate must establish a fresh authorized session/digest and then perform a durable freshness check before any provider effect is considered.

Do not run the production capture command before that review.

**Provider call #3 is NOT authorized.**

---

## 13. Crash/recovery posture

Deep review found no unsafe automatic retry path. Important conservative categories remain:

- pre-session / pre-attempt states: no provider effect;
- process-intent committed around `CreateProcessW`: potentially ambiguous process creation, manual classification required;
- proven NOT_CREATED: provider definitely not started but continuation/recovery still explicit;
- PRE_RESUME_READY: child suspended, no provider effect;
- resume intent / resume ambiguity: provider may have occurred, never retry automatically;
- post-resume durable states: manual durable recovery only;
- verified snapshot before terminal / terminal before selection: recover from durable authority without repeating provider effect.

A future read-only `inspect-capture` / `classify-capture` operator tool may be appropriate, but it must derive only from durable state, remain sanitized, and never grant retry authority.

---

## 14. Remaining C3 / pre-unattended reviews

Before unattended production operation, continue deep review of:

- production `close()` / concurrent admission and drain;
- secret and transport-object lifetime;
- artifact verification/publication TOCTOU;
- SQL invariant mutation testing;
- clock/calendar authority;
- selected-snapshot → paper-operation bridge;
- systematic top-level crash/fault matrix.

Native Windows authority, credential lifetime, external-effect ordering, crash/recovery ambiguity, publication/selection authority, retry semantics, and clock semantics require Sol High architecture review. Localized frozen-contract implementation may use Luna Extra High; subtle bounded implementation may use Sol Medium.

---

## 15. Roadmap after successful C3 acceptance

1. **Reliable manual paper cycle** — selected parent-verified snapshot → strategy → proposal → deterministic risk → paper execution → durable result.
2. **Unattended paper operation** — XNYS scheduling, startup reconciliation, recovery, health/alerts, stale/missing-data handling.
3. **Long paper soak** — extended unattended operation and failure recovery while consequences remain simulated.
4. **Broker-paper integration** — account/position reads, submit/cancel/replace, broker IDs, fills, partial fills, rejects, reconciliation, idempotency, ambiguous-submit recovery.
5. **Live-readiness certification** — explicit operating-mode authority, separate live credentials, exact account verification, strict exposure/order/frequency limits, kill switch, outage/halt handling, startup reconciliation, operator-visible health/reconciliation.
6. **Tiny restricted live deployment** — deliberately small, long-only, low-frequency real-money operation only after live-readiness acceptance.
7. **Mature operations, deeper AI, polished GUI** — AI remains a replaceable proposal component inside deterministic authority/risk/reconciliation boundaries.

Stable initial live constraints remain US stocks/ETFs, long-only, no margin/leverage/options/shorts/crypto, deterministic risk approval for every order, paper default, and complete auditability.

---

## 16. Development workflow

Use ChatGPT/Sol for architecture, debugging strategy, GitHub/diff review, test-gate decisions, merge readiness, release gating, and next-step planning.

Model routing:

```text
localized/mechanical/frozen contract → Luna Extra High
subtle bounded implementation       → Sol Medium
native Windows/security/authority/
ordering/crash/recovery/architecture → Sol High
```

Codex implementation prompts should reference `AGENTS.md`, `docs/PROJECT_STATUS.md`, this handoff, and only the relevant architecture documents. Use focused tests during iteration and one broad suite at final certification. Preserve unrelated generated/untracked reports.

For procedural wheel build/inspection/deployment/ACL/preflight/provider-call work, continue the directly supervised PowerShell procedure rather than introducing Codex unless a code change becomes necessary.

Without explicit approval, do not merge, resolve review threads, change PR metadata, force-push, rebase, amend, or modify unrelated files.

After every accepted checkpoint, review/update:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

The Git-tracked pair is authoritative.

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
```

Before any future provider effect, also review the latest durable E3 lineage evidence and confirm the candidate session/digest is genuinely new.

---

## 18. Definition of project success

The project succeeds when it can research deterministically, acquire trusted market data safely, make portfolio decisions under deterministic risk, interact safely with a brokerage, reconcile ambiguous outcomes, run unattended for long periods, fail closed on uncertainty, expose durable evidence and operator controls, operate under strict live limits, and present the same reviewed capabilities through a polished GUI.

The final system is a **safety-oriented automated trading platform in which AI is one replaceable decision-making component inside a deterministic operational and authority framework**.
