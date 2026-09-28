"""Focused source-only tests for Architecture-125 replacement state logic."""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import replace

import pytest

from scripts import d10_protected_replacement as r


def _root(path: str, state: str) -> r.RootObservation:
    if state == "ABSENT":
        return r.RootObservation(path, False)
    identity = r.OLD_IDENTITY if state == "OLD" else r.NEW_IDENTITY
    return r.RootObservation(path, True, identity)


def _namespace(canonical: str, staging: str, retired: str) -> r.NamespaceObservation:
    return r.NamespaceObservation(
        _root(r.CANONICAL_PATH, canonical),
        _root(r.STAGING_PATH, staging),
        _root(r.RETIRED_PATH, retired),
        unexpected_reserved_names_absent=True,
    )


def _admission() -> r.AdmissionFacts:
    return r.AdmissionFacts(*(True for _ in range(11)))


def _post_publication() -> r.PostPublicationFacts:
    return r.PostPublicationFacts(*(True for _ in range(9)))


def _ready() -> r.ReplacementResult:
    return r.begin_replacement(_namespace("OLD", "NEW", "ABSENT"), _admission())


def _published() -> r.ReplacementResult:
    retired = r.record_rename(
        _ready(), r.RenameStep.OLD_TO_RETIRED, r.MutationOutcome.SUCCESS
    )
    return r.record_rename(
        retired, r.RenameStep.STAGING_TO_CANONICAL, r.MutationOutcome.SUCCESS
    )


def test_frozen_old_and_new_identity_and_paths() -> None:
    assert r.OLD_IDENTITY == r.DeploymentIdentity(
        "2fd79986-fb50-5fe4-800a-2d4aa5e7307c",
        "e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a",
        306,
        5391245,
        68411,
        "3b28d0ffeede06a4785a903dbf6a48c12204651ce8a3c2f80cd6a1428efd8d1a",
        "a12ab7788120934ca928919a01b4cfc7a3f6f307fad79ab13a6bfff189aeb3f3",
        "7ae83e28bcd8ab7cb59ab990a7f3b3191f485621aa83f5431f7f25fc32c8b4eb",
    )
    assert r.NEW_IDENTITY == r.DeploymentIdentity(
        "9f3d111b-25bb-5ee4-9abf-f5215a32b826",
        "e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a",
        306,
        5391245,
        69259,
        "37d78c65800a315a12049b6c278addf609589d121e15d31dd9064dc8ec427298",
        "4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2",
        None,
        "c5cc0b01301600daf17f1114f4451dca2c9d7a1f",
        "bfacfadaa14315d2d378abcc0f1e4bc7c42034f1",
        "19c585519daefad917d6326b5180177b63f8e7f0",
        "ab0dccdea1e0e6646ba3b68b3afb725a553f68cc",
    )
    assert r.PARENT_PATH == r"F:\AITradingBot"
    assert r.CANONICAL_PATH == r"F:\AITradingBot\D10"
    assert r.STAGING_PATH == (
        r"F:\AITradingBot\D10.replacement-9f3d111b-25bb-5ee4-9abf-f5215a32b826.installing"
    )
    assert (
        r.RETIRED_PATH
        == r"F:\AITradingBot\D10.retired-2fd79986-fb50-5fe4-800a-2d4aa5e7307c"
    )


def test_complete_exact_namespace_classification_matrix() -> None:
    accepted = {
        ("OLD", "ABSENT", "ABSENT"): r.NamespaceState.CLEAN_INITIAL,
        ("OLD", "NEW", "ABSENT"): r.NamespaceState.OLD_CANONICAL,
        ("ABSENT", "NEW", "OLD"): r.NamespaceState.OLD_RETIRED,
        ("NEW", "ABSENT", "OLD"): r.NamespaceState.NEW_CANONICAL,
    }
    for triple in itertools.product(("ABSENT", "OLD", "NEW"), repeat=3):
        assert r.classify_namespace(_namespace(*triple)) is accepted.get(
            triple, r.NamespaceState.CONFLICTING
        )


