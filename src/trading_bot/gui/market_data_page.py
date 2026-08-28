"""Qt presentation for one bounded verified market-data snapshot state."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QVBoxLayout, QWidget

from trading_bot.gui.market_data_models import (
    MarketDataPageState,
    MarketDataPageStatus,
    VerifiedMarketSnapshotView,
)


def _plain_label(text: str, parent: QWidget, object_name: str) -> QLabel:
    label = QLabel(parent)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(text)
    return label


class MarketDataPage(QWidget):
    """Render one immutable verified market-data presentation state."""

    def __init__(
        self,
        state: MarketDataPageState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if type(state) is not MarketDataPageState:
            raise TypeError("state must be exactly MarketDataPageState")

        self._state = state
        self.setObjectName("marketDataPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)

        layout.addWidget(_plain_label("Market Data", self, "pageTitle"))
        layout.addWidget(_plain_label(state.message, self, "marketDataMessage"))

        message = self.findChild(QLabel, "marketDataMessage")
        if message is None:
            raise RuntimeError("market-data message label is missing")
        message.setObjectName("summaryLabel")
        message.setWordWrap(True)

        if state.status is MarketDataPageStatus.UNAVAILABLE:
            status = _plain_label("Unavailable", self, "marketDataStatus")
            status.setProperty("status", "unavailable")
            layout.insertWidget(1, status)
        else:
            snapshot = state.snapshot
            if type(snapshot) is not VerifiedMarketSnapshotView:
                raise RuntimeError("verified market-data state is missing its snapshot")
            status = _plain_label("Verified Offline", self, "marketDataStatus")
            status.setProperty("status", "verified")
            layout.insertWidget(1, status)
            layout.addWidget(self._build_snapshot_details(snapshot))

        layout.addStretch(1)

    @property
    def market_data_state(self) -> MarketDataPageState:
        """Return the immutable state rendered by this page."""
        return self._state

    def _build_snapshot_details(self, snapshot: VerifiedMarketSnapshotView) -> QFrame:
        details = QFrame(self)
        details.setObjectName("marketDataDetailPanel")
        form = QFormLayout(details)
        form.setContentsMargins(18, 16, 18, 16)
        form.setVerticalSpacing(10)

        fields = (
            ("Snapshot ID", str(snapshot.snapshot_id), "marketDataSnapshotId"),
            (
                "Target XNYS session",
                snapshot.target_session_date.isoformat(),
                "marketDataTargetSession",
            ),
            ("Symbols", ", ".join(snapshot.symbols), "marketDataSymbols"),
            ("Provider", snapshot.provider_id, "marketDataProviderId"),
            (
                "Provider operation",
                snapshot.provider_operation,
                "marketDataProviderOperation",
            ),
            ("Provider feed", snapshot.provider_feed, "marketDataProviderFeed"),
            (
                "Artifact SHA-256",
                snapshot.artifact_sha256,
                "marketDataArtifactSha256",
            ),
            (
                "Artifact bytes",
                str(snapshot.artifact_byte_length),
                "marketDataArtifactByteLength",
            ),
            (
                "Captured at",
                snapshot.captured_at.isoformat(),
                "marketDataCapturedAt",
            ),
            (
                "Provider as-of",
                (
                    snapshot.provider_as_of.isoformat()
                    if snapshot.provider_as_of is not None
                    else "Not retained"
                ),
                "marketDataProviderAsOf",
            ),
            (
                "Source payload SHA-256",
                snapshot.source_payload_sha256,
                "marketDataSourcePayloadSha256",
            ),
            (
                "Source payload bytes",
                str(snapshot.source_payload_byte_length),
                "marketDataSourcePayloadByteLength",
            ),
            (
                "Source payload media type",
                snapshot.source_payload_media_type,
                "marketDataSourcePayloadMediaType",
            ),
        )
        for field_name, value, object_name in fields:
            field_label = _plain_label(field_name, details, "marketDataFieldLabel")
            field_value = _plain_label(value, details, object_name)
            field_value.setWordWrap(True)
            field_value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            form.addRow(field_label, field_value)

        return details
