# AI Trading Bot - Current Handoff

## Current milestone: Architecture 148-B2-A accepted/integrated; B2-B separately reviewed


Current product authority is [Architecture 148](architecture/148-tqqq-sqqq-runtime-pivot.md). It replaces further L43 checkpoint accretion as the application architecture while retaining accepted Architecture-147 safety components as reusable infrastructure and historical evidence.

V1 scope is fixed: intraday-only, long-only, at most one of TQQQ/SQQQ, QQQ as the primary direction reference, two completed-bar confirmation, no same-cycle inverse flip, and forced flat beginning five minutes before official regular-session close. The source-owned hard stop is 3.00% below the reconciled average entry fill and may never be widened. Live readiness requires proving exact full-position stop protection; a broker stop-market order is preferred and software independently treats threshold breach as mandatory EXIT.

Primary application reference: `siropkin/robinhood-ai-trading-bot@1a778749cfbe92c7ab9444b12e3cc73587533ade` (MIT). 148-A used its simple cycle shape as a reference while retaining the repository's stronger deterministic risk, MCP boundary and durable reconciliation contracts; its direct `robin_stocks` credential path, generic write retry, prompt-only risk limits and non-durable order handling were not adopted. The accepted parity matrix is `docs/validation/arch148-runtime-parity.md`.

148-A is accepted/integrated at `df48cdd40bcd18f2bfdc65dda201cfe2b6f199bd` / tree `2e139bdd886ee6ce8f92da57cc11ea38f341114f`, parent `ec0f33b7c15521c1901d749d5a933564360448c7`. Feature mapped FULL `44411012023`, attempt 1, is SUCCESS. Develop `44423510835`, attempt 1, is SUCCESS with exact feature-certification reuse, stable identity and no duplicate FULL. Real provider calls and broker effects were zero.

### Architecture 148-B2-A accepted/integrated identity

B2-A is accepted and integrated at HEAD `6957afa159647ece18af876289d8a20637cfc6eb` /
tree `43701fcaef23990a793359d08a8213d43e434780`, direct parent
`0f188ed75216855bc13077ed959ae92bc7463222`. Feature source-gate run
`44485930260`, attempt 1, is terminal SUCCESS with active tests and all seven
canonical FULL lanes green. Develop source-gate run `44489803571`, attempt 1,
is terminal SUCCESS with exact feature-certification reuse; the exact-develop-
reuse step passed and active tests, `full-tests`, `certification-tests` and
`certification-full` were skipped. No duplicate seven-lane FULL ran.

The canonical feature worktree is
`F:\\AI\\worktrees\\ai-trading-bot-live-prototype-current`; the local
integration checkout is `F:\\AI\\worktrees\\ai-trading-bot-p4-integration-e5e800a`.
Both were verified at the accepted source identity with clean tracked/index/
untracked state, and both live remote refs now point to the accepted HEAD.
B2-A is source-only/fake-only. No Alpaca credential read, provider request,
Robinhood/broker action, production mutation or `FINAL_HOLDOUT` access occurred.

The next boundary is one separately reviewed real read-only B2-B acquisition
attempt on this exact integrated source. This closeout authorizes no Alpaca
credential/provider access, retry or fallback. ChatGPT must review and issue
the exact one-shot B2-B invocation; do not run B2-B from this handoff alone.

Architecture 148-B1 is accepted/integrated at `68b9526f022458cbcdd4f25ff268e0de7c56e562` / tree `85e4830e71cb3b0ab5e85c5da9131f90f7ce575b`. The initial B1 commit `70b0a8de5cb3b2cf4fb826352b6ada3650c57614` remains preserved with green run `44432367772` but was exact-source rejected; corrective C1 closed the reviewed defects. Feature mapped FULL `44438409583`, attempt 1, is SUCCESS. Develop `44465681331`, attempt 1, is SUCCESS with exact feature-certification reuse, stable identity and no duplicate FULL. The operator integration report records both canonical F: worktrees and both live refs at the exact accepted HEAD/tree and clean; the feature checkout required no catch-up.

