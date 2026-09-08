"""Canonical checkpointed-cycle reports and offline one-cycle replay proof."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.domain import OrderFill, Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.ledger import CompactPaperLedgerPosition, CompactPaperLedgerState
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    canonical_decimal,
    verify_daily_snapshot,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.portfolio import MetadataEntry, PortfolioConstraints
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode,
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    CheckpointedVerifiedSnapshotPaperCycleResult,
    CheckpointedVerifiedSnapshotPaperCycleStatus,
    VerifiedPriorCheckpoint,
    execute_checkpointed_verified_snapshot_paper_cycle,
    verified_prior_from_genesis,
)
from trading_bot.runtime.exceptions import (
    CheckpointedPaperCycleReportReconciliationError,
    CheckpointedPaperCycleReportSchemaError,
    CheckpointedPaperCycleReportSyntaxError,
    CheckpointedPaperCycleReportVerificationError,
)
from trading_bot.runtime.paper_account_checkpoint import (
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    CheckpointedPaperCycleReportReference,
    PriorPaperAccountCheckpointReference,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    ExplicitQuantityTarget,
    ExplicitQuantityTargetPortfolio,
    VerifiedDailySnapshotReference,
    VerifiedSnapshotPaperCyclePolicies,
)

CHECKPOINTED_PAPER_CYCLE_REPORT_SCHEMA_VERSION = 1
CHECKPOINTED_PAPER_CYCLE_REPORT_MATERIAL_VERSION = "checkpointed-paper-cycle-report-v1"
CHECKPOINTED_PAPER_CYCLE_REPORT_NAMESPACE = UUID("6ea73a26-8cf5-5b3d-bbea-aea09398f1db")
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES = 16 * 1024 * 1024
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_ARRAY_ITEMS = 20_000
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_STRING_CHARACTERS = 16_384
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_DECIMAL_CHARACTERS = 4096
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_INTEGER = (1 << 63) - 1
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA = 100
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_KEY_CHARACTERS = 128
MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_VALUE_CHARACTERS = 4096

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$"
)
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_ARITHMETIC_CONTEXT = Context(prec=4096, Emax=999_999, Emin=-999_999)
_ROOT_FIELDS = frozenset({"schema_version", "report"})
_REPORT_FIELDS = frozenset({"report_id", "evidence"})
_EVIDENCE_FIELDS = frozenset(
    {
        "cycle_result_id",
        "prior_checkpoint",
        "prior_lineage_id",
        "prior_account_state_id",
        "application_id",
        "restored_ledger_state_id",
        "opening_compact_state",
        "final_compact_state",
        "opening_realized_profit_loss",
        "final_realized_profit_loss",
        "preparation_id",
        "snapshot_audit_sha256",
        "snapshot_canonical_bars_sha256",
        "runtime_result_id",
        "runtime_application_result_id",
        "pre_engine_state_id",
        "pre_ledger_state_id",
        "post_engine_state_id",
        "post_ledger_state_id",
        "fills",
        "status",
        "diagnostic_codes",
        "request",
    }
)
_REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "snapshot_reference",
        "target",
        "open_references",
        "policies",
        "planning_at",
        "submitted_at",
        "filled_at",
        "metadata",
    }
)
_REFERENCE_FIELDS = frozenset(
    {"checkpoint_id", "sequence", "artifact_sha256", "artifact_byte_length"}
)
_SNAPSHOT_FIELDS = frozenset({"snapshot_id", "artifact_sha256", "artifact_byte_length"})
_TARGET_FIELDS = frozenset({"target_id", "quantities", "target_cash"})
_TARGET_QUANTITY_FIELDS = frozenset({"symbol", "quantity"})
_OPEN_FIELDS = frozenset({"symbol", "session_date", "price"})
_POLICY_FIELDS = frozenset(
    {
        "rebalance_assumptions",
        "portfolio_constraints",
        "proposal_policy",
        "proposal_confidence",
        "risk_limits",
        "risk_policy",
        "fill_policy",
        "trading_enabled",
    }
)
_ASSUMPTIONS_FIELDS = frozenset(
    {
        "fixed_commission",
        "allow_fractional_quantities",
        "quantity_increment",
        "minimum_trade_notional",
        "minimum_trade_quantity",
        "target_weight_tolerance",
        "additional_execution_cash_buffer",
        "use_planned_sell_proceeds",
    }
)
_CONSTRAINTS_FIELDS = frozenset(
    {
        "minimum_cash_weight",
        "maximum_cash_weight",
        "maximum_position_weight",
        "maximum_one_way_rebalance_turnover",
        "minimum_position_weight",
        "long_only",
        "allow_leverage",
    }
)
_PROPOSAL_POLICY_FIELDS = frozenset({"allow_partial_plans"})
_RISK_LIMITS_FIELDS = frozenset(
    {
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
    }
)
_RISK_POLICY_FIELDS = frozenset({"allow_sell_proceeds_for_later_buys"})
_FILL_POLICY_FIELDS = frozenset({"slippage_basis_points", "fixed_commission"})
_METADATA_FIELDS = frozenset({"key", "value"})
_COMPACT_STATE_FIELDS = frozenset(
    {"compact_state_id", "as_of", "cash", "positions", "realized_profit_loss"}
)
_POSITION_FIELDS = frozenset({"symbol", "quantity", "total_cost_basis", "average_cost"})
_FILL_FIELDS = frozenset(
    {
        "fill_id",
        "order_id",
        "symbol",
        "side",
        "quantity",
        "price",
        "commission",
        "filled_at",
    }
)


class CheckpointedPaperCycleReportVerificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class CheckpointedPaperCycleReportVerificationCode(StrEnum):
    REPORT_BYTE_LENGTH_MISMATCH = "REPORT_BYTE_LENGTH_MISMATCH"
    REPORT_SHA256_MISMATCH = "REPORT_SHA256_MISMATCH"
    REPORT_SYNTAX_FAILURE = "REPORT_SYNTAX_FAILURE"
    STRICT_SCHEMA_CANONICALIZATION_FAILURE = "STRICT_SCHEMA_CANONICALIZATION_FAILURE"
    PRIOR_CHECKPOINT_LINKAGE_FAILURE = "PRIOR_CHECKPOINT_LINKAGE_FAILURE"
    SNAPSHOT_LINKAGE_FAILURE = "SNAPSHOT_LINKAGE_FAILURE"
    EXECUTION_REPLAY_FAILURE = "EXECUTION_REPLAY_FAILURE"
    RESULT_RECONCILIATION_FAILURE = "RESULT_RECONCILIATION_FAILURE"


@dataclass(frozen=True, slots=True)
class CheckpointedPaperCycleReportEvidence:
    """Complete replay inputs and identity-bearing checkpointed-cycle evidence."""

    cycle_result_id: UUID
    prior_checkpoint: PriorPaperAccountCheckpointReference
    prior_lineage_id: UUID
    prior_account_state_id: UUID
    application_id: UUID
    restored_ledger_state_id: UUID
    opening_compact_state: CompactPaperLedgerState
    final_compact_state: CompactPaperLedgerState
    opening_realized_profit_loss: Decimal
    final_realized_profit_loss: Decimal
    preparation_id: UUID
    snapshot_audit_sha256: str
    snapshot_canonical_bars_sha256: str
    runtime_result_id: UUID
    runtime_application_result_id: UUID
    pre_engine_state_id: UUID
    pre_ledger_state_id: UUID
    post_engine_state_id: UUID
    post_ledger_state_id: UUID
    fills: tuple[OrderFill, ...]
    status: CheckpointedVerifiedSnapshotPaperCycleStatus
    diagnostic_codes: tuple[CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode, ...]
    request: CheckpointedVerifiedSnapshotPaperCycleRequest

    def __post_init__(self) -> None:
        for name in (
            "cycle_result_id",
            "prior_lineage_id",
            "prior_account_state_id",
            "application_id",
            "restored_ledger_state_id",
            "preparation_id",
            "runtime_result_id",
            "runtime_application_result_id",
            "pre_engine_state_id",
            "pre_ledger_state_id",
            "post_engine_state_id",
            "post_ledger_state_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise CheckpointedPaperCycleReportReconciliationError(
                    f"{name} must be an exact UUID"
                )
        for name, expected in (
            ("prior_checkpoint", PriorPaperAccountCheckpointReference),
            ("opening_compact_state", CompactPaperLedgerState),
            ("final_compact_state", CompactPaperLedgerState),
            ("request", CheckpointedVerifiedSnapshotPaperCycleRequest),
        ):
            if type(getattr(self, name)) is not expected:
                raise CheckpointedPaperCycleReportReconciliationError(
                    f"{name} has an invalid type"
                )
        if type(self.status) is not CheckpointedVerifiedSnapshotPaperCycleStatus:
            raise CheckpointedPaperCycleReportReconciliationError("status is invalid")
        for name in ("opening_realized_profit_loss", "final_realized_profit_loss"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite():
                raise CheckpointedPaperCycleReportReconciliationError(
                    f"{name} must be a finite Decimal"
                )
        for name in ("snapshot_audit_sha256", "snapshot_canonical_bars_sha256"):
            if _SHA256_PATTERN.fullmatch(getattr(self, name)) is None:
                raise CheckpointedPaperCycleReportReconciliationError(
                    f"{name} must be lowercase SHA-256 text"
                )
        fills = _tuple(self.fills, OrderFill, "fills")
        codes = _tuple(
            self.diagnostic_codes,
            CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode,
            "diagnostic_codes",
        )
        expected_codes = (
            ()
            if self.status is CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED
            else (CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode.NO_ACTION,)
        )
        if codes != expected_codes:
            raise CheckpointedPaperCycleReportReconciliationError(
                "status and diagnostic codes do not reconcile"
            )
        if (
            self.status is CheckpointedVerifiedSnapshotPaperCycleStatus.APPLIED
        ) != bool(fills):
            raise CheckpointedPaperCycleReportReconciliationError(
                "status and fills do not reconcile"
            )
        if (
            self.opening_realized_profit_loss
            != self.opening_compact_state.realized_profit_loss
            or self.final_realized_profit_loss
            != self.final_compact_state.realized_profit_loss
            or self.final_compact_state.as_of != self.request.filled_at
        ):
            raise CheckpointedPaperCycleReportReconciliationError(
                "retained compact state and realized P&L do not reconcile"
            )
        _validate_request_bounds(self.request)
        object.__setattr__(self, "fills", fills)
        object.__setattr__(self, "diagnostic_codes", codes)


@dataclass(frozen=True, slots=True)
class CheckpointedPaperCycleReport:
    """One canonical report for immutable checkpointed-cycle evidence."""

    report_id: UUID
    evidence: CheckpointedPaperCycleReportEvidence

    def __post_init__(self) -> None:
        if (
            type(self.report_id) is not UUID
            or type(self.evidence) is not CheckpointedPaperCycleReportEvidence
        ):
            raise CheckpointedPaperCycleReportReconciliationError(
                "report fields are invalid"
            )
        if self.report_id != derive_checkpointed_paper_cycle_report_id(
            self.evidence.cycle_result_id
        ):
            raise CheckpointedPaperCycleReportReconciliationError(
                "report_id does not match canonical material"
            )


@dataclass(frozen=True, slots=True)
class CheckpointedPaperCycleReportVerificationDiagnostic:
    code: CheckpointedPaperCycleReportVerificationCode
    detail: str

    def __post_init__(self) -> None:
        if type(self.code) is not CheckpointedPaperCycleReportVerificationCode:
            raise CheckpointedPaperCycleReportVerificationError(
                "diagnostic code invalid"
            )
        if type(self.detail) is not str or not self.detail.strip():
            raise CheckpointedPaperCycleReportVerificationError(
                "diagnostic detail invalid"
            )


@dataclass(frozen=True, slots=True)
class CheckpointedPaperCycleReportVerificationResult:
    status: CheckpointedPaperCycleReportVerificationStatus
    report_byte_length: int
    report_sha256: str
    snapshot_byte_length: int
    snapshot_sha256: str
    report: CheckpointedPaperCycleReport | None
    cycle_result: CheckpointedVerifiedSnapshotPaperCycleResult | None
    diagnostics: tuple[CheckpointedPaperCycleReportVerificationDiagnostic, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not CheckpointedPaperCycleReportVerificationStatus:
            raise CheckpointedPaperCycleReportVerificationError("status invalid")
        for name in ("report_byte_length", "snapshot_byte_length"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise CheckpointedPaperCycleReportVerificationError(f"{name} invalid")
        for name in ("report_sha256", "snapshot_sha256"):
            if _SHA256_PATTERN.fullmatch(getattr(self, name)) is None:
                raise CheckpointedPaperCycleReportVerificationError(f"{name} invalid")
        diagnostics = _tuple(
            self.diagnostics,
            CheckpointedPaperCycleReportVerificationDiagnostic,
            "diagnostics",
        )
        complete = (
            type(self.report) is CheckpointedPaperCycleReport
            and type(self.cycle_result) is CheckpointedVerifiedSnapshotPaperCycleResult
        )
        if self.status is CheckpointedPaperCycleReportVerificationStatus.PASS:
            if not complete or diagnostics:
                raise CheckpointedPaperCycleReportVerificationError(
                    "PASS must expose only complete reconstructed evidence"
                )
        elif complete or not diagnostics:
            raise CheckpointedPaperCycleReportVerificationError(
                "FAIL cannot expose reconstructed evidence"
            )
        object.__setattr__(self, "diagnostics", diagnostics)


def derive_checkpointed_paper_cycle_report_id(cycle_result_id: UUID) -> UUID:
    """Derive a report identity without binding artifact bytes or paths."""
    if type(cycle_result_id) is not UUID:
        raise TypeError("cycle_result_id must be an exact UUID")
    return uuid5(
        CHECKPOINTED_PAPER_CYCLE_REPORT_NAMESPACE,
        _framed(
            (CHECKPOINTED_PAPER_CYCLE_REPORT_MATERIAL_VERSION, str(cycle_result_id))
        ),
    )


def checkpointed_paper_cycle_report_from_result(
    result: CheckpointedVerifiedSnapshotPaperCycleResult,
) -> CheckpointedPaperCycleReport:
    """Retain canonical one-edge replay evidence from a completed cycle result."""
    if type(result) is not CheckpointedVerifiedSnapshotPaperCycleResult:
        raise TypeError("result must be an exact checkpointed cycle result")
    request = _request_from_result(result)
    evidence = CheckpointedPaperCycleReportEvidence(
        result.result_id,
        PriorPaperAccountCheckpointReference(
            result.prior_checkpoint_id,
            result.prior_sequence,
            result.prior_checkpoint_sha256,
            result.prior_checkpoint_byte_length,
        ),
        result.prior_lineage_id,
        result.prior_account_state_id,
        result.application_id,
        result.restoration_evidence.restored_ledger_state_id,
        result.opening_compact_state,
        result.final_compact_state,
        result.opening_realized_profit_loss,
        result.final_realized_profit_loss,
        result.preparation.preparation_id,
        result.preparation.snapshot_audit_sha256,
        result.preparation.snapshot_canonical_bars_sha256,
        result.runtime_result.result_id,
        result.runtime_result.application_result.result_id,
        result.pre_engine_state_id,
        result.pre_ledger_state_id,
        result.post_engine_state_id,
        result.post_ledger_state_id,
        result.cycle_fills,
        result.status,
        tuple(item.code for item in result.diagnostics),
        request,
    )
    return CheckpointedPaperCycleReport(
        derive_checkpointed_paper_cycle_report_id(result.result_id), evidence
    )


def serialize_checkpointed_paper_cycle_report(
    report: CheckpointedPaperCycleReport,
) -> bytes:
    """Serialize immutable checkpointed-cycle evidence as strict canonical JSON."""
    if type(report) is not CheckpointedPaperCycleReport:
        raise CheckpointedPaperCycleReportSchemaError("report must be exact")
    with localcontext(_ARITHMETIC_CONTEXT):
        payload = _canonical_json_bytes(
            {
                "schema_version": CHECKPOINTED_PAPER_CYCLE_REPORT_SCHEMA_VERSION,
                "report": {
                    "report_id": str(report.report_id),
                    "evidence": _evidence_tree(report.evidence),
                },
            }
        )
    if len(payload) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES:
        raise CheckpointedPaperCycleReportSchemaError("report exceeds byte bound")
    return payload


def serialize_checkpointed_verified_snapshot_paper_cycle_request(
    request: CheckpointedVerifiedSnapshotPaperCycleRequest,
) -> bytes:
    """Serialize one normalized checkpointed-cycle request canonically."""
    if type(request) is not CheckpointedVerifiedSnapshotPaperCycleRequest:
        raise CheckpointedPaperCycleReportReconciliationError(
            "request must be an exact CheckpointedVerifiedSnapshotPaperCycleRequest"
        )
    _validate_request_bounds(request)
    return _canonical_json_bytes(_request_tree(request))


def parse_checkpointed_verified_snapshot_paper_cycle_request(
    payload: bytes,
) -> CheckpointedVerifiedSnapshotPaperCycleRequest:
    """Parse one standalone canonical checkpointed-cycle request."""
    tree = _load_json(payload)
    request = _request(tree)
    _validate_request_bounds(request)
    if serialize_checkpointed_verified_snapshot_paper_cycle_request(request) != payload:
        raise CheckpointedPaperCycleReportSchemaError("request bytes are not canonical")
    return request


def parse_checkpointed_paper_cycle_report(
    payload: bytes,
) -> CheckpointedPaperCycleReport:
    """Strictly parse canonical checkpointed-cycle report bytes."""
    tree = _load_json(payload)
    root = _object(tree, _ROOT_FIELDS, "root")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != CHECKPOINTED_PAPER_CYCLE_REPORT_SCHEMA_VERSION
    ):
        raise CheckpointedPaperCycleReportSchemaError("unsupported report schema")
    raw = _object(root["report"], _REPORT_FIELDS, "report")
    try:
        report = CheckpointedPaperCycleReport(
            _uuid(raw["report_id"], "report.report_id"),
            _evidence(raw["evidence"]),
        )
    except (TypeError, ValueError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            "immutable report evidence does not reconcile"
        ) from error
    if serialize_checkpointed_paper_cycle_report(report) != payload:
        raise CheckpointedPaperCycleReportSchemaError("report bytes are not canonical")
    return report


def checkpointed_paper_cycle_report_reference(
    report_payload: bytes,
) -> CheckpointedPaperCycleReportReference:
    """Create transport evidence for one already-canonical report artifact."""
    report = parse_checkpointed_paper_cycle_report(report_payload)
    return CheckpointedPaperCycleReportReference(
        report.report_id,
        report.evidence.cycle_result_id,
        sha256(report_payload).hexdigest(),
        len(report_payload),
    )


def verify_checkpointed_paper_cycle_report(
    report_payload: bytes,
    prior_checkpoint_payload: bytes,
    snapshot_payload: bytes,
    calendar: IdentifiedMarketCalendar,
    *,
    expected_report_sha256: str | None = None,
    expected_report_byte_length: int | None = None,
    verified_prior: VerifiedPriorCheckpoint | None = None,
) -> CheckpointedPaperCycleReportVerificationResult:
    """Verify a report by restoring its prior checkpoint and replaying once."""
    if (
        type(report_payload) is not bytes
        or type(prior_checkpoint_payload) is not bytes
        or type(snapshot_payload) is not bytes
    ):
        raise CheckpointedPaperCycleReportVerificationError(
            "artifact payloads must be exact bytes"
        )
    _expected_sha256(expected_report_sha256)
    _expected_length(expected_report_byte_length)
    report_length = len(report_payload)
    report_hash = sha256(report_payload).hexdigest()
    snapshot_length = len(snapshot_payload)
    snapshot_hash = sha256(snapshot_payload).hexdigest()
    diagnostics: list[CheckpointedPaperCycleReportVerificationDiagnostic] = []
    if (
        expected_report_byte_length is not None
        and report_length != expected_report_byte_length
    ):
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.REPORT_BYTE_LENGTH_MISMATCH,
                "report byte length differs from supplied artifact evidence",
            )
        )
    if expected_report_sha256 is not None and report_hash != expected_report_sha256:
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.REPORT_SHA256_MISMATCH,
                "report SHA-256 differs from supplied artifact evidence",
            )
        )
    try:
        report = parse_checkpointed_paper_cycle_report(report_payload)
    except CheckpointedPaperCycleReportSyntaxError as error:
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.REPORT_SYNTAX_FAILURE,
                str(error),
            )
        )
        return _failed(
            report_length, report_hash, snapshot_length, snapshot_hash, diagnostics
        )
    except CheckpointedPaperCycleReportSchemaError as error:
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.STRICT_SCHEMA_CANONICALIZATION_FAILURE,
                str(error),
            )
        )
        return _failed(
            report_length, report_hash, snapshot_length, snapshot_hash, diagnostics
        )
    evidence = report.evidence
    try:
        if type(verified_prior) is VerifiedPriorCheckpoint:
            prior = verified_prior
            if (
                sha256(prior_checkpoint_payload).hexdigest() != prior.checkpoint_sha256
                or len(prior_checkpoint_payload) != prior.checkpoint_byte_length
            ):
                prior = None
        else:
            prior = verified_prior_from_genesis(
                verify_genesis_paper_account_checkpoint(
                    prior_checkpoint_payload,
                    expected_checkpoint_sha256=evidence.prior_checkpoint.artifact_sha256,
                    expected_checkpoint_byte_length=evidence.prior_checkpoint.artifact_byte_length,
                )
            )
    except Exception:
        prior = None
    if (
        prior is None
        or prior.checkpoint_id != evidence.prior_checkpoint.checkpoint_id
        or prior.sequence != evidence.prior_checkpoint.sequence
        or prior.lineage_id != evidence.prior_lineage_id
        or prior.checkpoint_sha256 != evidence.prior_checkpoint.artifact_sha256
        or prior.checkpoint_byte_length
        != evidence.prior_checkpoint.artifact_byte_length
    ):
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.PRIOR_CHECKPOINT_LINKAGE_FAILURE,
                "prior checkpoint is not a complete matching PASS artifact",
            )
        )
        return _failed(
            report_length, report_hash, snapshot_length, snapshot_hash, diagnostics
        )
    snapshot = verify_daily_snapshot(
        snapshot_payload,
        calendar,
        expected_sha256=evidence.request.snapshot_reference.artifact_sha256,
        expected_byte_length=evidence.request.snapshot_reference.artifact_byte_length,
    )
    if (
        snapshot.status is not DailySnapshotVerificationStatus.PASS
        or snapshot.snapshot is None
        or snapshot.diagnostics
        or snapshot.snapshot.snapshot_id
        != evidence.request.snapshot_reference.snapshot_id
    ):
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.SNAPSHOT_LINKAGE_FAILURE,
                "snapshot is not a complete matching PASS artifact",
            )
        )
        return _failed(
            report_length, report_hash, snapshot_length, snapshot_hash, diagnostics
        )
    try:
        with localcontext(_ARITHMETIC_CONTEXT):
            replay = execute_checkpointed_verified_snapshot_paper_cycle(
                evidence.request,
                prior,
                snapshot,
                calendar,
            )
    except Exception:
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.EXECUTION_REPLAY_FAILURE,
                "checkpointed cycle cannot be replayed exactly",
            )
        )
        return _failed(
            report_length, report_hash, snapshot_length, snapshot_hash, diagnostics
        )
    if checkpointed_paper_cycle_report_from_result(replay).evidence != evidence:
        diagnostics.append(
            _diagnostic(
                CheckpointedPaperCycleReportVerificationCode.RESULT_RECONCILIATION_FAILURE,
                "replayed checkpointed cycle differs from retained report evidence",
            )
        )
        return _failed(
            report_length, report_hash, snapshot_length, snapshot_hash, diagnostics
        )
    return CheckpointedPaperCycleReportVerificationResult(
        CheckpointedPaperCycleReportVerificationStatus.PASS,
        report_length,
        report_hash,
        snapshot_length,
        snapshot_hash,
        report,
        replay,
        (),
    )


def _request_from_result(
    result: CheckpointedVerifiedSnapshotPaperCycleResult,
) -> CheckpointedVerifiedSnapshotPaperCycleRequest:
    preparation = result.preparation
    return CheckpointedVerifiedSnapshotPaperCycleRequest(
        preparation.request_id,
        preparation.snapshot_reference,
        preparation.target,
        preparation.open_references,
        preparation.policies,
        preparation.planning_at,
        preparation.submitted_at,
        preparation.filled_at,
        preparation.metadata[:-4],
    )


def _evidence_tree(evidence: CheckpointedPaperCycleReportEvidence) -> dict[str, object]:
    return {
        "cycle_result_id": str(evidence.cycle_result_id),
        "prior_checkpoint": _prior_tree(evidence.prior_checkpoint),
        "prior_lineage_id": str(evidence.prior_lineage_id),
        "prior_account_state_id": str(evidence.prior_account_state_id),
        "application_id": str(evidence.application_id),
        "restored_ledger_state_id": str(evidence.restored_ledger_state_id),
        "opening_compact_state": _compact_tree(evidence.opening_compact_state),
        "final_compact_state": _compact_tree(evidence.final_compact_state),
        "opening_realized_profit_loss": canonical_decimal(
            evidence.opening_realized_profit_loss
        ),
        "final_realized_profit_loss": canonical_decimal(
            evidence.final_realized_profit_loss
        ),
        "preparation_id": str(evidence.preparation_id),
        "snapshot_audit_sha256": evidence.snapshot_audit_sha256,
        "snapshot_canonical_bars_sha256": evidence.snapshot_canonical_bars_sha256,
        "runtime_result_id": str(evidence.runtime_result_id),
        "runtime_application_result_id": str(evidence.runtime_application_result_id),
        "pre_engine_state_id": str(evidence.pre_engine_state_id),
        "pre_ledger_state_id": str(evidence.pre_ledger_state_id),
        "post_engine_state_id": str(evidence.post_engine_state_id),
        "post_ledger_state_id": str(evidence.post_ledger_state_id),
        "fills": [_fill_tree(fill) for fill in evidence.fills],
        "status": evidence.status.value,
        "diagnostic_codes": [item.value for item in evidence.diagnostic_codes],
        "request": _request_tree(evidence.request),
    }


def _prior_tree(reference: PriorPaperAccountCheckpointReference) -> dict[str, object]:
    return {
        "checkpoint_id": str(reference.checkpoint_id),
        "sequence": reference.sequence,
        "artifact_sha256": reference.artifact_sha256,
        "artifact_byte_length": reference.artifact_byte_length,
    }


def _compact_tree(state: CompactPaperLedgerState) -> dict[str, object]:
    return {
        "compact_state_id": str(state.compact_state_id),
        "as_of": canonical_timestamp(state.as_of),
        "cash": canonical_decimal(state.cash),
        "positions": [_position_tree(item) for item in state.positions],
        "realized_profit_loss": canonical_decimal(state.realized_profit_loss),
    }


def _position_tree(position: CompactPaperLedgerPosition) -> dict[str, object]:
    return {
        "symbol": str(position.symbol),
        "quantity": canonical_decimal(position.quantity),
        "total_cost_basis": canonical_decimal(position.total_cost_basis),
        "average_cost": canonical_decimal(position.average_cost),
    }


def _fill_tree(fill: OrderFill) -> dict[str, object]:
    return {
        "fill_id": str(fill.fill_id),
        "order_id": str(fill.order_id),
        "symbol": str(fill.symbol),
        "side": fill.side.value,
        "quantity": canonical_decimal(fill.quantity),
        "price": canonical_decimal(fill.price),
        "commission": canonical_decimal(fill.commission),
        "filled_at": canonical_timestamp(fill.filled_at),
    }


def _request_tree(
    request: CheckpointedVerifiedSnapshotPaperCycleRequest,
) -> dict[str, object]:
    return {
        "request_id": str(request.request_id),
        "snapshot_reference": {
            "snapshot_id": str(request.snapshot_reference.snapshot_id),
            "artifact_sha256": request.snapshot_reference.artifact_sha256,
            "artifact_byte_length": request.snapshot_reference.artifact_byte_length,
        },
        "target": {
            "target_id": str(request.target.target_id),
            "quantities": [
                {
                    "symbol": str(item.symbol),
                    "quantity": canonical_decimal(item.quantity),
                }
                for item in request.target.quantities
            ],
            "target_cash": canonical_decimal(request.target.target_cash),
        },
        "open_references": [
            {
                "symbol": str(item.symbol),
                "session_date": item.session.session_date.isoformat(),
                "price": canonical_decimal(item.caller_asserted_open_reference_price),
            }
            for item in request.open_references
        ],
        "policies": _policies_tree(request.policies),
        "planning_at": canonical_timestamp(request.planning_at),
        "submitted_at": canonical_timestamp(request.submitted_at),
        "filled_at": canonical_timestamp(request.filled_at),
        "metadata": [
            {"key": item.key, "value": item.value} for item in request.metadata
        ],
    }


def _policies_tree(policies: VerifiedSnapshotPaperCyclePolicies) -> dict[str, object]:
    assumptions = policies.rebalance_assumptions
    constraints = policies.portfolio_constraints
    limits = policies.risk_limits
    return {
        "rebalance_assumptions": {
            "fixed_commission": canonical_decimal(assumptions.fixed_commission),
            "allow_fractional_quantities": assumptions.allow_fractional_quantities,
            "quantity_increment": canonical_decimal(assumptions.quantity_increment),
            "minimum_trade_notional": canonical_decimal(
                assumptions.minimum_trade_notional
            ),
            "minimum_trade_quantity": canonical_decimal(
                assumptions.minimum_trade_quantity
            ),
            "target_weight_tolerance": canonical_decimal(
                assumptions.target_weight_tolerance
            ),
            "additional_execution_cash_buffer": canonical_decimal(
                assumptions.additional_execution_cash_buffer
            ),
            "use_planned_sell_proceeds": assumptions.use_planned_sell_proceeds,
        },
        "portfolio_constraints": None
        if constraints is None
        else {
            "minimum_cash_weight": canonical_decimal(constraints.minimum_cash_weight),
            "maximum_cash_weight": canonical_decimal(constraints.maximum_cash_weight),
            "maximum_position_weight": canonical_decimal(
                constraints.maximum_position_weight
            ),
            "maximum_one_way_rebalance_turnover": None
            if constraints.maximum_one_way_rebalance_turnover is None
            else canonical_decimal(constraints.maximum_one_way_rebalance_turnover),
            "minimum_position_weight": None
            if constraints.minimum_position_weight is None
            else canonical_decimal(constraints.minimum_position_weight),
            "long_only": constraints.long_only,
            "allow_leverage": constraints.allow_leverage,
        },
        "proposal_policy": {
            "allow_partial_plans": policies.proposal_policy.allow_partial_plans
        },
        "proposal_confidence": None
        if policies.proposal_confidence is None
        else canonical_decimal(policies.proposal_confidence),
        "risk_limits": {
            "max_position_percent": canonical_decimal(limits.max_position_percent),
            "max_total_exposure_percent": canonical_decimal(
                limits.max_total_exposure_percent
            ),
            "max_order_notional": None
            if limits.max_order_notional is None
            else canonical_decimal(limits.max_order_notional),
            "max_new_position_percent": None
            if limits.max_new_position_percent is None
            else canonical_decimal(limits.max_new_position_percent),
            "minimum_cash_reserve_percent": canonical_decimal(
                limits.minimum_cash_reserve_percent
            ),
            "allow_fractional_shares": limits.allow_fractional_shares,
            "fractional_increment": canonical_decimal(limits.fractional_increment),
            "allow_buying": limits.allow_buying,
            "allow_selling": limits.allow_selling,
            "estimated_commission": canonical_decimal(limits.estimated_commission),
        },
        "risk_policy": {
            "allow_sell_proceeds_for_later_buys": (
                policies.risk_policy.allow_sell_proceeds_for_later_buys
            )
        },
        "fill_policy": {
            "slippage_basis_points": canonical_decimal(
                policies.fill_policy.slippage_basis_points
            ),
            "fixed_commission": canonical_decimal(
                policies.fill_policy.fixed_commission
            ),
        },
        "trading_enabled": policies.trading_enabled,
    }


def _evidence(value: object) -> CheckpointedPaperCycleReportEvidence:
    raw = _object(value, _EVIDENCE_FIELDS, "evidence")
    request = _request(raw["request"])
    fills = tuple(
        _fill(item, f"evidence.fills[{index}]")
        for index, item in enumerate(_array(raw["fills"], "evidence.fills"))
    )
    codes = tuple(
        _enum(
            item,
            CheckpointedVerifiedSnapshotPaperCycleDiagnosticCode,
            f"evidence.diagnostic_codes[{index}]",
        )
        for index, item in enumerate(
            _array(raw["diagnostic_codes"], "evidence.diagnostic_codes")
        )
    )
    return CheckpointedPaperCycleReportEvidence(
        _uuid(raw["cycle_result_id"], "evidence.cycle_result_id"),
        _prior(raw["prior_checkpoint"]),
        _uuid(raw["prior_lineage_id"], "evidence.prior_lineage_id"),
        _uuid(raw["prior_account_state_id"], "evidence.prior_account_state_id"),
        _uuid(raw["application_id"], "evidence.application_id"),
        _uuid(raw["restored_ledger_state_id"], "evidence.restored_ledger_state_id"),
        _compact(raw["opening_compact_state"], "evidence.opening_compact_state"),
        _compact(raw["final_compact_state"], "evidence.final_compact_state"),
        _decimal(
            raw["opening_realized_profit_loss"], "evidence.opening_realized_profit_loss"
        ),
        _decimal(
            raw["final_realized_profit_loss"], "evidence.final_realized_profit_loss"
        ),
        _uuid(raw["preparation_id"], "evidence.preparation_id"),
        _sha(raw["snapshot_audit_sha256"], "evidence.snapshot_audit_sha256"),
        _sha(
            raw["snapshot_canonical_bars_sha256"],
            "evidence.snapshot_canonical_bars_sha256",
        ),
        _uuid(raw["runtime_result_id"], "evidence.runtime_result_id"),
        _uuid(
            raw["runtime_application_result_id"],
            "evidence.runtime_application_result_id",
        ),
        _uuid(raw["pre_engine_state_id"], "evidence.pre_engine_state_id"),
        _uuid(raw["pre_ledger_state_id"], "evidence.pre_ledger_state_id"),
        _uuid(raw["post_engine_state_id"], "evidence.post_engine_state_id"),
        _uuid(raw["post_ledger_state_id"], "evidence.post_ledger_state_id"),
        fills,
        _enum(
            raw["status"],
            CheckpointedVerifiedSnapshotPaperCycleStatus,
            "evidence.status",
        ),
        codes,
        request,
    )


def _request(value: object) -> CheckpointedVerifiedSnapshotPaperCycleRequest:
    raw = _object(value, _REQUEST_FIELDS, "request")
    target = _object(raw["target"], _TARGET_FIELDS, "request.target")
    quantities = tuple(
        ExplicitQuantityTarget(
            _symbol(
                _object(item, _TARGET_QUANTITY_FIELDS, "target.quantity")["symbol"],
                "target.symbol",
            ),
            _decimal(
                _object(item, _TARGET_QUANTITY_FIELDS, "target.quantity")["quantity"],
                "target.quantity",
            ),
        )
        for item in _array(target["quantities"], "request.target.quantities")
    )
    references = tuple(
        _open_reference(item, f"request.open_references[{index}]")
        for index, item in enumerate(
            _array(raw["open_references"], "request.open_references")
        )
    )
    metadata_items = _array(raw["metadata"], "request.metadata")
    if len(metadata_items) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA:
        raise CheckpointedPaperCycleReportSchemaError("request.metadata exceeds bound")
    metadata = tuple(
        MetadataEntry(
            _string_bounded(
                _object(item, _METADATA_FIELDS, "metadata")["key"],
                "metadata.key",
                MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_KEY_CHARACTERS,
            ),
            _string_bounded(
                _object(item, _METADATA_FIELDS, "metadata")["value"],
                "metadata.value",
                MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_VALUE_CHARACTERS,
            ),
        )
        for item in metadata_items
    )
    try:
        return CheckpointedVerifiedSnapshotPaperCycleRequest(
            _uuid(raw["request_id"], "request.request_id"),
            _snapshot_reference(
                raw["snapshot_reference"], "request.snapshot_reference"
            ),
            ExplicitQuantityTargetPortfolio(
                _uuid(target["target_id"], "request.target.target_id"),
                quantities,
                _decimal(target["target_cash"], "request.target.target_cash"),
            ),
            references,
            _policies(raw["policies"]),
            _timestamp(raw["planning_at"], "request.planning_at"),
            _timestamp(raw["submitted_at"], "request.submitted_at"),
            _timestamp(raw["filled_at"], "request.filled_at"),
            metadata,
        )
    except (TypeError, ValueError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            "request does not reconcile"
        ) from error


def _policies(value: object) -> VerifiedSnapshotPaperCyclePolicies:
    raw = _object(value, _POLICY_FIELDS, "policies")
    assumptions = _object(
        raw["rebalance_assumptions"], _ASSUMPTIONS_FIELDS, "assumptions"
    )
    constraints_raw = raw["portfolio_constraints"]
    constraints = None
    if constraints_raw is not None:
        item = _object(constraints_raw, _CONSTRAINTS_FIELDS, "constraints")
        constraints = PortfolioConstraints(
            _decimal(item["minimum_cash_weight"], "minimum_cash_weight"),
            _decimal(item["maximum_cash_weight"], "maximum_cash_weight"),
            _decimal(item["maximum_position_weight"], "maximum_position_weight"),
            None
            if item["maximum_one_way_rebalance_turnover"] is None
            else _decimal(
                item["maximum_one_way_rebalance_turnover"],
                "maximum_one_way_rebalance_turnover",
            ),
            None
            if item["minimum_position_weight"] is None
            else _decimal(item["minimum_position_weight"], "minimum_position_weight"),
            _bool(item["long_only"], "long_only"),
            _bool(item["allow_leverage"], "allow_leverage"),
        )
    proposal = _object(
        raw["proposal_policy"], _PROPOSAL_POLICY_FIELDS, "proposal_policy"
    )
    limits = _object(raw["risk_limits"], _RISK_LIMITS_FIELDS, "risk_limits")
    risk_policy = _object(raw["risk_policy"], _RISK_POLICY_FIELDS, "risk_policy")
    fill = _object(raw["fill_policy"], _FILL_POLICY_FIELDS, "fill_policy")
    try:
        return VerifiedSnapshotPaperCyclePolicies(
            RebalanceAssumptions(
                _decimal(assumptions["fixed_commission"], "fixed_commission"),
                _bool(
                    assumptions["allow_fractional_quantities"],
                    "allow_fractional_quantities",
                ),
                _decimal(assumptions["quantity_increment"], "quantity_increment"),
                _decimal(
                    assumptions["minimum_trade_notional"], "minimum_trade_notional"
                ),
                _decimal(
                    assumptions["minimum_trade_quantity"], "minimum_trade_quantity"
                ),
                _decimal(
                    assumptions["target_weight_tolerance"], "target_weight_tolerance"
                ),
                _decimal(
                    assumptions["additional_execution_cash_buffer"],
                    "additional_execution_cash_buffer",
                ),
                _bool(
                    assumptions["use_planned_sell_proceeds"],
                    "use_planned_sell_proceeds",
                ),
            ),
            constraints,
            RebalanceProposalPolicy(
                _bool(proposal["allow_partial_plans"], "allow_partial_plans")
            ),
            None
            if raw["proposal_confidence"] is None
            else _decimal(raw["proposal_confidence"], "proposal_confidence"),
            RiskLimits(
                _decimal(limits["max_position_percent"], "max_position_percent"),
                _decimal(
                    limits["max_total_exposure_percent"], "max_total_exposure_percent"
                ),
                None
                if limits["max_order_notional"] is None
                else _decimal(limits["max_order_notional"], "max_order_notional"),
                None
                if limits["max_new_position_percent"] is None
                else _decimal(
                    limits["max_new_position_percent"], "max_new_position_percent"
                ),
                _decimal(
                    limits["minimum_cash_reserve_percent"],
                    "minimum_cash_reserve_percent",
                ),
                _bool(limits["allow_fractional_shares"], "allow_fractional_shares"),
                _decimal(limits["fractional_increment"], "fractional_increment"),
                _bool(limits["allow_buying"], "allow_buying"),
                _bool(limits["allow_selling"], "allow_selling"),
                _decimal(limits["estimated_commission"], "estimated_commission"),
            ),
            PortfolioRiskPolicy(
                _bool(
                    risk_policy["allow_sell_proceeds_for_later_buys"],
                    "allow_sell_proceeds_for_later_buys",
                )
            ),
            PaperFillPolicy(
                _decimal(fill["slippage_basis_points"], "slippage_basis_points"),
                _decimal(fill["fixed_commission"], "fill_fixed_commission"),
            ),
            _bool(raw["trading_enabled"], "trading_enabled"),
        )
    except (TypeError, ValueError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            "policies do not reconcile"
        ) from error


def _compact(value: object, path: str) -> CompactPaperLedgerState:
    raw = _object(value, _COMPACT_STATE_FIELDS, path)
    positions = tuple(
        _position(item, f"{path}.positions[{index}]")
        for index, item in enumerate(_array(raw["positions"], f"{path}.positions"))
    )
    try:
        return CompactPaperLedgerState(
            _uuid(raw["compact_state_id"], f"{path}.compact_state_id"),
            _timestamp(raw["as_of"], f"{path}.as_of"),
            _decimal(raw["cash"], f"{path}.cash"),
            positions,
            _decimal(raw["realized_profit_loss"], f"{path}.realized_profit_loss"),
        )
    except (TypeError, ValueError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: compact state invalid"
        ) from error


def _position(value: object, path: str) -> CompactPaperLedgerPosition:
    raw = _object(value, _POSITION_FIELDS, path)
    try:
        return CompactPaperLedgerPosition(
            _symbol(raw["symbol"], f"{path}.symbol"),
            _decimal(raw["quantity"], f"{path}.quantity"),
            _decimal(raw["total_cost_basis"], f"{path}.total_cost_basis"),
            _decimal(raw["average_cost"], f"{path}.average_cost"),
        )
    except (TypeError, ValueError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: position invalid"
        ) from error


def _fill(value: object, path: str) -> OrderFill:
    from trading_bot.domain import OrderSide

    raw = _object(value, _FILL_FIELDS, path)
    try:
        return OrderFill(
            _uuid(raw["fill_id"], f"{path}.fill_id"),
            _uuid(raw["order_id"], f"{path}.order_id"),
            _symbol(raw["symbol"], f"{path}.symbol"),
            _enum(raw["side"], OrderSide, f"{path}.side"),
            _decimal(raw["quantity"], f"{path}.quantity"),
            _decimal(raw["price"], f"{path}.price"),
            _decimal(raw["commission"], f"{path}.commission"),
            _timestamp(raw["filled_at"], f"{path}.filled_at"),
        )
    except (TypeError, ValueError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: fill invalid"
        ) from error


def _open_reference(value: object, path: str) -> CallerAssertedNextSessionOpenReference:
    raw = _object(value, _OPEN_FIELDS, path)
    return CallerAssertedNextSessionOpenReference(
        _symbol(raw["symbol"], f"{path}.symbol"),
        TradingSession(_date(raw["session_date"], f"{path}.session_date")),
        _decimal(raw["price"], f"{path}.price"),
    )


def _prior(value: object) -> PriorPaperAccountCheckpointReference:
    raw = _object(value, _REFERENCE_FIELDS, "prior_checkpoint")
    return PriorPaperAccountCheckpointReference(
        _uuid(raw["checkpoint_id"], "prior_checkpoint.checkpoint_id"),
        _integer(raw["sequence"], "prior_checkpoint.sequence"),
        _sha(raw["artifact_sha256"], "prior_checkpoint.artifact_sha256"),
        _integer(raw["artifact_byte_length"], "prior_checkpoint.artifact_byte_length"),
    )


def _snapshot_reference(value: object, path: str) -> VerifiedDailySnapshotReference:
    raw = _object(value, _SNAPSHOT_FIELDS, path)
    return VerifiedDailySnapshotReference(
        _uuid(raw["snapshot_id"], f"{path}.snapshot_id"),
        _sha(raw["artifact_sha256"], f"{path}.artifact_sha256"),
        _integer(raw["artifact_byte_length"], f"{path}.artifact_byte_length"),
    )


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
        raise CheckpointedPaperCycleReportSchemaError(
            "cannot render canonical report"
        ) from error


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _load_json(payload: bytes) -> object:
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES
    ):
        raise CheckpointedPaperCycleReportSyntaxError(
            "report bytes invalid or exceed bounds"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise CheckpointedPaperCycleReportSyntaxError("report has UTF-8 BOM")
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        CheckpointedPaperCycleReportSchemaError,
    ) as error:
        raise CheckpointedPaperCycleReportSyntaxError(
            "report JSON is not strict"
        ) from error


def _object(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: fields do not match schema"
        )
    return value


def _array(value: object, path: str) -> list[object]:
    if (
        type(value) is not list
        or len(value) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_ARRAY_ITEMS
    ):
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: invalid bounded array")
    return value


def _string(value: object, path: str) -> str:
    if (
        type(value) is not str
        or len(value) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_STRING_CHARACTERS
    ):
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: invalid string")
    return value


def _string_bounded(value: object, path: str, maximum: int) -> str:
    text = _string(value, path)
    if len(text) > maximum:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: string exceeds bound")
    return text


def _validate_request_bounds(
    request: CheckpointedVerifiedSnapshotPaperCycleRequest,
) -> None:
    metadata = tuple(request.metadata)
    if len(metadata) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA or any(
        len(item.key) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_KEY_CHARACTERS
        or len(item.value)
        > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_METADATA_VALUE_CHARACTERS
        for item in metadata
    ):
        raise CheckpointedPaperCycleReportReconciliationError(
            "request metadata exceeds report bounds"
        )


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        parsed = UUID(text)
    except (TypeError, ValueError, AttributeError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: invalid UUID"
        ) from error
    if str(parsed) != text:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: UUID is not canonical")
    return parsed


def _sha(value: object, path: str) -> str:
    text = _string(value, path)
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: invalid SHA-256")
    return text


def _decimal(value: object, path: str) -> Decimal:
    text = _string(value, path)
    if len(text) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_DECIMAL_CHARACTERS:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: Decimal exceeds bound")
    try:
        parsed = Decimal(text)
    except InvalidOperation as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: invalid Decimal"
        ) from error
    if not parsed.is_finite() or canonical_decimal(parsed) != text:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: Decimal is not canonical"
        )
    return parsed


def _timestamp(value: object, path: str) -> datetime:
    text = _string(value, path)
    if _TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: invalid timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)
    except ValueError as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: invalid timestamp"
        ) from error
    if canonical_timestamp(parsed) != text:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: timestamp not canonical"
        )
    return parsed


def _date(value: object, path: str) -> date:
    text = _string(value, path)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: invalid date")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: invalid date"
        ) from error
    if parsed.isoformat() != text:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: date not canonical")
    return parsed


def _symbol(value: object, path: str) -> Symbol:
    text = _string(value, path)
    try:
        symbol = Symbol(text)
    except (TypeError, ValueError) as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: invalid symbol"
        ) from error
    if str(symbol) != text:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: symbol not canonical")
    return symbol


def _integer(value: object, path: str) -> int:
    if (
        type(value) is not int
        or abs(value) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_INTEGER
    ):
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: invalid integer")
    return value


def _bool(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: expected boolean")
    return value


def _enum(value: object, enum_type, path: str):  # type: ignore[no-untyped-def]
    text = _string(value, path)
    try:
        retained = enum_type(text)
    except ValueError as error:
        raise CheckpointedPaperCycleReportSchemaError(
            f"{path}: invalid enum"
        ) from error
    if retained.value != text:
        raise CheckpointedPaperCycleReportSchemaError(f"{path}: enum not canonical")
    return retained


def _tuple(value: object, expected: type, path: str):
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise CheckpointedPaperCycleReportReconciliationError(
            f"{path} must be iterable"
        ) from error
    if len(items) > MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_ARRAY_ITEMS or any(
        type(item) is not expected for item in items
    ):
        raise CheckpointedPaperCycleReportReconciliationError(
            f"{path} contains invalid values"
        )
    return items


def _duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CheckpointedPaperCycleReportSchemaError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise CheckpointedPaperCycleReportSchemaError("JSON float is not permitted")


def _reject_constant(value: str) -> None:
    raise CheckpointedPaperCycleReportSchemaError("JSON constant is not permitted")


def _expected_sha256(value: str | None) -> None:
    if value is not None and (
        type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None
    ):
        raise CheckpointedPaperCycleReportVerificationError(
            "expected report SHA-256 invalid"
        )


def _expected_length(value: int | None) -> None:
    if value is not None and (type(value) is not int or value < 0):
        raise CheckpointedPaperCycleReportVerificationError(
            "expected report byte length invalid"
        )


def _diagnostic(
    code: CheckpointedPaperCycleReportVerificationCode,
    detail: str,
) -> CheckpointedPaperCycleReportVerificationDiagnostic:
    return CheckpointedPaperCycleReportVerificationDiagnostic(code, detail)


def _failed(
    report_length: int,
    report_hash: str,
    snapshot_length: int,
    snapshot_hash: str,
    diagnostics: list[CheckpointedPaperCycleReportVerificationDiagnostic],
) -> CheckpointedPaperCycleReportVerificationResult:
    return CheckpointedPaperCycleReportVerificationResult(
        CheckpointedPaperCycleReportVerificationStatus.FAIL,
        report_length,
        report_hash,
        snapshot_length,
        snapshot_hash,
        None,
        None,
        tuple(diagnostics),
    )
