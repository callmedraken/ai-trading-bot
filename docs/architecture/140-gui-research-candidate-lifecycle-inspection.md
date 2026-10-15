# Architecture 140 / GUI-A16 — Read-Only Research Candidate Lifecycle Inspection

Status: implementation contract frozen before source work; pending exact GitHub
review. No canonical SOURCE ACCEPTED claim is made by this checkpoint.

## Admission and scope

Worktree: `F:\AI\worktrees\ai-trading-bot-gui-research-candidate-lifecycle-current`.
Branch: `feature/gui-research-candidate-lifecycle-current`.
Base HEAD `5889f83ea5a4baefc154283266d645a555ed2d5c`, TREE
`bad3b80ecacb3bef259bf0feb95cbeb3cf69255c`. Origin is exactly
`https://github.com/callmedraken/ai-trading-bot.git`. Admission requires clean
worktree/index and GUI-A15 `778151fe8f91632a1af66384a3ab0a85d8d65069`
ancestry. No GUI-A15 replay, merge, cherry-pick or product/history ref movement.

A16 inspects only the accepted BACKTESTED -> WALK_FORWARD_PASSED -> 139-A
binding -> 139-B1 observation batch -> 139-B2 qualification -> immutable SHADOW
successor. It creates no lifecycle domain artifact and no stage transition.

## Verification scope — normative

These are distinct: (1) canonical parser self-consistency, (2) exact local SHADOW
successor/linkage verification, (3) complete historical/external 137–139 chain
qualification. A16 performs only 1 and 2. Visible AVAILABLE wording is:

> Canonical local artifacts and SHADOW successor linkage verified.
> Full historical external-chain qualification was not re-run by this GUI.

No vague verified flag, external source acceptance, production compatibility,
promotion eligibility, profitability, trading quality/readiness or production
readiness is inferred. Original rank is evidence only and grants no authority.

## Explicit five-artifact input

Optional startup Path fields and matching consumed CLI flags are:

- `research_walk_forward_candidate` / `--research-walk-forward-candidate`
- `research_shadow_binding` / `--research-shadow-binding`
- `research_shadow_observation_batch` / `--research-shadow-observation-batch`
- `research_shadow_qualification` / `--research-shadow-qualification`
- `research_shadow_candidate` / `--research-shadow-candidate`

None selected means deterministic UNAVAILABLE, no inspection-service instance
and zero lifecycle file I/O. All five means one inspection. All 30 nonempty
partial combinations reject configuration before GUI construction. Wrong Path
types reject. Explicit local .json files only: reject UNC/device paths, URI/ADS,
control characters including DEL, unsupported suffixes and drive-relative paths.
No directory, glob, recursion, environment/Git lookup, latest/default location,
sibling inference or inferred source path. Existing report selection is separate.

## Bounded acquisition and adaptation

`ResearchCandidateLifecycleInspectionService` accepts exactly five explicit
Paths; configuration constructs it only for a complete set. Validate all path
syntax before any open. Each artifact is opened read-only in binary mode at most
once, with an **8 MiB per-file bound plus one rejection byte**, strict UTF-8 and
exact unmodified text passed to its accepted `from_json` parser. This deliberately
limits GUI inspection below the domain's possible 100,000-observation batch size;
larger canonical batches yield fixed ATTENTION, never arbitrary reads. No parser
or canonical schema is changed for GUI use.

Parsers: `WalkForwardPassedResearchStrategyCandidate`,
`ResearchCandidateShadowVariantBinding`, `ResearchCandidateShadowObservationBatch`,
`ResearchCandidateShadowQualification`, `ShadowResearchStrategyCandidate`.
After all parse, call public `verify_shadow_research_candidate(shadow,
walk_forward_passed, binding, batch, qualification)`. No generic dictionary
schema reconstruction, external-chain verifier or execution/qualification entry
point is used by product GUI code. Cache success and failure. Adapted immutable
Qt-free frozen/slotted state holds no Path, raw bytes/JSON, exception strings or
domain artifact. No rereads on navigation.

Closed statuses are UNAVAILABLE (nothing configured), AVAILABLE (five canonical
artifacts plus local successor linkage), ATTENTION (configured evidence unreadable,
noncanonical, over bound or inconsistent). Diagnostics use fixed closed text.
AVAILABLE requires complete evidence; other states contain none. Models validate
exact enums, UUIDs, lowercase 40-hex provenance, bounded text, exact int excluding
bool, rank None or positive, dates and exact UTC timestamps. Fixed governance
facts are non-constructor fields/properties, never override switches.

Presentation retains SHADOW candidate, WALK_FORWARD_PASSED candidate, BACKTESTED
ancestor, walk-forward qualification, binding, batch, B2 qualification, report,
experiment-result and variant IDs, caller ordinal/name and original rank. It
retains only existing candidate, walk-forward qualification, binding, observation
and B2 qualification source HEAD/TREE pairs, with no invented provenance.