The B2-A source checkpoint is complete. B2-B remains a separately reviewed
READ_ONLY historical-data acquisition/qualification on the accepted B1 OPEN
contract and exact integrated B2-A source. This closeout authorizes no provider
access, credential read, Robinhood/broker action, production mutation or
`FINAL_HOLDOUT` access.


### Architecture 148-B1 accepted intraday identity

- HEAD: `68b9526f022458cbcdd4f25ff268e0de7c56e562`
- tree: `85e4830e71cb3b0ab5e85c5da9131f90f7ce575b`
- direct parent / initial B1: `70b0a8de5cb3b2cf4fb826352b6ada3650c57614`
- integrated develop predecessor: `9237cfe5fe3b617e00f7b2885ab171eb06542334`
- original B1 mapped FULL: `44432367772`, attempt 1, terminal SUCCESS, preserved but exact-source rejected
- C1 mapped feature FULL: `44438409583`, attempt 1, terminal SUCCESS
- develop source gate: `44465681331`, attempt 1, terminal SUCCESS
- develop reuse: `DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`
- develop identity: `IDENTITY_STABLE=True`
- duplicate develop FULL: NO
- OPEN interval: `[2016-01-01, 2024-01-01)` UTC
- symbols: `QQQ`, `TQQQ`, `SQQQ`
- timeframe / basis: `5Min` / `ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1`
- schedule identity: `4fe981d0-34ef-57be-a7d1-ffd017460bf5`
- schedule SHA-256: `a33be70499cdafbfa21f45a04c854ab834425807b6c0314814b7442749aa2bad`
- source/provider/credential/broker/production/FINAL_HOLDOUT effects during B1: zero
- B2: NOT RUN / separately reviewed READ_ONLY boundary

The accepted B1 simulator executes signals no earlier than the next bar open, then activates the 3% hard stop immediately for the entry bar. Entry-bar gap-through exits use the bar OPEN; otherwise a LOW breach exits at the stop threshold. The shared `live_runtime.strategy.confirmed_regime_exit` rule is used by both runtime and research paths. Dataset and custody schemas are v2 and bind the Architecture-148 schedule commitment separately from the Architecture-146 session-date authority.

### Architecture 148-A accepted runtime identity

- HEAD: `df48cdd40bcd18f2bfdc65dda201cfe2b6f199bd`
- tree: `2e139bdd886ee6ce8f92da57cc11ea38f341114f`
- direct parent: `ec0f33b7c15521c1901d749d5a933564360448c7`
- feature mapped FULL: `44411012023`, attempt 1, terminal SUCCESS
- develop source gate: `44423510835`, attempt 1, terminal SUCCESS
- develop reuse: `DEVELOP_CERTIFICATION_REUSE=True / exact_feature_certification`
- develop identity: `IDENTITY_STABLE=True`
- duplicate develop FULL: NO
- provider/broker effects during source work/review/integration: zero
- live-promotion blockers retained: whole-share protective-stop compatibility under the <=$10 canary; approval-ID linkage for approval-originated provider orders

`ARCH148_A_CONNECTOR_INTEGRATION_MECHANISM_DEVIATION` is preserved: ChatGPT used a leased non-force GitHub ref fast-forward for develop in the connector-only review turn instead of the preferred admitted local `merge --ff-only` + ordinary push. Exact accepted history/tree and develop reuse were preserved; do not treat this as the normal integration method.

