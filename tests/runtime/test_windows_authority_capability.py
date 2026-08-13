from __future__ import annotations

import inspect
import pickle

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
    InstalledDatabaseValidation,
    ProvisioningEvidence,
    ProvisioningState,
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
    acquire_validated_production_authority_for_test,
    require_initialized_supported_authority_evidence,
    require_validated_production_authority,
)


def _bootstrap(
    *,
    approved_account_sid: str = "S-1-5-21-1",
) -> WindowsAuthorityBootstrap:
    return WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=7,
        machine_authority_id="11111111-1111-4111-8111-111111111111",
        authority_epoch_id="22222222-2222-4222-8222-222222222222",
        signing_key_id="test-key",
        approved_account_sid=approved_account_sid,
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
) -> InstalledAuthorityValidation:
    bootstrap = _bootstrap()
    verification = BootstrapVerification(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        signing_key_id=bootstrap.signing_key_id,
        signature_length=64,
    )
    production = evidence
    if state == SqliteDatabaseState.INITIALIZED_SUPPORTED.value and production is None:
        production = _production_evidence()
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
    )


def _production_validation(
    monkeypatch: pytest.MonkeyPatch,
    *,
    evidence: ProductionAuthorityEvidence | None = None,
    signed_sid: str = "S-1-5-21-1",
    verification_error: WindowsAuthorityError | None = None,
) -> ValidatedProductionAuthority:
    """Build production provenance through the public runtime issuer."""

    import trading_bot.runtime.windows_authority_validation as validation

    bootstrap = _bootstrap(approved_account_sid=signed_sid)
    evidence = evidence or _production_evidence()
    verification = BootstrapVerification(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        signing_key_id=bootstrap.signing_key_id,
        signature_length=64,
    )

    monkeypatch.setattr(
        validation,
        "resolve_current_token_sid",
        lambda: "S-1-5-21-1",
    )
    monkeypatch.setattr(
        validation,
        "require_trading_standard_account",
        lambda: "S-1-5-21-1",
    )
    monkeypatch.setattr(validation, "is_current_token_elevated", lambda: False)
    monkeypatch.setattr(validation, "is_current_token_administrator", lambda: False)
    monkeypatch.setattr(
        validation,
        "validate_lifecycle_mutex_security_descriptor",
        lambda sid: None,
    )
    if verification_error is None:
        monkeypatch.setattr(
            validation, "_verify_material", lambda *args, **kwargs: verification
        )
    else:
        monkeypatch.setattr(
            validation,
            "_verify_material",
            lambda *args, **kwargs: (_ for _ in ()).throw(verification_error),
        )
    monkeypatch.setattr(
        validation,
        "_inspect_runtime_tree",
        lambda sid: (
            ("root", "bootstrap", "signature", "capture-output", "database", "journal"),
            True,
            True,
            b"",
            b"",
        ),
    )
    monkeypatch.setattr(
        validation,
        "validate_installed_database_complete",
        lambda *args, **kwargs: InstalledDatabaseValidation(
            SqliteDatabaseState.INITIALIZED_SUPPORTED,
            evidence,
        ),
    )
    return validation.acquire_validated_production_authority()


def test_complete_installed_validation_still_requires_administrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    def reject() -> None:
        raise WindowsAuthorityError("administrator elevation required")

    monkeypatch.setattr(validation, "require_administrator_token", reject)
    with pytest.raises(WindowsAuthorityError, match="administrator elevation"):
        validation.validate_installed_authority_complete()


def test_installed_validation_is_administrator_evidence_only() -> None:
    validation = _validation()
    assert not hasattr(validation, "validated_production_authority")
    assert (
        require_initialized_supported_authority_evidence(validation)
        is validation.production_evidence
    )


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
        "_require_current_trading_token",
        lambda: "S-1-5-21-1",
    )
    bootstrap = _bootstrap()
    verification = BootstrapVerification(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        signing_key_id=bootstrap.signing_key_id,
        signature_length=64,
    )
    monkeypatch.setattr(validation, "_verify_material", lambda *a, **k: verification)
    monkeypatch.setattr(
        validation, "validate_lifecycle_mutex_security_descriptor", lambda sid: None
    )
    monkeypatch.setattr(
        validation,
        "_inspect_runtime_tree",
        lambda sid: ((), False, False, b"", b""),
    )
    monkeypatch.setattr(
        validation,
        "validate_installed_database_complete",
        lambda *a, **k: InstalledDatabaseValidation(SqliteDatabaseState(state), None),
    )

    with pytest.raises(WindowsAuthorityError):
        acquire_validated_production_authority()


def test_production_acquisition_rejects_missing_complete_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    _production_validation(monkeypatch, evidence=None)
    monkeypatch.setattr(
        validation,
        "validate_installed_database_complete",
        lambda *a, **k: InstalledDatabaseValidation(
            SqliteDatabaseState.INITIALIZED_SUPPORTED, None
        ),
    )
    with pytest.raises(WindowsAuthorityError):
        acquire_validated_production_authority()


