from __future__ import annotations

from datetime import UTC, datetime

from scripts import d10_arch128_r6_reactivation as r6
from scripts import d10_arch128_r7_protected as r7


ACTIVATION = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


class FakeBoundaries:
    def observe_admission(self, stage, plan):
        identity = r7.r6.r4.NEW_IDENTITY
        if stage == "INITIAL":
            return r6.AdmissionObservation(
                deployment_id=identity.deployment_id,
                attestation_sha256=identity.unsigned_attestation_sha256,
                certified_source_head=identity.certified_source_head,
                certified_source_tree=identity.certified_source_tree,
                lease_final_installing_tmp_present=(False, False, False),
                evidence_paths=(),
                scheduler_disabled_nonrunning_exact=True,
                scheduler=None,
            )
        assert plan is not None
        if stage == "AFTER_CREDENTIAL":
            scheduler = None
            final = False
            disabled = True
        elif stage == "BEFORE_LEASE":
            scheduler = plan.scheduler
            final = False
            disabled = False
        else:
            assert stage == "FINAL"
            scheduler = plan.scheduler
            final = True
            disabled = False
        return r6.AdmissionObservation(
            deployment_id=identity.deployment_id,
            attestation_sha256=identity.unsigned_attestation_sha256,
            certified_source_head=identity.certified_source_head,
            certified_source_tree=identity.certified_source_tree,
            lease_final_installing_tmp_present=(final, False, False),
            evidence_paths=(plan.evidence_path,),
            scheduler_disabled_nonrunning_exact=disabled,
            scheduler=scheduler,
        )

    def create_empty_evidence(self, path):
        self.path = path

    def observe_evidence(self, path):
        return r6.EvidenceObservation(
            path=path,
            size=0,
            owner_sid=r6.ADMINISTRATORS_SID,
            protected_dacl=True,
            administrators_access_mask=r6.FILE_ALL_ACCESS,
            system_access_mask=r6.FILE_ALL_ACCESS,
            trading_access_mask=r6.guard.TRADING_EVIDENCE_FILE_ACCESS,
            local_ntfs=True,
            non_reparse=True,
            hard_link_count=1,
        )

    def probe_trading_append_open(self, path):
        return r6.TradingOpenObservation(
            trading_sid=r6.guard.TRADING_SID,
            desired_access=r6.guard.TRADING_EVIDENCE_FILE_ACCESS,
            share_mode=1,
            creation_disposition=3,
            flags=r6.guard.FILE_FLAG_OPEN_REPARSE_POINT
            | r6.guard.FILE_FLAG_WRITE_THROUGH,
            opened=True,
            bytes_written=0,
        )

    def acquire_scheduler_credential(self):
        return object()

    def update_scheduler(self, plan, credential):
        self.plan = plan
        return r6.MutationDisposition.CALL_RETURNED

    def read_scheduler(self):
        return self.plan.scheduler

    def publish_lease(self, lease):
        return r6.LeasePublicationObservation(
            r6.MutationDisposition.PUBLISHED_VERIFIED,
            r6.LEASE_PUBLICATION_STEPS,
        )


def factory():
    return FakeBoundaries(), lambda: ACTIVATION


def test_missing_authorization_never_constructs_boundaries() -> None:
    calls = 0

    def forbidden_factory():
        nonlocal calls
        calls += 1
        return factory()

    result = r7._dispatch((r7.EXECUTE_FLAG,), {}, forbidden_factory)

    assert result["status"] == "BLOCKED"
    assert result["authorization"] == "NOT_ACCEPTED"
    assert result["evidence_provision"] == r6.MutationDisposition.NOT_RUN
    assert result["scheduler_mutation"] == r6.MutationDisposition.NOT_RUN
    assert result["lease_publication"] == r6.MutationDisposition.NOT_RUN
    assert calls == 0


def test_wrong_argument_never_constructs_boundaries() -> None:
    calls = 0

    def forbidden_factory():
        nonlocal calls
        calls += 1
        return factory()

    result = r7._dispatch(
        ("--wrong",),
        {r7.AUTH_ENV: r7.AUTH_VALUE},
        forbidden_factory,
    )

    assert result["status"] == "BLOCKED"
    assert calls == 0


def test_exact_interlock_composes_r6_and_preserves_closed_effects() -> None:
    result = r7._dispatch(
        (r7.EXECUTE_FLAG,),
        {r7.AUTH_ENV: r7.AUTH_VALUE},
        factory,
    )

    assert result["status"] == "PASS"
    assert result["stage"] == "COMPLETE"
    assert result["authorization"] == "ACCEPTED"
    assert result["evidence_provision"] == r6.MutationDisposition.CALL_RETURNED
    assert result["scheduler_mutation"] == r6.MutationDisposition.CALL_RETURNED
    assert result["lease_publication"] == r6.MutationDisposition.PUBLISHED_VERIFIED
    assert result["manual_task_start"] == "NOT_RUN"
    assert result["source_launch"] == "NOT_RUN"
    assert result["provider"] == "NOT_RUN"
    assert result["Paper-v2"] == "NOT_RUN"
    assert result["broker"] == "NOT_RUN"
    assert result["live"] == "NOT_RUN"
    assert result["automatic_retry"] is False
    assert result["automatic_rollback"] is False
    assert result["automatic_cleanup"] is False


def test_factory_failure_is_terminal_and_not_retry_authority() -> None:
    def broken_factory():
        raise RuntimeError("no host binding")

    result = r7._dispatch(
        (r7.EXECUTE_FLAG,),
        {r7.AUTH_ENV: r7.AUTH_VALUE},
        broken_factory,
    )

    assert result["status"] == "STOPPED"
    assert result["stage"] == "FACTORY_OR_COMPOSITION_FAILURE"
    assert result["reconciliation_required"] is True
    assert result["automatic_retry"] is False
    assert result["automatic_rollback"] is False
    assert result["automatic_cleanup"] is False
