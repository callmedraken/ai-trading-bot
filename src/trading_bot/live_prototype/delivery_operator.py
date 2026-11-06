"""Q63 delivery-plan assembly without inventing acceptance or readiness."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_GIT_ID = re.compile(r"[0-9a-f]{40}\Z")
_REFERENCE = re.compile(r"[A-Za-z0-9._:/-]{1,160}\Z")


class FutureEvidenceMilestone(StrEnum):
    L41R1 = "L41R1"
    Q61 = "Q61"
    Q62 = "Q62"
    L43 = "L43"
    Q63 = "Q63"


@dataclass(frozen=True, slots=True)
class AcceptedSourceIdentity:
    """Identity metadata already accepted elsewhere; this type verifies no claim."""

    milestone: str
    source_head: str
    source_tree: str
    acceptance_reference: str

    def __post_init__(self) -> None:
        if (
            type(self.milestone) is not str
            or re.fullmatch(r"[A-Z][A-Z0-9-]{0,31}", self.milestone) is None
        ):
            raise ValueError("milestone identifier is invalid")
        if (
            type(self.source_head) is not str
            or _GIT_ID.fullmatch(self.source_head) is None
        ):
            raise ValueError("exact accepted source HEAD required")
        if (
            type(self.source_tree) is not str
            or _GIT_ID.fullmatch(self.source_tree) is None
        ):
            raise ValueError("exact accepted source tree required")
        if (
            type(self.acceptance_reference) is not str
            or _REFERENCE.fullmatch(self.acceptance_reference) is None
        ):
            raise ValueError("acceptance reference required")


@dataclass(frozen=True, slots=True)
class FutureEvidenceSlot:
    milestone: FutureEvidenceMilestone
    status: str = "NOT_RUN"
    evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.milestone, FutureEvidenceMilestone):
            raise TypeError("future evidence milestone must be typed")
        if self.status != "NOT_RUN" or self.evidence_sha256 is not None:
            raise ValueError("this assembler cannot promote future evidence")


@dataclass(frozen=True, slots=True)
class Q63DeliveryPackage:
    accepted_identities: tuple[AcceptedSourceIdentity, ...]
    future_evidence: tuple[FutureEvidenceSlot, ...]
    q63_status: str = "NOT_RUN"
    readiness_label: None = None
    live_readiness_granted: bool = False

    def __post_init__(self) -> None:
        if type(self.accepted_identities) is not tuple or any(
            type(item) is not AcceptedSourceIdentity
            for item in self.accepted_identities
        ):
            raise TypeError("accepted identities must be a tuple")
        if type(self.future_evidence) is not tuple or any(
            type(item) is not FutureEvidenceSlot for item in self.future_evidence
        ):
            raise TypeError("future evidence slots must be a tuple")
        if tuple(slot.milestone for slot in self.future_evidence) != tuple(
            FutureEvidenceMilestone
        ):
            raise ValueError(
                "all future evidence slots must remain present and ordered"
            )
        milestones = tuple(item.milestone for item in self.accepted_identities)
        if len(set(milestones)) != len(milestones):
            raise ValueError("accepted source milestone identities must be unique")
        if self.q63_status != "NOT_RUN" or self.readiness_label is not None:
            raise ValueError(
                "delivery assembly cannot claim Q63 completion or readiness"
            )
        if self.live_readiness_granted is not False:
            raise ValueError("delivery assembly grants no live readiness")


def assemble_q63_delivery_package(
    accepted_identities: tuple[AcceptedSourceIdentity, ...],
) -> Q63DeliveryPackage:
    """Preserve supplied accepted identities and leave every future gate NOT_RUN."""

    if type(accepted_identities) is not tuple or not accepted_identities:
        raise ValueError("at least one accepted source identity is required")
    if any(type(item) is not AcceptedSourceIdentity for item in accepted_identities):
        raise TypeError("accepted source identities must be typed")
    milestones = tuple(item.milestone for item in accepted_identities)
    if len(set(milestones)) != len(milestones):
        raise ValueError("accepted source milestone identities must be unique")
    return Q63DeliveryPackage(
        accepted_identities=accepted_identities,
        future_evidence=tuple(
            FutureEvidenceSlot(item) for item in FutureEvidenceMilestone
        ),
    )
