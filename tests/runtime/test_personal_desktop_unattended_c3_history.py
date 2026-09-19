from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import pytest

import trading_bot.runtime.personal_desktop_unattended_c3_history as history_module
from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailyBarCandidate,
    DailyProviderResponse,
    DailySnapshotCaptureRequest,
    SourcePayloadEvidence,
    accept_daily_provider_response,
    build_daily_provider_request,
    replay_verified_daily_snapshot,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotAuditEvidence,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadError,
    SelectedC3SnapshotReadResult,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    PERSONAL_DESKTOP_UNATTENDED_HISTORY_SOURCE_ID,
    PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
    PersonalDesktopUnattendedC3HistoryError,
    SelectedC3StrategyHistoryBinding,
    SelectedC3StrategyHistoryWindowClassification,
    SessionIndexedSelectedC3SnapshotReadResult,
    build_selected_c3_strategy_history_binding,
    inspect_selected_c3_strategy_history_window_for_test,
    personal_desktop_unattended_capture_request,
)
from trading_bot.runtime.strategy_history_seed import (
    StrategyHistorySeedSourceDescriptor,
    create_strategy_history_seed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_NAMESPACE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_NEW_YORK = ZoneInfo("America/New_York")
_EPOCH = "11111111-1111-4111-8111-111111111111"
_CONFIG = MovingAverageCrossoverConfig(3, 5, Decimal("1"))


def _selected_result(
    session: TradingSession,
    *,
    symbol: Symbol = PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
    price: Decimal = Decimal("100"),
) -> SelectedC3SnapshotReadResult:
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    next_session = NYSEMarketCalendar().next_session(
        datetime.combine(session.session_date, time(12), tzinfo=_NEW_YORK)
    )
    requested_at = datetime.combine(
        next_session.session_date,
        time(12),
        tzinfo=_NEW_YORK,
    ).astimezone(UTC)
    request = DailySnapshotCaptureRequest(
        request_id=uuid5(_NAMESPACE, f"request:{session.session_date}:{symbol}"),
        symbols=(symbol,),
        requested_at=requested_at,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
    )
    provider_request = build_daily_provider_request(
        request,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        calendar,
    )
    assert provider_request.target_session == session
    source = f"fixture:{session.session_date}:{symbol}".encode()
    response = DailyProviderResponse(
        request=provider_request,
        candidates=(
            DailyBarCandidate(
                response_ordinal=0,
                symbol=symbol,
                session=session,
                timestamp=datetime.combine(
                    session.session_date,
                    time(20),
                    tzinfo=UTC,
                ),
                open=price,
                high=price + Decimal("2"),
                low=price - Decimal("1"),
                close=price + Decimal("1"),
                volume=1000,
            ),
        ),
        captured_at=requested_at + timedelta(seconds=1),
        provider_as_of=requested_at,
        provider_request_id=f"fixture-{session.session_date}",
        source_payload=SourcePayloadEvidence(
            sha256=hashlib.sha256(source).hexdigest(),
            byte_length=len(source),
            media_type="application/json",
        ),
        pagination_complete=True,
    )
    accepted = accept_daily_provider_response(provider_request, response, calendar)
    assert accepted.snapshot is not None
    payload = serialize_daily_snapshot(accepted.snapshot)
    verification = verify_daily_snapshot(payload, calendar)
    assert verification.passed
    assert verification.snapshot is not None
    audit = SelectedC3SnapshotAuditEvidence(
        selection_id=uuid5(_NAMESPACE, f"selection:{session.session_date}:{symbol}"),
        session_id=uuid5(_NAMESPACE, f"session:{session.session_date}:{symbol}"),
        attempt_id=uuid5(_NAMESPACE, f"attempt:{session.session_date}:{symbol}"),
        terminal_id=uuid5(_NAMESPACE, f"terminal:{session.session_date}:{symbol}"),
        snapshot_id=verification.snapshot.snapshot_id,
        artifact_sha256=hashlib.sha256(payload).hexdigest(),
        artifact_byte_length=len(payload),
        artifact_identity_sha256="1" * 64,
        terminal_state="SUCCEEDED",
        provider_call_disposition="CONFIRMED",
        canonical_artifact_path=f"fixture/{verification.snapshot.snapshot_id}.json",
    )
    permit = object.__new__(SelectedC3SnapshotPermit)
    return SelectedC3SnapshotReadResult(audit, permit, payload, verification)


def _session_read(
    session_date: date,
    *,
    symbol: Symbol = PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
    price: Decimal = Decimal("100"),
) -> SessionIndexedSelectedC3SnapshotReadResult:
    session = TradingSession(session_date)
    request = personal_desktop_unattended_capture_request(session)
    return SessionIndexedSelectedC3SnapshotReadResult(
        session,
        request,
        request.canonical_c2_request_json(),
        _selected_result(session, symbol=symbol, price=price),
    )


def _valid_chain() -> tuple[
    tuple[SessionIndexedSelectedC3SnapshotReadResult, ...],
    SessionIndexedSelectedC3SnapshotReadResult,
]:
    history_dates = (
        date(2026, 8, 17),
        date(2026, 8, 18),
        date(2026, 8, 19),
        date(2026, 8, 20),
        date(2026, 8, 21),
    )
    history = tuple(
        _session_read(value, price=Decimal(100 + index))
        for index, value in enumerate(history_dates)
    )
    current = _session_read(date(2026, 8, 24), price=Decimal("105"))
    return history, current


def _selection_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            authority_epoch_id TEXT NOT NULL,
            state TEXT NOT NULL,
            request_json BLOB NOT NULL,
            request_digest BLOB NOT NULL
        );
        CREATE TABLE session_selections (
            selection_id TEXT NOT NULL,
            session_id TEXT NOT NULL
        );
        """
    )
    return connection


def _insert_selection(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    selection_id: str,
    request_bytes: bytes,
    request_digest: bytes | None = None,
) -> None:
    connection.execute(
        "INSERT INTO sessions VALUES (?, ?, 'SUCCESS_SELECTED', ?, ?)",
        (
            session_id,
            _EPOCH,
            request_bytes,
            request_digest
            if request_digest is not None
            else hashlib.sha256(request_bytes).digest(),
        ),
    )
    connection.execute(
        "INSERT INTO session_selections VALUES (?, ?)",
        (selection_id, session_id),
    )
    connection.commit()


def _inspect_window(
    present: tuple[date, ...],
) -> tuple[object, sqlite3.Connection, list[str]]:
    connection = _selection_database()
    current = _session_read(date(2026, 8, 24), price=Decimal("105"))
    selected_by_id: dict[str, SelectedC3SnapshotReadResult] = {}
    for index, session_date in enumerate(present):
        item = (
            current
            if session_date == current.session.session_date
            else _session_read(session_date, price=Decimal(100 + index))
        )
        selection_id = str(item.selected.audit.selection_id)
        request_bytes = item.capture_request.canonical_c2_request_json()
        _insert_selection(
            connection,
            session_id=str(item.selected.audit.session_id),
            selection_id=selection_id,
            request_bytes=request_bytes,
        )
        selected_by_id[selection_id] = item.selected
    reads: list[str] = []

    def read_selected(selection_id: str) -> SelectedC3SnapshotReadResult:
        reads.append(selection_id)
        return selected_by_id[selection_id]

    result = inspect_selected_c3_strategy_history_window_for_test(
        connection,
        _EPOCH,
        current,
        _CONFIG,
        read_selected,
    )
    return result, connection, reads


def test_source_owned_capture_request_is_exact_spy_single_session() -> None:
    session = TradingSession(date(2026, 8, 21))

    request = personal_desktop_unattended_capture_request(session)

    assert request.ordered_universe == (Symbol("SPY"),)
    assert request.request_window_start_date == session.session_date
    assert request.request_window_end_date == session.session_date
    assert request.target_session_date == date(2026, 8, 24)


def test_exact_request_resolves_one_selection_without_mutation() -> None:
    connection = _selection_database()
    request = personal_desktop_unattended_capture_request(
        TradingSession(date(2026, 8, 21))
    )
    request_bytes = request.canonical_c2_request_json()
    selection_id = "22222222-2222-4222-8222-222222222222"
    _insert_selection(
        connection,
        session_id="33333333-3333-4333-8333-333333333333",
        selection_id=selection_id,
        request_bytes=request_bytes,
    )
    initial_changes = connection.total_changes

    assert (
        history_module._resolve_selection_id_from_connection(
            connection,
            _EPOCH,
            request_bytes,
        )
        == selection_id
    )
    assert connection.total_changes == initial_changes
    assert connection.execute("PRAGMA query_only").fetchone() == (1,)


def test_wrong_request_bytes_do_not_resolve_apparent_same_session() -> None:
    connection = _selection_database()
    expected = personal_desktop_unattended_capture_request(
        TradingSession(date(2026, 8, 21))
    ).canonical_c2_request_json()
    wrong = expected.replace(b'"SPY"', b'"QQQ"')
    _insert_selection(
        connection,
        session_id="33333333-3333-4333-8333-333333333333",
        selection_id="22222222-2222-4222-8222-222222222222",
        request_bytes=wrong,
    )

    with pytest.raises(
        PersonalDesktopUnattendedC3HistoryError,
        match="exactly one selected C3 lineage",
    ):
        history_module._resolve_selection_id_from_connection(
            connection,
            _EPOCH,
            expected,
        )


def test_wrong_request_digest_does_not_resolve() -> None:
    connection = _selection_database()
    request_bytes = personal_desktop_unattended_capture_request(
        TradingSession(date(2026, 8, 21))
    ).canonical_c2_request_json()
    _insert_selection(
        connection,
        session_id="33333333-3333-4333-8333-333333333333",
        selection_id="22222222-2222-4222-8222-222222222222",
        request_bytes=request_bytes,
        request_digest=b"x" * 32,
    )

    with pytest.raises(
        PersonalDesktopUnattendedC3HistoryError,
        match="exactly one selected C3 lineage",
    ):
        history_module._resolve_selection_id_from_connection(
            connection,
            _EPOCH,
            request_bytes,
        )


def test_zero_or_multiple_matching_selections_fail_closed() -> None:
    request_bytes = personal_desktop_unattended_capture_request(
        TradingSession(date(2026, 8, 21))
    ).canonical_c2_request_json()
    empty = _selection_database()
    with pytest.raises(PersonalDesktopUnattendedC3HistoryError):
        history_module._resolve_selection_id_from_connection(
            empty,
            _EPOCH,
            request_bytes,
        )

    duplicate = _selection_database()
    _insert_selection(
        duplicate,
        session_id="33333333-3333-4333-8333-333333333333",
        selection_id="22222222-2222-4222-8222-222222222222",
        request_bytes=request_bytes,
    )
    duplicate.execute("PRAGMA query_only = OFF")
    _insert_selection(
        duplicate,
        session_id="44444444-4444-4444-8444-444444444444",
        selection_id="55555555-5555-4555-8555-555555555555",
        request_bytes=request_bytes,
    )
    with pytest.raises(PersonalDesktopUnattendedC3HistoryError):
        history_module._resolve_selection_id_from_connection(
            duplicate,
            _EPOCH,
            request_bytes,
        )


@pytest.mark.parametrize(
    "present",
    (
        (date(2026, 8, 24),),
        (date(2026, 8, 21), date(2026, 8, 24)),
        (date(2026, 8, 20), date(2026, 8, 21), date(2026, 8, 24)),
    ),
)
def test_contiguous_selected_suffix_is_normal_warming_up(
    present: tuple[date, ...],
) -> None:
    result, connection, reads = _inspect_window(present)

    assert result.classification is (
        SelectedC3StrategyHistoryWindowClassification.WARMING_UP
    )
    assert tuple(item.session.session_date for item in result.selected) == present
    assert len(reads) == len(present) - 1
    assert connection.total_changes == len(present) * 2
    assert connection.execute("PRAGMA query_only").fetchone() == (1,)


def test_exact_five_preceding_sessions_plus_current_is_ready() -> None:
    dates = (
        date(2026, 8, 17),
        date(2026, 8, 18),
        date(2026, 8, 19),
        date(2026, 8, 20),
        date(2026, 8, 21),
        date(2026, 8, 24),
    )

    result, _connection, reads = _inspect_window(dates)

    assert result.classification is SelectedC3StrategyHistoryWindowClassification.READY
    assert tuple(item.session.session_date for item in result.selected) == dates
    assert len(reads) == 5


def test_selected_evidence_on_both_sides_of_missing_required_session_is_gap() -> None:
    present = (
        date(2026, 8, 19),
        date(2026, 8, 21),
        date(2026, 8, 24),
    )

    result, _connection, _reads = _inspect_window(present)

    assert result.classification is (
        SelectedC3StrategyHistoryWindowClassification.SESSION_GAP
    )


def test_disconnected_selected_evidence_before_exact_window_does_not_create_gap() -> (
    None
):
    connection = _selection_database()
    old = _session_read(date(2026, 8, 14))
    current = _session_read(date(2026, 8, 24))
    for item in (old, current):
        _insert_selection(
            connection,
            session_id=str(item.selected.audit.session_id),
            selection_id=str(item.selected.audit.selection_id),
            request_bytes=item.canonical_request_bytes,
        )
    reads: list[str] = []

    result = inspect_selected_c3_strategy_history_window_for_test(
        connection,
        _EPOCH,
        current,
        _CONFIG,
        lambda selection_id: reads.append(selection_id),
    )

    assert result.classification is (
        SelectedC3StrategyHistoryWindowClassification.WARMING_UP
    )
    assert result.selected == (current,)
    assert reads == []


def test_duplicate_or_malformed_selected_lineage_in_required_window_blocks() -> None:
    current = _session_read(date(2026, 8, 24))
    request_bytes = current.canonical_request_bytes
    duplicate = _selection_database()
    for suffix in ("one", "two"):
        _insert_selection(
            duplicate,
            session_id=str(uuid5(_NAMESPACE, f"duplicate-session:{suffix}")),
            selection_id=str(uuid5(_NAMESPACE, f"duplicate-selection:{suffix}")),
            request_bytes=request_bytes,
        )
    duplicate_result = inspect_selected_c3_strategy_history_window_for_test(
        duplicate, _EPOCH, current, _CONFIG, lambda value: value
    )
    assert duplicate_result.classification is (
        SelectedC3StrategyHistoryWindowClassification.BLOCKED
    )
    assert duplicate_result.selected == ()

    malformed = _selection_database()
    _insert_selection(
        malformed,
        session_id=str(current.selected.audit.session_id),
        selection_id="NOT-A-UUID",
        request_bytes=request_bytes,
    )
    malformed_result = inspect_selected_c3_strategy_history_window_for_test(
        malformed, _EPOCH, current, _CONFIG, lambda value: value
    )
    assert malformed_result.classification is (
        SelectedC3StrategyHistoryWindowClassification.BLOCKED
    )
    assert malformed_result.selected == ()


def test_session_binding_rejects_wrong_symbol_snapshot() -> None:
    session = TradingSession(date(2026, 8, 21))
    request = personal_desktop_unattended_capture_request(session)

    with pytest.raises(
        PersonalDesktopUnattendedC3HistoryError,
        match="source-owned SPY profile",
    ):
        SessionIndexedSelectedC3SnapshotReadResult(
            session,
            request,
            request.canonical_c2_request_json(),
            _selected_result(session, symbol=Symbol("QQQ")),
        )


def test_valid_history_binding_uses_non_authoritative_inner_seed() -> None:
    history, current = _valid_chain()
    verified = history_module._verified_history_seed(history, current, _CONFIG)

    binding = SelectedC3StrategyHistoryBinding(history, current, verified)

    assert binding.verified_seed.target_session == current.session
    assert binding.verified_seed.seed.source.source_id == (
        PERSONAL_DESKTOP_UNATTENDED_HISTORY_SOURCE_ID
    )
    assert binding.verified_seed.seed.source.authoritative is False
    assert binding.verified_seed.seed.source.classification.value == "OFFLINE_SEED"
    assert tuple(item.session for item in binding.history) == tuple(
        item.session for item in history
    )


def test_private_provenance_lifetime_is_nonsemantic() -> None:
    history, current = _valid_chain()
    verified = history_module._verified_history_seed(history, current, _CONFIG)
    retained = SelectedC3StrategyHistoryBinding(history, current, verified)
    disposable = SelectedC3StrategyHistoryBinding(history, current, verified)

    object.__setattr__(retained, "_provenance_lifetime", object())

    assert retained == disposable
    assert repr(retained) == repr(disposable)
    field = retained.__dataclass_fields__["_provenance_lifetime"]
    assert field.init is field.repr is field.compare is False


def test_history_gap_is_rejected() -> None:
    history = (
        _session_read(date(2026, 8, 14)),
        _session_read(date(2026, 8, 17)),
        _session_read(date(2026, 8, 18)),
        _session_read(date(2026, 8, 20)),
        _session_read(date(2026, 8, 21)),
    )
    current = _session_read(date(2026, 8, 24))

    with pytest.raises(
        PersonalDesktopUnattendedC3HistoryError,
        match="consecutive valid strategy seed",
    ):
        history_module._verified_history_seed(history, current, _CONFIG)


def test_history_cannot_contain_current_or_future_session() -> None:
    history, current = _valid_chain()
    contaminated = (*history[:-1], current)

    with pytest.raises(
        PersonalDesktopUnattendedC3HistoryError,
        match="strictly precede",
    ):
        history_module._verified_history_seed(contaminated, current, _CONFIG)


def test_offline_seed_substitution_is_rejected_by_binding() -> None:
    history, current = _valid_chain()
    bars = tuple(
        replay_verified_daily_snapshot(item.selected.verification).bars[0]
        for item in history
    )
    substituted = create_strategy_history_seed(
        symbol=PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
        source=StrategyHistorySeedSourceDescriptor("manual-offline-substitution"),
        bars=bars,
    )
    payload = serialize_strategy_history_seed(substituted)
    verified = verify_strategy_history_seed(
        payload,
        expected_symbol=PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
        target_session=current.session,
        strategy_config=_CONFIG,
        calendar=BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
    )

    with pytest.raises(
        PersonalDesktopUnattendedC3HistoryError,
        match="does not match selected C3 history",
    ):
        SelectedC3StrategyHistoryBinding(history, current, verified)


def test_production_builder_requires_every_p2_result_to_match_same_c1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history, current = _valid_chain()
    authority = object()
    seen: list[UUID] = []

    monkeypatch.setattr(
        history_module,
        "require_validated_production_authority",
        lambda value: value,
    )

    def require_match(
        permit: object,
        audit: SelectedC3SnapshotAuditEvidence,
        candidate_authority: object,
    ) -> None:
        del permit
        assert candidate_authority is authority
        seen.append(audit.selection_id)

    monkeypatch.setattr(
        history_module,
        "require_selected_c3_snapshot_matches_authority",
        require_match,
    )

    binding = build_selected_c3_strategy_history_binding(
        authority,  # type: ignore[arg-type]
        history,
        current,
        _CONFIG,
    )

    assert type(binding) is SelectedC3StrategyHistoryBinding
    assert len(seen) == 6


def test_production_builder_fails_when_any_p2_result_has_wrong_c1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history, current = _valid_chain()
    authority = object()
    rejected_selection = history[2].selected.audit.selection_id

    monkeypatch.setattr(
        history_module,
        "require_validated_production_authority",
        lambda value: value,
    )

    def require_match(
        permit: object,
        audit: SelectedC3SnapshotAuditEvidence,
        candidate_authority: object,
    ) -> None:
        del permit, candidate_authority
        if audit.selection_id == rejected_selection:
            raise SelectedC3SnapshotReadError("P2 read does not match C1 authority")

    monkeypatch.setattr(
        history_module,
        "require_selected_c3_snapshot_matches_authority",
        require_match,
    )

    with pytest.raises(SelectedC3SnapshotReadError, match="does not match C1"):
        build_selected_c3_strategy_history_binding(
            authority,  # type: ignore[arg-type]
            history,
            current,
            _CONFIG,
        )
