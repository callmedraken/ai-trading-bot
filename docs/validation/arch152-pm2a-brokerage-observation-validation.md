# Architecture 152-PM2A — Validation Plan and Source-Only Record

## Status and scope

This is the source-only PM2A checkpoint. It does not contain a real Robinhood
observation result. The currently authorized provider's actual tool schemas
have not been observed, so the current order-scope result is
`CURRENT_PROVIDER_ORDER_SCOPE_UNQUALIFIED`; the existing read path remains
`ROBINHOOD_AGENTIC_BOUNDED`. No account-wide open-order completeness is claimed.

PM1 remains closed and disarmed. PM2A does not authorize order review,
placement, cancellation, transfer, liquidation, or trading. No credentials,
OAuth, live session/provider request, account read, order read, broker action,
production mutation, or real financial payload was used during source work.

The architecture and public-reference matrix are in
[Architecture 152-PM2A](../architecture/152-pm2a-brokerage-observation-and-reconciliation.md).

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

The current provider does not expose cash-reservation semantics in source. Cash
held for orders, unsettled cash, and withdrawal availability therefore remain
unknown; no field names from public implementations are parsed as provider
facts. Agent-created, manual, and external order ownership is not inferred from
IDs. The current seven-day `placed_agent=agentic` query remains bounded.

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
  tests/portfolio_manager/test_observation.py `
  tests/portfolio_manager/test_adapters.py `
  tests/portfolio_manager/test_risk_planning.py `
  tests/portfolio_manager/test_vertical_slice.py -q
```

Latest focused result before this document update: **73 passed** using external
basetemp `F:\AI\temp\pytest\f2d11adacd9f4de78deb4250b79c7fc3`. The directory was
created with scoped sandbox escalation. An earlier directory-creation attempt
was denied and is not counted as a compliant test run.

Whole-repository Ruff check/format, `git diff --check`, relevant source-owner
and current-authority gates, and clean-candidate admission remain required
before publication. No local FULL run is authorized or required for this
source-only checkpoint; mapped canonical CI owns certification if the exact
checkpoint profile is registered.

## Future real-read operation (NOT YET AUTHORIZED)

After source publication, mapped CI completion, and independent exact-source
acceptance, the next separately reviewed operation may invoke
`qualify_current_read_provider(oauth_factory)` once to observe only provider
tool schemas. It must be wired to a one-shot create-once attempt record with
sanitized evidence containing exact source HEAD/tree, account fingerprint and
counts, provider/session and discovery attempts/pages, exact read tools and
invocation counts, page/row counts, pagination completion, result-account
binding, quote freshness, cash/buying-power availability, order-scope outcome,
unknown/incomplete conditions, and zero review/place/cancel/transfer/other
effect attempts. It must contain no raw credentials, OAuth material, full
account numbers, raw provider payloads, or unnecessary personal financial
values. It has no automatic retry. This source checkpoint neither prepares an
evidence file nor authorizes that operation.

If reviewed schemas cannot establish exhaustive selected-account open equity
orders, record `CURRENT_PROVIDER_ORDER_SCOPE_INSUFFICIENT` (or the repository's
equivalent) and stop. Do not probe speculative arguments or endpoints. A
dedicated read-only brokerage adapter would require a separate review.
