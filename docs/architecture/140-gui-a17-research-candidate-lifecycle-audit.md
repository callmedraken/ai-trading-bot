# Architecture 140 / GUI-A17 — Research Candidate Lifecycle Provenance & Audit

Status: implemented for exact GitHub source review; acceptance remains with
ChatGPT after terminal source gates. This is a parallel GUI presentation
checkpoint, with no Architecture 141 or product/history integration.

## Exact admission and isolation

Branch: `feature/gui-research-candidate-lifecycle-audit-current`.
Worktree: `F:\AI\worktrees\ai-trading-bot-gui-research-candidate-lifecycle-audit-current`.
Origin: `https://github.com/callmedraken/ai-trading-bot.git`.
Base HEAD `bbc3c72e34c95bc1ebde3129e327656d0f1ba097`, tree
`840f5201d038fc7865331bc01f5289f946603019`, parent
`6d092b8e05372d241dc4183b7b392f0eb83b4500`.
Require this exact base, registered worktree, empty index and clean tracked and
untracked state before editing. Do not adopt newer product commits.

Preserve armed D1R6 branch
`feature/robinhood-production-paper-overnight-wake-arming` at HEAD
`a36de3bfe81a6e1a94fb3deeec7e579145939f52`, tree
`6cde732e02e92eb2b34281672cdb7744250355b1`. No operation in its
worktree and no movement of its branch, D1R5, product or history refs.

## Pure retained-state composition

`research_candidate_lifecycle_audit.py` imports only dataclasses and the exact
A16 page-state type. `compose_lifecycle_audit` accepts that already acquired
`ResearchCandidateLifecyclePageState` only. It returns exact frozen/slotted
presentation rows and immutable tuples. It performs no acquisition, domain
parsing, domain verification, artifact creation, discovery or external lookup.
The existing A16 models, inspection service and application composition remain
byte-identical. The nine application-state getters and their acquisition order
remain unchanged.

AVAILABLE composition contains exactly:

- Five canonical artifact IDs, in retained order: WALK_FORWARD_PASSED candidate,
  139-A binding, B1 observation batch, B2 qualification, SHADOW candidate.
- Supporting BACKTESTED candidate, walk-forward qualification, report,
  experiment-result and variant IDs, caller ordinal, variant name and original
  rank. Rank is evidence only and grants no authority.
- Five retained HEAD/TREE pairs: candidate, walk-forward qualification, binding,
  observation and B2 qualification. No additional source identity is inferred.
- Three comparisons from retained B2 policy/results: minimum sessions against
  distinct sessions; minimum total observations against total observations;
  minimum observations per session against the recorded minimum in any session.
  Required/recorded counts are exact positive integers excluding bool. Margin
  equals recorded minus required and cannot be negative.
- The exact nine retained B1 zero counters, with the presentation-only recorded
  zero-effect invariant. This grants no authority or observation-origin claim.
- Fixed governance: SHADOW; local canonical artifacts Verified; local SHADOW
  linkage Verified; full historical chain Not re-run by this GUI; real observation
  acquisition Not connected; automatic promotion Disabled; promotion authority
  Not connected; production compatibility Not established; PAPER_CANDIDATE and
  AWAITING_HUMAN_PROMOTION Not materialized; trading authority None.

The visible coverage notice is:

> Margins are coverage headroom only; they do not represent profitability,
> alpha, strategy quality, trading quality, confidence, or production readiness.

No performance thresholds, ranking, recommendation or new qualification is
introduced. The A16 local-scope statement is preserved exactly:

> Canonical local artifacts and SHADOW successor linkage verified.
> Full historical external-chain qualification was not re-run by this GUI.

UNAVAILABLE/ATTENTION composition returns entirely empty audit tuples. The page
retains A16 status/diagnostic text and fixed no-authority governance; it displays
no fabricated evidence, provenance, coverage, local verification or zero-effect
success claim for either status.

## Presentation and capability closure

Enhance the existing Research Lifecycle page only. Page IDs/order are unchanged.
Static framed sections group governance, artifact identities, supporting facts,
provenance, coverage, zero effects, and retained B1/B2 detail. A grid compares
required/recorded/margin values. Plain-text labels remain mouse-selectable;
height-for-width is explicitly retained when configuring label size policies.
The content scrolls vertically with no horizontal overflow at 920x620 and
1180x760, including the existing MainWindow navigation-width reservation.

There are no buttons, editable fields, external links, clipboard accesses or
external applications. Navigation remains pure presentation. Repeated
composition/rendering does not invoke any service or reread any lifecycle file.
AST tests enforce exact imports and a closed call set on the Qt-free module;
retained A16 tests enforce the page/composition capability boundaries.

No provider/network, credentials, Robinhood, broker, paper, scheduler, ACL,
production SQLite, research/walk-forward execution, SHADOW acquisition,
promotion, post-SHADOW materialization, D1/D1R5/D2 or live operation is connected.

## Inventory-only successor authority

Discovery yields ACTIVE 64 / FULL 179 / ROBINHOOD 98 / LEGACY 221 /
EXHAUSTIVE 400 / GUI 50. The single new GUI test module remains LEGACY.

`ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES` succeeds the exact same seven
inventory-test paths after A16 at all five existing resolver sites:
historical -> HIST2 -> D1R5 -> 138 -> 139-A -> B1 -> B2 -> 140/A16 -> 140/A17
-> actual blob. The resolver freezes the exact A16 dictionary with literal
sorted-key JSON SHA-256
`887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f`.
It rejects a wrong before pin and any missing/extra/product overlay path;
existing authority checks reject a wrong after blob. A17 tests freeze all 34
older dictionaries and reject masked predecessor overlay drift.

No predecessor dictionary, operational executable/native/AST authority, ACTIVE
membership, workflow byte or certification topology changes. One A16 test now
checks its accepted pins through the explicit successor instead of asserting
obsolete current bytes. The seven live-inventory tests assert current counts.

Publication/validation is defined in
[the A17 validation record](../validation/gui-a17-research-candidate-lifecycle-audit.md).
Canonical status/handoff closeout remains ChatGPT-owned after acceptance.
