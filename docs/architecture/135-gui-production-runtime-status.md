# Architecture 135 / GUI-A14 — Read-only production runtime evidence

## Source boundary

Implementation checkpoint, pending exact GitHub source/CI review and acceptance.
Frozen parent: HEAD `2f122958366d1db282fea51abbd461b83fa893d9`, TREE
`c3fb82add37bdbea12ebad9836ca10000b924fe1`. Worktree:
`F:\AI\worktrees\ai-trading-bot-gui-production-runtime-status`; branch:
`feature/gui-production-runtime-status`. Accepted D1/R1 runtime and R2 ACL
execution source and checkpoint authority remain frozen.

## Allowed composition

Explicit operator-selected JSON -> bounded Qt-free evidence inspection ->
immutable GUI-owned models -> GuiApplicationService -> Runtime page -> pure
System Health / Evidence adapters. Operations retains historical PD4 semantics;
Runtime presents only the explicit ACL, qualification and D1 session artifacts.

Normal startup accepts optional `--runtime-acl-evidence PATH`,
`--runtime-qualification-evidence PATH`, and `--runtime-session-evidence PATH`.
The parser consumes these arguments before Qt forwarding. All absent means a
deterministic UNAVAILABLE state and zero runtime evidence I/O. No environment,
directory, production-root or latest-file selection is permitted.

## Closed evidence contract

Accepted schemas are exactly `production-paper-runtime-acl/v1`,
`production-paper-runtime-qualification/v1`, and `armed-paper-session/v1`.
Each file is opened read-only at most once per acquisition, read to at most
32 KiB + one rejection byte, then cached (including failures). JSON duplicate
keys, non-JSON constants, unknown/missing fields and malformed structures fail
closed. Session snapshot/seed digests are validated and discarded.

All display values are typed and immutable. HEAD/tree are lowercase 40-hex;
principal digest is null or lowercase 64-hex. UUIDs are canonical lowercase
UUID text at the parser boundary; dates are canonical ISO dates; instants require
an explicit offset and normalize to UTC. Exact booleans exclude integers.
General counts are 0..1,000,000; session history/read counts are bounded to 253,
evaluation/prepare/execute/review counts to one, order reads to 202, paper
mutations to one, and broker placement to zero. Incomplete effects may retain
unknown nullable counts from the accepted schema, always with ATTENTION.

GUI-owned closed classifications mirror the accepted current schemas. No
production execution module is imported for vocabulary reuse. Raw SID/user/ACL,
credential/token, provider payload, path, free-form exception and unknown fields
are rejected. Errors produce fixed bounded diagnostics without exception text.
Qualification/session HEAD and tree must match exactly; mismatch yields
ATTENTION / CONFLICTING without reconciliation. Blocking classifications,
incomplete effects and unexpected qualification/ACL effects yield ATTENTION.
Valid evidence yields AVAILABLE, never fresh production or trading authority.

## Presentation and navigation

Stable pages: home, research, paper, paper-account, market-data, operations,
runtime, evidence, system. Runtime clearly says read-only, evidence-based,
not current trading authority and not an execution/control surface. It renders
recorded source, ACL/digest/effect counts, SQLite readiness, credential-read
metadata, external/trading counts and the supplied D1 session. IDs/hashes are
selectable. Scrollable content fits the 920x620 minimum window. No ARM, retry,
qualify, provision, refresh, polling or effect button is present.

Overview adds a neutral unavailable Runtime card by default, an informational
recorded-evidence card when available, and BLOCKED when evidence requires
attention. MainWindow acquires exactly seven application-service states once:
overview, research, paper, paper-account, market-data, operations, runtime.
System and Evidence receive already-acquired RuntimePageState. Navigation,
filtering and Evidence -> Runtime source navigation perform zero service/file
rereads. Runtime UNAVAILABLE is neutral in System; AVAILABLE maps to AVAILABLE;
ATTENTION maps to BLOCKED and overall ATTENTION.

System copies only bounded HEAD/tree, principal digest and session
contract/operation identities. Evidence adds the closed RUNTIME source and
Runtime ACL, qualification and supplied session entries. ACL/qualification are
untimed; session uses admitted_at or wait_started_at only when serialized.
The A11 filters and A12/A13 closed mappings include Runtime without rediscovery.

## Effect boundaries

```text
DIRECT_PRODUCTION_SQLITE_ACCESS=False
CREDENTIAL_MANAGER_ACCESS=False
ALPACA_NETWORK_ACCESS=False
ROBINHOOD_NETWORK_ACCESS=False
SCHEDULER_ACCESS=False
ACL_MUTATION=False
PAPER_EXECUTION=False
BROKERAGE_ACCESS=False
FILESYSTEM_DISCOVERY=False
LATEST_EVIDENCE_DISCOVERY=False
EXPLICIT_EVIDENCE_ONLY=True
SERVICE_REREADS_ON_NAVIGATION=0
```

No production SQLite, credential, provider, Robinhood MCP, scheduler, ACL,
armed-session, strategy/risk/order execution or broker capability is composed.
Synthetic fixtures only; no user production evidence or real principal digest
is committed or read by tests.

## CI bootstrap boundary

The dedicated `gui-source-gates.yml` targets Windows/Python 3.14, installs
`.[dev,gui]`, requires real PySide6, and runs tests/gui, combined non-mutating
GUI Ruff checks and git diff checks. It performs no protected operation.
GUI-A14 is not registered in the R1/R2 checkpoint or ROBINHOOD profile.

Before the first push, the repository's branch-bootstrap rule requires an
independently reviewed registration on integration/default source. Neither the
frozen parent nor current develop admits this GUI branch. Adding it to the
existing push allowlist would also invalidate an exact branch-list test pinned
by frozen R1/R2 authority. Do not modify those pins or silently self-register.
The user chose to keep R1/R2 frozen, complete one local commit and return the
bootstrap decision to ChatGPT. No push is performed; publication and terminal
CI remain pending that decision.
