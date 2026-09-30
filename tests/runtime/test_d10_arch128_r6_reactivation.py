from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_arch128_r6_reactivation as r6
from scripts import run_personal_desktop_d10_launch_guard as guard
from scripts.d10_protected_deployment import (
    ADMINISTRATORS_SID,
    FILE_ALL_ACCESS,
    SYSTEM_SID,
)


ACTIVATION = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


class FakeBoundaries:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.plan: r6.ReactivationPlan | None = None
        self.evidence_calls = 0
        self.scheduler_disposition = r6.MutationDisposition.CALL_RETURNED
        self.publication = r6.LeasePublicationObservation(
            r6.MutationDisposition.PUBLISHED_VERIFIED,
            r6.LEASE_PUBLICATION_STEPS,
        )
        self.scheduler_readback_override: object | None = None
        self.nonempty_evidence_after = 10**9

    def _admission(
        self,
        plan: r6.ReactivationPlan | None,
        *,
        scheduler_planned: bool,
        final_lease: bool,
    ) -> r6.AdmissionObservation:
        identity = r4.NEW_IDENTITY
        return r6.AdmissionObservation(
            deployment_id=identity.deployment_id,
            attestation_sha256=identity.unsigned_attestation_sha256,
            certified_source_head=identity.certified_source_head,
            certified_source_tree=identity.certified_source_tree,
            lease_final_installing_tmp_present=(final_lease, False, False),
            evidence_paths=() if plan is None else (plan.evidence_path,),
            scheduler_disabled_nonrunning_exact=not scheduler_planned,
            scheduler=plan.scheduler if scheduler_planned and plan is not None else None,
        )

    def observe_admission(
        self, stage: str, plan: r6.ReactivationPlan | None
    ) -> r6.AdmissionObservation:
        self.events.append(f"admit:{stage}")
        if stage == "INITIAL":
            return self._admission(None, scheduler_planned=False, final_lease=False)
        assert plan is not None
        self.plan = plan
        if stage == "AFTER_CREDENTIAL":
            return self._admission(plan, scheduler_planned=False, final_lease=False)
        if stage == "BEFORE_LEASE":
            return self._admission(plan, scheduler_planned=True, final_lease=False)
        assert stage == "FINAL"
        return self._admission(plan, scheduler_planned=True, final_lease=True)

    def create_empty_evidence(self, path: str) -> None:
        self.events.append("create_evidence")
        assert path.endswith(".jsonl")

    def observe_evidence(self, path: str) -> r6.EvidenceObservation:
        self.events.append("observe_evidence")
        self.evidence_calls += 1
        size = 1 if self.evidence_calls >= self.nonempty_evidence_after else 0
        return r6.EvidenceObservation(
            path=path,
            size=size,
            owner_sid=ADMINISTRATORS_SID,
            protected_dacl=True,
            administrators_access_mask=FILE_ALL_ACCESS,
            system_access_mask=FILE_ALL_ACCESS,
            trading_access_mask=guard.TRADING_EVIDENCE_FILE_ACCESS,
            local_ntfs=True,
            non_reparse=True,
            hard_link_count=1,
        )

    def probe_trading_append_open(self, path: str) -> r6.TradingOpenObservation:
        self.events.append("probe_trading")
        assert path.endswith(".jsonl")
        return r6.TradingOpenObservation(
            trading_sid=guard.TRADING_SID,
            desired_access=guard.TRADING_EVIDENCE_FILE_ACCESS,
            share_mode=1,
            creation_disposition=3,
            flags=guard.FILE_FLAG_OPEN_REPARSE_POINT | guard.FILE_FLAG_WRITE_THROUGH,
            opened=True,
            bytes_written=0,
        )

    def acquire_scheduler_credential(self) -> object:
        self.events.append("credential")
        return object()

    def update_scheduler(
        self, plan: r6.ReactivationPlan, credential: object
    ) -> r6.MutationDisposition:
        self.events.append("update_scheduler")
        self.plan = plan
        assert credential is not None
        return self.scheduler_disposition

    def read_scheduler(self):
        self.events.append("read_scheduler")
        if self.scheduler_readback_override is not None:
            return self.scheduler_readback_override
        assert self.plan is not None
        return self.plan.scheduler

    def publish_lease(
        self, lease
    ) -> r6.LeasePublicationObservation:
        self.events.append("publish_lease")
        assert self.plan is not None
        assert lease == self.plan.lease
        return self.publication


def _run(fake: FakeBoundaries) -> dict[str, object]:
    return r6.ReactivationOperator(fake, lambda: ACTIVATION).run(execute_r7=True)


def test_plan_derives_new_lease_soak_and_evidence_path_only() -> None:
    plan = r6.derive_reactivation_plan(ACTIVATION)

    assert plan.lease.deployment_id == r4.NEW_DEPLOYMENT_ID
    assert plan.lease.soak_id != r4.OLD_SOAK_ID
    assert plan.lease.accepted_activation_utc == ACTIVATION
    assert plan.lease.end_utc == ACTIVATION + timedelta(days=7)
    assert plan.evidence_path == (
        rf"F:\AITradingBot\D10\evidence\wake-{plan.lease.soak_id}.jsonl"
    )
    assert plan.scheduler.window.activation_utc == plan.lease.accepted_activation_utc
    assert plan.scheduler.window.end_utc == plan.lease.end_utc


