# Architecture 152-PM2A — Validation Plan and Source-Only Record

## Status and scope

This record covers the **SOURCE/CERTIFICATION ACCEPTED** source-only PM2A
checkpoint at C3 HEAD `834ac5b942eb436ab7d06809953f21f7a0f8fcc5` / tree
`0051affa15e94253a15a47c7d51e6f5b9ca625ec`, based on starting parent
`6cc6a815325b49165ef5d0f48af744707715dc1f` / tree
`cb7cd3b5e422b65429782b42f1cfe822082e75cc`. It does not contain a real
Robinhood observation result. The currently authorized provider's actual tool
schemas have not been observed, so order scope remains
`CURRENT_PROVIDER_ORDER_SCOPE_UNQUALIFIED`; the existing read path remains
`ROBINHOOD_AGENTIC_BOUNDED`. No account-wide open-order completeness is claimed.

PM1 remains closed and disarmed. PM2A does not authorize order review,
placement, cancellation, transfer, liquidation, or trading. No credentials,
OAuth, live provider/session request, account read, order read, broker action,
production mutation, or real financial payload was used during source work,
focused tests, or mapped CI.

The architecture and public-reference matrix are in
[Architecture 152-PM2A](../architecture/152-pm2a-brokerage-observation-and-reconciliation.md).
The inert one-shot preparation is implemented in
`src/trading_bot/portfolio_manager/qualification_attempt.py`; no attempt
directory or real observation was created.

## Implemented source qualification

`qualify_current_read_schemas(list_tools)` is the fake-friendly metadata
adapter. The explicit `qualify_current_read_provider(oauth_factory)` operation
is the later-use path: if separately invoked, it opens the current lazy MCP
session and calls only `list_tools`; it has no tool-dispatch API. Neither test
nor source verification invoked a real provider session. The production-facing
operation is intentionally not executed in this checkpoint.

The qualifier inspects only the exact existing five-name `READ_TOOLS` list,
discards and counts other tool names, bounds schema/page sizes, validates
`tools/list` pagination, and returns only safe argument names/types, required
flags, recognized account/pagination/order-filter fields, bounded response
paths, and schema digests. It does not expose descriptions, schema values,
unallowlisted names, provider errors, or raw payloads. The result explicitly
marks order semantics `SCHEMA_ONLY_UNPROVEN`; schema presence alone cannot prove
that an account argument is honored or that rows are exhaustive.

## Focused synthetic test coverage

