# Architecture 133 — Single-Session Robinhood Unattended Review-Paper Authority

Status: **frozen design checkpoint**. This document authorizes source/design work
only. It does not authorize scheduler mutation, unattended provider access,
Robinhood review requests, synthetic paper mutation, broker placement, or live
trading.

## 133-H — source prerequisite for protected Q133-2

Q133-1 was accepted at the exact 133-G closeout HEAD
`65f0d40217f8ce129224531a5151f4acea889d89`, TREE
`16cb734cbeaa9e97aaf9e2d521d922fbbc7b7ae2`. That branch/worktree remains the
runtime TARGET. The separate publisher lives on
`feature/robinhood-unattended-review-paper-133h` in
`F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133h`. Existing 133-G host
and scheduler identities are preserved. 133-H is source accepted at HEAD
`6c86105fcbd278758b3b782a53429eb246a72fb3`, TREE
`3404c5ff98cb9e5dd4e48e7121ba7167372be8bc`; source-gate #260 /
37549018483 passed. Fresh FULL current-supported certification passed 5,056
cases: 5,053 passed, 3 skipped, 0 failed, 0 errors, with evidence at
`F:\AI\temp\certification\arch133h-full-6c86105`. **Q133-2 has not been
executed.**

`scripts/run_arch133_host_publication.py` requires the shared production Python
under `-I -B`. Its explicit modes are `plan` and `execute-once`. Input travels
through `--material-file` or, for planning only, bounded binary stdin via
`--material-file -`. The maximum-32-KiB canonical UTF-8 envelope has exactly
`schema=arch133-host-publication-material/v1`, `activation_json`, and
`host_binding_json`. The last two values are canonical strings parsed by the
accepted `ReviewPaperActivation.from_json` and `HostBinding.from_json` contracts.
No BOM, trailing newline, duplicate/unknown field or noncanonical inner/outer
bytes is admitted. The publisher selects/generates no proposal, session, UUID,
risk limit, cash, slippage, commission, OAuth bound, or predecessor. The reviewed
binding supplies the expected empty-paper fingerprint for the activation's
canonical starting cash. Pure material admission derives the required empty
schema-v2 fingerprint from frozen columns, exact starting cash and zero rows;
a well-formed but wrong predecessor fails before native observation or mutation.
Planning constructs no scratch store. Execute independently verifies the actual
predecessor again after initialization.

Planning requires an elevated Administrators-authorized token, excluding Trading
and SYSTEM user tokens, and the exact standard Trading SID. It proves the pinned
local NTFS parent chain, protected runtime ACLs, exact Python path/version/hash,
target launcher hash, clean 133-G branch/HEAD/TREE/origin and clean 133-H publisher
path/branch/HEAD/TREE/origin. It proves the entire Arch133 namespace absent twice.
Bounded stdout evidence includes the full activation/binding semantic summary,
pure scheduler spec, host/source/security identities, material SHA-256 and plan
SHA-256. Changes to these facts require a new reviewed plan. Planning writes no
publication, store or evidence, reads no OAuth and accesses no provider,
Task Scheduler or broker surface.

Execute requires a material **file**, `--reviewed-plan-sha256`, a real interactive
terminal and the exact line `AUTHORIZE Q133-2 <reviewed-plan-sha256>`. Redirected
or piped authorization is rejected. Readiness precedes the prompt and repeats
under held parent guards before mutation; the native backend also requires
one-time arming. Q133-1 PASS, scheduler metadata and environment variables
provide no publication authority.

Publication order is fixed:

1. Exclusively create Arch133 with protected Administrators/SYSTEM-only
   owner/DACL and retain a no-delete root handle.
2. Construct `ReviewPaperStore` once with the exact activation starting cash;
   admit exactly one activation/READY wake through `UnattendedStateStore`.
3. Publish canonical `activation.json` and `host-binding.json` once each through
   fixed `.activation.json.pending` / `.host-binding.json.pending` names inside
   Arch133. Create-new, exact bounded write/readback, flush and same-parent
   Win32 WRITE_THROUGH rename exclude every replacement/copy/delete flag.
