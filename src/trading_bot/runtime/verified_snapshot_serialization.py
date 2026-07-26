"""Canonical reporting and offline replay verification for one paper cycle."""

from __future__ import annotations

import json
import re
import types
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import Enum, StrEnum
from hashlib import sha256
from typing import Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.market_data import (
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    verify_daily_snapshot,
)
from trading_bot.market_data.daily_snapshot_identity import (
    canonical_decimal,
    canonical_timestamp,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.exceptions import (
    VerifiedSnapshotPaperCycleExecutionError,
    VerifiedSnapshotPaperCyclePreparationError,
    VerifiedSnapshotPaperCycleReplayError,
    VerifiedSnapshotPaperCycleReportReconciliationError,
    VerifiedSnapshotPaperCycleReportSchemaError,
    VerifiedSnapshotPaperCycleReportSyntaxError,
    VerifiedSnapshotPaperCycleReportVerificationError,
)
from trading_bot.runtime.verified_snapshot_execution import (
    VerifiedSnapshotPaperCycleResult,
    execute_prepared_verified_snapshot_paper_cycle,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    ExplicitQuantityTargetPortfolio,
    VerifiedDailySnapshotReference,
    VerifiedSnapshotAccountState,
    VerifiedSnapshotPaperCyclePolicies,
    VerifiedSnapshotPaperCyclePreparationRequest,
    prepare_verified_snapshot_paper_cycle,
)

VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_SCHEMA_VERSION = 1
MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_BYTES = 16 * 1024 * 1024
MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_ARRAY_ITEMS = 20_000
MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_STRING_CHARACTERS = 16_384
MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_DECIMAL_CHARACTERS = 256
MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_INTEGER = (1 << 63) - 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_ARITHMETIC_CONTEXT = Context(prec=4096, Emax=999_999, Emin=-999_999)
_ROOT_FIELDS = frozenset({"result", "schema_version"})
_EXECUTION_MODEL = "trading_bot.runtime.verified_snapshot_execution."
_PREPARATION_MODEL = "trading_bot.runtime.verified_snapshot_preparation."

# This is the schema-1 allowlist.  It deliberately freezes every retained model
# and field rather than recursively accepting arbitrary dataclasses.
_MODEL_FIELDS: dict[str, tuple[str, ...]] = {
    _EXECUTION_MODEL + "VerifiedSnapshotPaperCycleResult": (
        "result_id",
        "preparation",
        "bootstrap_evidence",
        "runtime_result",
        "status",
        "final_account_state",
        "diagnostics",
    ),
    _PREPARATION_MODEL + "PreparedVerifiedSnapshotPaperCycle": (
        "preparation_id",
        "request_id",
        "snapshot_reference",
        "snapshot_audit_sha256",
        "snapshot_canonical_bars_sha256",
        "snapshot_captured_at",
        "provider",
        "calendar",
        "target_session",
        "next_session",
        "close_marks",
        "account_state",
        "target",
        "open_references",
        "policies",
        "planning_at",
        "submitted_at",
        "filled_at",
        "metadata",
        "planner_request",
    ),
    _PREPARATION_MODEL + "VerifiedDailySnapshotReference": (
        "snapshot_id",
        "artifact_sha256",
        "artifact_byte_length",
    ),
    "trading_bot.market_data.daily_snapshot_models.ProviderDescriptor": (
        "provider_id",
        "adapter_version",
        "operation",
        "feed",
    ),
    "trading_bot.market_data.daily_snapshot_models.CalendarDescriptor": (
        "calendar_id",
        "version",
        "exchange_timezone",
    ),
    "trading_bot.market_calendar.models.TradingSession": ("session_date",),
    "trading_bot.runtime.verified_snapshot_preparation.VerifiedSnapshotCloseMark": (
        "symbol",
        "session",
        "planning_close",
    ),
    _PREPARATION_MODEL + "VerifiedSnapshotAccountState": (
        "account_state_id",
        "as_of",
        "cash",
        "positions",
    ),
    _PREPARATION_MODEL + "VerifiedSnapshotAccountPosition": (
        "symbol",
        "quantity",
        "average_cost",
    ),
    _PREPARATION_MODEL + "ExplicitQuantityTargetPortfolio": (
        "target_id",
        "quantities",
        "target_cash",
    ),
    _PREPARATION_MODEL + "ExplicitQuantityTarget": (
        "symbol",
        "quantity",
    ),
    _PREPARATION_MODEL + "CallerAssertedNextSessionOpenReference": (
        "symbol",
        "session",
        "caller_asserted_open_reference_price",
    ),
    _PREPARATION_MODEL + "VerifiedSnapshotPaperCyclePolicies": (
        "rebalance_assumptions",
        "portfolio_constraints",
        "proposal_policy",
        "proposal_confidence",
        "risk_limits",
        "risk_policy",
        "fill_policy",
        "trading_enabled",
    ),
    "trading_bot.rebalancing.models.RebalanceAssumptions": (
        "fixed_commission",
        "allow_fractional_quantities",
        "quantity_increment",
        "minimum_trade_notional",
        "minimum_trade_quantity",
        "target_weight_tolerance",
        "additional_execution_cash_buffer",
        "use_planned_sell_proceeds",
    ),
    "trading_bot.portfolio.models.PortfolioConstraints": (
        "minimum_cash_weight",
        "maximum_cash_weight",
        "maximum_position_weight",
        "maximum_one_way_rebalance_turnover",
        "minimum_position_weight",
        "long_only",
        "allow_leverage",
    ),
    "trading_bot.rebalancing.proposals.RebalanceProposalPolicy": (
        "allow_partial_plans",
    ),
    "trading_bot.risk.models.RiskLimits": (
        "max_position_percent",
        "max_total_exposure_percent",
        "max_order_notional",
        "max_new_position_percent",
        "minimum_cash_reserve_percent",
        "allow_fractional_shares",
        "fractional_increment",
        "allow_buying",
        "allow_selling",
        "estimated_commission",
    ),
    "trading_bot.risk.orchestration.PortfolioRiskPolicy": (
        "allow_sell_proceeds_for_later_buys",
    ),
    "trading_bot.execution.paper_fills.PaperFillPolicy": (
        "slippage_basis_points",
        "fixed_commission",
    ),
    "trading_bot.portfolio.models.MetadataEntry": ("key", "value"),
    "trading_bot.rebalancing.models.RebalancePlanRequest": (
        "request_id",
        "state",
        "target",
        "assumptions",
        "constraints",
        "metadata",
    ),
    "trading_bot.portfolio.models.PortfolioState": (
        "as_of",
        "positions",
        "cash",
        "equity",
    ),
    "trading_bot.portfolio.models.PortfolioPositionState": (
        "symbol",
        "quantity",
        "average_cost",
        "current_price",
    ),
    "trading_bot.portfolio.models.TargetPortfolio": (
        "target_id",
        "as_of",
        "allocations",
        "cash_weight",
        "source",
        "source_name",
        "metadata",
    ),
    "trading_bot.portfolio.models.TargetAllocation": ("symbol", "weight"),
    "trading_bot.ledger.initialization.PaperLedgerInitializationEvidence": (
        "initialization_id",
        "request",
        "bootstrap_fills",
    ),
    "trading_bot.ledger.initialization.PaperLedgerInitializationRequest": (
        "mode",
        "as_of",
        "available_cash",
        "positions",
        "identity_namespace",
        "identity_material",
    ),
    "trading_bot.ledger.initialization.PaperLedgerInitializationPosition": (
        "symbol",
        "quantity",
        "average_cost",
    ),
    "trading_bot.domain.orders.OrderFill": (
        "fill_id",
        "order_id",
        "symbol",
        "side",
        "quantity",
        "price",
        "commission",
        "filled_at",
    ),
    "trading_bot.runtime.paper_portfolio.PaperPortfolioCycleResult": (
        "result_id",
        "request",
        "status",
        "plan",
        "proposal_result",
        "risk_result",
        "order_result",
        "submission_result",
        "fill_result",
        "application_result",
        "pre_engine_state_id",
        "pre_ledger_state_id",
        "post_engine_state_id",
        "post_ledger_state_id",
        "diagnostics",
    ),
    "trading_bot.runtime.paper_portfolio.PaperPortfolioCycleRequest": (
        "request_id",
        "inputs",
        "metadata",
    ),
    "trading_bot.runtime.paper_portfolio.PaperPortfolioCycleInputs": (
        "state",
        "target",
        "rebalance_assumptions",
        "portfolio_constraints",
        "proposal_policy",
        "proposal_confidence",
        "risk_limits",
        "risk_policy",
        "prices",
        "fill_policy",
        "trading_enabled",
        "submitted_at",
        "filled_at",
    ),
    "trading_bot.runtime.paper_portfolio.PaperPortfolioCyclePrice": (
        "symbol",
        "risk_price",
        "fill_reference_price",
    ),
    "trading_bot.rebalancing.models.RebalancePlan": (
        "plan_id",
        "request",
        "status",
        "trades",
        "deviations",
        "diagnostics",
        "planning_equity",
        "target_cash_value",
        "estimated_starting_cash",
        "estimated_gross_sell_proceeds",
        "estimated_gross_buy_cost",
        "estimated_commissions",
        "estimated_ending_cash",
        "estimated_ending_equity",
        "estimated_achieved_cash_weight",
        "estimated_target_cash_value_at_ending_equity",
        "cash_value_deviation",
        "cash_weight_deviation",
        "estimated_constraints_satisfied",
    ),
    "trading_bot.rebalancing.models.PlannedTrade": (
        "planned_trade_id",
        "symbol",
        "side",
        "symbol_ordinal",
        "current_price",
        "current_quantity",
        "target_weight",
        "target_market_value",
        "target_quantity",
        "requested_quantity",
        "planned_quantity",
        "estimated_gross_notional",
        "estimated_commission",
        "estimated_net_cash_effect",
    ),
    "trading_bot.rebalancing.models.RebalanceDeviation": (
        "symbol",
        "symbol_ordinal",
        "target_weight",
        "estimated_achieved_weight",
        "signed_weight_deviation",
        "absolute_weight_deviation",
        "target_market_value",
        "estimated_achieved_market_value",
        "target_quantity",
        "estimated_achieved_quantity",
        "limiting_reason",
    ),
    "trading_bot.rebalancing.models.RebalanceDiagnostic": (
        "code",
        "message",
        "symbol",
    ),
    "trading_bot.rebalancing.proposals.RebalanceProposalResult": (
        "result_id",
        "request",
        "status",
        "proposals",
        "diagnostics",
    ),
    "trading_bot.rebalancing.proposals.RebalanceProposalRequest": (
        "request_id",
        "plan",
        "proposal_created_at",
        "policy",
        "confidence",
        "metadata",
    ),
    "trading_bot.domain.proposals.TradeProposal": (
        "proposal_id",
        "symbol",
        "side",
        "desired_quantity",
        "created_at",
        "reason",
        "confidence",
    ),
    "trading_bot.rebalancing.proposals.RebalanceProposalDiagnostic": (
        "code",
        "message",
    ),
    "trading_bot.risk.orchestration.PortfolioRiskBatchResult": (
        "result_id",
        "request",
        "status",
        "evaluations",
        "final_positions",
        "final_risk_available_cash",
        "final_economic_cash",
        "final_exposure",
        "final_economic_equity",
        "withheld_sell_proceeds",
        "total_reserved_commissions",
        "total_approved_buy_notional",
        "total_approved_sell_notional",
        "approved_count",
        "resized_count",
        "rejected_count",
        "diagnostics",
    ),
    "trading_bot.risk.orchestration.PortfolioRiskBatchRequest": (
        "request_id",
        "proposals",
        "base_context",
        "prices",
        "risk_limits",
        "policy",
        "metadata",
    ),
    "trading_bot.risk.models.RiskContext": (
        "cash",
        "equity",
        "positions",
        "current_price",
        "total_market_exposure",
        "new_trading_enabled",
        "as_of",
    ),
    "trading_bot.domain.positions.Position": (
        "symbol",
        "quantity",
        "average_cost",
    ),
    "trading_bot.risk.orchestration.PortfolioRiskPrice": ("symbol", "price"),
    "trading_bot.risk.orchestration.PortfolioRiskEvaluation": (
        "ordinal",
        "context",
        "decision",
        "risk_available_cash_before",
        "risk_available_cash_after",
        "economic_cash_after",
        "symbol_quantity_before",
        "symbol_quantity_after",
        "reserved_notional",
        "reserved_commission",
        "resulting_exposure",
    ),
    "trading_bot.risk.models.RiskDecision": (
        "proposal",
        "outcome",
        "approved_quantity",
        "reasons",
        "evaluated_at",
    ),
    "trading_bot.risk.models.RiskReason": (
        "code",
        "message",
        "observed",
        "limit",
    ),
    "trading_bot.risk.orchestration.PortfolioRiskDiagnostic": ("code", "message"),
    "trading_bot.execution.portfolio_orders.PortfolioOrderBatchResult": (
        "result_id",
        "request",
        "status",
        "source_evaluation_ordinals",
        "orders",
        "created_events",
        "diagnostics",
    ),
    "trading_bot.execution.portfolio_orders.PortfolioOrderBatchRequest": (
        "request_id",
        "risk_batch",
        "instruction",
        "metadata",
    ),
    "trading_bot.execution.models.ExecutionInstruction": (
        "order_type",
        "time_in_force",
        "created_at",
        "limit_price",
    ),
    "trading_bot.domain.orders.Order": (
        "request",
        "status",
        "filled_quantity",
        "average_fill_price",
        "rejection_reason",
    ),
    "trading_bot.domain.orders.OrderRequest": (
        "order_id",
        "symbol",
        "side",
        "order_type",
        "quantity",
        "time_in_force",
        "submitted_at",
        "limit_price",
    ),
    "trading_bot.execution.models.OrderEvent": (
        "event_id",
        "order_id",
        "event_type",
        "occurred_at",
        "fill_id",
        "reason",
    ),
    "trading_bot.execution.portfolio_orders.PortfolioOrderDiagnostic": (
        "code",
        "message",
    ),
    "trading_bot.execution.paper_submission.PaperSubmissionBatchResult": (
        "result_id",
        "request",
        "status",
        "orders",
        "submitted_events",
        "diagnostics",
    ),
    "trading_bot.execution.paper_submission.PaperSubmissionBatchRequest": (
        "request_id",
        "order_batch",
        "submitted_at",
        "metadata",
    ),
    "trading_bot.execution.paper_submission.PaperSubmissionDiagnostic": (
        "code",
        "message",
    ),
    "trading_bot.execution.paper_fills.PaperFillBatchResult": (
        "result_id",
        "request",
        "status",
        "evaluations",
        "diagnostics",
    ),
    "trading_bot.execution.paper_fills.PaperFillBatchRequest": (
        "request_id",
        "submission_batch",
        "filled_at",
        "prices",
        "policy",
        "metadata",
    ),
    "trading_bot.execution.paper_fills.PaperFillPrice": (
        "order_id",
        "reference_price",
    ),
    "trading_bot.execution.paper_fills.PaperFillEvaluation": (
        "source_order_ordinal",
        "reference_price",
        "slippage_amount",
        "fill",
    ),
    "trading_bot.execution.paper_fills.PaperFillDiagnostic": ("code", "message"),
    "trading_bot.execution.paper_fill_application.PaperFillApplicationBatchResult": (
        "result_id",
        "request",
        "status",
        "evaluations",
        "pre_engine_state_id",
        "pre_ledger_state_id",
        "post_engine_state_id",
        "post_ledger_state_id",
        "diagnostics",
    ),
    "trading_bot.execution.paper_fill_application.PaperFillApplicationBatchRequest": (
        "request_id",
        "fill_batch",
        "metadata",
    ),
    "trading_bot.execution.paper_fill_application.PaperFillApplicationEvaluation": (
        "source_fill_ordinal",
        "fill",
        "updated_order",
        "fill_event",
        "ledger_cash_after",
        "ledger_position_after",
        "ledger_realized_profit_loss_after",
    ),
    "trading_bot.execution.paper_fill_application.PaperFillApplicationDiagnostic": (
        "code",
        "message",
    ),
    "trading_bot.runtime.paper_portfolio.PaperPortfolioCycleDiagnostic": (
        "code",
        "message",
    ),
    _EXECUTION_MODEL + "VerifiedSnapshotPaperCycleAccountState": (
        "as_of",
        "cash",
        "positions",
        "realized_profit_loss",
    ),
    _EXECUTION_MODEL + "VerifiedSnapshotPaperCycleDiagnostic": (
        "code",
        "message",
    ),
}


class VerifiedSnapshotPaperCycleReportVerificationStatus(StrEnum):
    """Outcome of complete offline report and snapshot replay."""

    PASS = "PASS"
    FAIL = "FAIL"


class VerifiedSnapshotPaperCycleReportVerificationCode(StrEnum):
    """Stable, ordered offline-verification failure classifications."""

    REPORT_BYTE_LENGTH_MISMATCH = "REPORT_BYTE_LENGTH_MISMATCH"
    REPORT_SHA256_MISMATCH = "REPORT_SHA256_MISMATCH"
    REPORT_SYNTAX_FAILURE = "REPORT_SYNTAX_FAILURE"
    STRICT_SCHEMA_CANONICALIZATION_FAILURE = "STRICT_SCHEMA_CANONICALIZATION_FAILURE"
    SNAPSHOT_LINKAGE_FAILURE = "SNAPSHOT_LINKAGE_FAILURE"
    PREPARATION_RECONSTRUCTION_FAILURE = "PREPARATION_RECONSTRUCTION_FAILURE"
    EXECUTION_REPLAY_FAILURE = "EXECUTION_REPLAY_FAILURE"
    IDENTITY_STATE_RECONCILIATION_FAILURE = "IDENTITY_STATE_RECONCILIATION_FAILURE"


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleReportVerificationDiagnostic:
    """One stable failure code and non-identity human explanation."""

    code: VerifiedSnapshotPaperCycleReportVerificationCode
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, VerifiedSnapshotPaperCycleReportVerificationCode):
            raise VerifiedSnapshotPaperCycleReportVerificationError(
                "verification diagnostic code is invalid"
            )
        if type(self.detail) is not str or not self.detail:
            raise VerifiedSnapshotPaperCycleReportVerificationError(
                "verification diagnostic detail must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class VerifiedSnapshotPaperCycleReportVerificationResult:
    """Immutable complete PASS or deterministic FAIL offline evidence."""

    status: VerifiedSnapshotPaperCycleReportVerificationStatus
    report_byte_length: int
    report_sha256: str
    snapshot_byte_length: int
    snapshot_sha256: str
    result: VerifiedSnapshotPaperCycleResult | None
    diagnostics: tuple[VerifiedSnapshotPaperCycleReportVerificationDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.status, VerifiedSnapshotPaperCycleReportVerificationStatus
        ):
            raise VerifiedSnapshotPaperCycleReportVerificationError(
                "verification status is invalid"
            )
        for name in ("report_byte_length", "snapshot_byte_length"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise VerifiedSnapshotPaperCycleReportVerificationError(
                    f"{name} must be a nonnegative integer"
                )
        for name in ("report_sha256", "snapshot_sha256"):
            value = getattr(self, name)
            if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
                raise VerifiedSnapshotPaperCycleReportVerificationError(
                    f"{name} must be lowercase SHA-256 text"
                )
        diagnostics = tuple(self.diagnostics)
        if any(
            type(item) is not VerifiedSnapshotPaperCycleReportVerificationDiagnostic
            for item in diagnostics
        ):
            raise VerifiedSnapshotPaperCycleReportVerificationError(
                "diagnostics contain an invalid value"
            )
        if self.status is VerifiedSnapshotPaperCycleReportVerificationStatus.PASS:
            if type(self.result) is not VerifiedSnapshotPaperCycleResult or diagnostics:
                raise VerifiedSnapshotPaperCycleReportVerificationError(
                    "PASS requires one result and no diagnostics"
                )
        elif self.result is not None or not diagnostics:
            raise VerifiedSnapshotPaperCycleReportVerificationError(
                "FAIL requires diagnostics and no replay result"
            )
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def passed(self) -> bool:
        return self.status is VerifiedSnapshotPaperCycleReportVerificationStatus.PASS


def serialize_verified_snapshot_paper_cycle_result(
    result: VerifiedSnapshotPaperCycleResult,
) -> bytes:
    """Serialize complete immutable cycle evidence as schema-1 canonical JSON."""
    if type(result) is not VerifiedSnapshotPaperCycleResult:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "result must be exactly VerifiedSnapshotPaperCycleResult"
        )
    with localcontext(_ARITHMETIC_CONTEXT):
        tree = {
            "result": _encode(result, "$.result"),
            "schema_version": VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_SCHEMA_VERSION,
        }
        payload = _canonical_json_bytes(tree)
    if len(payload) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_BYTES:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "serialized cycle report exceeds the 16 MiB limit"
        )
    return payload


