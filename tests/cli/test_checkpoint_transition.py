"""Focused fixed-layout genesis and one-edge checkpoint transition coverage."""

# ruff: noqa: E501

from __future__ import annotations

import json
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from tests.cli.test_verified_snapshot_paper_cycle import _config_bytes, _snapshot_bytes
from tests.market_data.daily_snapshot_test_support import (
    CAPTURED_AT,
    accepted_result,
    capture_request,
)
from tests.runtime.test_checkpointed_paper_cycle_successor import _target
from tests.runtime.test_paper_account_lineage_verification import _one_edge, _two_edges
from tests.runtime.test_verified_snapshot_preparation import _request, _verification

import trading_bot.cli.checkpoint_transition as checkpoint_transition
from trading_bot.cli.checkpoint_transition import (
    CheckpointTransitionVerificationError,
    create_genesis_checkpoint,
    run_checkpointed_cycle,
    verify_checkpoint,
    verify_main,
)
from trading_bot.cli.checkpoint_transition_config import (
    parse_checkpoint_transition_config,
    parse_genesis_checkpoint_config,
)
from trading_bot.market_data import canonical_decimal, serialize_daily_snapshot
from trading_bot.runtime import VerifiedPriorCheckpointKind


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


def _successor_start_artifacts(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    genesis_config = tmp_path / "genesis.json"
    first_config = tmp_path / "first-transition.json"
    first_snapshot = tmp_path / "first-snapshot.json"
    second_config = tmp_path / "second-transition.json"
    second_snapshot = tmp_path / "second-snapshot.json"
    genesis_config.write_bytes(_genesis_bytes())
    first_config.write_bytes(_transition_bytes())
    first_snapshot.write_bytes(_snapshot_bytes())
    genesis = create_genesis_checkpoint(
        config_path=genesis_config,
        output_directory=output,
    )
    first = run_checkpointed_cycle(
        checkpoint_path=genesis.checkpoint_path,
        snapshot_path=first_snapshot,
        config_path=first_config,
        output_directory=output,
    )
    accepted = accepted_result(
        request=capture_request(
            request_id=UUID("0e2eef9a-02e6-5ed5-a7dc-203e0a94b01a")
        ),
        captured_at=CAPTURED_AT + timedelta(hours=3),
    )
    snapshot = accepted.snapshot
    assert snapshot is not None
    second_snapshot_payload = serialize_daily_snapshot(snapshot)
    second_snapshot.write_bytes(second_snapshot_payload)
    tree = json.loads(_transition_bytes())
    tree["request_id"] = "01a3fceb-4e75-581f-bbeb-6d405e51cc0a"
    tree["snapshot_reference"] = {
        "snapshot_id": str(snapshot.snapshot_id),
        "artifact_sha256": sha256(second_snapshot_payload).hexdigest(),
        "artifact_byte_length": len(second_snapshot_payload),
    }
    tree["target"] = {
        "target_id": tree["target"]["target_id"],
        "quantities": [
            {"symbol": "SPY", "quantity": "0"},
            {"symbol": "QQQ", "quantity": "0"},
        ],
        "target_cash": "1997.5",
    }
    tree["planning_at"] = "2025-01-07T21:01:01Z"
    tree["submitted_at"] = "2025-01-07T21:02:01Z"
    tree["filled_at"] = "2025-01-07T23:00:01Z"
    second_config.write_bytes(json.dumps(tree, separators=(",", ":")).encode())
    return output, genesis, first, first_snapshot, second_config, second_snapshot


def _run_from_successor(tmp_path):
    output, genesis, first, first_snapshot, config, snapshot = (
        _successor_start_artifacts(tmp_path)
    )
    return run_checkpointed_cycle(
        checkpoint_path=first.checkpoint_path,
        snapshot_path=snapshot,
        config_path=config,
        output_directory=output,
        prior_checkpoint_path=genesis.checkpoint_path,
        prior_cycle_report_path=first.report_path,
        prior_snapshot_path=first_snapshot,
    )


def _reference(artifact, path: str) -> dict[str, object]:
    return {
        "artifact_id": str(artifact.artifact_id),
        "path": path,
        "sha256": artifact.sha256,
        "byte_length": artifact.byte_length,
    }


def _write_lineage_manifest(root: Path, lineage) -> Path:
    root.mkdir()
    genesis_name = "genesis.json"
    (root / genesis_name).write_bytes(lineage.genesis.payload)
    successor_references = []
    for index, artifact in enumerate(lineage.successors):
        name = f"successor-{index}.json"
        (root / name).write_bytes(artifact.payload)
        successor_references.append(_reference(artifact, name))
    report_references = []
    for index, artifact in enumerate(lineage.reports):
        name = f"report-{index}.json"
        (root / name).write_bytes(artifact.payload)
        report_references.append(_reference(artifact, name))
    snapshot_references = []
    for index, artifact in enumerate(lineage.snapshots):
        name = f"snapshot-{index}.json"
        (root / name).write_bytes(artifact.payload)
        snapshot_references.append(_reference(artifact, name))
    manifest = {
        "schema_version": 1,
        "genesis_checkpoint": _reference(lineage.genesis, genesis_name),
        "terminal_checkpoint_id": str(lineage.terminal_id),
        "successor_checkpoints": successor_references,
        "cycle_reports": report_references,
        "snapshots": snapshot_references,
    }
    path = root / "lineage-manifest.json"
    path.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    return path


def _later_edge_paths(tmp_path: Path):
    lineage = _two_edges()
    prior_lineage = type(lineage)(
        lineage.genesis,
        lineage.successors[0].artifact_id,
        lineage.successors[:1],
        lineage.reports[:1],
        lineage.snapshots[:1],
    )
    manifest = _write_lineage_manifest(tmp_path / "prior-lineage", prior_lineage)
    edge = tmp_path / "edge"
    edge.mkdir()
    prior = edge / "prior.json"
    report = edge / "report.json"
    snapshot = edge / "snapshot.json"
    successor = edge / "successor.json"
    prior.write_bytes(lineage.successors[0].payload)
    report.write_bytes(lineage.reports[1].payload)
    snapshot.write_bytes(lineage.snapshots[1].payload)
    successor.write_bytes(lineage.successors[1].payload)
    return lineage, manifest, prior, report, snapshot, successor


def _edge_arguments(
    successor: Path,
    prior: Path,
    report: Path,
    snapshot: Path,
    manifest: Path | None = None,
) -> list[str]:
    arguments = [
        "--checkpoint",
        str(successor),
        "--prior-checkpoint",
        str(prior),
        "--cycle-report",
        str(report),
        "--snapshot",
        str(snapshot),
        "--quiet",
    ]
    if manifest is not None:
        arguments.extend(("--prior-lineage-manifest", str(manifest)))
    return arguments


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
    command_exit = verify_main(
        _edge_arguments(
            first.checkpoint_path,
            genesis.checkpoint_path,
            first.report_path,
            snapshot,
        )
    )

    assert first.status == "ACCEPTED"
    assert second.status == "ALREADY_APPLIED"
    assert command_exit == 0
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


def test_successor_start_runs_verified_sequence_one_to_sequence_two_cycle(
    tmp_path,
) -> None:
    outcome = _run_from_successor(tmp_path)

    assert outcome.status == "ACCEPTED"
    assert outcome.result.prior_sequence == 1
    assert outcome.successor.sequence == 2


@pytest.mark.parametrize(
    "missing",
    ("prior_checkpoint_path", "prior_cycle_report_path", "prior_snapshot_path"),
)
def test_successor_start_requires_all_predecessor_edge_dependencies(
    tmp_path, missing
) -> None:
    output, genesis, first, first_snapshot, config, snapshot = (
        _successor_start_artifacts(tmp_path)
    )
    arguments = {
        "checkpoint_path": first.checkpoint_path,
        "snapshot_path": snapshot,
        "config_path": config,
        "output_directory": output,
        "prior_checkpoint_path": genesis.checkpoint_path,
        "prior_cycle_report_path": first.report_path,
        "prior_snapshot_path": first_snapshot,
    }
    arguments[missing] = None

    with pytest.raises(CheckpointTransitionVerificationError):
        run_checkpointed_cycle(**arguments)


def test_genesis_start_rejects_predecessor_edge_dependencies(tmp_path) -> None:
    output, genesis, first, first_snapshot, config, snapshot = (
        _successor_start_artifacts(tmp_path)
    )

    with pytest.raises(CheckpointTransitionVerificationError):
        run_checkpointed_cycle(
            checkpoint_path=genesis.checkpoint_path,
            snapshot_path=snapshot,
            config_path=config,
            output_directory=output,
            prior_checkpoint_path=genesis.checkpoint_path,
            prior_cycle_report_path=first.report_path,
            prior_snapshot_path=first_snapshot,
        )


@pytest.mark.parametrize("wrong", ("checkpoint", "report", "snapshot"))
def test_successor_start_rejects_wrong_producing_edge_dependency(
    tmp_path, wrong
) -> None:
    output, genesis, first, first_snapshot, config, snapshot = (
        _successor_start_artifacts(tmp_path)
    )
    arguments = {
        "checkpoint_path": first.checkpoint_path,
        "snapshot_path": snapshot,
        "config_path": config,
        "output_directory": output,
        "prior_checkpoint_path": genesis.checkpoint_path,
        "prior_cycle_report_path": first.report_path,
        "prior_snapshot_path": first_snapshot,
    }
    if wrong == "checkpoint":
        arguments["prior_checkpoint_path"] = first.checkpoint_path
    elif wrong == "report":
        bad = tmp_path / "wrong-report.json"
        bad.write_bytes(first.report_path.read_bytes() + b" ")
        arguments["prior_cycle_report_path"] = bad
    else:
        arguments["prior_snapshot_path"] = snapshot

    with pytest.raises(CheckpointTransitionVerificationError):
        run_checkpointed_cycle(**arguments)


def test_successor_start_rejects_tampered_successor_before_execution(tmp_path) -> None:
    output, genesis, first, first_snapshot, config, snapshot = (
        _successor_start_artifacts(tmp_path)
    )
    tampered = tmp_path / "tampered-successor.json"
    tampered.write_bytes(first.checkpoint_path.read_bytes() + b" ")

    with pytest.raises(CheckpointTransitionVerificationError):
        run_checkpointed_cycle(
            checkpoint_path=tampered,
            snapshot_path=snapshot,
            config_path=config,
            output_directory=output,
            prior_checkpoint_path=genesis.checkpoint_path,
            prior_cycle_report_path=first.report_path,
            prior_snapshot_path=first_snapshot,
        )


def test_successor_start_invokes_later_command_execution_once(
    monkeypatch, tmp_path
) -> None:
    output, genesis, first, first_snapshot, config, snapshot = (
        _successor_start_artifacts(tmp_path)
    )
    calls = 0
    original = checkpoint_transition.execute_checkpointed_verified_snapshot_paper_cycle

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        checkpoint_transition,
        "execute_checkpointed_verified_snapshot_paper_cycle",
        counted,
    )

    outcome = run_checkpointed_cycle(
        checkpoint_path=first.checkpoint_path,
        snapshot_path=snapshot,
        config_path=config,
        output_directory=output,
        prior_checkpoint_path=genesis.checkpoint_path,
        prior_cycle_report_path=first.report_path,
        prior_snapshot_path=first_snapshot,
    )

    assert outcome.successor.sequence == 2
    assert calls == 1


