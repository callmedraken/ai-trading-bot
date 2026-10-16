# Architecture 140 / GUI-A18 — Research Candidate Lifecycle Boundary Map

Status: implemented for exact GitHub source review; acceptance remains with
ChatGPT after terminal source gates. This is an additive, presentation-only
successor to GUI-A17. It does not begin Architecture 141 or move the product or
canonical-history branches.

## Exact admission and isolation

The A17 remote predecessor was independently checked before worktree creation:

```text
branch  feature/gui-research-candidate-lifecycle-audit-current
HEAD    1b1670d8ac6a2bca1ce72be198c4cb0477af8238
TREE    8f634b08c1bb42c4023a6e2d537b63a8f4fce595
```

The A17 executable source is its ancestor at
`56f3e8ef73f8aa62e2444c7fc9c75dfb212ff246` / tree
`5de6706064424aa4734b53cad4efffe5011284f4`. The remote descendant changes
only `docs/PROJECT_STATUS.md` and `docs/AI_TRADING_BOT_HANDOFF.md`.

The isolated implementation worktree is
`F:\AI\worktrees\ai-trading-bot-gui-research-candidate-boundary-map-current`
on branch `feature/gui-research-candidate-lifecycle-boundary-map-current`.
No other active worktree or product/history ref is part of this checkpoint.

## Frozen presentation contract

A18 adds `research_candidate_lifecycle_boundary_map.py`. Its composer accepts
only the immutable A17 `LifecycleAuditPresentation`. It never opens files,
acquires artifacts, calls a service, parses or verifies a domain artifact, or
recomputes qualification evidence. It returns frozen/slotted rows in this
fixed order:

| Boundary | Recorded status | Authority meaning |
| --- | --- | --- |
| Local canonical artifacts | `VERIFIED_LOCAL` | A16 local artifact identities only; not source acceptance |
| Local SHADOW successor linkage | `VERIFIED_LOCAL` | Retained local linkage; no new lifecycle state |
| Retained source provenance | `RECORDED` | HEAD/TREE provenance only; not remote acceptance |
| Qualification coverage | `RECORDED_SATISFIED` | Retained B2 minima facts; descriptive coverage only |
| Observation effects | `RECORDED_ZERO` | Retained nine zero counters; no operational authority or observation-origin claim |
| Full historical/external chain | `NOT_REVERIFIED` | Not re-run by this GUI |
| Real observation acquisition | `NOT_CONNECTED` | No provider/acquisition boundary |
| Production compatibility | `NOT_ESTABLISHED` | No production compatibility or strategy selection |
| `PAPER_CANDIDATE` | `NOT_MATERIALIZED` | No later research lifecycle stage |
| `AWAITING_HUMAN_PROMOTION` | `NOT_MATERIALIZED` | No later research lifecycle stage |
| Automatic promotion | `DISABLED` | No automatic advancement or promotion control |
| Promotion authority | `NOT_CONNECTED` | No promotion authority boundary |
| Trading authority | `NONE` | No paper, broker, or live trading authority |

Coverage margins and zero-effect counters remain retained presentation facts.
They do not infer profitability, alpha, strategy quality, confidence, trading
quality, production readiness, or promotion eligibility. The lifecycle remains
stopped at `ResearchCandidateStage.SHADOW`; no `PAPER_CANDIDATE` or
`AWAITING_HUMAN_PROMOTION` artifact or stage is materialized.

For A17 empty audit evidence (UNAVAILABLE and ATTENTION), A18 returns an empty
boundary map and the page retains only A16's fixed no-authority presentation.
It fabricates no evidence rows.

## UI boundary

The existing `ResearchCandidateLifecyclePage` gains one clearly labeled
`Lifecycle boundary map` section with the presentation-only columns `Boundary`,
`Recorded status`, and `Authority meaning`. The page ID, route, startup
composition, application service, five-artifact acquisition boundary and A17
audit composer remain unchanged. The section has no buttons, links, file-open,
clipboard, refresh, provider, promotion, or trading controls. Repeated page
construction and rendering reuse the already supplied A17 presentation.

## Successor authority and inventory

A18 preserves the A16 overlay digest
`887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f` and the
A17 overlay digest
`dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3`.
Because the current inventory-count assertions record the new GUI test module,
the checkpoint runner adds an A18 overlay for the same seven current inventory
test paths as A17, pinned to their exact current blobs. The A18 overlay digest
is `a82247963625dea0f6842d4dc59a851c6986d9f3d8d0c0f40d452aaea2a35af5`, and
its resolver validates the A17 predecessor before returning current blobs.

The resulting source inventory is:

```text
ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 222
EXHAUSTIVE 401 / tests/gui 51
```

No workflow YAML, ACTIVE membership, certification profile, domain source,
Architecture-139 source, A16 acquisition, A17 audit, D1R5 product, scheduler,
provider, promotion, or trading authority is changed.

## Effect boundary

All A18 composition and rendering are synthetic, local, and read-only. No
production SQLite read/write, credential read, provider call, Robinhood read,
broker call, paper mutation, scheduler call, ACL mutation, research execution,
SHADOW observation acquisition, promotion, production-contract creation,
D1/D1R5/D2 operation, or live-money effect is connected.
