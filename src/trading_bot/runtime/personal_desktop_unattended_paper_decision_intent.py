"""Canonical durable pre-open decision intent for Architecture 111 G4."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.execution import PaperFillPolicy
from trading_bot.ledger import CompactPaperLedgerPosition, CompactPaperLedgerState
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    canonical_decimal,
    replay_verified_daily_snapshot,
    verify_daily_snapshot,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.portfolio import MetadataEntry, PortfolioConstraints
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    VerifiedPriorCheckpointKind,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperPriorCheckpointEvidence,
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyPlanError,
    ManualPaperStrategySignalStatus,
    PreparedManualPaperStrategyDecision,
    verify_prepared_manual_paper_strategy_decision,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    PERSONAL_DESKTOP_UNATTENDED_HISTORY_SOURCE_ID,
    SelectedC3StrategyHistoryBinding,
    require_selected_c3_strategy_history_binding,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    next_xnys_execution_session,
    xnys_regular_open,
)
from trading_bot.runtime.strategy_history_seed import (
    StrategyHistorySeedSourceDescriptor,
    create_strategy_history_seed,
    serialize_strategy_history_seed,
    verify_strategy_history_seed,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_SCHEMA = (
    "personal-desktop-unattended-paper-decision-intent/v1"
)
PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_POLICY_VERSION = (
    "personal-desktop-unattended-paper-decision-policy/v1"
)
PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_IDENTITY_MATERIAL_VERSION = (
    "personal-desktop-unattended-paper-decision-identity/v1"
)
PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_NAMESPACE = UUID(
    "b83c7339-3f61-58f3-82ed-3641e2d22d82"
)
MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_BYTES = 16 * 1024 * 1024

_SHA = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_ACCOUNT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ROOT_FIELDS = frozenset(
    {
        "current_c3",
        "decision_id",
        "decision_policy_version",
        "history_c3",
        "identity_material_version",
        "intended_execution_session",
        "paper_account_id",
        "predecessor_checkpoint_id",
        "prepared_decision",
        "schema",
        "selected_session",
    }
)
_C3_FIELDS = frozenset(
    {
        "artifact_byte_length",
        "artifact_sha256",
        "selected_session",
        "selection_id",
        "session_id",
        "snapshot_artifact_utf8",
        "snapshot_id",
        "terminal_id",
    }
)
_PREPARED_FIELDS = frozenset(
    {
        "caller_idempotency_key",
        "filled_at",
        "history_seed_artifact_utf8",
        "history_seed_byte_length",
        "history_seed_sha256",
        "metadata",
        "paper_account_id",
        "planning_at",
        "policies",
        "prior_checkpoint",
        "selected_c3_assertion",
        "selected_session",
        "selected_snapshot_artifact_utf8",
        "signal_status",
        "strategy_config",
        "strategy_context_material",
        "strategy_proposal",
        "strategy_run_id",
        "strategy_step_index",
        "submitted_at",
        "symbol",
        "target",
    }
)
_C3_ASSERTION_FIELDS = frozenset(
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
    {"as_of", "cash", "compact_state_id", "positions", "realized_profit_loss"}
)
_POSITION_FIELDS = frozenset({"average_cost", "quantity", "symbol", "total_cost_basis"})
_TARGET_FIELDS = frozenset({"quantities", "target_cash", "target_id"})
_TARGET_QUANTITY_FIELDS = frozenset({"quantity", "symbol"})
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
_METADATA_FIELDS = frozenset({"key", "value"})
_POLICY_FIELDS = frozenset(
    {
        "fill_policy",
        "portfolio_constraints",
        "proposal_confidence",
        "proposal_policy",
        "rebalance_assumptions",
        "risk_limits",
        "risk_policy",
        "trading_enabled",
    }
)
_ASSUMPTIONS_FIELDS = frozenset(
    {
        "additional_execution_cash_buffer",
        "allow_fractional_quantities",
        "fixed_commission",
        "minimum_trade_notional",
        "minimum_trade_quantity",
        "quantity_increment",
        "target_weight_tolerance",
        "use_planned_sell_proceeds",
    }
)
_CONSTRAINTS_FIELDS = frozenset(
    {
        "allow_leverage",
        "long_only",
        "maximum_cash_weight",
        "maximum_one_way_rebalance_turnover",
        "maximum_position_weight",
        "minimum_cash_weight",
        "minimum_position_weight",
    }
)
_PROPOSAL_POLICY_FIELDS = frozenset({"allow_partial_plans"})
_RISK_LIMITS_FIELDS = frozenset(
    {
        "allow_buying",
        "allow_fractional_shares",
        "allow_selling",
        "estimated_commission",
        "fractional_increment",
        "max_new_position_percent",
        "max_order_notional",
        "max_position_percent",
        "max_total_exposure_percent",
        "minimum_cash_reserve_percent",
    }
)
_RISK_POLICY_FIELDS = frozenset({"allow_sell_proceeds_for_later_buys"})
_FILL_POLICY_FIELDS = frozenset({"fixed_commission", "slippage_basis_points"})


class PersonalDesktopUnattendedPaperDecisionIntentError(Exception):
    """Base class for durable decision-intent failures."""


class PersonalDesktopUnattendedPaperDecisionIntentValidationError(
    PersonalDesktopUnattendedPaperDecisionIntentError, ValueError
):
    """An in-memory decision intent is inconsistent."""


class PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
    PersonalDesktopUnattendedPaperDecisionIntentError, ValueError
):
    """Decision-intent bytes are not the exact canonical representation."""


class PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
    PersonalDesktopUnattendedPaperDecisionIntentError, ValueError
):
    """Durable semantic decision replay failed closed."""


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperDecisionC3Evidence:
    """Durable non-authorizing evidence for one selected C3 snapshot."""

    selected_session: TradingSession
    selection_id: UUID
    session_id: UUID
    terminal_id: UUID
    snapshot_id: UUID
    artifact_sha256: str
    artifact_byte_length: int
    snapshot_artifact: bytes

    def __post_init__(self) -> None:
        if type(self.selected_session) is not TradingSession:
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "selected C3 session is invalid"
            )
        for name in ("selection_id", "session_id", "terminal_id", "snapshot_id"):
            if type(getattr(self, name)) is not UUID:
                raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                    f"selected C3 {name} is invalid"
                )
        if (
            type(self.artifact_sha256) is not str
            or _SHA.fullmatch(self.artifact_sha256) is None
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length <= 0
            or type(self.snapshot_artifact) is not bytes
            or len(self.snapshot_artifact) != self.artifact_byte_length
            or sha256(self.snapshot_artifact).hexdigest() != self.artifact_sha256
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "selected C3 artifact evidence is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperDecisionIntent:
    """Immutable complete pre-open semantic decision without future-open data."""

    decision_id: UUID
    paper_account_id: str
    predecessor_checkpoint_id: UUID
    selected_session: TradingSession
    intended_execution_session: TradingSession
    history_c3: tuple[PersonalDesktopUnattendedPaperDecisionC3Evidence, ...]
    current_c3: PersonalDesktopUnattendedPaperDecisionC3Evidence
    prepared_decision: PreparedManualPaperStrategyDecision
    decision_policy_version: str = (
        PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_POLICY_VERSION
    )
    identity_material_version: str = (
        PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_IDENTITY_MATERIAL_VERSION
    )
    schema: str = PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_SCHEMA

    def __post_init__(self) -> None:
        if type(self.decision_id) is not UUID:
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "decision_id must be an exact UUID"
            )
        if (
            type(self.paper_account_id) is not str
            or _ACCOUNT.fullmatch(self.paper_account_id) is None
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "paper_account_id is invalid"
            )
        if type(self.predecessor_checkpoint_id) is not UUID:
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "predecessor_checkpoint_id is invalid"
            )
        if (
            type(self.selected_session) is not TradingSession
            or type(self.intended_execution_session) is not TradingSession
            or next_xnys_execution_session(self.selected_session)
            != self.intended_execution_session
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "selected and intended execution sessions do not reconcile"
            )
        history = tuple(self.history_c3)
        if (
            any(
                type(item) is not PersonalDesktopUnattendedPaperDecisionC3Evidence
                for item in history
            )
            or type(self.current_c3)
            is not PersonalDesktopUnattendedPaperDecisionC3Evidence
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "selected C3 history evidence is invalid"
            )
        object.__setattr__(self, "history_c3", history)
        prepared = self.prepared_decision
        if type(prepared) is not PreparedManualPaperStrategyDecision:
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "prepared_decision must be exact"
            )
        if (
            len(history) != prepared.strategy_config.long_window
            or len({item.selected_session for item in history}) != len(history)
            or tuple(item.selected_session for item in history)
            != tuple(sorted(item.selected_session for item in history))
            or any(item.selected_session >= self.selected_session for item in history)
            or self.current_c3.selected_session != self.selected_session
            or prepared.paper_account_id != self.paper_account_id
            or prepared.prior_checkpoint.checkpoint_id != self.predecessor_checkpoint_id
            or prepared.selected_session != self.selected_session
            or prepared.intended_execution_session != self.intended_execution_session
            or prepared.selected_snapshot_artifact != self.current_c3.snapshot_artifact
            or prepared.history_seed_artifact == b""
            or not _assertion_matches(prepared.selected_c3_assertion, self.current_c3)
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "prepared decision does not reconcile with durable authority evidence"
            )
        modeled_open = xnys_regular_open(self.intended_execution_session)
        if prepared.submitted_at != modeled_open or prepared.filled_at != modeled_open:
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "submitted_at and filled_at must equal the source-owned regular open"
            )
        if (
            self.decision_policy_version
            != PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_POLICY_VERSION
            or self.identity_material_version
            != PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_IDENTITY_MATERIAL_VERSION
            or self.schema != PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_SCHEMA
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "decision intent version fields are not frozen"
            )
        if self.decision_id != _decision_id(self):
            raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
                "decision_id does not match canonical semantic material"
            )


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding:
    """Detached bytes and exact replayed durable decision."""

    decision: PersonalDesktopUnattendedPaperDecisionIntent
    artifact_bytes: bytes
    artifact_sha256: str
    artifact_byte_length: int

    def __post_init__(self) -> None:
        if (
            type(self.decision) is not PersonalDesktopUnattendedPaperDecisionIntent
            or type(self.artifact_bytes) is not bytes
            or not self.artifact_bytes
            or type(self.artifact_sha256) is not str
            or _SHA.fullmatch(self.artifact_sha256) is None
            or self.artifact_sha256 != sha256(self.artifact_bytes).hexdigest()
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length != len(self.artifact_bytes)
            or self.artifact_byte_length <= 0
            or self.artifact_byte_length
            > MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_BYTES
            or serialize_personal_desktop_unattended_paper_decision_intent(
                self.decision
            )
            != self.artifact_bytes
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
                "detached decision-intent binding is inconsistent"
            )


def create_personal_desktop_unattended_paper_decision_intent(
    prepared_decision: PreparedManualPaperStrategyDecision,
    history_binding: SelectedC3StrategyHistoryBinding,
    authority: ValidatedProductionAuthority,
    *,
    expected_paper_account_id: str,
    expected_predecessor_checkpoint_id: UUID,
) -> PersonalDesktopUnattendedPaperDecisionIntent:
    """Bind an accepted G3 decision to exact current-C1/G2 provenance."""

    c1 = require_validated_production_authority(authority)
    binding = require_selected_c3_strategy_history_binding(history_binding, c1)
    if type(prepared_decision) is not PreparedManualPaperStrategyDecision:
        raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
            "prepared_decision must be exact"
        )
    if (
        prepared_decision.paper_account_id != expected_paper_account_id
        or prepared_decision.prior_checkpoint.checkpoint_id
        != expected_predecessor_checkpoint_id
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
            "prepared account or predecessor binding is not authoritative"
        )
    current = _c3_from_process_read(binding.current)
    history = tuple(_c3_from_process_read(item) for item in binding.history)
    seed_bytes = serialize_strategy_history_seed(binding.verified_seed.seed)
    if (
        prepared_decision.snapshot_verification != binding.current.selected.verification
        or prepared_decision.selected_snapshot_artifact
        != binding.current.selected.snapshot_bytes
        or prepared_decision.history_seed_artifact != seed_bytes
        or prepared_decision.strategy_config != binding.verified_seed.strategy_config
        or prepared_decision.selected_session != binding.current.session
        or not _assertion_matches(prepared_decision.selected_c3_assertion, current)
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentValidationError(
            "prepared decision does not exactly match current selected-C3 history"
        )
    values = dict(
        paper_account_id=prepared_decision.paper_account_id,
        predecessor_checkpoint_id=prepared_decision.prior_checkpoint.checkpoint_id,
        selected_session=prepared_decision.selected_session,
        intended_execution_session=prepared_decision.intended_execution_session,
        history_c3=history,
        current_c3=current,
        prepared_decision=prepared_decision,
    )
    provisional = PersonalDesktopUnattendedPaperDecisionIntent.__new__(
        PersonalDesktopUnattendedPaperDecisionIntent
    )
    for name, value in values.items():
        object.__setattr__(provisional, name, value)
    object.__setattr__(
        provisional,
        "decision_policy_version",
        PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_POLICY_VERSION,
    )
    object.__setattr__(
        provisional,
        "identity_material_version",
        PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_IDENTITY_MATERIAL_VERSION,
    )
    object.__setattr__(
        provisional, "schema", PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_SCHEMA
    )
    object.__setattr__(provisional, "decision_id", _decision_id(provisional))
    return PersonalDesktopUnattendedPaperDecisionIntent(
        provisional.decision_id, **values
    )


def serialize_personal_desktop_unattended_paper_decision_intent(
    decision: PersonalDesktopUnattendedPaperDecisionIntent,
) -> bytes:
    """Serialize one decision intent as bounded canonical UTF-8 JSON."""

    if type(decision) is not PersonalDesktopUnattendedPaperDecisionIntent:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision must be exact"
        )
    payload = _canonical_json_bytes(_decision_tree(decision))
    if len(payload) > MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_BYTES:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision intent exceeds the 16 MiB bound"
        )
    return payload


def parse_personal_desktop_unattended_paper_decision_intent(
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperDecisionIntent:
    """Strictly parse and semantically replay canonical durable bytes."""

    return _parse_and_verify(payload, calendar)


def verify_personal_desktop_unattended_paper_decision_intent(
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
    *,
    expected_decision_id: UUID | None = None,
    expected_artifact_sha256: str | None = None,
    expected_artifact_byte_length: int | None = None,
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding:
    """Verify canonical bytes, detached evidence, and the complete G3 replay."""

    if type(payload) is not bytes:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "payload must be exact bytes"
        )
    if expected_decision_id is not None and type(expected_decision_id) is not UUID:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "expected_decision_id must be an exact UUID or None"
        )
    if expected_artifact_sha256 is not None and (
        type(expected_artifact_sha256) is not str
        or _SHA.fullmatch(expected_artifact_sha256) is None
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "expected artifact SHA-256 is invalid"
        )
    if expected_artifact_byte_length is not None and (
        type(expected_artifact_byte_length) is not int
        or expected_artifact_byte_length <= 0
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "expected artifact byte length is invalid"
        )
    digest = sha256(payload).hexdigest()
    length = len(payload)
    if expected_artifact_sha256 is not None and digest != expected_artifact_sha256:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "decision artifact SHA-256 differs from detached evidence"
        )
    if (
        expected_artifact_byte_length is not None
        and length != expected_artifact_byte_length
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "decision artifact byte length differs from detached evidence"
        )
    decision = _parse_and_verify(payload, calendar)
    if (
        expected_decision_id is not None
        and decision.decision_id != expected_decision_id
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "decision_id differs from detached evidence"
        )
    return PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding(
        decision, payload, digest, length
    )


def bind_personal_desktop_unattended_paper_decision_intent(
    decision: PersonalDesktopUnattendedPaperDecisionIntent,
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding:
    """Create detached evidence without re-evaluating the accepted G3 decision."""

    payload = serialize_personal_desktop_unattended_paper_decision_intent(decision)
    return PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding(
        decision, payload, sha256(payload).hexdigest(), len(payload)
    )


def _parse_and_verify(
    payload: bytes, calendar: IdentifiedMarketCalendar
) -> PersonalDesktopUnattendedPaperDecisionIntent:
    _require_xnys_calendar(calendar)
    root = _object(_load_json(payload), _ROOT_FIELDS, "root")
    try:
        history = tuple(
            _c3_from_tree(item, f"history_c3[{index}]")
            for index, item in enumerate(_array(root["history_c3"], "history_c3"))
        )
        current = _c3_from_tree(root["current_c3"], "current_c3")
        prepared = _prepared_from_tree(root["prepared_decision"], calendar)
        decision = PersonalDesktopUnattendedPaperDecisionIntent(
            _uuid(root["decision_id"], "decision_id"),
            _account(root["paper_account_id"]),
            _uuid(root["predecessor_checkpoint_id"], "predecessor_checkpoint_id"),
            _session(root["selected_session"], "selected_session"),
            _session(root["intended_execution_session"], "intended_execution_session"),
            history,
            current,
            prepared,
            _string(root["decision_policy_version"], "decision_policy_version"),
            _string(root["identity_material_version"], "identity_material_version"),
            _string(root["schema"], "schema"),
        )
        _verify_c3_history(decision, calendar)
        verify_prepared_manual_paper_strategy_decision(prepared, calendar)
    except PersonalDesktopUnattendedPaperDecisionIntentError:
        raise
    except ManualPaperStrategyPlanError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "embedded G3 prepared decision failed exact replay"
        ) from error
    except Exception as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "durable decision semantic replay failed"
        ) from error
    if serialize_personal_desktop_unattended_paper_decision_intent(decision) != payload:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision-intent bytes are not canonical"
        )
    return decision


def _verify_c3_history(
    decision: PersonalDesktopUnattendedPaperDecisionIntent,
    calendar: IdentifiedMarketCalendar,
) -> None:
    for item in (*decision.history_c3, decision.current_c3):
        verified = verify_daily_snapshot(
            item.snapshot_artifact,
            calendar,
            expected_sha256=item.artifact_sha256,
            expected_byte_length=item.artifact_byte_length,
        )
        if (
            verified.status is not DailySnapshotVerificationStatus.PASS
            or verified.snapshot is None
            or verified.snapshot.snapshot_id != item.snapshot_id
        ):
            raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
                "selected C3 artifact failed exact replay"
            )
        replay = replay_verified_daily_snapshot(verified)
        if len(replay.bars) != 1 or replay.bars[0].session != item.selected_session:
            raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
                "selected C3 artifact session is inconsistent"
            )
    bars = tuple(
        replay_verified_daily_snapshot(
            verify_daily_snapshot(item.snapshot_artifact, calendar)
        ).bars[0]
        for item in decision.history_c3
    )
    seed = create_strategy_history_seed(
        symbol=decision.prepared_decision.symbol,
        source=StrategyHistorySeedSourceDescriptor(
            PERSONAL_DESKTOP_UNATTENDED_HISTORY_SOURCE_ID
        ),
        bars=bars,
    )
    seed_payload = serialize_strategy_history_seed(seed)
    if seed_payload != decision.prepared_decision.history_seed_artifact:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "durable selected-C3 history differs from the canonical history seed"
        )
    verify_strategy_history_seed(
        seed_payload,
        expected_symbol=decision.prepared_decision.symbol,
        target_session=decision.selected_session,
        strategy_config=decision.prepared_decision.strategy_config,
        calendar=calendar,
    )


def _c3_from_process_read(
    item: object,
) -> PersonalDesktopUnattendedPaperDecisionC3Evidence:
    selected = item.selected
    audit = selected.audit
    return PersonalDesktopUnattendedPaperDecisionC3Evidence(
        item.session,
        audit.selection_id,
        audit.session_id,
        audit.terminal_id,
        audit.snapshot_id,
        audit.artifact_sha256,
        audit.artifact_byte_length,
        selected.snapshot_bytes,
    )


def _assertion_matches(
    assertion: ManualPaperSelectedC3Assertion,
    evidence: PersonalDesktopUnattendedPaperDecisionC3Evidence,
) -> bool:
    return (
        assertion.selection_id == evidence.selection_id
        and assertion.session_id == evidence.session_id
        and assertion.terminal_id == evidence.terminal_id
        and assertion.snapshot_id == evidence.snapshot_id
        and assertion.artifact_sha256 == evidence.artifact_sha256
        and assertion.artifact_byte_length == evidence.artifact_byte_length
    )


def _decision_id(decision: PersonalDesktopUnattendedPaperDecisionIntent) -> UUID:
    prepared = _prepared_tree(decision.prepared_decision)
    # Formation time and embedded artifact text are retained evidence, not identity.
    prepared.pop("planning_at")
    prepared.pop("selected_snapshot_artifact_utf8")
    prepared.pop("history_seed_artifact_utf8")
    history = []
    for item in decision.history_c3:
        tree = _c3_tree(item)
        tree.pop("snapshot_artifact_utf8")
        history.append(tree)
    current = _c3_tree(decision.current_c3)
    current.pop("snapshot_artifact_utf8")
    material = _canonical_json_bytes(
        {
            "current_c3": current,
            "decision_policy_version": decision.decision_policy_version,
            "history_c3": history,
            "identity_material_version": decision.identity_material_version,
            "intended_execution_session": (
                decision.intended_execution_session.session_date.isoformat()
            ),
            "paper_account_id": decision.paper_account_id,
            "predecessor_checkpoint_id": str(decision.predecessor_checkpoint_id),
            "prepared_decision": prepared,
            "selected_session": decision.selected_session.session_date.isoformat(),
        }
    ).decode("utf-8")
    return uuid5(PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_NAMESPACE, material)


def _decision_tree(
    decision: PersonalDesktopUnattendedPaperDecisionIntent,
) -> dict[str, object]:
    return {
        "current_c3": _c3_tree(decision.current_c3),
        "decision_id": str(decision.decision_id),
        "decision_policy_version": decision.decision_policy_version,
        "history_c3": [_c3_tree(item) for item in decision.history_c3],
        "identity_material_version": decision.identity_material_version,
        "intended_execution_session": (
            decision.intended_execution_session.session_date.isoformat()
        ),
        "paper_account_id": decision.paper_account_id,
        "predecessor_checkpoint_id": str(decision.predecessor_checkpoint_id),
        "prepared_decision": _prepared_tree(decision.prepared_decision),
        "schema": decision.schema,
        "selected_session": decision.selected_session.session_date.isoformat(),
    }


def _c3_tree(
    item: PersonalDesktopUnattendedPaperDecisionC3Evidence,
) -> dict[str, object]:
    return {
        "artifact_byte_length": item.artifact_byte_length,
        "artifact_sha256": item.artifact_sha256,
        "selected_session": item.selected_session.session_date.isoformat(),
        "selection_id": str(item.selection_id),
        "session_id": str(item.session_id),
        "snapshot_artifact_utf8": item.snapshot_artifact.decode("utf-8"),
        "snapshot_id": str(item.snapshot_id),
        "terminal_id": str(item.terminal_id),
    }


def _c3_from_tree(
    value: object, path: str
) -> PersonalDesktopUnattendedPaperDecisionC3Evidence:
    raw = _object(value, _C3_FIELDS, path)
    artifact = _utf8(raw["snapshot_artifact_utf8"], f"{path}.snapshot_artifact_utf8")
    return PersonalDesktopUnattendedPaperDecisionC3Evidence(
        _session(raw["selected_session"], f"{path}.selected_session"),
        _uuid(raw["selection_id"], f"{path}.selection_id"),
        _uuid(raw["session_id"], f"{path}.session_id"),
        _uuid(raw["terminal_id"], f"{path}.terminal_id"),
        _uuid(raw["snapshot_id"], f"{path}.snapshot_id"),
        _sha(raw["artifact_sha256"], f"{path}.artifact_sha256"),
        _positive_int(raw["artifact_byte_length"], f"{path}.artifact_byte_length"),
        artifact,
    )


def _prepared_tree(prepared: PreparedManualPaperStrategyDecision) -> dict[str, object]:
    seed = prepared.history_seed_artifact
    return {
        "caller_idempotency_key": prepared.caller_idempotency_key,
        "filled_at": canonical_timestamp(prepared.filled_at),
        "history_seed_artifact_utf8": seed.decode("utf-8"),
        "history_seed_byte_length": len(seed),
        "history_seed_sha256": sha256(seed).hexdigest(),
        "metadata": [
            {"key": item.key, "value": item.value} for item in prepared.metadata
        ],
        "paper_account_id": prepared.paper_account_id,
        "planning_at": canonical_timestamp(prepared.planning_at),
        "policies": _policies_tree(prepared.policies),
        "prior_checkpoint": _prior_tree(prepared.prior_checkpoint),
        "selected_c3_assertion": _assertion_tree(prepared.selected_c3_assertion),
        "selected_session": prepared.selected_session.session_date.isoformat(),
        "selected_snapshot_artifact_utf8": prepared.selected_snapshot_artifact.decode(
            "utf-8"
        ),
        "signal_status": prepared.signal_status.value,
        "strategy_config": {
            "desired_quantity": canonical_decimal(
                prepared.strategy_config.desired_quantity
            ),
            "long_window": prepared.strategy_config.long_window,
            "short_window": prepared.strategy_config.short_window,
        },
        "strategy_context_material": prepared.strategy_context_material,
        "strategy_proposal": _proposal_tree(prepared.strategy_proposal),
        "strategy_run_id": str(prepared.strategy_run_id),
        "strategy_step_index": prepared.strategy_step_index,
        "submitted_at": canonical_timestamp(prepared.submitted_at),
        "symbol": str(prepared.symbol),
        "target": _target_tree(prepared.target),
    }


def _prepared_from_tree(
    value: object, calendar: IdentifiedMarketCalendar
) -> PreparedManualPaperStrategyDecision:
    raw = _object(value, _PREPARED_FIELDS, "prepared_decision")
    config_raw = _object(raw["strategy_config"], _CONFIG_FIELDS, "strategy_config")
    assertion_raw = _object(
        raw["selected_c3_assertion"], _C3_ASSERTION_FIELDS, "selected_c3_assertion"
    )
    config = MovingAverageCrossoverConfig(
        _positive_int(config_raw["short_window"], "short_window"),
        _positive_int(config_raw["long_window"], "long_window"),
        _decimal(config_raw["desired_quantity"], "desired_quantity"),
    )
    snapshot_bytes = _utf8(
        raw["selected_snapshot_artifact_utf8"], "selected_snapshot_artifact_utf8"
    )
    snapshot = verify_daily_snapshot(snapshot_bytes, calendar)
    if snapshot.status is not DailySnapshotVerificationStatus.PASS:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "prepared selected snapshot failed replay"
        )
    seed = _utf8(raw["history_seed_artifact_utf8"], "history_seed_artifact_utf8")
    if sha256(seed).hexdigest() != _sha(
        raw["history_seed_sha256"], "history_seed_sha256"
    ) or len(seed) != _positive_int(
        raw["history_seed_byte_length"], "history_seed_byte_length"
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "history seed detached evidence is inconsistent"
        )
    verified_seed = verify_strategy_history_seed(
        seed,
        expected_symbol=_symbol(raw["symbol"], "symbol"),
        target_session=_session(raw["selected_session"], "selected_session"),
        strategy_config=config,
        calendar=calendar,
    )
    del verified_seed
    return PreparedManualPaperStrategyDecision(
        snapshot_bytes,
        snapshot,
        seed,
        _account(raw["paper_account_id"]),
        ManualPaperSelectedC3Assertion(
            _uuid(assertion_raw["selection_id"], "selection_id"),
            _uuid(assertion_raw["session_id"], "session_id"),
            _uuid(assertion_raw["terminal_id"], "terminal_id"),
            _uuid(assertion_raw["snapshot_id"], "snapshot_id"),
            _sha(assertion_raw["artifact_sha256"], "artifact_sha256"),
            _positive_int(
                assertion_raw["artifact_byte_length"], "artifact_byte_length"
            ),
        ),
        _prior(raw["prior_checkpoint"]),
        config,
        _string(raw["caller_idempotency_key"], "caller_idempotency_key"),
        _policies(raw["policies"]),
        _timestamp(raw["planning_at"], "planning_at"),
        _timestamp(raw["submitted_at"], "submitted_at"),
        _timestamp(raw["filled_at"], "filled_at"),
        tuple(
            MetadataEntry(
                _string(_object(item, _METADATA_FIELDS, "metadata item")["key"], "key"),
                _string(item["value"], "value"),
            )
            for item in _array(raw["metadata"], "metadata")
        ),
        _symbol(raw["symbol"], "symbol"),
        _session(raw["selected_session"], "selected_session"),
        next_xnys_execution_session(
            _session(raw["selected_session"], "selected_session")
        ),
        _string(raw["strategy_context_material"], "strategy_context_material"),
        _uuid(raw["strategy_run_id"], "strategy_run_id"),
        _nonnegative_int(raw["strategy_step_index"], "strategy_step_index"),
        _enum(raw["signal_status"], ManualPaperStrategySignalStatus, "signal_status"),
        _proposal(raw["strategy_proposal"], "strategy_proposal"),
        _target(raw["target"]),
    )


def _assertion_tree(value: ManualPaperSelectedC3Assertion) -> dict[str, object]:
    return {
        "artifact_byte_length": value.artifact_byte_length,
        "artifact_sha256": value.artifact_sha256,
        "selection_id": str(value.selection_id),
        "session_id": str(value.session_id),
        "snapshot_id": str(value.snapshot_id),
        "terminal_id": str(value.terminal_id),
    }


def _prior_tree(value: ManualPaperPriorCheckpointEvidence) -> dict[str, object]:
    compact = value.compact_state
    return {
        "account_state_id": str(value.account_state_id),
        "checkpoint_byte_length": value.checkpoint_byte_length,
        "checkpoint_id": str(value.checkpoint_id),
        "checkpoint_sha256": value.checkpoint_sha256,
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
        "empty_engine_state_id": str(value.empty_engine_state_id),
        "kind": value.kind.value,
        "lineage_id": str(value.lineage_id),
        "sequence": value.sequence,
    }


def _prior(value: object) -> ManualPaperPriorCheckpointEvidence:
    raw = _object(value, _PRIOR_FIELDS, "prior_checkpoint")
    compact_raw = _object(raw["compact_state"], _COMPACT_FIELDS, "compact_state")
    positions = tuple(
        CompactPaperLedgerPosition(
            _symbol(item["symbol"], "position.symbol"),
            _decimal(item["quantity"], "position.quantity"),
            _decimal(item["total_cost_basis"], "position.total_cost_basis"),
            _decimal(item["average_cost"], "position.average_cost"),
        )
        for item in (
            _object(entry, _POSITION_FIELDS, "position")
            for entry in _array(compact_raw["positions"], "positions")
        )
    )
    compact = CompactPaperLedgerState(
        _uuid(compact_raw["compact_state_id"], "compact_state_id"),
        _timestamp(compact_raw["as_of"], "compact.as_of"),
        _decimal(compact_raw["cash"], "compact.cash"),
        positions,
        _decimal(compact_raw["realized_profit_loss"], "realized_profit_loss"),
    )
    return ManualPaperPriorCheckpointEvidence(
        _enum(raw["kind"], VerifiedPriorCheckpointKind, "prior.kind"),
        _uuid(raw["checkpoint_id"], "checkpoint_id"),
        _nonnegative_int(raw["sequence"], "sequence"),
        _uuid(raw["lineage_id"], "lineage_id"),
        _uuid(raw["account_state_id"], "account_state_id"),
        compact,
        _uuid(raw["empty_engine_state_id"], "empty_engine_state_id"),
        _sha(raw["checkpoint_sha256"], "checkpoint_sha256"),
        _positive_int(raw["checkpoint_byte_length"], "checkpoint_byte_length"),
    )


def _target_tree(value: ExplicitQuantityTargetPortfolio) -> dict[str, object]:
    return {
        "quantities": [
            {"quantity": canonical_decimal(item.quantity), "symbol": str(item.symbol)}
            for item in value.quantities
        ],
        "target_cash": canonical_decimal(value.target_cash),
        "target_id": str(value.target_id),
    }


def _target(value: object) -> ExplicitQuantityTargetPortfolio:
    raw = _object(value, _TARGET_FIELDS, "target")
    quantities = tuple(
        ExplicitQuantityTarget(
            _symbol(item["symbol"], "target.symbol"),
            _decimal(item["quantity"], "target.quantity"),
        )
        for item in (
            _object(entry, _TARGET_QUANTITY_FIELDS, "target quantity")
            for entry in _array(raw["quantities"], "target.quantities")
        )
    )
    return ExplicitQuantityTargetPortfolio(
        _uuid(raw["target_id"], "target_id"),
        quantities,
        _decimal(raw["target_cash"], "target_cash"),
    )


def _proposal_tree(value: TradeProposal | None) -> object:
    if value is None:
        return None
    return {
        "confidence": None
        if value.confidence is None
        else canonical_decimal(value.confidence),
        "created_at": canonical_timestamp(value.created_at),
        "desired_quantity": canonical_decimal(value.desired_quantity),
        "proposal_id": str(value.proposal_id),
        "reason": value.reason,
        "side": value.side.value,
        "symbol": str(value.symbol),
    }


def _proposal(value: object, path: str) -> TradeProposal | None:
    if value is None:
        return None
    raw = _object(value, _PROPOSAL_FIELDS, path)
    return TradeProposal(
        _uuid(raw["proposal_id"], f"{path}.proposal_id"),
        _symbol(raw["symbol"], f"{path}.symbol"),
        _enum(raw["side"], OrderSide, f"{path}.side"),
        _decimal(raw["desired_quantity"], f"{path}.desired_quantity"),
        _timestamp(raw["created_at"], f"{path}.created_at"),
        _string(raw["reason"], f"{path}.reason"),
        None
        if raw["confidence"] is None
        else _decimal(raw["confidence"], f"{path}.confidence"),
    )


def _policies_tree(value: VerifiedSnapshotPaperCyclePolicies) -> dict[str, object]:
    a = value.rebalance_assumptions
    c = value.portfolio_constraints
    r = value.risk_limits
    return {
        "fill_policy": {
            "fixed_commission": canonical_decimal(value.fill_policy.fixed_commission),
            "slippage_basis_points": canonical_decimal(
                value.fill_policy.slippage_basis_points
            ),
        },
        "portfolio_constraints": None
        if c is None
        else {
            "allow_leverage": c.allow_leverage,
            "long_only": c.long_only,
            "maximum_cash_weight": canonical_decimal(c.maximum_cash_weight),
            "maximum_one_way_rebalance_turnover": _optional_decimal(
                c.maximum_one_way_rebalance_turnover
            ),
            "maximum_position_weight": canonical_decimal(c.maximum_position_weight),
            "minimum_cash_weight": canonical_decimal(c.minimum_cash_weight),
            "minimum_position_weight": _optional_decimal(c.minimum_position_weight),
        },
        "proposal_confidence": _optional_decimal(value.proposal_confidence),
        "proposal_policy": {
            "allow_partial_plans": value.proposal_policy.allow_partial_plans
        },
        "rebalance_assumptions": {
            "additional_execution_cash_buffer": canonical_decimal(
                a.additional_execution_cash_buffer
            ),
            "allow_fractional_quantities": a.allow_fractional_quantities,
            "fixed_commission": canonical_decimal(a.fixed_commission),
            "minimum_trade_notional": canonical_decimal(a.minimum_trade_notional),
            "minimum_trade_quantity": canonical_decimal(a.minimum_trade_quantity),
            "quantity_increment": canonical_decimal(a.quantity_increment),
            "target_weight_tolerance": canonical_decimal(a.target_weight_tolerance),
            "use_planned_sell_proceeds": a.use_planned_sell_proceeds,
        },
        "risk_limits": {
            "allow_buying": r.allow_buying,
            "allow_fractional_shares": r.allow_fractional_shares,
            "allow_selling": r.allow_selling,
            "estimated_commission": canonical_decimal(r.estimated_commission),
            "fractional_increment": canonical_decimal(r.fractional_increment),
            "max_new_position_percent": _optional_decimal(r.max_new_position_percent),
            "max_order_notional": _optional_decimal(r.max_order_notional),
            "max_position_percent": canonical_decimal(r.max_position_percent),
            "max_total_exposure_percent": canonical_decimal(
                r.max_total_exposure_percent
            ),
            "minimum_cash_reserve_percent": canonical_decimal(
                r.minimum_cash_reserve_percent
            ),
        },
        "risk_policy": {
            "allow_sell_proceeds_for_later_buys": (
                value.risk_policy.allow_sell_proceeds_for_later_buys
            )
        },
        "trading_enabled": value.trading_enabled,
    }


def _policies(value: object) -> VerifiedSnapshotPaperCyclePolicies:
    raw = _object(value, _POLICY_FIELDS, "policies")
    a = _object(raw["rebalance_assumptions"], _ASSUMPTIONS_FIELDS, "assumptions")
    p = _object(raw["proposal_policy"], _PROPOSAL_POLICY_FIELDS, "proposal_policy")
    r = _object(raw["risk_limits"], _RISK_LIMITS_FIELDS, "risk_limits")
    rp = _object(raw["risk_policy"], _RISK_POLICY_FIELDS, "risk_policy")
    f = _object(raw["fill_policy"], _FILL_POLICY_FIELDS, "fill_policy")
    constraints = None
    if raw["portfolio_constraints"] is not None:
        c = _object(raw["portfolio_constraints"], _CONSTRAINTS_FIELDS, "constraints")
        constraints = PortfolioConstraints(
            _decimal(c["minimum_cash_weight"], "minimum_cash_weight"),
            _decimal(c["maximum_cash_weight"], "maximum_cash_weight"),
            _decimal(c["maximum_position_weight"], "maximum_position_weight"),
            _nullable_decimal(
                c["maximum_one_way_rebalance_turnover"],
                "maximum_one_way_rebalance_turnover",
            ),
            _nullable_decimal(c["minimum_position_weight"], "minimum_position_weight"),
            _bool(c["long_only"], "long_only"),
            _bool(c["allow_leverage"], "allow_leverage"),
        )
    return VerifiedSnapshotPaperCyclePolicies(
        RebalanceAssumptions(
            _decimal(a["fixed_commission"], "fixed_commission"),
            _bool(a["allow_fractional_quantities"], "allow_fractional_quantities"),
            _decimal(a["quantity_increment"], "quantity_increment"),
            _decimal(a["minimum_trade_notional"], "minimum_trade_notional"),
            _decimal(a["minimum_trade_quantity"], "minimum_trade_quantity"),
            _decimal(a["target_weight_tolerance"], "target_weight_tolerance"),
            _decimal(
                a["additional_execution_cash_buffer"],
                "additional_execution_cash_buffer",
            ),
            _bool(a["use_planned_sell_proceeds"], "use_planned_sell_proceeds"),
        ),
        constraints,
        RebalanceProposalPolicy(_bool(p["allow_partial_plans"], "allow_partial_plans")),
        _nullable_decimal(raw["proposal_confidence"], "proposal_confidence"),
        RiskLimits(
            _decimal(r["max_position_percent"], "max_position_percent"),
            _decimal(r["max_total_exposure_percent"], "max_total_exposure_percent"),
            _nullable_decimal(r["max_order_notional"], "max_order_notional"),
            _nullable_decimal(
                r["max_new_position_percent"], "max_new_position_percent"
            ),
            _decimal(r["minimum_cash_reserve_percent"], "minimum_cash_reserve_percent"),
            _bool(r["allow_fractional_shares"], "allow_fractional_shares"),
            _decimal(r["fractional_increment"], "fractional_increment"),
            _bool(r["allow_buying"], "allow_buying"),
            _bool(r["allow_selling"], "allow_selling"),
            _decimal(r["estimated_commission"], "estimated_commission"),
        ),
        PortfolioRiskPolicy(
            _bool(
                rp["allow_sell_proceeds_for_later_buys"],
                "allow_sell_proceeds_for_later_buys",
            )
        ),
        PaperFillPolicy(
            _decimal(f["slippage_basis_points"], "slippage_basis_points"),
            _decimal(f["fixed_commission"], "fill_fixed_commission"),
        ),
        _bool(raw["trading_enabled"], "trading_enabled"),
    )


def _optional_decimal(value: Decimal | None) -> str | None:
    return None if value is None else canonical_decimal(value)


def _load_json(payload: bytes) -> object:
    if type(payload) is not bytes:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "payload must be exact bytes"
        )
    if len(payload) > MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_INTENT_BYTES:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision intent exceeds the 16 MiB bound"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "UTF-8 BOM is not permitted"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision intent is not UTF-8"
        ) from error
    if (
        not text.endswith("\n")
        or text.endswith("\n\n")
        or text[:-1] != text[:-1].strip()
    ):
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision JSON must have exactly one final newline and no outer whitespace"
        )
    try:
        return json.loads(
            text[:-1],
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision JSON is invalid"
        ) from error


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "decision intent cannot be serialized"
        ) from error


def _object(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    if type(value) is not dict or frozenset(value) != fields:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: object fields are not exact"
        )
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: expected array"
        )
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: expected string"
        )
    return value


def _utf8(value: object, path: str) -> bytes:
    try:
        return _string(value, path).encode("utf-8")
    except UnicodeEncodeError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: cannot encode UTF-8"
        ) from error


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        result = UUID(text)
    except ValueError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid UUID"
        ) from error
    if str(result) != text:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: UUID is noncanonical"
        )
    return result


def _session(value: object, path: str) -> TradingSession:
    text = _string(value, path)
    if _DATE.fullmatch(text) is None:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid session"
        )
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid session"
        ) from error
    if parsed.isoformat() != text:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: noncanonical session"
        )
    return TradingSession(parsed)


def _timestamp(value: object, path: str) -> datetime:
    text = _string(value, path)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: timestamp must be aware"
        )
    parsed = parsed.astimezone(UTC)
    if canonical_timestamp(parsed) != text:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: timestamp is noncanonical"
        )
    return parsed


def _decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    try:
        result = Decimal(text)
    except InvalidOperation as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid Decimal"
        ) from error
    if not result.is_finite() or canonical_decimal(result) != text:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: Decimal is noncanonical"
        )
    return result


def _nullable_decimal(value: object, path: str) -> Decimal | None:
    return None if value is None else _decimal(value, path)


def _positive_int(value: object, path: str) -> int:
    if type(value) is not int or value <= 0:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: expected positive integer"
        )
    return value


def _nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: expected nonnegative integer"
        )
    return value


def _bool(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: expected bool"
        )
    return value


def _sha(value: object, path: str) -> str:
    text = _string(value, path)
    if _SHA.fullmatch(text) is None:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid SHA-256"
        )
    return text


def _account(value: object) -> str:
    text = _string(value, "paper_account_id")
    if _ACCOUNT.fullmatch(text) is None:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            "paper_account_id is invalid"
        )
    return text


def _symbol(value: object, path: str) -> Symbol:
    try:
        result = Symbol(_string(value, path))
    except (TypeError, ValueError) as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid symbol"
        ) from error
    if str(result) != value:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: symbol is noncanonical"
        )
    return result


def _enum(value: object, enum_type: type, path: str):
    text = _string(value, path)
    try:
        result = enum_type(text)
    except ValueError as error:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: invalid enum"
        ) from error
    if result.value != text:
        raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
            f"{path}: enum is noncanonical"
        )
    return result


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise PersonalDesktopUnattendedPaperDecisionIntentSerializationError(
        f"nonstandard JSON constant is forbidden: {value}"
    )


def _require_xnys_calendar(calendar: IdentifiedMarketCalendar) -> None:
    if getattr(calendar, "descriptor", None) != XNYS_CALENDAR_DESCRIPTOR:
        raise PersonalDesktopUnattendedPaperDecisionIntentVerificationError(
            "calendar must be the exact identified XNYS calendar"
        )


def personal_desktop_unattended_decision_calendar() -> IdentifiedMarketCalendar:
    """Return the frozen public calendar used for decision-intent replay."""

    return BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