@pytest.mark.parametrize("field", ["canonical", "staging", "retired"])
def test_wrong_paths_and_identity_facts_conflict(field: str) -> None:
    observation = _namespace("OLD", "NEW", "ABSENT")
    root = getattr(observation, field)
    changed_path = replace(observation, **{field: replace(root, path=r"F:\Other\D10")})
    assert r.classify_namespace(changed_path) is r.NamespaceState.CONFLICTING
    if field != "retired":
        wrong = replace(
            observation,
            **{
                field: replace(
                    root, identity=replace(root.identity, guard_sha256="0" * 64)
                )
            },
        )
        assert r.classify_namespace(wrong) is r.NamespaceState.CONFLICTING


def test_partial_and_indeterminate_observations_conflict() -> None:
    observation = _namespace("OLD", "NEW", "ABSENT")
    assert (
        r.classify_namespace(
            replace(observation, canonical=r.RootObservation(r.CANONICAL_PATH, None))
        )
        is r.NamespaceState.CONFLICTING
    )
    assert (
        r.classify_namespace(
            replace(observation, staging=r.RootObservation(r.STAGING_PATH, True))
        )
        is r.NamespaceState.CONFLICTING
    )
    assert (
        r.classify_namespace(
            replace(
                observation,
                retired=r.RootObservation(r.RETIRED_PATH, False, r.OLD_IDENTITY),
            )
        )
        is r.NamespaceState.CONFLICTING
    )
    assert r.classify_namespace(None) is r.NamespaceState.CONFLICTING
    assert (
        r.classify_namespace(
            replace(observation, unexpected_reserved_names_absent=False)
        )
        is r.NamespaceState.CONFLICTING
    )
    wrong_numeric_type = replace(
        observation,
        canonical=r.RootObservation(
            r.CANONICAL_PATH,
            True,
            replace(r.OLD_IDENTITY, executable_file_count=306.0),
        ),
    )
    assert r.classify_namespace(wrong_numeric_type) is r.NamespaceState.CONFLICTING


def test_admission_requires_fresh_exact_staging_scheduler_and_closed_authority() -> (
    None
):
    assert _ready().next_rename is r.RenameStep.OLD_TO_RETIRED
    initial = r.begin_replacement(_namespace("OLD", "ABSENT", "ABSENT"), _admission())
    assert initial.phase is r.Phase.BLOCKED
    assert initial.reason_code is r.BlockReason.ADMISSION_FAILED
    for field in r.AdmissionFacts.__dataclass_fields__:
        denied = r.begin_replacement(
            _namespace("OLD", "NEW", "ABSENT"), replace(_admission(), **{field: False})
        )
        assert denied.phase is r.Phase.BLOCKED
        assert denied.next_rename is None


@pytest.mark.parametrize(
    "state",
    [
        ("ABSENT", "NEW", "OLD"),
        ("NEW", "ABSENT", "OLD"),
    ],
)
def test_prior_interrupted_states_require_separate_recovery(
    state: tuple[str, str, str],
) -> None:
    result = r.begin_replacement(_namespace(*state), _admission())
    assert result.reason_code is r.BlockReason.SEPARATE_RECOVERY_REQUIRED
    assert result.next_rename is None


def test_rename_order_and_indeterminate_result_never_authorize_retry() -> None:
    ready = _ready()
    assert ready.rename_plan == r.RenamePlan(
        r.RenameStep.OLD_TO_RETIRED, r.CANONICAL_PATH, r.RETIRED_PATH
    )
    assert ready.rename_plan.destination_must_be_absent is True
    assert ready.rename_plan.replace_existing is False
    premature = r.record_rename(
        ready, r.RenameStep.STAGING_TO_CANONICAL, r.MutationOutcome.SUCCESS
    )
    assert premature.phase is r.Phase.BLOCKED
    assert premature.next_rename is None
    uncertain_old = r.record_rename(
        ready, r.RenameStep.OLD_TO_RETIRED, r.MutationOutcome.INDETERMINATE
    )
    assert (
        uncertain_old.highest_definitely_completed_state
        is r.NamespaceState.OLD_CANONICAL
    )
    assert uncertain_old.completed_renames == ()
    assert uncertain_old.next_rename is None
    retired = r.record_rename(
        ready, r.RenameStep.OLD_TO_RETIRED, r.MutationOutcome.SUCCESS
    )
    assert retired.completed_renames == (r.RenameStep.OLD_TO_RETIRED,)
    assert retired.next_rename is r.RenameStep.STAGING_TO_CANONICAL
    assert retired.rename_plan == r.RenamePlan(
        r.RenameStep.STAGING_TO_CANONICAL, r.STAGING_PATH, r.CANONICAL_PATH
    )
    uncertain_new = r.record_rename(
        retired, r.RenameStep.STAGING_TO_CANONICAL, r.MutationOutcome.INDETERMINATE
    )
    assert (
        uncertain_new.highest_definitely_completed_state is r.NamespaceState.OLD_RETIRED
    )
    assert uncertain_new.completed_renames == (r.RenameStep.OLD_TO_RETIRED,)
    assert uncertain_new.next_rename is None
    assert uncertain_new.rename_plan is None
    assert (
        r.record_rename(
            uncertain_new, r.RenameStep.STAGING_TO_CANONICAL, r.MutationOutcome.SUCCESS
        ).next_rename
        is None
    )