Canonical feature worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`.
Branch: `feature/robinhood-live-prototype-current`.

Preserved accepted/integrated L43-Q1 predecessor identity:
- L43-Q1 HEAD: `05f4c4700f82c3d40c83f474c3cf614573d48091`
- tree: `70aec1c51e63705a68d6710cc3448ac994227e46`
- direct parent: `f38c3079d83f5e9773280fe36e43a4d9d9d3c76d`
- feature mapped FULL: `44260469616`, attempt 1, terminal SUCCESS
- develop exact-source run: `44264566809`, attempt 1, terminal SUCCESS
- develop reuse: exact feature certification
- develop identity stability: `IDENTITY_STABLE=True`
- duplicate develop FULL: NO
- accepted RHC4-C2 ancestor: `4f560a74b04ecba85c7b312364a9e4e7b30e57b6` / `b422ef66d88b184bdbe12788546e6b2ffd083846`

Preserved predecessor evidence:
- original RHC4 `2f4f50a1df44c261d172f55bc540b635d637cbd9` / tree `558e2f8c1f930d3f15810dea3f01a92ca20fdc24`; mapped run `44181143712` terminal SUCCESS but exact-source rejected;
- RHC4-C1 `f3f44e00ec17279ea74445df2b7a680875745f7b` / tree `8dac42fa7039bde8fdb6f6bdd63eeaf432cb049a`; run `44192574584` terminal FAILURE / `PREPUBLICATION_COVERAGE_DEFECT`;
- first clean C2 admission `F:\\AI\\temp\\ai-trading-bot-checkpoints\\arch132-r3n-prepublication-admission\\source-gate-20261118T012223.701722Z\\report.json` remains `PREPUBLICATION_ADMISSION_PORTABILITY_DEFECT`;
- final C2 admission `F:\\AI\\temp\\ai-trading-bot-checkpoints\\arch132-r3n-prepublication-admission\\source-gate-20261118T013037.569843Z\\report.json` passed FEATURE and PROSPECTIVE_DEVELOP with stable identity, `2692 passed, 1 skipped`, Ruff PASS and diff PASS.

RHC4-C2 is production composition source, not real-order evidence. Its default production exact-plan authorizer denies. Start/Stop does not grant trading authority. Pending bound orders settle through accepted RHC3P factual reads first. The serialized lifecycle interlock orders Stop against the transition into ENTRY placement, SELL nonplacing review and SELL placement. Import, construction and help remain effect-free. No RHC4 real Robinhood/OAuth/browser/MCP/Alpaca/review/place/cancel action occurred during source implementation, certification or integration.

### Q62 retained state and consumed observation

Q62 source was accepted/integrated before RHC4. Its create-once local state is consumed and must never be reinitialized:

- journal: `F:\AI\arch147-q62-live-state-v1\durable-state.jsonl`
- bytes: `806`
- SHA-256: `21F6C07273226D467F85CC8B86DED104B58A94C456E81C67521F94D8CC7CA7D1`

The separately reviewed protected read-only Q62 observation was consumed successfully:

- status: `READY_FOR_L43_PROTOTYPE_READ_ONLY`
- reason: `Q62_READ_ONLY_PREREQUISITES_PROVEN`
- evidence: `F:\AI\temp\arch147-q62-tiny-live-readiness-ecd813dcb93f4f66bb7f9adce592ed42\evidence.json`
- bytes: `11,663`
- SHA-256: `4D08EB505651CEB551BF6D94BB87960F14940925263D3E682B62610A063FC9C9`
- PROVEN: SOURCE, CONFIGURATION, ACCOUNT, CAPABILITY, OWNERSHIP, BUDGET, SESSION, SIGNAL_INPUTS, RECOVERY
- Robinhood reads: get_accounts=1, get_equity_positions=1, get_equity_orders=1
- Alpaca snapshot/provider call: 1
- review/place/cancel/other Robinhood calls: 0
- provider mutations: 0
- live readiness: false
- trade authority: false
- disposition: `CONSUMED / NO AUTOMATIC RETRY`

RHC2 remains `CONSUMED / PASS / NO RETRY`. RHC3 retained account-wide-all-agents order-scope evidence remains immutable and operationally required. Q62 evidence is an anchor, not current effect authorization.

### Workflow deviations preserved

`RHC4_C2_PREPUBLICATION_ATOMICITY_DEVIATION` records that C2 was published as two unpublished commits (`7dfd693b...` then `4f560a74...`) in one push rather than one atomic checkpoint commit. Do not rewrite published history.

`RHC4_C2_TRANSITION_WORKFLOW_REGRESSION` records that the first ChatGPT integration guard Boolean-tested `git diff --quiet` stdout and falsely stopped a clean worktree. The broader transition also failed to follow existing procedure in several places: remembered-path use instead of same-block worktree discovery/reproof, incomplete first cleanliness proof, unsafe native stderr handling, output parsing before native-exit classification, missing canonical-origin/final-cleanliness proof, oversized generated PowerShell, incorrect delegation of the tiny docs closeout, delayed automatic continuation, failure to batch the known L43-Q1 design freeze with the closeout, and an initially missed stale current Q62 summary. The diagnostic re-established exact clean state before successful integration. These are workflow/procedure regressions, not source defects.

`RHC4_C2_CLOSEOUT_C1_DOCS_HYGIENE_DEFECT` preserves direct docs run `44239165344`, attempt 1, terminal FAILURE. Its only source-static defect was one new blank line at EOF in each newly added L43-Q1 document; canonical FULL/active tests were skipped. The run is immutable evidence and is not rerun unchanged.

For future Windows/Git operator commands, follow the normative sections of `docs/AI_DEVELOPMENT_WORKFLOW.md` rather than reconstructing the rules from memory:
- discover or re-prove the exact worktree; never derive it from a branch name;
- normalize filesystem identity with `Resolve-Path`;
- use porcelain/status arrays for tracked/index cleanliness and explicitly account for untracked state when the contract requires it;
- check `$LASTEXITCODE` before parsing potentially absent native output;
- never Boolean-test stdout from an exit-code-only native command;
- use the reviewed wrapper or stderr-safe `Start-Process -Wait -PassThru` pattern when native stderr is expected;
- verify the canonical origin before network/ref mutation;
- re-prove final branch/HEAD/tree/tracked/index/untracked state;
- after any STOP, re-establish the complete gate before continuation.

### L43-Q1 consumed observation and next boundary

`ARCH147-L43-Q1_QUALIFICATION_PREFLIGHT_SOURCE` is accepted/integrated at `05f4c4700f82c3d40c83f474c3cf614573d48091` / tree `70aec1c51e63705a68d6710cc3448ac994227e46`. Feature run `44260469616` is terminal SUCCESS with mapped FULL; develop run `44264566809` is terminal SUCCESS with exact feature-certification reuse and no duplicate FULL. The registered slug remains `arch147-l43-qualification-preflight`, with protected read-only `preflight` and `execute=None`.

The separately reviewed Q1 preflight was invoked once after exact local/remote reconciliation and is now CONSUMED / BLOCKED / NO AUTOMATIC RETRY:
- evidence: `F:\AI\temp\ai-trading-bot-checkpoints\arch147-l43-qualification-preflight\preflight-20261118T091033.372793Z\report.json`
- source admission: PASS before/after
- identity: stable at the accepted Q1 HEAD/tree
- qualification: `BLOCKED / QUALIFICATION_INDETERMINATE`
- accepted source/config/binding/Q62 journal digests: present
- L43 durable-state snapshot/fresh pre-effect facts/challenge: absent
- review/place/cancel/broker mutation/L43 state mutation/Q62 mutation: all 0
- provider/credential call counts: `null` (unknown, not proof of zero)
- retry: `NOT_AUTHORIZED`

Source review narrows the failure to the interval after accepted source identity and before a durable-state snapshot was bound. The production snapshot path is fixed at `F:\AI\arch147-l43-live-state-v1\durable-state.jsonl`; the reader requires an already provisioned journal plus lock and never initializes them. The repository currently has no production L43 provisioning command; only test/fake fixtures create L43 state. The sanitized observation does not expose the underlying exception, so do not claim a specific host cause such as a missing journal or lock without separate evidence.

The former standalone L43 state-provisioning/diagnostic successor is superseded as the immediate milestone by Architecture 148. If the new application reuses L43 durable-state machinery, provisioning/migration must be owned by the new complete runtime dependency closure. No second Q1 preflight, Robinhood/Alpaca protected observation, review/place/cancel, Q63, or `FINAL_HOLDOUT` access is authorized by this handoff.

## RHC3 production order-scope admission

RHC3 consumes, but never mutates or retries, the exact retained A2/RHC2 chain:

- A2 semantic evidence: `F:\AI\temp\arch147-agent-initiated-runtime-proof-eligible-0d1c18123732442c9d3f4a14ba0f43e6\evidence.json`, SHA-256 `34483478bbf6430ff0e9a139cd33cdc8837be22eff100e53e0f6b2fdde46c3f1`
- RHC2 registered report: `F:\AI\temp\ai-trading-bot-checkpoints\arch147-rhc2-robinhood-order-scope-successor-observation\preflight-20261117T064253.945488Z\report.json`, SHA-256 `25873f5cdbb509b7a93b80a0644affb01e784c1bf0145a1aca20222ac71f56e9`
- RHC2 observer evidence: `F:\AI\temp\arch147-agent-initiated-runtime-partition-3f05ea6fed42440293ea3d58a1af5074\evidence.json`, SHA-256 `99bca426cba77589055be6dc826cf0d72884c51e40f493c19b55625ac2bf2189`
- reconstructed inner B2 evidence SHA-256: `7016e9c9f5a8b52e996a56e5eab4ee89ce993b967513109c09af23aa5e693fc3`

A2 authenticates the hosted `agent_initiated` filter semantics. RHC2 remains CONSUMED / PASS / NO RETRY and supplies four exhaustive runtime-consistency reads (`ALL_BEFORE`, `TRUE`, `FALSE`, `ALL_AFTER`), all zero-row. The zero-row observation is not treated as a non-empty semantic witness.

The RHC3 loader reads only those fixed paths, validates exact file hashes before parsing, rejects symlink/reparse/path/object drift, duplicate or unexpected JSON structure, wrong counters/status/source identity, and any write/other-tool attempt. It reconstructs and verifies the inner B2 digest and requires the retained RHC2 account fingerprint to equal canonical Q62.

At each current L43 proof request, the production verifier reauthenticates the evidence chain rather than caching authority. It accepts only the exact current unfiltered `{"account_number": ..., "symbol": "SPY"}` query, proves the account-number hash matches the Q62-bound fingerprint, requires bounded positive page count, bounded nonnegative row count and exhausted pagination, and returns an `ACCOUNT_WIDE_ALL_AGENTS` scope proof whose evidence digest binds all four retained evidence hashes plus current account/query/page/row/exhaustion facts. Any failure returns no proof and preserves `ORDER_SCOPE_UNPROVEN`.

The historical RHC2 field `production_order_scope_authority=NOT_GRANTED` remains unchanged; RHC3 is the separately source-reviewed consumer that grants only this narrow pre-effect order-scope prerequisite. It does not grant review/place/cancel authority or any generic live-effect permission.

The three pinned evidence files are now operational runtime dependencies. Do not clean, move, rewrite, regenerate, or replace them. Q63 must include their exact custody, backup/restore and hash verification in the final delivery package. Loss or mutation is fail-closed availability loss, not authority to recreate evidence.

## L41R1 consumed observation and L41R2 source successor

The consumed predecessor is recorded exactly as
`L41R1_REAL_OBSERVATION=CONSUMED_BLOCKED_NO_RETRY`. Its preserved evidence is
`F:\\AI\\temp\\arch147-l41r1-schema-observation-f5b81e5f60dc40c280f53007d1db2b52\\evidence.json`,
SHA-256
`2b62f54076fdfd34aa3eb799ed563701f8eadafe8877b25590f88fe72147160f`,
length `1130` bytes. It recorded source admission PASS, OAuth scope entry `1`,
MCP session-open `1`, `tools/list=0`, empty schemas, reason
`L41R1_MCP_SESSION_OPEN_FAILED`, and zero MCP tool, account, tradability,
position, order, portfolio, quote, review, placement, cancellation and
other-tool attempts.

The exact cause was `_create_windows_oauth_factory()` installing
`_forbid_interactive_oauth`; the MCP OAuth SDK required an authorization-code
flow and invoked that blocker. The classification is
`L41R1_INTERACTIVE_OAUTH_FORBIDDEN`, not a generic browser/environment failure.
The attempt also exposed an upstream OAuth/MCP traceback-output defect because
provider/OAuth traceback text reached the terminal despite sanitized evidence.

`L41R2_INTERACTIVE_SCHEMA_DISCOVERY` is the separately named additive successor
with evidence schema `arch147-l41r2-interactive-interface-observation/v1`. It
preserves the corrected schema facts, permits one reviewed interactive OAuth
authorization when persisted state is insufficient, suppresses upstream
provider/OAuth output, and invokes only bounded `tools/list`. Evidence records
browser launches as `0` or `1`, native credential read/write counts as `null`,
and `SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; raw URLs, callback values, tokens
and provider text are never persisted. A successful result is
`CAPTURED_FOR_REVIEW` only and grants no live readiness, broker authority, Q62
acceptance or order authority. At that historical checkpoint, Q62 remained NOT
RUN and blocked pending L41R3 classification.

