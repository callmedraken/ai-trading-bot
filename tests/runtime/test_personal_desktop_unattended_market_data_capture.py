from __future__ import annotations

import hashlib
import inspect
import sqlite3
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from types import ModuleType
from uuid import UUID, uuid5

import pytest

from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import (
    personal_desktop_unattended_market_data_capture as capture_module,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    next_xnys_execution_session,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED,
    PersonalDesktopUnattendedMarketDataCaptureClassification,
    PersonalDesktopUnattendedSelectedC3Evidence,
    inspect_personal_desktop_unattended_c3_preflight_for_test,
    run_personal_desktop_unattended_market_data_capture,
    run_personal_desktop_unattended_market_data_capture_for_test,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
)
from trading_bot.runtime.windows_effectful_capture import (
    ProductionCapturePlan,
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_effectful_capture_service import (
    ProductionCaptureInvocationResult,
    WindowsEffectfulDailySnapshotCapture,
)

_NAMESPACE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_EPOCH = "11111111-1111-4111-8111-111111111111"
_OBSERVED = datetime(2026, 8, 18, 14, tzinfo=UTC)
_SESSION = TradingSession(date(2026, 8, 17))


def _uuid(label: str) -> str:
    return str(uuid5(_NAMESPACE, label))


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE sessions (
            session_id TEXT,
            authority_epoch_id TEXT,
            state TEXT,
            request_json BLOB,
            request_digest BLOB,
            created_at_utc TEXT
        );
        CREATE TABLE attempts (attempt_id TEXT, session_id TEXT);
        CREATE TABLE provider_call_claims (claim_id TEXT, attempt_id TEXT);
        CREATE TABLE launch_reservations (
            launch_reservation_id TEXT,
            claim_id TEXT
        );
        CREATE TABLE terminals (
            terminal_id TEXT,
            launch_reservation_id TEXT
        );
        CREATE TABLE session_selections (selection_id TEXT, session_id TEXT);
        """
    )
    return connection


def _insert_session(
    connection: sqlite3.Connection,
    session: TradingSession,
    *,
    state: str = "OPEN",
    suffix: str = "",
) -> str:
    request = personal_desktop_unattended_capture_request(session)
    payload = request.canonical_c2_request_json()
    session_id = _uuid(f"session:{session.session_date}:{suffix}")
    connection.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            _EPOCH,
            state,
            payload,
            hashlib.sha256(payload).digest(),
            f"2026-08-18T12:00:0{len(suffix)}Z",
        ),
    )
    connection.commit()
    return session_id


def _select(
    connection: sqlite3.Connection,
    session: TradingSession,
    *,
    suffix: str = "",
) -> tuple[str, str]:
    session_id = _insert_session(
        connection,
        session,
        state="SUCCESS_SELECTED",
        suffix=suffix,
    )
    selection_id = _uuid(f"selection:{session.session_date}:{suffix}")
    connection.execute(
        "INSERT INTO session_selections VALUES (?, ?)",
        (selection_id, session_id),
    )
    attempt_id = _uuid(f"selected-attempt:{session.session_date}:{suffix}")
    claim_id = _uuid(f"selected-claim:{session.session_date}:{suffix}")
    reservation_id = _uuid(f"selected-reservation:{session.session_date}:{suffix}")
    connection.execute(
        "INSERT INTO attempts VALUES (?, ?)",
        (attempt_id, session_id),
    )
    connection.execute(
        "INSERT INTO provider_call_claims VALUES (?, ?)",
        (claim_id, attempt_id),
    )
    connection.execute(
        "INSERT INTO launch_reservations VALUES (?, ?)",
        (reservation_id, claim_id),
    )
    connection.execute(
        "INSERT INTO terminals VALUES (?, ?)",
        (_uuid(f"selected-terminal:{session.session_date}:{suffix}"), reservation_id),
    )
    connection.commit()
    return session_id, selection_id


def _classification(
    connection: sqlite3.Connection,
    session: TradingSession = _SESSION,
) -> str:
    return inspect_personal_desktop_unattended_c3_preflight_for_test(
        connection,
        _EPOCH,
        session,
    ).classification.value


def _authority() -> ValidatedProductionAuthority:
    return object.__new__(ValidatedProductionAuthority)


class _Preflight:
    def __init__(
        self,
        classification: PersonalDesktopUnattendedMarketDataCaptureClassification,
        *,
        session_id: str | None = None,
        selection_id: str | None = None,
    ) -> None:
        self.classification = classification
        self.session_id = session_id
        self.selection_id = selection_id
        self.calls = 0

    def inspect(self, session: TradingSession) -> object:
        assert session == _SESSION
        self.calls += 1
        return capture_module.PersonalDesktopUnattendedC3PreflightReadResult(
            self.classification,
            self.session_id,
            self.selection_id,
        )


class _UnusedSelectedReader:
    def read_selected_snapshot_for_session(self, session: TradingSession) -> object:
        del session
        raise AssertionError("selected C3 read must not run")


def _invocation() -> ProductionCaptureInvocationResult:
    return ProductionCaptureInvocationResult(
        session_id=_uuid("invocation-session"),
        attempt_id=_uuid("invocation-attempt"),
        claim_id=_uuid("invocation-claim"),
        reservation_id=_uuid("invocation-reservation"),
        execution_id=None,
        terminal_id=_uuid("invocation-terminal"),
        selection_id=None,
        terminal_state="FAILED",
        provider_call_disposition="NOT_STARTED",
    )


def _run(
    preflight: _Preflight,
    capture_factory: object,
) -> object:
    return run_personal_desktop_unattended_market_data_capture_for_test(
        _authority(),
        _OBSERVED,
        preflight=preflight,
        selected_reader=_UnusedSelectedReader(),
        capture_factory=capture_factory,  # type: ignore[arg-type]
    )


def _effect_modules() -> tuple[tuple[ModuleType, str], ...]:
    names = (
        (
            "trading_bot.runtime.personal_desktop_unattended_paper_decision_publication",
            "PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED",
        ),
        (
            "trading_bot.runtime.personal_desktop_paper_account_security",
            "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED",
        ),
        (
            "trading_bot.runtime.personal_desktop_paper_account_security",
            "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED",
        ),
        (
            "trading_bot.runtime.personal_desktop_supervised_paper_operation_execution",
            "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
        ),
        (
            "trading_bot.runtime.personal_desktop_paper_receipt_recovery_execution",
            "PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED",
        ),
        (
            "trading_bot.runtime.personal_desktop_unattended_paper_operation_execution",
            "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED",
        ),
        (
            "trading_bot.runtime.personal_desktop_unattended_paper_storage_provisioning",
            "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED",
        ),
    )
    return tuple(
        (__import__(module, fromlist=[field]), field) for module, field in names
    )


def test_production_api_accepts_no_semantic_arguments() -> None:
    assert (
        tuple(
            inspect.signature(
                run_personal_desktop_unattended_market_data_capture
            ).parameters
        )
        == ()
    )


def test_source_owned_request_is_stable_spy_and_next_session() -> None:
    first = personal_desktop_unattended_capture_request(_SESSION)
    second = personal_desktop_unattended_capture_request(_SESSION)

    assert first.ordered_universe == (PERSONAL_DESKTOP_UNATTENDED_SYMBOL,)
    assert (
        first.target_session_date == next_xnys_execution_session(_SESSION).session_date
    )
    assert first.canonical_c2_request_json() == second.canonical_c2_request_json()


def test_cold_start_requires_one_capture_without_mutation() -> None:
    connection = _database()
    before = connection.total_changes

    assert _classification(connection) == "CAPTURE_REQUIRED"
    assert connection.total_changes == before
    assert connection.execute("PRAGMA query_only").fetchone() == (0,)


def test_exact_selected_session_converges_read_only() -> None:
    connection = _database()
    _select(connection, _SESSION)
    before = connection.total_changes

    assert _classification(connection) == "NO_NEW_COMPLETED_SESSION"
    assert connection.total_changes == before


def test_multiple_or_conflicting_selected_lineage_fails_closed() -> None:
    connection = _database()
    session_id, _selection_id = _select(connection, _SESSION)
    connection.execute(
        "INSERT INTO session_selections VALUES (?, ?)",
        (_uuid("conflicting-selection"), session_id),
    )
    connection.commit()

    with pytest.raises(capture_module.PersonalDesktopUnattendedMarketDataCaptureError):
        _classification(connection)


def test_prior_claim_or_terminal_state_never_retries_blindly() -> None:
    connection = _database()
    session_id = _insert_session(connection, _SESSION)
    attempt_id = _uuid("attempt")
    claim_id = _uuid("claim")
    reservation_id = _uuid("reservation")
    connection.execute("INSERT INTO attempts VALUES (?, ?)", (attempt_id, session_id))
    connection.execute(
        "INSERT INTO provider_call_claims VALUES (?, ?)",
        (claim_id, attempt_id),
    )
    connection.execute(
        "INSERT INTO launch_reservations VALUES (?, ?)",
        (reservation_id, claim_id),
    )
    connection.execute(
        "INSERT INTO terminals VALUES (?, ?)",
        (_uuid("ambiguous-terminal"), reservation_id),
    )
    connection.commit()

    assert _classification(connection) == "PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS"


def test_session_gap_and_stale_clock_stop_without_backfill() -> None:
    gap = _database()
    _select(gap, TradingSession(date(2026, 8, 13)))
    assert _classification(gap) == "SESSION_GAP"

    stale = _database()
    _select(stale, TradingSession(date(2026, 8, 18)))
    assert _classification(stale) == "SESSION_GAP"


def test_g5_retains_backward_selected_session_nomination_protection() -> None:
    connection = _database()
    _select(connection, TradingSession(date(2026, 8, 18)))
    before = connection.total_changes

    result = inspect_personal_desktop_unattended_c3_preflight_for_test(
        connection,
        _EPOCH,
        TradingSession(date(2026, 8, 17)),
    )

    assert result.classification is (
        PersonalDesktopUnattendedMarketDataCaptureClassification.SESSION_GAP
    )
    assert connection.total_changes == before


def test_closed_gate_performs_no_effectful_root_construction() -> None:
    assert PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED is False
    constructed: list[object] = []

    def forbidden_factory(authority: object) -> object:
        constructed.append(authority)
        raise AssertionError("credential/process/provider/output root constructed")

    result = _run(
        _Preflight(
            PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
        ),
        forbidden_factory,
    )

    assert result.classification.value == "CAPTURE_REQUIRED"
    assert result.invocation is None
    assert constructed == []


@pytest.mark.parametrize("gate_index", range(7))
def test_any_wrong_companion_gate_blocks_before_c3_root(
    monkeypatch: pytest.MonkeyPatch,
    gate_index: int,
) -> None:
    monkeypatch.setattr(
        capture_module,
        "PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED",
        True,
    )
    module, field = _effect_modules()[gate_index]
    monkeypatch.setattr(module, field, True)

    result = _run(
        _Preflight(
            PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
        ),
        lambda _authority: pytest.fail("effectful C3 root was constructed"),
    )

    assert result.classification.value == "BLOCKED"


def test_gate_open_enters_existing_prepared_c3_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        capture_module,
        "PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED",
        True,
    )
    capture = object.__new__(WindowsEffectfulDailySnapshotCapture)
    capture._closed = False
    capture._adapter = object()
    capture._transactional = object()
    calls: list[ProductionCapturePlan] = []
    closed: list[bool] = []

    def invoke(
        self: WindowsEffectfulDailySnapshotCapture,
        plan: ProductionCapturePlan,
    ) -> ProductionCaptureInvocationResult:
        assert self is capture
        calls.append(plan)
        return _invocation()

    monkeypatch.setattr(
        WindowsEffectfulDailySnapshotCapture,
        "_capture_prepared_once",
        invoke,
    )
    monkeypatch.setattr(
        WindowsEffectfulDailySnapshotCapture,
        "close",
        lambda self: closed.append(self is capture),
    )

    result = _run(
        _Preflight(
            PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
        ),
        lambda authority: capture,
    )

    assert len(calls) == 1
    assert calls[0] == prepare_production_capture_plan(
        personal_desktop_unattended_capture_request(_SESSION),
        _OBSERVED,
    )
    assert closed == [True]
    assert result.invocation == _invocation()


def test_duplicate_wakes_do_not_reuse_effect_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        capture_module,
        "PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED",
        True,
    )
    provider_calls: list[ProductionCapturePlan] = []

    class Root:
        def capture_prepared_once(
            self, plan: ProductionCapturePlan
        ) -> ProductionCaptureInvocationResult:
            provider_calls.append(plan)
            return _invocation()

        def close(self) -> None:
            return None

    first = _run(
        _Preflight(
            PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
        ),
        lambda _authority: Root(),
    )
    assert first.invocation is not None

    session_id = _uuid("selected-session")
    selection_id = _uuid("selected-selection")
    selected_evidence = PersonalDesktopUnattendedSelectedC3Evidence(
        selection_id=UUID(selection_id),
        session_id=UUID(session_id),
        attempt_id=UUID(_uuid("selected-attempt")),
        terminal_id=UUID(_uuid("selected-terminal")),
        snapshot_id=UUID(_uuid("selected-snapshot")),
        artifact_sha256="a" * 64,
        artifact_byte_length=1,
    )
    monkeypatch.setattr(
        capture_module, "_selected_evidence", lambda _value: selected_evidence
    )

    class Reader:
        def read_selected_snapshot_for_session(self, session: TradingSession) -> object:
            assert session == _SESSION
            return object()

    second = run_personal_desktop_unattended_market_data_capture_for_test(
        _authority(),
        _OBSERVED,
        preflight=_Preflight(
            PersonalDesktopUnattendedMarketDataCaptureClassification.NO_NEW_COMPLETED_SESSION,
            session_id=session_id,
            selection_id=selection_id,
        ),
        selected_reader=Reader(),  # type: ignore[arg-type]
        capture_factory=lambda _authority: pytest.fail("duplicate effect root"),
    )

    assert second.classification.value == "NO_NEW_COMPLETED_SESSION"
    assert second.invocation is None
    assert len(provider_calls) == 1
    with pytest.raises(FrozenInstanceError):
        second.classification = (  # type: ignore[misc]
            PersonalDesktopUnattendedMarketDataCaptureClassification.CAPTURE_REQUIRED
        )
    assert not hasattr(second, "permit")
    assert not hasattr(second.selected_c3, "permit")


def test_all_eight_effect_gates_are_committed_false() -> None:
    assert PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED is False
    assert all(getattr(module, field) is False for module, field in _effect_modules())