def parse_verified_snapshot_paper_cycle_result(
    payload: bytes,
) -> VerifiedSnapshotPaperCycleResult:
    """Strictly parse canonical bytes into complete immutable cycle evidence."""
    tree = _load_and_validate_tree(payload)
    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            result = _decode(
                tree["result"],
                VerifiedSnapshotPaperCycleResult,
                "$.result",
                construct=True,
            )
    except VerifiedSnapshotPaperCycleReportSchemaError:
        raise
    except Exception as error:
        raise VerifiedSnapshotPaperCycleReportReconciliationError(
            "retained cycle evidence does not form a consistent immutable result"
        ) from error
    if type(result) is not VerifiedSnapshotPaperCycleResult:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "$.result: expected cycle result"
        )
    if serialize_verified_snapshot_paper_cycle_result(result) != payload:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "cycle report is not the canonical serialization"
        )
    return result


def verify_verified_snapshot_paper_cycle_report(
    report_payload: bytes,
    snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
    *,
    expected_report_sha256: str | None = None,
    expected_report_byte_length: int | None = None,
) -> VerifiedSnapshotPaperCycleReportVerificationResult:
    """Verify and replay one report using only its matching snapshot bytes."""
    if type(report_payload) is not bytes or type(snapshot_payload) is not bytes:
        raise VerifiedSnapshotPaperCycleReportVerificationError(
            "report_payload and snapshot_payload must be exact bytes"
        )
    _validate_expected_sha256(expected_report_sha256)
    _validate_expected_byte_length(expected_report_byte_length)
    report_length = len(report_payload)
    report_hash = sha256(report_payload).hexdigest()
    snapshot_length = len(snapshot_payload)
    snapshot_hash = sha256(snapshot_payload).hexdigest()
    diagnostics: list[VerifiedSnapshotPaperCycleReportVerificationDiagnostic] = []
    if (
        expected_report_byte_length is not None
        and report_length != expected_report_byte_length
    ):
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.REPORT_BYTE_LENGTH_MISMATCH,
                "report byte length does not match expected evidence",
            )
        )
    if expected_report_sha256 is not None and report_hash != expected_report_sha256:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.REPORT_SHA256_MISMATCH,
                "report SHA-256 does not match expected evidence",
            )
        )
    try:
        tree = _load_and_validate_tree(report_payload)
    except VerifiedSnapshotPaperCycleReportSyntaxError as error:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.REPORT_SYNTAX_FAILURE,
                str(error),
            )
        )
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )
    except VerifiedSnapshotPaperCycleReportSchemaError as error:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.STRICT_SCHEMA_CANONICALIZATION_FAILURE,
                str(error),
            )
        )
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )

    result_tree = tree["result"]
    preparation_tree = result_tree["preparation"]
    try:
        snapshot_reference = _decode(
            preparation_tree["snapshot_reference"],
            VerifiedDailySnapshotReference,
            "$.result.preparation.snapshot_reference",
            construct=True,
        )
    except Exception:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.SNAPSHOT_LINKAGE_FAILURE,
                "snapshot reference cannot be reconstructed",
            )
        )
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )
    snapshot_verification = verify_daily_snapshot(
        snapshot_payload,
        calendar,
        expected_sha256=snapshot_reference.artifact_sha256,
        expected_byte_length=snapshot_reference.artifact_byte_length,
    )
    if (
        snapshot_verification.status is not DailySnapshotVerificationStatus.PASS
        or snapshot_verification.snapshot is None
        or snapshot_verification.snapshot.snapshot_id != snapshot_reference.snapshot_id
    ):
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.SNAPSHOT_LINKAGE_FAILURE,
                "original snapshot is not a complete matching PASS artifact",
            )
        )
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )

    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            preparation_request = _preparation_request_from_tree(preparation_tree)
            expected_preparation = prepare_verified_snapshot_paper_cycle(
                preparation_request,
                snapshot_verification,
                calendar,
            )
    except (
        VerifiedSnapshotPaperCyclePreparationError,
        VerifiedSnapshotPaperCycleReportSchemaError,
        TypeError,
        ValueError,
    ):
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
                "retained preparation inputs cannot be replayed",
            )
        )
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )
    if _encode(expected_preparation, "$.result.preparation") != preparation_tree:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.PREPARATION_RECONSTRUCTION_FAILURE,
                "retained prepared evidence differs from pure replay",
            )
        )
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )

    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            expected_result = execute_prepared_verified_snapshot_paper_cycle(
                expected_preparation
            )
    except VerifiedSnapshotPaperCycleExecutionError:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
                "disposable paper-runtime replay did not complete",
            )
        )
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )

    expected_tree = _encode(expected_result, "$.result")
    if expected_tree["runtime_result"] != result_tree["runtime_result"]:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
                "retained runtime stage evidence differs from exact replay",
            )
        )
    elif expected_tree != result_tree:
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.IDENTITY_STATE_RECONCILIATION_FAILURE,
                "retained adapter identity or public state differs from exact replay",
            )
        )
    elif (
        serialize_verified_snapshot_paper_cycle_result(expected_result)
        != report_payload
    ):
        diagnostics.append(
            _diagnostic(
                VerifiedSnapshotPaperCycleReportVerificationCode.STRICT_SCHEMA_CANONICALIZATION_FAILURE,
                "report bytes differ from replayed canonical serialization",
            )
        )
    if diagnostics:
        return _failed(
            report_length,
            report_hash,
            snapshot_length,
            snapshot_hash,
            diagnostics,
        )
    return VerifiedSnapshotPaperCycleReportVerificationResult(
        VerifiedSnapshotPaperCycleReportVerificationStatus.PASS,
        report_length,
        report_hash,
        snapshot_length,
        snapshot_hash,
        expected_result,
        (),
    )