B1 summary contains observation/session counts, first/last session dates and
first/last exact caller UTC timestamps. No exchange-open/provider origin claim.
No individual observation list. Display all nine exact zero counters:
CREDENTIAL_READS, PROVIDER_CALLS, ROBINHOOD_READS, BROKER_CALLS, PAPER_MUTATIONS,
SCHEDULER_CALLS, ACL_MUTATIONS, PRODUCTION_SQLITE_READS, PRODUCTION_SQLITE_WRITES.
No switch can weaken zero requirements. B2 displays exact policy minima for
sessions/total/per-session, recomputed retained counts and minimum-per-session,
PASSED status and ordered empty failure reasons required by the successor verifier.
No performance thresholds are added.

## Pure composition and page

`GuiApplicationService.get_research_candidate_lifecycle_state()` is the sole
additional application-state acquisition: MainWindow acquires nine states once
in the existing eight-state order, appending lifecycle before pure composition.
Overview may report only configuration presence and never initiates lifecycle
reads. Supervisor, System and Evidence optionally receive the already acquired
state; no downstream service reference/reader. Existing optional callers remain
valid. No lifecycle/production contract identity comparison or compatibility.

Stable order: home, research, research-lifecycle, paper, paper-account,
market-data, operations, runtime, supervisor, evidence, system. Label Research
Lifecycle. Separate plain selectable text page, vertical scrolling, no horizontal
overflow at MainWindow 920x620 or 1180x760, no QPushButton or effect controls.
Research compact-report page remains intact.

Fixed visible governance: Stage SHADOW; Real observation acquisition Not
connected; Automatic promotion Disabled; Promotion authority Not connected;
Production compatibility Not established; PAPER_CANDIDATE Not materialized;
AWAITING_HUMAN_PROMOTION Not materialized; Trading authority None. Supervisor
also shows human promotion required Yes and production replacement Disabled.
Existing automatic=false, human-required=true, authority-connected=false,
research-replacement=false invariants remain. Lifecycle ATTENTION propagates
attention; AVAILABLE evidence never establishes production readiness.

System optional Research Lifecycle maps UNAVAILABLE/AVAILABLE/ATTENTION to
UNAVAILABLE/AVAILABLE/BLOCKED. BLOCKED means selected evidence needs attention,
not a trading rejection. Bounded audits contain lifecycle IDs, no paths/JSON.
Evidence adds closed RESEARCH_LIFECYCLE source with five untimed canonical
artifact entries, no invented batch event timestamp. B1 date/time range may
appear only in bounded detail. A11 filtering is pure; A12 System -> Evidence
maps lifecycle IDs; A13 Evidence -> research-lifecycle navigation adds zero
service/file reads.

## Capability and authority freeze

A16 product modules have no direct network/provider, credential, broker, paper,
production SQLite, runtime execution, simulator/research/walk-forward runner,
subprocess, scheduler/ACL, promotion, contract-creation or generic stage mutation
capability. AST tests enforce closed imports/calls and prohibit discovery/file
I/O outside the dedicated lifecycle service. Existing composition retains its
reviewed unrelated read-only adapters; A16 adds no operational composition.

No new research/walk-forward execution, live observation acquisition, provider,
production compatibility, PAPER_CANDIDATE, AWAITING_HUMAN_PROMOTION, D1/D1R5/D2,
paper/broker effects, credentials, production store, scheduler/ACL or Architecture
141 work. Synthetic selected temporary artifact reads are allowed in tests.

## Inventory successor and publication

Before: ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 215 / EXHAUSTIVE 394 /
GUI 44. Canonical discovery after the five new GUI modules confirms ACTIVE 64 /
FULL 179 / ROBINHOOD 98 / LEGACY 220 / EXHAUSTIVE 399 / GUI 49.
GUI stays LEGACY. No ACTIVE membership,
production executable/native/AST pin, workflow topology or workflow byte change.

Add `ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES` for exactly the same seven
current live-inventory test paths as 139-B2. Resolve after B2 at all five sites:
historical -> HIST2 -> D1R5 -> 138 -> 139-A -> B1 -> B2 -> 140 -> actual Git blob.
Freeze every predecessor dictionary, including exact B2 overlay SHA-256 in A16
tests; never mutate B1/B2 overlays. Reject missing/extra/executable paths, wrong
current blobs and predecessor drift. Update stale current GUI/inventory assertions
without rewriting historical acceptance records.

The frozen B2 overlay SHA-256 (sorted-key JSON dictionary material) is
`32ef60967164da03e02c8cfe40928b8839f89a2c4bb90074e967bb08213d6458`.
All 34 predecessor dictionary digests are literal A16 test cases. Existing
authority diagnostics stay intact; the new resolver adds the B2 overlay guard
after the existing frozen overlay guards, without broadening operational pins.

Local gates and CI are frozen in the companion validation record. After all
local gates pass, exact-file stage and one normal commit `feat: add read-only
research candidate lifecycle GUI`, one ordinary push, await automatic dedicated
GUI Source Gates terminal success, then exactly one fresh Checkpoint Source
Gates dispatch. No retries/duplicate dispatch; failure is STOP. Independently
review/refetch exact remote source, blobs, dictionaries, inventory, CI and clean
state. Stop for ChatGPT exact GitHub review. Do not update PROJECT_STATUS or
AI_TRADING_BOT_HANDOFF or integrate product/history refs.
