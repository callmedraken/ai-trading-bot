"""Execute one supervised Paper-v2 operation behind the PD2C effect gate.

The production-facing boundary validates genuine C1/P2 provenance by creating
the existing PD2B3 preparation before it checks the dedicated source gate.  A
disabled production call therefore never enters PD2B3 or reaches native or
filesystem effects.  The private disposable seam exists only so focused tests
can exercise the future enabled composition with a fake PD2B3 scope and
executor while the production gate remains false.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.cli.paper_operation_execution import (
    PaperOperationExecutionClassification,
    PaperOperationExecutionResult,
    execute_paper_operation_once,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
)
from trading_bot.runtime.paper_operation_execution_inputs import (
    VerifiedPaperOperationExecutionInputs,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_supervised_paper_operation_preparation import (  # noqa: E501
    _require_active_prepared_paper_operation_binding,
    _SupervisedPaperOperationPreparation,
    supervised_personal_desktop_paper_operation_preparation,
)
from trading_bot.runtime.strategy_history_seed import VerifiedStrategyHistorySeed
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = True

_PERSONAL_DESKTOP_PAPER_V2_OPERATION_ROOT = r"F:\AITradingBot\Paper-v2\runtime"
_PRODUCTION_EXECUTION_ISSUER = object()
_DISPOSABLE_EXECUTION_AUTHORITY_ISSUER = object()


class SupervisedPaperOperationExecutionError(PersonalDesktopPaperAccountError):
    """A supervised Architecture-67 execution failed closed."""


class SupervisedPaperOperationEffectsDisabledError(
    SupervisedPaperOperationExecutionError
):
    """The dedicated PD2C production-effect gate is disabled."""


class SupervisedPaperOperationRootMismatchError(SupervisedPaperOperationExecutionError):
    """The prepared operation root differs from the fixed production root."""


class SupervisedPaperOperationResultReconciliationError(
    SupervisedPaperOperationExecutionError
):
    """The Architecture-67 result does not match the active preparation."""


class _PaperOperationExecutor(Protocol):
    def __call__(
        self,
        operation_root: Path,
        inputs: VerifiedPaperOperationExecutionInputs,
    ) -> PaperOperationExecutionResult: ...


@dataclass(frozen=True, slots=True)
class SupervisedPaperOperationExecutionResult:
    """Immutable non-authorizing audit facts from one Architecture-67 call."""

    operation_id: UUID
    application_id: UUID
    execution_classification: PaperOperationExecutionClassification
    diagnostic_code: str
    cycle_result_id: UUID | None
    successor_checkpoint_id: UUID | None
    transition_evidence_produced: bool
    receipt_evidence_produced: bool
    executor_called: bool

    def __post_init__(self) -> None:
        if (
            type(self.operation_id) is not UUID
            or type(self.application_id) is not UUID
            or type(self.execution_classification)
            is not PaperOperationExecutionClassification
            or type(self.diagnostic_code) is not str
            or not self.diagnostic_code
            or (
                self.cycle_result_id is not None
                and type(self.cycle_result_id) is not UUID
            )
            or (
                self.successor_checkpoint_id is not None
                and type(self.successor_checkpoint_id) is not UUID
            )
            or type(self.transition_evidence_produced) is not bool
            or type(self.receipt_evidence_produced) is not bool
            or self.executor_called is not True
        ):
            raise ValueError("supervised paper-operation execution result is invalid")


class _DisposableSupervisedPaperExecutionAuthorityForTest:
    """Private one-shot authority for the injected disposable execution seam."""

    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _DISPOSABLE_EXECUTION_AUTHORITY_ISSUER:
            raise TypeError(
                "disposable supervised execution authority requires its test issuer"
            )
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        with self._lock:
            if self._issuer is not _DISPOSABLE_EXECUTION_AUTHORITY_ISSUER or self._used:
                raise TypeError(
                    "disposable supervised execution authority is invalid or consumed"
                )
            self._used = True

    def __copy__(self) -> object:
        raise TypeError("disposable supervised execution authorities cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(
            "disposable supervised execution authorities cannot be deep-copied"
        )

    def __reduce__(self) -> object:
        raise TypeError(
            "disposable supervised execution authorities cannot be serialized"
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("disposable supervised execution authorities cannot be pickled")


def execute_supervised_personal_desktop_paper_operation(
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
) -> SupervisedPaperOperationExecutionResult:
    """Validate C1/P2 and execute only when the source-owned PD2C gate allows."""

    preparation = supervised_personal_desktop_paper_operation_preparation(
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
    )
    if PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is not True:
        raise SupervisedPaperOperationEffectsDisabledError(
            "supervised Paper-v2 execution effects are disabled"
        )
    return _execute_prepared_supervised_paper_operation(
        preparation,
        executor=execute_paper_operation_once,
        _issuer=_PRODUCTION_EXECUTION_ISSUER,
    )


def _open_disposable_supervised_paper_execution_authority_for_test() -> (
    _DisposableSupervisedPaperExecutionAuthorityForTest
):
    """Issue one explicit private authority for a disposable focused test."""

    return _DisposableSupervisedPaperExecutionAuthorityForTest(
        _issuer=_DISPOSABLE_EXECUTION_AUTHORITY_ISSUER
    )


def _execute_prepared_supervised_paper_operation_for_test(
    preparation: _SupervisedPaperOperationPreparation,
    *,
    executor: _PaperOperationExecutor,
    authority: _DisposableSupervisedPaperExecutionAuthorityForTest,
) -> SupervisedPaperOperationExecutionResult:
    """Exercise the future enabled branch with explicit disposable authority."""

    if type(authority) is not _DisposableSupervisedPaperExecutionAuthorityForTest:
        raise TypeError("disposable supervised execution authority is invalid")
    authority._consume()
    return _execute_prepared_supervised_paper_operation(
        preparation,
        executor=executor,
        _issuer=_DISPOSABLE_EXECUTION_AUTHORITY_ISSUER,
    )


def _execute_prepared_supervised_paper_operation(
    preparation: _SupervisedPaperOperationPreparation,
    *,
    executor: _PaperOperationExecutor,
    _issuer: object,
) -> SupervisedPaperOperationExecutionResult:
    if (
        _issuer is not _PRODUCTION_EXECUTION_ISSUER
        and _issuer is not _DISPOSABLE_EXECUTION_AUTHORITY_ISSUER
    ):
        raise TypeError("supervised execution issuer is invalid")
    if type(preparation) is not _SupervisedPaperOperationPreparation:
        raise TypeError("supervised operation preparation type is invalid")
    if not callable(executor):
        raise TypeError("paper-operation executor is invalid")

    with preparation as active:
        if active is not preparation:
            raise SupervisedPaperOperationExecutionError(
                "supervised operation preparation context identity changed"
            )
        binding = _require_active_prepared_paper_operation_binding(active)
        if (
            type(binding.operation_root) is not str
            or binding.operation_root != _PERSONAL_DESKTOP_PAPER_V2_OPERATION_ROOT
        ):
            raise SupervisedPaperOperationRootMismatchError(
                "prepared operation root does not match the fixed Paper-v2 runtime"
            )
        expected_operation_id = active.operation_id
        expected_application_id = active.application_id
        inputs = binding.execution_inputs
        if (
            inputs.intent.operation_id != expected_operation_id
            or inputs.application_id != expected_application_id
        ):
            raise SupervisedPaperOperationResultReconciliationError(
                "prepared execution identities do not match the active preparation"
            )
        result = executor(Path(binding.operation_root), inputs)
        if type(result) is not PaperOperationExecutionResult:
            raise SupervisedPaperOperationResultReconciliationError(
                "Architecture-67 executor returned an invalid result type"
            )
        if (
            result.operation_id != expected_operation_id
            or result.application_id != expected_application_id
        ):
            raise SupervisedPaperOperationResultReconciliationError(
                "Architecture-67 result identities do not match the active preparation"
            )
        return SupervisedPaperOperationExecutionResult(
            operation_id=result.operation_id,
            application_id=result.application_id,
            execution_classification=result.classification,
            diagnostic_code=result.diagnostic_code,
            cycle_result_id=result.cycle_result_id,
            successor_checkpoint_id=result.successor_checkpoint_id,
            transition_evidence_produced=result.transition_path is not None,
            receipt_evidence_produced=result.receipt_path is not None,
            executor_called=True,
        )
