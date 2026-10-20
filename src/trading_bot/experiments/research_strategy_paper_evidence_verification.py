"""Pure Architecture-144-B paper-evidence verification composition.

This module accepts only caller-supplied canonical bytes and inert 142/143
artifacts.  The D1R8/D1R9 reducers below are deliberately limited to canonical
byte parsing and state replay; they do not expose the operational journal
stores, filesystem, scheduler, provider, credential, broker, or paper-state
capabilities of those runtimes.
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
    ResearchStrategyPaperCandidateEligibility,
    ResearchStrategyPaperCandidateEligibilityError,
    ResearchStrategyPaperSessionObservation,
    ResearchStrategyPaperSoakPolicy,
    validate_research_strategy_paper_eligibility_window,
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

D1R9_SCHEMA = "arch134-d1r9-one-session-supervisor/v1"
D1R9_BRANCH = "feature/robinhood-production-paper-d1-arbitrary-time-supervisor"
D1R9_SOURCE_HEAD = "efd1e6763dc4663d9c4b2444e785eb1c32adf8e8"
D1R9_SOURCE_TREE = "25a962daf3922c4226c7e395eba8613e1b03bbaf"
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

D1R9_MAX_BYTES = 131_072
D1R9_MAX_ROWS = 128
D1R9_TERMINALS = frozenset(
    {
        "NO_SIGNAL",
        "RISK_REJECTED",
        "PAPER_EXECUTED",
        "SESSION_MISSED",
        "BLOCKED",
        "INDETERMINATE",
    }
)
D1R9_BUDGETS = {
    "d1r7_attempts": 1,
    "d1r8_attempts": 1,
    "scheduler_creates": 1,
    "scheduler_updates": 0,
    "scheduler_runs": 1,
}
D1R9_INITIAL = ("AUTHORIZATION_RESERVED", "SOURCES_ADMITTED", "TARGET_BOUND")

_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA64 = re.compile(r"[0-9a-f]{64}")
_NEW_YORK = ZoneInfo("America/New_York")
_D1R7_CHECKPOINT = "arch134-d1r7-d1-session-authorization"
_D1R7_SCHEMA = "arch134-d1r7-d1-session-authorization/v1"
_CONTRACT_NAMESPACE = UUID("c0867c3b-548e-5512-a135-3c4f1225e6fc")
_CONTRACT_IDENTITY_VERSION = "production-strategy-contract-identity/v1"
_POSITIVE_CLASSIFICATIONS = frozenset({"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"})


class ResearchStrategyPaperEvidenceVerificationError(
    ResearchStrategyPaperCandidateEligibilityError
):
    """Malformed, incomplete, or independently unreconciled paper evidence."""


ResearchStrategyPaperEvidenceError = ResearchStrategyPaperEvidenceVerificationError


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ResearchStrategyPaperEvidenceVerificationError(
                "duplicate canonical field"
            )
        result[name] = value
    return result


def _reject_constant(value: str) -> None:
    raise ResearchStrategyPaperEvidenceVerificationError(f"non-JSON constant {value}")


def _rows(
    payload: bytes, *, maximum: int, row_limit: int
) -> tuple[dict[str, object], ...]:
    if type(payload) is not bytes or not 0 < len(payload) <= maximum:
        raise ResearchStrategyPaperEvidenceVerificationError(
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
        raise ResearchStrategyPaperEvidenceVerificationError(
            "canonical evidence JSON rejected"
        ) from None
    if not 0 < len(rows) <= row_limit or any(type(row) is not dict for row in rows):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "canonical evidence rows rejected"
        )
    try:
        canonical = b"".join(_canonical(row) + b"\n" for row in rows)
    except (TypeError, ValueError, OverflowError):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "canonical evidence rows rejected"
        ) from None
    if canonical != payload:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "noncanonical or incomplete evidence bytes"
        )
    return rows


def _hash(value: object, length: int) -> str:
    if type(value) is not str or len(value) != length:
        raise ResearchStrategyPaperEvidenceVerificationError("lowercase hash required")
    if any(char not in "0123456789abcdef" for char in value):
        raise ResearchStrategyPaperEvidenceVerificationError("lowercase hash required")
    return value


def _source(value: object) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise ResearchStrategyPaperEvidenceVerificationError("source digest required")
    return value


def _date_text(value: object) -> date:
    if type(value) is not str:
        raise ResearchStrategyPaperEvidenceVerificationError("date text required")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "canonical date required"
        ) from None
    if result.isoformat() != value:
        raise ResearchStrategyPaperEvidenceVerificationError("canonical date required")
    return result


def _utc_text(value: object) -> datetime:
    if type(value) is not str:
        raise ResearchStrategyPaperEvidenceVerificationError("aware timestamp required")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "canonical aware timestamp required"
        ) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "canonical aware timestamp required"
        )
    normalized = parsed.astimezone(UTC)
    if normalized.isoformat() != value:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "canonical UTC timestamp required"
        )
    return normalized


def _exact(value: object, expected: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise ResearchStrategyPaperEvidenceVerificationError(
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
        raise ResearchStrategyPaperEvidenceVerificationError(
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
            raise ResearchStrategyPaperEvidenceVerificationError(
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
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract schema/family/version mismatch"
        )
    target = _date_text(raw["target_session_date"])
    head = _source(raw["source_head"])
    tree = _source(raw["source_tree"])
    symbol_text = raw["symbol"]
    if type(symbol_text) is not str or str(Symbol(symbol_text)) != symbol_text:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract symbol rejected"
        )
    config_raw = _exact(
        raw["strategy_config"], {"short_window", "long_window", "desired_quantity"}
    )
    if (
        type(config_raw["short_window"]) is not int
        or type(config_raw["long_window"]) is not int
    ):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract windows rejected"
        )
    quantity = config_raw["desired_quantity"]
    if type(quantity) is not str:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract Decimal rejected"
        )
    try:
        parsed_quantity = Decimal(quantity)
        config = MovingAverageCrossoverConfig(
            config_raw["short_window"], config_raw["long_window"], parsed_quantity
        )
    except (ArithmeticError, TypeError, ValueError):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract configuration rejected"
        ) from None
    if _decimal(parsed_quantity) != quantity:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract Decimal is noncanonical"
        )
    symbol = Symbol(symbol_text)
    material = _contract_material(target, head, tree, symbol, config)
    try:
        contract_id = UUID(raw["contract_id"])
    except (TypeError, ValueError):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract ID rejected"
        ) from None
    if (
        str(contract_id) != raw["contract_id"]
        or contract_id.version != 5
        or contract_id != uuid5(_CONTRACT_NAMESPACE, material)
    ):
        raise ResearchStrategyPaperEvidenceVerificationError(
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
        "arch134-d1r6-overnight-wake-arming-2026-10-16-"
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
        raise ResearchStrategyPaperEvidenceVerificationError("D1R7 checkpoint rejected")
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
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R7 source lineage rejected"
        )
    target = _date_text(raw["target_session"])
    observed = _utc_text(raw["observed_at"])
    expires = _utc_text(raw["authorization_expires_at"])
    derived_target = observed.astimezone(_NEW_YORK).date()
    if target != derived_target:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R7 target session derivation rejected"
        )
    try:
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(target)
    except (TypeError, ValueError):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R7 published session rejected"
        ) from None
    if schedule is None:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R7 published session rejected"
        )
    expected_expires = schedule.closes_at.astimezone(UTC) - timedelta(minutes=5)
    if observed >= expected_expires or expires != expected_expires:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R7 authorization expiry rejected"
        )
    contract = _recover_contract(raw["strategy_contract"])
    if contract.target_session_date != target:
        raise ResearchStrategyPaperEvidenceVerificationError(
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
        raise ResearchStrategyPaperEvidenceVerificationError(
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
        raise ResearchStrategyPaperEvidenceVerificationError(
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
            raise ResearchStrategyPaperEvidenceVerificationError(
                "D1R8 state binding rejected"
            )
        result_hash = row["result_sha256"]
        needs_hash = row["event"] in D1R8_HASHED_STATES and row["action"] is None
        if needs_hash:
            _hash(result_hash, 64)
        elif result_hash is not None:
            raise ResearchStrategyPaperEvidenceVerificationError(
                "D1R8 result hash rejected"
            )
        observed = _utc_text(row["observed_at"])
        if observed < self.last_time:
            raise ResearchStrategyPaperEvidenceVerificationError(
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
                raise ResearchStrategyPaperEvidenceVerificationError(
                    "D1R8 terminal rejected"
                )
            if self.pending is not None and result != "INDETERMINATE":
                raise ResearchStrategyPaperEvidenceVerificationError(
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
                    raise ResearchStrategyPaperEvidenceVerificationError(
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
                        raise ResearchStrategyPaperEvidenceVerificationError(
                            "D1R8 order history bound rejected"
                        )
                if any(self.effects[key] != value for key, value in expected.items()):
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R8 effects rejected"
                    )
            self.terminal = True
        else:
            if row["classification"] is not None:
                raise ResearchStrategyPaperEvidenceVerificationError(
                    "D1R8 intermediate classification rejected"
                )
            if action is None:
                if (
                    counter is not None
                    or self.pending is not None
                    or self.phase + 1 >= len(D1R8_STATES)
                    or event != D1R8_STATES[self.phase + 1]
                ):
                    raise ResearchStrategyPaperEvidenceVerificationError(
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
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R8 state effects rejected"
                    )
                if event == "REVIEW_INTENT":
                    self.baseline_pages = self.effects["order_history_attempts"]
                    if not 1 <= self.baseline_pages <= 100:
                        raise ResearchStrategyPaperEvidenceVerificationError(
                            "D1R8 baseline bound rejected"
                        )
                if (
                    event == "PAPER_WRITE_INTENT"
                    and not 1
                    <= self.effects["order_history_attempts"] - self.baseline_pages
                    <= 100
                ):
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R8 post-review bound rejected"
                    )
            else:
                if (
                    self.phase < 0
                    or event != D1R8_STATES[self.phase]
                    or counter not in D1R8_ALLOWED
                ):
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R8 effect transition rejected"
                    )
                permitted = D1R8_ALLOWED[counter]
                if event not in ((permitted,) if type(permitted) is str else permitted):
                    raise ResearchStrategyPaperEvidenceVerificationError(
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
                    raise ResearchStrategyPaperEvidenceVerificationError(
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
            raise ResearchStrategyPaperEvidenceVerificationError(
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
            raise ResearchStrategyPaperEvidenceVerificationError(
                "D1R8 terminal evidence required"
            )
        return rows
    except ResearchStrategyPaperEvidenceVerificationError:
        raise
    except (KeyError, TypeError, IndexError, ValueError, OverflowError):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R8 canonical journal rejected"
        ) from None


def _validate_d1r9_facts(value: object) -> None:
    facts = _exact(
        value,
        {
            "source",
            "d1r7",
            "d1r8",
            "target_session",
            "authorized_at",
            "symbol",
            "runtime",
        },
    )
    source = _exact(facts["source"], {"branch", "head", "tree"})
    if (
        source["branch"] != D1R9_BRANCH
        or source["head"] != D1R9_SOURCE_HEAD
        or source["tree"] != D1R9_SOURCE_TREE
        or facts["d1r7"]
        != {
            "branch": D1R7_BRANCH,
            "head": D1R7_SOURCE_HEAD,
            "tree": D1R7_SOURCE_TREE,
        }
        or facts["d1r8"]
        != {
            "branch": D1R8_BRANCH,
            "head": D1R8_SOURCE_HEAD,
            "tree": D1R8_SOURCE_TREE,
        }
        or facts["symbol"] != "SPY"
    ):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R9 source binding rejected"
        )
    _date_text(facts["target_session"])
    _utc_text(facts["authorized_at"])
    runtime = _exact(facts["runtime"], {"paper", "sessions", "python"})
    for binding in runtime.values():
        raw = _exact(binding, {"device", "inode", "bytes", "sha256"})
        if (
            any(
                type(raw[name]) is not int or raw[name] < 0
                for name in ("device", "inode", "bytes")
            )
            or raw["inode"] == 0
        ):
            raise ResearchStrategyPaperEvidenceVerificationError(
                "D1R9 runtime binding rejected"
            )
        _hash(raw["sha256"], 64)


def _parse_d1r9(payload: bytes) -> tuple[dict[str, object], ...]:
    rows = _rows(payload, maximum=D1R9_MAX_BYTES, row_limit=D1R9_MAX_ROWS)
    try:
        facts = rows[0]["facts"]
        _validate_d1r9_facts(facts)
        binding = hashlib.sha256(_canonical(facts)).hexdigest()
        effects = dict.fromkeys(D1R9_BUDGETS, 0)
        phase = "START"
        last_time = _utc_text(facts["authorized_at"])  # type: ignore[index]
        ready = False
        for index, row in enumerate(rows):
            if (
                set(row)
                != {
                    "schema",
                    "event",
                    "classification",
                    "facts",
                    "binding",
                    "effects",
                    "budgets",
                    "observed_at",
                    "proof",
                }
                or row["schema"] != D1R9_SCHEMA
                or row["binding"] != binding
                or _canonical(row["facts"]) != _canonical(facts if index == 0 else None)
                or _canonical(row["budgets"]) != _canonical(D1R9_BUDGETS)
                or phase == "FINAL"
            ):
                raise ResearchStrategyPaperEvidenceVerificationError(
                    "D1R9 row binding rejected"
                )
            now = _utc_text(row["observed_at"])
            if now < last_time:
                raise ResearchStrategyPaperEvidenceVerificationError(
                    "D1R9 clock order rejected"
                )
            last_time = now
            event = row["event"]
            if event == "FINAL":
                if row["classification"] not in D1R9_TERMINALS or index == 0:
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 terminal rejected"
                    )
                success = row["classification"] in _POSITIVE_CLASSIFICATIONS
                if success and phase != "D1R8_DELEGATION_INTENT":
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 success state rejected"
                    )
                if success != (row["proof"] is not None):
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 terminal proof rejected"
                    )
                phase = "FINAL"
            else:
                if row["classification"] is not None:
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 intermediate classification rejected"
                    )
                allowed = {
                    "START": {D1R9_INITIAL[0]},
                    D1R9_INITIAL[0]: {D1R9_INITIAL[1]},
                    D1R9_INITIAL[1]: {D1R9_INITIAL[2]},
                    D1R9_INITIAL[2]: {"SCHEDULER_CREATE_INTENT", "SUPERVISOR_READY"},
                    "SCHEDULER_CREATE_INTENT": {"SCHEDULER_CREATE_ACK"},
                    "SCHEDULER_CREATE_ACK": {"SUPERVISOR_READY"},
                    "SUPERVISOR_READY": {"SCHEDULER_RUN_INTENT"},
                    "SCHEDULER_RUN_INTENT": {"SCHEDULER_RUN_ACK"},
                    "SCHEDULER_RUN_ACK": {
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
                }
                if event not in allowed[phase]:
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 state transition rejected"
                    )
                for state, counter in (
                    ("D1R7_DELEGATION_INTENT", "d1r7_attempts"),
                    ("D1R8_DELEGATION_INTENT", "d1r8_attempts"),
                    ("SCHEDULER_CREATE_INTENT", "scheduler_creates"),
                    ("SCHEDULER_RUN_INTENT", "scheduler_runs"),
                ):
                    if event == state:
                        effects[counter] += 1
                if (event == "D1R7_READY") != (row["proof"] is not None):
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 D1R7 proof rejected"
                    )
                if event == "D1R7_READY":
                    ready = True
                if event == "D1R8_DELEGATION_INTENT" and not ready:
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 D1R7 readiness rejected"
                    )
                phase = event
            proof = row["proof"]
            if proof is not None:
                proof_raw = _exact(proof, {"bytes", "sha256"})
                if (
                    type(proof_raw["bytes"]) is not int
                    or not 0 < proof_raw["bytes"] <= D1R8_MAX_BYTES
                ):
                    raise ResearchStrategyPaperEvidenceVerificationError(
                        "D1R9 proof bytes rejected"
                    )
                _hash(proof_raw["sha256"], 64)
            if _canonical(row["effects"]) != _canonical(effects) or any(
                effects[key] > D1R9_BUDGETS[key] for key in effects
            ):
                raise ResearchStrategyPaperEvidenceVerificationError(
                    "D1R9 effect accounting rejected"
                )
        if phase != "FINAL":
            raise ResearchStrategyPaperEvidenceVerificationError(
                "D1R9 terminal evidence required"
            )
        return rows
    except ResearchStrategyPaperEvidenceVerificationError:
        raise
    except (KeyError, TypeError, IndexError, ValueError, OverflowError):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R9 canonical journal rejected"
        ) from None


def _raise_chain_error(error: Exception) -> None:
    raise ResearchStrategyPaperEvidenceVerificationError(
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


def _recover_session(
    target_session_date: date,
    d1r9_evidence: bytes,
    d1r8_evidence: bytes,
) -> tuple[_RecoveredContract, str, str, str, str]:
    r9_rows = _parse_d1r9(d1r9_evidence)
    r8_rows = _parse_d1r8(d1r8_evidence)
    r9_facts = r9_rows[0]["facts"]
    r8_binding = r8_rows[0]["facts"]
    plan = _validate_d1r8_facts(r8_binding)
    contract = plan.contract
    r9_target = _date_text(r9_facts["target_session"])  # type: ignore[index]
    r8_target = _date_text(r8_binding["prerequisite"]["target_session"])  # type: ignore[index]
    if (r9_target, r8_target, contract.target_session_date) != (
        target_session_date,
        target_session_date,
        target_session_date,
    ):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R9/D1R8/contract target mismatch"
        )
    r9_classification = r9_rows[-1]["classification"]
    r8_classification = r8_rows[-1]["classification"]
    if (
        r9_classification != r8_classification
        or r9_classification not in _POSITIVE_CLASSIFICATIONS
    ):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R9/D1R8 terminal classification mismatch"
        )
    proof = r9_rows[-1]["proof"]
    expected_proof = {
        "bytes": len(d1r8_evidence),
        "sha256": hashlib.sha256(d1r8_evidence).hexdigest(),
    }
    if proof != expected_proof:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "D1R9/D1R8 journal proof mismatch"
        )
    return (
        contract,
        r9_facts["source"]["head"],  # type: ignore[index]
        r9_facts["source"]["tree"],  # type: ignore[index]
        r8_binding["prerequisite"]["intended_d1"]["head"],  # type: ignore[index]
        r8_binding["prerequisite"]["intended_d1"]["tree"],  # type: ignore[index]
    )


def build_verified_research_strategy_paper_session_observation(
    target_session_date: date,
    d1r9_evidence: bytes,
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
) -> ResearchStrategyPaperSessionObservation:
    """Verify all evidence and construct one positive observation."""
    if type(target_session_date) is not date:
        raise ResearchStrategyPaperEvidenceVerificationError(
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
    contract, d1r9_head, d1r9_tree, d1r8_head, d1r8_tree = _recover_session(
        target_session_date, d1r9_evidence, d1r8_evidence
    )
    if (
        contract.source_head != target.production_source_head
        or contract.source_tree != target.production_source_tree
        or contract.symbol != target.symbol
        or contract.strategy_config != target.strategy_config
    ):
        raise ResearchStrategyPaperEvidenceVerificationError(
            "production contract does not match verified target"
        )
    try:
        return ResearchStrategyPaperSessionObservation(
            compatibility_proof_id=proof.proof_id,
            production_target_id=target.target_id,
            target_session_date=target_session_date,
            production_contract_id=contract.contract_id,
            d1r9_source_head=d1r9_head,
            d1r9_source_tree=d1r9_tree,
            d1r8_source_head=d1r8_head,
            d1r8_source_tree=d1r8_tree,
            d1r9_journal_sha256=hashlib.sha256(d1r9_evidence).hexdigest(),
            d1r8_journal_sha256=hashlib.sha256(d1r8_evidence).hexdigest(),
            terminal_classification=_parse_d1r9(d1r9_evidence)[-1]["classification"],
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
        raise ResearchStrategyPaperEvidenceVerificationError(
            "verified observation construction failed"
        ) from error


def verify_research_strategy_paper_session_observation(
    observation: ResearchStrategyPaperSessionObservation,
    d1r9_evidence: bytes,
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
    if type(observation) is not ResearchStrategyPaperSessionObservation:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "exact observation required"
        )
    expected = build_verified_research_strategy_paper_session_observation(
        observation.target_session_date,
        d1r9_evidence,
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
        raise ResearchStrategyPaperEvidenceVerificationError(
            "observation does not reconcile with complete evidence"
        )


def build_verified_research_strategy_paper_candidate_eligibility(
    session_evidence: tuple[tuple[date, bytes, bytes], ...],
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
) -> ResearchStrategyPaperCandidateEligibility:
    """Verify a complete five-session window before positive eligibility."""
    if type(session_evidence) is not tuple or len(session_evidence) != 5:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "exactly five evidence sessions required"
        )
    eligibility_source_head = _source(eligibility_source_head)
    eligibility_source_tree = _source(eligibility_source_tree)
    observations = tuple(
        build_verified_research_strategy_paper_session_observation(
            session_date,
            d1r9_bytes,
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
        for session_date, d1r9_bytes, d1r8_bytes in session_evidence
    )
    try:
        paper_executed_count = validate_research_strategy_paper_eligibility_window(
            observations, ResearchStrategyPaperSoakPolicy()
        )
        return ResearchStrategyPaperCandidateEligibility(
            compatibility_proof_id=proof.proof_id,
            production_target_id=target.target_id,
            policy_id=ResearchStrategyPaperSoakPolicy().policy_id,
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
        raise ResearchStrategyPaperEvidenceVerificationError(
            "verified five-session window does not qualify"
        ) from error


def verify_research_strategy_paper_candidate_eligibility(
    eligibility: ResearchStrategyPaperCandidateEligibility,
    session_evidence: tuple[tuple[date, bytes, bytes], ...],
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
    if type(eligibility) is not ResearchStrategyPaperCandidateEligibility:
        raise ResearchStrategyPaperEvidenceVerificationError(
            "exact eligibility required"
        )
    expected = build_verified_research_strategy_paper_candidate_eligibility(
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
        raise ResearchStrategyPaperEvidenceVerificationError(
            "eligibility does not reconcile with complete evidence"
        )


__all__ = [
    "D1R8_BRANCH",
    "D1R8_SCHEMA",
    "D1R8_SOURCE_HEAD",
    "D1R8_SOURCE_TREE",
    "D1R9_BRANCH",
    "D1R9_SCHEMA",
    "D1R9_SOURCE_HEAD",
    "D1R9_SOURCE_TREE",
    "ResearchStrategyPaperEvidenceError",
    "ResearchStrategyPaperEvidenceVerificationError",
    "build_verified_research_strategy_paper_candidate_eligibility",
    "build_verified_research_strategy_paper_session_observation",
    "verify_research_strategy_paper_candidate_eligibility",
    "verify_research_strategy_paper_session_observation",
]
