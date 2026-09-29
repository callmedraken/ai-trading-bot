from __future__ import annotations

from dataclasses import fields, replace

import pytest

from scripts import d10_arch128_r4_replacement as r4


def _root(path: str, identity: r4.DeploymentIdentity | None) -> r4.RootObservation:
    return r4.RootObservation(path, identity is not None, identity)


def _absent(path: str) -> r4.RootObservation:
    return r4.RootObservation(path, False)


def _namespace(
    canonical: r4.RootObservation,
    staging: r4.RootObservation,
    retired: r4.RootObservation,
) -> r4.NamespaceObservation:
    return r4.NamespaceObservation(
        canonical,
        staging,
        retired,
        historical_s5r8_retired_absent=True,
        unexpected_reserved_names_absent=True,
    )


def _facts(**overrides: bool) -> r4.AdmissionFacts:
    values = {item.name: True for item in fields(r4.AdmissionFacts)}
    values.update(overrides)
    return r4.AdmissionFacts(**values)


def _post_facts(**overrides: bool) -> r4.PostRenameFacts:
    values = {item.name: True for item in fields(r4.PostRenameFacts)}
    values.update(overrides)
    return r4.PostRenameFacts(**values)


def test_fixed_arch128_paths_and_external_evidence_are_exact() -> None:
    assert r4.CANONICAL_PATH == r"F:\AITradingBot\D10"
    assert r4.STAGING_PATH == (
        r"F:\AITradingBot\D10.replacement-d2071f25-5a7c-5293-a28f-5b722c9917a2.installing"
    )
    assert r4.RETIRED_PATH == (
        r"F:\AITradingBot\D10.retired-9f3d111b-25bb-5ee4-9abf-f5215a32b826"
    )
    assert r4.NEW_EVIDENCE_ROOT == r4.STAGING_PATH + r"\evidence"
    assert r4.R1_MATERIAL_ROOT.startswith("F:\\AI\\temp\\")
    assert r4.R2_SIGNING_ROOT.startswith("F:\\AI\\temp\\")


def test_old_halted_incident_identity_is_frozen() -> None:
    assert r4.OLD_IDENTITY.deployment_id == r4.OLD_DEPLOYMENT_ID
    assert r4.OLD_IDENTITY.unsigned_attestation_sha256 == (
        "4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2"
    )
    assert r4.OLD_LEASE_SHA256 == (
        "91106d61129dc9c11e017a7ea613ba0fd82c87fd9debfc346b265c03c49a1e84"
    )
    assert r4.OLD_ACTIVATION_UTC == "2026-09-29T00:45:22.000000Z"
    assert r4.OLD_END_UTC == "2026-10-06T00:45:22.000000Z"
    assert r4.OLD_SOAK_ID == "48f14b13-aa18-5ce8-a0e0-402c867b17b6"


def test_new_signed_e6_identity_is_frozen() -> None:
    identity = r4.NEW_IDENTITY
    assert identity.deployment_id == "d2071f25-5a7c-5293-a28f-5b722c9917a2"
    assert identity.certified_source_head == "0f9551e13486ef65b35a5a9633da19081571144b"
    assert identity.certified_source_tree == "1186e92669af100542c055368c1b72495c36bc11"
    assert identity.manifest_sha256 == (
        "080c622035c7c8492a66ba5d5aa9a48c9020933fb16f85a7604010d529bd06e2"
    )
    assert identity.guard_sha256 == (
        "ab80233a6ce59a579653008609753441864f74592ac52d12ec65c6dc714eabf7"
    )
    assert identity.detached_signature_sha256 == (
        "9dbd3f44f259d338903a2ed2c52512992519f1f420a5825745cc81b677d104e9"
    )


@pytest.mark.parametrize(
    ("canonical", "staging", "retired", "expected"),
    [
        (
            _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
            _absent(r4.STAGING_PATH),
            _absent(r4.RETIRED_PATH),
            r4.NamespaceState.PRE_STAGE,
        ),
        (
            _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
            _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
            _absent(r4.RETIRED_PATH),
            r4.NamespaceState.READY,
        ),
        (
            _absent(r4.CANONICAL_PATH),
            _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
            _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
            r4.NamespaceState.RETIRED_WINDOW,
        ),
        (
            _root(r4.CANONICAL_PATH, r4.NEW_IDENTITY),
            _absent(r4.STAGING_PATH),
            _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
            r4.NamespaceState.COMPLETE,
        ),
    ],
)
def test_namespace_classifier_accepts_only_four_exact_states(
    canonical: r4.RootObservation,
    staging: r4.RootObservation,
    retired: r4.RootObservation,
    expected: r4.NamespaceState,
) -> None:
    assert r4.classify_namespace(_namespace(canonical, staging, retired)) is expected


