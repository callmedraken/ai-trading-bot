"""Qt-free adaptation of one explicit offline-verified snapshot artifact."""

from pathlib import Path

from trading_bot.gui.market_data_models import (
    MarketDataPageState,
    MarketDataPageStatus,
    VerifiedMarketSnapshotView,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES,
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    verify_daily_snapshot,
)

_VERIFIED_MESSAGE = "One local market-data snapshot artifact was verified offline."
_UNAVAILABLE_MESSAGE = "Verified market-data snapshot inspection is unavailable."


class VerifiedSnapshotInspectionService:
    """Inspect one explicit snapshot artifact without provider or authority access."""

    def __init__(
        self,
        artifact_path: Path,
        *,
        expected_sha256: str | None = None,
        expected_byte_length: int | None = None,
    ) -> None:
        self._artifact_path = artifact_path
        self._expected_sha256 = expected_sha256
        self._expected_byte_length = expected_byte_length

    def get_market_data_state(self) -> MarketDataPageState:
        """Return one bounded verified state without exposing inspection failures."""
        try:
            payload = _read_explicit_artifact(self._artifact_path)
            verification = verify_daily_snapshot(
                payload,
                BoundMarketCalendar(
                    XNYS_CALENDAR_DESCRIPTOR,
                    NYSEMarketCalendar(),
                ),
                expected_sha256=self._expected_sha256,
                expected_byte_length=self._expected_byte_length,
            )
            return _adapt_verification(verification)
        except Exception:
            return _unavailable_state()


def _read_explicit_artifact(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise TypeError("snapshot artifact path must be a Path")
    with path.open("rb") as stream:
        payload = stream.read(MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES + 1)
    if len(payload) > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES:
        raise ValueError("snapshot artifact exceeds the supported size bound")
    return payload


def _adapt_verification(
    verification: DailySnapshotVerificationResult,
) -> MarketDataPageState:
    if type(verification) is not DailySnapshotVerificationResult:
        raise TypeError("snapshot verification result has an unsupported type")
    if (
        verification.status is not DailySnapshotVerificationStatus.PASS
        or verification.snapshot is None
    ):
        return _unavailable_state()

    snapshot = verification.snapshot
    source_payload = snapshot.audit.source_payload
    return MarketDataPageState(
        status=MarketDataPageStatus.VERIFIED,
        message=_VERIFIED_MESSAGE,
        snapshot=VerifiedMarketSnapshotView(
            snapshot_id=snapshot.snapshot_id,
            target_session_date=snapshot.target_session.session_date,
            symbols=tuple(str(symbol) for symbol in snapshot.request.symbols),
            provider_id=snapshot.provider.provider_id,
            provider_operation=snapshot.provider.operation,
            provider_feed=snapshot.provider.feed,
            artifact_sha256=verification.sha256,
            artifact_byte_length=verification.byte_length,
            captured_at=snapshot.audit.captured_at,
            provider_as_of=snapshot.audit.provider_as_of,
            source_payload_sha256=source_payload.sha256,
            source_payload_byte_length=source_payload.byte_length,
            source_payload_media_type=source_payload.media_type,
        ),
    )


def _unavailable_state() -> MarketDataPageState:
    return MarketDataPageState(
        status=MarketDataPageStatus.UNAVAILABLE,
        message=_UNAVAILABLE_MESSAGE,
        snapshot=None,
    )
