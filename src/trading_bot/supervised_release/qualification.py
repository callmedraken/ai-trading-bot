"""133-AF source-only deployment evidence; no native or mutation capability."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import VerifiedRelease
from trading_bot.supervised_release.installation_contract import (
    InstalledEvidence,
    ObserverNative,
)
from trading_bot.supervised_release.maintenance import (
    TASK_PATH,
    Classification,
    MaintenanceTask,
    ModeObserver,
    SchedulerObservation,
    SchedulerObserver,
    classify_task,
    require_maintenance,
)
from trading_bot.supervised_release.model import DURABLE_DATA_ROOT, PRODUCTION_PYTHON
from trading_bot.supervised_release.observer import (
    observe_installed_release,
    replay_inputs,
)
from trading_bot.supervised_release.runtime_admission import (
    ProcessObservation,
    RuntimeAdmissionEvidence,
    RuntimeAdmissionResult,
    RuntimeObserver,
    RuntimeReason,
    RuntimeStatus,
    RuntimeSubstrateObservation,
    admit_runtime_host,
)


class QualificationClass(StrEnum):
    SELECTED_READY_DISABLED = "SELECTED_READY_DISABLED"
    SELECTED_RUNTIME_ADMITTED = "SELECTED_RUNTIME_ADMITTED"
    ROLLBACK_CANDIDATE_VERIFIED = "ROLLBACK_CANDIDATE_VERIFIED"
    BLOCKED_IDENTITY_DRIFT = "BLOCKED_IDENTITY_DRIFT"
    BLOCKED_SCHEDULER_STATE = "BLOCKED_SCHEDULER_STATE"
    BLOCKED_RUNTIME_STATE = "BLOCKED_RUNTIME_STATE"
    BLOCKED_ROLLBACK_STATE = "BLOCKED_ROLLBACK_STATE"


@dataclass(frozen=True, slots=True)
class SelectionObservation:
    """Complete read-only selection inventory, never a selection instruction."""

    selected_release_ids: tuple[str, ...]
    runtime_release_ids: tuple[str, ...]
    task_paths: tuple[str, ...]
    rollback_release_ids: tuple[str, ...] = ()
    rollback_bound_or_active: bool = False
    complete: bool = True


class SelectionObserver(Protocol):
    def observe_selection(self) -> SelectionObservation: ...


@dataclass(frozen=True, slots=True)
class RollbackCandidate:
    release: VerifiedRelease
    binding: RuntimeBinding
    installed: InstalledEvidence


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    selected: InstalledEvidence
    runtime: RuntimeAdmissionEvidence
    scheduler: SchedulerObservation
    rollback: InstalledEvidence | None
    durable_data_root: str = field(default=DURABLE_DATA_ROOT, init=False)


@dataclass(frozen=True, slots=True)
class QualificationResult:
    """All-or-nothing sanitized evidence, carrying no trading/effect authority."""

    classifications: tuple[QualificationClass, ...]
    evidence: QualificationEvidence | None = None


@dataclass(frozen=True, slots=True)
class _StableRuntime:
    observer: RuntimeObserver
    process: ProcessObservation
    substrate: RuntimeSubstrateObservation

    def observe_process(self) -> ProcessObservation:
        value = self.observer.observe_process()
        if type(value) is not ProcessObservation or value != self.process:
            raise ValueError("process observation drift")
        return value

    def observe_substrate(self) -> RuntimeSubstrateObservation:
        value = self.observer.observe_substrate()
        if type(value) is not RuntimeSubstrateObservation or value != self.substrate:
            raise ValueError("substrate observation drift")
        return value


def _identity(value: object) -> bool:
    return (
        type(value) is tuple
        and len(value) == 2
        and all(type(part) is int and part > 0 for part in value)
    )


def _identifiers(value: object) -> bool:
    return type(value) is tuple and all(type(part) is str for part in value)


def _image(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    installed: InstalledEvidence,
    observer: ObserverNative,
) -> InstalledEvidence:
    replay_inputs(release, binding)
    if type(installed) is not InstalledEvidence or observer is None:
        raise ValueError("exact installed evidence and independent observer required")
    if not all(
        type(value) is str
        for value in (
            installed.release_id,
            installed.manifest_sha256,
            installed.binding_sha256,
            installed.python_version,
            installed.python_sha256,
            installed.dependency_closure,
        )
    ):
        raise ValueError("exact installed identity fields required")
    for identity in (
        installed.parent_identity,
        installed.image_identity,
        installed.python_identity,
    ):
        if not _identity(identity):
            raise ValueError("exact native identity required")
    replay = observe_installed_release(release, binding, native=observer)
    if replay != installed:
        raise ValueError("installed identity drift")
    return replay


def qualify_deployment(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    installed: InstalledEvidence,
    runtime_admission: RuntimeAdmissionResult,
    *,
    image_observer: ObserverNative,
    scheduler_observer: SchedulerObserver,
    mode_observer: ModeObserver,
    runtime_observer: RuntimeObserver,
    selection_observer: SelectionObserver,
    rollback: RollbackCandidate | None = None,
    rollback_image_observer: ObserverNative | None = None,
) -> QualificationResult:
    """Replay AC/AD/AE and bracket all observations; never repair or activate.

    Every observer is mandatory and explicitly injected. A missing observer must
    never select an upstream native default. The optional rollback is one exact
    candidate, with its own independent image replay, and is never a task target.
    """
    blocked = QualificationClass.BLOCKED_IDENTITY_DRIFT
    try:
        first_image = _image(release, binding, installed, image_observer)
        selected_id = release.manifest.release_id

        blocked = QualificationClass.BLOCKED_ROLLBACK_STATE
        rollback_image = None
        if rollback is None:
            if rollback_image_observer is not None:
                raise ValueError("orphan rollback observer")
        else:
            if (
                type(rollback) is not RollbackCandidate
                or type(rollback.release) is not VerifiedRelease
                or rollback.release.manifest.release_id == selected_id
                or rollback_image_observer is None
            ):
                raise ValueError("one distinct rollback candidate required")
            rollback_image = _image(
                rollback.release,
                rollback.binding,
                rollback.installed,
                rollback_image_observer,
            )
            if (
                rollback_image.parent_identity != first_image.parent_identity
                or rollback_image.python_identity != first_image.python_identity
                or rollback_image.image_identity == first_image.image_identity
            ):
                raise ValueError("rollback host or image alias differs")
        expected_rollback = (
            () if rollback is None else (rollback.release.manifest.release_id,)
        )

        blocked = QualificationClass.BLOCKED_RUNTIME_STATE
        if mode_observer is None or runtime_observer is None:
            raise ValueError("independent runtime state required")
        first_mode = mode_observer.observe_mode()
        require_maintenance(first_mode)

        blocked = QualificationClass.BLOCKED_IDENTITY_DRIFT
        if selection_observer is None:
            raise ValueError("independent selection inventory required")
        first_selection = selection_observer.observe_selection()
        if (
            type(first_selection) is not SelectionObservation
            or first_selection.complete is not True
            or not _identifiers(first_selection.selected_release_ids)
            or first_selection.selected_release_ids != (selected_id,)
        ):
            raise ValueError("selected identity ambiguous")
        blocked = QualificationClass.BLOCKED_SCHEDULER_STATE
        if (
            not _identifiers(first_selection.task_paths)
            or first_selection.task_paths != (TASK_PATH,)
            or scheduler_observer is None
        ):
            raise ValueError("fixed task identity ambiguous")
        task = MaintenanceTask(release)
        first_task = scheduler_observer.observe_fixed_task()
        if classify_task(first_task, task) is not Classification.ALREADY_BOUND_DISABLED:
            raise ValueError("exact selected disabled task required")
        blocked = QualificationClass.BLOCKED_RUNTIME_STATE
        if not _identifiers(
            first_selection.runtime_release_ids
        ) or first_selection.runtime_release_ids != (selected_id,):
            raise ValueError("runtime identity ambiguous")
        blocked = QualificationClass.BLOCKED_ROLLBACK_STATE
        if (
            not _identifiers(first_selection.rollback_release_ids)
            or first_selection.rollback_release_ids != expected_rollback
            or first_selection.rollback_bound_or_active is not False
        ):
            raise ValueError("rollback ambiguous or activated")

        blocked = QualificationClass.BLOCKED_RUNTIME_STATE
        if (
            type(runtime_admission) is not RuntimeAdmissionResult
            or runtime_admission.status is not RuntimeStatus.VERIFIED
            or runtime_admission.reason is not RuntimeReason.VERIFIED
            or type(runtime_admission.evidence) is not RuntimeAdmissionEvidence
        ):
            raise ValueError("accepted AE evidence required")
        evidence = runtime_admission.evidence
        if (
            not _identity(evidence.image_identity)
            or not _identity(evidence.python_identity)
            or not all(
                type(value) is str
                for value in (
                    evidence.release_id,
                    evidence.manifest_sha256,
                    evidence.binding_sha256,
                    evidence.release_root,
                    evidence.source_root,
                    evidence.launcher,
                    evidence.site_packages,
                    evidence.dependency_closure,
                )
            )
        ):
            raise ValueError("exact AE identity fields required")
        first_process = runtime_observer.observe_process()
        first_substrate = runtime_observer.observe_substrate()
        stable_runtime = _StableRuntime(
            runtime_observer, first_process, first_substrate
        )
        admitted = admit_runtime_host(
            release,
            binding,
            first_image,
            image_observer=image_observer,
            runtime_observer=stable_runtime,
        )
        if (
            admitted.status is not RuntimeStatus.VERIFIED
            or admitted != runtime_admission
        ):
            raise ValueError("AE evidence does not independently replay")
        # AE proves substrate security; AF also joins its Python file identity to
        # the independently replayed AC host identity, rather than its path alone.
        python_rows = tuple(
            row for row in first_substrate.objects if row.path == PRODUCTION_PYTHON
        )
        if (
            len(python_rows) != 1
            or python_rows[0].identity != first_image.python_identity
        ):
            raise ValueError("runtime Python identity disagrees with installed image")

        blocked = QualificationClass.BLOCKED_ROLLBACK_STATE
        if (
            rollback is not None
            and _image(
                rollback.release,
                rollback.binding,
                rollback.installed,
                rollback_image_observer,
            )
            != rollback_image
        ):
            raise ValueError("rollback drift")
        blocked = QualificationClass.BLOCKED_IDENTITY_DRIFT
        if _image(release, binding, installed, image_observer) != first_image:
            raise ValueError("selected image drift")
        if selection_observer.observe_selection() != first_selection:
            raise ValueError("selection observation drift")
        blocked = QualificationClass.BLOCKED_SCHEDULER_STATE
        final_task = scheduler_observer.observe_fixed_task()
        if (
            final_task != first_task
            or classify_task(final_task, task)
            is not Classification.ALREADY_BOUND_DISABLED
        ):
            raise ValueError("scheduler observation drift")
        blocked = QualificationClass.BLOCKED_RUNTIME_STATE
        final_mode = mode_observer.observe_mode()
        require_maintenance(final_mode)
        if (
            final_mode != first_mode
            or stable_runtime.observe_process() != first_process
            or stable_runtime.observe_substrate() != first_substrate
        ):
            raise ValueError("runtime observation drift")

        classes = (
            QualificationClass.SELECTED_READY_DISABLED,
            QualificationClass.SELECTED_RUNTIME_ADMITTED,
        )
        if rollback is not None:
            classes += (QualificationClass.ROLLBACK_CANDIDATE_VERIFIED,)
        return QualificationResult(
            classes,
            QualificationEvidence(
                first_image, admitted.evidence, first_task, rollback_image
            ),
        )
    except Exception:
        # No diagnostic, capability, partial PASS, or follow-up action escapes.
        return QualificationResult((blocked,))