| Requirement | Test coverage |
| --- | --- |
| Multiple-account ambiguity and exact fingerprint binding | `tests/portfolio_manager/test_observation.py::test_account_selection_requires_explicit_fingerprint_and_blocks_ambiguity`; the pure binder binds an exact candidate, while the provider observer blocks any response with more than one eligible account even if a fingerprint is supplied. |
| Selected-account/profile mismatch and row-level mismatch for positions/orders | `test_missing_stale_and_echo_mismatch_remain_explicit`; `test_row_account_echo_mismatch_blocks_before_adopting_rows` |
| Managed/inactive/deactivated account visibility | Not modeled because no current provider schema has been observed; the capability remains `UNKNOWN`, with no public-reference field-name inference. |
| Fractional quantity, sellable quantity, average cost present/absent | `test_fake_robinhood_transport_adopts_fractional_holdings_without_filling_history` |
| Missing asset type, explicit unsupported holding, unknown position type | `test_unknown_position_classification_and_explicit_unsupported_hint_stay_visible`; `test_fake_robinhood_transport_adopts_fractional_holdings_without_filling_history`; `tests/portfolio_manager/test_adapters.py::test_unknown_asset_classification_blocks_preview_and_strict_conversion` |
| Missing and stale quote / missing valuation | `test_missing_stale_and_echo_mismatch_remain_explicit` |
| Duplicate positions and order IDs | `test_duplicate_position_rows_are_rejected_before_quote_reads`; `tests/portfolio_manager/test_risk_planning.py::test_pending_external_order_unknown_ownership_and_duplicate_ids_block_actions` |
| Complete position pagination and empty terminal cursor | `test_empty_next_cursor_retains_current_terminal_sentinel` |
| Repeated/invalid cursor, page bound, later-page failure | `test_malformed_pagination_is_explicit_and_prevents_quote_reads`; `test_invalid_position_cursor_is_incomplete`; `test_position_page_limit_is_incomplete_without_partial_observation`; `test_later_position_page_failure_does_not_return_partial_success` |
| Later-page failure never becomes partial success | `test_later_position_page_failure_does_not_return_partial_success`; equivalent schema-list failure is covered by `tests/robinhood_mcp/test_current_read_schema_qualification.py::test_later_page_failure_discards_partial_schema_observation` |
| Manual/external order conflict, duplicate IDs, bounded/unknown order scope | `tests/portfolio_manager/test_risk_planning.py::test_pending_external_order_unknown_ownership_and_duplicate_ids_block_actions`; `test_unknown_scope_and_incomplete_coverage_never_approve_a_preview` |
| Queued, pending, confirmed, partially filled order remains pending | `tests/portfolio_manager/test_risk_planning.py::test_open_order_states_and_partial_fills_remain_pending` |
| Missing cash, buying power, unleveraged buying power | `test_missing_cash_and_buying_power_remain_unknown`; `test_missing_unleveraged_buying_power_stays_unknown` |
| Provider schema mismatch, open/closed argument shape, pagination, page bound, and output shape facts | `tests/robinhood_mcp/test_current_read_schema_qualification.py::test_malformed_schema_and_ambiguous_schema_alias_fail_closed`; `test_open_input_schema_does_not_claim_account_argument_absent`; `test_schema_observation_is_allowlisted_paginated_and_never_dispatches`; `test_missing_allowlisted_tool_is_explicit_after_complete_listing`; `test_schema_discovery_page_limit_is_incomplete` |
| Unknown/effectful tools cannot be invoked or included in schema evidence | `test_schema_observation_is_allowlisted_paginated_and_never_dispatches`; existing `tests/robinhood_mcp/test_current_read_transport.py::test_mutation_inventory_is_unneeded_and_not_surfaced` |
| Import/construction has no provider effect; read facade stays five-method | Existing `tests/robinhood_mcp/test_current_read_transport.py::test_exact_public_read_surface_and_frozen_131_contract`, `test_mutation_inventory_is_unneeded_and_not_surfaced`, and `test_each_read_discovers_all_required_tools_before_one_dispatch`; the schema provider wrapper is exercised only with a fake session. |
| Fake PM vertical slice stays preview-only/disarmed | `tests/portfolio_manager/test_vertical_slice.py`; asserts `dispatch_authorized is False` and bounded order coverage blocks previews. |
| Attempt reserves source/fingerprint metadata before OAuth, binds reviewed HEAD/tree, and rechecks identity after schemas before read tools | `tests/portfolio_manager/test_qualification_attempt.py::test_schema_incomplete_reserves_before_provider_and_stops_before_reads`; `test_reviewed_source_head_and_tree_are_required_before_reservation`; `test_source_change_after_schema_preflight_blocks_before_read_tools` |
| Production attempt root stays fixed to `F:\AI\temp`; synthetic fixtures can use their pytest temp root without weakening the public operation | `tests/portfolio_manager/test_qualification_attempt.py::test_default_attempt_root_rejects_non_f_drive`; `_prepare` replaces only the private root resolver for fake attempt tests. |
| Attempt IDs are create-once; repeat, collision, crash-reserved, and concurrent IDs do not retry; evidence is sanitized | `tests/portfolio_manager/test_qualification_attempt.py::test_attempt_id_collision_and_crash_reserved_slot_are_never_reused`; `test_concurrent_attempt_id_has_one_provider_winner`; `test_complete_fake_observation_records_only_sanitized_facts` |
| Explicit fingerprint with multiple eligible accounts still blocks before any position/order read | `tests/portfolio_manager/test_qualification_attempt.py::test_explicit_account_fingerprint_does_not_override_multiple_account_block`; existing PM1 ambiguity behavior is unchanged. |
| Incomplete/malformed schema or missing static argument/account echo/pagination shape stops before reads | `tests/portfolio_manager/test_qualification_attempt.py::test_schema_incomplete_reserves_before_provider_and_stops_before_reads`; `test_schema_missing_static_account_or_order_filter_arguments_blocks_reads`; schema fixture coverage in `tests/robinhood_mcp/test_current_read_schema_qualification.py` |
| Advertised required arguments absent from a tool's static first-call arguments block transport construction and all reads | `tests/portfolio_manager/test_qualification_attempt.py::test_required_argument_missing_from_static_first_call_blocks_all_reads` covers accounts, portfolio, quotes, and first-page position/order cursors; `test_required_arguments_supplied_by_static_first_calls_are_supported` covers required arguments that the fixed call does send. |

