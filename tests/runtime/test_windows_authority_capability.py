from __future__ import annotations

import inspect
import pickle
from dataclasses import replace

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    BootstrapVerification,
    WindowsAuthorityBootstrap,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    ProductionAuthorityEvidence,
)
from trading_bot.runtime.windows_authority_sqlite import SqliteDatabaseState
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    ProvisioningEvidence,
    ProvisioningState,
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
    acquire_validated_production_authority_for_test,
    require_validated_production_authority,
)


def _bootstrap() -> WindowsAuthorityBootstrap:
    return WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=7,
        machine_authority_id="11111111-1111-4111-8111-111111111111",
        authority_epoch_id="22222222-2222-4222-8222-222222222222",
        signing_key_id="test-key",
        approved_account_sid="S-1-5-21-1",
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="ab" * 32,
    )


def _production_evidence(
    *,
    database_path: str | None = None,
    release_digest: str = "11" * 32,
    sqlite_digest: str = "22" * 32,
) -> ProductionAuthorityEvidence:
    return ProductionAuthorityEvidence(
        database_path=database_path or str(PRODUCTION_AUTHORITY_PATHS.database),
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="33" * 32,
        migration_id="migration-v1",
        release_manifest_digest=release_digest,
        sqlite_build_manifest_digest=sqlite_digest,
    )


def _validation(
    *,
    state: str = SqliteDatabaseState.INITIALIZED_SUPPORTED.value,
    evidence: ProductionAuthorityEvidence | None = None,
    capability: ValidatedProductionAuthority | None = None,
    issue_capability: bool = True,
) -> InstalledAuthorityValidation:
    bootstrap = _bootstrap()
    verification = BootstrapVerification(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        signing_key_id=bootstrap.signing_key_id,
        signature_length=64,
    )
    production = evidence
    issued = capability
    if (
        issue_capability
        and state == SqliteDatabaseState.INITIALIZED_SUPPORTED.value
        and production is None
    ):
        production = _production_evidence()
    if issue_capability and issued is None and production is not None:
        issued = acquire_validated_production_authority_for_test(
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap.digest,
            production_evidence=production,
        )
    return InstalledAuthorityValidation(
        provisioning=ProvisioningEvidence(
            state=ProvisioningState.VALIDATED,
            authority_root=str(PRODUCTION_AUTHORITY_PATHS.root),
            bootstrap_digest=bootstrap.digest,
            signing_key_id=bootstrap.signing_key_id,
            trading_sid=bootstrap.approved_account_sid,
            inspected_objects=("root", "bootstrap", "signature"),
            database_present=state != SqliteDatabaseState.NOT_PRESENT.value,
            journal_present=state != SqliteDatabaseState.NOT_PRESENT.value,
            database_state=state,
        ),
        bootstrap_verification=verification,
        production_evidence=production,
        validated_production_authority=issued,
    )


def _production_validation() -> InstalledAuthorityValidation:
    """Build a production-provenance fixture through the private issuer seam."""

    import trading_bot.runtime.windows_authority_validation as validation

    bootstrap = _bootstrap()
    evidence = _production_evidence()
    capability = validation._validate_exact_identity(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        trading_sid=bootstrap.approved_account_sid,
        production=evidence,
        require_fixed_database_path=True,
        issuer=validation._PRODUCTION_CAPABILITY_ISSUER,
    )
    return _validation(evidence=evidence, capability=capability)