def test_later_edge_requires_and_accepts_explicit_verified_prior_lineage(
    tmp_path: Path,
) -> None:
    _, manifest, prior, report, snapshot, successor = _later_edge_paths(tmp_path)

    assert verify_main(_edge_arguments(successor, prior, report, snapshot)) == 6
    assert (
        verify_main(
            _edge_arguments(successor, prior, report, snapshot, manifest),
        )
        == 0
    )


def test_prior_lineage_terminal_must_match_supplied_prior_checkpoint(
    tmp_path: Path,
) -> None:
    lineage, _, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    genesis_only = type(lineage)(
        lineage.genesis,
        lineage.genesis.artifact_id,
        (),
        (),
        (),
    )
    manifest = _write_lineage_manifest(tmp_path / "genesis-only", genesis_only)

    with pytest.raises(
        CheckpointTransitionVerificationError,
        match="prior checkpoint does not match verified lineage terminal",
    ):
        verify_checkpoint(
            checkpoint_path=successor,
            prior_checkpoint_path=prior,
            cycle_report_path=report,
            snapshot_path=snapshot,
            prior_lineage_manifest_path=manifest,
        )


@pytest.mark.parametrize("mutation", ("hash", "length"))
def test_prior_lineage_rejects_altered_supplied_prior_evidence(
    tmp_path: Path,
    mutation: str,
) -> None:
    _, manifest, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    payload = bytearray(prior.read_bytes())
    if mutation == "hash":
        payload[-2] = ord("0") if payload[-2] != ord("0") else ord("1")
    else:
        payload.extend(b" ")
    prior.write_bytes(bytes(payload))

    assert (
        verify_main(
            _edge_arguments(successor, prior, report, snapshot, manifest),
        )
        == 4
    )