def replay_verified_snapshot_paper_cycle_report(
    verification: VerifiedSnapshotPaperCycleReportVerificationResult,
) -> VerifiedSnapshotPaperCycleResult:
    """Expose reconstructed cycle evidence only from a complete PASS."""
    if type(verification) is not VerifiedSnapshotPaperCycleReportVerificationResult:
        raise VerifiedSnapshotPaperCycleReplayError(
            "verification must be an exact report verification result"
        )
    if not verification.passed or verification.result is None:
        raise VerifiedSnapshotPaperCycleReplayError(
            "cycle report replay requires a complete PASS verification"
        )
    return verification.result


def _preparation_request_from_tree(
    tree: dict[str, object],
) -> VerifiedSnapshotPaperCyclePreparationRequest:
    path = "$.result.preparation"
    return VerifiedSnapshotPaperCyclePreparationRequest(
        request_id=_decode(tree["request_id"], UUID, f"{path}.request_id", True),
        snapshot_reference=_decode(
            tree["snapshot_reference"],
            VerifiedDailySnapshotReference,
            f"{path}.snapshot_reference",
            True,
        ),
        account_state=_decode(
            tree["account_state"],
            VerifiedSnapshotAccountState,
            f"{path}.account_state",
            True,
        ),
        target=_decode(
            tree["target"],
            ExplicitQuantityTargetPortfolio,
            f"{path}.target",
            True,
        ),
        open_references=_decode(
            tree["open_references"],
            tuple[CallerAssertedNextSessionOpenReference, ...],
            f"{path}.open_references",
            True,
        ),
        policies=_decode(
            tree["policies"],
            VerifiedSnapshotPaperCyclePolicies,
            f"{path}.policies",
            True,
        ),
        planning_at=_decode(tree["planning_at"], datetime, f"{path}.planning_at", True),
        submitted_at=_decode(
            tree["submitted_at"], datetime, f"{path}.submitted_at", True
        ),
        filled_at=_decode(tree["filled_at"], datetime, f"{path}.filled_at", True),
        metadata=_decode(
            tree["metadata"],
            tuple[MetadataEntry, ...],
            f"{path}.metadata",
            True,
        ),
    )