The L41R2 observation is CONSUMED / BLOCKED / NO RETRY. Its immutable evidence
is
`F:\\AI\\temp\\arch147-l41r2-schema-observation-9a504f5e26b9414998cea287ee13936a\\evidence.json`,
SHA-256
`66C3E5C32A0FD575490B3219AEA7DE2ECCEE65C4E5FDEFF6EB339B9B963FA751`, length
`1386` bytes, reason `L41R2_SCHEMA_MALFORMED`. Source HEAD/tree were
`d421562703d6bae92b14afdcc1b3defcc595dbc8` /
`b0ca242360b1cfe17222c4b56e95198219eee4be`; FEATURE and
PROSPECTIVE_DEVELOP admission both passed. It recorded one OAuth scope-entry
attempt, one MCP session-open attempt, one browser launch, and one `tools/list`
attempt. All prohibited MCP tool/account/tradability/position/order/portfolio/
quote/review/place/cancel/other-tool counters were zero. Native credential
read/write fields are `null` with accounting
`SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED`; automatic retry is FORBIDDEN.

The failure is classified from source/client-model comparison: the source
extracts the wire spelling `inputSchema`, while MCP SDK v2 Tool objects expose
the Python attribute `input_schema`. The consumed evidence does not record the
raw provider object type. L41R3 is the additive successor with evidence schema
`arch147-l41r3-mcp-v2-interface-observation/v1`; it normalizes only name,
description, schema and pagination cursor before using the existing fail-closed
sanitized parser. Its success remains `CAPTURED_FOR_REVIEW` only, with zero
tool calls and no Q62, live, broker, order, numeric-rule or `FINAL_HOLDOUT`
authority. At the L41R2 source-acceptance checkpoint, real L41R3 had not yet
run; a later consumed observation followed that checkpoint.

