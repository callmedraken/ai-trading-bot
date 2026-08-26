"""Manual one-shot production C3 daily-snapshot capture command."""

from __future__ import annotations

import argparse
import json
from datetime import date

from trading_bot.domain import Symbol
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
)
from trading_bot.runtime.windows_effectful_capture import ProductionCaptureRequest
from trading_bot.runtime.windows_effectful_capture_service import (
    ProductionCaptureInvocationResult,
    WindowsEffectfulDailySnapshotCapture,
)


class _CliUsageError(ValueError):
    pass


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _CliUsageError("invalid production capture arguments")


def build_parser() -> argparse.ArgumentParser:
    """Build the nonsecret manual production intent parser."""

    parser = _SanitizedArgumentParser(
        description="Capture one C3-authorized production daily snapshot."
    )
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--request-window-start", required=True)
    parser.add_argument("--request-window-end", required=True)
    parser.add_argument("--target-session-date", required=True)
    return parser


def _request(args: argparse.Namespace) -> ProductionCaptureRequest:
    return ProductionCaptureRequest(
        ordered_universe=tuple(Symbol(value) for value in args.symbols),
        request_window_start_date=date.fromisoformat(args.request_window_start),
        request_window_end_date=date.fromisoformat(args.request_window_end),
        target_session_date=date.fromisoformat(args.target_session_date),
    )


def _result_record(result: ProductionCaptureInvocationResult) -> dict[str, object]:
    return {
        "artifact_byte_length": result.artifact_byte_length,
        "artifact_sha256": result.artifact_sha256,
        "attempt_id": result.attempt_id,
        "claim_id": result.claim_id,
        "execution_id": result.execution_id,
        "http_status": result.http_status,
        "provider_call_disposition": result.provider_call_disposition,
        "provider_request_id": result.provider_request_id,
        "reservation_id": result.reservation_id,
        "selection_id": result.selection_id,
        "session_id": result.session_id,
        "snapshot_id": None if result.snapshot_id is None else str(result.snapshot_id),
        "status": "COMPLETED",
        "terminal_id": result.terminal_id,
        "terminal_state": result.terminal_state,
    }


def _emit(record: dict[str, object]) -> None:
    print(
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Acquire C1 authority and delegate exactly one request to capture_once."""

    capture: WindowsEffectfulDailySnapshotCapture | None = None
    result: ProductionCaptureInvocationResult | None = None
    failure = "PRODUCTION_CAPTURE_BLOCKED"
    try:
        args = build_parser().parse_args(argv)
        request = _request(args)
        authority = acquire_validated_production_authority()
        capture = WindowsEffectfulDailySnapshotCapture(authority)
        result = capture.capture_once(request)
    except (ValueError, TypeError):
        failure = "REQUEST_INVALID"
    except Exception:
        failure = "PRODUCTION_CAPTURE_BLOCKED"
    finally:
        if capture is not None:
            try:
                capture.close()
            except Exception:
                result = None
                failure = "CAPTURE_CLOSE_FAILED"

    if result is None:
        _emit({"reason": failure, "status": "BLOCKED"})
        return 8
    _emit(_result_record(result))
    return 0 if result.terminal_state == "SUCCEEDED" else 6


if __name__ == "__main__":
    raise SystemExit(main())