def _load_and_validate_tree(payload: bytes) -> dict[str, object]:
    if type(payload) is not bytes:
        raise VerifiedSnapshotPaperCycleReportSyntaxError(
            "cycle report payload must be exact bytes"
        )
    if len(payload) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_BYTES:
        raise VerifiedSnapshotPaperCycleReportSyntaxError(
            "cycle report exceeds the 16 MiB limit"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise VerifiedSnapshotPaperCycleReportSyntaxError("UTF-8 BOM is not permitted")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerifiedSnapshotPaperCycleReportSyntaxError(
            "cycle report is not valid UTF-8"
        ) from error
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "cycle report must have exactly one final newline"
        )
    core = text[:-1]
    if not core or core != core.strip():
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "cycle report has leading or trailing whitespace"
        )
    try:
        tree = json.loads(
            core,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except VerifiedSnapshotPaperCycleReportSchemaError:
        raise
    except json.JSONDecodeError as error:
        raise VerifiedSnapshotPaperCycleReportSyntaxError(
            f"cycle report JSON is invalid at line {error.lineno} column {error.colno}"
        ) from error
    root = _object(tree, "$", _ROOT_FIELDS)
    if _exact_int(root["schema_version"], "$.schema_version") != 1:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "$.schema_version: unsupported schema version"
        )
    _decode(
        root["result"],
        VerifiedSnapshotPaperCycleResult,
        "$.result",
        construct=False,
    )
    if _canonical_json_bytes(root) != payload:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "cycle report JSON is not canonical"
        )
    return root


