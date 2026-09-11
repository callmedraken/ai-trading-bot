"""Prepare one supervised Paper-v2 operation without executing or mutating it.

The production boundary validates one genuine C1 authority and one exact P2
selected-snapshot result before entering PD2B1.  All mutable account material
then comes only from the post-lock read.  The Architecture-67 binding is kept
process-local and is valid only while the same account mutex remains held.
"""

from __future__ import annotations

import threading
import weakref
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Self
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    IdentifiedMarketCalendar,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    CheckpointedVerifiedSnapshotPaperCycleRequest,
    VerifiedPriorCheckpoint,
    derive_checkpointed_verified_snapshot_application_id,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotAuditEvidence,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadResult,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperPriorCheckpointEvidence,
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyPlanArtifactBinding,
    ManualPaperStrategyPlanRequest,
    build_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactEvidence,
    PaperAccountLineageArtifactKind,
)
from trading_bot.runtime.paper_operation import (
    PaperOperationArtifactEvidence,
    create_paper_operation_intent,
)
from trading_bot.runtime.paper_operation_execution_inputs import (
    VerifiedPaperOperationExecutionInputs,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexState,
)
from trading_bot.runtime.personal_desktop_supervised_paper_cycle import (
    SupervisedPersonalDesktopPaperCycle,
    supervised_personal_desktop_paper_cycle,
)
from trading_bot.runtime.strategy_history_seed import VerifiedStrategyHistorySeed
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig


class SupervisedPaperOperationPreparationError(PersonalDesktopPaperAccountError):
    """A supervised source-only operation preparation failed closed."""


class PaperOperationPreparationReconciliationRequiredError(
    SupervisedPaperOperationPreparationError
):
    """Abandoned mutex ownership requires reconciliation before preparation."""


class _SupervisedCycleFactory(Protocol):
    def __call__(
        self,
        authority: ValidatedProductionAuthority,
        *,
        historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
    ) -> SupervisedPersonalDesktopPaperCycle: ...


class _BuildPlan(Protocol):
    def __call__(
        self,
        request: ManualPaperStrategyPlanRequest,
        calendar: IdentifiedMarketCalendar,
    ) -> ManualPaperStrategyPlanArtifactBinding: ...


class _VerifyPlan(Protocol):
    def __call__(
        self,
        payload: bytes,
        calendar: IdentifiedMarketCalendar,
        *,
        expected_sha256: str | None = None,
        expected_byte_length: int | None = None,
        expected_checkpointed_request: (
            CheckpointedVerifiedSnapshotPaperCycleRequest | None
        ) = None,
    ) -> ManualPaperStrategyPlanArtifactBinding: ...


