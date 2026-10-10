"""133-AD read-only maintenance planning and inert one-attempt accounting.

There is no native scheduler backend, credential surface or execute entrypoint.
The read seams must independently observe host facts; supplied cached evidence
alone never establishes maintenance or installed-release authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from xml.etree import ElementTree as ET

from trading_bot.arch133_acl.read_only import TRADING_SID
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import VerifiedRelease
from trading_bot.supervised_release.installation_contract import (
    InstalledEvidence,
    ObserverNative,
)
from trading_bot.supervised_release.model import project_scheduler_action
from trading_bot.supervised_release.observer import (
    observe_installed_release,
    replay_inputs,
)

TASK_PATH = r"\AITradingBot-Arch133-SingleSessionReviewPaper-v1"
NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
PREDECESSOR_ROOT = r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g"

# Complete reviewed 133-P definition shape. Its historical TIME window is
# observation evidence only, never copied into the maintenance target. Every
# element/attribute, including the trigger's enabled flag, must match exactly.
TASK_TEMPLATE = r"""<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<RegistrationInfo><URI>\AITradingBot-Arch133-SingleSessionReviewPaper-v1</URI></RegistrationInfo>
<Triggers>{triggers}</Triggers>
<Principals><Principal id="Trading">
<UserId>S-1-5-21-1397534616-3988210162-180023805-1009</UserId>
<LogonType>Password</LogonType><RunLevel>LeastPrivilege</RunLevel>
</Principal></Principals>
<Settings>
<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
<AllowHardTerminate>true</AllowHardTerminate>
<StartWhenAvailable>false</StartWhenAvailable>
<RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
<IdleSettings><StopOnIdleEnd>true</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
<AllowStartOnDemand>false</AllowStartOnDemand><Enabled>false</Enabled>
<Hidden>false</Hidden><RunOnlyIfIdle>false</RunOnlyIfIdle><WakeToRun>false</WakeToRun>
<ExecutionTimeLimit>PT1H</ExecutionTimeLimit><Priority>7</Priority>
</Settings>
<Actions Context="Trading"><Exec><Command>F:\AITradingBot\runtime\python.exe</Command>
<Arguments>-I -B {root}\scripts\run_arch133_unattended_review_paper.py</Arguments>
<WorkingDirectory>{root}</WorkingDirectory></Exec></Actions></Task>"""


class OperatingMode(StrEnum):
    UNATTENDED_RUNTIME = "UNATTENDED_RUNTIME"
    SUPERVISED_MAINTENANCE = "SUPERVISED_MAINTENANCE"


@dataclass(frozen=True, slots=True)
class ModeEvidence:
    mode: OperatingMode
    active_bot_process: bool
    active_bot_cycle: bool
    runtime_authority: bool
    trading_authority: bool
    provider_authority: bool


class ModeObserver(Protocol):
    def observe_mode(self) -> ModeEvidence: ...


@dataclass(frozen=True, slots=True)
class SchedulerObservation:
    """One independent fixed-task read; absence carries no definition/state."""

    task_path: str = TASK_PATH
    xml: str | None = None
    enabled: bool = False
    running: bool = False
    active_instances: int = 0


class SchedulerObserver(Protocol):
    def observe_fixed_task(self) -> SchedulerObservation: ...


@dataclass(frozen=True, slots=True)
class MaintenanceTask:
    release: VerifiedRelease
    task_path: str = field(default=TASK_PATH, init=False)
    principal_sid: str = field(default=TRADING_SID, init=False)
    run_level: str = field(default="LeastPrivilege", init=False)
    enabled: bool = field(default=False, init=False)
    allow_demand_start: bool = field(default=False, init=False)
    semantic_arguments: tuple[str, ...] = field(default=(), init=False)
    scheduler_owned_environment: tuple[str, ...] = field(default=(), init=False)
    triggers: tuple[str, ...] = field(default=(), init=False)

    @property
    def executable(self) -> str:
        return project_scheduler_action(self.release.manifest).executable

    @property
    def arguments(self) -> tuple[str, ...]:
        return project_scheduler_action(self.release.manifest).arguments

    @property
    def working_directory(self) -> str:
        return project_scheduler_action(self.release.manifest).working_directory

    @property
    def xml(self) -> str:
        return TASK_TEMPLATE.format(root=self.working_directory, triggers="")


class Classification(StrEnum):
    ABSENT = "ABSENT"
    ALREADY_BOUND_DISABLED = "ALREADY_BOUND_DISABLED"
    EXACT_REVIEWED_133P_PREDECESSOR_DISABLED = (
        "EXACT_REVIEWED_133P_PREDECESSOR_DISABLED"
    )
    UNEXPECTED_EXISTING = "UNEXPECTED_EXISTING"
    RUNNING_OR_ENABLED = "RUNNING_OR_ENABLED"


class Status(StrEnum):
    PLANNED = "PLANNED"
    BLOCKED = "BLOCKED"
    ATTEMPT_STARTED = "ATTEMPT_STARTED"
    VERIFIED = "VERIFIED"
    INDETERMINATE = "INDETERMINATE"


class Disposition(StrEnum):
    NO_SCHEDULER_EFFECT = "NO_SCHEDULER_EFFECT"
    READ_ONLY_SUCCESS = "READ_ONLY_SUCCESS"
    ONE_CREATE = "ONE_CREATE"
    ONE_REBIND = "ONE_REBIND"
    PRESERVE_SCHEDULER_EVIDENCE_NO_RETRY = "PRESERVE_SCHEDULER_EVIDENCE_NO_RETRY"


class Reason(StrEnum):
    VERIFIED = "VERIFIED"
    MODE = "MODE"
    INPUT_OR_IMAGE = "INPUT_OR_IMAGE"
    SCHEDULER = "SCHEDULER"
    DRIFT = "DRIFT"


@dataclass(frozen=True, slots=True)
class MaintenancePlan:
    status: Status
    reason: Reason
    classification: Classification | None = None
    task: MaintenanceTask | None = None
    installed: InstalledEvidence | None = None
    observation: SchedulerObservation | None = None


def require_maintenance(evidence: ModeEvidence) -> None:
    if (
        type(evidence) is not ModeEvidence
        or evidence.mode is not OperatingMode.SUPERVISED_MAINTENANCE
        or any(
            value is not False
            for value in (
                evidence.active_bot_process,
                evidence.active_bot_cycle,
                evidence.runtime_authority,
                evidence.trading_authority,
                evidence.provider_authority,
            )
        )
    ):
        raise ValueError("supervised quiescent maintenance required")


def _tree(xml: str) -> ET.Element:
    if (
        type(xml) is not str
        or len(xml) > 65536
        or len(xml.encode("utf-8")) > 65536
        or "<!" in xml
        or "<?" in xml
    ):
        raise ValueError("bounded plain scheduler XML required")
    return ET.fromstring(xml)


def _material(node: ET.Element) -> tuple:
    if any((child.tail or "").strip() for child in node):
        raise ValueError("mixed scheduler XML forbidden")
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        (node.text or "").strip(),
        tuple(_material(child) for child in node),
    )


def _predecessor(tree: ET.Element) -> bool:
    # Accept only the full reviewed historical 133-P TIME-template family.
    # The historical window is deliberately not a current activation authority.
    ns = "{" + NAMESPACE + "}"
    triggers = tree.find(ns + "Triggers")
    if triggers is None or len(triggers) != 1:
        return False
    trigger = triggers[0]
    start, end = (
        trigger.findtext(ns + name) for name in ("StartBoundary", "EndBoundary")
    )
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z"
    if any(
        type(value) is not str or re.fullmatch(pattern, value) is None
        for value in (start, end)
    ):
        return False
    if not datetime.fromisoformat(start).astimezone(UTC) < datetime.fromisoformat(
        end
    ).astimezone(UTC):
        return False
    expected = TASK_TEMPLATE.format(
        root=PREDECESSOR_ROOT,
        triggers=f"<TimeTrigger><StartBoundary>{start}</StartBoundary><EndBoundary>{end}</EndBoundary><Enabled>true</Enabled></TimeTrigger>",
    )
    return _material(tree) == _material(_tree(expected))


def classify_task(
    observation: SchedulerObservation, task: MaintenanceTask
) -> Classification:
    if (
        type(observation) is not SchedulerObservation
        or observation.task_path != TASK_PATH
        or type(observation.enabled) is not bool
        or type(observation.running) is not bool
        or type(observation.active_instances) is not int
        or observation.active_instances < 0
    ):
        return Classification.UNEXPECTED_EXISTING
    if observation.enabled or observation.running or observation.active_instances:
        return Classification.RUNNING_OR_ENABLED
    if observation.xml is None:
        return Classification.ABSENT
    try:
        tree = _tree(observation.xml)
        if (
            tree.findtext("{" + NAMESPACE + "}Settings/{" + NAMESPACE + "}Enabled")
            == "true"
        ):
            return Classification.RUNNING_OR_ENABLED
        if _material(tree) == _material(_tree(task.xml)):
            return Classification.ALREADY_BOUND_DISABLED
        if _predecessor(tree):
            return Classification.EXACT_REVIEWED_133P_PREDECESSOR_DISABLED
    except (ValueError, ET.ParseError, OverflowError):
        pass
    return Classification.UNEXPECTED_EXISTING


def plan_maintenance_rebind(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    installed: InstalledEvidence,
    *,
    image_observer: ObserverNative,
    scheduler_observer: SchedulerObserver,
    mode_observer: ModeObserver,
) -> MaintenancePlan:
    """Reconstruct image and binding twice; no credentials or writes exist here."""
    reason = Reason.MODE
    classification = None
    try:
        initial_mode = mode_observer.observe_mode()
        require_maintenance(initial_mode)
        reason = Reason.INPUT_OR_IMAGE
        replay_inputs(release, binding)
        if type(installed) is not InstalledEvidence or image_observer is None:
            raise ValueError
        first_image = observe_installed_release(release, binding, native=image_observer)
        if first_image != installed:
            raise ValueError
        task = MaintenanceTask(release)
        reason = Reason.SCHEDULER
        first = scheduler_observer.observe_fixed_task()
        classification = classify_task(first, task)
        if classification in {
            Classification.UNEXPECTED_EXISTING,
            Classification.RUNNING_OR_ENABLED,
        }:
            return MaintenancePlan(Status.BLOCKED, reason, classification)
        reason = Reason.DRIFT
        require_maintenance(mode_observer.observe_mode())
        second = scheduler_observer.observe_fixed_task()
        second_class = classify_task(second, task)
        if first != second or classification != second_class:
            return MaintenancePlan(Status.BLOCKED, reason, second_class)
        if (
            observe_installed_release(release, binding, native=image_observer)
            != first_image
        ):
            raise ValueError
        final_mode = mode_observer.observe_mode()
        require_maintenance(final_mode)
        if final_mode != initial_mode:
            raise ValueError
        return MaintenancePlan(
            Status.PLANNED, Reason.VERIFIED, classification, task, installed, first
        )
    except Exception:
        # Native/private diagnostics never escape the closed source result.
        return MaintenancePlan(Status.BLOCKED, reason, classification)


@dataclass(frozen=True, slots=True)
class MutationResult:
    status: Status
    disposition: Disposition
    attempts: int


class MutationAccounting:
    """Inert future-boundary model, never a mutation or authorization capability.

    The local attempt latch is consumed before returning any write intent.
    Once begun, failure/ambiguous acknowledgement consumes the one attempt.
    Real authorization, custody and native transport are deferred checkpoints.
    """

    def __init__(self) -> None:
        self._begun = False
        self._result = MutationResult(
            Status.PLANNED, Disposition.NO_SCHEDULER_EFFECT, 0
        )

    @property
    def result(self) -> MutationResult:
        return self._result

    def begin(self, plan: MaintenancePlan) -> MutationResult:
        if self._begun or type(plan) is not MaintenancePlan:
            raise ValueError("attempt already consumed or invalid plan")
        self._begun = True
        if plan.status is not Status.PLANNED or plan.reason is not Reason.VERIFIED:
            self._result = MutationResult(
                Status.BLOCKED, Disposition.NO_SCHEDULER_EFFECT, 0
            )
        elif plan.classification is Classification.ALREADY_BOUND_DISABLED:
            self._result = MutationResult(
                Status.VERIFIED, Disposition.READ_ONLY_SUCCESS, 0
            )
        else:
            intent = {
                Classification.ABSENT: Disposition.ONE_CREATE,
                Classification.EXACT_REVIEWED_133P_PREDECESSOR_DISABLED: (
                    Disposition.ONE_REBIND
                ),
            }.get(plan.classification)
            self._result = (
                MutationResult(Status.BLOCKED, Disposition.NO_SCHEDULER_EFFECT, 0)
                if intent is None
                else MutationResult(Status.ATTEMPT_STARTED, intent, 1)
            )
        return self._result

    def finish(self, *, independently_verified: bool) -> MutationResult:
        if (
            self._result.status is not Status.ATTEMPT_STARTED
            or self._result.attempts != 1
        ):
            raise ValueError("no pending attempt")
        self._result = (
            MutationResult(Status.VERIFIED, self._result.disposition, 1)
            if independently_verified is True
            else MutationResult(
                Status.INDETERMINATE,
                Disposition.PRESERVE_SCHEDULER_EVIDENCE_NO_RETRY,
                1,
            )
        )
        return self._result