def test_old_halted_activation_is_never_reused() -> None:
    old = datetime.fromisoformat(
        r4.OLD_ACTIVATION_UTC[:-1] + "+00:00"
    ).astimezone(UTC)

    with pytest.raises(r6.ReactivationBlocked, match="halted_soak_identity_reuse"):
        r6.derive_reactivation_plan(old)


@pytest.mark.parametrize(
    "activation",
    [
        datetime(2026, 10, 1, 12, 0, 0),
        datetime(2026, 10, 1, 12, 0, 0, 1, tzinfo=UTC),
    ],
)
def test_activation_requires_exact_utc_second(activation: datetime) -> None:
    with pytest.raises(r6.ReactivationBlocked, match="exact_utc_second"):
        r6.derive_reactivation_plan(activation)


def test_success_order_keeps_final_lease_as_last_arming_mutation() -> None:
    fake = FakeBoundaries()

    result = _run(fake)

    assert result["status"] == "PASS"
    assert result["stage"] == "COMPLETE"
    assert result["evidence_provision"] == r6.MutationDisposition.CALL_RETURNED
    assert result["scheduler_mutation"] == r6.MutationDisposition.CALL_RETURNED
    assert result["lease_publication"] == r6.MutationDisposition.PUBLISHED_VERIFIED
    assert result["automatic_retry"] is False
    assert result["automatic_rollback"] is False
    assert result["automatic_cleanup"] is False
    assert result["manual_task_start"] == "NOT_RUN"
    assert result["source_launch"] == "NOT_RUN"
    assert result["provider"] == "NOT_RUN"
    assert result["Paper-v2"] == "NOT_RUN"
    assert result["broker"] == "NOT_RUN"
    assert result["live"] == "NOT_RUN"
    assert fake.events == [
        "admit:INITIAL",
        "create_evidence",
        "observe_evidence",
        "probe_trading",
        "credential",
        "admit:AFTER_CREDENTIAL",
        "observe_evidence",
        "update_scheduler",
        "read_scheduler",
        "admit:BEFORE_LEASE",
        "observe_evidence",
        "publish_lease",
        "admit:FINAL",
        "observe_evidence",
        "read_scheduler",
    ]


def test_evidence_policy_is_append_only_and_probe_writes_nothing() -> None:
    fake = FakeBoundaries()
    result = _run(fake)

    assert result["status"] == "PASS"
    mask = guard.TRADING_EVIDENCE_FILE_ACCESS
    assert mask & guard.FILE_APPEND_DATA
    assert not mask & guard.FILE_WRITE_DATA
    probe = fake.probe_trading_append_open(fake.plan.evidence_path)
    assert probe.bytes_written == 0
    assert probe.flags & guard.FILE_FLAG_WRITE_THROUGH


def test_evidence_drift_before_lease_blocks_publication() -> None:
    fake = FakeBoundaries()
    fake.nonempty_evidence_after = 3

    result = _run(fake)

    assert result["status"] == "STOPPED"
    assert result["reconciliation_required"] is True
    assert "publish_lease" not in fake.events
    assert result["lease_publication"] == r6.MutationDisposition.NOT_RUN


def test_scheduler_readback_mismatch_blocks_final_lease() -> None:
    fake = FakeBoundaries()
    fake.scheduler_readback_override = object()

    result = _run(fake)

    assert result["status"] == "STOPPED"
    assert result["reconciliation_required"] is True
    assert "publish_lease" not in fake.events


def test_indeterminate_scheduler_never_retries_or_publishes_lease() -> None:
    fake = FakeBoundaries()
    fake.scheduler_disposition = r6.MutationDisposition.INDETERMINATE

    result = _run(fake)

    assert result["status"] == "INDETERMINATE"
    assert result["reconciliation_required"] is True
    assert result["automatic_retry"] is False
    assert "publish_lease" not in fake.events
    assert fake.events.count("update_scheduler") == 1


def test_partial_lease_protocol_is_indeterminate_and_not_retried() -> None:
    fake = FakeBoundaries()
    fake.publication = r6.LeasePublicationObservation(
        r6.MutationDisposition.PUBLISHED_VERIFIED,
        r6.LEASE_PUBLICATION_STEPS[:-1],
    )

    result = _run(fake)

    assert result["status"] == "INDETERMINATE"
    assert result["reconciliation_required"] is True
    assert result["automatic_retry"] is False
    assert fake.events.count("publish_lease") == 1


def test_execution_interlock_is_source_only_by_default() -> None:
    fake = FakeBoundaries()
    operator = r6.ReactivationOperator(fake, lambda: ACTIVATION)

    result = operator.run()

    assert result["status"] == "BLOCKED"
    assert result["stage"] == "EXECUTION_INTERLOCK"
    assert fake.events == []
