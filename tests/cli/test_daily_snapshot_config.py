from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_bot.cli.daily_snapshot_config import (
    load_daily_snapshot_capture_config,
)
from trading_bot.cli.exceptions import (
    DailySnapshotConfigJsonError,
    DailySnapshotConfigValidationError,
)
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    AdjustmentType,
    Timeframe,
)

REQUEST_ID = "98dbdaca-e14b-5f10-8ca9-3650e18aa1d8"


def valid_config() -> dict:
    return {
        "schema_version": 1,
        "request_id": REQUEST_ID,
        "symbols": ["SPY", "QQQ"],
        "calendar": {
            "calendar_id": "XNYS",
            "version": "nyse-regular-sessions-1998-2100-v1",
            "exchange_timezone": "America/New_York",
        },
        "timeframe": "1D",
        "adjustment": "RAW",
        "provider": {
            "provider_id": "alpaca-market-data",
            "adapter_version": 1,
            "operation": "historical-stock-bars-v2-raw-usd-no-asof",
            "feed": "sip",
        },
    }


def write_config(path: Path, value: object | None = None) -> Path:
    retained = valid_config() if value is None else value
    path.write_text(json.dumps(retained), encoding="utf-8", newline="")
    return path


def test_exact_version_one_config_loads_in_caller_symbol_order(
    tmp_path: Path,
) -> None:
    loaded = load_daily_snapshot_capture_config(write_config(tmp_path / "capture.json"))

    assert tuple(str(symbol) for symbol in loaded.symbols) == ("SPY", "QQQ")
    assert loaded.calendar == XNYS_CALENDAR_DESCRIPTOR
    assert loaded.provider == ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
    assert loaded.timeframe is Timeframe.DAY_1
    assert loaded.adjustment is AdjustmentType.RAW
    assert str(loaded.request_id) == REQUEST_ID


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("schema_version", 2),
        ("request_id", REQUEST_ID.upper()),
        ("symbols", []),
        ("symbols", ["spy"]),
        ("symbols", ["SPY", "SPY"]),
        ("timeframe", "1Min"),
        ("adjustment", "SPLIT_ADJUSTED"),
    ],
)
def test_wrong_root_values_fail_closed(
    tmp_path: Path,
    path: str,
    value: object,
) -> None:
    config = valid_config()
    config[path] = value

    with pytest.raises(DailySnapshotConfigValidationError):
        load_daily_snapshot_capture_config(
            write_config(tmp_path / "capture.json", config)
        )


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("calendar", "version", "other-calendar"),
        ("provider", "provider_id", "other-provider"),
        ("provider", "adapter_version", True),
        ("provider", "feed", "iex"),
        ("provider", "operation", "historical-stock-bars-v2"),
    ],
)
def test_wrong_fixed_descriptor_values_fail_closed(
    tmp_path: Path,
    section: str,
    field: str,
    value: object,
) -> None:
    config = valid_config()
    config[section][field] = value

    with pytest.raises(DailySnapshotConfigValidationError):
        load_daily_snapshot_capture_config(
            write_config(tmp_path / "capture.json", config)
        )


def test_unknown_missing_duplicate_and_nonstandard_json_fail(
    tmp_path: Path,
) -> None:
    unknown = valid_config()
    unknown["unknown"] = 1
    with pytest.raises(DailySnapshotConfigValidationError):
        load_daily_snapshot_capture_config(
            write_config(tmp_path / "unknown.json", unknown)
        )

    missing = valid_config()
    del missing["provider"]
    with pytest.raises(DailySnapshotConfigValidationError):
        load_daily_snapshot_capture_config(
            write_config(tmp_path / "missing.json", missing)
        )

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":1,"schema_version":1}',
        encoding="utf-8",
    )
    with pytest.raises(DailySnapshotConfigJsonError):
        load_daily_snapshot_capture_config(duplicate)

    constant = tmp_path / "constant.json"
    constant.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(DailySnapshotConfigJsonError):
        load_daily_snapshot_capture_config(constant)
