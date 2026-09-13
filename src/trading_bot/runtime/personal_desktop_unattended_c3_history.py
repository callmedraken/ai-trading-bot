"""Architecture-111 session-indexed C3 read and rolling-history authority."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotBar,
    replay_verified_daily_snapshot,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    WindowsSelectedC3SnapshotReadAuthority,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    next_xnys_execution_session,
)
from trading_bot.runtime.strategy_history_seed import (
    StrategyHistorySeedSourceDescriptor,
    VerifiedStrategyHistorySeed,
    create_strategy_history_seed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.runtime.windows_authority import PRODUCTION_AUTHORITY_PATHS
from trading_bot.runtime.windows_authority_schema import load_approved_sqlite_authority_build
from trading_bot.runtime.windows_authority_sqlite import open_read_only_sqlite_connection
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_open_connection_matches_validated_authority,
    require_validated_production_authority,
)
from trading_bot.runtime.windows_effectful_capture import ProductionCaptureRequest
from trading_bot.strategies import MovingAverageCrossoverConfig

PERSONAL_DESKTOP_UNATTENDED_SYMBOL = Symbol("SPY")
PERSONAL_DESKTOP_UNATTENDED_HISTORY_SOURCE_ID = (
    "architecture111-selected-c3-history-v1"
)


class PersonalDesktopUnattendedC3HistoryError(ValueError):
    """Architecture-111 selected-C3 session/history evidence is invalid."""


@dataclass(frozen=True, slots=True)
class SessionIndexedSelectedC3SnapshotReadResult:
    """One exact source-owned session request bound to one strict P2 result."""

    session: TradingSession
    capture_request: ProductionCaptureRequest
    canonical_request_bytes: bytes
    selected: SelectedC3SnapshotReadResult

    def __post_init__(self) -> None:
        if type(self.session) is not TradingSession:
            raise PersonalDesktopUnattendedC3HistoryError(
                "session-indexed read requires an exact TradingSession"
            )
        expected_request = personal_desktop_unattended_capture_request(self.session)
        if self.capture_request != expected_request:
            raise PersonalDesktopUnattendedC3HistoryError(
                "session-indexed read capture request is not source-owned"
            )
        expected_bytes = expected_request.canonical_c2_request_json()
        if (
            type(self.canonical_request_bytes) is not bytes
            or self.canonical_request_bytes != expected_bytes
        ):
            raise PersonalDesktopUnattendedC3HistoryError(
                "session-indexed read request bytes are not canonical"
            )
        if type(self.selected) is not SelectedC3SnapshotReadResult:
            raise PersonalDesktopUnattendedC3HistoryError(
                "session-indexed read requires one exact P2 result"
            )
        bar = _single_profile_bar(self.selected)
        if bar.session != self.session:
            raise PersonalDesktopUnattendedC3HistoryError(
                "selected C3 snapshot session does not match the requested session"
            )


@dataclass(frozen=True, slots=True)
class SelectedC3StrategyHistoryBinding:
    """Process-local proof that one strategy seed came only from selected C3."""

    history: tuple[SessionIndexedSelectedC3SnapshotReadResult, ...]
    current: SessionIndexedSelectedC3SnapshotReadResult
    verified_seed: VerifiedStrategyHistorySeed

    def __post_init__(self) -> None:
        try:
            history = tuple(self.history)
        except TypeError as error:
            raise PersonalDesktopUnattendedC3HistoryError(
                "selected C3 strategy history must be iterable"
            ) from error
        if any(
            type(item) is not SessionIndexedSelectedC3SnapshotReadResult
            for item in history
        ):
            raise PersonalDesktopUnattendedC3HistoryError(
                "strategy history entries must be exact session-indexed P2 results"
            )
        if type(self.current) is not SessionIndexedSelectedC3SnapshotReadResult:
            raise PersonalDesktopUnattendedC3HistoryError(
                "current selected C3 result is invalid"
            )
        if type(self.verified_seed) is not VerifiedStrategyHistorySeed:
            raise PersonalDesktopUnattendedC3HistoryError(
                "verified strategy seed evidence is invalid"
            )
        object.__setattr__(self, "history", history)
        expected = _verified_history_seed(
            history,
            self.current,
            self.verified_seed.strategy_config,
        )
        if expected != self.verified_seed:
            raise PersonalDesktopUnattendedC3HistoryError(
                "verified strategy seed does not match selected C3 history"
            )


def personal_desktop_unattended_capture_request(
    session: TradingSession,
) -> ProductionCaptureRequest:
    """Derive the exact source-owned C3 request for one completed session."""

    if type(session) is not TradingSession:
        raise PersonalDesktopUnattendedC3HistoryError(
            "capture session must be an exact TradingSession"
        )
    execution_session = next_xnys_execution_session(session)
    return ProductionCaptureRequest(
        ordered_universe=(PERSONAL_DESKTOP_UNATTENDED_SYMBOL,),
        request_window_start_date=session.session_date,
        request_window_end_date=session.session_date,
        target_session_date=execution_session.session_date,
    )


class WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority:
    """Resolve one source-owned session to an exact strict production P2 read."""

    __slots__ = ("_authority", "_p2", "_sqlite_vfs")

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        authority = require_validated_production_authority(authority)
        sqlite_build = load_approved_sqlite_authority_build()
        if sqlite_build.digest.hex() != authority.sqlite_build_manifest_digest:
            raise PersonalDesktopUnattendedC3HistoryError(
                "approved SQLite build does not match production authority"
            )
        self._authority = authority
        self._sqlite_vfs = sqlite_build.vfs
        self._p2 = WindowsSelectedC3SnapshotReadAuthority(authority)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError(
            "WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority cannot be subclassed"
        )

    def read_selected_snapshot_for_session(
        self,
        session: TradingSession,
    ) -> SessionIndexedSelectedC3SnapshotReadResult:
        request = personal_desktop_unattended_capture_request(session)
        request_bytes = request.canonical_c2_request_json()
        connection: sqlite3.Connection | None = None
        try:
            connection = open_read_only_sqlite_connection(
                str(PRODUCTION_AUTHORITY_PATHS.database),
                vfs=self._sqlite_vfs,
            )
            require_open_connection_matches_validated_authority(
                self._authority,
                connection,
            )
            selection_id = _resolve_selection_id_from_connection(
                connection,
                self._authority.authority_epoch_id,
                request_bytes,
            )
        except PersonalDesktopUnattendedC3HistoryError:
            raise
        except BaseException as error:
            raise PersonalDesktopUnattendedC3HistoryError(
                "session-indexed selected C3 resolution failed closed"
            ) from error
        finally:
            if connection is not None:
                connection.close()

        selected = self._p2.read_selected_snapshot(selection_id)
        require_selected_c3_snapshot_matches_authority(
            selected.permit,
            selected.audit,
            self._authority,
        )
        return SessionIndexedSelectedC3SnapshotReadResult(
            session,
            request,
            request_bytes,
            selected,
        )


def build_selected_c3_strategy_history_binding(
    authority: ValidatedProductionAuthority,
    history: tuple[SessionIndexedSelectedC3SnapshotReadResult, ...],
    current: SessionIndexedSelectedC3SnapshotReadResult,
    strategy_config: MovingAverageCrossoverConfig,
) -> SelectedC3StrategyHistoryBinding:
    """Build C3-backed history only after every retained P2 read matches C1."""

    authority = require_validated_production_authority(authority)
    try:
        retained = tuple(history)
    except TypeError as error:
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 strategy history must be iterable"
        ) from error
    if type(current) is not SessionIndexedSelectedC3SnapshotReadResult:
        raise PersonalDesktopUnattendedC3HistoryError(
            "current selected C3 result is invalid"
        )
    for item in (*retained, current):
        if type(item) is not SessionIndexedSelectedC3SnapshotReadResult:
            raise PersonalDesktopUnattendedC3HistoryError(
                "strategy history entries must be exact session-indexed P2 results"
            )
        require_selected_c3_snapshot_matches_authority(
            item.selected.permit,
            item.selected.audit,
            authority,
        )
    verified = _verified_history_seed(retained, current, strategy_config)
    return SelectedC3StrategyHistoryBinding(retained, current, verified)


def require_selected_c3_strategy_history_binding(
    binding: SelectedC3StrategyHistoryBinding,
    authority: ValidatedProductionAuthority,
) -> SelectedC3StrategyHistoryBinding:
    """Revalidate process-local selected-C3 provenance before binding consumption."""

    if type(binding) is not SelectedC3StrategyHistoryBinding:
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 strategy history binding type is invalid"
        )
    authority = require_validated_production_authority(authority)
    for item in (*binding.history, binding.current):
        require_selected_c3_snapshot_matches_authority(
            item.selected.permit,
            item.selected.audit,
            authority,
        )
    expected = _verified_history_seed(
        binding.history,
        binding.current,
        binding.verified_seed.strategy_config,
    )
    if expected != binding.verified_seed:
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 strategy history binding no longer reconciles"
        )
    return binding


def _resolve_selection_id_from_connection(
    connection: sqlite3.Connection,
    authority_epoch_id: str,
    canonical_request_bytes: bytes,
) -> str:
    if type(connection) is not sqlite3.Connection:
        raise TypeError("session-indexed C3 resolution requires sqlite3.Connection")
    if type(authority_epoch_id) is not str or not authority_epoch_id:
        raise PersonalDesktopUnattendedC3HistoryError(
            "authority epoch ID is invalid"
        )
    if type(canonical_request_bytes) is not bytes or not canonical_request_bytes:
        raise PersonalDesktopUnattendedC3HistoryError(
            "canonical C3 request bytes are invalid"
        )
    initial_changes = connection.total_changes
    try:
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA query_only").fetchone() != (1,):
            raise PersonalDesktopUnattendedC3HistoryError(
                "session-indexed C3 resolver is not query-only"
            )
        connection.execute("BEGIN")
        rows = connection.execute(
            _SESSION_SELECTION_SQL,
            (
                authority_epoch_id,
                canonical_request_bytes,
                hashlib.sha256(canonical_request_bytes).digest(),
            ),
        ).fetchall()
        if len(rows) != 1:
            raise PersonalDesktopUnattendedC3HistoryError(
                "exactly one selected C3 lineage must match the source-owned request"
            )
        selection_id = _canonical_uuid_text(rows[0][0], "selection ID")
        if connection.total_changes != initial_changes:
            raise PersonalDesktopUnattendedC3HistoryError(
                "session-indexed C3 read observed a database mutation"
            )
        connection.rollback()
        return selection_id
    except PersonalDesktopUnattendedC3HistoryError:
        if connection.in_transaction:
            connection.rollback()
        raise
    except BaseException as error:
        if connection.in_transaction:
            connection.rollback()
        raise PersonalDesktopUnattendedC3HistoryError(
            "session-indexed C3 durable lookup is invalid"
        ) from error


def _verified_history_seed(
    history: tuple[SessionIndexedSelectedC3SnapshotReadResult, ...],
    current: SessionIndexedSelectedC3SnapshotReadResult,
    strategy_config: MovingAverageCrossoverConfig,
) -> VerifiedStrategyHistorySeed:
    if type(strategy_config) is not MovingAverageCrossoverConfig:
        raise PersonalDesktopUnattendedC3HistoryError(
            "strategy configuration is invalid"
        )
    if len(history) != strategy_config.long_window:
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 history must contain exactly the configured long window"
        )
    bars: list[DailySnapshotBar] = []
    seen: set[TradingSession] = set()
    for item in history:
        if item.session in seen:
            raise PersonalDesktopUnattendedC3HistoryError(
                "selected C3 history contains a duplicate session"
            )
        seen.add(item.session)
        if item.session >= current.session:
            raise PersonalDesktopUnattendedC3HistoryError(
                "selected C3 history must strictly precede the current session"
            )
        bars.append(_single_profile_bar(item.selected))
    source = StrategyHistorySeedSourceDescriptor(
        PERSONAL_DESKTOP_UNATTENDED_HISTORY_SOURCE_ID
    )
    seed = create_strategy_history_seed(
        symbol=PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
        source=source,
        bars=tuple(bars),
    )
    payload = serialize_strategy_history_seed(seed)
    try:
        return verify_strategy_history_seed(
            payload,
            expected_symbol=PERSONAL_DESKTOP_UNATTENDED_SYMBOL,
            target_session=current.session,
            strategy_config=strategy_config,
            calendar=BoundMarketCalendar(
                XNYS_CALENDAR_DESCRIPTOR,
                NYSEMarketCalendar(),
            ),
        )
    except Exception as error:
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 history is not a consecutive valid strategy seed"
        ) from error


def _single_profile_bar(selected: SelectedC3SnapshotReadResult) -> DailySnapshotBar:
    if type(selected) is not SelectedC3SnapshotReadResult:
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 result type is invalid"
        )
    try:
        replay = replay_verified_daily_snapshot(selected.verification)
    except Exception as error:
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 snapshot cannot be replayed"
        ) from error
    if (
        replay.symbols != (PERSONAL_DESKTOP_UNATTENDED_SYMBOL,)
        or len(replay.bars) != 1
        or replay.bars[0].bar.symbol != PERSONAL_DESKTOP_UNATTENDED_SYMBOL
    ):
        raise PersonalDesktopUnattendedC3HistoryError(
            "selected C3 snapshot does not match the source-owned SPY profile"
        )
    return replay.bars[0]


def _canonical_uuid_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise PersonalDesktopUnattendedC3HistoryError(
            f"{field_name} must be canonical UUID text"
        )
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise PersonalDesktopUnattendedC3HistoryError(
            f"{field_name} must be canonical UUID text"
        ) from None
    if str(parsed) != value:
        raise PersonalDesktopUnattendedC3HistoryError(
            f"{field_name} must be canonical UUID text"
        )
    return value


_SESSION_SELECTION_SQL = """
SELECT ss.selection_id
FROM sessions AS s
JOIN session_selections AS ss ON ss.session_id = s.session_id
WHERE s.authority_epoch_id = ?
  AND s.state = 'SUCCESS_SELECTED'
  AND s.request_json = ?
  AND s.request_digest = ?
ORDER BY ss.selection_id
"""
