"""Pure S2B metadata package; external artifact truth remains an operator review.

Digests identify reviewed artifacts only. Completeness is supplied evidence, not
independent verification, acceptance, trading authority, or a profitability test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from scripts import d10_end_of_soak_review as internal_review_policy

SCHEMA: Final = "d10-external-review-package/v1"
DEPLOYMENT_ID: Final = internal_review_policy.DEPLOYMENT_ID
SOAK_ID: Final = internal_review_policy.SOAK_ID
ATTESTATION_SHA256: Final = internal_review_policy.ATTESTATION_SHA256
ACTIVATION_UTC: Final = internal_review_policy.ACTIVATION_UTC
END_UTC: Final = internal_review_policy.END_UTC


class D10ExternalReviewCategory(StrEnum):
    SCHEDULER_SLOT_COVERAGE = "SCHEDULER_SLOT_COVERAGE"
    ELIGIBLE_XNYS_SESSION_COVERAGE = "ELIGIBLE_XNYS_SESSION_COVERAGE"
    SLEEP_REBOOT_DUPLICATE_CONTEXT = "SLEEP_REBOOT_DUPLICATE_CONTEXT"
    PAPER_V2_ACCOUNT_TRADES_POSITIONS_PERFORMANCE = (
        "PAPER_V2_ACCOUNT_TRADES_POSITIONS_PERFORMANCE"
    )
    AUDIT_COMPLETENESS = "AUDIT_COMPLETENESS"


CATEGORY_ORDER: Final = tuple(D10ExternalReviewCategory)
EXTERNAL_REVIEW_CATEGORIES: Final = tuple(item.value for item in CATEGORY_ORDER)
INTERNAL_REVIEW_FIELDS: Final = (
    "schema",
    "status",
    "internal_wake_evidence",
    "d10_accepted",
    "broker_paper_authorized",
    "operator_decision_required",
    "wake_count",
    "completed_count",
    "no_action_count",
    "stopped_count",
    "provider_attempts",
    "settlement_attempts",
    "publication_attempts",
    "first_observed_at_utc",
    "last_observed_at_utc",
    "reviewed_at_utc",
    "minimum_daily_wake_count_met",
    "extra_wake_count",
    "deployment_id",
    "soak_id",
    "attestation_sha256",
    "certified_source_head",
    "certified_source_tree",
    "executable_file_count",
    "external_review_required",
)
COUNT_FIELDS: Final = (
    "wake_count",
    "completed_count",
    "no_action_count",
    "stopped_count",
    "provider_attempts",
    "settlement_attempts",
    "publication_attempts",
    "extra_wake_count",
)


@dataclass(frozen=True, slots=True)
class D10ExternalReviewEvidence:
    category: D10ExternalReviewCategory
    deployment_id: str
    soak_id: str
    activation_utc: datetime
    end_utc: datetime
    reviewed_at_utc: datetime
    artifact_sha256: str
    artifact_byte_length: int
    complete: bool
    unresolved_findings: int


def _blocked(reason: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "reason": reason,
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }


def _utc(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is UTC


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime | None:
    # S2A always emits six fractional digits and the literal UTC suffix.
    if type(value) is not str or len(value) != 27:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if not _utc(parsed) or _timestamp(parsed) != value:
        return None
    return parsed


def _internal_reason(
    review: dict[str, object], packaged_at_utc: datetime
) -> str | None:
    if (
        type(review) is not dict
        or any(type(key) is not str for key in review)
        or set(review) != set(INTERNAL_REVIEW_FIELDS)
    ):
        return "internal_review_shape_invalid"
    if (
        type(review["schema"]) is not str
        or review["schema"] != internal_review_policy.SCHEMA
        or type(review["status"]) is not str
        or review["status"] != "READY_FOR_OPERATOR_REVIEW"
        or type(review["internal_wake_evidence"]) is not str
        or review["internal_wake_evidence"] != "PASS"
        or review["d10_accepted"] is not False
        or review["broker_paper_authorized"] is not False
        or review["operator_decision_required"] is not True
        or review["minimum_daily_wake_count_met"] is not True
    ):
        return "internal_review_not_ready"
    if any(
        type(review[field]) is not str or review[field] != expected
        for field, expected in (
            ("deployment_id", DEPLOYMENT_ID),
            ("soak_id", SOAK_ID),
            ("attestation_sha256", ATTESTATION_SHA256),
        )
    ):
        return "internal_review_identity_mismatch"
    required = review["external_review_required"]
    if (
        type(required) is not tuple
        or any(type(category) is not str for category in required)
        or required != internal_review_policy.EXTERNAL_REVIEW_REQUIRED
        or required != EXTERNAL_REVIEW_CATEGORIES
    ):
        return "internal_review_shape_invalid"
    if (
        any(
            type(review[field]) is not int or review[field] < 0
            for field in COUNT_FIELDS
        )
        or review["wake_count"] < 7
        or review["completed_count"] + review["no_action_count"] != review["wake_count"]
        or review["stopped_count"] != 0
        or review["extra_wake_count"] != review["wake_count"] - 7
        or type(review["executable_file_count"]) is not int
        or review["executable_file_count"] <= 0
    ):
        return "internal_review_counts_invalid"
    if any(
        type(review[field]) is not str or not review[field]
        for field in ("certified_source_head", "certified_source_tree")
    ):
        return "internal_review_shape_invalid"
    first = _parse_timestamp(review["first_observed_at_utc"])
    last = _parse_timestamp(review["last_observed_at_utc"])
    reviewed = _parse_timestamp(review["reviewed_at_utc"])
    if (
        first is None
        or last is None
        or reviewed is None
        or not ACTIVATION_UTC <= first <= last < END_UTC
        or not END_UTC <= reviewed <= packaged_at_utc
    ):
        return "internal_review_time_invalid"
    return None


def build_package(
    internal_review: dict[str, object],
    external_reviews: tuple[D10ExternalReviewEvidence, ...],
    *,
    packaged_at_utc: datetime,
) -> dict[str, object]:
    """Validate supplied metadata only; never collect, retry, repair, or decide."""
    if not _utc(packaged_at_utc):
        return _blocked("package_time_invalid")
    if packaged_at_utc < END_UTC:
        return _blocked("package_window_not_complete")
    reason = _internal_reason(internal_review, packaged_at_utc)
    if reason is not None:
        return _blocked(reason)
    if type(external_reviews) is not tuple or any(
        type(item) is not D10ExternalReviewEvidence for item in external_reviews
    ):
        return _blocked("external_review_input_invalid")
    if len(external_reviews) != 5 or any(
        type(item.category) is not D10ExternalReviewCategory
        for item in external_reviews
    ):
        return _blocked("external_review_category_set_invalid")
    by_category = {item.category: item for item in external_reviews}
    if len(by_category) != 5 or set(by_category) != set(CATEGORY_ORDER):
        return _blocked("external_review_category_set_invalid")
    ordered = tuple(by_category[category] for category in CATEGORY_ORDER)
    for item in ordered:
        if (
            type(item.deployment_id) is not str
            or item.deployment_id != DEPLOYMENT_ID
            or type(item.soak_id) is not str
            or item.soak_id != SOAK_ID
            or not _utc(item.activation_utc)
            or item.activation_utc != ACTIVATION_UTC
            or not _utc(item.end_utc)
            or item.end_utc != END_UTC
        ):
            return _blocked("external_review_identity_mismatch")
        if not _utc(item.reviewed_at_utc) or not (
            END_UTC <= item.reviewed_at_utc <= packaged_at_utc
        ):
            return _blocked("external_review_time_invalid")
        if (
            type(item.artifact_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", item.artifact_sha256) is None
            or type(item.artifact_byte_length) is not int
            or item.artifact_byte_length <= 0
        ):
            return _blocked("external_review_artifact_invalid")
        if type(item.complete) is not bool or item.complete is not True:
            return _blocked("external_review_incomplete")
        if type(item.unresolved_findings) is not int or item.unresolved_findings != 0:
            return _blocked("external_review_unresolved")
    return {
        "schema": SCHEMA,
        "status": "READY_FOR_OPERATOR_DECISION",
        "internal_review_status": "READY_FOR_OPERATOR_REVIEW",
        "external_review_status": "COMPLETE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
        "deployment_id": DEPLOYMENT_ID,
        "soak_id": SOAK_ID,
        "attestation_sha256": ATTESTATION_SHA256,
        "certified_source_head": internal_review["certified_source_head"],
        "certified_source_tree": internal_review["certified_source_tree"],
        "executable_file_count": internal_review["executable_file_count"],
        "wake_count": internal_review["wake_count"],
        "completed_count": internal_review["completed_count"],
        "no_action_count": internal_review["no_action_count"],
        "extra_wake_count": internal_review["extra_wake_count"],
        "packaged_at_utc": _timestamp(packaged_at_utc),
        "external_review_categories": EXTERNAL_REVIEW_CATEGORIES,
        "external_review_artifacts": tuple(
            {
                "category": item.category.value,
                "reviewed_at_utc": _timestamp(item.reviewed_at_utc),
                "artifact_sha256": item.artifact_sha256,
                "artifact_byte_length": item.artifact_byte_length,
                "complete": item.complete,
                "unresolved_findings": item.unresolved_findings,
            }
            for item in ordered
        ),
    }