def test_unrelated_valid_lineage_is_not_prior_authority(tmp_path: Path) -> None:
    _, _, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    unrelated = _one_edge(target=_target("10", "0", "972.50"))
    manifest = _write_lineage_manifest(tmp_path / "unrelated", unrelated)

    assert (
        verify_main(
            _edge_arguments(successor, prior, report, snapshot, manifest),
        )
        == 4
    )


def test_failed_lineage_never_reaches_public_edge_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    tree = json.loads(manifest.read_text(encoding="utf-8"))
    tree["cycle_reports"][0]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(tree, separators=(",", ":")), encoding="utf-8")
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("edge verifier must not run")

    monkeypatch.setattr(
        checkpoint_transition,
        "verify_checkpointed_paper_cycle_successor_edge",
        forbidden,
    )

    assert (
        verify_main(
            _edge_arguments(successor, prior, report, snapshot, manifest),
        )
        == 4
    )
    assert calls == []


def test_verified_prior_is_passed_only_after_full_lineage_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, manifest, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    original = checkpoint_transition.verify_checkpointed_paper_cycle_successor_edge
    received = []

    def recording(*args, **kwargs):
        received.append(kwargs.get("verified_prior"))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        checkpoint_transition,
        "verify_checkpointed_paper_cycle_successor_edge",
        recording,
    )

    outcome = verify_checkpoint(
        checkpoint_path=successor,
        prior_checkpoint_path=prior,
        cycle_report_path=report,
        snapshot_path=snapshot,
        prior_lineage_manifest_path=manifest,
    )

    assert outcome.edge
    assert len(received) == 1
    assert received[0].kind is VerifiedPriorCheckpointKind.CYCLE_SUCCESSOR


