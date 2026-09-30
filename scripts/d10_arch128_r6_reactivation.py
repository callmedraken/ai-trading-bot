"""Architecture-128 R6 pure reactivation operator contract.

R6 is source-only. This module owns no Windows transport, credential prompt,
Task Scheduler mutation, activation-lease writer, process launch, provider,
Paper-v2, broker, or live-trading capability. R7 may later bind reviewed host
adapters to this ordering contract after separate explicit authorization.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Protocol

from scripts import d10_arch128_r4_replacement as r4
from scripts import run_personal_desktop_d10_launch_guard as guard
from scripts.d10_protected_deployment import (
    ADMINISTRATORS_SID,
    FILE_ALL_ACCESS,
)
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as scheduler_contract,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10ActivationLease,
    build_activation_lease_model,
    format_utc_instant,
)
from trading_bot.runtime.personal_desktop_d10_wake_evidence_log import (
    D10_WAKE_EVIDENCE_ROOT,
)

SCHEMA = "architecture-128-r6-reactivation/v1"
LEASE_PUBLICATION_STEPS = (
    "TMP_CREATED_AND_VERIFIED",
    "TMP_TO_INSTALLING_VERIFIED",
    "INSTALLING_TO_FINAL_VERIFIED",
)


class ReactivationBlocked(RuntimeError):
    """R6 source-owned activation facts or ordering differ from Architecture 128."""


class MutationDisposition(StrEnum):
    NOT_RUN = "NOT_RUN"
    NOT_CALLED = "NOT_CALLED"
    CALL_RETURNED = "CALL_RETURNED"
    INDETERMINATE = "INDETERMINATE"
    PUBLISHED_VERIFIED = "PUBLISHED_VERIFIED"


@dataclass(frozen=True, slots=True)
class ReactivationPlan:
    lease: D10ActivationLease
    scheduler: scheduler_contract.OneWeekSoakSchedulerDeploymentSpec
    evidence_path: str


@dataclass(frozen=True, slots=True)
class EvidenceObservation:
    path: str
    size: int
    owner_sid: str
    protected_dacl: bool
    administrators_access_mask: int
    system_access_mask: int
    trading_access_mask: int
    local_ntfs: bool
    non_reparse: bool
    hard_link_count: int


@dataclass(frozen=True, slots=True)
class TradingOpenObservation:
    trading_sid: str
    desired_access: int
    share_mode: int
    creation_disposition: int
    flags: int
    opened: bool
    bytes_written: int


@dataclass(frozen=True, slots=True)
class AdmissionObservation:
    deployment_id: str
    attestation_sha256: str
    certified_source_head: str
    certified_source_tree: str
    lease_final_installing_tmp_present: tuple[bool, bool, bool]
    evidence_paths: tuple[str, ...]
    scheduler_disabled_nonrunning_exact: bool
    scheduler: scheduler_contract.OneWeekSoakSchedulerDeploymentSpec | None


@dataclass(frozen=True, slots=True)
class LeasePublicationObservation:
    disposition: MutationDisposition
    steps: tuple[str, ...]


class Boundaries(Protocol):
    def observe_admission(
        self, stage: str, plan: ReactivationPlan | None
    ) -> AdmissionObservation: ...

    def create_empty_evidence(self, path: str) -> None: ...

    def observe_evidence(self, path: str) -> EvidenceObservation: ...

    def probe_trading_append_open(
        self, path: str, credential: object
    ) -> TradingOpenObservation: ...

    def acquire_scheduler_credential(self) -> object: ...

    def update_scheduler(
        self, plan: ReactivationPlan, credential: object
    ) -> MutationDisposition: ...

    def read_scheduler(
        self,
    ) -> scheduler_contract.OneWeekSoakSchedulerDeploymentSpec: ...

    def publish_lease(
        self, lease: D10ActivationLease
    ) -> LeasePublicationObservation: ...


def _old_utc(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)


def derive_reactivation_plan(activation_utc: datetime) -> ReactivationPlan:
    if (
        type(activation_utc) is not datetime
        or activation_utc.tzinfo is not UTC
        or activation_utc.microsecond != 0
    ):
        raise ReactivationBlocked("activation_must_be_exact_utc_second")

    identity = r4.NEW_IDENTITY
    lease = build_activation_lease_model(
        deployment_id=identity.deployment_id,
        attestation_sha256=identity.unsigned_attestation_sha256,
        accepted_activation_utc=activation_utc,
        certified_source_head=identity.certified_source_head,
        certified_source_tree=identity.certified_source_tree,
    )
    scheduler = scheduler_contract.build_one_week_soak_scheduler_deployment_spec(
        activation_utc
    )

    if (
        lease.accepted_activation_utc == _old_utc(r4.OLD_ACTIVATION_UTC)
        or lease.end_utc == _old_utc(r4.OLD_END_UTC)
        or lease.soak_id == r4.OLD_SOAK_ID
    ):
        raise ReactivationBlocked("halted_soak_identity_reuse")

    if (
        scheduler.window.activation_utc != lease.accepted_activation_utc
        or scheduler.window.end_utc != lease.end_utc
    ):
        raise ReactivationBlocked("scheduler_lease_window_drift")

    evidence_path = str(
        PureWindowsPath(D10_WAKE_EVIDENCE_ROOT) / f"wake-{lease.soak_id}.jsonl"
    )
    expected_prefix = str(PureWindowsPath(D10_WAKE_EVIDENCE_ROOT)) + "\\wake-"
    if (
        not evidence_path.startswith(expected_prefix)
        or not evidence_path.endswith(".jsonl")
        or lease.soak_id not in evidence_path
    ):
        raise ReactivationBlocked("lease_derived_evidence_path_drift")

    return ReactivationPlan(lease, scheduler, evidence_path)


def _require_evidence(
    plan: ReactivationPlan,
    observed: EvidenceObservation,
) -> None:
    if (
        type(observed) is not EvidenceObservation
        or observed.path != plan.evidence_path
        or observed.size != 0
        or observed.owner_sid != ADMINISTRATORS_SID
        or observed.protected_dacl is not True
        or observed.administrators_access_mask != FILE_ALL_ACCESS
        or observed.system_access_mask != FILE_ALL_ACCESS
        or observed.trading_access_mask != guard.TRADING_EVIDENCE_FILE_ACCESS
        or observed.local_ntfs is not True
        or observed.non_reparse is not True
        or observed.hard_link_count != 1
    ):
        raise ReactivationBlocked("evidence_policy_or_identity_drift")


def _require_trading_probe(observed: TradingOpenObservation) -> None:
    if (
        type(observed) is not TradingOpenObservation
        or observed.trading_sid != guard.TRADING_SID
        or observed.desired_access != guard.TRADING_EVIDENCE_FILE_ACCESS
        or observed.share_mode != 1
        or observed.creation_disposition != 3
        or observed.flags
        != guard.FILE_FLAG_OPEN_REPARSE_POINT | guard.FILE_FLAG_WRITE_THROUGH
        or observed.opened is not True
        or observed.bytes_written != 0
    ):
        raise ReactivationBlocked("trading_append_only_probe_drift")


def _require_admission(
    observed: AdmissionObservation,
    *,
    plan: ReactivationPlan | None,
    scheduler_planned: bool,
    final_lease: bool,
) -> None:
    identity = r4.NEW_IDENTITY
    expected_paths = () if plan is None else (plan.evidence_path,)
    expected_leases = (final_lease, False, False)
    expected_scheduler = (
        plan.scheduler if scheduler_planned and plan is not None else None
    )
    expected_disabled = not scheduler_planned

    if (
        type(observed) is not AdmissionObservation
        or observed.deployment_id != identity.deployment_id
        or observed.attestation_sha256 != identity.unsigned_attestation_sha256
        or observed.certified_source_head != identity.certified_source_head
        or observed.certified_source_tree != identity.certified_source_tree
        or observed.lease_final_installing_tmp_present != expected_leases
        or observed.evidence_paths != expected_paths
        or observed.scheduler_disabled_nonrunning_exact is not expected_disabled
        or observed.scheduler != expected_scheduler
    ):
        raise ReactivationBlocked("reactivation_admission_drift")


def _planned_evidence(plan: ReactivationPlan) -> dict[str, object]:
    return {
        "activation_utc": format_utc_instant(plan.lease.accepted_activation_utc),
        "end_utc": format_utc_instant(plan.lease.end_utc),
        "soak_id": plan.lease.soak_id,
        "evidence_path": plan.evidence_path,
        "deployment_id": plan.lease.deployment_id,
        "attestation_sha256": plan.lease.attestation_sha256,
    }


class ReactivationOperator:
    """Single-use pure ordering composition over injected R7 host boundaries."""

    def __init__(
        self,
        boundaries: Boundaries,
        clock: Callable[[], datetime],
    ) -> None:
        self._boundaries = boundaries
        self._clock = clock
        self._used = False

    @staticmethod
    def _base() -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "stage": "ADMISSION",
            "planned": None,
            "evidence_provision": MutationDisposition.NOT_RUN,
            "scheduler_mutation": MutationDisposition.NOT_RUN,
            "lease_publication": MutationDisposition.NOT_RUN,
            "reconciliation_required": False,
            "automatic_retry": False,
            "automatic_rollback": False,
            "automatic_cleanup": False,
            "manual_task_start": "NOT_RUN",
            "source_launch": "NOT_RUN",
            "provider": "NOT_RUN",
            "Paper-v2": "NOT_RUN",
            "broker": "NOT_RUN",
            "live": "NOT_RUN",
        }

    def run(self, *, execute_r7: bool = False) -> dict[str, object]:
        result = self._base()
        if execute_r7 is not True or self._used:
            result["stage"] = "EXECUTION_INTERLOCK"
            return result
        self._used = True

        mutation_possible = False
        credential: object | None = None
        try:
            initial = self._boundaries.observe_admission("INITIAL", None)
            _require_admission(
                initial,
                plan=None,
                scheduler_planned=False,
                final_lease=False,
            )

            plan = derive_reactivation_plan(self._clock())
            result["planned"] = _planned_evidence(plan)

            result["stage"] = "EVIDENCE_CREATE"
            mutation_possible = True
            result["evidence_provision"] = MutationDisposition.INDETERMINATE
            self._boundaries.create_empty_evidence(plan.evidence_path)

            result["stage"] = "EVIDENCE_VERIFY"
            _require_evidence(
                plan, self._boundaries.observe_evidence(plan.evidence_path)
            )

            result["stage"] = "INTERACTIVE_CREDENTIAL"
            credential = self._boundaries.acquire_scheduler_credential()
            if credential is None:
                raise ReactivationBlocked("scheduler_credential_unavailable")

            result["stage"] = "FRESH_ADMISSION_AFTER_CREDENTIAL"
            fresh = self._boundaries.observe_admission("AFTER_CREDENTIAL", plan)
            _require_admission(
                fresh,
                plan=plan,
                scheduler_planned=False,
                final_lease=False,
            )
            _require_evidence(
                plan, self._boundaries.observe_evidence(plan.evidence_path)
            )

            result["stage"] = "TRADING_APPEND_OPEN_PROBE"
            _require_trading_probe(
                self._boundaries.probe_trading_append_open(
                    plan.evidence_path, credential
                )
            )
            result["evidence_provision"] = MutationDisposition.CALL_RETURNED

            result["stage"] = "SCHEDULER_MUTATION"
            result["scheduler_mutation"] = MutationDisposition.INDETERMINATE
            scheduler_disposition = self._boundaries.update_scheduler(plan, credential)
            if scheduler_disposition is not MutationDisposition.CALL_RETURNED:
                result["scheduler_mutation"] = scheduler_disposition
                raise ReactivationBlocked("scheduler_update_not_verified")
            result["scheduler_mutation"] = scheduler_disposition

            result["stage"] = "SCHEDULER_READBACK"
            if self._boundaries.read_scheduler() != plan.scheduler:
                raise ReactivationBlocked("scheduler_readback_drift")

            result["stage"] = "PRE_LEASE_REVERIFY"
            before_lease = self._boundaries.observe_admission("BEFORE_LEASE", plan)
            _require_admission(
                before_lease,
                plan=plan,
                scheduler_planned=True,
                final_lease=False,
            )
            _require_evidence(
                plan, self._boundaries.observe_evidence(plan.evidence_path)
            )

            result["stage"] = "FINAL_LEASE_PUBLICATION"
            result["lease_publication"] = MutationDisposition.INDETERMINATE
            publication = self._boundaries.publish_lease(plan.lease)
            if (
                type(publication) is not LeasePublicationObservation
                or publication.disposition is not MutationDisposition.PUBLISHED_VERIFIED
                or publication.steps != LEASE_PUBLICATION_STEPS
            ):
                raise ReactivationBlocked("lease_publication_protocol_drift")
            result["lease_publication"] = publication.disposition

            result["stage"] = "POST_ARM_READBACK"
            final = self._boundaries.observe_admission("FINAL", plan)
            _require_admission(
                final,
                plan=plan,
                scheduler_planned=True,
                final_lease=True,
            )
            _require_evidence(
                plan, self._boundaries.observe_evidence(plan.evidence_path)
            )
            if self._boundaries.read_scheduler() != plan.scheduler:
                raise ReactivationBlocked("final_scheduler_readback_drift")

            result.update(status="PASS", stage="COMPLETE")
            return result
        except Exception as exc:
            result["reason"] = type(exc).__name__
            result["detail"] = str(exc)
            if mutation_possible:
                result["reconciliation_required"] = True
                if (
                    result["scheduler_mutation"] is MutationDisposition.INDETERMINATE
                    or result["lease_publication"] is MutationDisposition.INDETERMINATE
                ):
                    result["status"] = "INDETERMINATE"
                else:
                    result["status"] = "STOPPED"
            return result
        finally:
            credential = None
