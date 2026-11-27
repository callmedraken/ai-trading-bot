"""Cached, synthetic Portfolio Manager application service and workers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Condition, Event, Lock
from typing import Protocol
from uuid import UUID

from trading_bot.domain._validation import normalize_utc
from trading_bot.live_prototype.application_service import DesktopWorkers
from trading_bot.portfolio_manager.models import (
    AccountBinding,
    PortfolioObservation,
    canonical_decimal,
)
from trading_bot.portfolio_manager.store import (
    PortfolioManagerStore,
    PortfolioManagerStoreError,
    StoredOutcome,
)

_HISTORY_LIMIT = 100
_SENSITIVE_KEY_PARTS = (
    "account_number",
    "credential",
    "password",
    "secret",
    "oauth",
    "token",
    "cookie",
)


class ServiceLifecycle(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    BLOCKED = "BLOCKED"


class WorkerHealth(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class ObservationSource(Protocol):
    """One injected observation source; PM1 composes only synthetic fakes."""

    def observe(self) -> PortfolioObservation: ...


class EvaluationPipeline(Protocol):
    """Decision, deterministic risk, and preview-only planning boundary."""

    def __call__(
        self, observation: PortfolioObservation, *, decision_at: datetime
    ) -> PipelineEvaluation: ...


@dataclass(frozen=True, slots=True)
class DecisionDisplay:
    symbol: str
    action: str
    target_quantity: str | None
    rationale: str
    evidence_available: bool
    provider_diagnostics: tuple[str, ...]
    risk_status: str
    risk_reasons: tuple[str, ...]
    recommendation_id: str

    def __post_init__(self) -> None:
        for name in (
            "symbol",
            "action",
            "rationale",
            "risk_status",
            "recommendation_id",
        ):
            if (
                not isinstance(getattr(self, name), str)
                or not getattr(self, name).strip()
            ):
                raise ValueError(f"{name} must be nonblank")
        if not isinstance(self.evidence_available, bool):
            raise TypeError("evidence_available must be a bool")
        provider_diagnostics = tuple(self.provider_diagnostics)
        if any(
            not isinstance(item, str) or not item.strip()
            for item in provider_diagnostics
        ):
            raise TypeError("provider_diagnostics must contain nonblank strings")
        object.__setattr__(self, "provider_diagnostics", provider_diagnostics)
        if self.target_quantity is not None and not isinstance(
            self.target_quantity, str
        ):
            raise TypeError("target_quantity must be string or None")
        reasons = tuple(self.risk_reasons)
        if any(not isinstance(reason, str) or not reason.strip() for reason in reasons):
            raise TypeError("risk_reasons must contain nonblank strings")
        object.__setattr__(self, "risk_reasons", reasons)


@dataclass(frozen=True, slots=True)
class PreviewLegDisplay:
    symbol: str
    side: str
    quantity: str
    reference_price: str | None
    status: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("symbol", "side", "quantity", "status"):
            if (
                not isinstance(getattr(self, name), str)
                or not getattr(self, name).strip()
            ):
                raise ValueError(f"{name} must be nonblank")
        if self.reference_price is not None and not isinstance(
            self.reference_price, str
        ):
            raise TypeError("reference_price must be string or None")
        reasons = tuple(self.reasons)
        if any(not isinstance(reason, str) or not reason.strip() for reason in reasons):
            raise TypeError("reasons must contain nonblank strings")
        object.__setattr__(self, "reasons", reasons)


@dataclass(frozen=True, slots=True)
class OutcomePresentation:
    portfolio_snapshot_id: UUID
    research_input_id: UUID
    decision_batch_id: UUID
    strategy_id: str
    strategy_version: str
    decision_at: datetime
    decisions: tuple[DecisionDisplay, ...]
    preview_legs: tuple[PreviewLegDisplay, ...]
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "portfolio_snapshot_id",
            "research_input_id",
            "decision_batch_id",
        ):
            if not isinstance(getattr(self, name), UUID):
                raise TypeError(f"{name} must be UUID")
        for name in ("strategy_id", "strategy_version"):
            if (
                not isinstance(getattr(self, name), str)
                or not getattr(self, name).strip()
            ):
                raise ValueError(f"{name} must be nonblank")
        object.__setattr__(
            self, "decision_at", normalize_utc(self.decision_at, "decision_at")
        )
        decisions = tuple(self.decisions)
        preview_legs = tuple(self.preview_legs)
        diagnostics = tuple(self.diagnostics)
        if any(not isinstance(item, DecisionDisplay) for item in decisions):
            raise TypeError("decisions must contain DecisionDisplay values")
        if any(not isinstance(item, PreviewLegDisplay) for item in preview_legs):
            raise TypeError("preview_legs must contain PreviewLegDisplay values")
        if any(not isinstance(item, str) or not item.strip() for item in diagnostics):
            raise TypeError("diagnostics must contain nonblank strings")
        object.__setattr__(self, "decisions", decisions)
        object.__setattr__(self, "preview_legs", preview_legs)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True, slots=True)
class PipelineEvaluation:
    """One pure domain result plus stable inputs and audit-only facts.

    ``semantic_inputs`` omits polling timestamps and generated IDs. It binds
    stable source/model/risk inputs so repeated synthetic polling or process
    restart cannot create another record for the same semantic evaluation.
    ``audit_payload`` preserves the fuller research, risk, and preview result.
    """

    presentation: OutcomePresentation
    semantic_inputs: dict[str, object]
    audit_payload: dict[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.presentation, OutcomePresentation):
            raise TypeError("presentation must be OutcomePresentation")
        for name in ("semantic_inputs", "audit_payload"):
            value = getattr(self, name)
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be a JSON object")
            copied = _json_copy(value)
            _reject_sensitive_keys(copied)
            object.__setattr__(self, name, copied)


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    stored: StoredOutcome
    presentation: OutcomePresentation


@dataclass(frozen=True, slots=True)
class PortfolioManagerSnapshot:
    lifecycle: ServiceLifecycle
    account_fingerprint: str
    observation: PortfolioObservation | None
    latest: OutcomePresentation | None
    history: tuple[HistoryEntry, ...]
    monitor_health: WorkerHealth
    research_health: WorkerHealth
    diagnostic: str | None = None
    mode: str = "SYNTHETIC / DISARMED"

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, ServiceLifecycle):
            raise TypeError("lifecycle must be ServiceLifecycle")
        AccountBinding(self.account_fingerprint)
        if self.observation is not None and not isinstance(
            self.observation, PortfolioObservation
        ):
            raise TypeError("observation must be PortfolioObservation or None")
        if self.latest is not None and not isinstance(self.latest, OutcomePresentation):
            raise TypeError("latest must be OutcomePresentation or None")
        history = tuple(self.history)
        if any(not isinstance(item, HistoryEntry) for item in history):
            raise TypeError("history must contain HistoryEntry values")
        if not isinstance(self.monitor_health, WorkerHealth):
            raise TypeError("monitor_health must be WorkerHealth")
        if not isinstance(self.research_health, WorkerHealth):
            raise TypeError("research_health must be WorkerHealth")
        object.__setattr__(self, "history", history)


class PortfolioManagerApplicationService:
    """Manually started pair of independent workers with cached GUI facts.

    The monitor publishes adopted observations. The research worker consumes
    those observations and composes the injected decision/risk/preview pipeline.
    It has no execution interface. Stop sets a cooperative event and returns
    without joining a worker, calling a provider, or waiting for SQLite.
    """

    def __init__(
        self,
        *,
        account_binding: AccountBinding,
        state_root: str | Path,
        observation_source: ObservationSource,
        pipeline: EvaluationPipeline,
        monitoring_interval: float = 1.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(account_binding, AccountBinding):
            raise TypeError("an explicit AccountBinding is required")
        if not isinstance(state_root, (str, Path)) or not str(state_root).strip():
            raise ValueError("state_root must be a nonblank path")
        if not callable(getattr(observation_source, "observe", None)):
            raise TypeError("observation_source must implement observe()")
        if not callable(pipeline):
            raise TypeError("pipeline must be callable")
        if (
            isinstance(monitoring_interval, bool)
            or not isinstance(monitoring_interval, (int, float))
            or not 0.01 <= monitoring_interval <= 3600
        ):
            raise ValueError("monitoring_interval must be from 0.01 to 3600 seconds")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._binding = account_binding
        self._source = observation_source
        self._pipeline = pipeline
        self._interval = float(monitoring_interval)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._store = PortfolioManagerStore(state_root, account_binding.fingerprint)
        self._lock = Lock()
        self._condition = Condition(self._lock)
        # Shared only by monitor publication and worker-side DB admission. Stop
        # never acquires this lock, so UI responsiveness is independent of I/O.
        self._preview_admission = Lock()
        self._desktop_workers = DesktopWorkers()
        self._stop = self._desktop_workers.stop_event
        self._generation = 0
        self._snapshot = PortfolioManagerSnapshot(
            lifecycle=ServiceLifecycle.STOPPED,
            account_fingerprint=account_binding.fingerprint,
            observation=None,
            latest=None,
            history=(),
            monitor_health=WorkerHealth.STOPPED,
            research_health=WorkerHealth.STOPPED,
        )

    @property
    def state_path(self) -> Path:
        """Expose only the selected PM account's durable namespace path."""
        return self._store.path

    def snapshot(self) -> PortfolioManagerSnapshot:
        with self._condition:
            self._refresh_lifecycle_locked()
            return self._snapshot

    def start(self) -> bool:
        with self._condition:
            self._refresh_lifecycle_locked()
            if (
                self._snapshot.lifecycle
                in {
                    ServiceLifecycle.STARTING,
                    ServiceLifecycle.RUNNING,
                    ServiceLifecycle.STOPPING,
                }
                or self._workers_alive_locked()
            ):
                return False
            self._generation = 0
            self._snapshot = replace(
                self._snapshot,
                lifecycle=ServiceLifecycle.STARTING,
                observation=None,
                latest=None,
                monitor_health=WorkerHealth.STARTING,
                research_health=WorkerHealth.STARTING,
                diagnostic=None,
            )
            try:
                started, _ = self._desktop_workers.start_workers(
                    (
                        (
                            "portfolio-manager-monitor",
                            self._monitor_loop,
                            (self._stop,),
                        ),
                        (
                            "portfolio-manager-research",
                            self._research_loop,
                            (self._stop,),
                        ),
                    )
                )
            except Exception:
                started = False
            if not started:
                self._stop.set()
                self._snapshot = replace(
                    self._snapshot,
                    lifecycle=ServiceLifecycle.BLOCKED,
                    monitor_health=WorkerHealth.FAILED,
                    research_health=WorkerHealth.FAILED,
                    diagnostic="WORKER_START_FAILED",
                )
                self._condition.notify_all()
                return False
            self._snapshot = replace(self._snapshot, lifecycle=ServiceLifecycle.RUNNING)
            self._condition.notify_all()
            return True

    def stop(self) -> None:
        """Prevent new preview admissions; worker reconciliation remains async."""
        with self._condition:
            # Start clears this event under the same short state lock; setting
            # it here prevents Stop racing with that reset during Start.
            self._stop.set()
            if self._snapshot.lifecycle not in {
                ServiceLifecycle.BLOCKED,
                ServiceLifecycle.STOPPED,
            }:
                self._snapshot = replace(
                    self._snapshot,
                    lifecycle=ServiceLifecycle.STOPPING,
                    monitor_health=(
                        WorkerHealth.STOPPING
                        if self._snapshot.monitor_health is WorkerHealth.RUNNING
                        else self._snapshot.monitor_health
                    ),
                    research_health=(
                        WorkerHealth.STOPPING
                        if self._snapshot.research_health is WorkerHealth.RUNNING
                        else self._snapshot.research_health
                    ),
                )
            self._condition.notify_all()
            self._refresh_lifecycle_locked()

    def shutdown_complete(self) -> bool:
        """Poll worker termination without joining on the caller's thread."""
        with self._condition:
            self._refresh_lifecycle_locked()
            return not self._workers_alive_locked()

    def _monitor_loop(self, stop: Event) -> None:
        self._set_worker_health("monitor_health", WorkerHealth.RUNNING)
        try:
            while not stop.is_set():
                observation = self._source.observe()
                if not isinstance(observation, PortfolioObservation):
                    raise TypeError("observation source returned an invalid value")
                with self._preview_admission:
                    with self._condition:
                        if stop.is_set():
                            break
                        current = self._snapshot.observation
                        same_snapshot = (
                            current is not None
                            and current.snapshot_id == observation.snapshot_id
                        )
                        same_financial_facts = (
                            current is not None
                            and _stable_observation_record(current)
                            == _stable_observation_record(observation)
                        )
                        if not same_snapshot:
                            if not same_financial_facts:
                                self._generation += 1
                            diagnostic = _account_diagnostic(
                                observation, self._binding.fingerprint
                            )
                            self._snapshot = replace(
                                self._snapshot,
                                observation=observation,
                                latest=(
                                    self._snapshot.latest
                                    if same_financial_facts
                                    else None
                                ),
                                diagnostic=diagnostic,
                            )
                            self._condition.notify_all()
                if stop.wait(self._interval):
                    break
        except Exception:
            self._fail("PORTFOLIO_OBSERVATION_FAILED", "monitor_health")
            return
        finally:
            self._set_worker_health("monitor_health", WorkerHealth.STOPPED)
            with self._condition:
                self._refresh_lifecycle_locked()

    def _research_loop(self, stop: Event) -> None:
        self._set_worker_health("research_health", WorkerHealth.RUNNING)
        try:
            try:
                history = self._load_history()
            except Exception:
                self._fail("DURABLE_HISTORY_FAILED", "research_health")
                return
            with self._condition:
                self._snapshot = replace(self._snapshot, history=history)
                self._condition.notify_all()
            consumed_generation = 0
            while not stop.is_set():
                with self._condition:
                    while not stop.is_set() and self._generation <= consumed_generation:
                        self._condition.wait(timeout=0.5)
                    if stop.is_set():
                        break
                    generation = self._generation
                    observation = self._snapshot.observation
                if observation is None:
                    continue
                consumed_generation = generation
                diagnostic = _account_diagnostic(observation, self._binding.fingerprint)
                if diagnostic is not None:
                    with self._condition:
                        self._snapshot = replace(self._snapshot, diagnostic=diagnostic)
                    continue

                try:
                    decision_at = normalize_utc(self._clock(), "decision_at")
                    evaluation = self._pipeline(observation, decision_at=decision_at)
                except Exception:
                    self._fail("PORTFOLIO_RESEARCH_FAILED", "research_health")
                    return
                if not isinstance(evaluation, PipelineEvaluation):
                    self._fail("PORTFOLIO_RESEARCH_FAILED", "research_health")
                    return
                if (
                    evaluation.presentation.portfolio_snapshot_id
                    != observation.snapshot_id
                ):
                    self._fail("PORTFOLIO_RESEARCH_FAILED", "research_health")
                    return
                if stop.is_set():
                    break

                intent_key = _intent_key(
                    self._binding.fingerprint,
                    _stable_observation_record(observation),
                    evaluation.semantic_inputs,
                )
                semantic_digest = _semantic_digest(evaluation.presentation)
                payload = {
                    "schema": "portfolio-manager-outcome/v1",
                    "account_fingerprint": self._binding.fingerprint,
                    "observation": _observation_record(observation),
                    "audit": evaluation.audit_payload,
                    "presentation": _presentation_record(evaluation.presentation),
                }
                # This is the commit linearization boundary. A monitor update
                # and a preview transaction cannot cross it at the same time.
                with self._preview_admission:
                    with self._condition:
                        current = self._snapshot.observation
                        if (
                            stop.is_set()
                            or generation != self._generation
                            or current is None
                            or _stable_observation_record(current)
                            != _stable_observation_record(observation)
                        ):
                            continue
                    try:
                        stored, inserted = self._store.record_outcome(
                            intent_key=intent_key,
                            snapshot_id=observation.snapshot_id,
                            semantic_digest=semantic_digest,
                            recorded_at=evaluation.presentation.decision_at,
                            payload=payload,
                        )
                    except PortfolioManagerStoreError:
                        self._fail("DURABLE_HISTORY_FAILED", "research_health")
                        return
                    except Exception:
                        self._fail("DURABLE_HISTORY_FAILED", "research_health")
                        return
                    presentation = (
                        evaluation.presentation
                        if inserted
                        else _presentation_from_stored(stored)
                    )
                    entry = HistoryEntry(stored, presentation)
                    with self._condition:
                        existing = next(
                            (
                                item
                                for item in self._snapshot.history
                                if item.stored.intent_key == intent_key
                            ),
                            None,
                        )
                        history = self._snapshot.history
                        if existing is None:
                            history = history + (entry,)
                        self._snapshot = replace(
                            self._snapshot,
                            latest=presentation,
                            history=history[-_HISTORY_LIMIT:],
                            diagnostic=None,
                        )
                        self._condition.notify_all()
        except Exception:
            self._fail("PORTFOLIO_RESEARCH_FAILED", "research_health")
            return
        finally:
            self._set_worker_health("research_health", WorkerHealth.STOPPED)
            with self._condition:
                self._refresh_lifecycle_locked()

    def _load_history(self) -> tuple[HistoryEntry, ...]:
        try:
            stored_outcomes = self._store.load_recent(limit=_HISTORY_LIMIT)
        except Exception:
            raise
        entries = []
        for stored in stored_outcomes:
            try:
                entries.append(HistoryEntry(stored, _presentation_from_stored(stored)))
            except Exception:
                raise
        return tuple(entries)

    def _set_worker_health(self, field: str, health: WorkerHealth) -> None:
        with self._condition:
            current = getattr(self._snapshot, field)
            if current is not WorkerHealth.FAILED or health is WorkerHealth.FAILED:
                self._snapshot = replace(self._snapshot, **{field: health})
            self._condition.notify_all()

    def _fail(self, diagnostic: str, field: str) -> None:
        self._stop.set()
        with self._condition:
            self._snapshot = replace(
                self._snapshot,
                lifecycle=ServiceLifecycle.BLOCKED,
                diagnostic=diagnostic,
                **{field: WorkerHealth.FAILED},
            )
            self._condition.notify_all()

    def _workers_alive_locked(self) -> bool:
        return self._desktop_workers.any_active()

    def _refresh_lifecycle_locked(self) -> None:
        if (
            self._snapshot.lifecycle is ServiceLifecycle.STOPPING
            and not self._workers_alive_locked()
        ):
            self._snapshot = replace(self._snapshot, lifecycle=ServiceLifecycle.STOPPED)


