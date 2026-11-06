from dataclasses import replace

import pytest

from trading_bot.live_prototype.delivery_operator import (
    AcceptedSourceIdentity,
    FutureEvidenceMilestone,
    FutureEvidenceSlot,
    assemble_q63_delivery_package,
)


def _accepted_identity(milestone: str = "L40") -> AcceptedSourceIdentity:
    return AcceptedSourceIdentity(
        milestone=milestone,
        source_head="a" * 40,
        source_tree="b" * 40,
        acceptance_reference="github-review:accepted-source-1",
    )


def test_q63_preserves_accepted_identity_and_leaves_future_evidence_not_run() -> None:
    accepted = _accepted_identity()

    package = assemble_q63_delivery_package((accepted,))

    assert package.accepted_identities == (accepted,)
    assert tuple(slot.milestone for slot in package.future_evidence) == tuple(
        FutureEvidenceMilestone
    )
    assert all(slot.status == "NOT_RUN" for slot in package.future_evidence)
    assert all(slot.evidence_sha256 is None for slot in package.future_evidence)
    assert package.q63_status == "NOT_RUN"
    assert package.readiness_label is None
    assert package.live_readiness_granted is False


def test_q63_rejects_duplicate_accepted_milestones_and_promoted_slots() -> None:
    identity = _accepted_identity()
    with pytest.raises(ValueError, match="must be unique"):
        assemble_q63_delivery_package((identity, identity))

    slot = FutureEvidenceSlot(FutureEvidenceMilestone.Q62)
    with pytest.raises(ValueError, match="cannot promote"):
        replace(slot, status="ACCEPTED", evidence_sha256="b" * 64)
