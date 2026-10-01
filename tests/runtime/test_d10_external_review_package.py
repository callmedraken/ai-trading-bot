"""Synthetic-only S2B contracts; no external facts are collected or inferred."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from scripts import d10_end_of_soak_review as internal
from scripts import d10_external_review_package as package
from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (
    D10OneWeekWakeEvidence,
    D10WakeOutcome,
)

CATEGORIES = (
    "SCHEDULER_SLOT_COVERAGE",
    "ELIGIBLE_XNYS_SESSION_COVERAGE",
    "SLEEP_REBOOT_DUPLICATE_CONTEXT",
    "PAPER_V2_ACCOUNT_TRADES_POSITIONS_PERFORMANCE",
    "AUDIT_COMPLETENESS",
)


def _internal() -> dict[str, object]:
    return {
        "schema": "d10-end-of-soak-operator-review/v1",
        "status": "READY_FOR_OPERATOR_REVIEW",
        "internal_wake_evidence": "PASS",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
        "wake_count": 8,
        "completed_count": 5,
        "no_action_count": 3,
        "stopped_count": 0,
        "provider_attempts": 3,
        "settlement_attempts": 0,
        "publication_attempts": 1,
        "first_observed_at_utc": "2026-09-30T22:07:24.000000Z",
        "last_observed_at_utc": "2026-10-07T21:07:24.000000Z",
        "reviewed_at_utc": "2026-10-07T22:07:24.000000Z",
        "minimum_daily_wake_count_met": True,
        "extra_wake_count": 1,
        "deployment_id": "d2071f25-5a7c-5293-a28f-5b722c9917a2",
        "soak_id": "30e31396-9f51-57ca-a480-d2a3e9cae4a0",
        "attestation_sha256": (
            "3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"
        ),
        "certified_source_head": "synthetic-source-head",
        "certified_source_tree": "synthetic-source-tree",
        "executable_file_count": 100,
        "external_review_required": CATEGORIES,
    }


def _reviews() -> tuple[package.D10ExternalReviewEvidence, ...]:
    return tuple(
        package.D10ExternalReviewEvidence(
            category=category,
            deployment_id=internal.DEPLOYMENT_ID,
            soak_id=internal.SOAK_ID,
            activation_utc=internal.ACTIVATION_UTC,
            end_utc=internal.END_UTC,
            reviewed_at_utc=internal.END_UTC,
            artifact_sha256="a" * 64,
            artifact_byte_length=123,
            complete=True,
            unresolved_findings=0,
        )
        for category in package.D10ExternalReviewCategory
    )


def _build(review=None, reviews=None, *, at=internal.END_UTC):
    return package.build_package(
        _internal() if review is None else review,
        _reviews() if reviews is None else reviews,
        packaged_at_utc=at,
    )


def _no_authority(result) -> None:
    assert result["schema"] == "d10-external-review-package/v1"
    assert result["d10_accepted"] is False
    assert result["broker_paper_authorized"] is False
    assert result["operator_decision_required"] is True


def _blocked(result, reason) -> None:
    _no_authority(result)
    assert result == {
        "schema": "d10-external-review-package/v1",
        "status": "BLOCKED",
        "reason": reason,
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
    }


def test_success_is_only_ready_for_operator_decision_and_sanitized() -> None:
    result = _build()
    _no_authority(result)
    assert result == {
        "schema": "d10-external-review-package/v1",
        "status": "READY_FOR_OPERATOR_DECISION",
        "internal_review_status": "READY_FOR_OPERATOR_REVIEW",
        "external_review_status": "COMPLETE",
        "d10_accepted": False,
        "broker_paper_authorized": False,
        "operator_decision_required": True,
        "deployment_id": internal.DEPLOYMENT_ID,
        "soak_id": internal.SOAK_ID,
        "attestation_sha256": internal.ATTESTATION_SHA256,
        "certified_source_head": "synthetic-source-head",
        "certified_source_tree": "synthetic-source-tree",
        "executable_file_count": 100,
        "wake_count": 8,
        "completed_count": 5,
        "no_action_count": 3,
        "extra_wake_count": 1,
        "packaged_at_utc": "2026-10-07T22:07:24.000000Z",
        "external_review_categories": CATEGORIES,
        "external_review_artifacts": tuple(
            {
                "category": category,
                "reviewed_at_utc": "2026-10-07T22:07:24.000000Z",
                "artifact_sha256": "a" * 64,
                "artifact_byte_length": 123,
                "complete": True,
                "unresolved_findings": 0,
            }
            for category in CATEGORIES
        ),
    }


def test_order_is_deterministic_and_inputs_and_output_are_independent() -> None:
    review = _internal()
    original = review.copy()
    reviews = _reviews()
    expected = _build(review, reviews)
    for offset in range(5):
        reordered = reviews[offset:] + reviews[:offset]
        assert _build(review, reordered) == expected
        assert _build(review, tuple(reversed(reordered))) == expected
    expected["external_review_artifacts"][0]["complete"] = False
    assert review == original
    assert reviews[0].complete is True
    assert _build(review, reviews)["external_review_artifacts"][0]["complete"] is True


def test_evidence_is_frozen_slotted_and_has_only_bounded_metadata() -> None:
    item = _reviews()[0]
    assert not hasattr(item, "__dict__")
    assert tuple(field.name for field in fields(item)) == (
        "category",
        "deployment_id",
        "soak_id",
        "activation_utc",
        "end_utc",
        "reviewed_at_utc",
        "artifact_sha256",
        "artifact_byte_length",
        "complete",
        "unresolved_findings",
    )
    with pytest.raises(FrozenInstanceError):
        item.complete = False


def test_exact_successful_s2a_result_is_consumed_without_analyzer_call(monkeypatch):
    wakes = tuple(
        D10OneWeekWakeEvidence(
            outcome=D10WakeOutcome.NO_ACTION,
            stop_reason=None,
            observed_at_utc=internal.ACTIVATION_UTC + timedelta(hours=index),
            deployment_id=internal.DEPLOYMENT_ID,
            attestation_sha256=internal.ATTESTATION_SHA256,
            soak_id=internal.SOAK_ID,
            activation_utc=internal.ACTIVATION_UTC,
            end_utc=internal.END_UTC,
            certified_source_head="synthetic-source-head",
            certified_source_tree="synthetic-source-tree",
            executable_file_count=100,
        )
        for index in range(7)
    )
    review = internal.analyze(wakes, reviewed_at_utc=internal.END_UTC)

    def forbidden(*args, **kwargs):
        pytest.fail("S2B must not call analyze")

    monkeypatch.setattr(internal, "analyze", forbidden)
    result = _build(review)
    assert result["status"] == "READY_FOR_OPERATOR_DECISION"
    assert result["no_action_count"] == 7
    assert result["extra_wake_count"] == 0
    _no_authority(result)


def test_no_profitability_input_or_threshold_is_required() -> None:
    # Same composite artifact digest can support every reviewed category,
    # including reviewed performance of any sign. No performance value is read.
    assert tuple(item.value for item in package.D10ExternalReviewCategory) == CATEGORIES
    assert _build()["status"] == "READY_FOR_OPERATOR_DECISION"
    assert all("profit" not in field.name for field in fields(_reviews()[0]))


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("deployment_id", "foreign", "external_review_identity_mismatch"),
        ("deployment_id", 1, "external_review_identity_mismatch"),
        ("soak_id", "foreign", "external_review_identity_mismatch"),
        (
            "activation_utc",
            internal.ACTIVATION_UTC + timedelta(seconds=1),
            "external_review_identity_mismatch",
        ),
        (
            "end_utc",
            internal.END_UTC + timedelta(seconds=1),
            "external_review_identity_mismatch",
        ),
        (
            "activation_utc",
            internal.ACTIVATION_UTC.replace(tzinfo=None),
            "external_review_identity_mismatch",
        ),
        (
            "end_utc",
            internal.END_UTC.replace(tzinfo=None),
            "external_review_identity_mismatch",
        ),
        (
            "reviewed_at_utc",
            internal.END_UTC - timedelta(microseconds=1),
            "external_review_time_invalid",
        ),
        (
            "reviewed_at_utc",
            internal.END_UTC + timedelta(microseconds=1),
            "external_review_time_invalid",
        ),
        ("complete", False, "external_review_incomplete"),
        ("complete", 1, "external_review_incomplete"),
        ("complete", "true", "external_review_incomplete"),
        ("unresolved_findings", 1, "external_review_unresolved"),
        ("unresolved_findings", -1, "external_review_unresolved"),
        ("unresolved_findings", False, "external_review_unresolved"),
        ("unresolved_findings", 0.0, "external_review_unresolved"),
        ("unresolved_findings", "0", "external_review_unresolved"),
    ),
)
@pytest.mark.parametrize("index", range(5))
def test_each_external_category_fails_closed(index, field, value, reason) -> None:
    reviews = list(_reviews())
    reviews[index] = replace(reviews[index], **{field: value})
    _blocked(_build(reviews=tuple(reviews)), reason)


@pytest.mark.parametrize(
    "digest", (None, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n", 123)
)
def test_digest_is_exact_lowercase_hex(digest) -> None:
    reviews = _reviews()
    _blocked(
        _build(reviews=(replace(reviews[0], artifact_sha256=digest), *reviews[1:])),
        "external_review_artifact_invalid",
    )


@pytest.mark.parametrize("length", (0, -1, False, True, 1.0, "1", None))
def test_artifact_length_requires_positive_exact_int(length) -> None:
    reviews = _reviews()
    _blocked(
        _build(
            reviews=(replace(reviews[0], artifact_byte_length=length), *reviews[1:])
        ),
        "external_review_artifact_invalid",
    )


class DateTimeSubclass(datetime):
    pass


BAD_TIMES = (
    None,
    "2026-10-07T22:07:24Z",
    internal.END_UTC.replace(tzinfo=None),
    internal.END_UTC.astimezone(timezone(timedelta(hours=1))),
    internal.END_UTC.replace(tzinfo=timezone(timedelta(0), "alternate UTC")),
    DateTimeSubclass(2026, 10, 7, 22, 7, 24, tzinfo=UTC),
)


@pytest.mark.parametrize("at", BAD_TIMES)
def test_package_time_requires_exact_utc_datetime(at) -> None:
    _blocked(_build(at=at), "package_time_invalid")


@pytest.mark.parametrize("at", BAD_TIMES)
def test_review_time_requires_exact_utc_datetime(at) -> None:
    reviews = _reviews()
    _blocked(
        _build(reviews=(replace(reviews[0], reviewed_at_utc=at), *reviews[1:])),
        "external_review_time_invalid",
    )


def test_package_before_end_blocks() -> None:
    _blocked(
        _build(at=internal.END_UTC - timedelta(microseconds=1)),
        "package_window_not_complete",
    )


def test_later_review_at_exact_package_time_allowed() -> None:
    at = internal.END_UTC + timedelta(days=1)
    reviews = tuple(replace(item, reviewed_at_utc=at) for item in _reviews())
    assert _build(reviews=reviews, at=at)["status"] == "READY_FOR_OPERATOR_DECISION"


@pytest.mark.parametrize(
    "reviews", ((), _reviews()[:4], _reviews() + (_reviews()[0],), (_reviews()[0],) * 5)
)
def test_exact_complete_unique_category_set_required(reviews) -> None:
    _blocked(_build(reviews=reviews), "external_review_category_set_invalid")


@pytest.mark.parametrize("category", (CATEGORIES[0], "foreign", None, 1))
def test_category_requires_exact_enum(category) -> None:
    reviews = _reviews()
    _blocked(
        _build(reviews=(replace(reviews[0], category=category), *reviews[1:])),
        "external_review_category_set_invalid",
    )


@pytest.mark.parametrize("reviews", ([], {}, "reviews", (object(),)))
def test_review_input_requires_exact_tuple_and_evidence(reviews) -> None:
    _blocked(_build(reviews=reviews), "external_review_input_invalid")


def test_none_reviews_and_subclasses_block() -> None:
    class TupleSubclass(tuple):
        pass

    class EvidenceSubclass(package.D10ExternalReviewEvidence):
        pass

    class DictSubclass(dict):
        pass

    for reviews in (
        None,
        TupleSubclass(_reviews()),
        (
            EvidenceSubclass(
                **{
                    field.name: getattr(_reviews()[0], field.name)
                    for field in fields(_reviews()[0])
                }
            ),
            *_reviews()[1:],
        ),
    ):
        _blocked(
            package.build_package(
                _internal(), reviews, packaged_at_utc=internal.END_UTC
            ),
            "external_review_input_invalid",
        )
    for review in (None, [], DictSubclass(_internal())):
        _blocked(
            package.build_package(review, _reviews(), packaged_at_utc=internal.END_UTC),
            "internal_review_shape_invalid",
        )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("schema", "wrong", "internal_review_not_ready"),
        ("status", "BLOCKED", "internal_review_not_ready"),
        ("internal_wake_evidence", "BLOCKED", "internal_review_not_ready"),
        ("d10_accepted", True, "internal_review_not_ready"),
        ("d10_accepted", 0, "internal_review_not_ready"),
        ("broker_paper_authorized", True, "internal_review_not_ready"),
        ("broker_paper_authorized", 0, "internal_review_not_ready"),
        ("operator_decision_required", False, "internal_review_not_ready"),
        ("operator_decision_required", 1, "internal_review_not_ready"),
        ("minimum_daily_wake_count_met", False, "internal_review_not_ready"),
        ("minimum_daily_wake_count_met", 1, "internal_review_not_ready"),
        ("deployment_id", "foreign", "internal_review_identity_mismatch"),
        ("soak_id", "foreign", "internal_review_identity_mismatch"),
        ("attestation_sha256", "a" * 64, "internal_review_identity_mismatch"),
        ("external_review_required", CATEGORIES[::-1], "internal_review_shape_invalid"),
        ("external_review_required", list(CATEGORIES), "internal_review_shape_invalid"),
        (
            "external_review_required",
            CATEGORIES + ("extra",),
            "internal_review_shape_invalid",
        ),
        ("wake_count", 6, "internal_review_counts_invalid"),
        ("completed_count", 4, "internal_review_counts_invalid"),
        ("no_action_count", 2, "internal_review_counts_invalid"),
        ("stopped_count", 1, "internal_review_counts_invalid"),
        ("extra_wake_count", 0, "internal_review_counts_invalid"),
        ("certified_source_head", "", "internal_review_shape_invalid"),
        ("certified_source_tree", "", "internal_review_shape_invalid"),
        ("certified_source_head", 1, "internal_review_shape_invalid"),
        ("executable_file_count", 0, "internal_review_counts_invalid"),
        ("executable_file_count", -1, "internal_review_counts_invalid"),
        ("executable_file_count", True, "internal_review_counts_invalid"),
        ("executable_file_count", 1.0, "internal_review_counts_invalid"),
    ),
)
def test_internal_success_contract_fails_closed(field, value, reason) -> None:
    review = _internal()
    review[field] = value
    _blocked(_build(review), reason)


@pytest.mark.parametrize("field", package.COUNT_FIELDS)
@pytest.mark.parametrize("value", (-1, True, 0.0, "0", None))
def test_all_internal_counts_are_nonnegative_exact_ints(field, value) -> None:
    review = _internal()
    review[field] = value
    _blocked(_build(review), "internal_review_counts_invalid")


@pytest.mark.parametrize("field", package.INTERNAL_REVIEW_FIELDS)
def test_every_internal_field_is_required(field) -> None:
    review = _internal()
    del review[field]
    _blocked(_build(review), "internal_review_shape_invalid")


def test_extra_internal_fields_and_s2a_blocked_shape_are_rejected() -> None:
    review = _internal()
    review["account"] = object()
    _blocked(_build(review), "internal_review_shape_invalid")
    review = internal.analyze((), reviewed_at_utc=internal.END_UTC)
    _blocked(_build(review), "internal_review_shape_invalid")


@pytest.mark.parametrize(
    "field", ("first_observed_at_utc", "last_observed_at_utc", "reviewed_at_utc")
)
@pytest.mark.parametrize(
    "value",
    (
        None,
        internal.END_UTC,
        "bad",
        "2026-10-07T22:07:24Z",
        "2026-10-07T22:07:24.000000+00:00",
        "2026-99-07T22:07:24.000000Z",
    ),
)
def test_internal_timestamps_are_exact_canonical_s2a_strings(field, value) -> None:
    review = _internal()
    review[field] = value
    _blocked(_build(review), "internal_review_time_invalid")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("first_observed_at_utc", "2026-09-30T22:07:23.999999Z"),
        ("first_observed_at_utc", "2026-10-07T21:07:24.000001Z"),
        ("last_observed_at_utc", "2026-09-30T22:07:23.999999Z"),
        ("last_observed_at_utc", "2026-10-07T22:07:24.000000Z"),
        ("reviewed_at_utc", "2026-10-07T22:07:23.999999Z"),
        ("reviewed_at_utc", "2026-10-07T22:07:24.000001Z"),
    ),
)
def test_internal_times_are_in_window_and_ordered_before_package(field, value):
    review = _internal()
    review[field] = value
    _blocked(_build(review), "internal_review_time_invalid")