4. Apply exact protected final-file ACLs: Trading read-only semantic files and
   accepted concrete SQLite data rights without DELETE/WRITE_DAC/WRITE_OWNER.
5. Independently reopen/verify all four objects, canonical JSON, exact empty
   paper metadata/fingerprint and one READY revision-0 wake at activation
   creation time while the root remains Administrators/SYSTEM-only.
6. Apply the exact root owner/protected DACL through the local 133-H Win32
   boundary, which accepts only the reviewed ACE count/order/type/flags/masks.
   Independently inspect that ACL before marking Trading admitted; application
   or readback failure leaves internal admission false. Then repeat verification
   and require identical content/state evidence. Root grants file creation and
   read/list/traverse, with inherit-only child-data rights for future SQLite
   journals/operator evidence. It grants no delete-child, delete-root, ACL or
   owner authority. The four protected file DACLs exclude that inheritance.

Only `paper.sqlite`, `wake.sqlite`, `activation.json` and `host-binding.json`
remain. Operator evidence and no-pycache remain absent. Any occupied root,
partial/pending/extra/conflicting state, interruption, uncertain acknowledgement
or verifier disagreement stops without deletion, overwrite, migration, repair
or retry. Even identical complete publication blocks execute re-entry.
Sanitized result evidence is stdout only; Q133-2V's existing OAuth availability
observation is outside this publisher.

Reuse is limited to A103's public no-follow reader/pinned production-parent
guard, exact Win32 inspection, binary security attributes/policies and native
handle closure. D10/Paper-v2 provisioning/staging/deployment/task/lease/recovery
authority is not reused. Native qualification of the new role ACLs remains at
the separately protected Q133-2/Q133-2V gates; tests use fake Win32 boundaries
and disposable stores only.

The dedicated `arch133-robinhood-unattended-host-publication` source registration
has `preflight=None` and `execute=None`. Its structural checks pin the complete
operator/interlock/native composition, accepted store/verifier dependencies,
reused security primitives, exact registration and batch workflow. CI and
ordinary verify cannot invoke the protected publisher. After source acceptance,
review one actual external activation plan before **fresh** Q133-2 authorization.
No source PASS authorizes provisioning, scheduler access, provider wake or live
money.

## Decision

The next current-supported product step after Architecture 131 is one bounded
**single-session unattended simulated-paper wake** using the already-accepted
Robinhood review/read boundary.

Architecture 133 does not revive the historical D10 unattended deployment. D10
remains historical infrastructure with its scheduler disabled. Architecture 133
is a new current-product authority built from the accepted Architecture 131
review-paper primitives and the Architecture 132 certification model.

The first unattended scope is deliberately smaller than a multi-day soak:

- exactly one pre-authorized NYSE session;
- exactly one pre-authorized `TradeProposal`;
- at most one fresh quote acquisition;
- at most one risk decision;
- at most one Robinhood `review_equity_order` request;
- at most one synthetic local paper fill;
- zero automatic retry;
- zero historical catch-up;
- zero real-order placement/cancel/options/crypto authority.

A successful single-session qualification is evidence for a later separately
designed multi-session soak. It does not automatically authorize recurrence.

## Controlling Architecture 131 contracts

Architecture 133 composes, rather than replaces, the accepted current-supported
Robinhood review-paper line:

```text
131-S published NYSE regular-session authority
131-P bounded quote acquisition
131-N canonical risk-price snapshot
131-O durable forward-paper risk preview
131-Q PREPARE / EXECUTE invariants
131-K durable virtual-paper risk context
131-J deterministic paper pipeline
131-I review-paper intent bridge
131-H review-only Robinhood paper operator
131-A2 durable review-paper store / deterministic synthetic fill
131-LQ / 131-V independent evidence lessons
```

Architecture 133 must not call the interactive 131-V human challenge wrapper.
131-V remains the supervised human-started qualification surface.

The unattended authority must preserve the safety properties that 131-V proved
while substituting a separate bounded source-owned activation/wake authority for
the per-execution human challenge. It may reuse accepted 131-Q primitives only
through an explicitly reviewed Architecture-133 composition that proves the new
authority before any provider/effect boundary.

