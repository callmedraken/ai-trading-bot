# Architecture 140 / GUI-A16 — Read-Only Research Candidate Lifecycle Inspection

Status: **SOURCE ACCEPTED** after independent ChatGPT GitHub review of exact
implementation source `6d092b8e05372d241dc4183b7b392f0eb83b4500` / tree
`fd17ccfd338266c04d24dd03e303ee36dd72b0ca`.

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


## Final exact-source acceptance

ChatGPT independently reviewed the exact GitHub implementation commit before this
bounded closeout. Architecture 140 / GUI-A16 is canonically **SOURCE ACCEPTED** at:

```text
HEAD  6d092b8e05372d241dc4183b7b392f0eb83b4500
TREE  fd17ccfd338266c04d24dd03e303ee36dd72b0ca
parent 5889f83ea5a4baefc154283266d645a555ed2d5c
commit feat: add read-only research candidate lifecycle GUI
```

The base is the accepted Architecture-139-B docs descendant and the implementation
is exactly one commit ahead with that exact merge base. The branch ref resolves to
the accepted HEAD. Product and canonical history refs remain independently at
`7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343`; no integration/replay occurred.

Key exact accepted blobs are:

| Path | Git blob |
| --- | --- |
| `src/trading_bot/gui/research_candidate_lifecycle_models.py` | `19ca4f9e4e75b4a061e0d8ec8d6515cf35a53352` |
| `src/trading_bot/gui/research_candidate_lifecycle_service.py` | `62da586b13a399b5c806cf159b33e47b21ffc56b` |
| `src/trading_bot/gui/research_candidate_lifecycle_page.py` | `8a13ed7e5a7351f1a0bca35a3aaf2741d6991790` |
| `tests/gui/test_gui_a16_research_candidate_lifecycle_models.py` | `3c85eab11d14aceafe22c5a0ef00c0fad54385bb` |
| `tests/gui/test_gui_a16_research_candidate_lifecycle_service.py` | `77ee72939af5a5df6ddba6aa3640db1102bfad91` |
| `tests/gui/test_gui_a16_research_candidate_lifecycle_page_qt.py` | `3ab95f58f8553dbcdc30fdaeba459a5f7aa1b2df` |
| `tests/gui/test_gui_a16_research_candidate_lifecycle_composition.py` | `fb00d23a87bfc9736d38131adae0908b560dbf6c` |
| `tests/gui/test_gui_a16_research_candidate_lifecycle_startup.py` | `95ce8c4be0e29aefc348d53e25302a51b76a3476` |
| `scripts/checkpoint_runner.py` | `6c108d1691eb70daa3cae5352ad7d6f211cd27d4` |

The accepted 137/138/139 domain/test blobs remain byte-identical, including B1
observation source `61a4f9bc67ad0c05f961a523c231e64e6fb55732` and B2 qualification source
`75cc22d16d65f51ce75921ab66c6dcabfbfa119b`. Workflow blobs remain exactly
`ff019356795e508b3b2e7a065871edd2d6bad5bd` (GUI) and
`fe6aceac62721338eba4fcb40e2e7fde0d976e18` (Checkpoint Source Gates).

The Architecture-140 seven-path overlay matches the actual seven current test
blobs and resolves immediately after 139-B2 at all five live authority sites.
The frozen 139-B2 overlay digest is
`32ef60967164da03e02c8cfe40928b8839f89a2c4bb90074e967bb08213d6458`;
A16 tests freeze 34 predecessor dictionaries. Current inventory is ACTIVE 64 /
FULL 179 / ROBINHOOD 98 / LEGACY 220 / EXHAUSTIVE 399 / GUI 49.

Dedicated GUI Source Gates #8 / `38684121623` is push-triggered, attempt 1,
terminal SUCCESS on the exact accepted HEAD with PySide6 6.10.3, **880 passed**,
Ruff check/format PASS and diff PASS. Checkpoint Source Gates #565 /
`38684312270` is workflow_dispatch, attempt 1, terminal SUCCESS on the same HEAD:
source-static passed all 64 current authorities with CHECKPOINTS=64,
TEST_PATHS=88, RUFF_PATHS=372, GIT_DIFF_CHECK=0, RUFF_CHECK=0,
RUFF_FORMAT=0 and PYTEST=SKIP; broad shards passed with PYTEST=0 in
99.178 / 94.690 / 85.018 / 109.033 seconds; active/certification jobs skipped
as expected for the unmapped GUI route; terminal source-gates passed.

Independent source review confirms the five explicit paths are all-or-none,
prevalidated before opening, read only in binary mode with the fixed 8 MiB + 1
bound, decoded strict UTF-8 and passed unmodified to the five accepted parsers.
Success/failure are cached; presentation state retains no path/raw JSON/raw
exception/domain object. The public `verify_shadow_research_candidate` establishes
only local successor linkage. The page truthfully states that complete historical
external-chain qualification was not re-run and exposes no effect controls.
Supervisor/System/Evidence composition uses the already-acquired state and adds
zero rereads.

All requested A16 operational/production effect counters remain zero. Filesystem
and latest-artifact discovery remain false. No real SHADOW observation,
research/walk-forward execution, provider/credential/broker/paper/production
store/scheduler/ACL effect, strategy promotion, production-contract creation,
D1/D1R5/D2 operation, production compatibility, PAPER_CANDIDATE,
AWAITING_HUMAN_PROMOTION or Architecture 141 is authorized by this acceptance.