def test_namespace_classifier_rejects_historical_retired_presence() -> None:
    observation = replace(
        _namespace(
            _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
            _absent(r4.STAGING_PATH),
            _absent(r4.RETIRED_PATH),
        ),
        historical_s5r8_retired_absent=False,
    )
    assert r4.classify_namespace(observation) is r4.NamespaceState.CONFLICTING


def test_namespace_classifier_rejects_identity_or_reserved_name_drift() -> None:
    wrong = replace(r4.NEW_IDENTITY, guard_byte_length=1)
    observation = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, wrong),
        _absent(r4.RETIRED_PATH),
    )
    assert r4.classify_namespace(observation) is r4.NamespaceState.CONFLICTING

    observation = replace(
        _namespace(
            _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
            _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
            _absent(r4.RETIRED_PATH),
        ),
        unexpected_reserved_names_absent=False,
    )
    assert r4.classify_namespace(observation) is r4.NamespaceState.CONFLICTING


@pytest.mark.parametrize(
    "field",
    [item.name for item in fields(r4.AdmissionFacts)],
)
def test_every_admission_fact_is_required(field: str) -> None:
    facts = _facts(**{field: False})
    assert facts.all_exact() is False


def test_begin_requires_ready_namespace_and_all_exact_facts() -> None:
    ready = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
        _absent(r4.RETIRED_PATH),
    )
    result = r4.begin_replacement(ready, _facts())
    assert result.phase is r4.Phase.READY_TO_RETIRE_OLD

    with pytest.raises(ValueError):
        r4.begin_replacement(
            _namespace(
                _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
                _absent(r4.STAGING_PATH),
                _absent(r4.RETIRED_PATH),
            ),
            _facts(),
        )
    with pytest.raises(ValueError):
        r4.begin_replacement(ready, _facts(old_final_lease_exact=False))


def test_happy_path_requires_read_only_verification_after_each_success() -> None:
    ready = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
        _absent(r4.RETIRED_PATH),
    )
    result = r4.begin_replacement(ready, _facts())
    result = r4.record_rename(
        result,
        r4.RenameStep.OLD_TO_RETIRED,
        r4.MutationOutcome.SUCCESS,
    )
    assert result.phase is r4.Phase.VERIFY_RETIRED_WINDOW

    with pytest.raises(ValueError):
        r4.record_rename(
            result,
            r4.RenameStep.STAGING_TO_CANONICAL,
            r4.MutationOutcome.SUCCESS,
        )

    result = r4.confirm_retired_window(
        result,
        _namespace(
            _absent(r4.CANONICAL_PATH),
            _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
            _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
        ),
        _post_facts(),
    )
    assert result.phase is r4.Phase.READY_TO_PUBLISH_NEW

    result = r4.record_rename(
        result,
        r4.RenameStep.STAGING_TO_CANONICAL,
        r4.MutationOutcome.SUCCESS,
    )
    assert result.phase is r4.Phase.VERIFY_COMPLETE

    result = r4.confirm_complete(
        result,
        _namespace(
            _root(r4.CANONICAL_PATH, r4.NEW_IDENTITY),
            _absent(r4.STAGING_PATH),
            _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
        ),
        _post_facts(),
    )
    assert result == r4.ReplacementResult(
        r4.Phase.COMPLETE,
        r4.MutationOutcome.SUCCESS,
        r4.MutationOutcome.SUCCESS,
    )


@pytest.mark.parametrize(
    "outcome",
    [r4.MutationOutcome.NOT_CALLED, r4.MutationOutcome.INDETERMINATE],
)
def test_first_step_non_success_latches_terminal_stop(
    outcome: r4.MutationOutcome,
) -> None:
    ready = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
        _absent(r4.RETIRED_PATH),
    )
    result = r4.record_rename(
        r4.begin_replacement(ready, _facts()),
        r4.RenameStep.OLD_TO_RETIRED,
        outcome,
    )
    assert result.phase is r4.Phase.STOPPED_INDETERMINATE
    with pytest.raises(ValueError):
        r4.record_rename(
            result,
            r4.RenameStep.OLD_TO_RETIRED,
            r4.MutationOutcome.SUCCESS,
        )