def _encode(value: object, path: str) -> object:
    if value is None or type(value) in (bool, int, str):
        _validate_scalar_bound(value, path)
        return value
    if type(value) is Decimal:
        text = canonical_decimal(value)
        if len(text) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_DECIMAL_CHARACTERS:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: Decimal text exceeds the schema bound"
            )
        return text
    if type(value) is UUID:
        return str(value)
    if type(value) is datetime:
        return canonical_timestamp(value.astimezone(UTC))
    if type(value) is date:
        return value.isoformat()
    if type(value) is Symbol:
        return str(value)
    if isinstance(value, Enum):
        if type(value.value) is not str:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: enum value must be text"
            )
        return value.value
    if isinstance(value, tuple):
        _validate_array_bound(value, path)
        return [_encode(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        _validate_array_bound(value, path)
        return [
            {
                "key": _encode(key, f"{path}[{index}].key"),
                "value": _encode(item, f"{path}[{index}].value"),
            }
            for index, (key, item) in enumerate(value.items())
        ]
    if is_dataclass(value) and not isinstance(value, type):
        model_type = type(value)
        names = _schema_fields(model_type, path)
        return {name: _encode(getattr(value, name), f"{path}.{name}") for name in names}
    raise VerifiedSnapshotPaperCycleReportSchemaError(
        f"{path}: unsupported report value type {type(value).__name__}"
    )


def _decode(
    value: object,
    expected: object,
    path: str,
    construct: bool,
) -> Any:
    origin = get_origin(expected)
    arguments = get_args(expected)
    if origin in (types.UnionType, Union):
        non_none = tuple(item for item in arguments if item is not type(None))
        if value is None and len(non_none) != len(arguments):
            return None
        if len(non_none) == 1:
            return _decode(value, non_none[0], path, construct)
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: unsupported union schema"
        )
    if origin is tuple:
        items = _array(value, path)
        _validate_array_bound(items, path)
        if len(arguments) != 2 or arguments[1] is not Ellipsis:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: unsupported tuple schema"
            )
        decoded = tuple(
            _decode(item, arguments[0], f"{path}[{index}]", construct)
            for index, item in enumerate(items)
        )
        return decoded
    if origin in (Mapping, dict):
        items = _array(value, path)
        _validate_array_bound(items, path)
        if len(arguments) != 2:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: unsupported mapping schema"
            )
        decoded_pairs = []
        for index, item in enumerate(items):
            entry_path = f"{path}[{index}]"
            entry = _object(item, entry_path, frozenset({"key", "value"}))
            decoded_pairs.append(
                (
                    _decode(entry["key"], arguments[0], f"{entry_path}.key", construct),
                    _decode(
                        entry["value"],
                        arguments[1],
                        f"{entry_path}.value",
                        construct,
                    ),
                )
            )
        if len({item[0] for item in decoded_pairs}) != len(decoded_pairs):
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: duplicate mapping key"
            )
        return dict(decoded_pairs)
    if expected is type(None):
        if value is not None:
            raise VerifiedSnapshotPaperCycleReportSchemaError(f"{path}: expected null")
        return None
    if expected is bool:
        if type(value) is not bool:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: expected boolean"
            )
        return value
    if expected is int:
        return _exact_int(value, path)
    if expected is str:
        text = _string(value, path)
        if path.rsplit(".", 1)[-1].endswith("sha256"):
            if _SHA256_PATTERN.fullmatch(text) is None:
                raise VerifiedSnapshotPaperCycleReportSchemaError(
                    f"{path}: expected lowercase SHA-256 text"
                )
        return text
    if expected is Decimal:
        return _canonical_decimal(value, path)
    if expected is UUID:
        return _canonical_uuid(value, path)
    if expected is datetime:
        return _canonical_timestamp(value, path)
    if expected is date:
        return _canonical_date(value, path)
    if expected is Symbol:
        return _canonical_symbol(value, path)
    if isinstance(expected, type) and issubclass(expected, Enum):
        text = _string(value, path)
        try:
            retained = expected(text)
        except ValueError as error:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: unsupported enum value"
            ) from error
        if retained.value != text:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"{path}: enum text is not canonical"
            )
        return retained
    if isinstance(expected, type) and is_dataclass(expected):
        names = _schema_fields(expected, path)
        item = _object(value, path, frozenset(names))
        hints = get_type_hints(expected)
        decoded = {
            name: _decode(
                item[name],
                hints[name],
                f"{path}.{name}",
                construct,
            )
            for name in names
        }
        if not construct:
            return decoded
        try:
            return expected(**decoded)
        except Exception as error:
            raise VerifiedSnapshotPaperCycleReportReconciliationError(
                f"{path}: immutable model does not reconcile"
            ) from error
    raise VerifiedSnapshotPaperCycleReportSchemaError(
        f"{path}: unsupported schema type"
    )


