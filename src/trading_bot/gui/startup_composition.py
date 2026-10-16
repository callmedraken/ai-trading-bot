"""Qt-free GUI-A8 startup configuration and read-only service composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trading_bot.gui.market_data_models import (
    MarketDataPageState,
    unavailable_market_data_state,
)
from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
    ResearchPageState,
)
from trading_bot.gui.operator_observability_models import (
    OperatorOperationsPageState,
    unavailable_operator_operations_state,
)
from trading_bot.gui.paper_account_models import (
    PaperAccountPageState,
    unavailable_paper_account_state,
)
from trading_bot.gui.paper_models import PaperPageState, unavailable_paper_state
from trading_bot.gui.production_strategy_models import (
    ProductionStrategyPageState,
    unavailable_production_strategy_state,
)
from trading_bot.gui.production_strategy_service import (
    ProductionStrategyContractInspectionService,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState,
    unavailable_research_candidate_lifecycle_state,
)
from trading_bot.gui.research_candidate_lifecycle_service import (
    ResearchCandidateLifecycleInspectionService,
)
from trading_bot.gui.research_service import (
    CompactReportResearchService,
    unavailable_research_state,
)
from trading_bot.gui.runtime_evidence_service import (
    ProductionRuntimeEvidenceInspectionService,
)
from trading_bot.gui.runtime_models import (
    RuntimePageState,
    RuntimePageStatus,
    unavailable_runtime_state,
)
from trading_bot.gui.supervisor_adapter import build_supervisor_state
from trading_bot.gui.supervisor_models import SupervisorPageStatus
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
    production_strategy_contract: Path | None = None
    runtime_acl_evidence: Path | None = None
    runtime_qualification_evidence: Path | None = None
    runtime_session_evidence: Path | None = None
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
    research_walk_forward_candidate: Path | None = None
    research_shadow_binding: Path | None = None
    research_shadow_observation_batch: Path | None = None
    research_shadow_qualification: Path | None = None
    research_shadow_candidate: Path | None = None

    def __post_init__(self) -> None:
        path_fields = (
            "production_strategy_contract",
            "runtime_acl_evidence",
            "runtime_qualification_evidence",
            "runtime_session_evidence",
            "research_report",
            "market_data_snapshot",
            "paper_account_genesis",
            "paper_account_prior",
            "paper_account_snapshot",
            "paper_account_cycle_report",
            "paper_account_successor",
            "research_walk_forward_candidate",
            "research_shadow_binding",
            "research_shadow_observation_batch",
            "research_shadow_qualification",
            "research_shadow_candidate",
        )
        for name in path_fields:
            value = getattr(self, name)
            if value is not None and not isinstance(value, Path):
                raise TypeError(f"{name} must be a Path or None")

        lifecycle_paths = (
            self.research_walk_forward_candidate,
            self.research_shadow_binding,
            self.research_shadow_observation_batch,
            self.research_shadow_qualification,
            self.research_shadow_candidate,
        )
        if any(path is not None for path in lifecycle_paths) and not all(
            path is not None for path in lifecycle_paths
        ):
            raise ValueError("research lifecycle requires all five explicit artifacts")

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
        self._lifecycle = (
            None
            if config.research_walk_forward_candidate is None
            else ResearchCandidateLifecycleInspectionService(
                config.research_walk_forward_candidate,
                config.research_shadow_binding,
                config.research_shadow_observation_batch,
                config.research_shadow_qualification,
                config.research_shadow_candidate,
            )
        )
        self._production_strategy = (
            None
            if config.production_strategy_contract is None
            else ProductionStrategyContractInspectionService(
                config.production_strategy_contract
            )
        )
        self._cached_research: ResearchPageState | None = None
        runtime_paths = (
            config.runtime_acl_evidence,
            config.runtime_qualification_evidence,
            config.runtime_session_evidence,
        )
        self._runtime = (
            ProductionRuntimeEvidenceInspectionService(
                acl=config.runtime_acl_evidence,
                qualification=config.runtime_qualification_evidence,
                session=config.runtime_session_evidence,
            )
            if any(path is not None for path in runtime_paths)
            else None
        )
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
        """Describe configured sources and the cached explicit runtime evidence."""
        market_configured = self._config.market_data_snapshot is not None
        paper_account_configured = (
            self._config.paper_account_genesis is not None
            or self._config.paper_account_successor is not None
        )
        runtime = (
            unavailable_runtime_state()
            if self._runtime is None
            else self._runtime.get_runtime_state()
        )
        strategy = (
            unavailable_production_strategy_state()
            if self._production_strategy is None
            else self._production_strategy.get_production_strategy_state()
        )
        supervisor = build_supervisor_state(self._research_state(), runtime, strategy)
        return ApplicationOverview(
            mode=OperatingMode.RESEARCH,
            environment="Local read-only GUI",
            summary=(
                "Read-only GUI; explicitly selected local artifacts may be inspected."
            ),
            components=(
                ComponentStatus(
                    key="research",
                    title="Research",
                    status=PresentationStatus.INFO,
                    detail=(
                        "Compact historical reports are presented read-only."
                        if self._config.research_report is None
                        else "An explicit local historical report is configured."
                    ),
                ),
                ComponentStatus(
                    key="paper",
                    title="Paper Operation",
                    status=PresentationStatus.INFO,
                    detail=(
                        "Paper Operation is read-only; execution controls are not "
                        "connected."
                    ),
                ),
                ComponentStatus(
                    key="paper-account",
                    title="Paper Account",
                    status=(
                        PresentationStatus.INFO
                        if paper_account_configured
                        else PresentationStatus.UNAVAILABLE
                    ),
                    detail=(
                        "Explicit local paper-account artifacts are configured "
                        "for offline verification."
                        if paper_account_configured
                        else "No verified paper-account checkpoint is connected."
                    ),
                ),
                ComponentStatus(
                    key="market-data",
                    title="Market Data",
                    status=(
                        PresentationStatus.INFO
                        if market_configured
                        else PresentationStatus.UNAVAILABLE
                    ),
                    detail=(
                        "An explicit local market-data snapshot is configured "
                        "for offline verification."
                        if market_configured
                        else "No verified market-data snapshot artifact is connected."
                    ),
                ),
                ComponentStatus(
                    key="operations",
                    title="Operations",
                    status=PresentationStatus.UNAVAILABLE,
                    detail=(
                        "Production operator observability is not connected to "
                        "this GUI service."
                    ),
                ),
                ComponentStatus(
                    key="evidence",
                    title="Evidence",
                    status=PresentationStatus.INFO,
                    detail=(
                        "Timeline is derived from already-acquired read-only "
                        "presentation evidence."
                    ),
                ),
                ComponentStatus(
                    key="runtime",
                    title="Runtime",
                    status={
                        RuntimePageStatus.UNAVAILABLE: PresentationStatus.UNAVAILABLE,
                        RuntimePageStatus.AVAILABLE: PresentationStatus.INFO,
                        RuntimePageStatus.ATTENTION: PresentationStatus.BLOCKED,
                    }[runtime.status],
                    detail=runtime.message,
                ),
                ComponentStatus(
                    key="system",
                    title="System",
                    status=PresentationStatus.INFO,
                    detail="The GUI is read-only; no production authority is granted.",
                ),
                ComponentStatus(
                    "supervisor",
                    "Supervisor",
                    {
                        SupervisorPageStatus.UNAVAILABLE: (
                            PresentationStatus.UNAVAILABLE
                        ),
                        SupervisorPageStatus.AVAILABLE: PresentationStatus.INFO,
                        SupervisorPageStatus.ATTENTION: PresentationStatus.BLOCKED,
                    }[supervisor.status],
                    supervisor.message,
                ),
            ),
        )

    def get_research_state(self) -> ResearchPageState:
        """Return the configured research report or deterministic unavailable state."""
        return self._research_state()

    def get_research_candidate_lifecycle_state(
        self,
    ) -> ResearchCandidateLifecyclePageState:
        """Acquire only the explicitly selected local set; never from Overview."""
        if self._lifecycle is None:
            return unavailable_research_candidate_lifecycle_state()
        return self._lifecycle.get_research_candidate_lifecycle_state()

    def _research_state(self) -> ResearchPageState:
        if self._research is None:
            return unavailable_research_state()
        if self._cached_research is None:
            self._cached_research = self._research.get_research_state()
        return self._cached_research

    def get_production_strategy_state(self) -> ProductionStrategyPageState:
        """Return cached explicit acquisition or the deterministic no-I/O default."""
        if self._production_strategy is None:
            return unavailable_production_strategy_state()
        return self._production_strategy.get_production_strategy_state()

    def get_runtime_state(self) -> RuntimePageState:
        """Return one cached explicit evidence acquisition, or no-I/O default."""
        if self._runtime is None:
            return unavailable_runtime_state()
        return self._runtime.get_runtime_state()

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