## Activation authority

The first Architecture-133 activation is immutable and binds exactly:

- schema/version;
- one deterministic activation ID;
- exact certified source/deployment identity;
- exact target NYSE session date;
- exact `TradeProposal`, including proposal ID, symbol, side, desired quantity,
  reason/confidence, and proposal creation time;
- exact `RiskLimits`;
- exact `new_trading_enabled` value;
- exact review-paper store identity/path and starting cash;
- exact opening/closing buffers;
- exact quote max age;
- exact slippage basis points and commission;
- exact local order UUID;
- exact zero-semantic-argument wake contract identity;
- activation creation time and terminal expiry rule.

The activation is single-use. It is not renewable in place and must not contain
a reusable provider credential, raw OAuth material, native handle, or broker
mutation capability.

The target session is explicit. The first unattended milestone does **not**
derive a missed historical session and does not search backward or forward for a
session to trade.

## Wake identity and durable state machine

One deterministic wake identity is derived from the activation ID, target
session date, proposal ID, and local order ID.

Before provider access the wake must durably classify the activation/wake state.
The exact state model must distinguish at least:

```text
READY
PREPARE_STARTED
PREPARED
REVIEW_STARTED
COMPLETED
STOPPED
INDETERMINATE
```

Names may be refined during source design, but these semantic distinctions are
frozen:

- no provider call occurs before durable wake admission;
- a previously COMPLETED wake is read-only/idempotent;
- a previously STOPPED wake is not retried automatically;
- a wake that may have crossed the review boundary is INDETERMINATE until an
  independent reconciliation proves the durable outcome;
- neither process restart nor scheduler replay manufactures fresh retry
  authority;
- the same activation can never produce two local order IDs or two paper fills.

A durable state write is local paper-control metadata only. It is not a
Robinhood order and carries no broker placement authority.

## One unattended wake

A valid wake performs at most this ordered sequence:

1. prove exact runtime/source identity and exact single-session activation;
2. read one current UTC instant and resolve the activation's exact target
   session through accepted 131-S;
3. require the wake is inside the exact admissible regular-session window;
4. prove the deterministic wake has no consumed/ambiguous prior effect;
5. reconstruct the exact durable review-paper account and proposal state;
6. acquire one accepted 131-P quote snapshot;
7. construct and independently validate the same risk-preview material required
   by the accepted supervised path;
8. require quote freshness and admitted session immediately before review;
9. durably mark the review boundary as started before invoking it;
10. invoke the accepted review-only 131-H/131-L composition at most once;
11. persist/reconcile the deterministic synthetic paper result;
12. independently reopen durable evidence and verify the exact completed state;
13. emit bounded sanitized wake evidence and close.

The source implementation may split these responsibilities into smaller
checkpoints. The ordering, one-attempt budget, and effect fences above are
contractual.

## Proposal authority

Architecture 133 v1 does **not** add autonomous proposal generation.

The exact proposal is frozen into the activation before unattended execution.
AI/research/strategy generation of future unattended proposals is a separate
future product authority. This keeps the first unattended qualification focused
on scheduling/effect safety rather than simultaneously introducing autonomous
strategy authority.

## Provider/effect budget

Per activation/wake:

```text
get_equity_quotes         <= 1 accepted PREPARE acquisition
review_equity_order       <= 1
get_accounts              only through the already-accepted 131-H operator
get_equity_orders         only through the already-accepted 131-H safety observer
place_equity_order         0
cancel_equity_order        0
place/cancel option        0
exercise option            0
place/cancel crypto        0
interactive OAuth reauth   0
retry                      0
historical catch-up        0
```

If persisted OAuth cannot be reused without interactive authorization, the wake
stops before review. Unattended mode must never open a browser or wait for a
human OAuth flow.

## Ambiguity and crash policy

A crash or exception before any provider effect may yield STOPPED only when
durable evidence proves the effect boundary was not crossed.

Once the review boundary is marked started, any exception, process death,
transport ambiguity, or missing terminal evidence is fail-closed
INDETERMINATE. The same activation may not retry the review request.

Independent reconciliation may prove that the deterministic local paper result
was completed. Reconciliation may not manufacture a second provider call or
synthetic fill.