def test_pass_needs_post_publication_reverification_and_has_no_rollback() -> None:
    published = _published()
    assert published.phase is r.Phase.VERIFY_PUBLICATION
    assert published.next_rename is None
    failed = r.verify_publication(
        published,
        _namespace("NEW", "ABSENT", "OLD"),
        replace(_post_publication(), canonical_trust_absent=False),
    )
    assert failed.phase is r.Phase.BLOCKED
    assert failed.highest_definitely_completed_state is r.NamespaceState.NEW_CANONICAL
    assert failed.completed_renames == (
        r.RenameStep.OLD_TO_RETIRED,
        r.RenameStep.STAGING_TO_CANONICAL,
    )
    assert failed.next_rename is None
    passed = r.verify_publication(
        published, _namespace("NEW", "ABSENT", "OLD"), _post_publication()
    )
    assert passed.phase is r.Phase.PASS
    assert passed.highest_definitely_completed_state is r.NamespaceState.NEW_CANONICAL
    assert passed.next_rename is None
    assert passed.rename_plan is None
    assert set(r.RenameStep) == {
        r.RenameStep.OLD_TO_RETIRED,
        r.RenameStep.STAGING_TO_CANONICAL,
    }


def test_transcripts_are_canonical_deterministic_sanitized_and_inert() -> None:
    passed = r.verify_publication(
        _published(), _namespace("NEW", "ABSENT", "OLD"), _post_publication()
    )
    transcript = passed.canonical_transcript()
    assert transcript == passed.canonical_transcript()
    assert transcript.endswith(b"\n")
    assert (
        transcript
        == (
            json.dumps(json.loads(transcript), sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
    )
    payload = json.loads(transcript)
    assert payload["completed_renames"] == ["OLD_TO_RETIRED", "STAGING_TO_CANONICAL"]
    assert payload["canonical_trust_disposition"] == "ABSENT"
    assert payload["activation_lease_disposition"] == "ABSENT"
    assert payload["retired_tree_verification"] == "PASS"
    for key in (
        "activation_authority",
        "scheduler_authority",
        "trading_authority",
        "retirement_cleanup_authority",
    ):
        assert payload[key] == "NONE"
    assert passed.retirement_cleanup_authority == "NONE"
    secret = "SENSITIVE-RAW-HOST-DATA"
    conflicting = r.begin_replacement(
        replace(
            _namespace("OLD", "NEW", "ABSENT"),
            staging=r.RootObservation(secret, True, r.NEW_IDENTITY),
        ),
        _admission(),
    )
    blocked = conflicting.canonical_transcript()
    assert secret.encode() not in blocked
    assert json.loads(blocked)["reason_code"] == "NAMESPACE_CONFLICT"
    assert b'activation_authority":"NONE' in blocked


def test_replacement_pass_is_distinct_from_signed_trust_and_retirement_cleanup() -> (
    None
):
    passed = r.verify_publication(
        _published(), _namespace("NEW", "ABSENT", "OLD"), _post_publication()
    )
    payload = json.loads(passed.canonical_transcript())
    assert payload["canonical_trust_disposition"] == "ABSENT"
    assert payload["retirement_cleanup_authority"] == "NONE"
    assert payload["retired_path"] == r.RETIRED_PATH
    assert "retirement_cleanup_pass" not in payload


def test_intermediate_and_forged_result_cannot_claim_pass() -> None:
    with pytest.raises(ValueError):
        _ready().canonical_transcript()
    with pytest.raises(ValueError):
        r.ReplacementResult(r.Phase.PASS, r.NamespaceState.NEW_CANONICAL)
    with pytest.raises(ValueError):
        r.RenamePlan(r.RenameStep.OLD_TO_RETIRED, r"F:\Other\D10", r.RETIRED_PATH)
    with pytest.raises(ValueError):
        r.RenamePlan(
            r.RenameStep.STAGING_TO_CANONICAL,
            r.STAGING_PATH,
            r.CANONICAL_PATH,
            replace_existing=True,
        )


@pytest.mark.parametrize(
    "state",
    [
        r.NamespaceState.CLEAN_INITIAL,
        r.NamespaceState.OLD_CANONICAL,
        r.NamespaceState.CONFLICTING,
    ],
)
def test_staging_failure_transcript_keeps_exact_highest_state(
    state: r.NamespaceState,
) -> None:
    blocked = r.ReplacementResult(
        r.Phase.BLOCKED, state, reason_code=r.BlockReason.STAGING_FAILED
    )
    payload = json.loads(blocked.canonical_transcript())
    assert payload["reason_code"] == "STAGING_FAILED"
    assert payload["highest_definitely_completed_namespace_state"] == state.value


@pytest.mark.parametrize("step", list(r.RenameStep))
@pytest.mark.parametrize("stage", list(r.RenameFailureStage))
def test_diagnostic_is_bounded_frozen_and_grants_no_transition(
    step: r.RenameStep,
    stage: r.RenameFailureStage,
) -> None:
    from dataclasses import FrozenInstanceError

    diagnostic = r.RenameDiagnostic(
        step, stage, 5 if stage is r.RenameFailureStage.NATIVE_FALSE else None
    )
    ready = _ready()
    if step is r.RenameStep.STAGING_TO_CANONICAL:
        ready = r.record_rename(
            ready, r.RenameStep.OLD_TO_RETIRED, r.MutationOutcome.SUCCESS
        )
    blocked = r.record_rename(ready, step, r.MutationOutcome.INDETERMINATE, diagnostic)
    assert blocked.rename_diagnostic is diagnostic
    assert blocked.next_rename is None and blocked.rename_plan is None
    assert r.record_rename(blocked, step, r.MutationOutcome.SUCCESS).next_rename is None
    payload = json.loads(blocked.canonical_transcript())
    assert payload["rename_diagnostic"] == {
        "stage": stage.value,
        "step": step.value,
        "win32_error": diagnostic.win32_error,
    }
    assert blocked.canonical_transcript() == blocked.canonical_transcript()
    assert blocked.canonical_transcript() == (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("ascii")
    assert set(diagnostic.__dataclass_fields__) == {"step", "stage", "win32_error"}
    with pytest.raises(FrozenInstanceError):
        diagnostic.win32_error = 42
    for key in (
        "activation_authority",
        "scheduler_authority",
        "trading_authority",
        "retirement_cleanup_authority",
    ):
        assert payload[key] == "NONE"


@pytest.mark.parametrize("error", [0, 0xFFFFFFFF])
def test_native_false_diagnostic_uint32_endpoints(error: int) -> None:
    assert (
        r.RenameDiagnostic(
            r.RenameStep.OLD_TO_RETIRED, r.RenameFailureStage.NATIVE_FALSE, error
        ).win32_error
        == error
    )


@pytest.mark.parametrize(
    "error", [-1, 0x100000000, True, False, 0.0, "5", None, object()]
)
def test_native_false_rejects_non_uint32_error(error: object) -> None:
    with pytest.raises(ValueError):
        r.RenameDiagnostic(
            r.RenameStep.OLD_TO_RETIRED, r.RenameFailureStage.NATIVE_FALSE, error
        )


@pytest.mark.parametrize(
    "stage",
    [
        stage
        for stage in r.RenameFailureStage
        if stage is not r.RenameFailureStage.NATIVE_FALSE
    ],
)
@pytest.mark.parametrize("error", [0, 5, "private host data", False])
def test_other_diagnostic_stages_reject_error_data(
    stage: r.RenameFailureStage, error: object
) -> None:
    with pytest.raises(ValueError):
        r.RenameDiagnostic(r.RenameStep.OLD_TO_RETIRED, stage, error)


@pytest.mark.parametrize(
    "step,stage",
    [
        ("OLD_TO_RETIRED", r.RenameFailureStage.PRE_CALL),
        (r.RenameStep.OLD_TO_RETIRED, "PRE_CALL"),
        (r.RenameStep.OLD_TO_RETIRED, "raw exception"),
        (object(), r.RenameFailureStage.PRE_CALL),
    ],
)
def test_diagnostic_rejects_unclosed_or_caller_supplied_values(
    step: object, stage: object
) -> None:
    with pytest.raises(ValueError):
        r.RenameDiagnostic(step, stage)


def test_diagnostic_cannot_accompany_success_other_reason_or_wrong_step() -> None:
    diagnostic = r.RenameDiagnostic(
        r.RenameStep.OLD_TO_RETIRED, r.RenameFailureStage.PRE_CALL
    )
    with pytest.raises(ValueError):
        r.record_rename(
            _ready(), diagnostic.step, r.MutationOutcome.SUCCESS, diagnostic
        )
    with pytest.raises(ValueError):
        r.record_rename(
            _ready(),
            r.RenameStep.STAGING_TO_CANONICAL,
            r.MutationOutcome.INDETERMINATE,
            diagnostic,
        )
    with pytest.raises(ValueError):
        replace(_ready(), rename_diagnostic=diagnostic)
    with pytest.raises(ValueError):
        r.ReplacementResult(
            r.Phase.BLOCKED,
            r.NamespaceState.OLD_CANONICAL,
            reason_code=r.BlockReason.SEPARATE_RECOVERY_REQUIRED,
            rename_diagnostic=diagnostic,
        )
    with pytest.raises(ValueError):
        r.ReplacementResult(
            r.Phase.BLOCKED,
            r.NamespaceState.OLD_RETIRED,
            (r.RenameStep.OLD_TO_RETIRED,),
            r.BlockReason.INDETERMINATE_MUTATION,
            diagnostic,
        )
    with pytest.raises(ValueError):
        r.ReplacementResult(
            r.Phase.BLOCKED,
            r.NamespaceState.OLD_CANONICAL,
            reason_code=r.BlockReason.INDETERMINATE_MUTATION,
            rename_diagnostic={"path": "private"},
        )
    passed = r.verify_publication(
        _published(), _namespace("NEW", "ABSENT", "OLD"), _post_publication()
    )
    with pytest.raises(ValueError):
        replace(passed, rename_diagnostic=diagnostic)


def test_closed_failure_stage_model_is_exact() -> None:
    assert {stage.value for stage in r.RenameFailureStage} == {
        "PRE_CALL",
        "NATIVE_FALSE",
        "POST_CALL_VERIFY",
        "CLOSE_AMBIGUITY",
    }


def test_ordinary_old_canonical_recovery_block_is_valid_and_inert() -> None:
    result = r.ReplacementResult(
        r.Phase.BLOCKED,
        r.NamespaceState.OLD_CANONICAL,
        reason_code=r.BlockReason.SEPARATE_RECOVERY_REQUIRED,
    )
    assert result.next_rename is None and result.completed_renames == ()


def test_legacy_transcripts_without_diagnostic_are_byte_identical() -> None:
    first = r.record_rename(
        _ready(), r.RenameStep.OLD_TO_RETIRED, r.MutationOutcome.INDETERMINATE
    )
    retired = r.record_rename(
        _ready(), r.RenameStep.OLD_TO_RETIRED, r.MutationOutcome.SUCCESS
    )
    second = r.record_rename(
        retired, r.RenameStep.STAGING_TO_CANONICAL, r.MutationOutcome.INDETERMINATE
    )
    passed = r.verify_publication(
        _published(), _namespace("NEW", "ABSENT", "OLD"), _post_publication()
    )
    # Frozen SHA-256 of the exact pre-R1G terminal transcript bytes.
    for result, digest in (
        (first, "ee575d6ee583dac294d94b0cb3830e5e1eb41c229bbaac6e502b5d8a625677ef"),
        (second, "7afe18feb87e96e126499f6174cdb24ef7f10cc4c456a203cf2ba430e9fcbb99"),
        (passed, "dc1f3890f2f52236719bf1e75055eebc20b82abe15dd35876ae2a42ae40cf843"),
    ):
        assert result.rename_diagnostic is None
        assert b"rename_diagnostic" not in result.canonical_transcript()
        assert hashlib.sha256(result.canonical_transcript()).hexdigest() == digest
