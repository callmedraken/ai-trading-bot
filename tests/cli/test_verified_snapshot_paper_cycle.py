"""Focused strict CLI tests for verified-snapshot paper-cycle artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from tests.market_data.daily_snapshot_test_support import accepted_result
from tests.runtime.test_verified_snapshot_preparation import _request, _verification

from trading_bot.cli.exceptions import (
    VerifiedSnapshotPaperCycleConfigJsonError,
    VerifiedSnapshotPaperCycleConfigValidationError,
)
from trading_bot.cli.verified_snapshot_cycle_config import (
    parse_verified_snapshot_paper_cycle_config,
)
from trading_bot.cli.verified_snapshot_paper_cycle import (
    run_main,
    run_verified_snapshot_paper_cycle,
    verify_main,
    verify_verified_snapshot_paper_cycle,
)
from trading_bot.market_data import (
    canonical_decimal,
    serialize_daily_snapshot,
)


def _config_bytes() -> bytes:
    request = _request(verification=_verification())
    policies = request.policies
    assumptions = policies.rebalance_assumptions
    limits = policies.risk_limits
    reference = request.snapshot_reference
    return json.dumps(
        {
            "schema_version": 1,
            "request_id": str(request.request_id),
            "snapshot_reference": {
                "snapshot_id": str(reference.snapshot_id),
                "artifact_sha256": reference.artifact_sha256,
                "artifact_byte_length": reference.artifact_byte_length,
            },
            "account_state": {
                "account_state_id": str(request.account_state.account_state_id),
                "as_of": _timestamp(request.account_state.as_of),
                "cash": canonical_decimal(request.account_state.cash),
                "positions": [
                    {
                        "symbol": str(item.symbol),
                        "quantity": canonical_decimal(item.quantity),
                        "average_cost": canonical_decimal(item.average_cost),
                    }
                    for item in request.account_state.positions
                ],
            },
            "target": {
                "target_id": str(request.target.target_id),
                "quantities": [
                    {
                        "symbol": str(item.symbol),
                        "quantity": canonical_decimal(item.quantity),
                    }
                    for item in request.target.quantities
                ],
                "target_cash": canonical_decimal(request.target.target_cash),
            },
            "open_references": [
                {
                    "symbol": str(item.symbol),
                    "session": item.session.session_date.isoformat(),
                    "caller_asserted_open_reference_price": canonical_decimal(
                        item.caller_asserted_open_reference_price
                    ),
                }
                for item in request.open_references
            ],
            "planning_at": _timestamp(request.planning_at),
            "submitted_at": _timestamp(request.submitted_at),
            "filled_at": _timestamp(request.filled_at),
            "metadata": [
                {"key": item.key, "value": item.value} for item in request.metadata
            ],
            "policies": {
                "rebalance_assumptions": {
                    "fixed_commission": canonical_decimal(assumptions.fixed_commission),
                    "allow_fractional_quantities": (
                        assumptions.allow_fractional_quantities
                    ),
                    "quantity_increment": canonical_decimal(
                        assumptions.quantity_increment
                    ),
                    "minimum_trade_notional": canonical_decimal(
                        assumptions.minimum_trade_notional
                    ),
                    "minimum_trade_quantity": canonical_decimal(
                        assumptions.minimum_trade_quantity
                    ),
                    "target_weight_tolerance": canonical_decimal(
                        assumptions.target_weight_tolerance
                    ),
                    "additional_execution_cash_buffer": canonical_decimal(
                        assumptions.additional_execution_cash_buffer
                    ),
                    "use_planned_sell_proceeds": assumptions.use_planned_sell_proceeds,
                },
                "portfolio_constraints": None,
                "proposal_policy": {
                    "allow_partial_plans": policies.proposal_policy.allow_partial_plans
                },
                "proposal_confidence": None,
                "risk_limits": {
                    "max_position_percent": canonical_decimal(
                        limits.max_position_percent
                    ),
                    "max_total_exposure_percent": canonical_decimal(
                        limits.max_total_exposure_percent
                    ),
                    "max_order_notional": None,
                    "max_new_position_percent": None,
                    "minimum_cash_reserve_percent": canonical_decimal(
                        limits.minimum_cash_reserve_percent
                    ),
                    "allow_fractional_shares": limits.allow_fractional_shares,
                    "fractional_increment": canonical_decimal(
                        limits.fractional_increment
                    ),
                    "allow_buying": limits.allow_buying,
                    "allow_selling": limits.allow_selling,
                    "estimated_commission": canonical_decimal(
                        limits.estimated_commission
                    ),
                },
                "risk_policy": {
                    "allow_sell_proceeds_for_later_buys": (
                        policies.risk_policy.allow_sell_proceeds_for_later_buys
                    )
                },
                "fill_policy": {
                    "slippage_basis_points": canonical_decimal(
                        policies.fill_policy.slippage_basis_points
                    ),
                    "fixed_commission": canonical_decimal(
                        policies.fill_policy.fixed_commission
                    ),
                },
                "trading_enabled": policies.trading_enabled,
            },
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _snapshot_bytes() -> bytes:
    snapshot = accepted_result().snapshot
    assert snapshot is not None
    return serialize_daily_snapshot(snapshot)


def _timestamp(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    timespec = "seconds" if normalized.microsecond == 0 else "microseconds"
    return normalized.isoformat(timespec=timespec).replace("+00:00", "Z")


def _paths(tmp_path):
    snapshot_path = tmp_path / "snapshot.json"
    config_path = tmp_path / "cycle-config.json"
    output_directory = tmp_path / "reports"
    output_directory.mkdir()
    snapshot_path.write_bytes(_snapshot_bytes())
    config_path.write_bytes(_config_bytes())
    return snapshot_path, config_path, output_directory


def test_config_parser_retains_complete_explicit_request() -> None:
    parsed = parse_verified_snapshot_paper_cycle_config(_config_bytes())

    assert parsed.preparation_request == _request(verification=_verification())


@pytest.mark.parametrize(
    "payload",
    (
        b"\xef\xbb\xbf{}",
        b'{"schema_version":1,"schema_version":1}',
        b'{"schema_version":true}',
        b'{"schema_version":1.0}',
        b'{"schema_version":NaN}',
        b'{"schema_version":1} trailing',
    ),
)
def test_config_parser_rejects_strict_json_failures(payload: bytes) -> None:
    with pytest.raises(
        (
            VerifiedSnapshotPaperCycleConfigJsonError,
            VerifiedSnapshotPaperCycleConfigValidationError,
        )
    ):
        parse_verified_snapshot_paper_cycle_config(payload)


def test_run_writes_verified_no_clobber_report_and_verify_replays(tmp_path) -> None:
    snapshot_path, config_path, output_directory = _paths(tmp_path)

    run = run_verified_snapshot_paper_cycle(
        snapshot_path=snapshot_path,
        config_path=config_path,
        output_directory=output_directory,
    )
    artifact = run.artifact
    verified = verify_verified_snapshot_paper_cycle(
        snapshot_path=snapshot_path,
        report_path=artifact.artifact_path,
        snapshot_sha256=sha256(_snapshot_bytes()).hexdigest(),
        snapshot_byte_length=len(_snapshot_bytes()),
        report_sha256=artifact.artifact_sha256,
        report_byte_length=artifact.artifact_byte_length,
    )

    assert artifact.artifact_path.exists()
    assert artifact.artifact_path.read_bytes() == serialize_report(artifact)
    assert verified.result_id == str(artifact.result.result_id)
    assert verified.preparation_id == str(artifact.result.preparation.preparation_id)
    assert verified.runtime_cycle_id == str(artifact.result.runtime_result.result_id)
    assert (
        run_main(
            [
                "--snapshot",
                str(snapshot_path),
                "--config",
                str(config_path),
                "--output-directory",
                str(output_directory),
                "--quiet",
            ]
        )
        == 7
    )


def serialize_report(artifact) -> bytes:
    from trading_bot.runtime import serialize_verified_snapshot_paper_cycle_result

    return serialize_verified_snapshot_paper_cycle_result(artifact.result)


def test_run_and_verify_cli_quiet_and_error_exit_codes(tmp_path, capsys) -> None:
    snapshot_path, config_path, output_directory = _paths(tmp_path)

    assert (
        run_main(
            [
                "--snapshot",
                str(snapshot_path),
                "--config",
                str(config_path),
                "--output-directory",
                str(output_directory),
                "--quiet",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == ""
    report_path = next(output_directory.glob("verified-snapshot-paper-cycle-*.json"))
    assert (
        verify_main(
            [
                "--snapshot",
                str(snapshot_path),
                "--report",
                str(report_path),
                "--quiet",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == ""
    assert (
        run_main(
            [
                "--snapshot",
                str(snapshot_path),
                "--config",
                str(tmp_path / "missing.json"),
                "--output-directory",
                str(output_directory),
            ]
        )
        == 3
    )
    assert (
        verify_main(
            [
                "--snapshot",
                str(snapshot_path),
                "--report",
                str(tmp_path / "missing.json"),
            ]
        )
        == 3
    )


def test_verify_rejects_tampered_report_with_exit_five(tmp_path) -> None:
    snapshot_path, config_path, output_directory = _paths(tmp_path)
    outcome = run_verified_snapshot_paper_cycle(
        snapshot_path=snapshot_path,
        config_path=config_path,
        output_directory=output_directory,
    )
    report = outcome.artifact.artifact_path
    report.write_bytes(report.read_bytes().replace(b'"result_id"', b'"result_Id"', 1))

    assert verify_main(["--snapshot", str(snapshot_path), "--report", str(report)]) == 5


def test_equal_runs_in_distinct_directories_write_identical_reports(tmp_path) -> None:
    snapshot_path, config_path, output_directory = _paths(tmp_path)
    second_directory = tmp_path / "other-reports"
    second_directory.mkdir()

    first = run_verified_snapshot_paper_cycle(
        snapshot_path=snapshot_path,
        config_path=config_path,
        output_directory=output_directory,
    )
    second = run_verified_snapshot_paper_cycle(
        snapshot_path=snapshot_path,
        config_path=config_path,
        output_directory=second_directory,
    )

    assert first.artifact.result == second.artifact.result
    assert (
        first.artifact.artifact_path.read_bytes()
        == second.artifact.artifact_path.read_bytes()
    )


def test_casefold_collision_is_not_overwritten(tmp_path) -> None:
    snapshot_path, config_path, output_directory = _paths(tmp_path)
    seed_directory = tmp_path / "seed"
    seed_directory.mkdir()
    seed = run_verified_snapshot_paper_cycle(
        snapshot_path=snapshot_path,
        config_path=config_path,
        output_directory=seed_directory,
    )
    collision = output_directory / seed.artifact.artifact_path.name.upper()
    collision.write_bytes(b"owned-by-someone-else")

    assert (
        run_main(
            [
                "--snapshot",
                str(snapshot_path),
                "--config",
                str(config_path),
                "--output-directory",
                str(output_directory),
                "--quiet",
            ]
        )
        == 7
    )
    assert collision.read_bytes() == b"owned-by-someone-else"


def test_staging_failure_cleans_only_this_invocations_staging(
    tmp_path, monkeypatch
) -> None:
    snapshot_path, config_path, output_directory = _paths(tmp_path)
    import trading_bot.cli.verified_snapshot_cycle_output as output

    monkeypatch.setattr(
        output,
        "_secure_read_staging",
        lambda *args: (_ for _ in ()).throw(OSError("deliberate staging failure")),
    )

    assert (
        run_main(
            [
                "--snapshot",
                str(snapshot_path),
                "--config",
                str(config_path),
                "--output-directory",
                str(output_directory),
                "--quiet",
            ]
        )
        == 7
    )
    assert tuple(output_directory.glob(".*.staging")) == ()