## Session, stale, and missed-wake policy

The activation targets exactly one published NYSE session.

- before the admissible window: no effect;
- inside the admissible window: one bounded wake may proceed;
- after the quote/session deadline: STOPPED with no retry;
- wake first observed after the session's admissible window: MISSED_SESSION /
  equivalent terminal no-effect classification;
- different session date: fail closed;
- no previous-session or next-session catch-up;
- no automatic activation extension.

A missed first qualification requires a newly reviewed activation, not reuse of
the expired one.

## Scheduler boundary

Architecture 133 source work may define a zero-semantic-argument scheduler
contract, but may not mutate Task Scheduler.

The first protected deployment must create or update a distinct
Architecture-133 task. It must not repurpose or re-enable historical D10 tasks.

Scheduler state is wake-up plumbing and defense in depth, never the sole source
of activation/session/effect authority. The source-owned activation and durable
wake state remain authoritative.

Any scheduler mutation is a separately approved protected checkpoint after
source certification and host preflight.

## Evidence

Sanitized evidence must be sufficient to prove:

- accepted source/runtime identity;
- activation/wake/proposal/order identities;
- target session and exact admission times;
- quote observation/deadline and accepted risk material;
- durable BEFORE/AFTER paper fingerprints;
- review/operator evidence digest and exact call counters;
- wake state transitions;
- zero retry;
- zero real-order mutation counters;
- final independent reconciliation result.

Evidence must not contain OAuth tokens, credential-manager secrets, raw request
headers, account identifiers beyond already-sanitized accepted operator
material, or arbitrary exception text.

## Source checkpoint plan

### 133-A — activation + wake identity/state core — ACCEPTED

Network-free/source-only.

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133a
PARENT 10e72fc5c609802e2704bb6a8b40bd99e8782d6a
HEAD   b0751e1ff2109b7f99725910ee901685e293e175
TREE   2230e11bcb3a2b27171aaa506f12110c31ae77a0
CI     #227 / 37388706716 SUCCESS
```

Accepted behavior:

- immutable/slotted `ReviewPaperActivation` and `ReviewPaperWake`;
- closed canonical JSON round-trip with unknown/missing/noncanonical material
  rejected;
- UUID5 activation identity over versioned canonical semantic facts;
- repository-wide identity policy preserved: filesystem `store_path` is
  retained exactly in activation storage material but excluded from UUID5
  domain identity, while `store_identity` remains identity-bearing;
- exact proposal, risk-limit, source/deployment, target-session, paper-account,
  buffer, quote-age, slippage/commission, order, creation-time, wake-contract,
  and expiry facts retained in the activation;
- deterministic wake identity bound to activation ID + target session date +
  proposal ID + local order ID;
- exact states `READY`, `PREPARE_STARTED`, `PREPARED`,
  `REVIEW_STARTED`, `COMPLETED`, `STOPPED`, `INDETERMINATE`;
- no outgoing transitions from terminal states;
- failure before the review-start fence terminates as `STOPPED`;
- failure after `REVIEW_STARTED` can terminate only as `INDETERMINATE`;
- caller-supplied timezone-aware timestamps only, UTC canonicalization, and no
  system-clock read;
- Decimal canonicalization independent of ambient Decimal context;
- no UUID4/randomness, filesystem access, SQLite, environment/config, network,
  subprocess, MCP/OAuth/provider adapter, risk evaluation, paper mutation,
  scheduler, retry, polling, or sleep authority.

The source-only checkpoint
`arch133-robinhood-unattended-activation-core` is registered once immediately
after the accepted Architecture-131 checkpoint sequence. Source-gate #227
reported Ruff check/format PASS, git diff check PASS, stable source identity,
and `AUTHORITY[arch133-robinhood-unattended-activation-core]=PASS`.

Focused implementation verification reported 233 core cases, 1,018 runner
cases, and the two profile-inventory cases across the focused/corrected-failure
runs, with Ruff and staged/diff checks passing. No FULL/ROBINHOOD certification
is required at this pure-model checkpoint; Architecture 132 reserves those for
the later coherent Robinhood/current-product boundaries.

### 133-B — durable wake store + provider-free reconciliation — ACCEPTED

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133b
PARENT 0609c08d2a3dd89b773c3416b629f377d04264ad
HEAD   e27ce1c2cebf38654404a96c06275e892909b2f5
TREE   37781465d0385aaa1251349ebb21fa5af59357c0
CI     #229 / 37392099387 SUCCESS
```