def _schema_fields(model_type: type[object], path: str) -> tuple[str, ...]:
    key = f"{model_type.__module__}.{model_type.__qualname__}"
    names = _MODEL_FIELDS.get(key)
    if names is None:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: model is not in report schema 1"
        )
    actual = tuple(item.name for item in fields(model_type))
    if actual != names:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: model fields differ from report schema 1"
        )
    return names


def _object(
    value: object,
    path: str,
    expected_fields: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        raise VerifiedSnapshotPaperCycleReportSchemaError(f"{path}: expected object")
    actual = frozenset(value)
    missing = sorted(expected_fields - actual)
    unknown = sorted(actual - expected_fields)
    if missing:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: missing fields: {', '.join(missing)}"
        )
    if unknown:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: unknown fields: {', '.join(unknown)}"
        )
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise VerifiedSnapshotPaperCycleReportSchemaError(f"{path}: expected array")
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str:
        raise VerifiedSnapshotPaperCycleReportSchemaError(f"{path}: expected string")
    if len(value) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_STRING_CHARACTERS:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: string exceeds the schema bound"
        )
    return value


def _exact_int(value: object, path: str) -> int:
    if type(value) is not int:
        raise VerifiedSnapshotPaperCycleReportSchemaError(f"{path}: expected integer")
    if abs(value) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_INTEGER:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: integer exceeds the schema bound"
        )
    return value