The first unpublished L41R2 prepublication admission is preserved at
`F:\\AI\\temp\\arch147-l41r2-source-admission-2804bb15b8ec49eab4f0ac8ac0fe0a0f` and is classified
`PREPUBLICATION_ADMISSION_TOPOLOGY_DEFECT` / `FULL_LANE_DUPLICATE_BASENAME`.
The enlarged FULL inventory placed `tests/portfolio/test_models.py` and
`tests/rebalancing/test_models.py` together in broad-5, producing the required
`40 != 39` basename invariant failure under the current pytest topology. No
authority failure occurred, `IDENTITY_STABLE=True`, and `PROTECTED_EFFECTS=0`.
This was not a product-source failure, published red source, coverage defect,
or GitHub CI failure. The corrected admission subsequently passed, the amended
candidate was published as
`235118f70b7c7039055e9fea45ccf27df46671a0` / tree
`972004101036afe52642ed93c38fed21ea479956`, mapped FULL
`42358983502` attempt 1 was terminal SUCCESS, and independent exact-source
review accepted the L41R2 implementation. At that source-acceptance checkpoint
the real observation had not yet run; it was subsequently consumed as
BLOCKED / NO RETRY in the L41R2 record above. It does not advance Q62.

## L40 accepted/integrated checkpoint