Accepted behavior:

- dedicated closed Architecture-133 SQLite state schema separate from the
  Architecture-131 review-paper ledger;
- exact canonical 133-A activation/wake JSON persisted with deterministic
  activation/wake identity binding;
- state-database path remains transport metadata and never enters deterministic
  identity material;
- exact-identical activation reopen is read-only/idempotent;
- same activation ID with different canonical activation bytes is a hard
  conflict, including a changed serialized paper-store path;
- first activation + READY wake admission is atomic;
- monotonic integer revision and exact one-shot optimistic compare-and-swap;
- transition legality is delegated to accepted 133-A rather than reimplemented;
- stale/conflicting writers fail closed with zero internal retry;
- terminal and INDETERMINATE state survives close/reopen with no restored
  transition authority;
- complete metadata/activation/wake snapshot is explicitly sorted and
  deterministically fingerprinted;
- independent verifier opens SQLite through URI `mode=ro`, never constructs
  the writer, and returns frozen/slotted sanitized verification facts;
- malformed schema/metadata, partial rows, noncanonical JSON, duplicate/binding
  conflicts, invalid revisions, and expected-state disagreement fail closed;
- embedded Architecture-131 paper-store material remains inert during normal
  admission/transition/verification paths;
- no provider/OAuth/risk-manager/review/paper-fill/scheduler/subprocess/
  environment/config/clock/retry/polling authority is introduced.

The source-only checkpoint
`arch133-robinhood-unattended-state-store` is registered exactly once after
133-A with `preflight=None`, `execute=None`, and no trusted remote-head
handoff. Source-gate #229 passed the 34-participant optimized batch, Ruff
check/format, git diff check, source identity stability, and both 133-A/133-B
authority pins.

Focused implementation verification reported 107 store/verifier cases, 233
activation-core cases, 1,067 runner cases, and 450 certification-inventory cases
across focused and corrected-failure runs. No ROBINHOOD/FULL certification is
required at this local-durability-only checkpoint.

### 133-C — effect-free one-wake composition — ACCEPTED

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133c
PARENT 4b86018fffce8e46ec348cc5aeddf0a8657d824b
HEAD   3f5a5b673bc9d66409e415152d6252cd80a46e3a
TREE   7b048cedea8a97501198311229b25ab32f112735
CI     #231 / 37410294723 SUCCESS
```

Accepted behavior:

- one source-owned coordinator/result boundary for exactly one activation/wake;
- exact accepted 133-A activation, exact 133-B persisted wake/revision, explicit
  caller-supplied instants, and no system-clock read;
- exact target-session resolution through accepted 131-S and admission through
  accepted 131-M with the activation's frozen buffers;
- durable READY -> PREPARE_STARTED before the quote seam;
- one quote/preparation seam invocation maximum;
- exact accepted 131-N snapshot plus 131-O/K preview/risk material;
- earliest exact source-mark freshness deadline, with no extension or
  reacquisition;
- durable PREPARE_STARTED -> PREPARED before final predecessor/risk/freshness
  revalidation;
- durable PREPARED -> REVIEW_STARTED before the fake effect receives control;
- one fake review/paper-effect invocation maximum;
- successful exact acknowledgement -> COMPLETED once;
- post-effect exception/ambiguity -> INDETERMINATE with no retry;
- pre-effect rejection, stale/expired session, material drift, or exception ->
  STOPPED with zero effect attempts;
- terminal replay is read-only with zero quote/effect calls;
- PREPARE_STARTED/PREPARED/REVIEW_STARTED reopen is reconciliation-only and
  performs zero new provider/effect calls;
- bounded immutable sanitized result facts only;
- no production Robinhood transport/OAuth/operator/pipeline/scheduler/mutation,
  subprocess/config discovery, polling/sleep/retry/catch-up/fallback authority.

The source-only checkpoint
`arch133-robinhood-unattended-one-wake-composition` is registered exactly once
after 133-B with
`remote_branch=feature/robinhood-unattended-review-paper-133c`,
`preflight=None`, `execute=None`, and no trusted remote-head handoff.
Source-gate #231 passed 35 optimized checkpoints, 60 test paths, 96 Ruff paths,
Ruff check/format, git diff check, source identity stability, and the
133-A/133-B/133-C authority pins.

Focused implementation verification reported 2,084 distinct cases: 87
composition, 340 overlapping 133-A/133-B, 1,545 runner/inventory, and 112
accepted 131-Q cases. Current certification inventory is FULL 119, ROBINHOOD
46, LEGACY 204, EXHAUSTIVE 323. No ROBINHOOD/FULL certification is required at
this fake-only composition boundary.

### 133-D — bounded unattended review-paper execution — ACCEPTED

Accepted source identity:

```text
BRANCH feature/robinhood-unattended-review-paper-133d

