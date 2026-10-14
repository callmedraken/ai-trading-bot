# Architecture 134-D1R5 — bounded pre-market wake qualification

## Source checkpoint and authority

This is a separate **source implementation, pending exact-source review** on
`feature/robinhood-production-paper-premarket-wake-qualification`, in
`F:\AI\worktrees\ai-trading-bot-production-paper-premarket-wake-qualification`.
Bootstrap is intentionally local-only at HEAD
`3e27d606dbec99e3e29c482a15c480139663118b`, TREE
`344a6d1be0394d4f66f1a42caa62f169b0fdcac9`. The accepted remote parent anchor
is `feature/robinhood-production-paper-alpaca-auth-qualification` at the same
identity. This implementation bootstrap exception does not apply to the future
real host: that host requires its own published branch, exact tracking and live
remote identity, clean source, fixed worktree, and unmixed imports.

D1R4 remote Alpaca authentication is **PASS and permanently consumed**:

```text
source HEAD  234614a21d68680f5b1e0ccdb5854347a6a8d090
source TREE  f70459d91c393c6ea7a4a6358f02a2073b246574
evidence     F:\AI\temp\qualification\arch134-d1r4-auth-234614a21d68680f5b1e0ccd.json
bytes        635
SHA256       100e3590543b8ba36002d50d890578533100035b9f618434dd2c9adc2f3505c4
pair reads   1 / succeeded
requests     1 / HTTP 200 / no provider code
readmitted   true
```

The consumed generation journal is irreversibly provider-fenced with SHA-256
`344f64a1c421c41174142aa4f30f2574537bb26e70901dd77cf56ec930ec7434`.
Do not rerun provisioning or authentication.

D1R5 is required before fresh D1 authorization. Source acceptance does not
authorize the real wait qualification. A future real D1R5 invocation is a
separately reviewed bounded clock/sleep/external-evidence effect. Even D1R5
PASS grants no D1 ARM, PREPARE, EXECUTE, paper mutation, broker placement, D2,
scheduler/ACL mutation, or live-trading authority. Real-money trading is NO-GO.

## Independent composition and frozen policy

The qualifier never calls the production armed-session effect path. Production
`armed_session.py` and its wait/wake tests remain unchanged. This qualification
reuses `NYSEPublishedRegularSessionAuthority`, `ReviewPaperSessionSchedule`,
and `admit_review_paper_session`; it does not implement exchange rules itself.
The frozen published calendar remains limited to 2026–2028 and does not claim
knowledge of emergency exchange closures.

| Policy | Fixed value |
| --- | --- |
| Opening buffer | 5 minutes |
| Closing buffer | 5 minutes |
| Maximum lead before regular open | 15 minutes |
| Maximum requested sleep | 20 minutes |
| Maximum wake lateness from admission open | 60 seconds, inclusive |

Today's target is derived from the observed clock in `America/New_York`.
Start must fall on that published session date, at or after regular open minus
15 minutes, and strictly before admission opens. Starts during the opening
buffer are eligible. Missing/unsupported sessions and starts that are too early,
already admitted, in the closing buffer, or after close are rejected before
evidence reservation or sleep. No caller supplies a session date or schedule.

Exact source is admitted before clock/schedule work. After start validation,
the external evidence destination is exclusively reserved with `xb`. Reservation
and source admission records are flushed/fsynced. Source is checked again
before waiting, then the clock is observed again to account for admission and
journal overhead. A backward clock or expired start window blocks the wait.
The remaining interval to admission open is the sole sleeper argument.
`WAITING_FOR_MARKET` is flushed/fsynced before the single sleeper call.

After that call, the qualifier observes the clock and records `WAKE_OBSERVED`.
It rejects early wake, excess lateness, wrong-date wake, and wake outside the
admitted interval. A valid wake requires one final exact-source re-admission,
then durable `SOURCE_READMITTED` and `FINAL / PASS`, and stops. There is no
second wait, retry, restart, recovery, or transition into D1.

## Closed canonical evidence

The fresh external destination has suffix `.jsonl`, lies outside all registered
repository worktrees and `F:\AITradingBot`, and has an existing real parent.
Existing files, symlinks, linked/reparse ancestors, and collision during exclusive
creation are rejected. No repository or production directory is provisioned.

Schema: `arch134-d1r5-pre-market-wake-qualification/v1`. Maximum payload:
16,384 bytes. Each event is one sorted-key compact UTF-8 JSON object followed
by exactly one newline. The complete success sequence is:

