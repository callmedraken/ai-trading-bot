# AI Trading Bot — Project Status

## Current checkpoint

Architecture 134-F1R1-D1S4-R1 is accepted, operationally complete and reconciled.
The shared namespace ACL recovery succeeded; its one-shot durable attempt is
permanently CONSUMED; the compromised D1S4 FINAL and two historical .installing
roots remain preserved incident evidence.

Architecture 134-F1R1-D1S4 Fresh Successor Source is SOURCE ACCEPTED and
integrated. Exact accepted source:

    HEAD b18c6e32606828beeebc540a93c9f05e3e024323
    TREE b082c15bc697bf289fc7997b3d7bf87050082dc3

Feature CI #714 / 40167976672 attempt 1 and develop integration CI #715 /
40169150780 attempt 1 are terminal SUCCESS. The post-acceptance status/handoff
closeout is develop commit a637f1b34565a715c14874d0f9a9686388319c16,
tree e870cc8f28138076d1e247eb92358d88a89c2f26; docs-only Source Gates #716 /
40169845896 attempt 1 is terminal SUCCESS.

## Architecture 146 historical-data prerequisite

The weekend offline robustness diagnostic is blocked because
F:\AI\ai-trading-bot\data is empty and repository CSVs are synthetic
fixtures/examples.

Architecture 146 — Historical Research Data Custody and Partition Contract is
DESIGN ACCEPTED as a documentation-only checkpoint. It is not Architecture
145-B and grants no acquisition, holdout, promotion or production authority.

The frozen v1 design uses SPY only, Alpaca historical stock bars with exact
1Day/RAW/SIP/USD/asof=- semantics, and a same-vendor corporate-action sidecar.
Coverage/partition boundaries are fixed before acquisition/results:

    DEVELOPMENT  [2016-01-01T00:00:00Z, 2020-01-01T00:00:00Z)
    WALK_FORWARD [2020-01-01T00:00:00Z, 2024-01-01T00:00:00Z)
    FINAL_HOLDOUT[2024-01-01T00:00:00Z, 2026-10-24T00:00:00Z)

Development-visible normalized data will contain only DEVELOPMENT + WALK_FORWARD
rows under F:\AI\ai-trading-bot\data\research\arch146-v1. Final-holdout
bytes are designed for separate protected custody under
F:\AI\research-holdout\arch146-v1; neither path is created by the design.

The design records an important compatibility requirement: Architecture 145-A
binds one logical historical_data_fingerprint across all three partitions, while
physically split files have distinct current fingerprints. A new additive
Architecture-146 manifest/snapshot enforcement layer is therefore required; do
not reinterpret or rewrite accepted 145-A schemas.

Details:
[Architecture 146](architecture/146-historical-research-data-custody.md) and
[validation plan](validation/arch146-historical-research-data-custody-plan.md).

## Production boundary

No production deployment generation is frozen for the weekend. Normal safe-side
source/research development may continue on develop. Sunday night, select the
then-current exact terminal-green develop HEAD/TREE as the deployment candidate.

No real-host successor preflight, latch creation, production materialization,
ACL mutation, scheduler/runtime mutation, credential/provider access,
paper/broker effect, D1/D2 effect or live effect is authorized here. Live remains
NO-GO.

Architecture 145-B remains deferred until the fresh F1 successor soak; Research
Results GUI follows 145-B, then large strategy campaigns.

## Next step

Implement **Architecture 146-A — historical research dataset manifest and
partition enforcement** as a pure/source-only checkpoint using synthetic fixtures
only. It must add immutable manifest/commitment models and external verification
without network access, real data, real holdout paths, ACL mutation or
Architecture-145 schema changes.

Only after 146-A source acceptance/integration may a separately reviewed 146-B
acquisition/custody checkpoint be designed/run.

The production lane remains unfrozen until Sunday-night market-open preparation.

## Architecture 146-A feature source pending review

The additive synthetic-only implementation is being published from
`feature/research-arch146-a-historical-research-dataset-enforcement-current`,
based exactly on develop `724e027af44457fcc76f0055d9cc037f9f933a42` /
`eb561d6fd2b6812f54d333dfd7e12d2b5f532a44`. It adds strict immutable
partition manifests/snapshots, external integrity/session verification, distinct
physical and full logical fingerprints, an OPEN-only commitment boundary and an
additive Architecture-145 policy binding. Architecture-145 source stays frozen.

The checkpoint has source-only dispatch and CI-owned FULL. Terminal CI and
ChatGPT exact-source review are still required before acceptance/integration.
Existing NYSE historical-calendar limitations and future acquisition/provenance
requirements remain explicit in the Architecture-146 implementation notes.

Immediate next step: complete one atomic feature publication and terminal CI,
then ChatGPT exact-source review. Do not start 146-B acquisition, open a real
holdout, create eligibility, or cross any host/production/trading boundary.