IMPLEMENTATION
HEAD 14bc4902a231fc87f8449c5971f2f8a9b382cc6e
TREE 084c8b794e3aa6f2795ef70deb70f92b92842bcd

CI-RECOVERY SAME-TREE HEAD
HEAD 6677676170fa9ffb70ca62809c03b2df40ca1253
TREE 084c8b794e3aa6f2795ef70deb70f92b92842bcd

SOURCE-GATE #234 / 37413871721 SUCCESS
```

The original implementation push received no GitHub workflow run despite the
already-reviewed Robinhood branch-family trigger. No missing run was treated as
acceptance. A single no-file-change fast-forward commit preserved the exact
implementation tree and retriggered the gate. #234 passed the 36-checkpoint
optimized batch, 61 test paths, 98 Ruff paths, Ruff check/format, diff check,
stable source identity, and all 133-A/B/C/D authority pins.

Accepted behavior:

- one source-owned 133-D binding around the accepted 133-C coordinator; no
  duplicate wake state machine or transition authority;
- persisted OAuth read exactly for the bounded provider path, with no browser,
  interactive challenge, token refresh, discovery/registration, or credential
  write authority;
- exact required-symbol validation and one Robinhood quote request maximum;
- accepted 131-N snapshot construction with the activation's frozen freshness
  policy;
- independent durable REVIEW_STARTED verification before review-paper operator
  control;
- exact proposal/risk/order/store/source material preserved and revalidated;
- deterministic market-order intent uses the activation's frozen local order ID;
- accepted 131-H review-paper operator invoked at most once;
- successful acknowledgement requires exact PASS evidence, expected call
  budgets, exact synthetic paper record, deterministic idempotency, and zero
  placement/cancel/options/crypto mutation counters;
- quote/OAuth/provider failure before the 133-D effect boundary is STOPPED;
- exception, malformed acknowledgement, process/transport ambiguity, or inability
  to prove the exact result after effect entry is INDETERMINATE;
- terminal/reconciliation replay performs zero new provider/review effects;
- no quote reacquisition, fallback session, catch-up, polling, sleep, retry,
  scheduler mutation, environment/config discovery, autonomous proposal
  generation, or broker/live effect.

The source-only checkpoint
`arch133-robinhood-unattended-review-paper-execution` is registered exactly once
after 133-C with
`remote_branch=feature/robinhood-unattended-review-paper-133d`,
`preflight=None`, and `execute=None`.

Required ROBINHOOD certification passed on the exact accepted tree:

```text
profile robinhood PASS
robinhood-1: 1893 / 1893
robinhood-2: 1899 / 1899
total:       3792 / 3792
skipped: 0
failed:  0
errors:  0
evidence: F:\AI\temp\certification\arch133d-robinhood-667767
```

Current certification inventory is FULL 120, ROBINHOOD 47, LEGACY 204,
EXHAUSTIVE 324. FULL remains deferred to 133-F.

### 133-E — zero-argument host/scheduler source surface — ACCEPTED

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133e
PARENT c24039f229b66f1d5510cf8e5c317cc8d0cbafc5
HEAD   ee542d5decf9b9fb1933a0a8681ee0c5cae29f27
TREE   274e2097c86a7cf41efa9e7af41f7324686d1ff7
CI     #236 / 37427681435 SUCCESS
```