def _account_diagnostic(
    observation: PortfolioObservation, expected_fingerprint: str
) -> str | None:
    if observation.account_fingerprint != expected_fingerprint:
        return "ACCOUNT_BINDING_MISMATCH"
    observed_fingerprint = observation.observed_account_fingerprint
    if (
        observed_fingerprint is not None
        and observed_fingerprint != expected_fingerprint
    ):
        return "ACCOUNT_BINDING_MISMATCH"
    return None


def _intent_key(
    account_fingerprint: str,
    stable_observation: dict[str, object],
    semantic_inputs: dict[str, object],
) -> str:
    return _sha256_json(
        {
            "schema": "portfolio-manager-preview-intent/v1",
            "account_fingerprint": account_fingerprint,
            "observation": stable_observation,
            "semantic_inputs": semantic_inputs,
        }
    )


def _semantic_digest(presentation: OutcomePresentation) -> str:
    return _sha256_json(
        {
            "strategy_id": presentation.strategy_id,
            "strategy_version": presentation.strategy_version,
            "decisions": [
                {
                    "symbol": item.symbol,
                    "action": item.action,
                    "target_quantity": item.target_quantity,
                    "rationale": item.rationale,
                    "evidence_available": item.evidence_available,
                    "provider_diagnostics": list(item.provider_diagnostics),
                    "risk_status": item.risk_status,
                    "risk_reasons": list(item.risk_reasons),
                }
                for item in presentation.decisions
            ],
            "preview_legs": [
                {
                    "symbol": item.symbol,
                    "side": item.side,
                    "quantity": item.quantity,
                    "reference_price": item.reference_price,
                    "status": item.status,
                    "reasons": list(item.reasons),
                }
                for item in presentation.preview_legs
            ],
            "diagnostics": list(presentation.diagnostics),
        }
    )


