"""Pure Architecture-144-C F1 paper-evidence verification composition.

This module accepts only caller-supplied canonical bytes and inert 142/143
artifacts.  The D1R7/D1R8/F1 reducers below are deliberately limited to canonical
byte parsing and state replay; they do not expose the operational journal
stores, filesystem, scheduler, provider, credential, broker, or paper-state
capabilities of those runtimes. The replay grammars are independently owned here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.experiments.research_strategy_paper_candidate_eligibility import (
    ResearchStrategyPaperCandidateEligibilityError,
    ResearchStrategyPaperSoakPolicy,
)
from trading_bot.experiments.research_strategy_paper_candidate_eligibility_v2 import (
    PAPER_AUTHORITY_KIND,
    PAPER_AUTHORITY_SCHEMA,
    PAPER_AUTHORITY_SOURCE_HEAD,
    PAPER_AUTHORITY_SOURCE_TREE,
    ResearchStrategyPaperCandidateEligibilityV2,
    ResearchStrategyPaperSessionObservationV2,
    validate_research_strategy_paper_eligibility_window_v2,
)
from trading_bot.experiments.research_strategy_production_compatibility import (
    ProductionStrategySemanticTarget,
    ResearchStrategyProductionCompatibilityProof,
    verify_research_strategy_production_compatibility_proof,
)
from trading_bot.experiments.research_strategy_walk_forward import (
    CompletedResearchStrategyWalkForward,
    ResearchStrategyWalkForwardQualification,
    ResearchStrategyWalkForwardQualificationPolicy,
    WalkForwardPassedResearchStrategy,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import (
    MOVING_AVERAGE_STRATEGY_ID,
    MOVING_AVERAGE_STRATEGY_VERSION,
    PRODUCTION_STRATEGY_SCHEMA,
)

D1R8_BRANCH = "feature/robinhood-production-paper-d1-session-execution"
D1R8_SOURCE_HEAD = "aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2"
D1R8_SOURCE_TREE = "fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f"
D1R7_BRANCH = "feature/robinhood-production-paper-d1-session-authorization"
D1R7_SOURCE_HEAD = "30322c49b13b80af8d20acee4bdb1efd83d86260"
D1R7_SOURCE_TREE = "b7dc7f054fca50c3ab784505f264b6f716a45dff"

D1R8_SCHEMA = "arch134-d1r8-d1-session-execution-consumer/v1"
D1R8_MAX_BYTES = 1_048_576
D1R8_MAX_ROWS = 600
D1R8_TERMINALS = frozenset(
    {
        "NO_SIGNAL",
        "RISK_REJECTED",
        "PAPER_EXECUTED",
        "BLOCKED",
        "SESSION_EXPIRED",
        "INDETERMINATE",
    }
)
D1R8_STATES = (
    "SESSION_RESERVED",
    "SOURCE_AND_D1R7_BOUND",
    "WRITE_READINESS_STARTED",
    "WRITE_READINESS_CONFIRMED",
    "LEGACY_SESSION_FENCE_CLAIMED",
    "CREDENTIAL_READ_INTENT",
    "CREDENTIAL_READ_CONFIRMED",
    *[
        state
        for _ in range(4)
        for state in ("HISTORY_READ_INTENT", "HISTORY_READ_CONFIRMED")
    ],
    "HISTORY_READY",
    "STRATEGY_STARTED",
    "STRATEGY_DECIDED",
    "PREPARE_STARTED",
    "QUOTE_INTENT",
    "QUOTE_CONFIRMED",
    "PREPARED",
    "EXECUTE_STARTED",
    "ACCOUNT_READ",
    "BASELINE_ORDER_READS",
    "REVIEW_INTENT",
    "REVIEW_CONFIRMED",
    "POST_REVIEW_ORDER_READS",
    "PAPER_WRITE_INTENT",
    "PAPER_WRITE_ACKNOWLEDGED",
)
D1R8_FIELDS = frozenset(
    {
        "schema",
        "event",
        "action",
        "counter",
        "facts",
        "binding_sha256",
        "budgets",
        "effects",
        "classification",
        "observed_at",
        "result_sha256",
    }
)
D1R8_HASHED_STATES = {
    "HISTORY_READY",
    "STRATEGY_DECIDED",
    "PREPARED",
    "PAPER_WRITE_ACKNOWLEDGED",
}
D1R8_BUDGETS = {
    "write_readiness_attempts": 1,
    "compatibility_reservations": 1,
    "alpaca_history_requests": 4,
    "alpaca_credential_reads": 2,
    "robinhood_credential_reads": 2,
    "credential_reads": 4,
    "credential_writes": 0,
    "credential_deletes": 0,
    "oauth_refresh": 0,
    "oauth_browser": 0,
    "oauth_callback": 0,
    "oauth_registration": 0,
    "strategy_evaluations": 1,
    "prepare_attempts": 1,
    "quote_requests": 1,
    "account_resolutions": 1,
    "order_history_attempts": 202,
    "order_reviews": 1,
    "execute_attempts": 1,
    "paper_fill_mutations": 1,
    "broker_placements": 0,
    "broker_cancellations": 0,
    "options_mutations": 0,
    "crypto_mutations": 0,
    "scheduler_operations": 0,
    "acl_mutations": 0,
    "d2_effects": 0,
    "live_effects": 0,
}
D1R8_ALLOWED = {
    "write_readiness_attempts": "WRITE_READINESS_STARTED",
    "compatibility_reservations": "WRITE_READINESS_CONFIRMED",
    "alpaca_credential_reads": "CREDENTIAL_READ_INTENT",
    "robinhood_credential_reads": "PREPARE_STARTED",
    "alpaca_history_requests": "HISTORY_READ_INTENT",
    "strategy_evaluations": "STRATEGY_STARTED",
    "prepare_attempts": "PREPARE_STARTED",
    "quote_requests": "QUOTE_INTENT",
    "execute_attempts": "EXECUTE_STARTED",
    "account_resolutions": "ACCOUNT_READ",
    "order_history_attempts": ("BASELINE_ORDER_READS", "POST_REVIEW_ORDER_READS"),
    "order_reviews": "REVIEW_INTENT",
    "paper_fill_mutations": "PAPER_WRITE_INTENT",
}

_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA64 = re.compile(r"[0-9a-f]{64}")
_NEW_YORK = ZoneInfo("America/New_York")
_D1R7_CHECKPOINT = "arch134-d1r7-d1-session-authorization"
_D1R7_SCHEMA = "arch134-d1r7-d1-session-authorization/v1"
_CONTRACT_NAMESPACE = UUID("c0867c3b-548e-5512-a135-3c4f1225e6fc")
_CONTRACT_IDENTITY_VERSION = "production-strategy-contract-identity/v1"
_POSITIVE_CLASSIFICATIONS = frozenset({"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"})


class ResearchStrategyF1PaperEvidenceVerificationError(
    ResearchStrategyPaperCandidateEligibilityError
):
    """Malformed, incomplete, or independently unreconciled paper evidence."""


ResearchStrategyF1PaperEvidenceError = ResearchStrategyF1PaperEvidenceVerificationError


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ResearchStrategyF1PaperEvidenceVerificationError(
                "duplicate canonical field"
            )
        result[name] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyF1PaperEvidenceVerificationError(f"non-JSON constant {value}")


def _rows(
    payload: bytes, *, maximum: int, row_limit: int
) -> tuple[dict[str, object], ...]:
    if type(payload) is not bytes or not 0 < len(payload) <= maximum:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "evidence byte bound rejected"
        )
    try:
        rows = tuple(
            json.loads(
                line, object_pairs_hook=_unique_object, parse_constant=_reject_constant
            )
            for line in payload.decode("utf-8").splitlines()
        )
    except (UnicodeError, TypeError, ValueError, RecursionError):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical evidence JSON rejected"
        ) from None
    if not 0 < len(rows) <= row_limit or any(type(row) is not dict for row in rows):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical evidence rows rejected"
        )
    try:
        canonical = b"".join(_canonical(row) + b"\n" for row in rows)
    except (TypeError, ValueError, OverflowError):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical evidence rows rejected"
        ) from None
    if canonical != payload:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "noncanonical or incomplete evidence bytes"
        )
    return rows


def _hash(value: object, length: int) -> str:
    if type(value) is not str or len(value) != length:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "lowercase hash required"
        )
    if any(char not in "0123456789abcdef" for char in value):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "lowercase hash required"
        )
    return value


def _source(value: object) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyF1PaperEvidenceVerificationError("source digest required")
    return value


def _date_text(value: object) -> date:
    if type(value) is not str:
        raise ResearchStrategyF1PaperEvidenceVerificationError("date text required")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical date required"
        ) from None
    if result.isoformat() != value:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical date required"
        )
    return result


def _utc_text(value: object) -> datetime:
    if type(value) is not str:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "aware timestamp required"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical aware timestamp required"
        ) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical aware timestamp required"
        )
    normalized = parsed.astimezone(UTC)
    if normalized.isoformat() != value:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "canonical UTC timestamp required"
        )
    return normalized


def _exact(value: object, expected: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "exact evidence fields required"
        )
    return value


def _contract_material(
    target_session_date: date,
    source_head: str,
    source_tree: str,
    symbol: Symbol,
    config: MovingAverageCrossoverConfig,
) -> str:
    values = (
        _CONTRACT_IDENTITY_VERSION,
        target_session_date.isoformat(),
        source_head,
        source_tree,
        MOVING_AVERAGE_STRATEGY_ID,
        MOVING_AVERAGE_STRATEGY_VERSION,
        str(symbol),
        str(config.short_window),
        str(config.long_window),
        _decimal(config.desired_quantity),
    )
    return "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values)


def _decimal(value: object) -> str:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "positive finite Decimal required"
        )
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


@dataclass(frozen=True, slots=True)
class _RecoveredContract:
    contract_id: UUID
    target_session_date: date
    source_head: str
    source_tree: str
    symbol: Symbol
    strategy_config: MovingAverageCrossoverConfig


@dataclass(frozen=True, slots=True)
class _RecoveredPlan:
    contract: _RecoveredContract
    observed_at: datetime
    target: date
    expires_at: datetime
    facts: dict[str, object]

    def require_current(self, observed: datetime) -> None:
        if (
            observed < self.observed_at
            or observed >= self.expires_at
            or observed.astimezone(_NEW_YORK).date() != self.target
        ):
            raise ResearchStrategyF1PaperEvidenceVerificationError(
                "D1R7 authorization is not current"
            )


def _recover_contract(value: object) -> _RecoveredContract:
    raw = _exact(
        value,
        {
            "schema",
            "contract_id",
            "target_session_date",
            "source_head",
            "source_tree",
            "strategy_id",
            "strategy_version",
            "symbol",
            "strategy_config",
        },
    )
    if (
        raw["schema"] != PRODUCTION_STRATEGY_SCHEMA
        or raw["strategy_id"] != MOVING_AVERAGE_STRATEGY_ID
        or raw["strategy_version"] != MOVING_AVERAGE_STRATEGY_VERSION
    ):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract schema/family/version mismatch"
        )
    target = _date_text(raw["target_session_date"])
    head = _source(raw["source_head"])
    tree = _source(raw["source_tree"])
    symbol_text = raw["symbol"]
    if type(symbol_text) is not str or str(Symbol(symbol_text)) != symbol_text:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract symbol rejected"
        )
    config_raw = _exact(
        raw["strategy_config"], {"short_window", "long_window", "desired_quantity"}
    )
    if (
        type(config_raw["short_window"]) is not int
        or type(config_raw["long_window"]) is not int
    ):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract windows rejected"
        )
    quantity = config_raw["desired_quantity"]
    if type(quantity) is not str:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract Decimal rejected"
        )
    try:
        parsed_quantity = Decimal(quantity)
        config = MovingAverageCrossoverConfig(
            config_raw["short_window"], config_raw["long_window"], parsed_quantity
        )
    except (ArithmeticError, TypeError, ValueError):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract configuration rejected"
        ) from None
    if _decimal(parsed_quantity) != quantity:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract Decimal is noncanonical"
        )
    symbol = Symbol(symbol_text)
    material = _contract_material(target, head, tree, symbol, config)
    try:
        contract_id = UUID(raw["contract_id"])
    except (TypeError, ValueError):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract ID rejected"
        ) from None
    if (
        str(contract_id) != raw["contract_id"]
        or contract_id.version != 5
        or contract_id != uuid5(_CONTRACT_NAMESPACE, material)
    ):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract identity mismatch"
        )
    return _RecoveredContract(contract_id, target, head, tree, symbol, config)


def _recovered_contract_facts(contract: _RecoveredContract) -> dict[str, object]:
    config = contract.strategy_config
    return {
        "schema": PRODUCTION_STRATEGY_SCHEMA,
        "contract_id": str(contract.contract_id),
        "target_session_date": contract.target_session_date.isoformat(),
        "source_head": contract.source_head,
        "source_tree": contract.source_tree,
        "strategy_id": MOVING_AVERAGE_STRATEGY_ID,
        "strategy_version": MOVING_AVERAGE_STRATEGY_VERSION,
        "symbol": str(contract.symbol),
        "strategy_config": {
            "short_window": config.short_window,
            "long_window": config.long_window,
            "desired_quantity": _decimal(config.desired_quantity),
        },
    }


_D1R5 = {
    "basename": (
        "arch134-d1r5-2026-10-16-7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343.jsonl"
    ),
    "bytes": 6714,
    "sha256": "9967e978cbf5f97afd9453e24fcfc3cdee4e864b589751fda3051c833b6d32cf",
    "schema": "arch134-d1r5-pre-market-wake-qualification/v1",
    "source_head": "7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343",
    "source_tree": "c826c2a71e6d907866ce3f80afce479d38ab7842",
    "qualification_session": "2026-10-16",
    "final": "PASS",
}
_D1R6 = {
    "basename": (
        "arch134-d1r6-2026-10-16-"
        "7aa54bb618f63bfb2b470ff8fc88ba8d27ef9343-"
        "a36de3bfe81a6e1a94fb3deeec7e579145939f52-"
        "6cde732e02e92eb2b34281672cdb7744250355b1.jsonl"
    ),
    "bytes": 19321,
    "sha256": "837825d8cb3042431276bf6b7bdee0580da40ee2ef6a761eace86976924275f2",
    "schema": "arch134-d1r6-overnight-wake-arming/v1",
    "source_head": "a36de3bfe81a6e1a94fb3deeec7e579145939f52",
    "source_tree": "6cde732e02e92eb2b34281672cdb7744250355b1",
    "qualification_session": "2026-10-16",
    "final": "ARMED",
    "authority_kind": "ORDINARY_ARM",
    "historical_scheduler_create_calls": 1,
}
_D1R7_POLICY = {
    "starting_synthetic_cash": "10000",
    "opening_buffer_seconds": 300,
    "closing_buffer_seconds": 300,
    "max_quote_age_seconds": 60,
    "max_snapshot_age_seconds": 600,
    "risk_limits": {
        "max_position_percent": "0.20",
        "max_total_exposure_percent": "0.80",
        "max_order_notional": None,
        "max_new_position_percent": None,
        "minimum_cash_reserve_percent": "0.10",
        "allow_fractional_shares": True,
        "fractional_increment": "0.001",
        "allow_buying": True,
        "allow_selling": True,
        "estimated_commission": "0",
    },
    "synthetic_execution": {
        "order_type": "MARKET",
        "time_in_force": "DAY",
        "slippage_basis_points": "0",
        "commission": "0",
        "broker_placement_budget": 0,
        "maximum_synthetic_paper_fills": 1,
    },
}


def _validate_d1r7_facts(facts: object) -> _RecoveredPlan:
    raw = _exact(
        facts,
        {
            "checkpoint",
            "source",
            "intended_d1",
            "qualification_session",
            "target_session",
            "observed_at",
            "authorization_expires_at",
            "reservation_basename",
            "d1r5",
            "d1r6",
            "strategy_contract",
            "d1_policy",
        },
    )
    if raw["checkpoint"] != _D1R7_CHECKPOINT:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 checkpoint rejected"
        )
    source = _exact(raw["source"], {"origin", "branch", "head", "tree"})
    intended = _exact(raw["intended_d1"], {"origin", "branch", "head", "tree"})
    if (
        source["origin"] != "https://github.com/callmedraken/ai-trading-bot.git"
        or source["branch"] != D1R7_BRANCH
        or source["head"] != D1R7_SOURCE_HEAD
        or source["tree"] != D1R7_SOURCE_TREE
        or intended["origin"] != source["origin"]
        or intended["branch"] != D1R8_BRANCH
        or intended["head"] != D1R8_SOURCE_HEAD
        or intended["tree"] != D1R8_SOURCE_TREE
        or raw["qualification_session"] != "2026-10-16"
    ):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 source lineage rejected"
        )
    target = _date_text(raw["target_session"])
    observed = _utc_text(raw["observed_at"])
    expires = _utc_text(raw["authorization_expires_at"])
    derived_target = observed.astimezone(_NEW_YORK).date()
    if target != derived_target:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 target session derivation rejected"
        )
    try:
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(target)
    except (TypeError, ValueError):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 published session rejected"
        ) from None
    if schedule is None:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 published session rejected"
        )
    expected_expires = schedule.closes_at.astimezone(UTC) - timedelta(minutes=5)
    if observed >= expected_expires or expires != expected_expires:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 authorization expiry rejected"
        )
    contract = _recover_contract(raw["strategy_contract"])
    if contract.target_session_date != target:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 contract date mismatch"
        )
    expected_basename = (
        "arch134-d1r7-"
        + target.isoformat()
        + "-"
        + hashlib.sha256(
            _canonical(
                [
                    _D1R7_SCHEMA,
                    target.isoformat(),
                    _D1R5["sha256"],
                    _D1R6["sha256"],
                ]
            )
        ).hexdigest()
        + ".jsonl"
    )
    expected_facts = {
        "checkpoint": _D1R7_CHECKPOINT,
        "source": dict(source),
        "intended_d1": dict(intended),
        "qualification_session": "2026-10-16",
        "target_session": target.isoformat(),
        "observed_at": observed.isoformat(),
        "authorization_expires_at": expected_expires.isoformat(),
        "reservation_basename": expected_basename,
        "d1r5": _D1R5,
        "d1r6": _D1R6,
        "strategy_contract": _recovered_contract_facts(contract),
        "d1_policy": _D1R7_POLICY,
    }
    if _canonical(raw) != _canonical(expected_facts):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R7 reconstructed facts rejected"
        )
    return _RecoveredPlan(contract, observed, target, expected_expires, expected_facts)


def _validate_d1r8_facts(facts: object) -> _RecoveredPlan:
    raw = _exact(
        facts,
        {"prerequisite", "d1r7_bytes", "d1r7_sha256", "publication_confirmed"},
    )
    if (
        type(raw["d1r7_bytes"]) is not int
        or not 0 < raw["d1r7_bytes"] <= 131_072
        or raw["publication_confirmed"] is not True
    ):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R8 publication proof rejected"
        )
    _hash(raw["d1r7_sha256"], 64)
    return _validate_d1r7_facts(raw["prerequisite"])


class _D1R8Replay:
    def __init__(self, facts: object) -> None:
        self._raw_facts = facts
        self.plan = _validate_d1r8_facts(facts)
        self.contract = self.plan.contract
        self.binding = hashlib.sha256(_canonical(facts)).hexdigest()
        self.effects = dict.fromkeys(D1R8_BUDGETS, 0)
        self.pending: str | None = None
        self.phase = -1
        self.last_time = self.plan.observed_at
        self.terminal = False
        self.baseline_pages = 0
        self.index = 0

    @property
    def _facts(self) -> dict[str, object]:
        return self._raw_facts["prerequisite"]  # type: ignore[index]

    def add(self, row: dict[str, object]) -> None:
        if (
            set(row) != D1R8_FIELDS
            or (self.index == 0 and row["event"] != "SESSION_RESERVED")
            or row["schema"] != D1R8_SCHEMA
            or row["binding_sha256"] != self.binding
            or _canonical(row["budgets"]) != _canonical(D1R8_BUDGETS)
            or (self.index > 0 and row["facts"] is not None)
            or self.terminal
        ):
            raise ResearchStrategyF1PaperEvidenceVerificationError(
                "D1R8 state binding rejected"
            )
        result_hash = row["result_sha256"]
        needs_hash = row["event"] in D1R8_HASHED_STATES and row["action"] is None
        if needs_hash:
            _hash(result_hash, 64)
        elif result_hash is not None:
            raise ResearchStrategyF1PaperEvidenceVerificationError(
                "D1R8 result hash rejected"
            )
        observed = _utc_text(row["observed_at"])
        if observed < self.last_time:
            raise ResearchStrategyF1PaperEvidenceVerificationError(
                "D1R8 clock order rejected"
            )
        self.last_time = observed
        event, action, counter = row["event"], row["action"], row["counter"]
        if event == "FINAL":
            result = row["classification"]
            if (
                action is not None
                or counter is not None
                or result not in D1R8_TERMINALS
            ):
                raise ResearchStrategyF1PaperEvidenceVerificationError(
                    "D1R8 terminal rejected"
                )
            if self.pending is not None and result != "INDETERMINATE":
                raise ResearchStrategyF1PaperEvidenceVerificationError(
                    "D1R8 pending effect rejected"
                )
            if result in {"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"}:
                required = {
                    "NO_SIGNAL": "STRATEGY_DECIDED",
                    "RISK_REJECTED": "PREPARED",
                    "PAPER_EXECUTED": "PAPER_WRITE_ACKNOWLEDGED",
                }[result]
                if (
                    self.phase < 0
                    or D1R8_STATES[self.phase] != required
                    or self.pending is not None
                ):
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 terminal state rejected"
                    )
                self.plan.require_current(observed)
                if result == "NO_SIGNAL":
                    expected = {
                        "alpaca_credential_reads": 2,
                        "alpaca_history_requests": 4,
                        "strategy_evaluations": 1,
                        "robinhood_credential_reads": 0,
                        "prepare_attempts": 0,
                        "execute_attempts": 0,
                        "paper_fill_mutations": 0,
                    }
                elif result == "RISK_REJECTED":
                    expected = {
                        "alpaca_credential_reads": 2,
                        "alpaca_history_requests": 4,
                        "strategy_evaluations": 1,
                        "robinhood_credential_reads": 2,
                        "prepare_attempts": 1,
                        "quote_requests": 1,
                        "execute_attempts": 0,
                        "paper_fill_mutations": 0,
                    }
                else:
                    expected = {
                        "alpaca_credential_reads": 2,
                        "alpaca_history_requests": 4,
                        "strategy_evaluations": 1,
                        "robinhood_credential_reads": 2,
                        "prepare_attempts": 1,
                        "quote_requests": 1,
                        "execute_attempts": 1,
                        "account_resolutions": 1,
                        "order_reviews": 1,
                        "paper_fill_mutations": 1,
                    }
                    if not 2 <= self.effects["order_history_attempts"] <= 200:
                        raise ResearchStrategyF1PaperEvidenceVerificationError(
                            "D1R8 order history bound rejected"
                        )
                if any(self.effects[key] != value for key, value in expected.items()):
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 effects rejected"
                    )
            self.terminal = True
        else:
            if row["classification"] is not None:
                raise ResearchStrategyF1PaperEvidenceVerificationError(
                    "D1R8 intermediate classification rejected"
                )
            if action is None:
                if (
                    counter is not None
                    or self.pending is not None
                    or self.phase + 1 >= len(D1R8_STATES)
                    or event != D1R8_STATES[self.phase + 1]
                ):
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 state transition rejected"
                    )
                self.phase += 1
                required = {
                    "WRITE_READINESS_CONFIRMED": {"write_readiness_attempts": 1},
                    "LEGACY_SESSION_FENCE_CLAIMED": {"compatibility_reservations": 1},
                    "CREDENTIAL_READ_CONFIRMED": {"alpaca_credential_reads": 2},
                    "HISTORY_READY": {"alpaca_history_requests": 4},
                    "STRATEGY_DECIDED": {"strategy_evaluations": 1},
                    "QUOTE_INTENT": {
                        "robinhood_credential_reads": 2,
                        "prepare_attempts": 1,
                    },
                    "QUOTE_CONFIRMED": {"quote_requests": 1},
                    "ACCOUNT_READ": {"execute_attempts": 1},
                    "BASELINE_ORDER_READS": {"account_resolutions": 1},
                    "REVIEW_CONFIRMED": {"order_reviews": 1},
                    "PAPER_WRITE_ACKNOWLEDGED": {"paper_fill_mutations": 1},
                }.get(event, {})
                if event == "HISTORY_READ_CONFIRMED":
                    required = {
                        "alpaca_history_requests": D1R8_STATES[: self.phase + 1].count(
                            event
                        )
                    }
                if any(self.effects[key] != value for key, value in required.items()):
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 state effects rejected"
                    )
                if event == "REVIEW_INTENT":
                    self.baseline_pages = self.effects["order_history_attempts"]
                    if not 1 <= self.baseline_pages <= 100:
                        raise ResearchStrategyF1PaperEvidenceVerificationError(
                            "D1R8 baseline bound rejected"
                        )
                if (
                    event == "PAPER_WRITE_INTENT"
                    and not 1
                    <= self.effects["order_history_attempts"] - self.baseline_pages
                    <= 100
                ):
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 post-review bound rejected"
                    )
            else:
                if (
                    self.phase < 0
                    or event != D1R8_STATES[self.phase]
                    or counter not in D1R8_ALLOWED
                ):
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 effect transition rejected"
                    )
                permitted = D1R8_ALLOWED[counter]
                if event not in ((permitted,) if type(permitted) is str else permitted):
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 counter transition rejected"
                    )
                if action == "INTENT" and self.pending is None:
                    self.effects[counter] += 1
                    if counter.endswith("credential_reads"):
                        self.effects["credential_reads"] += 1
                    self.pending = counter
                elif action == "ACK" and self.pending == counter:
                    self.pending = None
                else:
                    raise ResearchStrategyF1PaperEvidenceVerificationError(
                        "D1R8 intent/ack rejected"
                    )
        if (
            type(row["effects"]) is not dict
            or set(row["effects"]) != set(D1R8_BUDGETS)
            or any(
                type(value) is not int or not 0 <= value <= D1R8_BUDGETS[key]
                for key, value in row["effects"].items()
            )
            or row["effects"] != self.effects
        ):
            raise ResearchStrategyF1PaperEvidenceVerificationError(
                "D1R8 effect accounting rejected"
            )
        self.index += 1


def _parse_d1r8(payload: bytes) -> tuple[dict[str, object], ...]:
    rows = _rows(payload, maximum=D1R8_MAX_BYTES, row_limit=D1R8_MAX_ROWS)
    try:
        facts = rows[0]["facts"]
        replay = _D1R8Replay(facts)
        for row in rows:
            replay.add(row)
        if not replay.terminal:
            raise ResearchStrategyF1PaperEvidenceVerificationError(
                "D1R8 terminal evidence required"
            )
        return rows
    except ResearchStrategyF1PaperEvidenceVerificationError:
        raise
    except (KeyError, TypeError, IndexError, ValueError, OverflowError):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "D1R8 canonical journal rejected"
        ) from None


def _raise_chain_error(error: Exception) -> None:
    raise ResearchStrategyF1PaperEvidenceVerificationError(
        "complete 142/143 chain verification failed"
    ) from error


def _verify_chain(
    proof: ResearchStrategyProductionCompatibilityProof,
    completed: CompletedResearchStrategyWalkForward,
    qualification: ResearchStrategyWalkForwardQualification,
    qualification_policy: ResearchStrategyWalkForwardQualificationPolicy,
    passed: WalkForwardPassedResearchStrategy,
    target: ProductionStrategySemanticTarget,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    proof_source_head: str,
    proof_source_tree: str,
) -> None:
    try:
        verify_research_strategy_production_compatibility_proof(
            proof,
            completed,
            qualification,
            qualification_policy,
            passed,
            target,
            qualification_source_head=qualification_source_head,
            qualification_source_tree=qualification_source_tree,
            proof_source_head=proof_source_head,
            proof_source_tree=proof_source_tree,
        )
    except Exception as error:
        _raise_chain_error(error)


_f1_schema = "arch134-f1-five-session-soak/v1"
_f1_child_schema = "arch134-f1-granted-session/v1"
_f1_branch = "feature/robinhood-production-paper-134f-five-session-soak"
_f1_origin = "https://github.com/callmedraken/ai-trading-bot.git"
_f1_task = "AITradingBot-Arch134-F1-FiveSessionSoak-v1"
_f1_max_bytes = 2097152
_f1_max_rows = 128
_f1_namespace = UUID("e9dd0368-2ca4-536f-bc95-3cc510337aac")
_f1_parent_name = "arch134-f1-five-session-soak-v1.jsonl"
_f1_progress = frozenset({"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"})
_f1_terminals = _f1_progress | {"SESSION_MISSED", "BLOCKED", "INDETERMINATE"}
_f1_wait_states = frozenset({"NEXT_SESSION_WAIT", "PREMARKET_WAIT", "D1R8_WAIT"})
_f1_initial = ("CHILD_RESERVED", "SOURCES_ADMITTED", "TARGET_BOUND")
_f1_scheduler = dict(
    task=_f1_task,
    logon_triggers=1,
    actions=1,
    semantic_arguments=0,
    elevation=False,
    wake=False,
    start_when_available=False,
    demand_start=True,
    instances="IgnoreNew",
    restarts=3,
    restart_interval="PT1M",
    time_limit="PT0S",
    repetition=False,
)
_f1_ceilings = dict(
    parent_series=1,
    frozen_sessions=5,
    d1r7_delegations=5,
    d1r8_delegations=5,
    per_target_d1r7=1,
    per_target_d1r8=1,
    scheduler_creates=1,
    scheduler_runs=1,
    provider_retries=0,
    replacement_sessions=0,
    broker_placements=0,
    d2=0,
    promotion=0,
    real_money=0,
)
_f1_budgets = dict(
    child_grants=5,
    scheduler_creates=1,
    scheduler_updates=0,
    scheduler_runs=1,
)
_f1_child_budgets = dict(
    d1r7_attempts=1,
    d1r8_attempts=1,
    scheduler_creates=0,
    scheduler_updates=0,
    scheduler_runs=0,
)
_f1_d1r7 = {
    "branch": "feature/robinhood-production-paper-d1-session-authorization",
    "head": "30322c49b13b80af8d20acee4bdb1efd83d86260",
    "tree": "b7dc7f054fca50c3ab784505f264b6f716a45dff",
}
_f1_d1r8 = {
    "branch": "feature/robinhood-production-paper-d1-session-execution",
    "head": "aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2",
    "tree": "fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f",
}
_f1_d1r9_predecessor = {
    "branch": "feature/robinhood-production-paper-d1-arbitrary-time-supervisor",
    "head": "efd1e6763dc4663d9c4b2444e785eb1c32adf8e8",
    "tree": "25a962daf3922c4226c7e395eba8613e1b03bbaf",
}
_f1_policy = {
    "starting_synthetic_cash": "10000",
    "opening_buffer_seconds": 300,
    "closing_buffer_seconds": 300,
    "max_quote_age_seconds": 60,
    "max_snapshot_age_seconds": 600,
    "risk_limits": {
        "max_position_percent": "0.20",
        "max_total_exposure_percent": "0.80",
        "max_order_notional": None,
        "max_new_position_percent": None,
        "minimum_cash_reserve_percent": "0.10",
        "allow_fractional_shares": True,
        "fractional_increment": "0.001",
        "allow_buying": True,
        "allow_selling": True,
        "estimated_commission": "0",
    },
    "synthetic_execution": {
        "order_type": "MARKET",
        "time_in_force": "DAY",
        "slippage_basis_points": "0",
        "commission": "0",
        "broker_placement_budget": 0,
        "maximum_synthetic_paper_fills": 1,
    },
}
_f1_d1r8_budgets = {
    "write_readiness_attempts": 1,
    "compatibility_reservations": 1,
    "alpaca_history_requests": 4,
    "alpaca_credential_reads": 2,
    "robinhood_credential_reads": 2,
    "credential_reads": 4,
    "credential_writes": 0,
    "credential_deletes": 0,
    "oauth_refresh": 0,
    "oauth_browser": 0,
    "oauth_callback": 0,
    "oauth_registration": 0,
    "strategy_evaluations": 1,
    "prepare_attempts": 1,
    "quote_requests": 1,
    "account_resolutions": 1,
    "order_history_attempts": 202,
    "order_reviews": 1,
    "execute_attempts": 1,
    "paper_fill_mutations": 1,
    "broker_placements": 0,
    "broker_cancellations": 0,
    "options_mutations": 0,
    "crypto_mutations": 0,
    "scheduler_operations": 0,
    "acl_mutations": 0,
    "d2_effects": 0,
    "live_effects": 0,
}


def _f1_canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _f1_digest(value: object) -> str:
    return hashlib.sha256(_f1_canonical(value)).hexdigest()


def _f1_utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware clock required")
    return value.astimezone(UTC)


def _f1_is_hash(value: object, length: int = 64) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(c in "0123456789abcdef" for c in value)
    )


def _f1_proof(value: object) -> None:
    if (
        type(value) is not dict
        or set(value) != {"bytes", "sha256"}
        or type(value["bytes"]) is not int
        or not 0 < value["bytes"] <= _f1_max_bytes
        or not _f1_is_hash(value["sha256"])
    ):
        raise ValueError("closed bounded proof required")


def _f1_contract(target: str) -> dict:
    material = [
        "production-strategy-contract-identity/v1",
        target,
        _f1_d1r8["head"],
        _f1_d1r8["tree"],
        "MovingAverageCrossoverStrategy",
        "1.0.0",
        "SPY",
        "2",
        "3",
        "1",
    ]
    framed = "".join(f"{len(v.encode('utf-8'))}:{v}" for v in material)
    return dict(
        contract_id=str(uuid5(UUID("c0867c3b-548e-5512-a135-3c4f1225e6fc"), framed)),
        schema="production-strategy-contract/v1",
        source_head=_f1_d1r8["head"],
        source_tree=_f1_d1r8["tree"],
        strategy_id="MovingAverageCrossoverStrategy",
        strategy_version="1.0.0",
        symbol="SPY",
        target_session_date=target,
        strategy_config=dict(desired_quantity="1", short_window=2, long_window=3),
    )


_f1_common = {
    "source",
    "d1r7",
    "d1r8",
    "semantic_predecessor",
    "symbol",
    "targets",
    "contracts",
    "policy",
    "scheduler",
    "ceilings",
    "runtime",
    "authorized_at",
    "kind",
}
_f1_child_extra = {"parent_id", "parent_prefix", "ordinal", "target_session"}


def _f1_semantic(facts: dict) -> dict:
    # F1 identities bind semantic facts; journal bytes and clocks are proof,
    # never UUID inputs. Source and contract identities remain explicit.
    return {
        "schema": _f1_child_schema if facts["kind"] == "child" else _f1_schema,
        "facts": {
            k: v
            for k, v in facts.items()
            if k not in {"runtime", "authorized_at", "parent_prefix"}
        },
    }


def _f1_domain_id(facts: dict) -> str:
    material = _f1_canonical(_f1_semantic(facts)).decode("utf-8")
    return str(uuid5(_f1_namespace, "arch134-f1-identity/v1:" + material))


def _f1_validate_facts(facts: dict) -> None:
    if type(facts) is not dict or facts.get("kind") not in {"parent", "child"}:
        raise ValueError("closed F1 authority required")
    if set(facts) != (
        _f1_common | (_f1_child_extra if facts["kind"] == "child" else set())
    ):
        raise ValueError("closed F1 facts required")
    source = facts["source"]
    if (
        type(source) is not dict
        or set(source) != {"branch", "head", "tree"}
        or source["branch"] != _f1_branch
        or source["head"] != PAPER_AUTHORITY_SOURCE_HEAD
        or source["tree"] != PAPER_AUTHORITY_SOURCE_TREE
    ):
        raise ValueError("F1 source rejected")
    fixed = dict(
        d1r7=_f1_d1r7,
        d1r8=_f1_d1r8,
        semantic_predecessor=_f1_d1r9_predecessor,
        symbol="SPY",
        policy=_f1_policy,
        scheduler=_f1_scheduler,
        ceilings=_f1_ceilings,
    )
    if any(_f1_canonical(facts[k]) != _f1_canonical(v) for k, v in fixed.items()):
        raise ValueError("fixed F1 policy rejected")
    targets = facts["targets"]
    if type(targets) is not list or len(targets) != 5 or len(set(targets)) != 5:
        raise ValueError("exact ordered five-session tuple required")
    if (
        any(
            type(t) is not str or date.fromisoformat(t).isoformat() != t
            for t in targets
        )
        or targets != sorted(targets)
        or _f1_canonical(facts["contracts"])
        != _f1_canonical([_f1_contract(t) for t in targets])
    ):
        raise ValueError("immutable contracts/targets rejected")
    if (
        _f1_utc(datetime.fromisoformat(facts["authorized_at"])).isoformat()
        != facts["authorized_at"]
    ):
        raise ValueError("canonical UTC required")
    runtime = facts["runtime"]
    if type(runtime) is not dict or set(runtime) != {"paper", "sessions", "python"}:
        raise ValueError("runtime binding rejected")
    for v in runtime.values():
        if (
            type(v) is not dict
            or set(v) != {"device", "inode", "bytes", "sha256"}
            or any(
                type(v[k]) is not int or v[k] < 0 for k in ("device", "inode", "bytes")
            )
            or v["inode"] == 0
            or not _f1_is_hash(v["sha256"])
        ):
            raise ValueError("runtime identity rejected")
    if facts["kind"] == "child":
        if (
            type(facts["ordinal"]) is not int
            or not 1 <= facts["ordinal"] <= 5
            or facts["target_session"] != targets[facts["ordinal"] - 1]
            or str(UUID(facts["parent_id"])) != facts["parent_id"]
        ):
            raise ValueError("child ordinal/parent rejected")
        _f1_proof(facts["parent_prefix"])


def _f1__unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _f1_allowed(phase: str, child: bool, completed: list) -> set[str]:
    if child:
        return {
            "START": {"CHILD_RESERVED"},
            "CHILD_RESERVED": {"SOURCES_ADMITTED"},
            "SOURCES_ADMITTED": {"TARGET_BOUND"},
            "TARGET_BOUND": {"CHILD_READY"},
            "CHILD_READY": {
                "NEXT_SESSION_WAIT",
                "PREMARKET_WAIT",
                "D1R7_DELEGATION_INTENT",
            },
            "NEXT_SESSION_WAIT": {"PREMARKET_WAIT", "D1R7_DELEGATION_INTENT"},
            "PREMARKET_WAIT": {"D1R7_DELEGATION_INTENT"},
            "D1R7_DELEGATION_INTENT": {"D1R7_READY"},
            "D1R7_READY": {"D1R8_WAIT", "D1R8_DELEGATION_INTENT"},
            "D1R8_WAIT": {"D1R8_DELEGATION_INTENT"},
            "D1R8_DELEGATION_INTENT": set(),
        }[phase]
    if phase == "SCHEDULER_RUN_ACK" or phase.endswith("_FINAL"):
        if (
            any(r["classification"] not in _f1_progress for r in completed)
            or len(completed) == 5
        ):
            return set()
        return {f"SESSION_{len(completed) + 1}_GRANT_INTENT"}
    if phase.startswith("SESSION_") and phase.endswith("_GRANT_INTENT"):
        return {phase.replace("GRANT_INTENT", "FINAL")}
    return {
        "START": {"SOAK_RESERVED"},
        "SOAK_RESERVED": {"SOURCES_ADMITTED"},
        "SOURCES_ADMITTED": {"WINDOW_BOUND"},
        "WINDOW_BOUND": {"SCHEDULER_CREATE_INTENT", "SOAK_READY"},
        "SCHEDULER_CREATE_INTENT": {"SCHEDULER_CREATE_ACK"},
        "SCHEDULER_CREATE_ACK": {"SOAK_READY"},
        "SOAK_READY": {"SCHEDULER_RUN_INTENT"},
        "SCHEDULER_RUN_INTENT": {"SCHEDULER_RUN_ACK"},
    }[phase]


def _f1_summary(value: dict, facts: dict, ordinal: int) -> None:
    if type(value) is not dict or set(value) != {
        "ordinal",
        "target_session",
        "child_id",
        "child_journal",
        "grant_prefix",
        "classification",
        "d1r7",
        "d1r8",
        "effects",
        "d1r8_effects",
        "contract",
    }:
        raise ValueError("closed child reconciliation required")
    if (
        type(value["ordinal"]) is not int
        or value["ordinal"] != ordinal
        or value["target_session"] != facts["targets"][ordinal - 1]
        or value["classification"] not in _f1_terminals
        or _f1_canonical(value["contract"])
        != _f1_canonical(facts["contracts"][ordinal - 1])
        or str(UUID(value["child_id"])) != value["child_id"]
    ):
        raise ValueError("ordered child identity rejected")
    _f1_proof(value["child_journal"])
    _f1_proof(value["grant_prefix"])
    for key in ("d1r7", "d1r8"):
        if value[key] is not None:
            _f1_proof(value[key])
    effects = value["effects"]
    if (
        type(effects) is not dict
        or set(effects) != set(_f1_child_budgets)
        or any(
            type(effects[k]) is not int or not 0 <= effects[k] <= b
            for k, b in _f1_child_budgets.items()
        )
    ):
        raise ValueError("child effects rejected")
    if value["classification"] in _f1_progress and (
        value["d1r7"] is None
        or value["d1r8"] is None
        or effects["d1r7_attempts"] != 1
        or effects["d1r8_attempts"] != 1
    ):
        raise ValueError("positive child proof required")
    counts = value["d1r8_effects"]
    if (
        type(counts) is not dict
        or set(counts) != set(_f1_d1r8_budgets)
        or any(
            type(counts[k]) is not int or not 0 <= counts[k] <= b
            for k, b in _f1_d1r8_budgets.items()
        )
    ):
        raise ValueError("D1R8 complete accounting rejected")


def _f1_parse(payload: bytes) -> tuple[dict, ...]:
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= _f1_max_bytes:
            raise ValueError
        rows = tuple(
            json.loads(line, object_pairs_hook=_f1__unique)
            for line in payload.decode().splitlines()
        )
        if (
            not 0 < len(rows) <= _f1_max_rows
            or b"".join(_f1_canonical(r) + b"\n" for r in rows) != payload
        ):
            raise ValueError
        facts = rows[0]["facts"]
        _f1_validate_facts(facts)
        child = facts["kind"] == "child"
        budgets = _f1_child_budgets if child else _f1_budgets
        effects = dict.fromkeys(budgets, 0)
        phase = "START"
        completed = []
        last = _f1_utc(datetime.fromisoformat(facts["authorized_at"]))
        for i, row in enumerate(rows):
            if (
                type(row) is not dict
                or set(row)
                != {
                    "schema",
                    "event",
                    "classification",
                    "facts",
                    "binding",
                    "identity",
                    "effects",
                    "budgets",
                    "observed_at",
                    "proof",
                }
                or row["schema"] != (_f1_child_schema if child else _f1_schema)
                or row["binding"] != _f1_digest(facts)
                or row["identity"] != _f1_domain_id(facts)
                or _f1_canonical(row["facts"])
                != _f1_canonical(facts if i == 0 else None)
                or _f1_canonical(row["budgets"]) != _f1_canonical(budgets)
                or phase == "FINAL"
            ):
                raise ValueError
            now = _f1_utc(datetime.fromisoformat(row["observed_at"]))
            if now.isoformat() != row["observed_at"] or now < last:
                raise ValueError
            last = now
            event = row["event"]
            if event == "FINAL":
                status = row["classification"]
                if i == 0 or status not in (
                    _f1_terminals if child else _f1_terminals | {"COMPLETED"}
                ):
                    raise ValueError
                if child:
                    if status in _f1_progress:
                        if phase != "D1R8_DELEGATION_INTENT":
                            raise ValueError
                        _f1_proof(row["proof"])
                    elif row["proof"] is not None:
                        raise ValueError
                elif status == "COMPLETED":
                    expected = dict(
                        children=completed,
                        scheduler="MATCH",
                        parent_prefix=dict(
                            bytes=len(
                                b"".join(_f1_canonical(r) + b"\n" for r in rows[:i])
                            ),
                            sha256=hashlib.sha256(
                                b"".join(_f1_canonical(r) + b"\n" for r in rows[:i])
                            ).hexdigest(),
                        ),
                    )
                    if (
                        len(completed) != 5
                        or any(
                            c["classification"] not in _f1_progress for c in completed
                        )
                        or _f1_canonical(row["proof"]) != _f1_canonical(expected)
                    ):
                        raise ValueError
                elif status in _f1_progress or row["proof"] is not None:
                    raise ValueError
            else:
                if event not in _f1_allowed(phase, child, completed):
                    raise ValueError
                session_final = (
                    not child
                    and event.startswith("SESSION_")
                    and event.endswith("_FINAL")
                )
                if session_final:
                    _f1_summary(row["proof"], facts, len(completed) + 1)
                    if row["classification"] != row["proof"]["classification"]:
                        raise ValueError
                    completed.append(row["proof"])
                elif row["classification"] is not None:
                    raise ValueError
                if child and event == "D1R7_READY":
                    _f1_proof(row["proof"])
                elif not session_final and row["proof"] is not None:
                    raise ValueError
                for state, counter in (
                    ("SCHEDULER_CREATE_INTENT", "scheduler_creates"),
                    ("SCHEDULER_RUN_INTENT", "scheduler_runs"),
                    ("D1R7_DELEGATION_INTENT", "d1r7_attempts"),
                    ("D1R8_DELEGATION_INTENT", "d1r8_attempts"),
                ):
                    if event == state:
                        effects[counter] += 1
                if not child and event.endswith("_GRANT_INTENT"):
                    effects["child_grants"] += 1
            if _f1_canonical(row["effects"]) != _f1_canonical(effects) or any(
                effects[k] > budgets[k] for k in effects
            ):
                raise ValueError
            phase = event
        return rows
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        UnicodeError,
        OverflowError,
        RecursionError,
    ):
        raise ValueError("F1 canonical journal rejected") from None


_D1R7_READY = "READY_FOR_SEPARATE_D1_SESSION_AUTHORIZATION"

_D1R7_EVENTS = (
    "AUTHORIZATION_RESERVED",
    "SOURCE_ADMITTED",
    "PREDECESSOR_BOUND",
    "SESSION_BOUND",
    "D1_POLICY_BOUND",
    "SOURCE_READMITTED",
    "FINAL",
)

_D1R7_COUNTERS = (
    "d1_invocations",
    "d1r5_invocations",
    "alpaca_requests",
    "provider_requests",
    "credential_reads",
    "credential_writes",
    "oauth_interactions",
    "robinhood_reads",
    "robinhood_reviews",
    "strategy_evaluations",
    "prepare_attempts",
    "execute_attempts",
    "paper_mutations",
    "broker_placements",
    "scheduler_reads",
    "scheduler_creates",
    "scheduler_updates",
    "scheduler_runs",
    "scheduler_deletes",
    "acl_mutations",
    "d2_invocations",
    "live_effects",
    "production_sqlite_reads",
    "production_sqlite_writes",
    "armed_session_store_reads",
    "armed_session_store_writes",
    "review_paper_store_reads",
    "review_paper_store_writes",
)

_D1R7_AUTHORITY = (
    "d1_execution_authorized",
    "prepare_authorized",
    "execute_authorized",
)


def _proof_bytes(payload: bytes) -> dict[str, object]:
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def _parse_d1r7(payload: bytes) -> tuple[dict[str, object], ...]:
    rows = _rows(payload, maximum=131_072, row_limit=len(_D1R7_EVENTS))
    facts = rows[0].get("facts")
    _validate_d1r7_facts(facts)
    expected = tuple(
        {
            "schema": _D1R7_SCHEMA,
            "event": event,
            "classification": _D1R7_READY if event == "FINAL" else None,
            "reason_code": "PREREQUISITES_BOUND" if event == "FINAL" else None,
            "facts": facts,
            "budgets": dict.fromkeys(_D1R7_COUNTERS, 0),
            "effects": dict.fromkeys(_D1R7_COUNTERS, 0),
            "authority": dict.fromkeys(_D1R7_AUTHORITY, False),
        }
        for event in _D1R7_EVENTS
    )
    if _canonical(rows) != _canonical(expected):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "complete exact D1R7 journal required"
        )
    return rows


def parse_f1_parent_journal(payload: bytes) -> tuple[dict, ...]:
    """Independently replay supplied completed F1 bytes; acquire no evidence."""
    try:
        rows = _f1_parse(payload)
        facts = rows[0]["facts"]
        if (
            facts["kind"] != "parent"
            or rows[-1]["event"] != "FINAL"
            or rows[-1]["classification"] != "COMPLETED"
        ):
            raise ValueError("exact completed F1 parent required")
        # Reconstruct the published window using only frozen authorization facts.
        authority = NYSEPublishedRegularSessionAuthority()
        observed = _utc_text(facts["authorized_at"])
        day = observed.astimezone(_NEW_YORK).date()
        targets = []
        for offset in range(40):
            candidate = day + timedelta(days=offset)
            schedule = authority.schedule_for(candidate)
            if schedule is not None and observed < schedule.closes_at.astimezone(
                UTC
            ) - timedelta(minutes=5):
                targets.append(candidate.isoformat())
                if len(targets) == 5:
                    break
        if facts["targets"] != targets:
            raise ValueError("frozen published window mismatch")
        summaries = rows[-1]["proof"]["children"]
        for ordinal, summary in enumerate(summaries, 1):
            grant_index = next(
                i
                for i, r in enumerate(rows)
                if r["event"] == f"SESSION_{ordinal}_GRANT_INTENT"
            )
            prefix = b"".join(_canonical(r) + b"\n" for r in rows[: grant_index + 1])
            child_facts = dict(
                facts,
                kind="child",
                parent_id=rows[0]["identity"],
                parent_prefix=_proof_bytes(prefix),
                ordinal=ordinal,
                target_session=targets[ordinal - 1],
            )
            if summary["grant_prefix"] != _proof_bytes(prefix) or summary[
                "child_id"
            ] != _f1_domain_id(child_facts):
                raise ValueError("immutable grant identity/prefix mismatch")
        return rows
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        StopIteration,
        OverflowError,
    ) as error:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "F1 parent replay rejected"
        ) from error


def _recover_f1_session(
    parent_evidence: bytes,
    child_evidence: bytes,
    d1r7_evidence: bytes,
    d1r8_evidence: bytes,
):
    try:
        parent = parse_f1_parent_journal(parent_evidence)
        child = _f1_parse(child_evidence)
        pf, cf = parent[0]["facts"], child[0]["facts"]
        if (
            cf["kind"] != "child"
            or child[-1]["event"] != "FINAL"
            or child[-1]["classification"] not in _POSITIVE_CLASSIFICATIONS
        ):
            raise ValueError("complete positive child required")
        ordinal = cf["ordinal"]
        summary = parent[-1]["proof"]["children"][ordinal - 1]
        grant_index = next(
            i
            for i, r in enumerate(parent)
            if r["event"] == f"SESSION_{ordinal}_GRANT_INTENT"
        )
        grant = parent[grant_index]
        prefix = b"".join(_canonical(r) + b"\n" for r in parent[: grant_index + 1])
        expected = dict(
            pf,
            kind="child",
            runtime=cf["runtime"],
            parent_id=parent[0]["identity"],
            parent_prefix=_proof_bytes(prefix),
            ordinal=ordinal,
            target_session=pf["targets"][ordinal - 1],
        )
        if _canonical(cf) != _canonical(expected) or _utc_text(
            child[0]["observed_at"]
        ) < _utc_text(grant["observed_at"]):
            raise ValueError("durable grant mismatch")
        final_parent_row = next(
            r for r in parent if r["event"] == f"SESSION_{ordinal}_FINAL"
        )
        if _utc_text(child[-1]["observed_at"]) > _utc_text(
            final_parent_row["observed_at"]
        ):
            raise ValueError("child closes after parent summary")
        for key in ("paper", "sessions", "python"):
            names = (
                ("device", "inode")
                if key != "python"
                else ("device", "inode", "bytes", "sha256")
            )
            if any(
                pf["runtime"][key][name] != cf["runtime"][key][name] for name in names
            ):
                raise ValueError("runtime lineage mismatch")
        r7 = _parse_d1r7(d1r7_evidence)
        r8 = _parse_d1r8(d1r8_evidence)
        p7, p8 = _proof_bytes(d1r7_evidence), _proof_bytes(d1r8_evidence)
        expected_binding = dict(
            prerequisite=r7[0]["facts"],
            d1r7_bytes=p7["bytes"],
            d1r7_sha256=p7["sha256"],
            publication_confirmed=True,
        )
        plan = _validate_d1r8_facts(r8[0]["facts"])
        contract = plan.contract
        target = _date_text(cf["target_session"])
        if (
            _canonical(r8[0]["facts"]) != _canonical(expected_binding)
            or contract.target_session_date != target
            or _canonical(r7[0]["facts"]["strategy_contract"])
            != _canonical(summary["contract"])
        ):
            raise ValueError("exact D1R7/D1R8/contract binding mismatch")
        saved7 = next(r["proof"] for r in child if r["event"] == "D1R7_READY")
        status = child[-1]["classification"]
        if (
            saved7 != p7
            or child[-1]["proof"] != p8
            or r8[-1]["classification"] != status
        ):
            raise ValueError("child supplied proof/classification mismatch")
        expected_summary = dict(
            ordinal=ordinal,
            target_session=target.isoformat(),
            child_id=child[0]["identity"],
            child_journal=_proof_bytes(child_evidence),
            grant_prefix=_proof_bytes(prefix),
            classification=status,
            d1r7=p7,
            d1r8=p8,
            effects=child[-1]["effects"],
            d1r8_effects=r8[-1]["effects"],
            contract=_recovered_contract_facts(contract),
        )
        if _canonical(summary) != _canonical(expected_summary):
            raise ValueError("full parent child proof/effect reconciliation mismatch")
        return parent, child, contract
    except ResearchStrategyF1PaperEvidenceVerificationError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        StopIteration,
        OverflowError,
    ) as error:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "F1 child/evidence reconciliation rejected"
        ) from error


def build_verified_research_strategy_paper_session_observation_v2(
    target_session_date: date,
    parent_evidence: bytes,
    child_evidence: bytes,
    d1r7_evidence: bytes,
    d1r8_evidence: bytes,
    proof: ResearchStrategyProductionCompatibilityProof,
    completed: CompletedResearchStrategyWalkForward,
    qualification: ResearchStrategyWalkForwardQualification,
    qualification_policy: ResearchStrategyWalkForwardQualificationPolicy,
    passed: WalkForwardPassedResearchStrategy,
    target: ProductionStrategySemanticTarget,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    proof_source_head: str,
    proof_source_tree: str,
) -> ResearchStrategyPaperSessionObservationV2:
    """Verify all evidence and construct one positive observation."""
    if type(target_session_date) is not date:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "exact target date required"
        )
    _verify_chain(
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
        proof_source_head=proof_source_head,
        proof_source_tree=proof_source_tree,
    )
    parent, child, contract = _recover_f1_session(
        parent_evidence, child_evidence, d1r7_evidence, d1r8_evidence
    )
    if contract.target_session_date != target_session_date:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "exact requested target mismatch"
        )
    if (
        contract.source_head != target.production_source_head
        or contract.source_tree != target.production_source_tree
        or contract.symbol != target.symbol
        or contract.strategy_config != target.strategy_config
    ):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "production contract does not match verified target"
        )
    try:
        return ResearchStrategyPaperSessionObservationV2(
            compatibility_proof_id=proof.proof_id,
            production_target_id=target.target_id,
            target_session_date=target_session_date,
            production_contract_id=contract.contract_id,
            paper_authority_kind=PAPER_AUTHORITY_KIND,
            paper_authority_schema=PAPER_AUTHORITY_SCHEMA,
            paper_authority_source_head=PAPER_AUTHORITY_SOURCE_HEAD,
            paper_authority_source_tree=PAPER_AUTHORITY_SOURCE_TREE,
            authority_parent_id=UUID(parent[0]["identity"]),
            authority_parent_journal_sha256=hashlib.sha256(parent_evidence).hexdigest(),
            authority_child_ordinal=child[0]["facts"]["ordinal"],
            authority_child_id=UUID(child[0]["identity"]),
            authority_child_journal_sha256=hashlib.sha256(child_evidence).hexdigest(),
            d1r7_source_head=D1R7_SOURCE_HEAD,
            d1r7_source_tree=D1R7_SOURCE_TREE,
            d1r7_evidence_sha256=hashlib.sha256(d1r7_evidence).hexdigest(),
            d1r8_source_head=D1R8_SOURCE_HEAD,
            d1r8_source_tree=D1R8_SOURCE_TREE,
            d1r8_evidence_sha256=hashlib.sha256(d1r8_evidence).hexdigest(),
            terminal_classification=child[-1]["classification"],
            symbol=target.symbol,
            strategy_config=target.strategy_config,
            production_source_head=contract.source_head,
            production_source_tree=contract.source_tree,
        )
    except (
        ResearchStrategyPaperCandidateEligibilityError,
        TypeError,
        ValueError,
    ) as error:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "verified observation construction failed"
        ) from error


def verify_research_strategy_paper_session_observation_v2(
    observation: ResearchStrategyPaperSessionObservationV2,
    parent_evidence: bytes,
    child_evidence: bytes,
    d1r7_evidence: bytes,
    d1r8_evidence: bytes,
    proof: ResearchStrategyProductionCompatibilityProof,
    completed: CompletedResearchStrategyWalkForward,
    qualification: ResearchStrategyWalkForwardQualification,
    qualification_policy: ResearchStrategyWalkForwardQualificationPolicy,
    passed: WalkForwardPassedResearchStrategy,
    target: ProductionStrategySemanticTarget,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    proof_source_head: str,
    proof_source_tree: str,
) -> None:
    """Rebuild one observation from independent evidence and require equality."""
    if type(observation) is not ResearchStrategyPaperSessionObservationV2:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "exact observation required"
        )
    expected = build_verified_research_strategy_paper_session_observation_v2(
        observation.target_session_date,
        parent_evidence,
        child_evidence,
        d1r7_evidence,
        d1r8_evidence,
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
        proof_source_head=proof_source_head,
        proof_source_tree=proof_source_tree,
    )
    if observation != expected:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "observation does not reconcile with complete evidence"
        )


def build_verified_research_strategy_paper_candidate_eligibility_v2(
    parent_evidence: bytes,
    session_evidence: tuple[tuple[date, bytes, bytes, bytes], ...],
    proof: ResearchStrategyProductionCompatibilityProof,
    completed: CompletedResearchStrategyWalkForward,
    qualification: ResearchStrategyWalkForwardQualification,
    qualification_policy: ResearchStrategyWalkForwardQualificationPolicy,
    passed: WalkForwardPassedResearchStrategy,
    target: ProductionStrategySemanticTarget,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    proof_source_head: str,
    proof_source_tree: str,
    eligibility_source_head: str,
    eligibility_source_tree: str,
) -> ResearchStrategyPaperCandidateEligibilityV2:
    """Verify a complete five-session window before positive eligibility."""
    if type(session_evidence) is not tuple or len(session_evidence) != 5:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "exactly five evidence sessions required"
        )
    eligibility_source_head = _source(eligibility_source_head)
    eligibility_source_tree = _source(eligibility_source_tree)
    parse_f1_parent_journal(parent_evidence)
    if any(type(item) is not tuple or len(item) != 4 for item in session_evidence):
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "exact supplied session tuple required"
        )
    observations = tuple(
        build_verified_research_strategy_paper_session_observation_v2(
            session_date,
            parent_evidence,
            child_bytes,
            d1r7_bytes,
            d1r8_bytes,
            proof,
            completed,
            qualification,
            qualification_policy,
            passed,
            target,
            qualification_source_head=qualification_source_head,
            qualification_source_tree=qualification_source_tree,
            proof_source_head=proof_source_head,
            proof_source_tree=proof_source_tree,
        )
        for session_date, child_bytes, d1r7_bytes, d1r8_bytes in session_evidence
    )
    try:
        paper_executed_count = validate_research_strategy_paper_eligibility_window_v2(
            observations, ResearchStrategyPaperSoakPolicy()
        )
        return ResearchStrategyPaperCandidateEligibilityV2(
            compatibility_proof_id=proof.proof_id,
            production_target_id=target.target_id,
            policy_id=ResearchStrategyPaperSoakPolicy().policy_id,
            paper_authority_kind=observations[0].paper_authority_kind,
            paper_authority_schema=observations[0].paper_authority_schema,
            paper_authority_source_head=observations[0].paper_authority_source_head,
            paper_authority_source_tree=observations[0].paper_authority_source_tree,
            authority_parent_id=observations[0].authority_parent_id,
            authority_parent_journal_sha256=observations[
                0
            ].authority_parent_journal_sha256,
            observation_ids=tuple(item.observation_id for item in observations),
            first_session_date=observations[0].target_session_date,
            last_session_date=observations[-1].target_session_date,
            paper_executed_count=paper_executed_count,
            symbol=target.symbol,
            strategy_config=target.strategy_config,
            research_strategy_source_head=completed.definition.strategy_source_head,
            research_strategy_source_tree=completed.definition.strategy_source_tree,
            production_source_head=target.production_source_head,
            production_source_tree=target.production_source_tree,
            eligibility_source_head=eligibility_source_head,
            eligibility_source_tree=eligibility_source_tree,
        )
    except (
        ResearchStrategyPaperCandidateEligibilityError,
        TypeError,
        ValueError,
    ) as error:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "verified five-session window does not qualify"
        ) from error


def verify_research_strategy_paper_candidate_eligibility_v2(
    eligibility: ResearchStrategyPaperCandidateEligibilityV2,
    parent_evidence: bytes,
    session_evidence: tuple[tuple[date, bytes, bytes, bytes], ...],
    proof: ResearchStrategyProductionCompatibilityProof,
    completed: CompletedResearchStrategyWalkForward,
    qualification: ResearchStrategyWalkForwardQualification,
    qualification_policy: ResearchStrategyWalkForwardQualificationPolicy,
    passed: WalkForwardPassedResearchStrategy,
    target: ProductionStrategySemanticTarget,
    *,
    qualification_source_head: str,
    qualification_source_tree: str,
    proof_source_head: str,
    proof_source_tree: str,
    eligibility_source_head: str,
    eligibility_source_tree: str,
) -> None:
    """Rebuild positive eligibility from independent evidence and compare exactly."""
    if type(eligibility) is not ResearchStrategyPaperCandidateEligibilityV2:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "exact eligibility required"
        )
    expected = build_verified_research_strategy_paper_candidate_eligibility_v2(
        parent_evidence,
        session_evidence,
        proof,
        completed,
        qualification,
        qualification_policy,
        passed,
        target,
        qualification_source_head=qualification_source_head,
        qualification_source_tree=qualification_source_tree,
        proof_source_head=proof_source_head,
        proof_source_tree=proof_source_tree,
        eligibility_source_head=_source(eligibility_source_head),
        eligibility_source_tree=_source(eligibility_source_tree),
    )
    if eligibility != expected:
        raise ResearchStrategyF1PaperEvidenceVerificationError(
            "eligibility does not reconcile with complete evidence"
        )
