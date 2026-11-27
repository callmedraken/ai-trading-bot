# Architecture 152-PM2A — Brokerage Observation and Reconciliation

## Mission and authority

PM2A determines what the existing authorized Robinhood read path can establish
about one explicitly selected account: positions, valuations, cash and buying
power, outstanding orders, and reconciliation completeness. This is an
observation qualification, not an execution milestone. It grants no order
review, placement, cancellation, transfer, liquidation, or trading authority.

PM1 remains closed and unchanged. Its recommendations remain bound to an
observation; deterministic risk remains independent; stale quotes, account
mismatch, concentration, sellability, cash, buying-power, and pending-order
conflicts remain blocking; plans remain preview-only with
`dispatch_authorized=False`; Start/Stop does not liquidate; durable state stays
account-namespaced. Unknown brokerage facts are not converted to strict
`PortfolioState` values.

The first PM2A publication is source-only. The implementation and tests use fake
provider/session fixtures. No credential or OAuth access, live session/provider
request, account/order read, review, placement, cancellation, transfer, or
production mutation is performed. A future real read requires separate exact
source review and a separately authorized, create-once observation.

## Public implementation review

The references were reviewed at these immutable commits. They are evidence of
implementation patterns, not project authority.

| Reference | What it demonstrates | Caveats and disposition |
| --- | --- | --- |
| [`arunitmaity/robinhood-portfolio-mcp` at `d80bc3c`](https://github.com/arunitmaity/robinhood-portfolio-mcp/tree/d80bc3c2f4e4753d390c806ace1d3a1f1740eb30) | Account selection and managed-account inclusion; account-scoped position/order reads; multi-page collection; open and partially filled orders; average cost, quotes, cash, buying power, and order-reservation fields; request timeout, one bounded transient retry, and fail-closed later-page errors. | Its README identifies the brokerage integration as unofficial and uses Robinhood private brokerage endpoints through `robin_stocks`. Its account selection by default/managed/last digits is weaker than this project's required explicit fingerprint. Some reads are not account-scoped; page-cycle detection and quote/cost missingness are weaker. We reuse only abstract lessons: exact account binding, explicit managed visibility, bounded pagination, and no partial result after a later-page failure. We do not copy its authentication, private endpoint URLs, payload parsers, defaults, or retry policy. |
| [`jmfernandes/robin_stocks` at `1b4ef98`](https://github.com/jmfernandes/robin_stocks/tree/1b4ef98be36d1df127886889c843256799a1dfea) | Account profile fields for cash, buying power, held cash and unsettled balances; optional account-number arguments; position holdings and average cost; open/all stock-order helpers; fundamental `pe_ratio`. | It calls unofficial/private Robinhood brokerage REST endpoints. Its ordinary GET path has no explicit timeout/retry, returns `None` on failures, and can return accumulated rows after a later-page failure; some holdings helpers use an implicit/default account. These behaviors are inventory only and are not copied. Public field names do not establish the current MCP provider's schema or semantics. |
| [`nirholas/robinhood-mcp` at `54c59c7`](https://github.com/nirholas/robinhood-mcp/tree/54c59c719ad4e1268802178b8925794541278876) | A data-only server separated from an order-capable trading server; order-history-derived cost/reconciliation diagnostics; explicit incomplete-history warnings. | Its README describes Robinhood's documented signed Crypto Trading API, not brokerage equities. Its account selection takes the first account result. Its pagination helper can fail to mark invalid/repeated cursors as truncated, and callers do not enforce the truncation flag. We reuse the separation principle only; we do not copy its crypto endpoints, signing/authentication, account selection, or effectful tools. |

No source code was vendored, no runtime dependency was added, and no public
reference's authentication or effectful surface was copied. The current
repository's explicit read allowlist, lazy session, typed Decimal observations,
and existing fail-closed page reader remain the implementation base.

## Capability matrix

`PROVEN_BOUNDED` means the source enforces the stated limited behavior; it does
not mean the provider returns every fact outside that bound. `AVAILABLE_NOT_YET_QUALIFIED`
means a read method exists but its provider schema/runtime semantics have not
been observed. No brokerage capability is classified `PROVEN_COMPLETE` by this
source-only checkpoint.

| Capability | Current source evidence | Classification |
| --- | --- | --- |
| Account discovery | `get_accounts`; account collection is bounded to 1–100 rows and malformed/duplicate account numbers fail closed. | `PROVEN_BOUNDED` |
| Exact selected-account identity | User selection is a SHA-256 fingerprint; the selected account must match the account resolved from discovery; a sole account is not implicitly selected. | `PROVEN_BOUNDED` |
| Multiple accounts | The provider observation path rejects any discovery response with more than one eligible account, even when a selected fingerprint is supplied. The pure binder supports exact fingerprint binding, but this observer only proceeds with one eligible account; PM1 behavior is preserved. | `PROVEN_BOUNDED` |
| Managed-account visibility | No current response schema has been observed and no managed flag is inferred from a public repository field. | `UNKNOWN` |
| Inactive/deactivated accounts | Current account eligibility is represented only by the existing `agentic_allowed` fact; inactive/deactivated semantics are not independently modeled. | `UNKNOWN` |
| Position reads | `get_equity_positions` receives the selected `account_number`; at most three pages and 1,000 rows are accepted. | `PROVEN_BOUNDED` |
| Fractional quantities | Provider quantities parse as `Decimal`; fractional values are preserved. Provider completeness remains unobserved. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Available/sellable quantity | `shares_available_for_sells` is preserved and checked against nonnegative/long quantity bounds. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Average cost | Broker `average_buy_price` is retained when present and remains `None` when absent. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Position entry chronology, historical fills, and tax lots | No timestamp, fill, or lot is invented from average cost or current holdings. Current-order cumulative fill quantity is a separate bounded fact below. | `UNAVAILABLE` |
| Supported versus unsupported asset | Explicit recognized equity/ETF hints classify supported; explicit other hints classify unsupported; absent hints remain `None` / `ASSET_TYPE_UNKNOWN` and block. | `PROVEN_BOUNDED` |
| Quote reads | `get_equity_quotes` is called per position symbol; quote symbols are matched exactly and current trade price/timestamp are retained. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Quote freshness | A quote older than five minutes or observed in the future is marked stale and blocks. | `PROVEN_BOUNDED` |
| Missing quote/valuation | Missing quote produces no fabricated price and leaves market value unknown. | `PROVEN_BOUNDED` |
| Broker equity | Broker `total_value` is separately retained when a USD value is present; it is not replaced by local computation. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Local equity | Computed only from known cash plus all valued positions; missing inputs produce `None`. | `PROVEN_BOUNDED` |
| Cash | A missing cash field remains `None` and adds `MISSING_CASH`; no zero substitution occurs. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Buying power | Parsed only when the response declares USD display currency; missing field remains `None`. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Unleveraged buying power | Parsed independently only when the response declares USD display currency; missing value remains `None`. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Cash reserved/held for orders | No current provider schema or semantic mapping is available; public-reference field names are not treated as current-provider facts. | `UNKNOWN` |
| Unsettled cash/withdrawable cash | No current provider schema or semantic mapping is available. | `UNKNOWN` |
| All currently open equity orders | Current query sends `placed_agent=agentic` and `created_at_gte` for a seven-day window; at most three pages and 300 rows are accepted. No evidence establishes account-wide open-order coverage. | `PROVEN_BOUNDED` |
| Manual/external orders | The current query is agentic-filtered; external/manual visibility is not established. Returned ownership remains `UNKNOWN`. | `UNKNOWN` |
| Agent-created orders | Rows are returned only within the bounded agentic/date query; they are not promoted to account-wide coverage. | `PROVEN_BOUNDED` |
| Partially filled orders | Cumulative filled quantity is retained; a partially filled nonterminal order remains pending and can block a preview. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Queued/pending/confirmed states | Known nonterminal states are pending; unrecognized nonterminal states remain pending and add `UNKNOWN_ORDER_STATE`. | `PROVEN_BOUNDED` |
| Order ownership | No bot ownership is inferred from order ID or request shape; all observed current-path order rows use `UNKNOWN`. | `PROVEN_BOUNDED` |
| Position/order pagination | Repeated/invalid cursors, page/row bounds, malformed pages, and later-page failures produce an incomplete error, never a partial portfolio result. | `PROVEN_BOUNDED` |
| Empty `next` cursor | Existing current-read behavior treats `None` or `""` as end-of-pages; this sentinel is regression-tested. | `PROVEN_BOUNDED` |
| Returned account binding | Portfolio, position, and order calls include the selected account argument; quote reads are symbol-scoped. Mismatched root or position/order row `account_number` echoes reject without exposing identifiers. Missing echoes do not prove result semantics. | `PROVEN_BOUNDED` |
| Duplicate positions/order IDs | Duplicate position symbols reject; duplicate order IDs remain an explicit blocking condition. | `PROVEN_BOUNDED` |
| Staleness outside quotes | Portfolio/cash freshness and order update/settlement timestamps are not available; order creation time is retained but not treated as an update time. | `UNKNOWN` |
| Missing/malformed provider data | Missing supported values remain `None`; malformed data/errors map to fixed sanitized diagnostics. | `PROVEN_BOUNDED` |
| Provider schema discovery | A separate explicit operation enumerates only the existing five `READ_TOOLS` schemas using `tools/list`; it exposes bounded argument/output shape facts and has no tool-dispatch method. No real provider schema has been observed in this checkpoint. | `AVAILABLE_NOT_YET_QUALIFIED` |
| Provider list pagination | Discovery is bounded to 20 pages; repeated/invalid cursors and later-page failures discard partial schema results. | `PROVEN_BOUNDED` |
| Provider/session failures | Existing MCP session uses a 60-second HTTP timeout and sanitized failure codes; current source has no transient retry. No retry is added without provider-specific evidence. | `PROVEN_BOUNDED` |
| Cross-origin pagination links | Current MCP/read protocol passes opaque cursors; it does not follow provider-supplied URLs. URL-origin checks are not applicable to this cursor contract. | `UNKNOWN` |

### Order-scope result and stop rule

The current implemented scope remains exactly
`ROBINHOOD_AGENTIC_BOUNDED`: selected account argument, `placed_agent=agentic`,
seven-day lower time bound, and bounded page/row counts. Open-order visibility
for external/manual orders and account-wide exhaustive order scope are not
proven. The PM risk layer continues to reject executable previews when coverage
is bounded or incomplete.

The current provider's actual schemas have not been observed. The source-only
result is therefore `CURRENT_PROVIDER_ORDER_SCOPE_UNQUALIFIED`; it is not a
claim that the provider is insufficient or sufficient. After the exact
allowlisted schemas are reviewed, if they cannot establish selected-account,
account-wide open-equity-order visibility, record
`CURRENT_PROVIDER_ORDER_SCOPE_INSUFFICIENT` (or the repository-equivalent
explicit classification) and stop. Do not guess alternate arguments,
endpoints, pagination rules, or filters. Any dedicated read-only brokerage
adapter is a separately reviewed next milestone.

## Schema qualification and transport boundary

`current_read_schema_qualification.py` provides two paths:

* `qualify_current_read_schemas(list_tools)` is an injected metadata-only
  adapter used with synthetic fixtures. It bounds pages/schema size, validates
  aliases and cursor progression, requires closed schemas before reporting a
  complete argument/response shape, hashes schemas, and returns safe argument
  names/types, requiredness, recognized pagination/order-filter arguments, and
  result account/pagination paths. It does not return descriptions, raw schemas,
  unallowlisted names, provider errors, or schema values.
* `qualify_current_read_provider(oauth_factory)` is explicit and inert on import.
  When later separately reviewed and authorized, it opens the existing lazy
  current provider session and calls only `list_tools`. It contains no
  `call_tool`/dispatch surface. It was not invoked during this source-only
  checkpoint.

Schema shape alone is not proof that an argument is honored or that returned
rows are complete/account-bound. The five-method
`RobinhoodCurrentReadTransport` public API remains unchanged. Arbitrary tool
discovery cannot turn effectful tools into callable methods.

The existing read transport already has a 60-second session timeout, a 20-page
cap for tool discovery, repeated-cursor checks, and fixed sanitized errors. The
PM observation page reader uses three-page/row caps, fails on a later-page
error, and never returns prior rows as a successful partial snapshot. It treats
`next` as an opaque cursor, not as a URL. The source contains no automatic
transient retry; no retry is added without evidence that the MCP/provider layer
does not already implement the relevant behavior. Account IDs and raw provider
payloads are not included in diagnostics.

## Future real-read boundary

After source publication, mapped CI, and independent exact-source acceptance,
ChatGPT may separately review one real read-only qualification. It must be
create-once/consumed-once with no automatic retry and sanitized evidence bound
to the exact source HEAD/tree. The future evidence record must include the
selected account fingerprint, account counts, session/tool-list attempts and
pages, exact read tools invoked and per-tool counts, position/order page and row
counts, pagination completion, result-account binding, quote freshness,
cash/buying-power presence, explicit order-scope classification, unknown or
incomplete conditions, and zero review/place/cancel/transfer/other-effect
attempts. It must not contain credentials, tokens, full account numbers, raw
provider payloads, or unnecessary personal financial values. This source
checkpoint does not authorize or perform that operation.

## Next milestone

PM2B is **Architecture 152-PM2B — Research Evidence and Signal Catalog**. It is
not implemented here. It will separately review Qlib and PyPortfolioOpt and
define provenance for valuation/fundamentals, growth/revisions, free cash flow,
quality/profitability, leverage, technical momentum/trend, volatility/downside,
relative attractiveness, and portfolio context. PM2A remains limited to
truthful brokerage/account observation and reconciliation.