Canonical worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`;
branch: `feature/robinhood-live-prototype-current`.

Accepted L40 source HEAD:
`14e1b628c0c51c27b23deabee56eb91859818529`

Accepted L40 source tree:
`48b588cbb37818b0d1edfcbb895cfb715a2bf2d3`

Direct parent:
`f7f13f805ad6a0eea7041cb6d13c561149a13f6e`

Feature mapped FULL `41995282653`, attempt 1, was SUCCESS with all seven
canonical broad lanes, active tests, hygiene/evidence and aggregate source gate
green. The exact source was independently accepted. Ordinary fast-forward
integration then moved `develop` to the accepted L40 source; develop gate
`41997418576`, attempt 1, was SUCCESS and reused feature certification
`41995282653` without another FULL. Remote feature and develop were both
verified at the accepted L40 HEAD/tree before this coordination closeout.

The accepted [L40 contract](architecture/147-restricted-live-contract.md) is an
effect-disabled pure policy owner. It freezes exact-owned full-remainder exits,
the <=$10 requested/cumulative new-acquisition budget, reducing exits without a
universal $10 exit-notional ceiling, partial-fill ownership, residual
preservation, exact identity matching and UNKNOWN/MAY_HAVE_OCCURRED no-retry
semantics. Evidence-reference flags are necessary-only prerequisites and
authenticate nothing by themselves. L40 does not establish actual Robinhood
account fractional-sell eligibility, numeric quantity/minimum/notional rules,
durable controller persistence or live-order authority.

The next source step described at L40 was superseded by the current source
preparation milestone above. D33 and D34 remain consumed/no-retry and
`FINAL_HOLDOUT` remains sealed. No paper soak is inserted.

## D34 accepted/integrated closeout identity

Worktree: `F:\AI\worktrees\ai-trading-bot-live-prototype-current`

Branch: `feature/robinhood-live-prototype-current`

Integrated source HEAD: `b86defebf9ccbf1efb91397de8f2e66db24a6665`

Integrated source tree: `9fa2360dfe7afdd902fd539e94f888063439785d`

Feature mapped FULL `41969407894`, attempt 1, and develop source-gate
`41973853073`, attempt 1, both succeeded; develop reused the exact feature
certification. That is the accepted D34 implementation identity; the later
canonical closeout and current L40 base are recorded above. The accepted/integrated
D33 source remains the D34 lineage ancestor
`fad65c9f4eab5bc1de4e154fdf0f59e397bc943a` / tree
`beab205abcc045fad38625ff73bb48affea9a0e9`. The first D34 publication
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` is its direct child, and accepted
D34 corrective source `b86defebf9ccbf1efb91397de8f2e66db24a6665` is the direct
child of `9981bf47072d35381a2e5b6f187c9497e9dbed5a`. D33 is a consumed
predecessor incident, not an available observation boundary.

