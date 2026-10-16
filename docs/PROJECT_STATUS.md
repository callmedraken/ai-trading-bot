# AI Trading Bot - Project Status

## Current phase

Architecture 134-D1R5 operational source remains accepted and the product line
is still waiting on the separately protected real pre-market
`WAITING_FOR_MARKET` / wake / source-readmission qualification. No protected
product effect is authorized by this documentation closeout.

Parallel safe-side research is now **SOURCE ACCEPTED through Architecture
139-B / RCL-3B** on
`feature/research-candidate-shadow-qualification-current`. The two independently
reviewed source checkpoints are:

```text
139-B1  HEAD 3bf604f407445da0c587cfd91545c113c99e341f
        TREE 732f75cc09c8296ce09f244edc36ca8bda61e7b7
        CI   #563 / 38664134287 / workflow_dispatch / attempt 1 / SUCCESS

139-B2  HEAD bf98553592d2ef740d6a6ffdc104c6cd28023379
        TREE 34627f90f3ad8fc441346cc3d567a3f15495219b
        CI   #564 / 38665480838 / workflow_dispatch / attempt 1 / SUCCESS
```

The B1 continuation PASS was internal permission to begin B2 only. Canonical
SOURCE ACCEPTED status for both exact commits is established by the final
independent ChatGPT GitHub review recorded in the Architecture-139 documents.

139-B is deterministic source-only research. B1 canonically models
caller-supplied, zero-effect SHADOW observations and independently reconciles
them to the accepted 139-A binding chain. B2 deterministically qualifies
coverage/provenance/no-effect integrity and may materialize only an immutable
`SHADOW` research successor. It adds no observation acquisition, provider,
credential, broker, paper, runtime, production compatibility, promotion,
`PAPER_CANDIDATE`, `AWAITING_HUMAN_PROMOTION`, D1/D1R5/D2, or live-trading
authority.

Parallel safe-side GUI presentation is now **SOURCE ACCEPTED through Architecture
140 / GUI-A17** on `feature/gui-research-candidate-lifecycle-audit-current`:

```text
A16 source  HEAD 6d092b8e05372d241dc4183b7b392f0eb83b4500
            TREE fd17ccfd338266c04d24dd03e303ee36dd72b0ca

A17 source  HEAD 56f3e8ef73f8aa62e2444c7fc9c75dfb212ff246
            TREE 5de6706064424aa4734b53cad4efffe5011284f4
            GUI  #10 / 38848617395 / push / attempt 1 / SUCCESS
            CI   #580 / 38848782422 / workflow_dispatch / attempt 1 / SUCCESS
```

A16 remains the only lifecycle acquisition/linkage boundary: one explicit local
five-artifact WALK_FORWARD_PASSED -> 139-A -> 139-B1 -> 139-B2 -> SHADOW set is
parsed and locally successor-verified, while complete historical/external-chain
qualification is explicitly not re-run.

A17 is presentation-only over the already acquired immutable A16 state. It adds
a Qt-free provenance/audit composer and improves the existing Research Lifecycle
page in place with five artifact identities, five retained source HEAD/TREE
pairs, three policy-vs-recorded coverage comparisons and margins, the exact nine
zero-effect counters, and the fixed no-authority governance matrix. It adds no
artifact reads, service getter, domain parser/verifier, lifecycle stage,
observation acquisition, production compatibility, promotion, provider,
credential, broker, paper, runtime, scheduler/ACL, D1/D1R5/D2, or live-trading
authority.

GUI #10 independently passed 984/984 tests with real PySide6 6.10.3. Checkpoint
#580 passed exact-source static gates and four broad shards at 90.745 / 71.385 /
52.168 / 104.792 seconds. Current parallel-line inventory is ACTIVE 64 / FULL
179 / ROBINHOOD 98 / LEGACY 221 / EXHAUSTIVE 400 / GUI 50.

The canonical bounded new-chat handoff/history branch remains
`feature/project-history-storage-foundation` on the active product lineage.
It and the active product branch currently remain at the bounded docs descendant:

```text
HEAD  7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343
TREE  c826c2a71e6d907866ce3f80afce479d38ab7842
```

Do **not** move that canonical history branch onto this parallel research
lineage absent a separately reviewed integration/replay.

Current accepted operational executable identity remains:

```text
branch  feature/robinhood-production-paper-premarket-wake-qualification
HEAD    a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a
TREE    9fcbc170e8339e0b4a93844466e8924ff8ef7f36
CI      #557 / 38549244176 / SUCCESS
```

Exact active product HEAD/tree must still be re-proven before any future
protected source admission. No fresh D1 session, PREPARE, EXECUTE, paper/broker
mutation, D2, real SHADOW acquisition, or live trading is authorized.

## Operational checkpoint

The one-shot D1R4 authentication qualification is **PASS / consumed**.