```text
QUALIFICATION_RESERVED -> SOURCE_ADMITTED -> WAITING_FOR_MARKET
-> WAKE_OBSERVED -> SOURCE_READMITTED -> FINAL / PASS
```

Each record has exactly the source identities, target session, published regular
open/close, buffered admission open/close, initial observed start, observed wait
start, computed wait seconds, observed wake, source-readmission flag,
classification, schema, event, and the source-defined zero effect counters.
Timestamps use canonical aware UTC ISO text. Wait seconds is a bounded JSON
floating-point number derived from the exact datetime interval; null precedes
the waiting record. Nonterminal classification is null. No exception text,
provider content, secrets, paths, or user free text enters the journal.

Closed terminal classifications are `PASS`, `SOURCE_REJECTED`,
`SESSION_UNAVAILABLE`, `START_WINDOW_REJECTED`, `WAIT_FAILED`, `WAKE_TOO_EARLY`,
`WAKE_TOO_LATE`, and `WAKE_SESSION_INVALID`. Initial source/session/start
rejections return a fixed classification without reserving evidence. After
reservation, source rejection or an expired start may terminate before waiting;
sleeper/clock failure terminates after waiting; bad wake/source drift terminates
after wake. PASS requires the complete six-event sequence.

The canonical parser accepts complete durable event prefixes for read-only
interruption assessment. Every reserved destination is consumed, including an
empty file, partial last line, interrupted `WAITING_FOR_MARKET`, or failed
fsync. Complete prefixes without FINAL are incomplete consumed evidence, never
PASS. Partial/corrupt evidence fails parsing and remains consumed. A future
invocation always needs a fresh destination; there is no resume API.

Unknown/missing/duplicate fields, bool counters, nonzero effects, invalid source
identities, impossible order, changing facts, unpublished/incoherent schedules,
incoherent timestamp/wait facts, incompatible terminal classification,
noncanonical JSON, BOM, trailing bytes, and oversized payloads fail closed.
Write/flush/fsync failure stops without retry or further sleep/source effects.

## Host and effect budget

The noninteractive module is
`trading_bot.review_paper.pre_market_wake_qualification_host`. Its only inputs
are `--expected-head`, `--expected-tree`, `--evidence`, and `--qualify-wake`.
The exact interlock is
`AUTHORIZE_ARCH134_D1R5_ONE_PREMARKET_WAKE_QUALIFICATION`.
Abbreviations and semantic inputs are rejected. Import/help performs no effect.
Host failures use fixed sanitized output. No execution command is provided here;
the future reviewed operator boundary must supply the published exact identity
and a fresh external evidence destination.

Implementation, fake/temp tests, and source CI perform zero real operational
effects. The future qualifier permits only read-only source/Git admission, real
clock observations, one bounded real sleep, and fresh external journal creation
with durable append/fsync. It imports no credential module and performs zero
credential reads, provider requests, Robinhood reads/reviews, OAuth/browser
interaction, production SQLite/store reads/writes, strategy evaluations,
PREPARE/EXECUTE, paper/broker effects, scheduler/ACL changes, D1/D2 invocations,
or live effects. Every journal record explicitly fixes all these counters to zero.

## Source certification and next boundary

The new `arch134-d1r5-pre-market-wake-qualification` checkpoint maps its exact
`feature/robinhood-*` branch to canonical CI-owned ROBINHOOD certification.
It has no registered preflight or execute hook and never invokes the real host.
The workflow's existing reviewed family pattern already admits this branch.

Canonical discovery adds exactly one supported `tests/review_paper` module:
FULL 174 -> 175, ROBINHOOD 97 -> 98, LEGACY 215 unchanged, EXHAUSTIVE 389 -> 390.
Frozen required baseline tuples and predecessor pin dictionaries remain unchanged.
The narrowly bounded `ARCH134_D1R5_TEST_PIN_OVERRIDES` successor resolves after
HIST-2 for certification profiles and checkpoint core/CI/helper tests only.
Unreviewed override paths fail closed.

Focused verification uses fake clocks/sleepers and fresh external pytest
basetemp with no pytest cache. It covers the new module, retained armed-session
wait/wake behavior, session admission, profile inventories, affected checkpoint
core/CI registration, and predecessor source authority. Ruff check/format and
`git diff --check` are required. No local broad FULL/ROBINHOOD run is requested;
mapped CI owns that obligation after separately authorized publication/review.

Stop at local implementation: no staging, commit, push, remote branch creation,
real qualification, ARM, credentials, provider access, or production-root access.
Next owner is ChatGPT for exact local diff review and source-checkpoint handoff.
