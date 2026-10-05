"""Focused read-only D10 historical settlement inventory and proof tests."""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.runtime.test_personal_desktop_paper_account_security import (
    SID,
)
from tests.runtime.test_personal_desktop_unattended_paper_decision_intent import (
    _calendar,
    _decision_binding,
)
from tests.runtime.test_personal_desktop_unattended_paper_decision_storage import (
    _empty_api,
    _put_final,
)
from tests.runtime.test_personal_desktop_unattended_paper_invocation_storage import (
    Observer,
)

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import (
    personal_desktop_unattended_historical_settlement_audit as audit,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_storage as storage,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationReceiptVerificationStatus,
    PaperOperationStatus,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    CompleteDecisionNamespaceClassification as Namespace,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    CompleteDecisionNamespaceResult,
    FinalizedDecisionIdentity,
)
from trading_bot.runtime.windows_authority import AuthorityObjectError

Status = audit.HistoricalSettlementAuditClassification


def _fake_binding(
    day: int, identity: int
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding:
    binding = object.__new__(
        PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
    )
    object.__setattr__(
        binding,
        "decision",
        SimpleNamespace(
            intended_execution_session=TradingSession(date(2026, 8, day)),
            decision_id=UUID(int=identity),
        ),
    )
    return binding


def _dependencies(
    monkeypatch: pytest.MonkeyPatch,
    bindings: tuple[PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding, ...],
    *,
    classification: Namespace = Namespace.VALID,
) -> audit.DisposableHistoricalSettlementAuditDependencies:
    c1 = object()
    token = object()
    account = object.__new__(PersonalDesktopPaperAccountReadEvidence)
    monkeypatch.setattr(audit, "require_trading_token", lambda _sid, _token: None)
    inventory = CompleteDecisionNamespaceResult(
        classification,
        tuple(
            FinalizedDecisionIdentity(
                item.decision.intended_execution_session, item.decision.decision_id
            )
            for item in bindings
        )
        if classification is Namespace.VALID
        else (),
    )

    def discover(value):
        assert value is c1
        return inventory

    def require_discovery(result, value):
        assert result is inventory and value is c1
        return bindings

    def read_account(value, configs):
        assert value is c1 and configs == (b"config",)
        return account

    return audit.DisposableHistoricalSettlementAuditDependencies(
        gate_state=lambda: (False,) * 8,
        acquire_c1=lambda: c1,
        validate_c1=lambda value: value,
        observe_token=lambda: token,
        now=lambda: datetime(2026, 8, 27, 22, tzinfo=UTC),
        discover=discover,
        require_discovery=require_discovery,
        read_selected=lambda *_: None,
        require_selected=lambda *_: None,
        build_open=lambda *_: None,
        complete_plan=lambda *_: None,
        verify_plan=lambda *_: None,
        historical_configurations=lambda _: (b"config",),
        read_account=read_account,
        require_account=lambda value: value,
        build_material=lambda *_: None,
        read_storage=lambda *_: None,
        require_storage=lambda *_: None,
        inspect_operation=lambda *_: None,
    )


def test_multiple_old_reconciled_decisions_are_benign(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bindings = (_fake_binding(24, 1), _fake_binding(25, 2), _fake_binding(26, 3))
    d = _dependencies(monkeypatch, bindings)
    visited = []
    monkeypatch.setattr(
        audit,
        "_reconcile_one",
        lambda _d, _c1, binding, _account: visited.append(binding.decision.decision_id),
    )
    result = audit.audit_personal_desktop_historical_settlements_for_test(d)
    assert result.classification is Status.RECONCILED_HISTORY
    assert result.reconciled_decision_ids == (UUID(int=1), UUID(int=2))
    assert result.current_decision_id == UUID(int=3)
    assert visited == [UUID(int=1), UUID(int=2)]
    assert result.all_eight_gates_closed and not result.real_effect_performed


def test_one_unresolved_old_decision_stops_at_that_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bindings = (_fake_binding(24, 1), _fake_binding(25, 2))
    d = _dependencies(monkeypatch, bindings)

    def reconcile(_d, _c1, binding, _account):
        if binding.decision.decision_id == UUID(int=2):
            raise ValueError("missing exact receipt")

    monkeypatch.setattr(audit, "_reconcile_one", reconcile)
    result = audit.audit_personal_desktop_historical_settlements_for_test(d)
    assert result.classification is Status.STALE_UNRESOLVED_DECISION
    assert result.reconciled_decision_ids == (UUID(int=1),)
    assert result.unresolved_decision_id == UUID(int=2)


@pytest.mark.parametrize(
    "problem", ["pending", "conflicting", "missing receipt", "invalid lineage"]
)
def test_any_unproven_old_settlement_fails_closed(
    monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    d = _dependencies(monkeypatch, (_fake_binding(24, 1),))

    def fail(*_args):
        raise ValueError(problem)

    monkeypatch.setattr(audit, "_reconcile_one", fail)
    result = audit.audit_personal_desktop_historical_settlements_for_test(d)
    assert result.classification is Status.STALE_UNRESOLVED_DECISION
    assert result.unresolved_decision_id == UUID(int=1)


def test_future_and_blocked_namespace_stop_before_account_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    future = _dependencies(monkeypatch, (_fake_binding(28, 1),))
    assert (
        audit.audit_personal_desktop_historical_settlements_for_test(
            future
        ).classification
        is Status.BLOCKED
    )
    blocked = _dependencies(monkeypatch, (), classification=Namespace.BLOCKED)
    assert (
        audit.audit_personal_desktop_historical_settlements_for_test(
            blocked
        ).classification
        is Status.BLOCKED
    )


def test_duplicate_historical_sessions_or_identifiers_block() -> None:
    item = FinalizedDecisionIdentity(TradingSession(date(2026, 8, 24)), UUID(int=1))
    with pytest.raises(ValueError):
        CompleteDecisionNamespaceResult(Namespace.VALID, (item, item))
    with pytest.raises(ValueError):
        CompleteDecisionNamespaceResult(
            Namespace.VALID,
            (item, FinalizedDecisionIdentity(item.execution_session, UUID(int=2))),
        )


@pytest.mark.parametrize("problem", ["staging", "unknown", "malformed", "duplicate"])
def test_native_safe_complete_namespace_rejects_unsafe_entries(
    monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    directory = _put_final(api, binding)
    if problem == "staging":
        api.put(
            PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
            + "\\"
            + storage.unattended_paper_decision_directory_name(
                binding.decision.decision_id, staging=True
            )
        )
    elif problem == "unknown":
        api.overrides[PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = (
            directory.split("\\")[-1],
            "unknown",
        )
    elif problem == "malformed":
        api.overrides[directory] = (
            storage.unattended_paper_decision_artifact_name(
                binding.decision.decision_id
            ),
            "junk",
        )
    else:
        api.overrides[PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = (
            directory.split("\\")[-1],
            directory.split("\\")[-1],
        )
    with pytest.raises(
        (storage.PersonalDesktopUnattendedDecisionStorageError, AuthorityObjectError)
    ):
        storage._read_complete_fixed_namespace(SID, api=api, calendar=_calendar())
    assert not any(
        call[0] in {"write", "create", "rename", "delete"} for call in api.calls
    )


def _receipt_case():
    predecessor, successor = UUID(int=10), UUID(int=11)
    operation, application = UUID(int=20), UUID(int=21)
    prior = SimpleNamespace(
        edge_count=0,
        checkpoint_ids=(predecessor,),
        terminal_checkpoint_id=predecessor,
    )
    intent = SimpleNamespace(operation_id=operation, prior_lineage_evidence=prior)
    inputs = SimpleNamespace(
        intent=intent,
        application_id=application,
        cycle_configuration_payload=b"config",
        prior_genesis_checkpoint=object(),
        prior_successor_checkpoints=(),
        prior_cycle_reports=(),
        prior_snapshots=(),
        completed_snapshot_payload=b"snapshot",
        calendar=object(),
    )
    successor_evidence = object()
    report_evidence = object()
    receipt = SimpleNamespace(
        status=PaperOperationStatus.COMPLETED,
        receipt_id=operation,
        intent=intent,
        application_id=application,
        prior_lineage_evidence=prior,
        successor_lineage_evidence=SimpleNamespace(
            checkpoint_ids=(predecessor, successor),
            application_ids=(application,),
            terminal_checkpoint_id=successor,
        ),
        successor_checkpoint_artifact=successor_evidence,
        transition_report_artifact=report_evidence,
    )
    account = SimpleNamespace(
        receipts=(receipt,),
        lineage=SimpleNamespace(
            edge_count=1,
            checkpoint_ids=(predecessor, successor),
            application_ids=(application,),
            checkpoint_artifacts=(object(), successor_evidence),
            report_artifacts=(report_evidence,),
        ),
        successors=(SimpleNamespace(artifact_id=successor, payload=b"successor"),),
        reports=(SimpleNamespace(payload=b"report"),),
    )
    return account, inputs, receipt


def test_exact_historical_receipt_and_lineage_reverify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account, inputs, receipt = _receipt_case()
    calls = []
    monkeypatch.setattr(
        audit, "serialize_paper_operation_receipt", lambda item: b"receipt"
    )

    def verify(payload, **kwargs):
        calls.append((payload, kwargs))
        return SimpleNamespace(
            status=PaperOperationReceiptVerificationStatus.PASS,
            diagnostics=(),
            receipt=receipt,
        )

    monkeypatch.setattr(audit, "verify_paper_operation_receipt", verify)
    audit._verify_historical_receipt(account, inputs)
    assert calls[0][0] == b"receipt"
    assert calls[0][1]["successor_checkpoint_payload"] == b"successor"
    assert calls[0][1]["transition_report_payload"] == b"report"


@pytest.mark.parametrize(
    "change", ["no-receipt", "wrong-application", "wrong-successor", "bad-verification"]
)
def test_historical_receipt_failures(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    account, inputs, receipt = _receipt_case()
    monkeypatch.setattr(
        audit, "serialize_paper_operation_receipt", lambda item: b"receipt"
    )
    monkeypatch.setattr(
        audit,
        "verify_paper_operation_receipt",
        lambda *_args, **_kwargs: (
            SimpleNamespace(
                status=PaperOperationReceiptVerificationStatus.FAIL,
                diagnostics=("bad",),
                receipt=receipt,
            )
            if change == "bad-verification"
            else SimpleNamespace(
                status=PaperOperationReceiptVerificationStatus.PASS,
                diagnostics=(),
                receipt=receipt,
            )
        ),
    )
    if change == "no-receipt":
        account.receipts = ()
    elif change == "wrong-application":
        account.lineage.application_ids = (UUID(int=99),)
    elif change == "wrong-successor":
        receipt.successor_lineage_evidence.terminal_checkpoint_id = UUID(int=99)
    with pytest.raises(ValueError):
        audit._verify_historical_receipt(account, inputs)


def test_public_result_is_sanitized_and_source_has_no_effect_imports() -> None:
    names = {field.name for field in fields(audit.HistoricalSettlementAuditResult)}
    assert not names & {
        "c1",
        "authority",
        "binding",
        "plan",
        "receipt",
        "path",
        "handle",
        "capability",
        "credential",
        "artifact_bytes",
    }
    assert not inspect.signature(
        audit.audit_personal_desktop_historical_settlements
    ).parameters
    forbidden = {
        "personal_desktop_single_deferred_settlement_execution",
        "personal_desktop_paper_receipt_recovery_execution",
        "personal_desktop_unattended_decision_publication",
        "personal_desktop_unattended_market_data_capture",
        "personal_desktop_unattended_settlement_execution",
        "execute_personal_desktop_unattended_settlement",
        "recover_personal_desktop_paper_receipt",
        "TaskScheduler",
    }
    for filename in (
        "personal_desktop_unattended_historical_settlement_audit.py",
        "personal_desktop_unattended_one_week_soak_window.py",
        "personal_desktop_unattended_one_week_soak_scheduler_contract.py",
    ):
        source = Path(audit.__file__).with_name(filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [
            name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for name in (
                *(alias.name for alias in node.names),
                *((node.module,) if isinstance(node, ast.ImportFrom) else ()),
            )
            if name is not None
        ]
        assert not any(banned in name for name in imports for banned in forbidden)
        assert not any(
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and any(
                target.id.endswith("EFFECTS_ENABLED")
                for target in (
                    node.targets if isinstance(node, ast.Assign) else (node.target,)
                )
                if isinstance(target, ast.Name)
            )
            for node in ast.walk(tree)
        )


@pytest.mark.parametrize(
    ("classification", "diagnostic", "receipt_path"),
    [
        ("PENDING", "PENDING", None),
        ("CONFLICTING", "LINEAGE_CONFLICT", None),
        ("BLOCKED", "FINALIZED_TRANSITION_WITHOUT_RECEIPT", None),
        ("ALREADY_APPLIED", "ALREADY_APPLIED", None),
    ],
)
def test_only_exact_already_applied_inspection_is_accepted(
    classification: str, diagnostic: str, receipt_path: Path | None
) -> None:
    from trading_bot.cli.paper_operation_inspection import (
        PaperOperationClassification,
        PaperOperationInspectionCode,
        PaperOperationInspectionResult,
    )

    operation, predecessor, application = UUID(int=1), UUID(int=2), UUID(int=3)
    result = PaperOperationInspectionResult(
        PaperOperationClassification(classification),
        operation,
        predecessor,
        application,
        receipt_path,
        (PaperOperationInspectionCode(diagnostic),),
    )
    with pytest.raises(ValueError):
        audit._require_applied_inspection(result, operation, application, predecessor)
    exact = replace(
        result,
        classification=PaperOperationClassification.ALREADY_APPLIED,
        receipt_path=Path("receipt.json"),
        diagnostics=(PaperOperationInspectionCode.ALREADY_APPLIED,),
    )
    audit._require_applied_inspection(exact, operation, application, predecessor)


def test_public_complete_inventory_is_provenanced_and_native_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _decision_binding(monkeypatch)
    api = _empty_api()
    _put_final(api, binding)
    c1 = SimpleNamespace(approved_account_sid=SID)
    monkeypatch.setattr(
        storage, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(storage, "WindowsPaperReadNativeApi", lambda: api)
    monkeypatch.setattr(storage, "WindowsTradingTokenObserver", Observer)
    monkeypatch.setattr(
        storage,
        "_require_decision_c3_matches_current_authority",
        lambda _binding, _c1: None,
    )
    result = storage.read_complete_personal_desktop_unattended_decision_namespace(c1)
    assert result.classification is Namespace.VALID
    assert result.decisions == (
        FinalizedDecisionIdentity(
            binding.decision.intended_execution_session, binding.decision.decision_id
        ),
    )
    assert storage.require_complete_personal_desktop_unattended_decision_namespace(
        result, c1
    ) == (binding,)
    copied = CompleteDecisionNamespaceResult(Namespace.VALID, result.decisions)
    with pytest.raises(storage.PersonalDesktopUnattendedDecisionStorageError):
        storage.require_complete_personal_desktop_unattended_decision_namespace(
            copied, c1
        )
    api.overrides[PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = ("unknown",)
    assert (
        storage.read_complete_personal_desktop_unattended_decision_namespace(
            c1
        ).classification
        is Namespace.BLOCKED
    )
    assert not any(
        call[0] in {"write", "create", "rename", "delete"} for call in api.calls
    )


def test_historical_per_decision_reconstruction_accepts_exact_completed_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.runtime import (
        test_personal_desktop_unattended_settlement_reconciliation as base,
    )

    from trading_bot.cli.paper_operation_inspection import (
        PaperOperationClassification,
    )

    harness = base.Harness(monkeypatch)
    harness.operation = PaperOperationClassification.ALREADY_APPLIED
    expected = harness.expected
    predecessor = expected.binding.decision.predecessor_checkpoint_id
    successor = harness.successor
    application = harness.application_id
    successor_evidence, report_evidence = object(), object()
    prior = SimpleNamespace(
        edge_count=0,
        checkpoint_ids=(predecessor,),
        terminal_checkpoint_id=predecessor,
    )
    intent = SimpleNamespace(
        operation_id=harness.operation_id,
        prior_lineage_evidence=prior,
    )
    inputs = SimpleNamespace(
        intent=intent,
        application_id=application,
        cycle_configuration_payload=b"config",
        prior_genesis_checkpoint=object(),
        prior_successor_checkpoints=(),
        prior_cycle_reports=(),
        prior_snapshots=(),
        completed_snapshot_payload=b"snapshot",
        calendar=object(),
    )
    receipt = SimpleNamespace(
        status=PaperOperationStatus.COMPLETED,
        receipt_id=harness.operation_id,
        intent=intent,
        application_id=application,
        prior_lineage_evidence=prior,
        successor_lineage_evidence=SimpleNamespace(
            checkpoint_ids=(predecessor, successor),
            application_ids=(application,),
            terminal_checkpoint_id=successor,
        ),
        successor_checkpoint_artifact=successor_evidence,
        transition_report_artifact=report_evidence,
    )
    account = harness.account
    account.lineage.edge_count = 1
    account.lineage.checkpoint_ids = (predecessor, successor)
    account.lineage.application_ids = (application,)
    account.lineage.checkpoint_artifacts = (object(), successor_evidence)
    account.lineage.report_artifacts = (report_evidence,)
    account.successors = (SimpleNamespace(artifact_id=successor, payload=b"successor"),)
    account.reports = (SimpleNamespace(payload=b"report"),)
    account.receipts = (receipt,)
    old = harness.dependencies()
    values = {
        field.name: getattr(old, field.name)
        for field in fields(audit.DisposableHistoricalSettlementAuditDependencies)
        if hasattr(old, field.name)
    }
    values["build_material"] = lambda _account, _original, plan, _calendar: (
        audit.preparation.PreparedPaperOperationMaterial(plan, inputs)
    )
    values["discover"] = lambda _: None
    values["require_discovery"] = lambda *_: ()
    d = audit.DisposableHistoricalSettlementAuditDependencies(**values)
    monkeypatch.setattr(
        audit, "serialize_paper_operation_receipt", lambda _: b"receipt"
    )
    monkeypatch.setattr(
        audit,
        "verify_paper_operation_receipt",
        lambda *_args, **_kwargs: SimpleNamespace(
            status=PaperOperationReceiptVerificationStatus.PASS,
            diagnostics=(),
            receipt=receipt,
        ),
    )
    audit._reconcile_one(d, harness.authority, expected.binding, account)


def _complete_namespace_fixture(monkeypatch, bindings):
    api = _empty_api()
    payload_bindings = {}
    names = []
    for binding in bindings:
        decision_id = binding.decision.decision_id
        name = storage.unattended_paper_decision_directory_name(decision_id)
        directory = PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS + "\\" + name
        payload = decision_id.bytes
        api.put(directory)
        api.put(
            directory
            + "\\"
            + storage.unattended_paper_decision_artifact_name(decision_id),
            payload,
        )
        payload_bindings[payload] = binding
        names.append(name)
    c1 = SimpleNamespace(approved_account_sid=SID)
    monkeypatch.setattr(
        storage, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(storage, "WindowsPaperReadNativeApi", lambda: api)
    monkeypatch.setattr(storage, "WindowsTradingTokenObserver", Observer)
    monkeypatch.setattr(
        storage,
        "verify_personal_desktop_unattended_paper_decision_intent",
        lambda payload, _calendar: payload_bindings[payload],
    )
    monkeypatch.setattr(
        storage,
        "_require_decision_c3_matches_current_authority",
        lambda _binding, _c1: None,
    )
    return api, c1, tuple(names)


def test_complete_namespace_canonicalizes_opposite_native_enumeration_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _fake_binding(24, 9)
    new = _fake_binding(25, 1)
    api, c1, names = _complete_namespace_fixture(monkeypatch, (new, old))
    api.overrides[PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = names
    first = storage.read_complete_personal_desktop_unattended_decision_namespace(c1)
    api.overrides[PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = names[::-1]
    second = storage.read_complete_personal_desktop_unattended_decision_namespace(c1)
    expected = (
        FinalizedDecisionIdentity(old.decision.intended_execution_session, UUID(int=9)),
        FinalizedDecisionIdentity(new.decision.intended_execution_session, UUID(int=1)),
    )
    assert first.classification is second.classification is Namespace.VALID
    assert first.decisions == second.decisions == expected
    for result in (first, second):
        assert storage.require_complete_personal_desktop_unattended_decision_namespace(
            result, c1
        ) == (old, new)
    assert not any(
        call[0] in {"write", "create", "rename", "delete"} for call in api.calls
    )


def test_historical_audit_reread_ignores_native_enumeration_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _fake_binding(24, 9)
    middle = _fake_binding(25, 1)
    current = _fake_binding(26, 5)
    bindings = (current, middle, old)
    api, c1, names = _complete_namespace_fixture(monkeypatch, bindings)
    original = _dependencies(monkeypatch, bindings)
    account = original.read_account(original.acquire_c1(), (b"config",))
    reads = []

    def discover(value):
        assert value is c1
        api.overrides[PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = (
            names if not reads else names[::-1]
        )
        reads.append(1)
        return storage.read_complete_personal_desktop_unattended_decision_namespace(c1)

    d = replace(
        original,
        acquire_c1=lambda: c1,
        discover=discover,
        require_discovery=storage.require_complete_personal_desktop_unattended_decision_namespace,
        read_account=lambda *_: account,
    )
    visited = []
    monkeypatch.setattr(
        audit,
        "_reconcile_one",
        lambda _d, _c1, binding, _account: visited.append(binding.decision.decision_id),
    )
    result = audit.audit_personal_desktop_historical_settlements_for_test(d)
    assert reads == [1, 1]
    assert result.classification is Status.RECONCILED_HISTORY
    assert result.reconciled_decision_ids == (UUID(int=9), UUID(int=1))
    assert result.current_decision_id == UUID(int=5)
    assert visited == [UUID(int=9), UUID(int=1)]
    assert result.all_eight_gates_closed and not result.real_effect_performed


@pytest.mark.parametrize("duplicate", ["session", "identity"])
def test_complete_namespace_duplicate_session_or_identity_blocks(
    monkeypatch: pytest.MonkeyPatch, duplicate: str
) -> None:
    first = _fake_binding(24, 1)
    bindings = (first, _fake_binding(24, 2)) if duplicate == "session" else (first,)
    api, c1, names = _complete_namespace_fixture(monkeypatch, bindings)
    if duplicate == "identity":
        api.overrides[PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS] = names * 2
    result = storage.read_complete_personal_desktop_unattended_decision_namespace(c1)
    assert result.classification is Namespace.BLOCKED
    assert result.decisions == ()
    with pytest.raises(storage.PersonalDesktopUnattendedDecisionStorageError):
        storage.require_complete_personal_desktop_unattended_decision_namespace(
            result, c1
        )