def _stable_observation_record(observation: PortfolioObservation) -> dict[str, object]:
    record = _observation_record(observation)
    record.pop("snapshot_id", None)
    record.pop("observed_at", None)
    for position in record["positions"]:
        position.pop("price_observed_at", None)
    for order in record["orders"]:
        order.pop("created_at", None)
    return record


def _observation_record(observation: PortfolioObservation) -> dict[str, object]:
    coverage = observation.coverage
    return {
        "snapshot_id": str(observation.snapshot_id),
        "observed_at": observation.observed_at.isoformat(),
        "account_fingerprint": observation.account_fingerprint,
        "observed_account_fingerprint": observation.observed_account_fingerprint,
        "broker_reported_equity": _decimal_text(observation.broker_reported_equity),
        "broker_reported_position_value": _decimal_text(
            observation.broker_reported_position_value
        ),
        "local_equity": _decimal_text(observation.locally_computed_equity),
        "cash": _decimal_text(observation.cash),
        "buying_power": _decimal_text(observation.buying_power),
        "unleveraged_buying_power": _decimal_text(observation.unleveraged_buying_power),
        "coverage": {
            "account_bound": coverage.account_bound,
            "portfolio_complete": coverage.portfolio_complete,
            "positions_complete": coverage.positions_complete,
            "quotes_complete": coverage.quotes_complete,
            "pagination_complete": coverage.pagination_complete,
            "order_scope": coverage.order_scope.value,
        },
        "provenance": observation.provenance.value,
        "conditions": [condition.value for condition in observation.conditions],
        "positions": [
            {
                "symbol": str(position.symbol),
                "quantity": canonical_decimal(position.quantity),
                "available_to_sell": canonical_decimal(position.available_to_sell),
                "average_cost": _decimal_text(position.average_cost),
                "current_price": _decimal_text(position.current_price),
                "price_observed_at": (
                    None
                    if position.price_observed_at is None
                    else position.price_observed_at.isoformat()
                ),
                "market_value": _decimal_text(position.market_value),
                "unrealized_pnl": _decimal_text(position.unrealized_pnl),
                "supported": position.supported,
                "position_type": position.position_type.value,
            }
            for position in observation.positions
        ],
        "orders": [
            {
                "order_fingerprint": hashlib.sha256(
                    order.order_id.encode("utf-8")
                ).hexdigest(),
                "symbol": str(order.symbol),
                "side": order.side.casefold(),
                "state": order.state.casefold(),
                "quantity": _decimal_text(order.quantity),
                "filled_quantity": canonical_decimal(order.filled_quantity),
                "created_at": order.created_at.isoformat(),
                "ownership": order.ownership.value,
            }
            for order in observation.orders
        ],
    }