def _canonical_uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        retained = UUID(text)
    except ValueError as error:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: expected canonical UUID"
        ) from error
    if str(retained) != text:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: UUID is not canonical"
        )
    return retained


def _canonical_decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    if len(text) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_DECIMAL_CHARACTERS:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: Decimal text exceeds the schema bound"
        )
    try:
        retained = Decimal(text)
    except InvalidOperation as error:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: invalid Decimal"
        ) from error
    if not retained.is_finite() or canonical_decimal(retained) != text:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: expected exponent-free canonical Decimal string"
        )
    return retained


def _canonical_timestamp(value: object, path: str) -> datetime:
    text = _string(value, path)
    if _TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: expected canonical UTC timestamp"
        )
    try:
        retained = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: invalid UTC timestamp"
        ) from error
    if canonical_timestamp(retained) != text:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: timestamp is not canonical"
        )
    return retained


def _canonical_date(value: object, path: str) -> date:
    text = _string(value, path)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: expected canonical date"
        )
    try:
        retained = date.fromisoformat(text)
    except ValueError as error:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: invalid date"
        ) from error
    if retained.isoformat() != text:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: date is not canonical"
        )
    return retained


def _canonical_symbol(value: object, path: str) -> Symbol:
    text = _string(value, path)
    try:
        retained = Symbol(text)
    except (TypeError, ValueError) as error:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: invalid symbol"
        ) from error
    if str(retained) != text:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: symbol is not canonical"
        )
    return retained


