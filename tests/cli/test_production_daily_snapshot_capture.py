from __future__ import annotations

import json
from datetime import date
from uuid import UUID

import trading_bot.cli.production_daily_snapshot_capture as cli_module
from trading_bot.domain import Symbol
from trading_bot.runtime.windows_effectful_capture_service import (
    ProductionCaptureInvocationResult,
)


def _result() -> ProductionCaptureInvocationResult:
    return ProductionCaptureInvocationResult(
        session_id="11111111-1111-4111-8111-111111111111",
        attempt_id="22222222-2222-4222-8222-222222222222",
        claim_id="33333333-3333-4333-8333-333333333333",
        reservation_id="44444444-4444-4444-8444-444444444444",
        execution_id="55555555-5555-4555-8555-555555555555",
        terminal_id="66666666-6666-4666-8666-666666666666",
        selection_id="77777777-7777-4777-8777-777777777777",
        terminal_state="SUCCEEDED",
        provider_call_disposition="CONFIRMED",
        snapshot_id=UUID("88888888-8888-4888-8888-888888888888"),
        artifact_sha256="ab" * 32,
        artifact_byte_length=123,
    )


def test_parser_exposes_only_frozen_nonsecret_intent() -> None:
    parser = cli_module.build_parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option != "--help"
    }
    assert option_strings == {
        "-h",
        "--symbols",
        "--request-window-start",
        "--request-window-end",
        "--target-session-date",
    }


def test_cli_acquires_c1_delegates_to_capture_once_and_always_closes(
    monkeypatch, capsys
) -> None:
    authority = object()
    calls: list[object] = []

    class FakeCapture:
        def __init__(self, candidate: object) -> None:
            assert candidate is authority
            calls.append("constructed")

        def capture_once(self, request):
            calls.append(request)
            return _result()

        def close(self) -> None:
            calls.append("closed")

    monkeypatch.setattr(
        cli_module, "acquire_validated_production_authority", lambda: authority
    )
    monkeypatch.setattr(cli_module, "WindowsEffectfulDailySnapshotCapture", FakeCapture)

    exit_code = cli_module.main(
        [
            "--symbols",
            "AAPL",
            "MSFT",
            "--request-window-start",
            "2026-08-17",
            "--request-window-end",
            "2026-08-17",
            "--target-session-date",
            "2026-08-18",
        ]
    )

    assert exit_code == 0
    assert calls[0] == "constructed"
    assert calls[-1] == "closed"
    assert calls[1].ordered_universe == (Symbol("AAPL"), Symbol("MSFT"))
    assert calls[1].request_window_start_date == date(2026, 8, 17)
    record = json.loads(capsys.readouterr().out)
    assert record["status"] == "COMPLETED"
    assert record["terminal_state"] == "SUCCEEDED"
    assert record["artifact_sha256"] == "ab" * 32
    assert record["http_status"] is None
    assert record["provider_request_id"] is None


def test_cli_failure_output_is_one_sanitized_record(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli_module,
        "acquire_validated_production_authority",
        lambda: (_ for _ in ()).throw(RuntimeError("secret native detail")),
    )

    exit_code = cli_module.main(
        [
            "--symbols",
            "AAPL",
            "--request-window-start",
            "2026-08-17",
            "--request-window-end",
            "2026-08-17",
            "--target-session-date",
            "2026-08-18",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 8
    assert output.err == ""
    assert output.out.count("\n") == 1
    assert json.loads(output.out) == {
        "reason": "PRODUCTION_CAPTURE_BLOCKED",
        "status": "BLOCKED",
    }
    assert "secret native detail" not in output.out


def test_cli_result_record_exposes_only_sanitized_http_evidence() -> None:
    result = ProductionCaptureInvocationResult(
        session_id="11111111-1111-4111-8111-111111111111",
        attempt_id="22222222-2222-4222-8222-222222222222",
        claim_id="33333333-3333-4333-8333-333333333333",
        reservation_id="44444444-4444-4444-8444-444444444444",
        execution_id="55555555-5555-4555-8555-555555555555",
        terminal_id="66666666-6666-4666-8666-666666666666",
        selection_id=None,
        terminal_state="FAILED",
        provider_call_disposition="CONFIRMED",
        http_status=403,
        provider_request_id="safe-request-403",
    )

    record = cli_module._result_record(result)

    assert record["http_status"] == 403
    assert record["provider_request_id"] == "safe-request-403"
    assert "provider_code" not in record