The current provider does not expose cash-reservation semantics in source. Cash
held for orders, unsettled cash, and withdrawal availability therefore remain
unknown; no field names from public implementations are parsed as provider
facts. Agent-created, manual, and external order ownership is not inferred from
IDs. The current seven-day `placed_agent=agentic` query remains bounded.

The prepared API requires an attempt ID, literal expected source HEAD/tree,
explicit selected account fingerprint, and injected OAuth factory. It checks
the exact clean source and current FEATURE/PROSPECTIVE_DEVELOP authority before
reservation; binds those identities and the fingerprint in create-once
`attempt.json`; rechecks the source after reservation and after schema
qualification immediately before constructing the read transport; then writes
create-once sanitized `evidence.json`. A directory containing only reservation
metadata after a crash remains consumed and is incomplete evidence, never
retryable under that ID. A later separately reviewed attempt uses a new ID.
The schema step calls only `tools/list`; malformed/incomplete schemas or a
missing static argument, account echo, or pagination path stop before any read
tool. `SCHEMA_ONLY_UNPROVEN` does not establish provider semantics or exhaustive
orders. No attempt ID was used and no attempt/evidence directory was created.

## Focused verification performed

Focused tests use the repository-mandated interpreter and a new external temp
directory for each invocation:

```powershell
$testGuid = [guid]::NewGuid().ToString('N')
$testBaseTemp = "F:\AI\temp\pytest\$testGuid"
New-Item -ItemType Directory -Path $testBaseTemp
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -u -m pytest `
  -p no:cacheprovider --basetemp $testBaseTemp `
  tests/robinhood_mcp/test_current_read_schema_qualification.py `
  tests/robinhood_mcp/test_current_read_transport.py `
  tests/portfolio_manager/test_qualification_attempt.py `
  tests/portfolio_manager/test_observation.py `
  tests/portfolio_manager/test_adapters.py `
  tests/portfolio_manager/test_risk_planning.py `
  tests/portfolio_manager/test_vertical_slice.py -q
```

Complete focused result at C2: **90 passed in 2.60s** using external
basetemp `F:\AI\temp\pytest\8955343ba1514e4c85696bb2b421fcc5`. The isolated
attempt module passed **17 tests in 0.28s** using fresh basetemp
`F:\AI\temp\pytest\36075fe63b404517bda82ec5ec617270`. An earlier
directory-creation attempt was denied and is not counted as a compliant test
run.

The source-owner/current-authority command passed **60 tests in 71.10s** using
fresh external basetemp
`F:\AI\temp\pytest\3fd404c2e7004955a5987336e4539434`:

```powershell
$ownerGuid = [guid]::NewGuid().ToString('N')
$ownerBaseTemp = "F:\AI\temp\pytest\$ownerGuid"
New-Item -ItemType Directory -Path $ownerBaseTemp
& 'F:\AI\ai-trading-bot\.venv\Scripts\python.exe' -B -u -m pytest `
  -p no:cacheprovider --basetemp $ownerBaseTemp `
  tests/portfolio_manager/test_certification_ownership.py `
  tests/runtime/checkpoint_runner/test_source_authority.py -q