The preserved D34 predecessor is
`9981bf47072d35381a2e5b6f187c9497e9dbed5a` / tree
`a8d2b4fb4a40039b74768b44fd0198dc87bc55f3`. Its mapped run `41950572892`,
attempt 1, was terminal SUCCESS, but exact-source review rejected it before
develop integration because blocked-result attempt counts were not bound to
their failure phase and the operator fallback could write false `0/0`
credential/provider counts after an escaped failure. No D34 real observation
occurred; the candidate remains immutable evidence.

D30 is ACCEPTED with dataset ID
`d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`, dataset SHA
`ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`, and
`ALPACA_ALL_ADJUSTED_PRICE_V1`. D31's exact bundle is ACCEPTED with campaign
`9b2a000e-3adc-50f4-ab47-2aa90665e3c9`, bundle
`f01a39a7-0a65-55bb-9d38-608b1ce0bd21`, bundle SHA
`94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11`, result
`NONE_QUALIFIES`, and retained control `BASE_MA35_50_V1` / candidate
`21158358-75be-5597-b940-5bccdda1429c`. D32 is ACCEPTED / CLOSED: strategy
math parity, research-binding integrity, and live data-basis parity passed;
the 2,516 comparisons had zero mismatches. The former
`DATA_BASIS_MISMATCH` blocker is closed.