Accepted behavior:

- fixed Architecture-133 launcher with zero semantic command-line arguments and
  sanitized rejection before trading-source import;
- exact source HEAD/TREE, runtime executable/version/launcher digest, Trading
  principal, and deployment identity admission before OAuth/provider access;
- one fixed host binding, activation publication, wake store, paper store, and
  evidence location; no CLI/environment path or trading-authority injection;
- exact canonical activation bytes and dedicated wake-state binding before
  execution composition;
- one initial admission clock read plus exactly one post-quote response clock read for an admitted READY wake;
- at most one delegation to accepted 133-D and no retry/polling/catch-up loop;
- persisted-OAuth-only execution path and provider-free persisted-OAuth
  availability metadata for preflight;
- terminal and reconciliation-only wake states return read-only with zero
  133-D/provider delegation;
- immutable single-session scheduler spec with task identity distinct from D10,
  zero semantic arguments, IgnoreNew overlap policy, zero restart/repetition
  authority, and explicit session start/end boundaries;
- scheduler/task state never creates activation/effect authority;
- no Task Scheduler query/mutation surface in the scheduler module;
- provider-free Q133-1 preflight verifies exact source/runtime/activation/wake,
  paper predecessor, OAuth availability metadata, proposed scheduler spec, and
  zero consumed wake authority without invoking 133-D;
- bounded sanitized host/preflight evidence with no credentials, account IDs,
  raw provider payloads, arbitrary exception text, or secret-bearing CLI/env
  material.

The source-only checkpoint
`arch133-robinhood-unattended-host-scheduler-surface` is registered exactly
once after 133-D with
`remote_branch=feature/robinhood-unattended-review-paper-133e`,
`preflight=None`, and `execute=None`.

Focused verification reported 1,051 distinct cases: 80 host, 356 runner, 2
inventory, and 613 overlapping tests. Source-gate #236 passed 37 checkpoints,
62 test paths, 103 Ruff paths, Ruff check/format, git diff check, stable source
identity, and all 133-A/B/C/D/E authority pins.

Current certification inventory is FULL 121, ROBINHOOD 48, LEGACY 204,
EXHAUSTIVE 325. No separate ROBINHOOD rerun is required at 133-E because the
accepted 133-D provider/review-paper effect boundary was not changed.

Architecture-124's historical sealed pre-source D10 guard remains historical
one-week-soak precedent, not an Architecture-133-v1 requirement. 133-E's frozen
single-session contract requires exact source/runtime admission before
OAuth/provider access; native deployment/ACL qualification remains a separate
protected gate.

### 133-F — final source certification — ACCEPTED (corrected PR source)

The original 133-F certification was superseded during PR #26 review after an
integration-level timing defect was found before merge. The production host had
reused a pre-request timestamp for quote observation and final pre-effect
validation. The corrected source now observes time once after the single quote
response and advances the final session/freshness fence to that later
observation, without adding retry, reacquisition, polling, or catch-up authority.

Final corrected certified source:

```text
BRANCH feature/robinhood-unattended-review-paper-133e
HEAD   2fa3ec574e0a0d0c3e0cf20211b12bf2c7921b62
TREE   46f5514c8fbe57af592237772a5a8cf73bf8194e
PR SOURCE-GATE #247 / 37438768450 SUCCESS
```

The corrected source gate passed 37 checkpoints, 62 test paths, 103 Ruff paths,
pytest/Ruff/diff checks, stable source identity, and all Architecture-133
authority pins.

Fresh FULL certification passed on that exact corrected tree:

```text
profile full PASS

broad-1
modules 58
cases 2721
passed 2721
skipped 0
failed 0
errors 0

broad-2
modules 63
cases 2124
passed 2121
skipped 3
failed 0
errors 0

TOTAL
cases 4845
passed 4842
skipped 3
failed 0
errors 0
wall 304.855 s
evidence F:\AI\temp\certification\arch133-timing-full-2fa3ec5
```