def _presentation_record(presentation: OutcomePresentation) -> dict[str, object]:
    return {
        "portfolio_snapshot_id": str(presentation.portfolio_snapshot_id),
        "research_input_id": str(presentation.research_input_id),
        "decision_batch_id": str(presentation.decision_batch_id),
        "strategy_id": presentation.strategy_id,
        "strategy_version": presentation.strategy_version,
        "decision_at": presentation.decision_at.isoformat(),
        "decisions": [
            {
                "symbol": item.symbol,
                "action": item.action,
                "target_quantity": item.target_quantity,
                "rationale": item.rationale,
                "evidence_available": item.evidence_available,
                "provider_diagnostics": list(item.provider_diagnostics),
                "risk_status": item.risk_status,
                "risk_reasons": list(item.risk_reasons),
                "recommendation_id": item.recommendation_id,
            }
            for item in presentation.decisions
        ],
        "preview_legs": [
            {
                "symbol": item.symbol,
                "side": item.side,
                "quantity": item.quantity,
                "reference_price": item.reference_price,
                "status": item.status,
                "reasons": list(item.reasons),
            }
            for item in presentation.preview_legs
        ],
        "diagnostics": list(presentation.diagnostics),
    }


def _presentation_from_stored(stored: StoredOutcome) -> OutcomePresentation:
    try:
        payload = json.loads(stored.payload_json)
        value = payload["presentation"]
        return OutcomePresentation(
            portfolio_snapshot_id=UUID(value["portfolio_snapshot_id"]),
            research_input_id=UUID(value["research_input_id"]),
            decision_batch_id=UUID(value["decision_batch_id"]),
            strategy_id=value["strategy_id"],
            strategy_version=value["strategy_version"],
            decision_at=datetime.fromisoformat(value["decision_at"]),
            decisions=tuple(
                DecisionDisplay(
                    symbol=item["symbol"],
                    action=item["action"],
                    target_quantity=item["target_quantity"],
                    rationale=item["rationale"],
                    evidence_available=item["evidence_available"],
                    provider_diagnostics=tuple(item["provider_diagnostics"]),
                    risk_status=item["risk_status"],
                    risk_reasons=tuple(item["risk_reasons"]),
                    recommendation_id=item["recommendation_id"],
                )
                for item in value["decisions"]
            ),
            preview_legs=tuple(
                PreviewLegDisplay(
                    symbol=item["symbol"],
                    side=item["side"],
                    quantity=item["quantity"],
                    reference_price=item["reference_price"],
                    status=item["status"],
                    reasons=tuple(item["reasons"]),
                )
                for item in value["preview_legs"]
            ),
            diagnostics=tuple(value["diagnostics"]),
        )
    except Exception:
        raise ValueError("stored presentation is malformed") from None


def _decimal_text(value) -> str | None:
    return None if value is None else canonical_decimal(value)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _json_copy(value: dict[str, object]) -> dict[str, object]:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        decoded = json.loads(encoded)
    except (TypeError, ValueError):
        raise ValueError("pipeline audit facts must be JSON-safe") from None
    if not isinstance(decoded, dict):
        raise ValueError("pipeline audit facts must be a JSON object")
    return deepcopy(decoded)


def _reject_sensitive_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).casefold()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                raise ValueError("pipeline audit payload contains a prohibited field")
            _reject_sensitive_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_keys(nested)