## Consumed D33 incident

D33's one real read-only attempt is CONSUMED / BLOCKED / NO RETRY. Preserved
evidence:
`F:\\AI\\temp\\arch147-d33-alpaca-observation-576b4b5c8f7b41548df7b822c44c74de\\evidence.json`;
SHA-256 `b767727712e4634950be8a6ba8f43522910d037987824ad33cb7c20c8eab95ec`,
1,999 bytes; observation `2026-11-04T23:59:08.218729Z`; credentials `1`;
provider requests `1`; selected sessions `60`; production, broker,
runtime-binding, campaign, and FINAL_HOLDOUT mutation counts are all `0`.
The exact provider rejection subtype is unavailable because D33 discarded it.
The request end exceeded observation through end-of-calendar-day semantics;
this is a source-contract defect, not proof of the provider's exact rejection
cause. D33's exact request target is preserved in the validation ledger.

## Accepted D34 observation and stop conditions

The corrective D34 child changes only attempt-accounting/evidence truthfulness
and focused tests/docs. The additive D34 source derives one exact published
regular close after selecting the 60 completed XNYS sessions and before
credential/provider construction. That same cutoff is used for the request and
`CompletedSignalInputs`; it never uses next midnight, end-of-calendar-day,
observation-as-substitute, silent subtraction, provider fallback, or a changed
session set. D34's separately named entry point is
`trading_bot.live_prototype.alpaca_signal_recovery_operator`, with evidence
schema `arch147-d34-alpaca-signal-observation/v1`. The old D33 CLI is retired
before credentials/provider access; `--help` remains effect-free.

D34 source admission and the mapped feature FULL completed before the
separately labeled read-only observation. The accepted evidence is
`F:\\AI\\temp\\arch147-d34-alpaca-observation-84d32fb2af5045e7a661a77259b690fb\\evidence.json`,
2800 bytes, SHA-256
`7c6f2d391cbb3141405e3252efcfcd94db18b8e81083d947d778310bfe49464b`.
Schema: `arch147-d34-alpaca-signal-observation/v1`; status READY; reason
`D34_ALPACA_SIGNAL_INPUTS_READY`; observation timestamp
`2026-11-05T05:28:41.664723Z`.

The observation consumed exactly one credential read and one provider call, with
automatic retry FORBIDDEN. The exact one-request target is
`GET /v2/stocks/bars?symbols=SPY&timeframe=1Day&start=2026-08-12T04%3A00%3A00.000000Z&end=2026-11-04T21%3A00%3A00.000000Z&limit=60&adjustment=all&asof=-&feed=sip&currency=USD&sort=asc`.
It selected 60 sessions from 2026-08-12 through 2026-11-04. Response-body
bytes were 6702 with SHA-256
`296c9e89dd2f48d47b1ca3b071411d6e8509ca769fc92e433be19696bbf68c94`;
provider request-ID digest was
`6384000426f7d007ed9391b81bef6beb2ba40a5193cf94dd30a2a58fb63ae15f`; and
the `CompletedSignalInputs` digest was
`8b6d4f88012da820890cb5070de975c1d02504aeb432939a2e954d9bf9dfecb0`.
No raw request ID or credential material is retained.

The D34 attempt is CONSUMED SUCCESSFULLY / NO RETRY. Production, broker,
runtime-binding, campaign, order, paper, live, and `FINAL_HOLDOUT` effects are
all zero. The observed BASE_MA35_50_V1 BUY/HOLD outputs are signal outputs only;
they do not authorize an order or grant live eligibility.

At the L40 closeout, its original L41-L43 dependency plan was the accepted
baseline and Q61 had not yet run. Q61 was accepted later; this passage records
the earlier L40 state. No live-readiness label or paper-soak milestone is
granted and `FINAL_HOLDOUT` remains sealed.

The old P6 preflight is historical predecessor context, not the current next
operator action and not the D33/D34 signal-data path. It grants no retry.
