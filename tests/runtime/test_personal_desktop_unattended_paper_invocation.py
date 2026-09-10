"""Focused PD4-A canonical unattended-invocation coverage."""

import json
import os
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import uuid5

import pytest
from tests.market_data.daily_snapshot_test_support import calendar
from tests.runtime.test_manual_paper_strategy_plan import _binding
from tests.runtime.test_verified_snapshot_preparation import _policies

from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES,
    UNATTENDED_PAPER_INVOCATION_IDENTITY_MATERIAL_VERSION,
    UNATTENDED_PAPER_INVOCATION_NAMESPACE,
    UNATTENDED_PAPER_INVOCATION_SCHEMA,
    UNATTENDED_PAPER_POLICY_VERSION,
    PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    PersonalDesktopUnattendedPaperInvocationSerializationError,
    PersonalDesktopUnattendedPaperInvocationValidationError,
    PersonalDesktopUnattendedPaperInvocationVerificationError,
    create_personal_desktop_unattended_paper_invocation,
    parse_personal_desktop_unattended_paper_invocation,
    serialize_personal_desktop_unattended_paper_invocation,
    verify_personal_desktop_unattended_paper_invocation,
)
from trading_bot.strategies import MovingAverageCrossoverConfig


def _invocation():
    return create_personal_desktop_unattended_paper_invocation(_binding(), calendar())