```text
evidence  F:\AI\temp\qualification\arch134-d1r4-auth-234614a21d68680f5b1e0ccd.json
bytes     635
SHA256    100e3590543b8ba36002d50d890578533100035b9f618434dd2c9adc2f3505c4
status    PASS
reason    PASS
HTTP      200
requests  1
source    234614a21d68680f5b1e0ccdb5854347a6a8d090
tree      f70459d91c393c6ea7a4a6358f02a2073b246574
```

The post-auth generation journal SHA-256 is
`344f64a1c421c41174142aa4f30f2574537bb26e70901dd77cf56ec930ec7434`;
its provider-effect fence is now irreversible. Authentication must not be retried.

The accepted fresh `/v3` provisioning effect was executed from:

```text
HEAD  ae19cc933f00445d00f196f7b7963bf01b5433ae
TREE  b361c153035ec1dca3ffacc5c819398239f55da6
```

Its preserved generation journal is:

```text
path    F:\AI\temp\qualification\arch134-d1r4-v3-generation-b206df8a30964c4c9a807d306b54c0b9.json
bytes   4881
SHA256  3cb18e50b821c4f7361b213f2095d148dd18a172f60cdf72255e36838eaa7ce3
schema  alpaca-v3-credential-generation-journal/v1
policy  windows-credential-manager-alpaca-market-data/v3
```

The journal is exactly:

```text
PROVISIONING_RESERVED -> LOCK_ACQUIRED -> EXPECTED_GENERATION
-> INITIAL_STATE_ACCEPTED -> KEY_WRITE_INTENT -> KEY_WRITE_CONFIRMED
-> SECRET_WRITE_INTENT -> SECRET_WRITE_CONFIRMED -> PAIR_CONFIRMED
-> FINAL / LOCAL_EXACT_MATCH
```

The expected UTF-8 lengths are key 26 and secret 44. The only accepted
classification is `LOCAL_V3_PAIR_EXACTLY_PROVISIONED`. There is no
`V3_PROVIDER_EFFECT_INTENT`, no Alpaca/provider request, and no ambiguity.
The provisioning invocation is consumed and must not be rerun. Ordinary fresh
`/v3` provisioning must block because the accepted staging pair exists.

The provisioning record alone did not establish remote authentication, but the
subsequent one-shot D1R4 qualification now does establish
`REMOTE_ALPACA_AUTH_READY` for the fixed accepted probe/source observation.
It does not establish D1 session, paper, D2, broker, or live-trading readiness.

## Completed foundations

- Architecture 131 provides the reviewed Robinhood paper, risk, execution, and
  audit foundation ([architecture/131-robinhood-review-paper-trading.md](architecture/131-robinhood-review-paper-trading.md)).
- Architecture 132 provides the tiered current/legacy certification model and
  source-gate topology ([architecture/132-tiered-certification-profiles.md](architecture/132-tiered-certification-profiles.md)).
- Architecture 133 preserves supervised immutable-release and unattended
  review-paper runtime boundaries ([architecture/133-robinhood-single-session-unattended-review-paper-authority.md](architecture/133-robinhood-single-session-unattended-review-paper-authority.md)).
- Architecture 134 is the current production strategy and AI-research
  authority ([architecture/134-production-strategy-and-ai-research-authority.md](architecture/134-production-strategy-and-ai-research-authority.md)).
- The D1R4 `/v3` provisioning contract and accepted evidence are preserved in
  [architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md](architecture/134-d1r4-alpaca-v3-provisioning-concurrency.md) and
  [validation/arch134-d1r4-alpaca-v3-credential-generation.md](validation/arch134-d1r4-alpaca-v3-credential-generation.md).

## Active work

The immediate product boundary remains the real pre-market start /
`WAITING_FOR_MARKET` / wake qualification. The independent Architecture
134-D1R5 source checkpoint is accepted at HEAD
`a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a`, TREE
`9fcbc170e8339e0b4a93844466e8924ff8ef7f36`, but its real bounded
clock/sleep/external-evidence qualification has not run.

Parallel safe-side research is closed through Architecture 139-B. Architecture
138 / RCL-2 remains SOURCE ACCEPTED at
`a9c3682231f8540be6e9dc6f2bfecd06ecf1a8b1` / tree
`55841f5119228dbf302747256326d43ff7d32e23`, CI #561 / `38634855492`.
Architecture 139-A / RCL-3A remains SOURCE ACCEPTED at
`bf500ffecefe0a8be8117e315228e3bc07ffdf54` / tree
`69d4ee1d6e7b3c2ca095b3ddf3cf05fdb7e3babd`, CI #562 / `38640090298`.
Architecture 139-B1 and 139-B2 are SOURCE ACCEPTED at the exact identities
recorded above.

The accepted 139-B domain boundary remains ACTIVE 64 / FULL 179 / ROBINHOOD 98 /
LEGACY 215 / EXHAUSTIVE 394 / GUI 44 at its source checkpoint. A16 advanced the
parallel GUI inventory to LEGACY 220 / EXHAUSTIVE 399 / GUI 49. A17 adds exactly
one new LEGACY GUI test module, yielding ACTIVE 64 / FULL 179 / ROBINHOOD 98 /
LEGACY 221 / EXHAUSTIVE 400 / GUI 50.

