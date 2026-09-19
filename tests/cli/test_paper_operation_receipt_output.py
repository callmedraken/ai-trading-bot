"""Focused fixed-layout receipt commit safety coverage."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli.checkpoint_transition_output import validate_output_parent
from trading_bot.cli.paper_operation_output_capability import (
    PaperOperationOutputCapability,
)
from trading_bot.cli.paper_operation_receipt_output import (
    PaperOperationReceiptOutputError,
    ReceiptCommitVerificationPhase,
    commit_paper_operation_receipt,
)

_OPERATION_ID = UUID("84754a78-0bf3-5c53-af0a-1f8c5606d4f4")
_PAYLOAD = b'{"receipt":"canonical-test"}\n'


def test_commit_creates_exact_parent_layout_and_verifies_both_rereads(
    tmp_path: Path,
) -> None:
    phases: list[ReceiptCommitVerificationPhase] = []
    payloads: list[bytes] = []

    def verify(payload: bytes, phase: ReceiptCommitVerificationPhase) -> None:
        payloads.append(payload)
        phases.append(phase)

    result = commit_paper_operation_receipt(
        validate_output_parent(tmp_path),
        operation_id=_OPERATION_ID,
        receipt_payload=_PAYLOAD,
        verifier=verify,
    )

    assert phases == [
        ReceiptCommitVerificationPhase.STAGED_REREAD,
        ReceiptCommitVerificationPhase.FINALIZED_REREAD,
    ]
    assert payloads == [_PAYLOAD, _PAYLOAD]
    assert result.payload == _PAYLOAD
    assert result.receipt_path.read_bytes() == _PAYLOAD
    assert {item.name for item in result.directory.iterdir()} == {
        f"paper-operation-receipt-{_OPERATION_ID}.json"
    }
    assert {item.name for item in (tmp_path / "paper-operations").iterdir()} == {
        f"paper-operation-{_OPERATION_ID}"
    }


def test_capability_mode_requires_preexisting_operations_parent(
    tmp_path: Path,
) -> None:
    parent = validate_output_parent(tmp_path)
    events: list[str] = []

    class Capability(PaperOperationOutputCapability):
        def verify_parent(self, path: Path) -> None:
            events.append(f"verify:{path.name}")

        def create_staging_directory(self, path: Path) -> None:
            pytest.fail("missing production parent reached staging create")

        def write_staged_file(self, path: Path, payload: bytes) -> None:
            pytest.fail("missing production parent reached file write")

        def verify_staged_directory(self, path: Path) -> None:
            pytest.fail("missing production parent reached staging verification")

        def verify_staged_file(self, path: Path) -> None:
            pytest.fail("missing production parent reached file verification")

        def finalize_directory(self, staging: Path, final: Path) -> None:
            pytest.fail("missing production parent reached finalization")

        def verify_finalized_directory(self, path: Path) -> None:
            pytest.fail("missing production parent reached final verification")

        def verify_finalized_file(self, path: Path) -> None:
            pytest.fail("missing production parent reached final verification")

    with pytest.raises(
        PaperOperationReceiptOutputError,
        match="must already exist",
    ):
        commit_paper_operation_receipt(
            parent,
            operation_id=_OPERATION_ID,
            receipt_payload=_PAYLOAD,
            verifier=lambda payload, phase: None,
            output_capability=Capability(),
        )
    assert not (tmp_path / "paper-operations").exists()
    assert events == [f"verify:{tmp_path.name}"]


def test_staged_verifier_mutation_is_preserved_and_never_finalized(
    tmp_path: Path,
) -> None:
    staging = (
        tmp_path / "paper-operations" / f".paper-operation-{_OPERATION_ID}.staging"
    )

    def mutate(payload: bytes, phase: ReceiptCommitVerificationPhase) -> None:
        if phase is ReceiptCommitVerificationPhase.STAGED_REREAD:
            (staging / "unexpected").write_bytes(b"x")

    with pytest.raises(PaperOperationReceiptOutputError):
        commit_paper_operation_receipt(
            validate_output_parent(tmp_path),
            operation_id=_OPERATION_ID,
            receipt_payload=_PAYLOAD,
            verifier=mutate,
        )

    assert staging.is_dir()
    assert (staging / "unexpected").read_bytes() == b"x"
    assert not (
        tmp_path / "paper-operations" / f"paper-operation-{_OPERATION_ID}"
    ).exists()


def test_finalized_verifier_mutation_fails_closed_without_repair(
    tmp_path: Path,
) -> None:
    final = tmp_path / "paper-operations" / f"paper-operation-{_OPERATION_ID}"
    receipt = final / f"paper-operation-receipt-{_OPERATION_ID}.json"

    def mutate(payload: bytes, phase: ReceiptCommitVerificationPhase) -> None:
        if phase is ReceiptCommitVerificationPhase.FINALIZED_REREAD:
            receipt.write_bytes(b"altered")

    with pytest.raises(PaperOperationReceiptOutputError):
        commit_paper_operation_receipt(
            validate_output_parent(tmp_path),
            operation_id=_OPERATION_ID,
            receipt_payload=_PAYLOAD,
            verifier=mutate,
        )

    assert final.is_dir()
    assert receipt.read_bytes() == b"altered"


@pytest.mark.parametrize(
    "hostile_name",
    (
        "PAPER-OPERATIONS",
        f"Paper-Operation-{_OPERATION_ID}",
        f".Paper-Operation-{_OPERATION_ID}.Staging",
    ),
)
def test_casefold_collisions_block_without_replacement(
    tmp_path: Path,
    hostile_name: str,
) -> None:
    if hostile_name == "PAPER-OPERATIONS":
        hostile = tmp_path / hostile_name
    else:
        operations = tmp_path / "paper-operations"
        operations.mkdir()
        hostile = operations / hostile_name
    hostile.mkdir()

    with pytest.raises(PaperOperationReceiptOutputError):
        commit_paper_operation_receipt(
            validate_output_parent(tmp_path),
            operation_id=_OPERATION_ID,
            receipt_payload=_PAYLOAD,
            verifier=lambda *args: None,
        )

    assert hostile.is_dir()


def test_final_collision_is_never_overwritten(tmp_path: Path) -> None:
    operations = tmp_path / "paper-operations"
    final = operations / f"paper-operation-{_OPERATION_ID}"
    final.mkdir(parents=True)
    hostile = final / "hostile"
    hostile.write_bytes(b"retain")

    with pytest.raises(PaperOperationReceiptOutputError):
        commit_paper_operation_receipt(
            validate_output_parent(tmp_path),
            operation_id=_OPERATION_ID,
            receipt_payload=_PAYLOAD,
            verifier=lambda *args: None,
        )

    assert hostile.read_bytes() == b"retain"
    assert not (operations / f".paper-operation-{_OPERATION_ID}.staging").exists()


@pytest.mark.parametrize(
    ("failed_read", "final_exists", "staging_exists"),
    ((1, False, True), (3, True, False)),
)
def test_bounded_reread_failure_preserves_crash_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_read: int,
    final_exists: bool,
    staging_exists: bool,
) -> None:
    from trading_bot.cli import paper_operation_receipt_output as output_module

    original = output_module.read_safe_regular_file
    calls = 0

    def fail_selected(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == failed_read:
            raise OSError("read failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(output_module, "read_safe_regular_file", fail_selected)
    with pytest.raises(PaperOperationReceiptOutputError):
        commit_paper_operation_receipt(
            validate_output_parent(tmp_path),
            operation_id=_OPERATION_ID,
            receipt_payload=_PAYLOAD,
            verifier=lambda *args: None,
        )

    operations = tmp_path / "paper-operations"
    final = operations / f"paper-operation-{_OPERATION_ID}"
    staging = operations / f".paper-operation-{_OPERATION_ID}.staging"
    assert final.exists() is final_exists
    assert staging.exists() is staging_exists


def test_linked_operations_parent_fails_closed_when_supported(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    operations = tmp_path / "paper-operations"
    try:
        operations.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")

    with pytest.raises(PaperOperationReceiptOutputError):
        commit_paper_operation_receipt(
            validate_output_parent(tmp_path),
            operation_id=_OPERATION_ID,
            receipt_payload=_PAYLOAD,
            verifier=lambda *args: None,
        )

    assert tuple(target.iterdir()) == ()