def _payload(tree: object) -> bytes:
    return (
        json.dumps(
            tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def test_frozen_constants_and_deterministic_exact_round_trip() -> None:
    assert UNATTENDED_PAPER_INVOCATION_SCHEMA == (
        "personal-desktop-unattended-paper-invocation/v1"
    )
    assert UNATTENDED_PAPER_INVOCATION_IDENTITY_MATERIAL_VERSION == (
        "personal-desktop-unattended-paper-invocation-identity/v1"
    )
    assert str(UNATTENDED_PAPER_INVOCATION_NAMESPACE) == (
        "fd618526-0508-56be-b8e9-7316b813b585"
    )
    assert UNATTENDED_PAPER_POLICY_VERSION == (
        "personal-desktop-unattended-paper-policy/v1"
    )
    assert MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES == 16 * 1024 * 1024

    first = _invocation()
    second = _invocation()
    payload = serialize_personal_desktop_unattended_paper_invocation(first)
    parsed = parse_personal_desktop_unattended_paper_invocation(payload, calendar())
    verified = verify_personal_desktop_unattended_paper_invocation(
        payload,
        calendar(),
        expected_invocation_id=first.invocation_id,
        expected_artifact_sha256=sha256(payload).hexdigest(),
        expected_artifact_byte_length=len(payload),
    )

    assert first == second
    assert parsed == first
    assert verified == PersonalDesktopUnattendedPaperInvocationArtifactBinding(
        first,
        payload,
        sha256(payload).hexdigest(),
        len(payload),
        verified.replayed_plan,
    )
    assert verified.invocation == first


def test_invocation_id_matches_independent_framed_uuid5_material() -> None:
    binding = _binding()
    invocation = _invocation()
    plan = binding.plan
    session = plan.request_core.open_references[0].session
    parts = (
        UNATTENDED_PAPER_INVOCATION_IDENTITY_MATERIAL_VERSION,
        UNATTENDED_PAPER_POLICY_VERSION,
        plan.paper_account_id,
        str(plan.prior_checkpoint.checkpoint_id),
        session.session_date.isoformat(),
        str(plan.selected_c3_assertion.selection_id),
        str(plan.selected_c3_assertion.snapshot_id),
        str(plan.plan_id),
        binding.artifact_sha256,
        str(binding.artifact_byte_length),
    )
    material = "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)

    assert invocation.invocation_id == uuid5(
        UNATTENDED_PAPER_INVOCATION_NAMESPACE, material
    )


def test_embedded_plan_bytes_and_pd3_recovery_facts_survive_restart_replay() -> None:
    original = _binding()
    invocation = create_personal_desktop_unattended_paper_invocation(
        original, calendar()
    )
    payload = serialize_personal_desktop_unattended_paper_invocation(invocation)
    evidence = verify_personal_desktop_unattended_paper_invocation(payload, calendar())
    replayed = evidence.replayed_plan
    plan = replayed.plan

    assert evidence.artifact_bytes == payload
    assert plan == original.plan
    assert replayed.artifact_bytes == original.artifact_bytes
    assert replayed.checkpointed_request == original.checkpointed_request
    assert plan.caller_idempotency_key == original.plan.caller_idempotency_key
    assert plan.history_seed_artifact == original.plan.history_seed_artifact
    assert plan.selected_snapshot_artifact == original.plan.selected_snapshot_artifact
    assert plan.strategy_config == original.plan.strategy_config
    assert plan.prior_checkpoint == original.plan.prior_checkpoint
    assert plan.selected_c3_assertion == original.plan.selected_c3_assertion
    assert (
        plan.request_core.open_references == original.plan.request_core.open_references
    )
    assert plan.request_core.policies == original.plan.request_core.policies
    assert plan.request_core.planning_at == original.plan.request_core.planning_at
    assert plan.request_core.submitted_at == original.plan.request_core.submitted_at
    assert plan.request_core.filled_at == original.plan.request_core.filled_at
    assert plan.request_core.metadata == original.plan.request_core.metadata
    assert plan.request_core == original.plan.request_core


def test_creation_requires_exact_binding_and_replays_the_supplied_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.personal_desktop_unattended_paper_invocation as module

    binding = _binding()
    calls = 0
    original_verify = module.verify_manual_paper_strategy_plan

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(module, "verify_manual_paper_strategy_plan", counted)
    created = create_personal_desktop_unattended_paper_invocation(binding, calendar())

    assert type(created).__name__ == "PersonalDesktopUnattendedPaperInvocation"
    assert calls == 1
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationValidationError):
        create_personal_desktop_unattended_paper_invocation(object(), calendar())


def test_parse_and_verify_mandate_embedded_manual_plan_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.personal_desktop_unattended_paper_invocation as module

    payload = serialize_personal_desktop_unattended_paper_invocation(_invocation())

    def forbidden(*_args, **_kwargs):
        raise AssertionError("embedded manual plan replay was bypassed")

    monkeypatch.setattr(module, "verify_manual_paper_strategy_plan", forbidden)
    with pytest.raises(AssertionError, match="bypassed"):
        parse_personal_desktop_unattended_paper_invocation(payload, calendar())


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("plan_sha256", "0" * 64),
        ("plan_byte_length", 1),
        ("plan_id", "00000000-0000-0000-0000-000000000001"),
    ),
)
def test_wrong_plan_detached_evidence_or_id_blocks(field: str, value: object) -> None:
    tree = json.loads(
        serialize_personal_desktop_unattended_paper_invocation(_invocation())
    )
    tree[field] = value
    with pytest.raises(
        (
            PersonalDesktopUnattendedPaperInvocationSerializationError,
            PersonalDesktopUnattendedPaperInvocationVerificationError,
        )
    ):
        parse_personal_desktop_unattended_paper_invocation(_payload(tree), calendar())


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("paper_account_id", "paper.account-2"),
        ("predecessor_checkpoint_id", "00000000-0000-0000-0000-000000000001"),
        ("execution_session", "2025-01-08"),
        ("selection_id", "00000000-0000-0000-0000-000000000001"),
        ("selected_snapshot_id", "00000000-0000-0000-0000-000000000001"),
    ),
)
def test_wrong_top_level_binding_blocks(field: str, value: object) -> None:
    tree = json.loads(
        serialize_personal_desktop_unattended_paper_invocation(_invocation())
    )
    tree[field] = value
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(_payload(tree), calendar())


