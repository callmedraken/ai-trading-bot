"""Focused fixed-layout genesis and one-edge checkpoint transition coverage."""

# ruff: noqa: E501

from __future__ import annotations

import json
from hashlib import sha256

from tests.cli.test_verified_snapshot_paper_cycle import _config_bytes, _snapshot_bytes
from tests.runtime.test_verified_snapshot_preparation import _request, _verification

from trading_bot.cli.checkpoint_transition import (
    create_genesis_checkpoint,
    run_checkpointed_cycle,
    verify_checkpoint,
)
from trading_bot.cli.checkpoint_transition_config import (
    parse_checkpoint_transition_config,
    parse_genesis_checkpoint_config,
)
from trading_bot.market_data import canonical_decimal


def _genesis_bytes() -> bytes:
    request = _request(verification=_verification())
    return json.dumps(
        {
            "schema_version": 1,
            "opening_state": {
                "as_of": request.account_state.as_of.isoformat().replace("+00:00", "Z"),
                "cash": canonical_decimal(request.account_state.cash),
                "positions": [
                    {
                        "symbol": str(item.symbol),
                        "quantity": canonical_decimal(item.quantity),
                        "total_cost_basis": canonical_decimal(
                            item.quantity * item.average_cost
                        ),
                    }
                    for item in request.account_state.positions
                ],
                "realized_profit_loss": "0",
                "metadata": [],
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _transition_bytes() -> bytes:
    tree = json.loads(_config_bytes())
    del tree["account_state"]
    return json.dumps(tree, separators=(",", ":")).encode("utf-8")


def _no_action_transition_bytes() -> bytes:
    tree = json.loads(_transition_bytes())
    tree["target"]["quantities"] = [
        {"symbol": "SPY", "quantity": "10"},
        {"symbol": "QQQ", "quantity": "0"},
    ]
    tree["target"]["target_cash"] = "972.5"
    return json.dumps(tree, separators=(",", ":")).encode("utf-8")


def test_genesis_directory_is_fixed_layout_and_verifiable(tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    config = tmp_path / "genesis.json"
    config.write_bytes(_genesis_bytes())

    parsed = parse_genesis_checkpoint_config(config.read_bytes())
    outcome = create_genesis_checkpoint(config_path=config, output_directory=output)
    verified = verify_checkpoint(
        checkpoint_path=outcome.checkpoint_path,
        checkpoint_sha256=outcome.sha256,
        checkpoint_byte_length=outcome.byte_length,
    )

    assert outcome.checkpoint.account_state.cash == parsed.request.cash
    assert (
        outcome.directory.name
        == f"paper-account-genesis-{outcome.checkpoint.checkpoint_id}"
    )
    assert outcome.checkpoint_path.name == (
        f"paper-account-checkpoint-{outcome.checkpoint.checkpoint_id}.json"
    )
    assert verified.checkpoint_id == str(outcome.checkpoint.checkpoint_id)


def test_transition_is_idempotent_without_duplicate_execution_or_writes(
    tmp_path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    genesis_config = tmp_path / "genesis.json"
    transition_config = tmp_path / "transition.json"
    snapshot = tmp_path / "snapshot.json"
    genesis_config.write_bytes(_genesis_bytes())
    transition_config.write_bytes(_transition_bytes())
    snapshot.write_bytes(_snapshot_bytes())
    genesis = create_genesis_checkpoint(
        config_path=genesis_config, output_directory=output
    )
    parsed = parse_checkpoint_transition_config(transition_config.read_bytes())

    first = run_checkpointed_cycle(
        checkpoint_path=genesis.checkpoint_path,
        snapshot_path=snapshot,
        config_path=transition_config,
        output_directory=output,
    )
    before = (first.report_path.read_bytes(), first.checkpoint_path.read_bytes())
    second = run_checkpointed_cycle(
        checkpoint_path=genesis.checkpoint_path,
        snapshot_path=snapshot,
        config_path=transition_config,
        output_directory=output,
    )
    edge = verify_checkpoint(
        checkpoint_path=first.checkpoint_path,
        prior_checkpoint_path=genesis.checkpoint_path,
        cycle_report_path=first.report_path,
        snapshot_path=snapshot,
    )

    assert first.status == "ACCEPTED"
    assert second.status == "ALREADY_APPLIED"
    assert second.report.evidence.request == parsed.request
    assert before == (
        second.report_path.read_bytes(),
        second.checkpoint_path.read_bytes(),
    )
    assert edge.edge
    assert sha256(first.report_path.read_bytes()).hexdigest() == first.report_sha256


def test_no_action_transition_uses_fixed_successor_layout(tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    genesis_config = tmp_path / "genesis.json"
    transition_config = tmp_path / "transition.json"
    snapshot = tmp_path / "snapshot.json"
    genesis_config.write_bytes(_genesis_bytes())
    transition_config.write_bytes(_no_action_transition_bytes())
    snapshot.write_bytes(_snapshot_bytes())
    genesis = create_genesis_checkpoint(
        config_path=genesis_config,
        output_directory=output,
    )

    outcome = run_checkpointed_cycle(
        checkpoint_path=genesis.checkpoint_path,
        snapshot_path=snapshot,
        config_path=transition_config,
        output_directory=output,
    )

    assert outcome.result.status.value == "NO_ACTION"
    assert (
        outcome.directory.name
        == f"paper-account-transition-{outcome.result.application_id}"
    )
