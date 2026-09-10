"""PD3-B read-only qualification of installed Paper-v2 receipt state."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.runtime import personal_desktop_paper_account_mutex as mutex
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_qualification as qualification,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as execution_boundary,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)

from .test_personal_desktop_paper_account_read_authority import (
    MACHINE,
    Observer,
    memory_case,
    read_case,
)
from .test_personal_desktop_paper_account_security import (
    OPERATIONS,
    RUNTIME,
    SID,
)
from .test_personal_desktop_paper_account_security import (
    block_real_native as block_real_native,
)
from .test_personal_desktop_paper_account_security import (
    prohibit_production_effects as prohibit_production_effects,
)
from .test_verified_snapshot_preparation import calendar


def qualify(case, *, observer=None, configurations=None):
    return qualification._qualify_personal_desktop_paper_receipt_recovery_for_test(
        MACHINE,
        SID,
        api=case.api,
        observer=observer or Observer(),
        calendar=calendar(),
        configurations=(
            case.configurations if configurations is None else configurations
        ),
    )


def remove_receipt(case, index):
    receipt = case.receipts[index]
    directory = OPERATIONS + f"\\paper-operation-{receipt.receipt_id}"
    for path in tuple(case.api.nodes):
        if path == directory or path.startswith(directory + "\\"):
            del case.api.nodes[path]


def test_healthy_fully_verified_account_needs_no_recovery():
    case = memory_case(2, no_action=True)
    result = qualify(case)
    assert result.status is (
        qualification.PaperReceiptRecoveryQualificationStatus.NO_RECOVERY_REQUIRED
    )
    assert result.paper_account_id == case.anchor.paper_account_id
    assert result.terminal_checkpoint_id == case.successors[-1].artifact_id
    assert result.missing_application_id is None
    assert result.predecessor_checkpoint_id is None
    assert not case.api.handles


def test_terminal_missing_receipt_is_required_but_test_evidence_is_unregistered():
    case = memory_case(2, no_action=True)
    remove_receipt(case, 1)
    result = qualify(case, configurations=(case.configurations[0],))
    terminal = case.receipts[1]
    assert result.status is (
        qualification.PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
    )
    assert result.missing_application_id == terminal.application_id
    assert result.terminal_checkpoint_id == case.successors[-1].artifact_id
    assert result.predecessor_checkpoint_id == case.successors[0].artifact_id
    with pytest.raises(PersonalDesktopPaperAccountError, match="production"):
        qualification.require_validated_paper_receipt_recovery_qualification(result)
    with pytest.raises(PersonalDesktopPaperAccountError, match="production"):
        mutex.paper_receipt_recovery_admission(result)


def test_ordinary_reader_still_rejects_same_terminal_missing_receipt_state():
    case = memory_case(1)
    remove_receipt(case, 0)
    result = qualify(case, configurations=())
    assert result.status is (
        qualification.PaperReceiptRecoveryQualificationStatus.RECEIPT_RECOVERY_REQUIRED
    )
    with pytest.raises(PersonalDesktopPaperAccountError, match="no verified receipt"):
        read_case(case, configurations=())


def test_missing_receipt_on_nonterminal_transition_is_blocked():
    case = memory_case(2, no_action=True)
    remove_receipt(case, 0)
    result = qualify(case, configurations=(case.configurations[1],))
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )


def test_multiple_missing_receipts_are_blocked():
    case = memory_case(2, no_action=True)
    remove_receipt(case, 0)
    remove_receipt(case, 1)
    result = qualify(case, configurations=())
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )


@pytest.mark.parametrize("kind", ["transition", "receipt"])
def test_any_transition_or_receipt_staging_is_blocked(kind):
    case = memory_case(1)
    identity = UUID(int=999)
    if kind == "transition":
        current = case.api.names(None, RUNTIME, 1024)
        case.api.overrides[RUNTIME] = (
            *current,
            f".paper-account-transition-{identity}.staging",
        )
    else:
        current = case.api.names(None, OPERATIONS, 1024)
        case.api.overrides[OPERATIONS] = (
            *current,
            f".paper-operation-{identity}.staging",
        )
    result = qualify(case)
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )


def test_invalid_receipt_is_blocked():
    case = memory_case(1)
    receipt_id = case.receipts[0].receipt_id
    path = (
        OPERATIONS
        + f"\\paper-operation-{receipt_id}"
        + f"\\paper-operation-receipt-{receipt_id}.json"
    )
    case.api.put(path, case.api.nodes[path].payload + b" ")
    result = qualify(case)
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )


@pytest.mark.parametrize("kind", ["invalid-transition", "lineage-conflict"])
def test_invalid_or_conflicting_lineage_is_blocked(kind):
    case = memory_case(1)
    if kind == "invalid-transition":
        report_path = next(
            path
            for path in case.api.nodes
            if path.startswith(RUNTIME + "\\paper-account-transition-")
            and "\\checkpointed-paper-cycle-report-" in path
        )
        case.api.put(report_path, case.api.nodes[report_path].payload + b" ")
        configurations = case.configurations
    else:
        conflicting = memory_case(1, no_action=True)
        for path, node in conflicting.api.nodes.items():
            if path.startswith(RUNTIME + "\\") and path not in case.api.nodes:
                case.api.put(path, node.payload)
        configurations = case.configurations + conflicting.configurations
    result = qualify(case, configurations=configurations)
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )


def test_missing_configuration_for_present_receipt_is_blocked():
    case = memory_case(1)
    result = qualify(case, configurations=())
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )


@pytest.mark.parametrize("change", ["mismatch", "drift"])
def test_trading_token_mismatch_or_drift_is_blocked(change):
    case = memory_case(1)
    observer = Observer(elevated=change == "mismatch")
    if change == "drift":

        def drift(path, count, node):
            del node
            if path == security.PERSONAL_DESKTOP_PAPER_V2_ANCHOR and count == 2:
                observer.observation = replace(observer.observation, elevated=True)

        case.api.on_inspect = drift
    result = qualify(case, observer=observer)
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )
    assert result.paper_account_id is None
    assert not case.api.handles


def test_invalid_c1_blocks_before_native_construction(monkeypatch):
    called = False

    def forbidden():
        nonlocal called
        called = True
        pytest.fail("invalid C1 reached the native read boundary")

    monkeypatch.setattr(qualification, "WindowsTradingTokenObserver", forbidden)
    result = qualification.qualify_personal_desktop_paper_receipt_recovery(object())
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )
    assert called is False


def test_c1_provenance_drift_after_read_blocks_and_never_registers(monkeypatch):
    case = memory_case(1)
    c1 = SimpleNamespace(machine_authority_id=MACHINE, approved_account_sid=SID)
    calls = 0

    def require(value):
        nonlocal calls
        calls += 1
        if calls == 1 and value is c1:
            return c1
        raise PersonalDesktopPaperAccountError("C1 provenance drift")

    monkeypatch.setattr(
        qualification, "require_validated_production_authority", require
    )
    monkeypatch.setattr(qualification, "WindowsTradingTokenObserver", Observer)
    monkeypatch.setattr(qualification, "WindowsPaperReadNativeApi", lambda: case.api)
    monkeypatch.setattr(qualification, "BoundMarketCalendar", lambda *args: calendar())
    result = qualification.qualify_personal_desktop_paper_receipt_recovery(
        c1, historical_cycle_configuration_payloads=case.configurations
    )
    assert calls == 2
    assert (
        result.status is qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )
    with pytest.raises(PersonalDesktopPaperAccountError):
        qualification.require_validated_paper_receipt_recovery_qualification(result)


@pytest.mark.parametrize("missing_terminal", [False, True])
def test_qualification_is_read_only_and_has_no_a67_execution_or_recovery_path(
    missing_terminal,
):
    case = memory_case(1)
    configurations = case.configurations
    if missing_terminal:
        remove_receipt(case, 0)
        configurations = ()
    result = qualify(case, configurations=configurations)
    assert (
        result.status
        is not qualification.PaperReceiptRecoveryQualificationStatus.BLOCKED
    )
    assert {call[0] for call in case.api.calls} <= {
        "fixed_staging_present",
        "open",
        "close",
        "read",
        "names",
    }
    assert not hasattr(qualification, "recover_paper_operation_receipt_once")
    assert not hasattr(qualification, "execute_paper_operation_once")
    assert not hasattr(qualification, "inspect_paper_operation_root")


def test_existing_effect_gates_remain_closed_and_no_new_gate_is_added():
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        execution_boundary.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert not hasattr(
        qualification, "PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED"
    )