```

Whole-repository `ruff check --no-cache .` passed; `ruff format --check
--no-cache .` reported 1,775 files already formatted; `git diff --check` passed
with only LF-to-CRLF warnings. C3 clean-candidate admission passed with
`FEATURE=PASS`, `PROSPECTIVE_DEVELOP=PASS`, `IDENTITY_STABLE=True`, and
`OVERALL=PASS`; its report is recorded below. No local FULL run was performed.
Mapped GitHub CI owns canonical certification for C2 and C3.

## Preserved mapped CI failure and C1 correction

The first mapped source-gate run, `45974606765` attempt 1, is preserved as a
terminal failure on the prior candidate. Source-static and active checkpoint
tests passed. FULL `broad-2` had nine failures, all in
`test_qualification_attempt.py`; the six other FULL lanes passed. The failure
was a test-host path mismatch: fake tests replaced `_ATTEMPT_ROOT` with
`tmp_path`, but the real-operation resolver correctly rejected the hosted
runner's non-F drive before reservation, schema observation, or any read tool.
The broad-2 artifact is `15185959030`; the downloaded diagnostic copy is under
`F:\AI\temp\arch152-pm2a-broad2-artifact-a91c4d6db745488daa344b722708d53d`.
ChatGPT classified this as `PREPUBLICATION_COVERAGE_DEFECT`; the run and
artifact remain unchanged and were not retried.

C1 extracts the production F-drive check into a private root resolver and has
fake fixtures replace only that resolver with their pytest temp directory. The
public attempt API and production `F:\AI\temp` default are unchanged. The new
`test_default_attempt_root_rejects_non_f_drive` regression proves the normal
resolver continues to reject `C:\Windows`. C1's attempt module passed 11 tests,
and the full focused PM2A/PM1 set passed 84 tests, as recorded above. This
correction changes no provider schema, order-scope, or broker-effect claim.

C1 source `0840fce67d896be43eed6494ee74458b06d26a85` / tree
`aa5170acd36729233f76bf337777a92fd56039ad` passed mapped run `45977590119`,
attempt 1. Source-static, active-tests, all seven canonical FULL lanes, and the
final `source-gates` job passed. Lane durations were broad-1 4m40s, broad-2
2m54s, broad-3 3m1s, broad-4 3m33s, broad-5 3m50s, broad-6 4m19s, and broad-7
5m51s. The prior red run and its artifact remain preserved.

C2 checks every advertised `required` argument against the existing static
first-call argument set for its tool before constructing the read transport.
The sets are empty for `get_accounts`, `account_number` for the selected
portfolio and first position page, `symbols` for quotes, and
`account_number`/`placed_agent`/`created_at_gte` for the first order page.
Position and order `cursor` values are added only after a page supplies a next
cursor, so a schema requiring `cursor` on page one blocks before any read tool.
The synthetic tests cover each first-call gap and confirm required arguments
already supplied by the fixed calls remain supported. No provider fields,
actual schemas, account-wide order semantics, or broker effects are inferred.
C2's attempt module passed 17 tests, and the final formatted-source focused set
and source-owner/current-authority checks passed 90 and 60 tests respectively,
as recorded above.

C2 source `f5303eae49df1b431e09be489aa356eb76a81af6` / tree
`36cab55b80efe275d195ff79c35d1b88fe25e66e` passed mapped run `45981347432`,
attempt 1: source-static, active-tests, all seven canonical FULL lanes, and
source-gates passed. This run is preserved as terminal SUCCESS.

C3 accepts the compatible cursor shape used by the static reader: position and
order calls omit `cursor` on page one, then send a non-null string on later
pages. Cursor schemas therefore need to admit `string`; they do not need to
admit JSON `null`. The new synthetic regression supplies optional string-only
cursor arguments for both tools and confirms that the schema gate accepts the
static page-call shape. C2's required-cursor regressions remain in place and
continue to block schemas that require a cursor on page one.

C3's isolated cursor regression passed **1 test in 0.09s** using fresh
basetemp `F:\AI\temp\pytest\db26de97f0aa4e298c83b6d98e328680`. The complete
focused set passed **91 tests in 0.73s** using fresh basetemp
`F:\AI\temp\pytest\3300cc13ad044d5cadda06189b411f84`. Source-owner/current-
authority checks passed **60 tests in 71.06s** using fresh basetemp
`F:\AI\temp\pytest\0804b65e9e2f4f12aa8f68721ad4db0a`.

C3 source `834ac5b942eb436ab7d06809953f21f7a0f8fcc5` / tree
`0051affa15e94253a15a47c7d51e6f5b9ca625ec` passed prepublication admission at
`F:\AI\temp\ai-trading-bot-checkpoints\arch132-r3n-prepublication-admission\source-gate-20261127T103735.643783Z\report.json`.
Mapped run `45984464000`, attempt 1, is terminal SUCCESS: source-static,
active-tests, source-gates, and all seven canonical FULL lanes passed. Lane
durations were broad-1 5m45s, broad-2 4m29s, broad-3 3m48s, broad-4 3m46s,
broad-5 3m12s, broad-6 4m37s, and broad-7 5m23s. C3 is the accepted PM2A
source; `develop` remains at the starting parent. The earlier red run
`45974606765` and artifact `15185959030` remain unchanged and preserved; neither
C2 nor C3 reran or overwrote them.

Across implementation, focused tests, admission, and mapped CI, no provider,
OAuth, credential, account, or order read occurred. Review, placement,
cancellation, transfer, broker, and production-effect attempts remained zero.

## Prepared future real-read operation (NOT YET AUTHORIZED)

Source publication, mapped CI completion, and independent exact-source
acceptance are complete. A real-read invocation still requires a separate
reviewed authorization; this record does not authorize one. The prepared API
shape is:

```python
run_pm2a_qualification_attempt(
    attempt_id="<new 32-character lowercase hex ID>",
    expected_source_head="<literal accepted feature HEAD>",
    expected_source_tree="<literal accepted feature tree>",
    selected_account_fingerprint="<64-character lowercase account fingerprint>",
    oauth_factory=<existing separately reviewed OAuth factory>,
)
```

The function reserves its attempt ID with immutable source/fingerprint metadata
before OAuth, calls only `tools/list` until all closed schema and static read
surface checks pass, then may call the exact existing five read methods once
through `RobinhoodCurrentReadTransport`. It records exact source HEAD/tree,
account fingerprint and observed/eligible counts, provider/session and schema
discovery attempts/pages, exact read tools and per-tool counts, position/order
pages/rows, pagination, selected-account binding, quote availability/freshness,
cash/buying-power availability, the bounded order-scope result, unknown or
incomplete conditions, and zero review/place/cancel/transfer/other-effect
attempts. It writes immutable sanitized evidence with no raw credentials, OAuth
material, full account numbers, raw provider payloads, symbols, quantities, or
unnecessary personal financial values. Existing attempt directories, including
crash-reserved directories missing final evidence, remain consumed. There is no
automatic retry. This source checkpoint prepares the API and evidence schema;
it creates no attempt/evidence file and does not authorize execution.

If more than one account is eligible, PM1's observer rejects the observation
even when the required fingerprint matches one of those accounts. The attempt
records counts and the selected fingerprint, marks account binding false, and
invokes no portfolio, position, quote, or order read. It does not change PM1
account-selection behavior.

If reviewed schemas cannot establish exhaustive selected-account open equity
orders, record `CURRENT_PROVIDER_ORDER_SCOPE_INSUFFICIENT` (or the repository's
equivalent) and stop. Do not probe speculative arguments or endpoints. A
dedicated read-only brokerage adapter would require a separate review.