def _canonical_json_bytes(tree: object) -> bytes:
    try:
        rendered = json.dumps(
            tree,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return (rendered + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            "cycle report cannot be rendered as canonical JSON"
        ) from error


def _validate_scalar_bound(value: object, path: str) -> None:
    if type(value) is int:
        _exact_int(value, path)
    elif type(value) is str:
        _string(value, path)


def _validate_array_bound(value: object, path: str) -> None:
    if len(value) > MAX_VERIFIED_SNAPSHOT_PAPER_CYCLE_REPORT_ARRAY_ITEMS:  # type: ignore[arg-type]
        raise VerifiedSnapshotPaperCycleReportSchemaError(
            f"{path}: array exceeds the schema bound"
        )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise VerifiedSnapshotPaperCycleReportSchemaError(
                f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise VerifiedSnapshotPaperCycleReportSchemaError(
        f"nonstandard JSON constant is not permitted: {value}"
    )


def _reject_float(value: str) -> None:
    raise VerifiedSnapshotPaperCycleReportSchemaError(
        f"JSON floating-point number is not permitted: {value}"
    )


def _validate_expected_sha256(value: str | None) -> None:
    if value is not None and (
        type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise VerifiedSnapshotPaperCycleReportVerificationError(
            "expected_report_sha256 must be lowercase SHA-256 text or None"
        )


def _validate_expected_byte_length(value: int | None) -> None:
    if value is not None and (type(value) is not int or value < 0):
        raise VerifiedSnapshotPaperCycleReportVerificationError(
            "expected_report_byte_length must be a nonnegative integer or None"
        )


def _diagnostic(
    code: VerifiedSnapshotPaperCycleReportVerificationCode,
    detail: str,
) -> VerifiedSnapshotPaperCycleReportVerificationDiagnostic:
    return VerifiedSnapshotPaperCycleReportVerificationDiagnostic(code, detail)


def _failed(
    report_length: int,
    report_hash: str,
    snapshot_length: int,
    snapshot_hash: str,
    diagnostics: list[VerifiedSnapshotPaperCycleReportVerificationDiagnostic],
) -> VerifiedSnapshotPaperCycleReportVerificationResult:
    return VerifiedSnapshotPaperCycleReportVerificationResult(
        VerifiedSnapshotPaperCycleReportVerificationStatus.FAIL,
        report_length,
        report_hash,
        snapshot_length,
        snapshot_hash,
        None,
        tuple(diagnostics),
    )
