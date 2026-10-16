# AI Trading Bot - Project Status

## Current phase

The repository now has one **SOURCE ACCEPTED canonical integration candidate**
combining the accepted product/D1R6 lineage with the accepted Architecture
138/139 research and Architecture 140 GUI-A16/A17/A18 safe-side lineage:

```text
branch  feature/test-suite-canonical-handoff-integration-current
HEAD    e2b46c104168c007263c688450beb79d71637a94
TREE    eaec980bda6e0669878e54d622cb8694ef3e2fc4

CI      Checkpoint Source Gates #591 / 38957936922 / attempt 1 / SUCCESS
GUI     GUI Source Gates #20 / 38957942329 / attempt 1 / SUCCESS
```

Checkpoint #591 passed source-static and all four broad FULL shards at 88.401 /
73.968 / 92.000 / 63.715 seconds, all below the frozen 300-second hygiene
ceiling. GUI #20 passed the complete 1,001-test real-PySide6 suite plus Ruff and
diff checks. The integrated inventory is:

```text
ACTIVE 65 / FULL 180 / ROBINHOOD 99 / LEGACY 222
EXHAUSTIVE 402 / GUI 51
```

The integration is additive. It preserves the accepted D1R6 product source and
authority chain, the frozen Architecture-139 SHADOW research semantics, the A16
five-artifact local acquisition/linkage boundary, the A17 immutable audit
presentation, and the A18 read-only lifecycle boundary map. The A16/A17/A18
predecessor dictionaries and digests remain frozen; a separate seven-path
canonical integration overlay binds only the shared current inventory-test
bytes. No research promotion, production compatibility, post-SHADOW stage,
provider effect, scheduler mutation, trading effect, or live-money authority is
created by the integration.

The real October 16 D1R6 wake has also completed successfully. Read-only
post-wake reconciliation ran from exact published source:

```text
D1R6 local HEAD   a36de3bfe81a6e1a94fb3deeec7e579145939f52
D1R6 local TREE   6cde732e02e92eb2b34281672cdb7744250355b1
D1R6 remote HEAD  a36de3bfe81a6e1a94fb3deeec7e579145939f52
source admission  PASS

disposition        PASS
evidence           PASS
task               MATCH
reconcile exit     0
```

At the accepted D1R6 source, `PASS` requires canonical bounded D1R5 evidence
for the frozen target source/session ending in `FINAL / PASS`; scheduler state
cannot manufacture that result. The frozen D1R5 target remains:

```text
HEAD  7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343
TREE  c826c2a71e6d907866ce3f80afce479d38ab7842
```

The successful D1R5 sequence is therefore established as
`QUALIFICATION_RESERVED -> SOURCE_ADMITTED -> WAITING_FOR_MARKET ->
WAKE_OBSERVED -> SOURCE_READMITTED -> FINAL / PASS`. The reconciliation
reported every operational effect counter as zero. No ARM retry, operator task
run, task create/update/delete, evidence mutation, D1, PREPARE, EXECUTE, paper
mutation, broker placement, provider/credential access, D2, or live effect was
performed by the reconciliation.

The earlier October 15 fail-closed task incident remains immutable historical
evidence only; it is no longer the current product blocker. D1R5 PASS still
stops before D1 and grants no D1/PREPARE/EXECUTE/paper/broker/D2/live authority.

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

The October 16 pre-market wake qualification is **PASS and consumed for that
qualification attempt**. Do not rerun D1R5, do not rerun D1R6 ARM, and do not
treat the still-observed scheduler task as permission to run, update, delete, or
recreate it.

The accepted post-wake facts are:

```text
D1R6 source       a36de3bfe81a6e1a94fb3deeec7e579145939f52
D1R6 tree         6cde732e02e92eb2b34281672cdb7744250355b1
source admission  PASS
D1R5 evidence     PASS
task projection   MATCH
overall           PASS
effects           all reported zero
```

This proves the bounded D1R5 timing/wake/source-readmission gate. It does not
prove or authorize a D1 session, strategy evaluation, PREPARE, EXECUTE, paper
mutation, broker placement, D2, or live trading.

Parallel safe-side work is source accepted through Architecture 139-B and
Architecture 140 / GUI-A18. The research lifecycle remains stopped at SHADOW:
no `PAPER_CANDIDATE`, `AWAITING_HUMAN_PROMOTION`, production compatibility,
or promotion authority is materialized.

## Current blocker / protected boundary

The next protected product boundary is now a **separately designed and
source-reviewed D1-session authorization checkpoint that may consume the
accepted D1R5 PASS**.

Nothing in the D1R5 PASS or this repository integration authorizes that boundary
implicitly. Until a new exact contract is implemented, reviewed, admitted, and
separately authorized:

- do not invoke D1;
- do not invoke PREPARE or EXECUTE;
- do not perform paper or broker mutations;
- do not invoke D2 or live trading;
- do not rerun the consumed D1R6 arm or D1R5 qualification;
- do not manually run/update/delete/recreate the scheduler task merely as
  cleanup.

Any future scheduler cleanup/replacement is its own reviewed effect boundary,
not a side effect of accepting D1R5 PASS.

## Roadmap

### Now

- Preserve the exact accepted canonical integration source at
  `e2b46c104168c007263c688450beb79d71637a94` /
  `eaec980bda6e0669878e54d622cb8694ef3e2fc4`.
- Preserve the October 16 D1R6/D1R5 post-wake result as PASS / PASS / MATCH with
  zero reported operational effects and no retries.
- Keep the October 15 fail-closed incident as historical evidence only.
- Preserve Architecture 139-B SHADOW semantics and GUI-A16/A17/A18
  already-acquired-state presentation boundaries.
- Keep D1, PREPARE, EXECUTE, paper/broker, D2 and live effects stopped.

### Next

- Design and source-review the exact D1-session authorization boundary that may
  consume the accepted D1R5 PASS without expanding authority implicitly.
- Define any scheduler retirement/replacement operation separately if it is
  still needed; require its own effect budget, durable fencing and independent
  reconciliation.
- Keep the D1R5 evidence immutable; no rerun/resume/repair.

### Later

- Only after a separately accepted D1 authorization may the product proceed to
  the next bounded session step.
- Keep PREPARE/EXECUTE, broker effects, D2 and real-money trading behind their
  own reviewed gates.
- Continue safe-side GUI/research work only without creating production
  compatibility or promotion authority unless a new architecture explicitly
  reviews that transition.

## History and deep-reference pointers

The immutable snapshot is indexed at [docs/history/INDEX.md](history/INDEX.md).
Its exact files and manifest are under
`docs/history/legacy/HIST-2B-2026-10-13/`. The legacy snapshot is for targeted
audit and reconstruction, not routine startup. Read the relevant architecture
or validation record first; use Git history when exact source-era provenance is
required. Do not grow this dashboard back into a cumulative milestone journal.