@pytest.mark.parametrize(
    "state",
    [
        SqliteDatabaseState.NOT_PRESENT.value,
        SqliteDatabaseState.PRECREATED_UNINITIALIZED.value,
        SqliteDatabaseState.INITIALIZED_UNSUPPORTED.value,
    ],
)
def test_production_acquisition_rejects_non_supported_states(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    monkeypatch.setattr(
        validation,
        "validate_installed_authority_complete",
        lambda: _validation(state=state),
    )

    with pytest.raises(WindowsAuthorityError):
        acquire_validated_production_authority()


def test_production_acquisition_rejects_missing_complete_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    monkeypatch.setattr(
        validation,
        "validate_installed_authority_complete",
        lambda: _validation(
            state=SqliteDatabaseState.INITIALIZED_SUPPORTED.value,
            evidence=None,
            capability=None,
            issue_capability=False,
        ),
    )
    result = _validation(
        state=SqliteDatabaseState.INITIALIZED_SUPPORTED.value,
        evidence=None,
        capability=None,
        issue_capability=False,
    )
    assert result.validated_production_authority is None
    with pytest.raises(WindowsAuthorityError):
        acquire_validated_production_authority()


def test_exact_supported_validation_issues_one_immutable_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    reviewed = _production_validation()
    monkeypatch.setattr(
        validation, "validate_installed_authority_complete", lambda: reviewed
    )

    capability = acquire_validated_production_authority()

    assert type(capability) is ValidatedProductionAuthority
    assert (
        capability.authority_epoch_id
        == reviewed.bootstrap_verification.bootstrap.authority_epoch_id
    )
    assert (
        capability.machine_authority_id
        == reviewed.bootstrap_verification.bootstrap.machine_authority_id
    )
    assert (
        capability.bootstrap_digest == reviewed.bootstrap_verification.bootstrap_digest
    )
    assert capability.schema_id == reviewed.production_evidence.schema_id  # type: ignore[union-attr]
    assert capability.metadata_digest == reviewed.production_evidence.metadata_digest  # type: ignore[union-attr]
    assert capability.migration_id == reviewed.production_evidence.migration_id  # type: ignore[union-attr]
    with pytest.raises(AttributeError):
        capability.authority_epoch_id = "substituted"  # type: ignore[misc]
    with pytest.raises(TypeError):
        pickle.dumps(capability)


def test_test_capability_has_test_provenance_and_cannot_cross_production_boundary() -> (
    None
):
    import trading_bot.runtime.windows_authority_validation as validation

    test_capability = _validation().validated_production_authority
    production_capability = _production_validation().validated_production_authority
    assert test_capability is not None
    assert production_capability is not None
    assert test_capability._provenance is validation._TEST_CAPABILITY_ISSUER
    assert production_capability._provenance is validation._PRODUCTION_CAPABILITY_ISSUER
    assert test_capability != production_capability
    assert hash(test_capability) != hash(production_capability)
    with pytest.raises(WindowsAuthorityError):
        require_validated_production_authority(_validation())


def test_parameterless_and_test_complete_validators_select_distinct_issuers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    calls: list[object] = []

    def fake_validate(**kwargs: object) -> object:
        calls.append(kwargs["capability_issuer"])
        return object()

    monkeypatch.setattr(validation, "_validate_installed_authority", fake_validate)

    assert validation.validate_installed_authority_complete() is not None
    assert (
        validation.validate_installed_authority_complete_for_test(
            key_registry=object(),  # type: ignore[arg-type]
        )
        is not None
    )
    assert calls == [
        validation._PRODUCTION_CAPABILITY_ISSUER,
        validation._TEST_CAPABILITY_ISSUER,
    ]


def test_production_issuer_has_no_raw_authority_inputs() -> None:
    assert (
        tuple(inspect.signature(acquire_validated_production_authority).parameters)
        == ()
    )
    with pytest.raises(TypeError):
        acquire_validated_production_authority(key_registry=object())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        acquire_validated_production_authority(validation=object())  # type: ignore[call-arg]


def test_validation_result_cannot_be_consumed_as_executable_without_capability() -> (
    None
):
    with pytest.raises(WindowsAuthorityError):
        require_validated_production_authority(
            _validation(
                state=SqliteDatabaseState.INITIALIZED_SUPPORTED.value,
                capability=None,
                issue_capability=False,
            )
        )


@pytest.mark.parametrize("mismatch", ["bootstrap", "release", "sqlite"])
def test_capability_cannot_outlive_bootstrap_or_database_identity(
    mismatch: str,
) -> None:
    reviewed = _validation()
    if mismatch == "bootstrap":
        bootstrap = reviewed.bootstrap_verification.bootstrap
        substituted = replace(bootstrap, database_identity_digest="cd" * 32)
        actual = replace(
            reviewed,
            bootstrap_verification=replace(
                reviewed.bootstrap_verification, bootstrap=substituted
            ),
        )
    else:
        evidence = reviewed.production_evidence
        assert evidence is not None
        actual = replace(
            reviewed,
            production_evidence=replace(
                evidence,
                release_manifest_digest=(
                    "44" * 32
                    if mismatch == "release"
                    else evidence.release_manifest_digest
                ),
                sqlite_build_manifest_digest=(
                    "55" * 32
                    if mismatch == "sqlite"
                    else evidence.sqlite_build_manifest_digest
                ),
            ),
        )

    with pytest.raises(WindowsAuthorityError):
        require_validated_production_authority(actual)


def test_test_only_capability_injection_is_explicit_and_disposable() -> None:
    bootstrap = _bootstrap()
    capability = acquire_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=_production_evidence(
            database_path="C:\\test\\authority.sqlite3"
        ),
    )
    assert capability.database_path == "C:\\test\\authority.sqlite3"
    assert "_for_test" in acquire_validated_production_authority_for_test.__name__
