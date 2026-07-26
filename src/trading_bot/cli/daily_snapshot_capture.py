"""One-shot orchestration for an audited Alpaca daily-snapshot artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.cli.daily_snapshot_config import (
    load_daily_snapshot_capture_config,
)
from trading_bot.cli.daily_snapshot_output import (
    DailySnapshotArtifactResult,
    install_daily_snapshot_artifact,
    validate_daily_snapshot_destination_directory,
)
from trading_bot.cli.exceptions import (
    DailySnapshotArtifactOutputError,
    DailySnapshotCaptureRejectedError,
    DailySnapshotConfigJsonError,
    DailySnapshotConfigReadError,
    DailySnapshotConfigValidationError,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotAcceptanceStatus,
    DailySnapshotSerializationError,
    DailySnapshotVerificationError,
    InvalidDailySnapshotCalendarError,
    InvalidDailySnapshotModelError,
    InvalidDailySnapshotProviderError,
    InvalidDailySnapshotRequestError,
    InvalidDailySnapshotResponseError,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.market_data.alpaca_daily_snapshot import (
    create_alpaca_daily_snapshot_provider,
)
from trading_bot.market_data.alpaca_http import (
    AlpacaHistoricalBarsTransport,
    StdlibAlpacaHistoricalBarsTransport,
)
from trading_bot.market_data.daily_snapshot_provider import capture_daily_snapshot
from trading_bot.market_data.exceptions import (
    AlpacaCredentialError,
    AlpacaResponseError,
    AlpacaTransportError,
)


def capture_daily_snapshot_artifact(
    *,
    config_path: Path,
    destination_directory: Path,
    transport: AlpacaHistoricalBarsTransport | None = None,
    clock: Callable[[], datetime] | None = None,
    environment: Mapping[str, str] | None = None,
) -> DailySnapshotArtifactResult:
    """Capture, accept, serialize, verify, stage, and finalize one snapshot."""
    loaded = load_daily_snapshot_capture_config(config_path)
    calendar = BoundMarketCalendar(
        XNYS_CALENDAR_DESCRIPTOR,
        NYSEMarketCalendar(),
    )
    destination = validate_daily_snapshot_destination_directory(destination_directory)
    capture_clock = _utc_now if clock is None else clock
    if not callable(capture_clock):
        raise DailySnapshotArtifactOutputError("capture clock must be callable")
    provider_transport = (
        StdlibAlpacaHistoricalBarsTransport() if transport is None else transport
    )
    provider = create_alpaca_daily_snapshot_provider(
        transport=provider_transport,
        clock=capture_clock,
        environment=os.environ if environment is None else environment,
    )
    requested_at = capture_clock()
    request = loaded.capture_request(requested_at)
    acceptance = capture_daily_snapshot(request, provider, calendar)
    if (
        acceptance.status is not DailySnapshotAcceptanceStatus.ACCEPTED
        or acceptance.snapshot is None
    ):
        raise DailySnapshotCaptureRejectedError(acceptance)
    snapshot = acceptance.snapshot
    payload = serialize_daily_snapshot(snapshot)
    artifact_sha256 = hashlib.sha256(payload).hexdigest()
    in_memory_verification = verify_daily_snapshot(
        payload,
        calendar,
        expected_sha256=artifact_sha256,
        expected_byte_length=len(payload),
    )
    if (
        not in_memory_verification.passed
        or in_memory_verification.snapshot != snapshot
        or in_memory_verification.snapshot is None
        or in_memory_verification.snapshot.snapshot_id != snapshot.snapshot_id
    ):
        raise DailySnapshotArtifactOutputError("in-memory snapshot verification failed")
    return install_daily_snapshot_artifact(
        destination=destination,
        snapshot=snapshot,
        payload=payload,
        in_memory_verification=in_memory_verification,
        calendar=calendar,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def build_parser() -> argparse.ArgumentParser:
    """Build the dedicated one-shot Alpaca capture parser."""
    parser = argparse.ArgumentParser(
        description="Capture one verified Alpaca daily market-data snapshot."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--destination-directory", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one audited daily capture and return a stable exit code."""
    args = build_parser().parse_args(argv)
    try:
        result = capture_daily_snapshot_artifact(
            config_path=args.config,
            destination_directory=args.destination_directory,
        )
    except (DailySnapshotConfigReadError, DailySnapshotConfigJsonError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except (
        DailySnapshotConfigValidationError,
        InvalidDailySnapshotCalendarError,
        InvalidDailySnapshotProviderError,
        InvalidDailySnapshotRequestError,
    ) as error:
        print(f"error: capture configuration is invalid: {error}", file=sys.stderr)
        return 4
    except (
        AlpacaCredentialError,
        AlpacaTransportError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 5
    except DailySnapshotCaptureRejectedError as error:
        result = error.result
        classification = getattr(result, "classification", None)
        value = "UNKNOWN" if classification is None else classification.value
        print(
            f"error: provider response rejected: classification={value}",
            file=sys.stderr,
        )
        for diagnostic in getattr(result, "diagnostics", ()):
            symbol = (
                ""
                if diagnostic.symbol is None
                else f" symbol={json.dumps(str(diagnostic.symbol))}"
            )
            ordinal = (
                ""
                if diagnostic.response_ordinal is None
                else f" ordinal={diagnostic.response_ordinal}"
            )
            print(
                f"  {diagnostic.code.value}{symbol}{ordinal}",
                file=sys.stderr,
            )
        return 6
    except (
        AlpacaResponseError,
        InvalidDailySnapshotModelError,
        InvalidDailySnapshotResponseError,
    ) as error:
        print(f"error: provider response is invalid: {error}", file=sys.stderr)
        return 6
    except (
        DailySnapshotSerializationError,
        DailySnapshotVerificationError,
        DailySnapshotArtifactOutputError,
    ) as error:
        print(f"error: snapshot artifact output failed: {error}", file=sys.stderr)
        cleanup_message = getattr(error, "cleanup_message", None)
        if cleanup_message is not None:
            print(f"cleanup warning: {cleanup_message}", file=sys.stderr)
        return 7
    if not args.quiet:
        print("Daily market-data snapshot capture: PASS")
        print(f"  snapshot ID: {result.snapshot.snapshot_id}")
        print(f"  target session: {result.snapshot.target_session.session_date}")
        print(
            "  symbols: "
            + ",".join(str(symbol) for symbol in result.snapshot.request.symbols)
        )
        print(
            f"  provider: {result.snapshot.provider.provider_id} "
            f"feed={result.snapshot.provider.feed}"
        )
        print(
            "  source payload: "
            f"sha256={result.snapshot.audit.source_payload.sha256} "
            f"bytes={result.snapshot.audit.source_payload.byte_length}"
        )
        print(
            "  artifact: "
            f"sha256={result.artifact_sha256} "
            f"bytes={result.artifact_byte_length}"
        )
        print(f"  destination: {json.dumps(str(result.artifact_path))}")
    if result.cleanup_warning is not None:
        print(f"cleanup warning: {result.cleanup_warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