def test_wrong_invocation_id_unknown_missing_and_duplicate_fields_block() -> None:
    payload = serialize_personal_desktop_unattended_paper_invocation(_invocation())
    tree = json.loads(payload)
    tree["invocation_id"] = "00000000-0000-0000-0000-000000000001"
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(_payload(tree), calendar())

    extra = json.loads(payload)
    extra["unknown"] = True
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(_payload(extra), calendar())

    missing = json.loads(payload)
    del missing["selection_id"]
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(
            _payload(missing), calendar()
        )

    duplicate = payload.replace(
        b'"schema":"personal-desktop-unattended-paper-invocation/v1"',
        b'"schema":"personal-desktop-unattended-paper-invocation/v1",'
        b'"schema":"personal-desktop-unattended-paper-invocation/v1"',
    )
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(duplicate, calendar())


@pytest.mark.parametrize(
    "candidate",
    (
        lambda payload: json.dumps(json.loads(payload), indent=2).encode() + b"\n",
        lambda payload: payload[:-1],
        lambda payload: b"\xef\xbb\xbf" + payload,
        lambda _payload: b"{not-json}\n",
        lambda _payload: b"\xff\n",
    ),
)
def test_malformed_noncanonical_and_invalid_utf8_artifacts_block(candidate) -> None:
    payload = serialize_personal_desktop_unattended_paper_invocation(_invocation())
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(
            candidate(payload), calendar()
        )


def test_oversized_artifact_blocks_before_replay() -> None:
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(
            b"x" * (MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES + 1),
            calendar(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("invocation_id", "00000000-0000-0000-0000-000000000001".upper()),
        ("plan_sha256", "A" * 64),
        ("execution_session", "2025-1-7"),
    ),
)
def test_noncanonical_uuid_sha_and_date_forms_block(field: str, value: str) -> None:
    tree = json.loads(
        serialize_personal_desktop_unattended_paper_invocation(_invocation())
    )
    tree[field] = value
    with pytest.raises(PersonalDesktopUnattendedPaperInvocationSerializationError):
        parse_personal_desktop_unattended_paper_invocation(_payload(tree), calendar())


def test_identity_ignores_environment_cwd_and_process_scheduler_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    first = _invocation()
    monkeypatch.setenv("PD4_SCHEDULER_TASK", r"Z:\different\task")
    monkeypatch.setenv("PD4_INVOCATION_PATH", r"Z:\different\invocation.json")
    monkeypatch.chdir(tmp_path)
    second = _invocation()

    assert first == second
    assert first.invocation_id == second.invocation_id
    assert os.environ["PD4_SCHEDULER_TASK"] == r"Z:\different\task"


@pytest.mark.parametrize(
    "build_changed",
    (
        lambda: _binding(caller_key="manual-cycle-changed"),
        lambda: _binding(open_price="13"),
        lambda: _binding(config=MovingAverageCrossoverConfig(2, 3, Decimal("3"))),
        lambda: _binding(
            policies=replace(_policies(), proposal_confidence=Decimal("0.5"))
        ),
        lambda: _binding(
            planning_at=(
                _binding().checkpointed_request.planning_at + timedelta(seconds=1)
            ),
            submitted_at=(
                _binding().checkpointed_request.submitted_at + timedelta(seconds=1)
            ),
        ),
        lambda: _binding(metadata=(MetadataEntry("source", "changed"),)),
    ),
)
def test_changed_valid_plan_semantics_change_invocation_identity(build_changed) -> None:
    baseline = _invocation()
    changed_binding = build_changed()
    changed = create_personal_desktop_unattended_paper_invocation(
        changed_binding, calendar()
    )
    assert changed.plan_id != baseline.plan_id
    assert changed.invocation_id != baseline.invocation_id


def test_creation_does_not_require_effect_or_production_modules() -> None:
    import trading_bot.runtime.personal_desktop_unattended_paper_invocation as module

    assert not any(
        name in module.__dict__
        for name in (
            "PaperPortfolioRuntime",
            "PaperOperationIntent",
            "WindowsPaperOperationRuntime",
            "WindowsSelectedC3SnapshotReadAuthority",
        )
    )