B1/B2, A16 and A17 use additive successor overlays only. A17 freezes the exact
A16 seven-path overlay digest
`887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f`
and its own seven-path overlay digest is
`dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3`.
All predecessor dictionaries, accepted 137/138/139 domain/test blobs,
executable/native/AST pins, ACTIVE membership, and workflow bytes remain frozen.
No research checkpoint is integrated into the active product/history lineage.

The 139-B source boundary is complete. No real SHADOW observation acquisition,
integration, promotion, production conversion, or later research architecture
is started by this closeout.

The D1R4 authentication PASS grants no PREPARE, EXECUTE, paper mutation, broker
placement, scheduler/ACL mutation, D1 launch, D2 invocation, or live-trading
authority.

## Current blocker / protected boundary

Remote Alpaca authentication is proven for the fixed probe and D1R5 source is
accepted, but the required real pre-market / `WAITING_FOR_MARKET` / wake
qualification has not yet been executed or accepted. No fresh D1 session is
authorized until that protected boundary is complete.
The D1R4 authentication invocation is permanently consumed and must not be
retried. Real-money trading is **NO-GO**.

## Verification and certification posture

Architecture 132 remains the governing posture:

```text
FOCUSED -> SOURCE-GATE CI
-> ChatGPT selects ROBINHOOD or FULL at a coherent current-product boundary
-> LEGACY / EXHAUSTIVE only when explicitly relevant
PROTECTED only at the exact separately reviewed effect boundary
```

Mapped certification remains CI-owned; local repetition of the same valid
profile is not routine. Checkpoint Source Gates #549 accepted the integrated
operational source: static authority and active tests passed, and canonical
ROBINHOOD certification passed 9,065 / 9,066 cases with one skip and zero
failures/errors in 200.417 seconds. Artifact `11875285428` has SHA-256
`02c29f3debd0cf274e85986ab5bd74ebbfc7b9ce9ec234e04fd9d3ad93240b2e`.
Current inventory after accepted D1R5 is FULL 175 / ROBINHOOD 98 /
LEGACY 215 / EXHAUSTIVE 390. The earlier #549 result remains historical
integrated-source evidence. Current D1R5/R3H acceptance is Checkpoint Source
Gates #557 / `38549244176`: static authority PASS, active tests PASS, canonical
ROBINHOOD 9,182 cases / 9,181 passed / one skipped / zero failed/errors, wall
253.493 seconds (below the frozen 300-second hygiene ceiling). FULL covers currently supported
functionality, while LEGACY/EXHAUSTIVE retain explicit historical
compatibility. This acceptance grants no protected authority. See the
[tiered certification profile](architecture/132-tiered-certification-profiles.md)
and [development workflow](AI_DEVELOPMENT_WORKFLOW.md).

## Roadmap

### Now

- Preserve the exact accepted Architecture 139-B1/B2 research identities,
  deterministic models, verifiers, seven-path successor overlays, and zero-effect
  boundary.
- Preserve accepted Architecture 140 / GUI-A16 acquisition/linkage semantics and
  GUI-A17 presentation semantics: A17 consumes only the already-acquired immutable
  A16 state, performs zero new artifact/service acquisition, and grants no
  external-chain acceptance, promotion, production conversion, or operational
  authority.
- Keep `feature/project-history-storage-foundation` on the accepted active
  product-lineage bounded-docs descendant. Do not fast-forward it to the
  parallel research branch.
- Keep the immutable HIST-2B snapshot unchanged.
- Preserve the consumed D1R4 authentication evidence and fenced generation
  journal.
- Preserve the accepted D1R5 source qualifier without executing its protected
  real clock/sleep/external-evidence qualification in this closeout.
- Keep all D1/PREPARE/EXECUTE/paper/broker effects and all real SHADOW
  acquisition stopped unless a later prompt separately reviews and authorizes
  the exact boundary.

### Next

- Production remains gated on the separately reviewed real D1R5 pre-market /
  `WAITING_FOR_MARKET` / wake / exact source re-admission qualification.
- The research lifecycle domain still stops at accepted Architecture 139-B.
  GUI presentation is accepted through Architecture 140 / GUI-A17. Further
  source-only GUI work must continue to consume already acquired presentation
  state unless a new protected acquisition boundary is separately designed and
  reviewed. No integration, production compatibility, promotion, or post-SHADOW
  lifecycle progression is implied by A17.

### Later

- Consider protected product or research effects only through their own explicit
  reviewed contracts, exact source admission, effect accounting, and
  reconciliation requirements.
- Keep live trading unavailable until every explicit production/live gate is
  implemented, accepted, and separately enabled.

## History and deep-reference pointers

The immutable snapshot is indexed at [docs/history/INDEX.md](history/INDEX.md).
Its exact files and manifest are under
`docs/history/legacy/HIST-2B-2026-10-13/`. The legacy snapshot is for targeted
audit and reconstruction, not routine startup. Read the relevant architecture
or validation record first; use Git history when exact source-era provenance is
required. Do not grow this dashboard back into a cumulative milestone journal.
