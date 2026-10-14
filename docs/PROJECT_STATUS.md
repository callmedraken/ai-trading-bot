# AI Trading Bot - Project Status

## Current phase

The project is in the Architecture 134 D1R4 local-staging and authentication-
qualification sequence. HIST-2B has completed the documentation/state-storage
cutover: the former cumulative current-state documents are preserved as an
immutable legacy snapshot, while this file and
`docs/AI_TRADING_BOT_HANDOFF.md` are bounded current-state documents.

The history-storage branch is not trading authority. HIST-2B is accepted: its
exact legacy snapshot is sealed, these bounded current documents are accepted,
and its integration changes documentation, history, and archive tooling only.
It grants no trading or provider authority. The operational product lane
remains:

```text
feature/robinhood-production-paper-alpaca-auth-qualification
```

The accepted HIST-2C.1 integration source base for this HIST-2B closeout is:

```text
HEAD  f156953b373aafbf80b6984752f65f3dc42caea1
TREE  40fcf475584b2145dc3b99f6af3a75273f21d84d
```

The pre-HIST-2 operational baseline was:

```text
HEAD  a2d4e4aca8e31fa9c72b4e21372c4d97f45b74fa
TREE  2d29744b4d116c9567fe8a5894f5adaece4578cf
```

That baseline is not the current operational branch tip. The accepted HIST-2
operational integration executable/test source is:

```text
HEAD  cb1971eaf22eb27690bf60a24d72b5db50c67c34
TREE  a39db98bec8a1096b8ee2cea6212bd0090953101
CI    #549 / 38522621732 / SUCCESS
```

At every protected source admission, exact current operational branch HEAD/TREE
must still be re-proven from local Git and origin; the accepted identity above
does not predict a later docs-only tip.

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

The immediate product boundary is now the real pre-market start /
`WAITING_FOR_MARKET` / wake qualification. The independent Architecture 134-D1R5
source checkpoint is accepted at HEAD
`a7f985c6e4c723fdd4c4a1c49798531ddabe9e4a`, TREE
`9fcbc170e8339e0b4a93844466e8924ff8ef7f36`, but its real bounded
clock/sleep/external-evidence qualification has not yet run.

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

- Keep the bounded status and handoff aligned with the exact operational D1R4
  state.
- Keep the immutable HIST-2B snapshot unchanged.
- Record and preserve the consumed D1R4 authentication evidence and fenced
  generation journal.
- Preserve the accepted [D1R5 timing/source qualifier](validation/arch134-d1r5-pre-market-wake-qualification.md)
  and its Architecture 132-R3H certification-hygiene proof.
- Review only the separate real bounded clock/sleep/external-evidence D1R5
  qualification next; it stops after wake/source proof and grants no D1 authority.
- Keep all D1/PREPARE/EXECUTE/paper/broker effects stopped until that source and
  operator boundary are separately accepted.

### Next

- Qualify pre-market start, durable `WAITING_FOR_MARKET`, wake timing, and
  exact source re-admission.
- Only after that qualification is accepted, review the next fresh D1 session
  authorization boundary.

### Later

- Consider D1, paper, broker-paper, and later live-readiness gates only through
  their own reviewed authority boundaries and reconciliation requirements.
- Keep live trading unavailable until every explicit production/live gate is
  implemented, accepted, and separately enabled.

## History and deep-reference pointers

The immutable snapshot is indexed at [docs/history/INDEX.md](history/INDEX.md).
Its exact files and manifest are under
`docs/history/legacy/HIST-2B-2026-10-13/`. The legacy snapshot is for targeted
audit and reconstruction, not routine startup. Read the relevant architecture
or validation record first; use Git history when exact source-era provenance is
required. Do not grow this dashboard back into a cumulative milestone journal.