Architecture-132's profile classifier enforces
`ROBINHOOD ⊆ FULL`, so the fresh FULL run re-certifies the complete current
Robinhood subset on the corrected source. The historical dedicated 133-D
ROBINHOOD run remains provenance for the first coherent Robinhood boundary; no
second redundant Robinhood-only run is required after this corrected FULL PASS.

PR #26 remains the integration vehicle. Merge is allowed only after exact
head/tree, clean mergeability, review-thread resolution, and computed merge-tree
verification. The merge itself does not authorize Q133 protected effects.

## Integration — ACCEPTED

Architecture 133 was merged through PR #26 after the timing correction, exact
review-thread resolution, corrected FULL certification, clean mergeability, and
byte-exact merge-tree verification.

```text
PR       #26
BASE     10e72fc5c609802e2704bb6a8b40bd99e8782d6a
PR HEAD  4bbefe37f4ce52d085791982c7a86e6460460b3e
MERGE    b9ec5ea782ab14600a96de938cc16831557c1866
TREE     1936813b864dee7ab1263800ce76b65cd4c78e4e
POST-MERGE SOURCE-GATE #250 / 37445845063 SUCCESS
```

The merge tree exactly equals the reviewed PR-head tree. Post-merge source gate
#250 passed 37 checkpoints, 62 test paths, 103 Ruff paths, pytest/Ruff/diff
checks, stable identity, and all Architecture-133 authority checks.

Architecture 133 is integrated and source-complete. No integration result grants
any protected qualification authority.

### 133-G — pre-publication host bootstrap correction — ACCEPTED

The original 133-E "Q133-1 preflight" required already-published host binding,
activation, wake-state, paper-store, and persisted-OAuth metadata and therefore
could not prove the host before publication. 133-G separates that concern.

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133g
HEAD   4677ba442eafdcec56933b992f230a702012d573
TREE   6ce181b2900df0bf8c88cdd7509eb86a2b36d8dc
CI     #256 / 37527021604 SUCCESS
FULL   4,878 passed / 3 skipped / 0 failed / 0 errors
evidence F:\AI\temp\certification\arch133g-full-4677ba4
```

133-G reuses the already protected shared Python substrate only:

```text
F:\AITradingBot\runtime\python.exe
Python 3.14.3
SHA-256 cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b
```

D10 task/deployment/lease/scheduler authority remains distinct and is not
reused. The new zero-argument Q133-1 bootstrap requires the Architecture-133
host root to be absent before and after exact Trading-principal/source/runtime
qualification and has no OAuth/provider/scheduler/publication/store/broker
effect surface. The former 133-E preflight remains available only as
post-publication **Q133-2V** verification.

## Protected qualification sequence

No protected step is authorized merely by this document or by certification.

After 133-G source acceptance, the intended protected sequence is:

1. **Q133-1** provider-free/read-only pre-publication host bootstrap;
2. separately authorize **Q133-2** publication/provisioning of one exact
   single-session activation and host material;
3. **Q133-2V** provider-free/read-only post-publication verifier;
4. separately authorize **Q133-3** Architecture-133 scheduler
   installation/update;
5. separately authorize **Q133-4** observation of the first unattended provider
   wake;
6. **Q133-5** independent provider-free reconciliation;
7. **Q133-6** disable/expire the one-session task/activation before review;
8. only after acceptance decide whether to design a multi-session soak.

Each protected effect step has fresh authority. A source/CI/certification PASS
never grants the next effect.

## Explicit non-goals

Architecture 133 v1 does not authorize or implement:

- real Robinhood order placement or cancellation;
- options or crypto trading;
- broker-paper/live-money execution;
- autonomous AI proposal generation;
- multi-day recurring soak authority;
- automatic catch-up/backfill;
- provider retry after ambiguity;
- browser-based unattended OAuth;
- D10 task/deployment/lease/scheduler authority reuse; the already protected
  shared Python interpreter may be reused only under the exact 133-G runtime
  identity;
- production deployment as part of source implementation.

Production/live real-money placement remains **NO-GO**.