@pytest.mark.parametrize(
    "current_sid,elevated,administrator",
    [
        ("S-1-5-21-2", False, False),
        ("S-1-5-21-1", True, False),
        ("S-1-5-21-1", False, True),
    ],
)
def test_runtime_issuer_rejects_wrong_or_privileged_current_token(
    monkeypatch: pytest.MonkeyPatch,
    current_sid: str,
    elevated: bool,
    administrator: bool,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    _production_validation(monkeypatch)
    monkeypatch.setattr(validation, "resolve_current_token_sid", lambda: current_sid)
    monkeypatch.setattr(validation, "is_current_token_elevated", lambda: elevated)
    monkeypatch.setattr(
        validation, "is_current_token_administrator", lambda: administrator
    )
    with pytest.raises(WindowsAuthorityError):
        acquire_validated_production_authority()


def test_runtime_issuer_does_not_reuse_administrator_parent_or_backup_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    _production_validation(monkeypatch)
    monkeypatch.setattr(
        validation,
        "validate_installed_authority_complete",
        lambda: pytest.fail("administrator complete validator was reused"),
    )
    monkeypatch.setattr(
        validation,
        "validate_fixed_parent_chain",
        lambda *args, **kwargs: pytest.fail("parent chain was inspected"),
    )
    assert (
        type(acquire_validated_production_authority()) is ValidatedProductionAuthority
    )


def test_runtime_object_validation_uses_opened_handles_and_excludes_parent_backup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.runtime.windows_authority_validation as validation

    opened: list[str] = []

    class Handle:
        def __enter__(self) -> Handle:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        validation,
        "open_authority_object",
        lambda path, kind: opened.append(str(path)) or Handle(),
    )
    monkeypatch.setattr(
        validation, "inspect_open_authority_object", lambda *args: object()
    )
    monkeypatch.setattr(validation, "require_security_policy", lambda *args: None)
    monkeypatch.setattr(
        validation, "read_open_authority_file", lambda handle: b"material"
    )
    monkeypatch.setattr(validation.os.path, "lexists", lambda path: True)

    inspected, database_present, journal_present, bootstrap, signature = (
        validation._inspect_runtime_tree("S-1-5-21-1")
    )

    assert inspected == (
        "root",
        "bootstrap",
        "signature",
        "capture-output",
        "database",
        "journal",
    )
    assert database_present is True
    assert journal_present is True
    assert bootstrap == b"material"
    assert signature == b"material"
    assert all("backup" not in path.casefold() for path in opened)
    assert all(path != r"F:\AITradingBot" for path in opened)


def test_signed_bootstrap_sid_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(WindowsAuthorityError):
        _production_validation(monkeypatch, signed_sid="S-1-5-21-2")


def test_wrong_bootstrap_signature_or_key_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(WindowsAuthorityError):
        _production_validation(
            monkeypatch,
            verification_error=WindowsAuthorityError("bootstrap signature invalid"),
        )


def test_exact_supported_validation_issues_one_immutable_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    capability = _production_validation(monkeypatch)

    assert type(capability) is ValidatedProductionAuthority
    assert capability.authority_epoch_id == _bootstrap().authority_epoch_id
    assert capability.machine_authority_id == _bootstrap().machine_authority_id
    assert capability.bootstrap_digest == _bootstrap().digest
    assert capability.schema_id == _production_evidence().schema_id
    assert capability.metadata_digest == _production_evidence().metadata_digest
    assert capability.migration_id == _production_evidence().migration_id
    with pytest.raises(AttributeError):
        capability.authority_epoch_id = "substituted"  # type: ignore[misc]
    with pytest.raises(TypeError):
        pickle.dumps(capability)


def test_test_capability_has_test_provenance_and_cannot_cross_production_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production_capability = _production_validation(monkeypatch)
    test_capability = acquire_validated_production_authority_for_test(
        bootstrap=_bootstrap(),
        bootstrap_digest=_bootstrap().digest,
        production_evidence=_production_evidence(),
    )
    public_fields = (
        "authority_epoch_id",
        "machine_authority_id",
        "bootstrap_schema",
        "bootstrap_generation",
        "signing_key_id",
        "approved_account_sid",
        "provider_id",
        "permitted_provider_operation",
        "authority_policy_version",
        "claim_policy_version",
        "bootstrap_digest",
        "database_identity_digest",
        "database_path",
        "schema_id",
        "schema_version",
        "schema_digest",
        "metadata_digest",
        "migration_id",
        "release_manifest_digest",
        "sqlite_build_manifest_digest",
    )
    assert tuple(getattr(test_capability, field) for field in public_fields) == tuple(
        getattr(production_capability, field) for field in public_fields
    )
    assert test_capability != production_capability
    with pytest.raises(WindowsAuthorityError):
        require_validated_production_authority(test_capability)


def test_parameterless_complete_validator_issues_accepted_production_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = _production_validation(monkeypatch)
    assert require_validated_production_authority(capability) is capability


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
        require_validated_production_authority(_validation())  # type: ignore[arg-type]


def test_capability_deletion_is_rejected_and_leaves_production_authority_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = _production_validation(monkeypatch)
    before_repr = repr(capability)
    before_hash = hash(capability)
    for field in ("schema_id", "authority_epoch_id", "database_path"):
        with pytest.raises(AttributeError):
            delattr(capability, field)
    assert capability.schema_id == PRODUCTION_SCHEMA_ID
    assert repr(capability) == before_repr
    assert hash(capability) == before_hash
    assert capability == capability
    assert require_validated_production_authority(capability) is capability


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