class _MatchSelectedSnapshot(Protocol):
    def __call__(
        self,
        permit: SelectedC3SnapshotPermit,
        audit: SelectedC3SnapshotAuditEvidence,
        authority: ValidatedProductionAuthority,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _PreparationAudit:
    paper_account_id: str
    plan_id: UUID
    operation_id: UUID
    application_id: UUID
    selected_snapshot_id: UUID
    plan_artifact_sha256: str
    plan_artifact_byte_length: int
    mutex_acquisition_state: PaperAccountMutexState


@dataclass(frozen=True, slots=True)
class _PreparedPaperOperationBinding:
    operation_root: str
    execution_inputs: VerifiedPaperOperationExecutionInputs


@dataclass(frozen=True, slots=True)
class _PreparedPaperOperationMaterial:
    """Pure post-lock plan and A67 inputs with no filesystem authority."""

    plan_binding: ManualPaperStrategyPlanArtifactBinding
    execution_inputs: VerifiedPaperOperationExecutionInputs


_CONTEXT_KEY = object()
_ACTIVE_BINDINGS: weakref.WeakKeyDictionary[
    _SupervisedPaperOperationPreparation, _PreparedPaperOperationBinding
] = weakref.WeakKeyDictionary()
_ACTIVE_BINDINGS_LOCK = threading.Lock()


class _SupervisedPaperOperationPreparation:
    """One-shot preparation whose private A67 binding lives only under PD2A."""

    __slots__ = (
        "__weakref__",
        "_audit",
        "_authority",
        "_build_plan",
        "_calendar",
        "_configurations",
        "_exit_stack",
        "_filled_at",
        "_history_seed",
        "_metadata",
        "_match_selected_snapshot",
        "_open_reference",
        "_planning_at",
        "_policies",
        "_selected_snapshot",
        "_strategy_config",
        "_submitted_at",
        "_supervised_cycle",
        "_used",
        "_user_key",
        "_verify_plan",
    )

    def __init__(
        self,
        authority: ValidatedProductionAuthority,
        selected_snapshot: SelectedC3SnapshotReadResult,
        *,
        history_seed: VerifiedStrategyHistorySeed,
        strategy_config: MovingAverageCrossoverConfig,
        caller_idempotency_key: UUID,
        open_reference: CallerAssertedNextSessionOpenReference,
        policies: VerifiedSnapshotPaperCyclePolicies,
        planning_at: datetime,
        submitted_at: datetime,
        filled_at: datetime,
        metadata: tuple[MetadataEntry, ...],
        historical_cycle_configuration_payloads: tuple[bytes, ...],
        supervised_cycle: _SupervisedCycleFactory,
        build_plan: _BuildPlan,
        verify_plan: _VerifyPlan,
        match_selected_snapshot: _MatchSelectedSnapshot,
        calendar: IdentifiedMarketCalendar,
        _key: object,
    ) -> None:
        if _key is not _CONTEXT_KEY:
            raise SupervisedPaperOperationPreparationError(
                "supervised operation preparation requires production authority"
            )
        if type(caller_idempotency_key) is not UUID:
            raise SupervisedPaperOperationPreparationError(
                "caller idempotency key must be an exact UUID"
            )
        if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
            raise SupervisedPaperOperationPreparationError(
                "selected snapshot must be an exact P2 read result"
            )
        if not callable(match_selected_snapshot):
            raise SupervisedPaperOperationPreparationError(
                "selected snapshot matcher is invalid"
            )
        self._authority = authority
        self._selected_snapshot = selected_snapshot
        self._history_seed = history_seed
        self._strategy_config = strategy_config
        self._user_key = caller_idempotency_key
        self._open_reference = open_reference
        self._policies = policies
        self._planning_at = planning_at
        self._submitted_at = submitted_at
        self._filled_at = filled_at
        self._metadata = metadata
        self._configurations = historical_cycle_configuration_payloads
        self._supervised_cycle = supervised_cycle
        self._build_plan = build_plan
        self._verify_plan = verify_plan
        self._match_selected_snapshot = match_selected_snapshot
        self._calendar = calendar
        self._exit_stack: ExitStack | None = None
        self._audit: _PreparationAudit | None = None
        self._used = False

    def __copy__(self) -> object:
        raise TypeError("supervised operation preparations cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("supervised operation preparations cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("supervised operation preparations cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("supervised operation preparations cannot be pickled")

    def __enter__(self) -> Self:
        if self._used:
            raise SupervisedPaperOperationPreparationError(
                "supervised operation preparation is one-shot"
            )
        self._used = True
        stack = ExitStack()
        try:
            self._match_selected_snapshot(
                self._selected_snapshot.permit,
                self._selected_snapshot.audit,
                self._authority,
            )
            cycle = stack.enter_context(
                self._supervised_cycle(
                    self._authority,
                    historical_cycle_configuration_payloads=self._configurations,
                )
            )
            acquisition = cycle.acquisition
            if acquisition.state is PaperAccountMutexState.ABANDONED_OWNER:
                raise PaperOperationPreparationReconciliationRequiredError(
                    "abandoned paper-account mutex ownership requires reconciliation"
                )
            if acquisition.state is not PaperAccountMutexState.OWNED:
                raise SupervisedPaperOperationPreparationError(
                    "paper-account mutex is not owned"
                )

            account = cycle.evidence
            material = _prepare_verified_paper_operation_from_account(
                account,
                self._selected_snapshot,
                history_seed=self._history_seed,
                strategy_config=self._strategy_config,
                caller_idempotency_key=self._user_key,
                open_reference=self._open_reference,
                policies=self._policies,
                planning_at=self._planning_at,
                submitted_at=self._submitted_at,
                filled_at=self._filled_at,
                metadata=self._metadata,
                build_plan=self._build_plan,
                verify_plan=self._verify_plan,
                calendar=self._calendar,
            )
            verified_plan = material.plan_binding
            execution_inputs = material.execution_inputs
            paper_account_id = account.anchor.paper_account_id
            application_id = execution_inputs.application_id
            audit = _PreparationAudit(
                paper_account_id,
                verified_plan.plan.plan_id,
                execution_inputs.intent.operation_id,
                application_id,
                self._selected_snapshot.audit.snapshot_id,
                verified_plan.artifact_sha256,
                verified_plan.artifact_byte_length,
                acquisition.state,
            )
            binding = _PreparedPaperOperationBinding(
                cycle.operation_root,
                execution_inputs,
            )
            with _ACTIVE_BINDINGS_LOCK:
                _ACTIVE_BINDINGS[self] = binding
            self._audit = audit
            self._exit_stack = stack
            return self
        except BaseException:
            with _ACTIVE_BINDINGS_LOCK:
                _ACTIVE_BINDINGS.pop(self, None)
            stack.close()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        stack, self._exit_stack = self._exit_stack, None
        if stack is None:
            raise SupervisedPaperOperationPreparationError(
                "supervised operation preparation is not active"
            )
        with _ACTIVE_BINDINGS_LOCK:
            _ACTIVE_BINDINGS.pop(self, None)
        return stack.__exit__(exc_type, exc, traceback)

    def _require_audit(self) -> _PreparationAudit:
        if self._exit_stack is None or self._audit is None:
            raise SupervisedPaperOperationPreparationError(
                "supervised operation preparation is not active"
            )
        return self._audit

    @property
    def paper_account_id(self) -> str:
        return self._require_audit().paper_account_id

    @property
    def plan_id(self) -> UUID:
        return self._require_audit().plan_id

    @property
    def operation_id(self) -> UUID:
        return self._require_audit().operation_id

    @property
    def application_id(self) -> UUID:
        return self._require_audit().application_id

    @property
    def selected_snapshot_id(self) -> UUID:
        return self._require_audit().selected_snapshot_id

    @property
    def plan_artifact_sha256(self) -> str:
        return self._require_audit().plan_artifact_sha256

    @property
    def plan_artifact_byte_length(self) -> int:
        return self._require_audit().plan_artifact_byte_length

    @property
    def mutex_acquisition_state(self) -> PaperAccountMutexState:
        return self._require_audit().mutex_acquisition_state


def supervised_personal_desktop_paper_operation_preparation(
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    *,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: UUID,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...] = (),
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
) -> _SupervisedPaperOperationPreparation:
    """Validate C1/P2 and create one source-owned supervised preparation."""

    production_authority = require_validated_production_authority(authority)
    if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
        raise SupervisedPaperOperationPreparationError(
            "selected snapshot must be an exact P2 read result"
        )
    require_selected_c3_snapshot_matches_authority(
        selected_snapshot.permit,
        selected_snapshot.audit,
        production_authority,
    )
    return _supervised_personal_desktop_paper_operation_preparation(
        production_authority,
        selected_snapshot,
        history_seed=history_seed,
        strategy_config=strategy_config,
        caller_idempotency_key=caller_idempotency_key,
        open_reference=open_reference,
        policies=policies,
        planning_at=planning_at,
        submitted_at=submitted_at,
        filled_at=filled_at,
        metadata=metadata,
        historical_cycle_configuration_payloads=(
            historical_cycle_configuration_payloads
        ),
        supervised_cycle=supervised_personal_desktop_paper_cycle,
        build_plan=build_manual_paper_strategy_plan,
        verify_plan=verify_manual_paper_strategy_plan,
        match_selected_snapshot=require_selected_c3_snapshot_matches_authority,
        calendar=BoundMarketCalendar(
            XNYS_CALENDAR_DESCRIPTOR,
            NYSEMarketCalendar(),
        ),
    )


def _supervised_personal_desktop_paper_operation_preparation(
    authority: ValidatedProductionAuthority,
    selected_snapshot: SelectedC3SnapshotReadResult,
    *,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: UUID,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...] = (),
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
    supervised_cycle: _SupervisedCycleFactory,
    build_plan: _BuildPlan,
    verify_plan: _VerifyPlan,
    match_selected_snapshot: _MatchSelectedSnapshot,
    calendar: IdentifiedMarketCalendar,
) -> _SupervisedPaperOperationPreparation:
    """Inject already-bounded pure/supervised seams for isolated tests only."""

    return _SupervisedPaperOperationPreparation(
        authority,
        selected_snapshot,
        history_seed=history_seed,
        strategy_config=strategy_config,
        caller_idempotency_key=caller_idempotency_key,
        open_reference=open_reference,
        policies=policies,
        planning_at=planning_at,
        submitted_at=submitted_at,
        filled_at=filled_at,
        metadata=metadata,
        historical_cycle_configuration_payloads=(
            historical_cycle_configuration_payloads
        ),
        supervised_cycle=supervised_cycle,
        build_plan=build_plan,
        verify_plan=verify_plan,
        match_selected_snapshot=match_selected_snapshot,
        calendar=calendar,
        _key=_CONTEXT_KEY,
    )


def _require_active_prepared_paper_operation_binding(
    preparation: _SupervisedPaperOperationPreparation,
) -> _PreparedPaperOperationBinding:
    """Return the internal PD2C seam only during this exact active context."""

    if type(preparation) is not _SupervisedPaperOperationPreparation:
        raise SupervisedPaperOperationPreparationError(
            "prepared operation context type is invalid"
        )
    with _ACTIVE_BINDINGS_LOCK:
        binding = _ACTIVE_BINDINGS.get(preparation)
    if binding is None or preparation._exit_stack is None:
        raise SupervisedPaperOperationPreparationError(
            "prepared operation binding is not active"
        )
    return binding


def _prepare_verified_paper_operation_from_account(
    account: object,
    selected: SelectedC3SnapshotReadResult,
    *,
    history_seed: VerifiedStrategyHistorySeed,
    strategy_config: MovingAverageCrossoverConfig,
    caller_idempotency_key: UUID,
    open_reference: CallerAssertedNextSessionOpenReference,
    policies: VerifiedSnapshotPaperCyclePolicies,
    planning_at: datetime,
    submitted_at: datetime,
    filled_at: datetime,
    metadata: tuple[MetadataEntry, ...],
    build_plan: _BuildPlan,
    verify_plan: _VerifyPlan,
    calendar: IdentifiedMarketCalendar,
) -> _PreparedPaperOperationMaterial:
    """Derive and replay exact plan/A67 inputs from authoritative account evidence."""

    if type(selected) is not SelectedC3SnapshotReadResult:
        raise SupervisedPaperOperationPreparationError(
            "selected snapshot must be an exact P2 read result"
        )
    if type(caller_idempotency_key) is not UUID:
        raise SupervisedPaperOperationPreparationError(
            "caller idempotency key must be an exact UUID"
        )
    paper_account_id = account.anchor.paper_account_id
    prior = account.prior_checkpoint
    terminal = _terminal_artifact(account, prior.checkpoint_id)
    assertion = ManualPaperSelectedC3Assertion(
        selected.audit.selection_id,
        selected.audit.session_id,
        selected.audit.terminal_id,
        selected.audit.snapshot_id,
        selected.audit.artifact_sha256,
        selected.audit.artifact_byte_length,
    )
    plan_request = ManualPaperStrategyPlanRequest(
        selected.verification,
        paper_account_id,
        assertion,
        prior,
        history_seed,
        strategy_config,
        str(caller_idempotency_key),
        open_reference,
        policies,
        planning_at,
        submitted_at,
        filled_at,
        metadata,
    )
    built_plan = build_plan(plan_request, calendar)
    verified_plan = verify_plan(
        built_plan.artifact_bytes,
        calendar,
        expected_sha256=built_plan.artifact_sha256,
        expected_byte_length=built_plan.artifact_byte_length,
        expected_checkpointed_request=built_plan.checkpointed_request,
    )
    if verified_plan != built_plan:
        raise SupervisedPaperOperationPreparationError(
            "strategy-plan replay differs from the produced binding"
        )
    _reconcile_plan(
        verified_plan,
        paper_account_id=paper_account_id,
        prior=prior,
        assertion=assertion,
        selected_snapshot=selected,
        caller_idempotency_key=caller_idempotency_key,
    )

    terminal_evidence = _artifact_evidence(terminal)
    snapshot_evidence = PaperAccountLineageArtifactEvidence(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        selected.audit.snapshot_id,
        selected.audit.artifact_sha256,
        selected.audit.artifact_byte_length,
    )
    configuration_evidence = PaperOperationArtifactEvidence(
        verified_plan.artifact_sha256,
        verified_plan.artifact_byte_length,
    )
    request = verified_plan.checkpointed_request
    intent = create_paper_operation_intent(
        caller_idempotency_key,
        account.lineage,
        terminal_evidence,
        snapshot_evidence,
        configuration_evidence,
        request,
    )
    application_id = derive_checkpointed_verified_snapshot_application_id(
        prior.checkpoint_id,
        request.request_id,
    )
    execution_inputs = VerifiedPaperOperationExecutionInputs(
        intent,
        application_id,
        account.genesis,
        account.successors,
        account.reports,
        account.snapshots,
        prior,
        terminal.payload,
        selected.snapshot_bytes,
        selected.verification,
        verified_plan.artifact_bytes,
        request,
        calendar,
    )
    return _PreparedPaperOperationMaterial(verified_plan, execution_inputs)


def _terminal_artifact(
    account: object, checkpoint_id: UUID
) -> PaperAccountLineageArtifact:
    try:
        lineage = account.lineage
        artifacts = (account.genesis, *account.successors)
    except AttributeError as error:
        raise SupervisedPaperOperationPreparationError(
            "post-lock account evidence is incomplete"
        ) from error
    matching = tuple(
        artifact for artifact in artifacts if artifact.artifact_id == checkpoint_id
    )
    if (
        len(matching) != 1
        or matching[0].artifact_id != lineage.terminal_checkpoint_id
        or _artifact_evidence(matching[0]) != lineage.checkpoint_artifacts[-1]
    ):
        raise SupervisedPaperOperationPreparationError(
            "post-lock terminal checkpoint evidence does not reconcile"
        )
    return matching[0]


def _artifact_evidence(
    artifact: PaperAccountLineageArtifact,
) -> PaperAccountLineageArtifactEvidence:
    if type(artifact) is not PaperAccountLineageArtifact:
        raise SupervisedPaperOperationPreparationError(
            "post-lock lineage artifact type is invalid"
        )
    return PaperAccountLineageArtifactEvidence(
        artifact.kind,
        artifact.artifact_id,
        artifact.sha256,
        artifact.byte_length,
    )


def _reconcile_plan(
    binding: ManualPaperStrategyPlanArtifactBinding,
    *,
    paper_account_id: str,
    prior: VerifiedPriorCheckpoint,
    assertion: ManualPaperSelectedC3Assertion,
    selected_snapshot: SelectedC3SnapshotReadResult,
    caller_idempotency_key: UUID,
) -> None:
    plan = binding.plan
    if (
        plan.paper_account_id != paper_account_id
        or plan.prior_checkpoint
        != ManualPaperPriorCheckpointEvidence.from_verified(prior)
        or plan.selected_c3_assertion != assertion
        or plan.selected_snapshot_artifact != selected_snapshot.snapshot_bytes
        or plan.caller_idempotency_key != str(caller_idempotency_key)
        or binding.checkpointed_request.snapshot_reference.snapshot_id
        != selected_snapshot.audit.snapshot_id
        or binding.checkpointed_request.snapshot_reference.artifact_sha256
        != selected_snapshot.audit.artifact_sha256
        or binding.checkpointed_request.snapshot_reference.artifact_byte_length
        != selected_snapshot.audit.artifact_byte_length
    ):
        raise SupervisedPaperOperationPreparationError(
            "verified strategy plan does not retain exact post-lock/P2 evidence"
        )
