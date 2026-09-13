"""Pure Architecture-94 planning with Architecture-111 two-phase construction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from trading_bot.backtesting import BacktestContext
from trading_bot.domain import OrderSide, Position, Symbol, TradeProposal
from trading_bot.ledger import (
    AccountSnapshot,
    CompactPaperLedgerPosition,
    CompactPaperLedgerState,
)
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    DailySnapshotVerificationResult,
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    canonical_decimal,
    replay_verified_daily_snapshot,
    serialize_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.portfolio import MetadataEntry
from trading_bot.rebalancing import (
    RebalancePlanner,
    RebalanceProposalFactory,
    RebalanceProposalRequest,
    RebalanceProposalStatus,
    RebalanceStatus,
)
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA,
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_KEY_CHARACTERS,
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_VALUE_CHARACTERS,
    parse_checkpointed_verified_snapshot_paper_cycle_request,
    serialize_checkpointed_verified_snapshot_paper_cycle_request,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    VerifiedPriorCheckpoint,
    VerifiedPriorCheckpointKind,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    PersonalDesktopUnattendedDailyCycleTimingError,
    next_xnys_execution_session,
)
from trading_bot.runtime.strategy_history_seed import (
    StrategyHistorySeedVerificationError,
    VerifiedStrategyHistorySeed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.runtime.verified_c3_daily_bar_open import (
    C3VerifiedDailyBarOpenBinding,
    C3VerifiedDailyBarOpenBindingError,
    require_c3_verified_daily_bar_open_binding,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    VerifiedDailySnapshotReference,
    VerifiedSnapshotAccountPosition,
    VerifiedSnapshotAccountState,
    VerifiedSnapshotPaperCyclePolicies,
    VerifiedSnapshotPaperCyclePreparationRequest,
    prepare_verified_snapshot_paper_cycle,
)
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)

MANUAL_PAPER_STRATEGY_PLAN_SCHEMA = "manual-paper-strategy-plan/v1"
MANUAL_PAPER_STRATEGY_PLAN_IDENTITY_MATERIAL_VERSION = (
    "manual-paper-strategy-plan-identity/v1"
)
MANUAL_PAPER_STRATEGY_CONTEXT_MATERIAL_VERSION = "manual-paper-strategy-context/v1"
MANUAL_PAPER_CHECKPOINTED_REQUEST_MATERIAL_VERSION = (
    "manual-paper-checkpointed-request/v1"
)
MANUAL_PAPER_TARGET_MATERIAL_VERSION = "manual-paper-quantity-target/v1"
MANUAL_PAPER_STRATEGY_PLAN_NAMESPACE = UUID("65954286-9802-55a3-b938-2abf75b8e54c")
MANUAL_PAPER_STRATEGY_CONTEXT_NAMESPACE = UUID("26cbe765-16a8-51da-9ee8-a468940910cd")
MANUAL_PAPER_CHECKPOINTED_REQUEST_NAMESPACE = UUID(
    "f8d5eed4-994a-52c8-92bc-79f80fbd0d65"
)
MANUAL_PAPER_TARGET_NAMESPACE = UUID("b10973fa-2ad9-57b0-8934-15cafdb0c04a")
MAX_MANUAL_PAPER_STRATEGY_PLAN_BYTES = 8 * 1024 * 1024
MAX_MANUAL_PAPER_IDEMPOTENCY_KEY_CHARACTERS = 256
MAX_MANUAL_PAPER_BASE_METADATA = MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA - 3

ARCHITECTURE94_STRATEGY_PLAN_ID_METADATA_KEY = "architecture94.strategy_plan_id"
ARCHITECTURE94_STRATEGY_PLAN_SHA256_METADATA_KEY = "architecture94.strategy_plan_sha256"
ARCHITECTURE94_STRATEGY_PLAN_BYTE_LENGTH_METADATA_KEY = (
    "architecture94.strategy_plan_byte_length"
)
ARCHITECTURE94_METADATA_PREFIX = "architecture94."

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_PAPER_ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)
_ZERO = Decimal("0")

_ROOT_FIELDS = frozenset(
    {
        "caller_idempotency_key",
        "history_seed_artifact_utf8",
        "paper_account_id",
        "plan_id",
        "planner_result",
        "prior_checkpoint",
        "request_core_utf8",
        "schema",
        "selected_snapshot_artifact_utf8",
        "selected_c3_assertion",
        "strategy_config",
        "strategy_context",
        "strategy_result",
        "target",
    }
)
_SELECTED_C3_ASSERTION_FIELDS = frozenset(
    {
        "artifact_byte_length",
        "artifact_sha256",
        "selection_id",
        "session_id",
        "snapshot_id",
        "terminal_id",
    }
)
_CONFIG_FIELDS = frozenset({"desired_quantity", "long_window", "short_window"})
_CONTEXT_FIELDS = frozenset({"run_id", "step_index"})
_RESULT_FIELDS = frozenset({"proposal", "status"})
_PLANNER_FIELDS = frozenset({"plan_id", "proposal", "result_id", "status"})
_PROPOSAL_FIELDS = frozenset(
    {
        "confidence",
        "created_at",
        "desired_quantity",
        "proposal_id",
        "reason",
        "side",
        "symbol",
    }
)
_TARGET_FIELDS = frozenset({"quantities", "target_cash", "target_id"})
_TARGET_QUANTITY_FIELDS = frozenset({"quantity", "symbol"})
_PRIOR_FIELDS = frozenset(
    {
        "account_state_id",
        "checkpoint_byte_length",
        "checkpoint_id",
        "checkpoint_sha256",
        "compact_state",
        "empty_engine_state_id",
        "kind",
        "lineage_id",
        "sequence",
    }
)
_COMPACT_FIELDS = frozenset(
    {
        "as_of",
        "cash",
        "compact_state_id",
        "positions",
        "realized_profit_loss",
    }
)
_COMPACT_POSITION_FIELDS = frozenset(
    {"average_cost", "quantity", "symbol", "total_cost_basis"}
)


class ManualPaperStrategyPlanError(Exception):
    """Base class for pure strategy-plan failures."""


class ManualPaperStrategyPlanValidationError(ManualPaperStrategyPlanError, ValueError):
    """Raised when pure strategy-plan inputs or derived values fail closed."""


class ManualPaperStrategyPlanSerializationError(
    ManualPaperStrategyPlanError, ValueError
):
    """Raised when plan artifact bytes violate the canonical schema."""


class ManualPaperStrategyPlanVerificationError(
    ManualPaperStrategyPlanError, ValueError
):
    """Raised when replay or detached binding evidence disagrees."""


class ManualPaperStrategySignalStatus(StrEnum):
    """Explicit strategy outcome retained by the plan."""

    TRADE_PROPOSAL = "TRADE_PROPOSAL"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass(frozen=True, slots=True)
class ManualPaperPriorCheckpointEvidence:
    """Complete non-authorizing retained evidence for one verified prior."""

    kind: VerifiedPriorCheckpointKind
    checkpoint_id: UUID
    sequence: int
    lineage_id: UUID
    account_state_id: UUID
    compact_state: CompactPaperLedgerState
    empty_engine_state_id: UUID
    checkpoint_sha256: str
    checkpoint_byte_length: int

    def __post_init__(self) -> None:
        if type(self.kind) is not VerifiedPriorCheckpointKind:
            raise ManualPaperStrategyPlanValidationError("prior kind is invalid")
        for name in (
            "checkpoint_id",
            "lineage_id",
            "account_state_id",
            "empty_engine_state_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise ManualPaperStrategyPlanValidationError(
                    f"prior {name} must be an exact UUID"
                )
        if type(self.sequence) is not int or self.sequence < 0:
            raise ManualPaperStrategyPlanValidationError(
                "prior sequence must be nonnegative"
            )
        if type(self.compact_state) is not CompactPaperLedgerState:
            raise ManualPaperStrategyPlanValidationError(
                "prior compact_state must be exact"
            )
        if (
            type(self.checkpoint_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.checkpoint_sha256) is None
            or type(self.checkpoint_byte_length) is not int
            or self.checkpoint_byte_length <= 0
        ):
            raise ManualPaperStrategyPlanValidationError(
                "prior artifact evidence is invalid"
            )

    @classmethod
    def from_verified(
        cls, prior: VerifiedPriorCheckpoint
    ) -> ManualPaperPriorCheckpointEvidence:
        """Retain an existing verified-prior contract without minting authority."""
        if type(prior) is not VerifiedPriorCheckpoint:
            raise ManualPaperStrategyPlanValidationError(
                "prior_checkpoint must be an exact VerifiedPriorCheckpoint"
            )
        return cls(
            prior.kind,
            prior.checkpoint_id,
            prior.sequence,
            prior.lineage_id,
            prior.account_state_id,
            prior.compact_state,
            prior.empty_engine_state_id,
            prior.checkpoint_sha256,
            prior.checkpoint_byte_length,
        )


@dataclass(frozen=True, slots=True)
class ManualPaperSelectedC3Assertion:
    """Pure non-authorizing provenance asserted for the selected C3 artifact."""

    selection_id: UUID
    session_id: UUID
    terminal_id: UUID
    snapshot_id: UUID
    artifact_sha256: str
    artifact_byte_length: int

    def __post_init__(self) -> None:
        for name in ("selection_id", "session_id", "terminal_id", "snapshot_id"):
            if type(getattr(self, name)) is not UUID:
                raise ManualPaperStrategyPlanValidationError(
                    f"selected C3 {name} must be an exact UUID"
                )
        if (
            type(self.artifact_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.artifact_sha256) is None
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length <= 0
        ):
            raise ManualPaperStrategyPlanValidationError(
                "selected C3 artifact evidence is invalid"
            )


@dataclass(frozen=True, slots=True)
class ManualPaperStrategyPlanRequest:
    """Complete explicit pure inputs for one strategy plan."""

    snapshot_verification: DailySnapshotVerificationResult
    paper_account_id: str
    selected_c3_assertion: ManualPaperSelectedC3Assertion
    prior_checkpoint: VerifiedPriorCheckpoint
    history_seed: VerifiedStrategyHistorySeed
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: str
    open_reference: CallerAssertedNextSessionOpenReference
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if type(self.snapshot_verification) is not DailySnapshotVerificationResult:
            raise ManualPaperStrategyPlanValidationError(
                "snapshot_verification must be exact"
            )
        _paper_account_id(self.paper_account_id)
        if type(self.selected_c3_assertion) is not ManualPaperSelectedC3Assertion:
            raise ManualPaperStrategyPlanValidationError(
                "selected_c3_assertion must be exact non-authorizing evidence"
            )
        if type(self.prior_checkpoint) is not VerifiedPriorCheckpoint:
            raise ManualPaperStrategyPlanValidationError(
                "prior_checkpoint must use the existing verified-prior contract"
            )
        if type(self.history_seed) is not VerifiedStrategyHistorySeed:
            raise ManualPaperStrategyPlanValidationError(
                "history_seed must be complete verified seed evidence"
            )
        if type(self.strategy_config) is not MovingAverageCrossoverConfig:
            raise ManualPaperStrategyPlanValidationError(
                "strategy_config must be an exact MovingAverageCrossoverConfig"
            )
        _idempotency_key(self.caller_idempotency_key)
        if type(self.open_reference) is not CallerAssertedNextSessionOpenReference:
            raise ManualPaperStrategyPlanValidationError(
                "open_reference must be one exact next-session assertion"
            )
        if type(self.policies) is not VerifiedSnapshotPaperCyclePolicies:
            raise ManualPaperStrategyPlanValidationError("policies must be exact")
        metadata = _metadata(self.metadata)
        if any(
            item.key.startswith(ARCHITECTURE94_METADATA_PREFIX) for item in metadata
        ):
            raise ManualPaperStrategyPlanValidationError(
                "caller/base architecture94. metadata is reserved"
            )
        object.__setattr__(self, "planning_at", _utc(self.planning_at, "planning_at"))
        object.__setattr__(
            self, "submitted_at", _utc(self.submitted_at, "submitted_at")
        )
        object.__setattr__(self, "filled_at", _utc(self.filled_at, "filled_at"))
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class ManualPaperStrategyDecisionRequest:
    """Complete pre-open inputs for one pure strategy decision."""

    snapshot_verification: DailySnapshotVerificationResult
    paper_account_id: str
    selected_c3_assertion: ManualPaperSelectedC3Assertion
    prior_checkpoint: VerifiedPriorCheckpoint
    history_seed: VerifiedStrategyHistorySeed
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: str
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if type(self.snapshot_verification) is not DailySnapshotVerificationResult:
            raise ManualPaperStrategyPlanValidationError(
                "snapshot_verification must be exact"
            )
        _paper_account_id(self.paper_account_id)
        if type(self.selected_c3_assertion) is not ManualPaperSelectedC3Assertion:
            raise ManualPaperStrategyPlanValidationError(
                "selected_c3_assertion must be exact non-authorizing evidence"
            )
        if type(self.prior_checkpoint) is not VerifiedPriorCheckpoint:
            raise ManualPaperStrategyPlanValidationError(
                "prior_checkpoint must use the existing verified-prior contract"
            )
        if type(self.history_seed) is not VerifiedStrategyHistorySeed:
            raise ManualPaperStrategyPlanValidationError(
                "history_seed must be complete verified seed evidence"
            )
        if type(self.strategy_config) is not MovingAverageCrossoverConfig:
            raise ManualPaperStrategyPlanValidationError(
                "strategy_config must be an exact MovingAverageCrossoverConfig"
            )
        _idempotency_key(self.caller_idempotency_key)
        if type(self.policies) is not VerifiedSnapshotPaperCyclePolicies:
            raise ManualPaperStrategyPlanValidationError("policies must be exact")
        metadata = _metadata(self.metadata)
        if any(
            item.key.startswith(ARCHITECTURE94_METADATA_PREFIX) for item in metadata
        ):
            raise ManualPaperStrategyPlanValidationError(
                "caller/base architecture94. metadata is reserved"
            )
        object.__setattr__(self, "planning_at", _utc(self.planning_at, "planning_at"))
        object.__setattr__(
            self, "submitted_at", _utc(self.submitted_at, "submitted_at")
        )
        object.__setattr__(self, "filled_at", _utc(self.filled_at, "filled_at"))
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class PreparedManualPaperStrategyDecision:
    """Immutable pre-open result retained for later verified-open completion."""

    selected_snapshot_artifact: bytes
    snapshot_verification: DailySnapshotVerificationResult
    history_seed_artifact: bytes
    paper_account_id: str
    selected_c3_assertion: ManualPaperSelectedC3Assertion
    prior_checkpoint: ManualPaperPriorCheckpointEvidence
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: str
    policies: VerifiedSnapshotPaperCyclePolicies
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    metadata: tuple[MetadataEntry, ...]
    symbol: Symbol
    selected_session: TradingSession
    intended_execution_session: TradingSession
    strategy_context_material: str
    strategy_run_id: UUID
    strategy_step_index: int
    signal_status: ManualPaperStrategySignalStatus
    strategy_proposal: TradeProposal | None
    target: ExplicitQuantityTargetPortfolio

    def __post_init__(self) -> None:
        if type(self.selected_snapshot_artifact) is not bytes or not (
            self.selected_snapshot_artifact
        ):
            raise ManualPaperStrategyPlanValidationError(
                "prepared selected snapshot artifact must be nonempty bytes"
            )
        if type(self.snapshot_verification) is not DailySnapshotVerificationResult:
            raise ManualPaperStrategyPlanValidationError(
                "prepared snapshot verification must be exact"
            )
        if type(self.history_seed_artifact) is not bytes or not (
            self.history_seed_artifact
        ):
            raise ManualPaperStrategyPlanValidationError(
                "prepared history seed artifact must be nonempty bytes"
            )
        _paper_account_id(self.paper_account_id)
        if type(self.selected_c3_assertion) is not ManualPaperSelectedC3Assertion:
            raise ManualPaperStrategyPlanValidationError(
                "prepared selected C3 assertion must be exact"
            )
        if type(self.prior_checkpoint) is not ManualPaperPriorCheckpointEvidence:
            raise ManualPaperStrategyPlanValidationError(
                "prepared prior checkpoint evidence must be exact"
            )
        if type(self.strategy_config) is not MovingAverageCrossoverConfig:
            raise ManualPaperStrategyPlanValidationError(
                "prepared strategy configuration must be exact"
            )
        _idempotency_key(self.caller_idempotency_key)
        if type(self.policies) is not VerifiedSnapshotPaperCyclePolicies:
            raise ManualPaperStrategyPlanValidationError(
                "prepared policies must be exact"
            )
        metadata = _metadata(self.metadata)
        if any(
            item.key.startswith(ARCHITECTURE94_METADATA_PREFIX) for item in metadata
        ):
            raise ManualPaperStrategyPlanValidationError(
                "prepared architecture94. metadata is reserved"
            )
        if type(self.symbol) is not Symbol:
            raise ManualPaperStrategyPlanValidationError(
                "prepared symbol must be exact"
            )
        if (
            type(self.selected_session) is not TradingSession
            or type(self.intended_execution_session) is not TradingSession
            or self.intended_execution_session <= self.selected_session
        ):
            raise ManualPaperStrategyPlanValidationError(
                "prepared execution session must be later than selected session"
            )
        if (
            type(self.strategy_context_material) is not str
            or not self.strategy_context_material
            or type(self.strategy_run_id) is not UUID
            or type(self.strategy_step_index) is not int
            or self.strategy_step_index < 0
        ):
            raise ManualPaperStrategyPlanValidationError(
                "prepared strategy context evidence is invalid"
            )
        if type(self.signal_status) is not ManualPaperStrategySignalStatus:
            raise ManualPaperStrategyPlanValidationError(
                "prepared strategy signal status is invalid"
            )
        if self.signal_status is ManualPaperStrategySignalStatus.NO_SIGNAL:
            if self.strategy_proposal is not None:
                raise ManualPaperStrategyPlanValidationError(
                    "prepared NO_SIGNAL requires no strategy proposal"
                )
        elif type(self.strategy_proposal) is not TradeProposal:
            raise ManualPaperStrategyPlanValidationError(
                "prepared TRADE_PROPOSAL requires one exact proposal"
            )
        if type(self.target) is not ExplicitQuantityTargetPortfolio:
            raise ManualPaperStrategyPlanValidationError(
                "prepared target must be exact"
            )
        object.__setattr__(self, "planning_at", _utc(self.planning_at, "planning_at"))
        object.__setattr__(
            self, "submitted_at", _utc(self.submitted_at, "submitted_at")
        )
        object.__setattr__(self, "filled_at", _utc(self.filled_at, "filled_at"))
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class ManualPaperStrategyPlan:
    """Canonical pure plan retaining strategy, target, and planner evidence."""

    plan_id: UUID
    selected_snapshot_artifact: bytes
    history_seed_artifact: bytes
    paper_account_id: str
    selected_c3_assertion: ManualPaperSelectedC3Assertion
    prior_checkpoint: ManualPaperPriorCheckpointEvidence
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: str
    strategy_run_id: UUID
    strategy_step_index: int
    signal_status: ManualPaperStrategySignalStatus
    strategy_proposal: TradeProposal | None
    target: ExplicitQuantityTargetPortfolio
    planner_plan_id: UUID
    planner_status: RebalanceStatus
    planner_result_id: UUID
    planner_proposal: TradeProposal | None
    request_core: CheckpointedVerifiedSnapshotPaperCycleRequest
    schema: str = MANUAL_PAPER_STRATEGY_PLAN_SCHEMA

    def __post_init__(self) -> None:
        if type(self.plan_id) is not UUID:
            raise ManualPaperStrategyPlanValidationError(
                "plan_id must be an exact UUID"
            )
        for name in ("selected_snapshot_artifact", "history_seed_artifact"):
            value = getattr(self, name)
            if type(value) is not bytes or not value:
                raise ManualPaperStrategyPlanValidationError(
                    f"{name} must be nonempty exact bytes"
                )
        _paper_account_id(self.paper_account_id)
        if type(self.selected_c3_assertion) is not ManualPaperSelectedC3Assertion:
            raise ManualPaperStrategyPlanValidationError(
                "selected C3 assertion is invalid"
            )
        if type(self.prior_checkpoint) is not ManualPaperPriorCheckpointEvidence:
            raise ManualPaperStrategyPlanValidationError(
                "prior_checkpoint evidence is invalid"
            )
        if type(self.strategy_config) is not MovingAverageCrossoverConfig:
            raise ManualPaperStrategyPlanValidationError("strategy_config is invalid")
        _idempotency_key(self.caller_idempotency_key)
        if type(self.strategy_run_id) is not UUID:
            raise ManualPaperStrategyPlanValidationError("strategy_run_id is invalid")
        if type(self.strategy_step_index) is not int or self.strategy_step_index < 0:
            raise ManualPaperStrategyPlanValidationError(
                "strategy_step_index must be nonnegative"
            )
        if type(self.signal_status) is not ManualPaperStrategySignalStatus:
            raise ManualPaperStrategyPlanValidationError("signal_status is invalid")
        if self.signal_status is ManualPaperStrategySignalStatus.NO_SIGNAL:
            if self.strategy_proposal is not None or self.planner_proposal is not None:
                raise ManualPaperStrategyPlanValidationError(
                    "NO_SIGNAL requires no strategy or planner proposal"
                )
            if self.planner_status is not RebalanceStatus.NO_ACTION:
                raise ManualPaperStrategyPlanValidationError(
                    "NO_SIGNAL requires a no-action planner result"
                )
        elif (
            type(self.strategy_proposal) is not TradeProposal
            or type(self.planner_proposal) is not TradeProposal
        ):
            raise ManualPaperStrategyPlanValidationError(
                "TRADE_PROPOSAL requires exact strategy and planner proposals"
            )
        if type(self.target) is not ExplicitQuantityTargetPortfolio:
            raise ManualPaperStrategyPlanValidationError("target is invalid")
        if (
            type(self.planner_plan_id) is not UUID
            or type(self.planner_result_id) is not UUID
        ):
            raise ManualPaperStrategyPlanValidationError(
                "planner identities must be exact UUIDs"
            )
        if type(self.planner_status) is not RebalanceStatus:
            raise ManualPaperStrategyPlanValidationError("planner_status is invalid")
        if type(self.request_core) is not CheckpointedVerifiedSnapshotPaperCycleRequest:
            raise ManualPaperStrategyPlanValidationError("request_core is invalid")
        _metadata(self.request_core.metadata)
        if self.request_core.target != self.target:
            raise ManualPaperStrategyPlanValidationError(
                "request core target does not match retained target"
            )
        if any(
            item.key.startswith(ARCHITECTURE94_METADATA_PREFIX)
            for item in self.request_core.metadata
        ):
            raise ManualPaperStrategyPlanValidationError(
                "request core must not contain architecture94. metadata"
            )
        if (
            type(self.schema) is not str
            or self.schema != MANUAL_PAPER_STRATEGY_PLAN_SCHEMA
        ):
            raise ManualPaperStrategyPlanValidationError(
                "schema must be manual-paper-strategy-plan/v1"
            )
        if self.plan_id != _plan_id(self):
            raise ManualPaperStrategyPlanValidationError(
                "plan_id does not match complete canonical semantic material"
            )


@dataclass(frozen=True, slots=True)
class ManualPaperStrategyPlanArtifactBinding:
    """Detached artifact evidence plus the exact final existing request."""

    plan: ManualPaperStrategyPlan
    artifact_bytes: bytes
    artifact_sha256: str
    artifact_byte_length: int
    checkpointed_request: CheckpointedVerifiedSnapshotPaperCycleRequest

    def __post_init__(self) -> None:
        if type(self.plan) is not ManualPaperStrategyPlan:
            raise ManualPaperStrategyPlanVerificationError("bound plan is invalid")
        if type(self.artifact_bytes) is not bytes or not self.artifact_bytes:
            raise ManualPaperStrategyPlanVerificationError(
                "artifact_bytes must be nonempty exact bytes"
            )
        if (
            type(self.artifact_sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.artifact_sha256) is None
            or self.artifact_sha256 != sha256(self.artifact_bytes).hexdigest()
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length != len(self.artifact_bytes)
            or self.artifact_byte_length <= 0
        ):
            raise ManualPaperStrategyPlanVerificationError(
                "detached artifact evidence does not match canonical plan bytes"
            )
        if serialize_manual_paper_strategy_plan(self.plan) != self.artifact_bytes:
            raise ManualPaperStrategyPlanVerificationError(
                "artifact bytes do not serialize the retained plan"
            )
        expected = _final_checkpointed_request(
            self.plan, self.artifact_sha256, self.artifact_byte_length
        )
        if self.checkpointed_request != expected:
            raise ManualPaperStrategyPlanVerificationError(
                "checkpointed request does not match frozen metadata injection"
            )


def build_manual_paper_strategy_plan(
    request: ManualPaperStrategyPlanRequest,
    calendar: IdentifiedMarketCalendar,
) -> ManualPaperStrategyPlanArtifactBinding:
    """Compatibility builder for existing supervised/manual callers."""
    if type(request) is not ManualPaperStrategyPlanRequest:
        raise ManualPaperStrategyPlanValidationError(
            "request must be an exact ManualPaperStrategyPlanRequest"
        )
    prepared = build_manual_paper_strategy_decision(
        ManualPaperStrategyDecisionRequest(
            request.snapshot_verification,
            request.paper_account_id,
            request.selected_c3_assertion,
            request.prior_checkpoint,
            request.history_seed,
            request.strategy_config,
            request.caller_idempotency_key,
            request.policies,
            request.planning_at,
            request.submitted_at,
            request.filled_at,
            request.metadata,
        ),
        calendar,
    )
    return _complete_prepared_manual_paper_strategy_decision(
        prepared, request.open_reference, calendar
    )


def build_manual_paper_strategy_decision(
    request: ManualPaperStrategyDecisionRequest,
    calendar: IdentifiedMarketCalendar,
) -> PreparedManualPaperStrategyDecision:
    """Perform the complete deterministic pre-open strategy decision phase."""
    if type(request) is not ManualPaperStrategyDecisionRequest:
        raise ManualPaperStrategyPlanValidationError(
            "request must be an exact ManualPaperStrategyDecisionRequest"
        )
    verification = request.snapshot_verification
    if (
        verification.status is not DailySnapshotVerificationStatus.PASS
        or verification.snapshot is None
        or verification.diagnostics
    ):
        raise ManualPaperStrategyPlanValidationError(
            "strategy planning requires one complete PASS snapshot verification"
        )
    snapshot_payload = serialize_daily_snapshot(verification.snapshot)
    if (
        sha256(snapshot_payload).hexdigest() != verification.sha256
        or len(snapshot_payload) != verification.byte_length
    ):
        raise ManualPaperStrategyPlanValidationError(
            "snapshot verification does not match its canonical artifact"
        )
    replayed_snapshot = verify_daily_snapshot(
        snapshot_payload,
        calendar,
        expected_sha256=verification.sha256,
        expected_byte_length=verification.byte_length,
    )
    if replayed_snapshot.status is not DailySnapshotVerificationStatus.PASS:
        raise ManualPaperStrategyPlanValidationError(
            "snapshot cannot be replayed under the supplied XNYS calendar"
        )
    _require_c3_snapshot_match(request.selected_c3_assertion, replayed_snapshot)
    seed_payload = serialize_strategy_history_seed(request.history_seed.seed)
    if (
        sha256(seed_payload).hexdigest() != request.history_seed.artifact_sha256
        or len(seed_payload) != request.history_seed.artifact_byte_length
        or request.history_seed.strategy_config != request.strategy_config
    ):
        raise ManualPaperStrategyPlanValidationError(
            "verified history seed evidence does not match the requested plan"
        )
    prior = ManualPaperPriorCheckpointEvidence.from_verified(request.prior_checkpoint)
    return _prepare_decision_from_evidence(
        snapshot_payload=snapshot_payload,
        snapshot_verification=replayed_snapshot,
        seed_payload=seed_payload,
        paper_account_id=request.paper_account_id,
        selected_c3_assertion=request.selected_c3_assertion,
        prior=prior,
        strategy_config=request.strategy_config,
        caller_idempotency_key=request.caller_idempotency_key,
        policies=request.policies,
        planning_at=request.planning_at,
        submitted_at=request.submitted_at,
        filled_at=request.filled_at,
        metadata=request.metadata,
        calendar=calendar,
    )


def complete_manual_paper_strategy_plan(
    prepared_decision: PreparedManualPaperStrategyDecision,
    verified_open_binding: C3VerifiedDailyBarOpenBinding,
    calendar: IdentifiedMarketCalendar,
) -> ManualPaperStrategyPlanArtifactBinding:
    """Complete one prepared decision from an exact production C3 open proof."""
    if type(prepared_decision) is not PreparedManualPaperStrategyDecision:
        raise ManualPaperStrategyPlanValidationError(
            "prepared_decision must be an exact PreparedManualPaperStrategyDecision"
        )
    try:
        binding = require_c3_verified_daily_bar_open_binding(verified_open_binding)
    except C3VerifiedDailyBarOpenBindingError as error:
        raise ManualPaperStrategyPlanValidationError(
            "execution-session C3 open binding provenance is invalid"
        ) from error
    if binding.symbol != prepared_decision.symbol:
        raise ManualPaperStrategyPlanValidationError(
            "execution-session C3 open binding symbol does not match decision"
        )
    if binding.session != prepared_decision.intended_execution_session:
        raise ManualPaperStrategyPlanValidationError(
            "execution-session C3 open binding session does not match decision"
        )
    open_reference = CallerAssertedNextSessionOpenReference(
        binding.symbol,
        binding.session,
        binding.open_price,
    )
    return _complete_prepared_manual_paper_strategy_decision(
        prepared_decision, open_reference, calendar
    )


def serialize_manual_paper_strategy_plan(plan: ManualPaperStrategyPlan) -> bytes:
    """Serialize the semantic request core without self-hash fields."""
    if type(plan) is not ManualPaperStrategyPlan:
        raise ManualPaperStrategyPlanSerializationError(
            "plan must be an exact ManualPaperStrategyPlan"
        )
    payload = _canonical_json_bytes(_plan_tree(plan, include_plan_id=True))
    if len(payload) > MAX_MANUAL_PAPER_STRATEGY_PLAN_BYTES:
        raise ManualPaperStrategyPlanSerializationError(
            "serialized strategy plan exceeds the 8 MiB limit"
        )
    return payload


def parse_manual_paper_strategy_plan(payload: bytes) -> ManualPaperStrategyPlan:
    """Strictly parse canonical plan bytes without running a paper cycle."""
    root = _object(_load_json(payload), _ROOT_FIELDS, "root")
    config_raw = _object(root["strategy_config"], _CONFIG_FIELDS, "strategy_config")
    context_raw = _object(root["strategy_context"], _CONTEXT_FIELDS, "strategy_context")
    strategy_raw = _object(root["strategy_result"], _RESULT_FIELDS, "strategy_result")
    planner_raw = _object(root["planner_result"], _PLANNER_FIELDS, "planner_result")
    c3_raw = _object(
        root["selected_c3_assertion"],
        _SELECTED_C3_ASSERTION_FIELDS,
        "selected_c3_assertion",
    )
    try:
        config = MovingAverageCrossoverConfig(
            _integer(config_raw["short_window"], "strategy_config.short_window"),
            _integer(config_raw["long_window"], "strategy_config.long_window"),
            _decimal(
                config_raw["desired_quantity"],
                "strategy_config.desired_quantity",
            ),
        )
        plan = ManualPaperStrategyPlan(
            _uuid(root["plan_id"], "plan_id"),
            _utf8_artifact(
                root["selected_snapshot_artifact_utf8"],
                "selected_snapshot_artifact_utf8",
            ),
            _utf8_artifact(
                root["history_seed_artifact_utf8"],
                "history_seed_artifact_utf8",
            ),
            _paper_account_id(root["paper_account_id"]),
            ManualPaperSelectedC3Assertion(
                _uuid(
                    c3_raw["selection_id"],
                    "selected_c3_assertion.selection_id",
                ),
                _uuid(c3_raw["session_id"], "selected_c3_assertion.session_id"),
                _uuid(c3_raw["terminal_id"], "selected_c3_assertion.terminal_id"),
                _uuid(c3_raw["snapshot_id"], "selected_c3_assertion.snapshot_id"),
                _sha(
                    c3_raw["artifact_sha256"],
                    "selected_c3_assertion.artifact_sha256",
                ),
                _positive_integer(
                    c3_raw["artifact_byte_length"],
                    "selected_c3_assertion.artifact_byte_length",
                ),
            ),
            _prior(root["prior_checkpoint"]),
            config,
            _idempotency_key(root["caller_idempotency_key"]),
            _uuid(context_raw["run_id"], "strategy_context.run_id"),
            _nonnegative_integer(
                context_raw["step_index"], "strategy_context.step_index"
            ),
            _enum(
                strategy_raw["status"],
                ManualPaperStrategySignalStatus,
                "strategy_result.status",
            ),
            _optional_proposal(strategy_raw["proposal"], "strategy_result.proposal"),
            _target(root["target"]),
            _uuid(planner_raw["plan_id"], "planner_result.plan_id"),
            _enum(planner_raw["status"], RebalanceStatus, "planner_result.status"),
            _uuid(planner_raw["result_id"], "planner_result.result_id"),
            _optional_proposal(planner_raw["proposal"], "planner_result.proposal"),
            parse_checkpointed_verified_snapshot_paper_cycle_request(
                _utf8_artifact(root["request_core_utf8"], "request_core_utf8")
            ),
            _string(root["schema"], "schema"),
        )
    except ManualPaperStrategyPlanError:
        raise
    except Exception as error:
        raise ManualPaperStrategyPlanSerializationError(
            "retained plan model does not reconcile"
        ) from error
    if serialize_manual_paper_strategy_plan(plan) != payload:
        raise ManualPaperStrategyPlanSerializationError(
            "plan bytes are not the canonical representation"
        )
    return plan


def verify_manual_paper_strategy_plan(
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
    *,
    expected_sha256: str | None = None,
    expected_byte_length: int | None = None,
    expected_checkpointed_request: (
        CheckpointedVerifiedSnapshotPaperCycleRequest | None
    ) = None,
) -> ManualPaperStrategyPlanArtifactBinding:
    """Purely replay a plan and verify detached evidence and final request."""
    _expected_sha(expected_sha256)
    _expected_length(expected_byte_length)
    actual_sha = sha256(payload).hexdigest() if type(payload) is bytes else ""
    actual_length = len(payload) if type(payload) is bytes else -1
    if expected_sha256 is not None and actual_sha != expected_sha256:
        raise ManualPaperStrategyPlanVerificationError(
            "plan artifact SHA-256 does not match expected detached evidence"
        )
    if expected_byte_length is not None and actual_length != expected_byte_length:
        raise ManualPaperStrategyPlanVerificationError(
            "plan artifact byte length does not match expected detached evidence"
        )
    plan = parse_manual_paper_strategy_plan(payload)
    try:
        replayed = _replay_plan(plan, calendar)
    except ManualPaperStrategyPlanValidationError as error:
        raise ManualPaperStrategyPlanVerificationError(
            "retained strategy-plan evidence failed replay validation"
        ) from error
    if replayed.plan != plan or replayed.artifact_bytes != payload:
        raise ManualPaperStrategyPlanVerificationError(
            "pure strategy-plan replay differs from retained semantic material"
        )
    if expected_checkpointed_request is not None and (
        type(expected_checkpointed_request)
        is not CheckpointedVerifiedSnapshotPaperCycleRequest
        or replayed.checkpointed_request != expected_checkpointed_request
    ):
        raise ManualPaperStrategyPlanVerificationError(
            "injected checkpointed request or metadata order does not match"
        )
    return replayed


def _replay_plan(
    plan: ManualPaperStrategyPlan,
    calendar: IdentifiedMarketCalendar,
) -> ManualPaperStrategyPlanArtifactBinding:
    snapshot = verify_daily_snapshot(plan.selected_snapshot_artifact, calendar)
    if snapshot.status is not DailySnapshotVerificationStatus.PASS:
        raise ManualPaperStrategyPlanVerificationError(
            "embedded selected snapshot artifact does not verify"
        )
    request = plan.request_core
    if (
        request.snapshot_reference.artifact_sha256 != snapshot.sha256
        or request.snapshot_reference.artifact_byte_length != snapshot.byte_length
        or snapshot.snapshot is None
        or request.snapshot_reference.snapshot_id != snapshot.snapshot.snapshot_id
    ):
        raise ManualPaperStrategyPlanVerificationError(
            "selected snapshot artifact and request core do not reconcile"
        )
    rebuilt = _build_from_evidence(
        snapshot_payload=plan.selected_snapshot_artifact,
        snapshot_verification=snapshot,
        seed_payload=plan.history_seed_artifact,
        paper_account_id=plan.paper_account_id,
        selected_c3_assertion=plan.selected_c3_assertion,
        prior=plan.prior_checkpoint,
        strategy_config=plan.strategy_config,
        caller_idempotency_key=plan.caller_idempotency_key,
        open_reference=request.open_references[0],
        policies=request.policies,
        planning_at=request.planning_at,
        submitted_at=request.submitted_at,
        filled_at=request.filled_at,
        metadata=request.metadata,
        calendar=calendar,
    )
    return rebuilt


def _build_from_evidence(
    *,
    snapshot_payload: bytes,
    snapshot_verification: DailySnapshotVerificationResult,
    seed_payload: bytes,
    paper_account_id: str,
    selected_c3_assertion: ManualPaperSelectedC3Assertion,
    prior: ManualPaperPriorCheckpointEvidence,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: str,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...],
    calendar: IdentifiedMarketCalendar,
) -> ManualPaperStrategyPlanArtifactBinding:
    prepared = _prepare_decision_from_evidence(
        snapshot_payload=snapshot_payload,
        snapshot_verification=snapshot_verification,
        seed_payload=seed_payload,
        paper_account_id=paper_account_id,
        selected_c3_assertion=selected_c3_assertion,
        prior=prior,
        strategy_config=strategy_config,
        caller_idempotency_key=caller_idempotency_key,
        policies=policies,
        planning_at=planning_at,
        submitted_at=submitted_at,
        filled_at=filled_at,
        metadata=metadata,
        calendar=calendar,
    )
    return _complete_prepared_manual_paper_strategy_decision(
        prepared, open_reference, calendar
    )


def _prepare_decision_from_evidence(
    *,
    snapshot_payload: bytes,
    snapshot_verification: DailySnapshotVerificationResult,
    seed_payload: bytes,
    paper_account_id: str,
    selected_c3_assertion: ManualPaperSelectedC3Assertion,
    prior: ManualPaperPriorCheckpointEvidence,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: str,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...],
    calendar: IdentifiedMarketCalendar,
) -> PreparedManualPaperStrategyDecision:
    _paper_account_id(paper_account_id)
    _require_c3_snapshot_match(selected_c3_assertion, snapshot_verification)
    try:
        replay = replay_verified_daily_snapshot(snapshot_verification)
    except Exception as error:
        raise ManualPaperStrategyPlanValidationError(
            "selected snapshot replay failed"
        ) from error
    if len(replay.symbols) != 1 or len(replay.bars) != 1:
        raise ManualPaperStrategyPlanValidationError(
            "Architecture 94 P1 supports exactly one snapshot symbol"
        )
    symbol = replay.symbols[0]
    current = replay.bars[0]
    if current.bar.symbol != symbol or current.session != replay.target_session:
        raise ManualPaperStrategyPlanValidationError(
            "selected snapshot current bar does not reconcile"
        )
    try:
        verified_seed = verify_strategy_history_seed(
            seed_payload,
            expected_symbol=symbol,
            target_session=replay.target_session,
            strategy_config=strategy_config,
            calendar=calendar,
        )
    except StrategyHistorySeedVerificationError as error:
        raise ManualPaperStrategyPlanValidationError(
            "history seed is invalid for the selected strategy target"
        ) from error
    if any(item.symbol != symbol for item in prior.compact_state.positions):
        raise ManualPaperStrategyPlanValidationError(
            "verified prior contains a symbol outside the one-symbol plan"
        )
    _idempotency_key(caller_idempotency_key)
    retained_metadata = _metadata(metadata)
    if any(
        item.key.startswith(ARCHITECTURE94_METADATA_PREFIX)
        for item in retained_metadata
    ):
        raise ManualPaperStrategyPlanValidationError(
            "caller/base architecture94. metadata is reserved"
        )
    if type(policies) is not VerifiedSnapshotPaperCyclePolicies:
        raise ManualPaperStrategyPlanValidationError("policies must be exact")
    normalized_planning = _utc(planning_at, "planning_at")
    normalized_submitted = _utc(submitted_at, "submitted_at")
    normalized_filled = _utc(filled_at, "filled_at")

    context_material = _context_material(
        snapshot_payload,
        seed_payload,
        prior,
        strategy_config,
        caller_idempotency_key,
    )
    run_id = uuid5(MANUAL_PAPER_STRATEGY_CONTEXT_NAMESPACE, context_material)
    step_index = prior.sequence
    context = _strategy_context(
        run_id,
        step_index,
        current.bar,
        replay.target_session,
        verified_seed.seed.bars,
        prior.compact_state,
    )
    # Architecture 94 requires exactly one existing strategy evaluation per plan.
    strategy_proposal = MovingAverageCrossoverStrategy(strategy_config).evaluate(
        context
    )
    signal_status = (
        ManualPaperStrategySignalStatus.NO_SIGNAL
        if strategy_proposal is None
        else ManualPaperStrategySignalStatus.TRADE_PROPOSAL
    )
    target = _bridge_target(
        symbol,
        current.bar.close,
        prior.compact_state,
        strategy_proposal,
        context_material,
    )
    intended_execution_session = _derive_intended_execution_session(
        replay.target_session
    )
    _validate_prepared_chronology(
        prior.compact_state.as_of,
        snapshot_verification.snapshot.audit.captured_at,
        normalized_planning,
        normalized_submitted,
        normalized_filled,
        intended_execution_session,
        snapshot_verification,
    )
    return PreparedManualPaperStrategyDecision(
        snapshot_payload,
        snapshot_verification,
        seed_payload,
        paper_account_id,
        selected_c3_assertion,
        prior,
        strategy_config,
        caller_idempotency_key,
        policies,
        normalized_planning,
        normalized_submitted,
        normalized_filled,
        retained_metadata,
        symbol,
        replay.target_session,
        intended_execution_session,
        context_material,
        run_id,
        step_index,
        signal_status,
        strategy_proposal,
        target,
    )


def _complete_prepared_manual_paper_strategy_decision(
    prepared_decision: PreparedManualPaperStrategyDecision,
    open_reference: CallerAssertedNextSessionOpenReference,
    calendar: IdentifiedMarketCalendar,
) -> ManualPaperStrategyPlanArtifactBinding:
    if type(prepared_decision) is not PreparedManualPaperStrategyDecision:
        raise ManualPaperStrategyPlanValidationError("prepared_decision must be exact")
    if (
        type(open_reference) is not CallerAssertedNextSessionOpenReference
        or open_reference.symbol != prepared_decision.symbol
        or open_reference.session != prepared_decision.intended_execution_session
    ):
        raise ManualPaperStrategyPlanValidationError(
            "one exact intended-session same-symbol open reference is required"
        )
    context_material = prepared_decision.strategy_context_material
    paper_account_id = prepared_decision.paper_account_id
    selected_c3_assertion = prepared_decision.selected_c3_assertion
    target = prepared_decision.target
    policies = prepared_decision.policies
    normalized_planning = prepared_decision.planning_at
    normalized_submitted = prepared_decision.submitted_at
    normalized_filled = prepared_decision.filled_at
    retained_metadata = prepared_decision.metadata
    request_id = _checkpointed_request_id(
        context_material,
        paper_account_id,
        selected_c3_assertion,
        target,
        open_reference,
        policies,
        normalized_planning,
        normalized_submitted,
        normalized_filled,
        retained_metadata,
    )
    snapshot_reference = VerifiedDailySnapshotReference(
        prepared_decision.snapshot_verification.snapshot.snapshot_id,
        prepared_decision.snapshot_verification.sha256,
        prepared_decision.snapshot_verification.byte_length,
    )
    request_core = CheckpointedVerifiedSnapshotPaperCycleRequest(
        request_id,
        snapshot_reference,
        target,
        (open_reference,),
        policies,
        normalized_planning,
        normalized_submitted,
        normalized_filled,
        retained_metadata,
    )
    account_state = _verified_account_state(prepared_decision.prior_checkpoint)
    try:
        prepared = prepare_verified_snapshot_paper_cycle(
            VerifiedSnapshotPaperCyclePreparationRequest(
                request_id,
                snapshot_reference,
                account_state,
                target,
                (open_reference,),
                policies,
                normalized_planning,
                normalized_submitted,
                normalized_filled,
                retained_metadata,
            ),
            prepared_decision.snapshot_verification,
            calendar,
        )
        plan = RebalancePlanner().plan(prepared.planner_request)
        proposal_result = RebalanceProposalFactory().create(
            RebalanceProposalRequest(
                request_id,
                plan,
                normalized_planning,
                policies.proposal_policy,
                policies.proposal_confidence,
                retained_metadata,
            )
        )
    except Exception as error:
        raise ManualPaperStrategyPlanValidationError(
            "existing preparation/planner/proposal path rejected the exact target"
        ) from error
    planner_proposal = _reconcile_proposals(
        prepared_decision.symbol,
        prepared_decision.strategy_proposal,
        plan.status,
        proposal_result.status,
        proposal_result.proposals,
    )
    values = _PlanValues(
        prepared_decision.selected_snapshot_artifact,
        prepared_decision.history_seed_artifact,
        paper_account_id,
        selected_c3_assertion,
        prepared_decision.prior_checkpoint,
        prepared_decision.strategy_config,
        prepared_decision.caller_idempotency_key,
        prepared_decision.strategy_run_id,
        prepared_decision.strategy_step_index,
        prepared_decision.signal_status,
        prepared_decision.strategy_proposal,
        target,
        plan.plan_id,
        plan.status,
        proposal_result.result_id,
        planner_proposal,
        request_core,
    )
    built = ManualPaperStrategyPlan(
        _plan_id(values),
        values.selected_snapshot_artifact,
        values.history_seed_artifact,
        values.paper_account_id,
        values.selected_c3_assertion,
        values.prior_checkpoint,
        values.strategy_config,
        values.caller_idempotency_key,
        values.strategy_run_id,
        values.strategy_step_index,
        values.signal_status,
        values.strategy_proposal,
        values.target,
        values.planner_plan_id,
        values.planner_status,
        values.planner_result_id,
        values.planner_proposal,
        values.request_core,
    )
    artifact = serialize_manual_paper_strategy_plan(built)
    digest = sha256(artifact).hexdigest()
    length = len(artifact)
    final_request = _final_checkpointed_request(
        built,
        digest,
        length,
        error_type=ManualPaperStrategyPlanValidationError,
    )
    return ManualPaperStrategyPlanArtifactBinding(
        built,
        artifact,
        digest,
        length,
        final_request,
    )


@dataclass(frozen=True, slots=True)
class _PlanValues:
    selected_snapshot_artifact: bytes
    history_seed_artifact: bytes
    paper_account_id: str
    selected_c3_assertion: ManualPaperSelectedC3Assertion
    prior_checkpoint: ManualPaperPriorCheckpointEvidence
    strategy_config: MovingAverageCrossoverConfig
    caller_idempotency_key: str
    strategy_run_id: UUID
    strategy_step_index: int
    signal_status: ManualPaperStrategySignalStatus
    strategy_proposal: TradeProposal | None
    target: ExplicitQuantityTargetPortfolio
    planner_plan_id: UUID
    planner_status: RebalanceStatus
    planner_result_id: UUID
    planner_proposal: TradeProposal | None
    request_core: CheckpointedVerifiedSnapshotPaperCycleRequest


def _derive_intended_execution_session(
    selected_session: TradingSession,
) -> TradingSession:
    try:
        return next_xnys_execution_session(selected_session)
    except PersonalDesktopUnattendedDailyCycleTimingError as error:
        raise ManualPaperStrategyPlanValidationError(
            "intended execution session cannot be derived"
        ) from error


def _validate_prepared_chronology(
    account_as_of: datetime,
    captured_at: datetime,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    intended_execution_session: TradingSession,
    snapshot_verification: DailySnapshotVerificationResult,
) -> None:
    if not (account_as_of <= captured_at <= planning_at <= submitted_at <= filled_at):
        raise ManualPaperStrategyPlanValidationError(
            "timestamps must satisfy account <= capture <= plan <= submit <= fill"
        )
    snapshot = snapshot_verification.snapshot
    if snapshot is None:
        raise ManualPaperStrategyPlanValidationError(
            "selected snapshot is unavailable for chronology validation"
        )
    try:
        filled_session_date = filled_at.astimezone(
            ZoneInfo(snapshot.request.calendar.exchange_timezone)
        ).date()
    except ZoneInfoNotFoundError as error:
        raise ManualPaperStrategyPlanValidationError(
            "intended execution timezone cannot be loaded"
        ) from error
    if filled_session_date != intended_execution_session.session_date:
        raise ManualPaperStrategyPlanValidationError(
            "filled_at must name the intended execution session"
        )


def _strategy_context(
    run_id: UUID,
    step_index: int,
    current_bar,
    target_session,
    seed_bars,
    compact: CompactPaperLedgerState,
) -> BacktestContext:
    positions = {
        item.symbol: Position(item.symbol, item.quantity, item.average_cost)
        for item in compact.positions
    }
    with localcontext(_ARITHMETIC_CONTEXT):
        market_value = sum(
            (item.quantity * current_bar.close for item in compact.positions),
            start=_ZERO,
        )
        unrealized = sum(
            (
                (current_bar.close - item.average_cost) * item.quantity
                for item in compact.positions
            ),
            start=_ZERO,
        )
        equity = compact.cash + market_value
    if equity <= _ZERO:
        raise ManualPaperStrategyPlanValidationError(
            "verified marked account equity must be positive"
        )
    account = AccountSnapshot(
        current_bar.timestamp,
        compact.cash,
        market_value,
        equity,
        compact.cash,
        compact.realized_profit_loss,
        unrealized,
    )
    history = tuple(item.bar for item in seed_bars) + (current_bar,)
    return BacktestContext(
        run_id,
        step_index,
        target_session,
        current_bar,
        history,
        account,
        MappingProxyType(positions),
    )


def _bridge_target(
    symbol: Symbol,
    selected_close: Decimal,
    compact: CompactPaperLedgerState,
    proposal: TradeProposal | None,
    context_material: str,
) -> ExplicitQuantityTargetPortfolio:
    current_quantity = compact.positions[0].quantity if compact.positions else _ZERO
    with localcontext(_ARITHMETIC_CONTEXT):
        marked_equity = compact.cash + current_quantity * selected_close
        if proposal is None:
            target_quantity = current_quantity
        elif proposal.symbol != symbol:
            raise ManualPaperStrategyPlanValidationError(
                "strategy proposal symbol is outside the one-symbol plan"
            )
        elif proposal.side is OrderSide.BUY:
            target_quantity = proposal.desired_quantity
        elif proposal.side is OrderSide.SELL:
            target_quantity = _ZERO
        else:
            raise ManualPaperStrategyPlanValidationError(
                "strategy proposal side is unsupported"
            )
        target_cash = marked_equity - target_quantity * selected_close
    if (
        not marked_equity.is_finite()
        or marked_equity <= _ZERO
        or not target_cash.is_finite()
        or target_cash < _ZERO
        or target_cash + target_quantity * selected_close != marked_equity
    ):
        raise ManualPaperStrategyPlanValidationError(
            "strategy quantity cannot be expressed as an exact long-only target"
        )
    signal = "NO_SIGNAL" if proposal is None else str(proposal.proposal_id)
    target_id = uuid5(
        MANUAL_PAPER_TARGET_NAMESPACE,
        _framed_material(
            (
                MANUAL_PAPER_TARGET_MATERIAL_VERSION,
                context_material,
                str(symbol),
                canonical_decimal(selected_close),
                canonical_decimal(marked_equity),
                canonical_decimal(target_quantity),
                canonical_decimal(target_cash),
                signal,
            )
        ),
    )
    return ExplicitQuantityTargetPortfolio(
        target_id,
        (ExplicitQuantityTarget(symbol, target_quantity),),
        target_cash,
    )


def _reconcile_proposals(
    symbol: Symbol,
    strategy: TradeProposal | None,
    planner_status: RebalanceStatus,
    proposal_status: RebalanceProposalStatus,
    proposals: tuple[TradeProposal, ...],
) -> TradeProposal | None:
    if strategy is None:
        if (
            planner_status is not RebalanceStatus.NO_ACTION
            or proposal_status is not RebalanceProposalStatus.NO_ACTION
            or proposals
        ):
            raise ManualPaperStrategyPlanValidationError(
                "NO_SIGNAL must produce exact no-action planner evidence"
            )
        return None
    if proposal_status is not RebalanceProposalStatus.CREATED or len(proposals) != 1:
        raise ManualPaperStrategyPlanValidationError(
            "one strategy signal must produce exactly one planner proposal"
        )
    planner = proposals[0]
    if (
        planner.symbol != symbol
        or planner.symbol != strategy.symbol
        or planner.side is not strategy.side
        or planner.desired_quantity != strategy.desired_quantity
    ):
        raise ManualPaperStrategyPlanValidationError(
            "planner proposal does not exactly match strategy symbol/side/quantity"
        )
    return planner


def _verified_account_state(
    prior: ManualPaperPriorCheckpointEvidence,
) -> VerifiedSnapshotAccountState:
    compact = prior.compact_state
    return VerifiedSnapshotAccountState(
        prior.account_state_id,
        compact.as_of,
        compact.cash,
        tuple(
            VerifiedSnapshotAccountPosition(
                item.symbol, item.quantity, item.average_cost
            )
            for item in compact.positions
        ),
    )


def _context_material(
    snapshot_payload: bytes,
    seed_payload: bytes,
    prior: ManualPaperPriorCheckpointEvidence,
    config: MovingAverageCrossoverConfig,
    caller_key: str,
) -> str:
    return _framed_material(
        (
            MANUAL_PAPER_STRATEGY_CONTEXT_MATERIAL_VERSION,
            snapshot_payload.decode("utf-8"),
            seed_payload.decode("utf-8"),
            _canonical_json_bytes(_prior_tree(prior)).decode("utf-8"),
            str(config.short_window),
            str(config.long_window),
            canonical_decimal(config.desired_quantity),
            caller_key,
        )
    )


def _checkpointed_request_id(
    context_material: str,
    paper_account_id: str,
    selected_c3_assertion: ManualPaperSelectedC3Assertion,
    target: ExplicitQuantityTargetPortfolio,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...],
) -> UUID:
    # A temporary exact request gives the accepted serializer ownership of all
    # policy/timestamp/metadata canonicalization before deriving the final ID.
    provisional = CheckpointedVerifiedSnapshotPaperCycleRequest(
        UUID(int=0),
        VerifiedDailySnapshotReference(UUID(int=0), "0" * 64, 1),
        target,
        (open_reference,),
        policies,
        planning_at,
        submitted_at,
        filled_at,
        metadata,
    )
    material = _framed_material(
        (
            MANUAL_PAPER_CHECKPOINTED_REQUEST_MATERIAL_VERSION,
            context_material,
            paper_account_id,
            _canonical_json_bytes(
                _selected_c3_assertion_tree(selected_c3_assertion)
            ).decode("utf-8"),
            serialize_checkpointed_verified_snapshot_paper_cycle_request(
                provisional
            ).decode("utf-8"),
        )
    )
    return uuid5(MANUAL_PAPER_CHECKPOINTED_REQUEST_NAMESPACE, material)


def _plan_id(plan: ManualPaperStrategyPlan | _PlanValues) -> UUID:
    semantic = _canonical_json_bytes(_plan_tree(plan, include_plan_id=False)).decode(
        "utf-8"
    )
    return uuid5(
        MANUAL_PAPER_STRATEGY_PLAN_NAMESPACE,
        _framed_material(
            (MANUAL_PAPER_STRATEGY_PLAN_IDENTITY_MATERIAL_VERSION, semantic)
        ),
    )


def _final_checkpointed_request(
    plan: ManualPaperStrategyPlan,
    artifact_sha256: str,
    artifact_byte_length: int,
    *,
    error_type: type[
        ManualPaperStrategyPlanValidationError
        | ManualPaperStrategyPlanVerificationError
    ] = ManualPaperStrategyPlanVerificationError,
) -> CheckpointedVerifiedSnapshotPaperCycleRequest:
    if _SHA256_PATTERN.fullmatch(artifact_sha256) is None:
        raise error_type("plan artifact SHA-256 is invalid")
    if type(artifact_byte_length) is not int or artifact_byte_length <= 0:
        raise error_type("plan artifact byte length must be positive")
    core = plan.request_core
    metadata = core.metadata + (
        MetadataEntry(ARCHITECTURE94_STRATEGY_PLAN_ID_METADATA_KEY, str(plan.plan_id)),
        MetadataEntry(
            ARCHITECTURE94_STRATEGY_PLAN_SHA256_METADATA_KEY, artifact_sha256
        ),
        MetadataEntry(
            ARCHITECTURE94_STRATEGY_PLAN_BYTE_LENGTH_METADATA_KEY,
            str(artifact_byte_length),
        ),
    )
    try:
        request = CheckpointedVerifiedSnapshotPaperCycleRequest(
            core.request_id,
            core.snapshot_reference,
            core.target,
            core.open_references,
            core.policies,
            core.planning_at,
            core.submitted_at,
            core.filled_at,
            metadata,
        )
        payload = serialize_checkpointed_verified_snapshot_paper_cycle_request(request)
        parsed = parse_checkpointed_verified_snapshot_paper_cycle_request(payload)
    except Exception as error:
        raise error_type(
            "final checkpointed request is incompatible with the existing schema"
        ) from error
    if parsed != request:
        raise error_type(
            "final checkpointed request does not round-trip through the existing schema"
        )
    return request


def _plan_tree(
    plan: ManualPaperStrategyPlan | _PlanValues,
    *,
    include_plan_id: bool,
) -> dict[str, object]:
    tree: dict[str, object] = {
        "caller_idempotency_key": plan.caller_idempotency_key,
        "history_seed_artifact_utf8": plan.history_seed_artifact.decode("utf-8"),
        "paper_account_id": plan.paper_account_id,
        "planner_result": {
            "plan_id": str(plan.planner_plan_id),
            "proposal": _proposal_tree(plan.planner_proposal),
            "result_id": str(plan.planner_result_id),
            "status": plan.planner_status.value,
        },
        "prior_checkpoint": _prior_tree(plan.prior_checkpoint),
        "request_core_utf8": (
            serialize_checkpointed_verified_snapshot_paper_cycle_request(
                plan.request_core
            ).decode("utf-8")
        ),
        "schema": MANUAL_PAPER_STRATEGY_PLAN_SCHEMA,
        "selected_snapshot_artifact_utf8": (
            plan.selected_snapshot_artifact.decode("utf-8")
        ),
        "selected_c3_assertion": _selected_c3_assertion_tree(
            plan.selected_c3_assertion
        ),
        "strategy_config": {
            "desired_quantity": canonical_decimal(
                plan.strategy_config.desired_quantity
            ),
            "long_window": plan.strategy_config.long_window,
            "short_window": plan.strategy_config.short_window,
        },
        "strategy_context": {
            "run_id": str(plan.strategy_run_id),
            "step_index": plan.strategy_step_index,
        },
        "strategy_result": {
            "proposal": _proposal_tree(plan.strategy_proposal),
            "status": plan.signal_status.value,
        },
        "target": _target_tree(plan.target),
    }
    if include_plan_id:
        if type(plan) is not ManualPaperStrategyPlan:
            raise ManualPaperStrategyPlanSerializationError(
                "plan_id is unavailable from provisional values"
            )
        tree["plan_id"] = str(plan.plan_id)
    return tree


def _selected_c3_assertion_tree(
    assertion: ManualPaperSelectedC3Assertion,
) -> dict[str, object]:
    return {
        "artifact_byte_length": assertion.artifact_byte_length,
        "artifact_sha256": assertion.artifact_sha256,
        "selection_id": str(assertion.selection_id),
        "session_id": str(assertion.session_id),
        "snapshot_id": str(assertion.snapshot_id),
        "terminal_id": str(assertion.terminal_id),
    }


def _prior_tree(prior: ManualPaperPriorCheckpointEvidence) -> dict[str, object]:
    compact = prior.compact_state
    return {
        "account_state_id": str(prior.account_state_id),
        "checkpoint_byte_length": prior.checkpoint_byte_length,
        "checkpoint_id": str(prior.checkpoint_id),
        "checkpoint_sha256": prior.checkpoint_sha256,
        "compact_state": {
            "as_of": canonical_timestamp(compact.as_of),
            "cash": canonical_decimal(compact.cash),
            "compact_state_id": str(compact.compact_state_id),
            "positions": [
                {
                    "average_cost": canonical_decimal(item.average_cost),
                    "quantity": canonical_decimal(item.quantity),
                    "symbol": str(item.symbol),
                    "total_cost_basis": canonical_decimal(item.total_cost_basis),
                }
                for item in compact.positions
            ],
            "realized_profit_loss": canonical_decimal(compact.realized_profit_loss),
        },
        "empty_engine_state_id": str(prior.empty_engine_state_id),
        "kind": prior.kind.value,
        "lineage_id": str(prior.lineage_id),
        "sequence": prior.sequence,
    }


def _target_tree(target: ExplicitQuantityTargetPortfolio) -> dict[str, object]:
    return {
        "quantities": [
            {"quantity": canonical_decimal(item.quantity), "symbol": str(item.symbol)}
            for item in target.quantities
        ],
        "target_cash": canonical_decimal(target.target_cash),
        "target_id": str(target.target_id),
    }


def _proposal_tree(proposal: TradeProposal | None) -> object:
    if proposal is None:
        return None
    return {
        "confidence": (
            None
            if proposal.confidence is None
            else canonical_decimal(proposal.confidence)
        ),
        "created_at": canonical_timestamp(proposal.created_at),
        "desired_quantity": canonical_decimal(proposal.desired_quantity),
        "proposal_id": str(proposal.proposal_id),
        "reason": proposal.reason,
        "side": proposal.side.value,
        "symbol": str(proposal.symbol),
    }


def _prior(value: object) -> ManualPaperPriorCheckpointEvidence:
    raw = _object(value, _PRIOR_FIELDS, "prior_checkpoint")
    compact_raw = _object(
        raw["compact_state"], _COMPACT_FIELDS, "prior_checkpoint.compact_state"
    )
    positions = tuple(
        _compact_position(item, index)
        for index, item in enumerate(
            _array(compact_raw["positions"], "prior_checkpoint.compact_state.positions")
        )
    )
    try:
        compact = CompactPaperLedgerState(
            _uuid(
                compact_raw["compact_state_id"],
                "prior_checkpoint.compact_state.compact_state_id",
            ),
            _timestamp(compact_raw["as_of"], "prior_checkpoint.compact_state.as_of"),
            _decimal(compact_raw["cash"], "prior_checkpoint.compact_state.cash"),
            positions,
            _decimal(
                compact_raw["realized_profit_loss"],
                "prior_checkpoint.compact_state.realized_profit_loss",
            ),
        )
        return ManualPaperPriorCheckpointEvidence(
            _enum(raw["kind"], VerifiedPriorCheckpointKind, "prior_checkpoint.kind"),
            _uuid(raw["checkpoint_id"], "prior_checkpoint.checkpoint_id"),
            _nonnegative_integer(raw["sequence"], "prior_checkpoint.sequence"),
            _uuid(raw["lineage_id"], "prior_checkpoint.lineage_id"),
            _uuid(raw["account_state_id"], "prior_checkpoint.account_state_id"),
            compact,
            _uuid(
                raw["empty_engine_state_id"],
                "prior_checkpoint.empty_engine_state_id",
            ),
            _sha(raw["checkpoint_sha256"], "prior_checkpoint.checkpoint_sha256"),
            _positive_integer(
                raw["checkpoint_byte_length"],
                "prior_checkpoint.checkpoint_byte_length",
            ),
        )
    except ManualPaperStrategyPlanError:
        raise
    except Exception as error:
        raise ManualPaperStrategyPlanSerializationError(
            "prior checkpoint evidence does not reconcile"
        ) from error


def _compact_position(value: object, index: int) -> CompactPaperLedgerPosition:
    path = f"prior_checkpoint.compact_state.positions[{index}]"
    raw = _object(value, _COMPACT_POSITION_FIELDS, path)
    try:
        return CompactPaperLedgerPosition(
            _symbol(raw["symbol"], f"{path}.symbol"),
            _decimal(raw["quantity"], f"{path}.quantity"),
            _decimal(raw["total_cost_basis"], f"{path}.total_cost_basis"),
            _decimal(raw["average_cost"], f"{path}.average_cost"),
        )
    except Exception as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: compact position does not reconcile"
        ) from error


def _target(value: object) -> ExplicitQuantityTargetPortfolio:
    raw = _object(value, _TARGET_FIELDS, "target")
    quantities = tuple(
        ExplicitQuantityTarget(
            _symbol(
                _object(item, _TARGET_QUANTITY_FIELDS, f"target.quantities[{index}]")[
                    "symbol"
                ],
                f"target.quantities[{index}].symbol",
            ),
            _decimal(
                _object(item, _TARGET_QUANTITY_FIELDS, f"target.quantities[{index}]")[
                    "quantity"
                ],
                f"target.quantities[{index}].quantity",
            ),
        )
        for index, item in enumerate(_array(raw["quantities"], "target.quantities"))
    )
    try:
        return ExplicitQuantityTargetPortfolio(
            _uuid(raw["target_id"], "target.target_id"),
            quantities,
            _decimal(raw["target_cash"], "target.target_cash"),
        )
    except Exception as error:
        raise ManualPaperStrategyPlanSerializationError(
            "target does not reconcile"
        ) from error


def _optional_proposal(value: object, path: str) -> TradeProposal | None:
    if value is None:
        return None
    raw = _object(value, _PROPOSAL_FIELDS, path)
    try:
        return TradeProposal(
            _uuid(raw["proposal_id"], f"{path}.proposal_id"),
            _symbol(raw["symbol"], f"{path}.symbol"),
            _enum(raw["side"], OrderSide, f"{path}.side"),
            _decimal(raw["desired_quantity"], f"{path}.desired_quantity"),
            _timestamp(raw["created_at"], f"{path}.created_at"),
            _string(raw["reason"], f"{path}.reason"),
            (
                None
                if raw["confidence"] is None
                else _decimal(raw["confidence"], f"{path}.confidence")
            ),
        )
    except Exception as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: proposal does not reconcile"
        ) from error


def _canonical_json_bytes(tree: object) -> bytes:
    try:
        return (
            json.dumps(
                tree,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ManualPaperStrategyPlanSerializationError(
            "plan cannot be serialized as canonical JSON"
        ) from error


def _load_json(payload: bytes) -> object:
    if type(payload) is not bytes:
        raise ManualPaperStrategyPlanSerializationError("payload must be exact bytes")
    if len(payload) > MAX_MANUAL_PAPER_STRATEGY_PLAN_BYTES:
        raise ManualPaperStrategyPlanSerializationError(
            "plan payload exceeds the 8 MiB limit"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise ManualPaperStrategyPlanSerializationError("UTF-8 BOM is not permitted")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ManualPaperStrategyPlanSerializationError(
            "plan payload is not valid UTF-8"
        ) from error
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ManualPaperStrategyPlanSerializationError(
            "plan JSON must have exactly one final newline"
        )
    core = text[:-1]
    if not core or core != core.strip():
        raise ManualPaperStrategyPlanSerializationError(
            "plan JSON has leading or trailing whitespace"
        )
    try:
        return json.loads(
            core,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"plan JSON is invalid at line {error.lineno} column {error.colno}"
        ) from error


def _object(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ManualPaperStrategyPlanSerializationError(f"{path}: expected object")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        raise ManualPaperStrategyPlanSerializationError(f"{path}: {'; '.join(details)}")
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise ManualPaperStrategyPlanSerializationError(f"{path}: expected array")
    if len(value) > 4096:
        raise ManualPaperStrategyPlanSerializationError(f"{path}: array exceeds bound")
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str:
        raise ManualPaperStrategyPlanSerializationError(f"{path}: expected string")
    return value


def _utf8_artifact(value: object, path: str) -> bytes:
    text = _string(value, path)
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: cannot encode as UTF-8"
        ) from error
    if not encoded or len(encoded) > MAX_MANUAL_PAPER_STRATEGY_PLAN_BYTES:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: embedded artifact exceeds bound"
        )
    return encoded


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: expected canonical UUID"
        ) from error
    if str(parsed) != text:
        raise ManualPaperStrategyPlanSerializationError(f"{path}: UUID not canonical")
    return parsed


def _symbol(value: object, path: str) -> Symbol:
    text = _string(value, path)
    try:
        parsed = Symbol(text)
    except Exception as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: invalid symbol"
        ) from error
    if str(parsed) != text:
        raise ManualPaperStrategyPlanSerializationError(f"{path}: symbol not canonical")
    return parsed


def _timestamp(value: object, path: str) -> datetime:
    text = _string(value, path)
    if not text.endswith("Z"):
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: expected canonical UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: invalid timestamp"
        ) from error
    if canonical_timestamp(parsed) != text:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: timestamp not canonical"
        )
    return parsed


def _decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    if not 1 <= len(text) <= 128:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: Decimal exceeds bound"
        )
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: invalid Decimal"
        ) from error
    if not parsed.is_finite() or canonical_decimal(parsed) != text:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: Decimal not canonical"
        )
    return parsed


def _integer(value: object, path: str) -> int:
    if type(value) is not int:
        raise ManualPaperStrategyPlanSerializationError(f"{path}: expected integer")
    return value


def _nonnegative_integer(value: object, path: str) -> int:
    retained = _integer(value, path)
    if not 0 <= retained <= 2**63 - 1:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: expected bounded nonnegative integer"
        )
    return retained


def _positive_integer(value: object, path: str) -> int:
    retained = _integer(value, path)
    if not 1 <= retained <= 2**63 - 1:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: expected bounded positive integer"
        )
    return retained


def _sha(value: object, path: str) -> str:
    text = _string(value, path)
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: expected lowercase SHA-256"
        )
    return text


def _enum(value: object, enum_type: type[StrEnum], path: str) -> Any:
    text = _string(value, path)
    try:
        return enum_type(text)
    except ValueError as error:
        raise ManualPaperStrategyPlanSerializationError(
            f"{path}: unsupported value"
        ) from error


def _metadata(value: object) -> tuple[MetadataEntry, ...]:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise ManualPaperStrategyPlanValidationError(
            "metadata must be iterable"
        ) from error
    if any(type(item) is not MetadataEntry for item in items):
        raise ManualPaperStrategyPlanValidationError(
            "metadata must contain exact MetadataEntry values"
        )
    if (
        len(items) > MAX_MANUAL_PAPER_BASE_METADATA
        or len({item.key for item in items}) != len(items)
        or any(
            len(item.key) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_KEY_CHARACTERS
            or len(item.value)
            > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_VALUE_CHARACTERS
            for item in items
        )
    ):
        raise ManualPaperStrategyPlanValidationError(
            "metadata exceeds the P1 base bounds or contains duplicate keys"
        )
    return items


def _paper_account_id(value: object) -> str:
    if type(value) is not str or _PAPER_ACCOUNT_ID_PATTERN.fullmatch(value) is None:
        raise ManualPaperStrategyPlanValidationError(
            "paper_account_id must be 1..128 canonical ASCII characters"
        )
    return value


def _require_c3_snapshot_match(
    assertion: object,
    verification: DailySnapshotVerificationResult,
) -> None:
    if type(assertion) is not ManualPaperSelectedC3Assertion:
        raise ManualPaperStrategyPlanValidationError(
            "selected_c3_assertion must be exact non-authorizing evidence"
        )
    if (
        verification.status is not DailySnapshotVerificationStatus.PASS
        or verification.snapshot is None
        or verification.diagnostics
        or assertion.snapshot_id != verification.snapshot.snapshot_id
        or assertion.artifact_sha256 != verification.sha256
        or assertion.artifact_byte_length != verification.byte_length
    ):
        raise ManualPaperStrategyPlanValidationError(
            "selected C3 assertion does not match the complete PASS snapshot"
        )


def _idempotency_key(value: object) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= MAX_MANUAL_PAPER_IDEMPOTENCY_KEY_CHARACTERS
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ManualPaperStrategyPlanValidationError(
            "caller_idempotency_key must be bounded canonical nonblank text"
        )
    return value


def _utc(value: object, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ManualPaperStrategyPlanValidationError(
            f"{name} must be a timezone-aware datetime"
        )
    return value.astimezone(UTC)


def _expected_sha(value: str | None) -> None:
    if value is not None and (
        type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise ManualPaperStrategyPlanVerificationError(
            "expected_sha256 must be lowercase SHA-256 or None"
        )


def _expected_length(value: int | None) -> None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ManualPaperStrategyPlanVerificationError(
            "expected_byte_length must be positive or None"
        )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManualPaperStrategyPlanSerializationError(
                f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ManualPaperStrategyPlanSerializationError(
        f"nonstandard JSON constant is not permitted: {value}"
    )


def _framed_material(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
