from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from decimal import Context, Decimal, localcontext
from functools import cache, lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.filtered_trend_data import (
    ADJUSTMENT,
    ADJUSTMENT_SEMANTICS,
    CURRENCY,
    DATA_END_EXCLUSIVE,
    DATA_START,
    FEED,
    MAX_PROVIDER_PAGE_BYTES,
    PRICE_BASIS,
    PROVIDER_ENDPOINT,
    PROVIDER_NAME,
    TIMEFRAME,
    UNIVERSE,
    AlpacaPageTransport,
    FilteredTrendDataError,
    HistoricalBarsPage,
    HistoricalBarsRequest,
    MultiAssetDataset,
    ProviderProvenance,
    SymbolDataset,
    acquire_dataset,
    build_alpaca_request,
    parse_alpaca_page,
    read_dataset,
    write_dataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

_NEW_YORK = ZoneInfo("America/New_York")


@lru_cache(maxsize=1)
def _session_dates() -> tuple[date, ...]:
    return tuple(
        item
        for item in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= item < date(2024, 1, 1)
    )


@cache
def _bars(symbol: str) -> tuple[Bar, ...]:
    result = []
    for ordinal, day in enumerate(_session_dates()):
        price = Decimal("100") + Decimal(ordinal) / Decimal("100")
        timestamp = datetime.combine(day, time.min, _NEW_YORK).astimezone(UTC)
        result.append(
            Bar(
                Symbol(symbol),
                timestamp,
                price,
                price + Decimal("1"),
                price - Decimal("1"),
                price + Decimal("0.25"),
                1000 + ordinal,
            )
        )
    return tuple(result)


@lru_cache(maxsize=1)
def _valid_dataset() -> MultiAssetDataset:
    provenance = ProviderProvenance()
    return MultiAssetDataset(
        tuple(SymbolDataset(symbol, _bars(symbol), provenance) for symbol in UNIVERSE)
    )


def _alpaca_json_page(
    symbol: str,
    bars: tuple[Bar, ...],
    next_page_token: str | None,
    currency: object | None = None,
) -> bytes:
    rows = []
    for ordinal, bar in enumerate(bars):
        values = [
            f'"t":{json.dumps(bar.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"))}',
            f'"o":{format(bar.open, "f")}',
            f'"h":{format(bar.high, "f")}',
            f'"l":{format(bar.low, "f")}',
            f'"c":{format(bar.close, "f")}',
            f'"v":{bar.volume}',
        ]
        if ordinal == 0:
            values.extend((f'"n":{bar.volume // 2}', f'"vw":{format(bar.close, "f")}'))
        rows.append("{" + ",".join(values) + "}")
    token = json.dumps(next_page_token)
    currency_field = ""
    if currency is not None:
        currency_field = ',"currency":' + json.dumps(currency)
    return (
        '{"bars":{'
        + json.dumps(symbol)
        + ":["
        + ",".join(rows)
        + "]}"
        + currency_field
        + ',"next_page_token":'
        + token
        + "}"
    ).encode("utf-8")


class _PagedFakeTransport:
    def __init__(self, *, page_size: int = 503) -> None:
        self.page_size = page_size
        self.requests: list[HistoricalBarsRequest] = []

    def fetch_page(self, request: HistoricalBarsRequest) -> HistoricalBarsPage:
        self.requests.append(request)
        assert request.start == DATA_START
        assert request.end_exclusive == DATA_END_EXCLUSIVE
        assert request.adjustment == "all"
        bars = _bars(request.symbol)
        start = 0 if request.page_token is None else int(request.page_token)
        end = min(start + self.page_size, len(bars))
        next_token = str(end) if end < len(bars) else None
        return HistoricalBarsPage(bars[start:end], next_token)


def test_fixed_universe_sessions_and_new_york_midnight_contract() -> None:
    dataset = _valid_dataset()

    assert dataset.symbols == UNIVERSE
    assert dataset.price_basis == "ALPACA_ALL_ADJUSTED_PRICE_V1"
    assert PRICE_BASIS == "ALPACA_ALL_ADJUSTED_PRICE_V1"
    assert len(_session_dates()) > 253
    for series in dataset.datasets:
        assert tuple(
            bar.timestamp.astimezone(_NEW_YORK).date() for bar in series.bars
        ) == (_session_dates())
        assert all(
            bar.timestamp.astimezone(_NEW_YORK).time() == time.min
            for bar in series.bars
        )
        assert max(bar.timestamp for bar in series.bars) < DATA_END_EXCLUSIVE


def test_identity_is_stable_and_uses_canonical_semantic_values() -> None:
    dataset = _valid_dataset()
    with localcontext(Context(prec=3)):
        same = MultiAssetDataset(dataset.datasets)
    assert same.identity == dataset.identity
    assert len(dataset.identity) == 36


def test_alpaca_price_basis_is_not_labeled_total_return() -> None:
    provenance = ProviderProvenance()
    assert provenance.provider == PROVIDER_NAME
    assert provenance.endpoint == PROVIDER_ENDPOINT
    assert provenance.timeframe == TIMEFRAME
    assert provenance.feed == FEED
    assert provenance.currency == CURRENCY
    assert provenance.adjustment == ADJUSTMENT == "all"
    assert provenance.adjustment_semantics == ADJUSTMENT_SEMANTICS
    assert PRICE_BASIS != "TOTAL_RETURN"
    with pytest.raises(FilteredTrendDataError, match="provenance is frozen"):
        ProviderProvenance(adjustment_semantics="REINVESTED_TOTAL_RETURN")


def test_dataset_and_storage_round_trip_preserve_identity(tmp_path: Path) -> None:
    dataset = _valid_dataset()
    artifact = tmp_path / "multi-asset.json"

    write_dataset(artifact, dataset)
    loaded = read_dataset(artifact)

    assert loaded.identity == dataset.identity
    assert loaded.to_json() == dataset.to_json()
    with pytest.raises(FilteredTrendDataError, match="already exists"):
        write_dataset(artifact, dataset)


def test_parser_rejects_unknown_duplicate_and_changed_identity_fields() -> None:
    dataset = _valid_dataset()
    value = dataset.to_dict()
    value["unexpected"] = "ignored fields are forbidden"
    with pytest.raises(FilteredTrendDataError, match="fields do not match"):
        MultiAssetDataset.from_dict(value)

    duplicate = b'{"schema":"first","schema":"second"}'
    with pytest.raises(FilteredTrendDataError, match="duplicate JSON field"):
        MultiAssetDataset.from_json(duplicate)

    changed = dataset.to_dict()
    changed["identity"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(FilteredTrendDataError, match="identity is inconsistent"):
        MultiAssetDataset.from_dict(changed)


def test_parser_rejects_duplicate_bar_fields_inside_canonical_artifact() -> None:
    dataset = _valid_dataset()
    payload = (
        dataset.to_json()
        .encode("utf-8")
        .replace(
            b'"symbol":"SPY","timestamp":',
            b'"symbol":"SPY","symbol":"SPY","timestamp":',
            1,
        )
    )
    assert payload != dataset.to_json().encode("utf-8")
    with pytest.raises(FilteredTrendDataError, match="duplicate JSON field"):
        MultiAssetDataset.from_json(payload)


@pytest.mark.parametrize("failure", ["missing", "duplicate", "wrong_time", "2024"])
def test_symbol_dataset_fails_closed_on_bad_coverage(failure: str) -> None:
    bars = list(_bars("SPY"))
    if failure == "missing":
        bars.pop(500)
    elif failure == "duplicate":
        bars.insert(501, bars[500])
    elif failure == "wrong_time":
        original = bars[500]
        bars[500] = Bar(
            original.symbol,
            original.timestamp.replace(hour=1),
            original.open,
            original.high,
            original.low,
            original.close,
            original.volume,
        )
    else:
        bars.append(
            Bar(
                Symbol("SPY"),
                datetime(2024, 1, 2, 5, tzinfo=UTC),
                Decimal("100"),
                Decimal("101"),
                Decimal("99"),
                Decimal("100"),
                1000,
            )
        )

    with pytest.raises(FilteredTrendDataError):
        SymbolDataset("SPY", tuple(bars))


@pytest.mark.parametrize(
    "symbols",
    [UNIVERSE[:-1], (*UNIVERSE[:-1], "SPY"), tuple(reversed(UNIVERSE))],
)
def test_dataset_rejects_missing_duplicate_or_reordered_symbols(
    symbols: tuple[str, ...],
) -> None:
    provenance = ProviderProvenance()
    datasets = tuple(
        SymbolDataset(symbol, _bars(symbol), provenance) for symbol in symbols
    )
    with pytest.raises(FilteredTrendDataError, match="fixed universe"):
        MultiAssetDataset(datasets)


def test_acquisition_uses_only_injected_transport_and_follows_pages() -> None:
    transport = _PagedFakeTransport()

    dataset = acquire_dataset(transport)

    assert dataset.symbols == UNIVERSE
    assert all(len(series.bars) == len(_session_dates()) for series in dataset.datasets)
    assert len(transport.requests) > len(UNIVERSE)
    first_symbol_page_count = (
        len(_bars("SPY")) + transport.page_size - 1
    ) // transport.page_size
    assert (
        tuple(
            request.symbol for request in transport.requests[:first_symbol_page_count]
        )
        == ("SPY",) * first_symbol_page_count
    )
    assert transport.requests[first_symbol_page_count].symbol == "QQQ"
    assert all(request.adjustment == "all" for request in transport.requests)


def test_acquisition_rejects_repeated_pagination_token() -> None:
    first = _bars("SPY")[0]

    class RepeatingTransport:
        def fetch_page(self, request: HistoricalBarsRequest) -> HistoricalBarsPage:
            if request.page_token is None:
                return HistoricalBarsPage((first,), "loop")
            return HistoricalBarsPage((), "loop")

    with pytest.raises(FilteredTrendDataError, match="token repeated"):
        acquire_dataset(RepeatingTransport())


def test_acquisition_rejects_out_of_range_provider_bars() -> None:
    future = Bar(
        Symbol("SPY"),
        datetime(2024, 1, 2, 5, tzinfo=UTC),
        Decimal("100"),
        Decimal("101"),
        Decimal("99"),
        Decimal("100"),
        1000,
    )

    class OutOfRangeTransport:
        def fetch_page(self, request: HistoricalBarsRequest) -> HistoricalBarsPage:
            return HistoricalBarsPage((future,))

    with pytest.raises(FilteredTrendDataError, match="out-of-range"):
        acquire_dataset(OutOfRangeTransport())


def test_parser_rejects_noncanonical_artifact_bytes() -> None:
    body = _valid_dataset().to_json().encode("utf-8")
    with pytest.raises(FilteredTrendDataError, match="canonical dataset JSON"):
        MultiAssetDataset.from_json(body + b" ")


def test_alpaca_request_is_exact_and_contains_no_authentication() -> None:
    request = build_alpaca_request(HistoricalBarsRequest("SPY"))

    assert request.method == "GET"
    assert request.host == "data.alpaca.markets"
    assert request.target == (
        "/v2/stocks/bars?symbols=SPY&timeframe=1Day"
        "&start=2016-01-01T00%3A00%3A00Z"
        "&end=2023-12-31T23%3A59%3A59.999999Z"
        "&limit=10000&adjustment=all&asof=-&feed=sip&currency=USD&sort=asc"
    )
    assert request.public_headers == (("Accept", "application/json"),)
    assert not {name.casefold() for name, _ in request.public_headers} & {
        "authorization",
        "apca-api-key-id",
        "apca-api-secret-key",
    }

    paged = build_alpaca_request(HistoricalBarsRequest("SPY", page_token="next+/token"))
    assert paged.target.endswith("&page_token=next%2B%2Ftoken")


def test_alpaca_page_parser_accepts_documented_multi_symbol_bar_fields() -> None:
    request = HistoricalBarsRequest("SPY")
    payload = (
        b'{"bars":{"SPY":['
        b'{"t":"2016-01-04T05:00:00Z","o":100.0,"h":101,"l":99,'
        b'"c":100.5,"v":123,"n":50,"vw":100.25},'
        b'{"t":"2016-01-05T05:00:00Z","o":100.5,"h":102,"l":100,'
        b'"c":101.5,"v":124}]},"next_page_token":"next/2"}'
    )

    page = parse_alpaca_page(payload, request)

    assert tuple(bar.symbol.value for bar in page.bars) == ("SPY", "SPY")
    assert page.bars[0].open == Decimal("100.0")
    assert page.bars[0].close == Decimal("100.5")
    assert page.bars[0].timestamp == datetime(2016, 1, 4, 5, tzinfo=UTC)
    assert page.next_page_token == "next/2"


def test_alpaca_page_parser_accepts_optional_requested_currency() -> None:
    payload = _alpaca_json_page("SPY", _bars("SPY")[:1], None, currency=CURRENCY)

    page = parse_alpaca_page(payload, HistoricalBarsRequest("SPY"))

    assert len(page.bars) == 1
    assert page.next_page_token is None


@pytest.mark.parametrize(
    "payload,match",
    [
        (
            b'{"bars":{"QQQ":[]},"next_page_token":null}',
            "unexpected symbol",
        ),
        (
            b'{"bars":{"SPY":[{"t":"2016-01-04T05:00:00Z",'
            b'"o":100,"h":101,"l":99,"c":100,"v":1,"x":0}]},'
            b'"next_page_token":null}',
            "bar fields",
        ),
        (
            b'{"bars":{"SPY":[{"t":"2024-01-02T05:00:00Z",'
            b'"o":100,"h":101,"l":99,"c":100,"v":1}]},'
            b'"next_page_token":null}',
            "outside the requested interval",
        ),
        (
            b'{"bars":{"SPY":[{"t":"2016-01-04T05:00:00Z",'
            b'"t":"2016-01-04T05:00:00Z","o":100,"h":101,"l":99,'
            b'"c":100,"v":1}]},"next_page_token":null}',
            "duplicate JSON field",
        ),
        (
            _alpaca_json_page("SPY", _bars("SPY")[:1], None, currency="EUR"),
            "provider response currency is invalid",
        ),
        (
            _alpaca_json_page("SPY", _bars("SPY")[:1], None, currency=123),
            "provider response currency is invalid",
        ),
        (
            b'{"bars":{"SPY":[]},"next_page_token":null,"unexpected":1}',
            "provider response fields",
        ),
        (
            b'{"bars":{"SPY":[]},"currency":"USD","currency":"USD",'
            b'"next_page_token":null}',
            "duplicate JSON field",
        ),
        (
            b'{"bars":{"SPY":[{"t":"2016-01-04T05:00:00Z",'
            b'"o":NaN,"h":101,"l":99,"c":100,"v":1}]},'
            b'"next_page_token":null}',
            "non-finite JSON number",
        ),
    ],
)
def test_alpaca_page_parser_rejects_malformed_or_out_of_scope_pages(
    payload: bytes, match: str
) -> None:
    with pytest.raises(FilteredTrendDataError, match=match):
        parse_alpaca_page(payload, HistoricalBarsRequest("SPY"))


def test_alpaca_page_parser_enforces_four_megabyte_bound() -> None:
    with pytest.raises(FilteredTrendDataError, match="size or type"):
        parse_alpaca_page(
            b" " * (MAX_PROVIDER_PAGE_BYTES + 1), HistoricalBarsRequest("SPY")
        )


def test_fake_alpaca_json_transport_acquires_and_stores_dataset(tmp_path: Path) -> None:
    class FakeSender:
        def __init__(self) -> None:
            self.requests = []

        def __call__(self, provider_request) -> bytes:
            self.requests.append(provider_request)
            parameters = parse_qs(urlsplit(provider_request.target).query)
            symbol = parameters["symbols"][0]
            assert parameters["end"] == ["2023-12-31T23:59:59.999999Z"]
            assert parameters["adjustment"] == ["all"]
            assert parameters["feed"] == ["sip"]
            assert parameters["currency"] == ["USD"]
            offset = int(parameters.get("page_token", ["0"])[0])
            source_bars = _bars(symbol)
            page_size = 1300
            end = min(offset + page_size, len(source_bars))
            token = str(end) if end < len(source_bars) else None
            return _alpaca_json_page(
                symbol, source_bars[offset:end], token, currency=CURRENCY
            )

    sender = FakeSender()
    dataset = acquire_dataset(AlpacaPageTransport(sender))
    artifact = tmp_path / "alpaca-fixture.json"

    write_dataset(artifact, dataset)
    loaded = read_dataset(artifact)

    assert dataset.identity == loaded.identity
    assert len(sender.requests) > len(UNIVERSE)
    assert all(
        request.public_headers == (("Accept", "application/json"),)
        for request in sender.requests
    )
