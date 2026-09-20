"""Qt-free GUI-A8 startup configuration and read-only service composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trading_bot.gui.market_data_models import (
    MarketDataPageState,
    unavailable_market_data_state,
)
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.models import ApplicationOverview, ResearchPageState
from trading_bot.gui.operator_observability_models import (
    OperatorOperationsPageState,
    unavailable_operator_operations_state,
)
from trading_bot.gui.paper_account_models import (
    PaperAccountPageState,
    unavailable_paper_account_state,
)
from trading_bot.gui.paper_models import PaperPageState, unavailable_paper_state
from trading_bot.gui.research_service import (
    CompactReportResearchService,
    unavailable_research_state,
)
from trading_bot.gui.verified_genesis_paper_account_inspection_service import (
    VerifiedGenesisPaperAccountInspectionService,
)
from trading_bot.gui.verified_snapshot_inspection_service import (
    VerifiedSnapshotInspectionService,
)
from trading_bot.gui.verified_successor_paper_account_inspection_service import (
    VerifiedSuccessorPaperAccountInspectionService,
)


@dataclass(frozen=True, slots=True)
class GuiStartupConfiguration:
    """Explicit local read-only artifacts selected for one GUI startup."""

    research_report: Path | None = None
    market_data_snapshot: Path | None = None
    market_data_expected_sha256: str | None = None
    market_data_expected_byte_length: int | None = None
    paper_account_genesis: Path | None = None
    paper_account_expected_sha256: str | None = None
    paper_account_expected_byte_length: int | None = None
    paper_account_prior: Path | None = None
    paper_account_snapshot: Path | None = None
    paper_account_cycle_report: Path | None = None
    paper_account_successor: Path | None = None
    paper_account_successor_expected_sha256: str | None = None
    paper_account_successor_expected_byte_length: int | None = None

    def __post_init__(self) -> None:
        path_fields = (
            "research_report",
            "market_data_snapshot",
            "paper_account_genesis",
            "paper_account_prior",
            "paper_account_snapshot",
            "paper_account_cycle_report",
            "paper_account_successor",
        )
        for name in path_fields:
            value = getattr(self, name)
            if value is not None and not isinstance(value, Path):
                raise TypeError(f"{name} must be a Path or None")

        text_fields = (
            "market_data_expected_sha256",
            "paper_account_expected_sha256",
            "paper_account_successor_expected_sha256",
        )
        for name in text_fields:
            value = getattr(self, name)
            if value is not None and type(value) is not str:
                raise TypeError(f"{name} must be a string or None")

        length_fields = (
            "market_data_expected_byte_length",
            "paper_account_expected_byte_length",
            "paper_account_successor_expected_byte_length",
        )
        for name in length_fields:
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer or None")

        if self.market_data_snapshot is None and (
            self.market_data_expected_sha256 is not None
            or self.market_data_expected_byte_length is not None
        ):
            raise ValueError("market-data expected evidence requires a snapshot")

        successor_paths = (
            self.paper_account_prior,
            self.paper_account_snapshot,
            self.paper_account_cycle_report,
            self.paper_account_successor,
        )
        successor_any = any(value is not None for value in successor_paths)
        successor_all = all(value is not None for value in successor_paths)

        if successor_any and not successor_all:
            raise ValueError("paper-account successor mode requires all four artifacts")
        if self.paper_account_genesis is not None and successor_any:
            raise ValueError(
                "paper-account GENESIS and successor modes are mutually exclusive"
            )

        if self.paper_account_genesis is None and (
            self.paper_account_expected_sha256 is not None
            or self.paper_account_expected_byte_length is not None
        ):
            raise ValueError("GENESIS expected evidence requires a GENESIS artifact")

        if not successor_all and (
            self.paper_account_successor_expected_sha256 is not None
            or self.paper_account_successor_expected_byte_length is not None
        ):
            raise ValueError(
                "successor expected evidence requires the complete successor proof set"
            )


class ReadOnlyGuiApplicationService:
    """Compose existing reviewed read-only GUI adapters from explicit inputs."""

    def __init__(self, config: GuiStartupConfiguration) -> None:
        if type(config) is not GuiStartupConfiguration:
            raise TypeError("config must be exactly GuiStartupConfiguration")
        self._config = config
        self._overview = MockGuiApplicationService().get_overview()
        self._research = (
            None
            if config.research_report is None
            else CompactReportResearchService(config.research_report)
        )
        self._market_data = (
            None
            if config.market_data_snapshot is None
            else VerifiedSnapshotInspectionService(
                config.market_data_snapshot,
                expected_sha256=config.market_data_expected_sha256,
                expected_byte_length=config.market_data_expected_byte_length,
            )
        )
        self._paper_account = self._paper_account_service(config)

    @staticmethod
    def _paper_account_service(config: GuiStartupConfiguration):
        if config.paper_account_genesis is not None:
            return VerifiedGenesisPaperAccountInspectionService(
                config.paper_account_genesis,
                expected_sha256=config.paper_account_expected_sha256,
                expected_byte_length=config.paper_account_expected_byte_length,
            )
        if config.paper_account_successor is not None:
            prior = config.paper_account_prior
            snapshot = config.paper_account_snapshot
            report = config.paper_account_cycle_report
            if prior is None or snapshot is None or report is None:
                raise ValueError("complete successor proof set is required")
            return VerifiedSuccessorPaperAccountInspectionService(
                prior,
                snapshot,
                report,
                config.paper_account_successor,
                expected_successor_sha256=(
                    config.paper_account_successor_expected_sha256
                ),
                expected_successor_byte_length=(
                    config.paper_account_successor_expected_byte_length
                ),
            )
        return None

    def get_overview(self) -> ApplicationOverview:
        """Return the existing bounded GUI overview."""
        return self._overview

    def get_research_state(self) -> ResearchPageState:
        """Return the configured research report or deterministic unavailable state."""
        if self._research is None:
            return unavailable_research_state()
        return self._research.get_research_state()

    def get_paper_state(self) -> PaperPageState:
        """Keep Paper Operation unavailable without already-verified inputs."""
        return unavailable_paper_state()

    def get_market_data_state(self) -> MarketDataPageState:
        """Return one explicit verified snapshot or deterministic unavailable state."""
        if self._market_data is None:
            return unavailable_market_data_state()
        return self._market_data.get_market_data_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        """Return one explicit verified account artifact/edge or unavailable state."""
        if self._paper_account is None:
            return unavailable_paper_account_state()
        return self._paper_account.get_paper_account_state()

    def get_operator_observability_state(self) -> OperatorOperationsPageState:
        """Keep production operator observability disconnected from normal startup."""
        return unavailable_operator_operations_state()

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        """Retain the existing explicit local Research Open Report behavior."""
        return CompactReportResearchService(artifact_path).get_research_state()