@pytest.mark.parametrize(
    "outcome",
    [r4.MutationOutcome.NOT_CALLED, r4.MutationOutcome.INDETERMINATE],
)
def test_second_step_non_success_latches_terminal_stop(
    outcome: r4.MutationOutcome,
) -> None:
    ready = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
        _absent(r4.RETIRED_PATH),
    )
    first = r4.record_rename(
        r4.begin_replacement(ready, _facts()),
        r4.RenameStep.OLD_TO_RETIRED,
        r4.MutationOutcome.SUCCESS,
    )
    first = r4.confirm_retired_window(
        first,
        _namespace(
            _absent(r4.CANONICAL_PATH),
            _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
            _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
        ),
        _post_facts(),
    )
    result = r4.record_rename(
        first,
        r4.RenameStep.STAGING_TO_CANONICAL,
        outcome,
    )
    assert result.phase is r4.Phase.STOPPED_INDETERMINATE
    with pytest.raises(ValueError):
        r4.record_rename(
            result,
            r4.RenameStep.STAGING_TO_CANONICAL,
            r4.MutationOutcome.SUCCESS,
        )


def test_rename_order_and_paths_are_fixed() -> None:
    assert r4.fixed_rename_paths(r4.RenameStep.OLD_TO_RETIRED) == (
        r4.CANONICAL_PATH,
        r4.RETIRED_PATH,
    )
    assert r4.fixed_rename_paths(r4.RenameStep.STAGING_TO_CANONICAL) == (
        r4.STAGING_PATH,
        r4.CANONICAL_PATH,
    )


@pytest.mark.parametrize(
    "field",
    [item.name for item in fields(r4.PostRenameFacts)],
)
def test_every_post_rename_fact_is_required(field: str) -> None:
    assert _post_facts(**{field: False}).all_exact() is False


def test_retired_window_verification_rejects_wrong_namespace_or_facts() -> None:
    ready = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
        _absent(r4.RETIRED_PATH),
    )
    result = r4.record_rename(
        r4.begin_replacement(ready, _facts()),
        r4.RenameStep.OLD_TO_RETIRED,
        r4.MutationOutcome.SUCCESS,
    )

    with pytest.raises(ValueError):
        r4.confirm_retired_window(result, ready, _post_facts())

    with pytest.raises(ValueError):
        r4.confirm_retired_window(
            result,
            _namespace(
                _absent(r4.CANONICAL_PATH),
                _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
                _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
            ),
            _post_facts(old_final_lease_exact=False),
        )


def test_completion_verification_rejects_wrong_namespace_or_facts() -> None:
    ready = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
        _absent(r4.RETIRED_PATH),
    )
    result = r4.record_rename(
        r4.begin_replacement(ready, _facts()),
        r4.RenameStep.OLD_TO_RETIRED,
        r4.MutationOutcome.SUCCESS,
    )
    result = r4.confirm_retired_window(
        result,
        _namespace(
            _absent(r4.CANONICAL_PATH),
            _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
            _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
        ),
        _post_facts(),
    )
    result = r4.record_rename(
        result,
        r4.RenameStep.STAGING_TO_CANONICAL,
        r4.MutationOutcome.SUCCESS,
    )

    with pytest.raises(ValueError):
        r4.confirm_complete(
            result,
            _namespace(
                _absent(r4.CANONICAL_PATH),
                _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
                _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
            ),
            _post_facts(),
        )

    with pytest.raises(ValueError):
        r4.confirm_complete(
            result,
            _namespace(
                _root(r4.CANONICAL_PATH, r4.NEW_IDENTITY),
                _absent(r4.STAGING_PATH),
                _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
            ),
            _post_facts(new_evidence_root_exact_empty=False),
        )


def test_post_rename_verification_failure_latches_terminal_stop() -> None:
    ready = _namespace(
        _root(r4.CANONICAL_PATH, r4.OLD_IDENTITY),
        _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
        _absent(r4.RETIRED_PATH),
    )
    first = r4.record_rename(
        r4.begin_replacement(ready, _facts()),
        r4.RenameStep.OLD_TO_RETIRED,
        r4.MutationOutcome.SUCCESS,
    )
    stopped = r4.fail_post_rename_verification(first)
    assert stopped == r4.ReplacementResult(
        r4.Phase.STOPPED_INDETERMINATE,
        r4.MutationOutcome.SUCCESS,
        r4.MutationOutcome.NOT_CALLED,
    )

    with pytest.raises(ValueError):
        r4.confirm_retired_window(
            stopped,
            _namespace(
                _absent(r4.CANONICAL_PATH),
                _root(r4.STAGING_PATH, r4.NEW_IDENTITY),
                _root(r4.RETIRED_PATH, r4.OLD_IDENTITY),
            ),
            _post_facts(),
        )
