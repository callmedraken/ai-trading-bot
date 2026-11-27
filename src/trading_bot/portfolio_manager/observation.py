"""Explicit account selection, adoption and injected read-only observation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from trading_bot.desktop_paper.robinhood_read import (
    data,
    decimal_value,
    parse_order,
    parse_position,
    resolve_account,
)
from trading_bot.desktop_paper.robinhood_read import (
    symbol as parse_symbol,
)
from trading_bot.desktop_paper.robinhood_reconciliation import (
    MAX_ORDER_PAGES,
    MAX_ORDERS,
    MAX_POSITION_PAGES,
    MAX_POSITIONS,
    ORDER_WINDOW_DAYS,
)
from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.models import (
    AccountBinding,
    AccountBindingResult,
    AccountBindingStatus,
    AccountCandidate,
    ObservationCondition,
    ObservationCoverage,
    ObservationProvenance,
    OrderCoverage,
    OrderObservation,
    OrderOwnership,
    PortfolioObservation,
    PositionObservation,
    PositionType,
)
from trading_bot.robinhood_mcp.parsing import parse_equity_quotes_response


class PortfolioReadBoundary(Protocol):
    """The existing five-method Robinhood read surface, injectable for tests."""

    def get_accounts(self) -> Mapping[str, object]: ...

    def get_portfolio(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class PortfolioObservationError(ValueError):
    """A sanitized fixed diagnostic from the source-only read pipeline."""

    def __init__(
        self,
        code: str,
        *,
        condition: ObservationCondition | None = None,
        binding_result: AccountBindingResult | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.condition = condition
        self.binding_result = binding_result


def account_candidates(payload: Mapping[str, object]) -> tuple[AccountCandidate, ...]:
    """Return sanitized candidate fingerprints without exposing raw account IDs."""
    try:
        accounts = data(payload).get("accounts")
        if not isinstance(accounts, list) or not 1 <= len(accounts) <= 100:
            raise PortfolioObservationError("ACCOUNT_COLLECTION_INVALID")
        candidates: list[AccountCandidate] = []
        seen_numbers: set[str] = set()
        for account in accounts:
            if not isinstance(account, Mapping):
                raise PortfolioObservationError("ACCOUNT_RECORD_INVALID")
            number = account.get("account_number")
            eligible = account.get("agentic_allowed")
            if (
                not isinstance(number, str)
                or not number
                or number != number.strip()
                or len(number) > 128
                or any(
                    char.isspace() or ord(char) < 32 or ord(char) == 127
                    for char in number
                )
                or not isinstance(eligible, bool)
            ):
                raise PortfolioObservationError("ACCOUNT_RECORD_INVALID")
            if number in seen_numbers:
                raise PortfolioObservationError("ACCOUNT_DUPLICATE")
            seen_numbers.add(number)
            candidates.append(
                AccountCandidate(
                    hashlib.sha256(number.encode("utf-8")).hexdigest(), eligible
                )
            )
        return tuple(candidates)
    except PortfolioObservationError:
        raise
    except Exception:
        raise PortfolioObservationError("ACCOUNT_RESPONSE_INVALID") from None


def bind_account(
    candidates: tuple[AccountCandidate, ...], selected_fingerprint: str | None
) -> AccountBindingResult:
    """Require an explicit selected fingerprint, including for a sole account."""
    items = tuple(candidates)
    if any(not isinstance(item, AccountCandidate) for item in items):
        raise TypeError("candidates must contain AccountCandidate values")
    if len({item.fingerprint for item in items}) != len(items):
        raise ValueError("candidate fingerprints must be unique")
    eligible = tuple(item.fingerprint for item in items if item.eligible)
    if not eligible:
        return AccountBindingResult(
            AccountBindingStatus.NO_ELIGIBLE_ACCOUNT, None, eligible
        )
    if selected_fingerprint is None:
        status = (
            AccountBindingStatus.MULTIPLE_ELIGIBLE_ACCOUNTS
            if len(eligible) > 1
            else AccountBindingStatus.SELECTION_REQUIRED
        )
        return AccountBindingResult(status, None, eligible)
    if selected_fingerprint not in eligible:
        return AccountBindingResult(
            AccountBindingStatus.SELECTED_ACCOUNT_UNAVAILABLE, None, eligible
        )
    return AccountBindingResult(
        AccountBindingStatus.BOUND,
        AccountBinding(selected_fingerprint),
        eligible,
    )


def adopt_portfolio_observation(
    binding: AccountBinding | None,
    *,
    observed_at: datetime,
    observed_account_fingerprint: str | None,
    broker_reported_equity: Decimal | None,
    cash: Decimal | None,
    buying_power: Decimal | None,
    unleveraged_buying_power: Decimal | None,
    positions: tuple[PositionObservation, ...],
    orders: tuple[OrderObservation, ...] = (),
    coverage: ObservationCoverage,
    provenance: ObservationProvenance,
    conditions: tuple[ObservationCondition, ...] = (),
    broker_reported_position_value: Decimal | None = None,
) -> PortfolioObservation:
    """Adopt provider facts under the explicit binding, preserving mismatches."""
    if binding is not None and not isinstance(binding, AccountBinding):
        raise TypeError("binding must be AccountBinding or None")
    return PortfolioObservation(
        observed_at=observed_at,
        account_fingerprint=None if binding is None else binding.fingerprint,
        broker_reported_equity=broker_reported_equity,
        cash=cash,
        buying_power=buying_power,
        unleveraged_buying_power=unleveraged_buying_power,
        positions=positions,
        orders=orders,
        coverage=coverage,
        provenance=provenance,
        conditions=conditions,
        observed_account_fingerprint=observed_account_fingerprint,
        broker_reported_position_value=broker_reported_position_value,
    )


def _portfolio_values(
    payload: Mapping[str, object],
) -> tuple[
    Decimal | None, Decimal | None, Decimal | None, Decimal | None, Decimal | None
]:
    """Preserve missing portfolio facts as None; accept only known USD units."""
    root = data(payload)
    currency = root.get("currency")
    if currency not in (None, "USD"):
        raise PortfolioObservationError("PORTFOLIO_CURRENCY_UNSUPPORTED")
    power = root.get("buying_power")
    if power is not None and not isinstance(power, Mapping):
        raise PortfolioObservationError("PORTFOLIO_INVALID")
    if currency != "USD":
        # Unitless values cannot be safely adopted as dollars.
        return None, None, None, None, None

    def optional_amount(container: Mapping[str, object], key: str) -> Decimal | None:
        value = container.get(key)
        return None if value is None else decimal_value(value)

    total_value = optional_amount(root, "total_value")
    cash = optional_amount(root, "cash")
    equity_value = optional_amount(root, "equity_value")
    buying_power: Decimal | None = None
    unleveraged_buying_power: Decimal | None = None
    if isinstance(power, Mapping) and power.get("display_currency") == "USD":
        buying_power = optional_amount(power, "buying_power")
        unleveraged_buying_power = optional_amount(power, "unleveraged_buying_power")
    elif isinstance(power, Mapping) and power.get("display_currency") not in (
        None,
        "USD",
    ):
        raise PortfolioObservationError("PORTFOLIO_CURRENCY_UNSUPPORTED")
    return (
        total_value,
        cash,
        equity_value,
        buying_power,
        unleveraged_buying_power,
    )


def _read_pages(
    read: Callable[[Mapping[str, object]], Mapping[str, object]],
    *,
    arguments: dict[str, object],
    key: str,
    max_pages: int,
    max_items: int,
    expected_account_number: str | None = None,
) -> list[object]:
    rows: list[object] = []
    seen: set[str] = set()
    request = dict(arguments)
    for _ in range(max_pages):
        try:
            payload = read(request)
            _validate_account_echo(payload, expected_account_number)
            page = data(payload)
        except PortfolioObservationError:
            raise
        except Exception:
            raise PortfolioObservationError(
                f"{key.upper()}_READ_FAILED",
                condition=ObservationCondition.PAGINATION_INCOMPLETE,
            ) from None
        items = page.get(key)
        if not isinstance(items, list) or len(rows) + len(items) > max_items:
            raise PortfolioObservationError(
                f"{key.upper()}_PAGE_INVALID",
                condition=ObservationCondition.PAGINATION_INCOMPLETE,
            )
        _validate_row_account_echo(items, expected_account_number)
        rows.extend(items)
        cursor = page.get("next")
        if cursor in (None, ""):
            return rows
        if not isinstance(cursor, str) or len(cursor) > 4096 or cursor in seen:
            raise PortfolioObservationError(
                f"{key.upper()}_CURSOR_INVALID",
                condition=ObservationCondition.PAGINATION_INCOMPLETE,
            )
        seen.add(cursor)
        request = {**arguments, "cursor": cursor}
    raise PortfolioObservationError(
        f"{key.upper()}_PAGE_BOUND_EXCEEDED",
        condition=ObservationCondition.PAGINATION_INCOMPLETE,
    )


def _validate_account_echo(
    payload: Mapping[str, object], expected_account_number: str | None
) -> None:
    """Reject mismatched echoes without including either identifier in errors."""
    if expected_account_number is None:
        return
    root = data(payload)
    echoed = root.get("account_number")
    if echoed is not None and echoed != expected_account_number:
        raise PortfolioObservationError(
            "ACCOUNT_ECHO_MISMATCH", condition=ObservationCondition.ACCOUNT_MISMATCH
        )


def _validate_row_account_echo(
    rows: list[object], expected_account_number: str | None
) -> None:
    """Reject a returned row explicitly bound to a different account."""
    if expected_account_number is None:
        return
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        echoed = row.get("account_number")
        if echoed is not None and echoed != expected_account_number:
            raise PortfolioObservationError(
                "ACCOUNT_ECHO_MISMATCH",
                condition=ObservationCondition.ACCOUNT_MISMATCH,
            )


def _position_type(value: str) -> PositionType:
    return {
        "long": PositionType.LONG,
        "short": PositionType.SHORT,
        "empty": PositionType.FLAT,
    }.get(value, PositionType.UNKNOWN)


def _position_facts(
    value: object,
) -> tuple[Symbol, Decimal, Decimal, Decimal | None, PositionType, bool]:
    """Use the accepted parser when possible; preserve unknown hints explicitly."""
    if not isinstance(value, Mapping):
        raise PortfolioObservationError("POSITION_INVALID")
    asset_hints = tuple(
        value[name]
        for name in ("asset_type", "asset_class", "instrument_type")
        if value.get(name) is not None
    )
    supported: bool | None = (
        None
        if not asset_hints
        else all(
            isinstance(asset_hint, str)
            and asset_hint.casefold() in {"equity", "stock", "etf", "equity_etf"}
            for asset_hint in asset_hints
        )
    )
    try:
        parsed = parse_position(value)
        return (
            Symbol(parsed.symbol),
            parsed.quantity,
            parsed.shares_available_for_sells,
            parsed.average_buy_price,
            _position_type(parsed.position_type),
            supported,
        )
    except Exception:
        classification = value.get("type")
        if not isinstance(classification, str) or classification.casefold() in {
            "long",
            "short",
            "empty",
        }:
            raise PortfolioObservationError("POSITION_INVALID") from None
        try:
            symbol_value = Symbol(parse_symbol(value.get("symbol")))
            quantity = decimal_value(value.get("quantity"))
            available = decimal_value(value.get("shares_available_for_sells"))
            raw_cost = value.get("average_buy_price")
            average_cost = None if raw_cost is None else decimal_value(raw_cost)
            if quantity >= 0 and available > quantity:
                raise ValueError("sellable exceeds position")
            if available < 0:
                raise ValueError("negative sellable quantity")
        except Exception:
            raise PortfolioObservationError("POSITION_INVALID") from None
        return (
            symbol_value,
            quantity,
            available,
            average_cost,
            PositionType.UNKNOWN,
            supported,
        )


def _quote(payload: Mapping[str, object], symbol: Symbol) -> tuple[Decimal, datetime]:
    try:
        parsed = parse_equity_quotes_response(payload)
        results = tuple(
            item
            for item in parsed.results
            if item is not None
            and item.quote is not None
            and item.quote.symbol == symbol
        )
        if len(results) != 1:
            raise PortfolioObservationError("QUOTE_MISSING")
        quote = results[0].quote
        if quote is None or quote.state != "active" or not quote.has_traded:
            raise PortfolioObservationError("QUOTE_NOT_CURRENT")
        price, timestamp = quote.current_trade_candidate()
        if not price.is_finite() or price <= 0:
            raise PortfolioObservationError("QUOTE_PRICE_INVALID")
        return price, normalize_utc(timestamp, "quote timestamp")
    except PortfolioObservationError:
        raise
    except Exception:
        raise PortfolioObservationError("QUOTE_INVALID") from None


def observe_robinhood_portfolio(
    read: PortfolioReadBoundary,
    *,
    observed_at: datetime,
    selected_account_fingerprint: str | None,
    max_quote_age: timedelta = timedelta(minutes=5),
) -> PortfolioObservation:
    """Read a bounded Robinhood snapshot through an injected, read-only boundary.

    Construction is inert. Calling this function only invokes the five existing
    current read methods; it does not review, place or cancel orders.
    """
    # Structural validation keeps simple test fakes and the existing transport
    # on the same narrow contract without adding a runtime-checkable Protocol.
    for name in (
        "get_accounts",
        "get_portfolio",
        "get_equity_positions",
        "get_equity_quotes",
        "get_equity_orders",
    ):
        if not callable(getattr(read, name, None)):
            raise TypeError("read must implement the five current read methods")
    stamp = normalize_utc(observed_at, "observed_at")
    if not isinstance(max_quote_age, timedelta) or max_quote_age <= timedelta(0):
        raise ValueError("max_quote_age must be a positive timedelta")
    context = read if callable(getattr(read, "__enter__", None)) else nullcontext(read)
    try:
        with context as scoped:
            accounts_payload = scoped.get_accounts()
            candidates = account_candidates(accounts_payload)
            eligible_candidates = tuple(item for item in candidates if item.eligible)
            if len(eligible_candidates) > 1:
                blocked = AccountBindingResult(
                    AccountBindingStatus.MULTIPLE_ELIGIBLE_ACCOUNTS,
                    None,
                    tuple(item.fingerprint for item in eligible_candidates),
                )
                raise PortfolioObservationError(
                    blocked.status.value, binding_result=blocked
                )
            binding_result = bind_account(candidates, selected_account_fingerprint)
            if binding_result.status is not AccountBindingStatus.BOUND:
                raise PortfolioObservationError(
                    binding_result.status.value, binding_result=binding_result
                )
            binding = binding_result.binding
            if binding is None:
                raise PortfolioObservationError("ACCOUNT_SELECTION_FAILED")
            try:
                canonical_account = resolve_account(accounts_payload)
            except Exception:
                raise PortfolioObservationError("ACCOUNT_SELECTION_FAILED") from None
            if canonical_account.fingerprint != binding.fingerprint:
                raise PortfolioObservationError(
                    "ACCOUNT_SELECTION_MISMATCH",
                    condition=ObservationCondition.ACCOUNT_MISMATCH,
                )
            raw_account_number = canonical_account.account_number
            arguments = {"account_number": raw_account_number}
            try:
                portfolio_payload = scoped.get_portfolio(arguments)
                _validate_account_echo(portfolio_payload, raw_account_number)
                portfolio_facts = _portfolio_values(portfolio_payload)
            except PortfolioObservationError:
                raise
            except Exception:
                raise PortfolioObservationError("PORTFOLIO_INVALID") from None
            raw_positions = _read_pages(
                scoped.get_equity_positions,
                arguments=arguments,
                key="positions",
                max_pages=MAX_POSITION_PAGES,
                max_items=MAX_POSITIONS,
                expected_account_number=raw_account_number,
            )
            try:
                parsed_positions = tuple(
                    _position_facts(item) for item in raw_positions
                )
            except Exception:
                raise PortfolioObservationError("POSITIONS_INVALID") from None
            if len({item[0] for item in parsed_positions}) != len(parsed_positions):
                raise PortfolioObservationError("POSITION_SYMBOL_DUPLICATE")
            positions: list[PositionObservation] = []
            conditions: list[ObservationCondition] = []
            quote_coverage = True
            for (
                symbol,
                quantity,
                available_to_sell,
                average_cost,
                classification,
                supported,
            ) in parsed_positions:
                try:
                    raw_quote = scoped.get_equity_quotes({"symbols": [str(symbol)]})
                    _validate_account_echo(raw_quote, raw_account_number)
                    price, price_at = _quote(raw_quote, symbol)
                except PortfolioObservationError as error:
                    if error.condition is ObservationCondition.ACCOUNT_MISMATCH:
                        raise
                    price = None
                    price_at = None
                    quote_coverage = False
                    conditions.append(ObservationCondition.MISSING_PRICE)
                if price is not None and price_at is not None:
                    if price_at > stamp or stamp - price_at > max_quote_age:
                        conditions.append(ObservationCondition.STALE_PRICE)
                positions.append(
                    PositionObservation(
                        symbol=symbol,
                        quantity=quantity,
                        available_to_sell=available_to_sell,
                        average_cost=average_cost,
                        current_price=price,
                        price_observed_at=price_at,
                        supported=supported,
                        position_type=classification,
                    )
                )
            orders_since = stamp - timedelta(days=ORDER_WINDOW_DAYS)
            raw_orders = _read_pages(
                scoped.get_equity_orders,
                arguments={
                    **arguments,
                    "placed_agent": "agentic",
                    "created_at_gte": orders_since.isoformat(),
                },
                key="orders",
                max_pages=MAX_ORDER_PAGES,
                max_items=MAX_ORDERS,
                expected_account_number=raw_account_number,
            )
            try:
                parsed_orders = tuple(parse_order(item) for item in raw_orders)
            except Exception:
                raise PortfolioObservationError("ORDERS_INVALID") from None
            orders = tuple(
                OrderObservation(
                    order_id=item.order_id,
                    symbol=Symbol(item.symbol),
                    side=item.side,
                    state=item.state,
                    quantity=item.quantity,
                    filled_quantity=item.cumulative_quantity,
                    created_at=item.created_at,
                    ownership=OrderOwnership.UNKNOWN,
                )
                for item in sorted(
                    parsed_orders, key=lambda item: (item.created_at, item.order_id)
                )
            )
            coverage = ObservationCoverage(
                account_bound=True,
                portfolio_complete=all(value is not None for value in portfolio_facts),
                positions_complete=True,
                quotes_complete=quote_coverage,
                pagination_complete=True,
                order_scope=OrderCoverage.ROBINHOOD_AGENTIC_BOUNDED,
            )
            return adopt_portfolio_observation(
                binding,
                observed_at=stamp,
                observed_account_fingerprint=binding.fingerprint,
                broker_reported_equity=portfolio_facts[0],
                broker_reported_position_value=portfolio_facts[2],
                cash=portfolio_facts[1],
                buying_power=portfolio_facts[3],
                unleveraged_buying_power=portfolio_facts[4],
                positions=tuple(positions),
                orders=orders,
                coverage=coverage,
                provenance=ObservationProvenance.ROBINHOOD_READ_ONLY,
                conditions=tuple(conditions),
            )
    except PortfolioObservationError:
        raise
    except Exception:
        # No provider exception or response body is allowed to escape this seam.
        raise PortfolioObservationError("READ_OPERATION_FAILED") from None
