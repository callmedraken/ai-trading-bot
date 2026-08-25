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
13. E3.4 closed sanitized response-metadata sub-classifications.

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

Administrator deployment is accepted:

- runtime quiescent before replacement;
- Trading RX revoked before install;
- offline uninstall/install succeeded;
- all 191 accepted-wheel payload files matched after installation;
- installed RECORD contained 380 rows: the 192 accepted wheel rows plus 188 accepted installer extras (185 `.pyc`, `INSTALLER`, `REQUESTED`, `direct_url.json`);
- installed E3.4 metadata mappings passed;
- E3.3 HTTP hierarchy and CLI handling remained correct;
- production SQL remained 118,896 bytes / frozen SHA-256;
- SQLite version 3.50.4;
- read-only authority validation returned `VALIDATED` with the exact Trading SID;
- runtime owner normalized to Administrators;
- Administrator/SYSTEM-only sealed topology passed with 12,453 descendants and zero ACL anomalies.

Trading RX republication is also accepted:

- root owner: Administrators SID `S-1-5-32-544`;
- root ACE count: 3;
- SYSTEM: Full Control;
- Administrators: Full Control;
- Trading: inheritable Read & Execute only;
- 12,453 descendants;
- zero RX topology anomalies.

The non-admin Trading E3.4 preflight passed:

- exact Trading SID and non-admin token;
- fixed runtime Python and package location verified;
- exact E3.4 metadata reason/classification mapping verified;
- arbitrary metadata reason sanitizes to `GENERIC` without retaining raw text;
- E3.3 HTTP hierarchy verified;
- production capture module importable without invocation;
- runtime write blocked under Trading;
- production temp write/read/delete probe passed and cleaned;
- no Credential Manager read;
- no network operation;
- no production child launch;
- no authority database mutation;
- no provider request.

**The E3.4 deployment checkpoint is accepted.**

## Parallel GUI track: GUI-A3 certified

GUI-A1 through GUI-A3 are complete on isolated branch `feature/gui-foundation`, based on `develop` and intentionally separate from the frozen C3 production branch.

Accepted GUI-A3 checkpoint:

- GUI branch HEAD: `9076ca4b4be125e42c14460c35b2d1ce677e5a82`;
- Architecture 90 continues to define the GUI dependency direction and no-effect boundary;
- PySide6/Qt remains optional and presentation-only;
- the existing bounded compact-report service remains authoritative for report loading, including exact canonical deserialization, a 10 MB + 1 byte read bound, a 500-row result bound, and one sanitized unavailable state;
- GUI-A3 adds a native `Open Report…` flow for explicit local `.json` report selection without scanning directories or persisting recent-file state;
- report replacement updates only the Research presentation state and does not rebuild unrelated application state or mutate the source artifact;
- the current report path is operator-visible but bounded to 512 presentation characters;
- filtering is case-insensitive over displayed variant/parameter labels and bounded to 200 characters;
- the results table remains non-editable, single-row-selection, and supports deterministic presentation-only sorting over rank, variant, parameters, total return, maximum drawdown, turnover, and trades;
- sortable keys safely handle unranked rows and use `caller_ordinal` as the deterministic tie-breaker for equal primary values;
- supported header clicks explicitly start ascending and then toggle direction; unsupported Exposure and Return/drawdown columns do not reorder the table;
- sorting/filtering never mutates the underlying immutable `ResearchReportView.rows` sequence;
- selected-row detail displays only approved report fields: rank, variant, parameters, total return, maximum drawdown, turnover, and trade count;
- Exposure and Return/drawdown remain explicitly `Unavailable` because compact-report v1 supplies no approved source or derivation policy;
- existing CLI startup via `python -m trading_bot.gui --research-report PATH` remains operational;
- no research execution, optimization, strategy mutation, network access, Credential Manager access, C1/C2/C3 authority access, production child launch, provider transport, brokerage, scheduler, recovery, or live controls are connected;
- focused GUI-A3 implementation verification passed before commit, and the deterministic-sorting follow-up gate passed with 18 GUI-A3 tests;
- full repository regression at final GUI-A3 HEAD: 2,759 passed, 13 skipped, 0 failed;
- Ruff check passed;
- Ruff format check passed across 351 tracked Python files;
- final `git diff --check` passed;
- interactive visual smoke passed using the tracked compact-report fixture: Open Report, bounded filtering, deterministic table ordering, row selection, detail-panel updates, and unavailable metrics all rendered correctly in the dark theme;
- final tracked working tree was clean; unrelated generated/untracked artifacts remained untouched.

The GUI branch is 15 commits ahead of `develop`, 0 behind. GUI-A4 should remain read-only and focus on research visualization/comparison over already-reviewed report data rather than adding trading or production effects. Any control that can invoke production capture, modify trading state, access credentials, recover/retry authority, or submit brokerage actions remains out of scope.

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

Total real Alpaca provider effects: **exactly 2**.

## Planner clock contract and next eligible session

The current planner contract is exchange-local **calendar-date** based. For completed session date `D`, planning reconciles only after the New York calendar date has advanced to `D + 1`. Merely waiting until market close plus a buffer is insufficient.

Both August 21 and August 24 are consumed. The next genuinely new XNYS session is **August 25, 2026**, but it is not yet a completed eligible session at the current checkpoint. Under the current planner contract, the earliest pure planning gate for the August 25 session is after:

- `2026-08-26 00:00 EDT`, equivalently
- `2026-08-25 21:00 PDT`.

Until that exchange-date rollover, do not manufacture a new digest and do not invoke the production capture command.

After rollover, the next step is **pure planning only** for the August 25 session. Review the authorized session date, fresh request digest, and durable freshness before considering any real provider effect.

**Provider call #3 is NOT authorized.**

## Immediate deep-review status

Completed deep reviews found no unsafe automatic retry path, but identified follow-up work before unattended operation:

- operator diagnosis/recovery routing remains too opaque;
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