def test_explicit_manifest_is_not_replaced_by_directory_scanning(
    tmp_path: Path,
) -> None:
    lineage, _, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    genesis_only = type(lineage)(
        lineage.genesis,
        lineage.genesis.artifact_id,
        (),
        (),
        (),
    )
    selected = _write_lineage_manifest(tmp_path / "selected", genesis_only)

    assert (
        verify_main(
            _edge_arguments(successor, prior, report, snapshot, selected),
        )
        == 4
    )


def test_malformed_prior_lineage_manifest_uses_read_syntax_exit(
    tmp_path: Path,
) -> None:
    _, _, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    manifest = tmp_path / "malformed.json"
    manifest.write_bytes(b'{"schema_version":1')

    assert (
        verify_main(
            _edge_arguments(successor, prior, report, snapshot, manifest),
        )
        == 3
    )


def test_invalid_prior_lineage_manifest_schema_uses_validation_exit(
    tmp_path: Path,
) -> None:
    _, manifest, prior, report, snapshot, successor = _later_edge_paths(tmp_path)
    tree = json.loads(manifest.read_text(encoding="utf-8"))
    tree["unknown"] = True
    manifest.write_text(json.dumps(tree, separators=(",", ":")), encoding="utf-8")

    assert (
        verify_main(
            _edge_arguments(successor, prior, report, snapshot, manifest),
        )
        == 5
    )


def test_prior_lineage_manifest_without_complete_edge_inputs_fails_closed(
    tmp_path: Path,
) -> None:
    lineage = _one_edge()
    manifest = _write_lineage_manifest(tmp_path / "lineage", lineage)
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_bytes(lineage.successors[0].payload)

    with pytest.raises(
        CheckpointTransitionVerificationError,
        match="prior lineage manifest requires complete edge inputs",
    ):
        verify_checkpoint(
            checkpoint_path=checkpoint,
            prior_lineage_manifest_path=manifest,
        )
