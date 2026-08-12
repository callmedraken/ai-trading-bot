from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.runtime import windows_authority_initialization as initialization
from trading_bot.runtime import windows_authority_provisioning as provisioning
from trading_bot.runtime.windows_authority import PRODUCTION_AUTHORITY_PATHS
from trading_bot.runtime.windows_authority_schema import (
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    InitializationBlockedError,
    validate_production_authority_database_for_test,
)


def _installed_validation(
    *,
    state: str = "INITIALIZED_SUPPORTED",
    machine_authority_id: str = "machine-1",
    authority_epoch_id: str = "epoch-1",
    bootstrap_generation: int = 1,
    database_identity_digest: str = "database-1",
    bootstrap_digest: str = "bootstrap-1",
    trading_sid: str = "S-1-5-21-1",
    database_path: str | None = None,
) -> SimpleNamespace:
    bootstrap = SimpleNamespace(
        machine_authority_id=machine_authority_id,
        authority_epoch_id=authority_epoch_id,
        bootstrap_generation=bootstrap_generation,
        database_identity_digest=database_identity_digest,
        approved_account_sid=trading_sid,
    )
    production = SimpleNamespace(
        database_path=database_path or str(PRODUCTION_AUTHORITY_PATHS.database),
        schema_id=PRODUCTION_SCHEMA_ID,
        schema_version=PRODUCTION_SCHEMA_VERSION,
        schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
        metadata_digest="metadata-1",
        migration_id="migration-1",
        release_manifest_digest=bytes.fromhex("72656c65617365").hex(),
        sqlite_build_manifest_digest=bytes.fromhex("6275696c64").hex(),
    )
    return SimpleNamespace(
        provisioning=SimpleNamespace(
            database_state=state,
            bootstrap_digest=bootstrap_digest,
            trading_sid=trading_sid,
        ),
        bootstrap_verification=SimpleNamespace(
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap_digest,
        ),
        production_evidence=production if state == "INITIALIZED_SUPPORTED" else None,
    )


def _approved_identity(
    *, release_digest: str = "11" * 32, sqlite_digest: str = "22" * 32
) -> tuple[SimpleNamespace, SimpleNamespace]:
    return (
        SimpleNamespace(digest=bytes.fromhex(release_digest)),
        SimpleNamespace(digest=bytes.fromhex(sqlite_digest)),
    )


def _test_capability(
    *, release_digest: str = "11" * 32, sqlite_digest: str = "22" * 32
) -> object:
    from tests.runtime.test_windows_authority_capability import (
        _bootstrap,
        _production_evidence,
    )

    from trading_bot.runtime.windows_authority_validation import (
        acquire_validated_production_authority_for_test,
    )

    bootstrap = _bootstrap()
    return acquire_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=_production_evidence(
            release_digest=release_digest,
            sqlite_digest=sqlite_digest,
        ),
    )


def test_production_entrypoints_do_not_accept_caller_trust_evidence() -> None:
    assert (
        tuple(
            inspect.signature(
                initialization.initialize_installed_authority_database
            ).parameters
        )
        == ()
    )
    assert (
        tuple(inspect.signature(provisioning.validate_installed_authority).parameters)
        == ()
    )
    assert tuple(inspect.signature(provisioning.provision_authority).parameters) == (
        "bootstrap_source",
        "signature_source",
    )

    with pytest.raises(TypeError):
        initialization.initialize_installed_authority_database(key_registry=object())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        provisioning.validate_installed_authority(key_registry=object())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        provisioning.provision_authority(  # type: ignore[call-arg]
            bootstrap_source=Path("bootstrap"),
            signature_source=Path("signature"),
            key_registry=object(),
        )


def test_explicit_test_boundaries_retain_trust_evidence_injection() -> None:
    assert (
        "key_registry"
        in inspect.signature(
            provisioning.validate_installed_authority_for_test
        ).parameters
    )
    assert (
        "key_registry"
        in inspect.signature(provisioning.provision_authority_for_test).parameters
    )
    assert (
        "connection"
        in inspect.signature(validate_production_authority_database_for_test).parameters
    )


def test_complete_installed_boundary_retains_sqlite_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validation = _installed_validation()
    monkeypatch.setattr(
        provisioning.authority_validation,
        "validate_installed_authority_complete",
        lambda: validation,
    )

    complete = provisioning.validate_installed_authority_complete()
    compatible = provisioning.validate_installed_authority()

    assert complete is validation
    assert compatible is validation.provisioning
    assert complete.production_evidence is not None


def test_complete_installed_database_validation_uses_one_vfs_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.runtime.test_windows_authority_capability import (
        _bootstrap,
        _production_evidence,
    )

    import trading_bot.runtime.windows_authority_validation as validation

    close_calls = 0
    production = _production_evidence()
    bootstrap = _bootstrap()

    def close() -> None:
        nonlocal close_calls
        close_calls += 1

    fake_connection = SimpleNamespace(close=close)
    open_calls: list[object] = []

    def open_connection(path: object, *, vfs: str) -> SimpleNamespace:
        open_calls.append((path, vfs))
        return fake_connection

    monkeypatch.setattr(validation, "open_read_only_sqlite_connection", open_connection)
    monkeypatch.setattr(
        validation,
        "validate_installed_sqlite_prerequisites",
        lambda actual_connection, **_: SimpleNamespace(
            database_state=initialization.SqliteDatabaseState.INITIALIZED_SUPPORTED
        ),
    )
    monkeypatch.setattr(
        validation,
        "validate_production_authority_database_connection",
        lambda actual_connection, **_: (
            production
            if actual_connection is fake_connection
            else pytest.fail("production validation used a different connection")
        ),
    )

    complete = validation.validate_installed_database_complete(
        True,
        True,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        release_manifest=object(),  # type: ignore[arg-type]
        sqlite_build=SimpleNamespace(vfs="approved"),  # type: ignore[arg-type]
    )

    assert (
        complete.database_state
        is initialization.SqliteDatabaseState.INITIALIZED_SUPPORTED
    )
    assert complete.production_evidence is production
    assert not hasattr(complete, "validated_production_authority")
    assert len(open_calls) == 1
    assert close_calls == 1


def _provisioning_race_setup() -> tuple[
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
    dict[object, bool],
]:
    bootstrap = SimpleNamespace(
        machine_authority_id="machine-1",
        authority_epoch_id="epoch-1",
        bootstrap_generation=1,
        database_identity_digest="database-1",
        approved_account_sid="S-1-5-21-1",
    )
    verification = SimpleNamespace(
        bootstrap=bootstrap,
        bootstrap_digest="bootstrap-1",
        signing_key_id="key-1",
    )
    release, approved_build = _approved_identity()
    build = SimpleNamespace(digest=approved_build.digest, vfs="approved")
    existing = {path: True for path in PRODUCTION_AUTHORITY_PATHS.protected_objects}
    existing[PRODUCTION_AUTHORITY_PATHS.bootstrap] = False
    existing[PRODUCTION_AUTHORITY_PATHS.signature] = False
    return verification, release, build, existing


def test_provisioning_revalidates_raced_supported_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verification, release, build, existing = _provisioning_race_setup()
    staging_bootstrap = tmp_path / "staging.bootstrap.json"
    staging_signature = tmp_path / "staging.bootstrap.sig"
    staging_bootstrap.write_bytes(b"bootstrap")
    staging_signature.write_bytes(b"signature")
    complete_calls: list[dict[str, object]] = []
    installed_files: list[object] = []

    monkeypatch.setattr(provisioning, "require_administrator_token", lambda: None)
    monkeypatch.setattr(provisioning, "parse_bootstrap_bytes", lambda data: None)
    monkeypatch.setattr(
        provisioning,
        "require_trading_standard_account",
        lambda: "S-1-5-21-1",
    )
    monkeypatch.setattr(
        provisioning, "_verify_material", lambda *args, **kwargs: verification
    )
    monkeypatch.setattr(
        provisioning,
        "validate_lifecycle_mutex_security_descriptor",
        lambda sid: None,
    )
    monkeypatch.setattr(
        provisioning, "_require_reserved_temporary_objects_absent", lambda: None
    )
    monkeypatch.setattr(provisioning, "_existing_fixed_objects", lambda sid: existing)
    monkeypatch.setattr(
        provisioning, "_validate_existing_objects", lambda sid, found: None
    )
    monkeypatch.setattr(
        provisioning,
        "_validate_database_if_present",
        lambda database, journal, **kwargs: (
            provisioning.SqliteDatabaseState.PRECREATED_UNINITIALIZED
        ),
    )
    monkeypatch.setattr(
        provisioning,
        "_install_exact_file",
        lambda path, data, policy, present: installed_files.append(path),
    )
    monkeypatch.setattr(provisioning, "_inspect_tree", lambda sid: ((), True, True))

    def complete_validation(*args: object, **kwargs: object) -> SimpleNamespace:
        complete_calls.append(kwargs)
        return SimpleNamespace(
            database_state=provisioning.SqliteDatabaseState.INITIALIZED_SUPPORTED,
            production_evidence=object(),
        )

    monkeypatch.setattr(
        provisioning, "_validate_installed_database_complete", complete_validation
    )

    result = provisioning._provision_authority(
        bootstrap_source=staging_bootstrap,
        signature_source=staging_signature,
        key_registry=object(),  # type: ignore[arg-type]
        release_manifest=release,  # type: ignore[arg-type]
        sqlite_build=build,  # type: ignore[arg-type]
    )

    assert result.database_state == "INITIALIZED_SUPPORTED"
    assert installed_files == [
        PRODUCTION_AUTHORITY_PATHS.bootstrap,
        PRODUCTION_AUTHORITY_PATHS.signature,
    ]
    assert len(complete_calls) == 1
    assert complete_calls[0]["bootstrap"] is verification.bootstrap
    assert complete_calls[0]["bootstrap_digest"] == verification.bootstrap_digest
    assert complete_calls[0]["release_manifest"] is release
    assert complete_calls[0]["sqlite_build"] is build


@pytest.mark.parametrize("mismatch", ["bootstrap", "release", "build"])
def test_provisioning_raced_supported_database_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mismatch: str,
) -> None:
    verification, release, build, existing = _provisioning_race_setup()
    staging_bootstrap = tmp_path / "staging.bootstrap.json"
    staging_signature = tmp_path / "staging.bootstrap.sig"
    staging_bootstrap.write_bytes(b"bootstrap")
    staging_signature.write_bytes(b"signature")
    database_repairs: list[object] = []

    monkeypatch.setattr(provisioning, "require_administrator_token", lambda: None)
    monkeypatch.setattr(provisioning, "parse_bootstrap_bytes", lambda data: None)
    monkeypatch.setattr(
        provisioning,
        "require_trading_standard_account",
        lambda: "S-1-5-21-1",
    )
    monkeypatch.setattr(
        provisioning, "_verify_material", lambda *args, **kwargs: verification
    )
    monkeypatch.setattr(
        provisioning,
        "validate_lifecycle_mutex_security_descriptor",
        lambda sid: None,
    )
    monkeypatch.setattr(
        provisioning, "_require_reserved_temporary_objects_absent", lambda: None
    )
    monkeypatch.setattr(provisioning, "_existing_fixed_objects", lambda sid: existing)
    monkeypatch.setattr(
        provisioning, "_validate_existing_objects", lambda sid, found: None
    )
    monkeypatch.setattr(
        provisioning,
        "_validate_database_if_present",
        lambda database, journal, **kwargs: (
            provisioning.SqliteDatabaseState.PRECREATED_UNINITIALIZED
        ),
    )
    monkeypatch.setattr(
        provisioning,
        "_install_exact_file",
        lambda path, data, policy, present: None,
    )
    monkeypatch.setattr(provisioning, "_inspect_tree", lambda sid: ((), True, True))

    def reject_mismatch(*args: object, **kwargs: object) -> tuple[object, object]:
        database_repairs.append("attempted")
        raise provisioning.WindowsAuthorityError(f"{mismatch} mismatch")

    monkeypatch.setattr(
        provisioning, "_validate_installed_database_complete", reject_mismatch
    )

    with pytest.raises(
        provisioning.WindowsAuthorityError, match=f"{mismatch} mismatch"
    ):
        provisioning._provision_authority(
            bootstrap_source=staging_bootstrap,
            signature_source=staging_signature,
            key_registry=object(),  # type: ignore[arg-type]
            release_manifest=release,  # type: ignore[arg-type]
            sqlite_build=build,  # type: ignore[arg-type]
        )

    assert database_repairs == ["attempted"]


def test_post_commit_complete_validation_is_consumed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _installed_validation()
    actual = _installed_validation()
    calls = 0

    def complete_validation() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return actual

    monkeypatch.setattr(
        initialization, "validate_installed_authority_complete", complete_validation
    )
    capability = _test_capability()
    monkeypatch.setattr(
        initialization, "require_validated_production_authority", lambda _: capability
    )
    release, build = _approved_identity()
    evidence = initialization._post_commit_installed_production_evidence(
        expected_validation=expected,
        selected_release=release,
        selected_build=build,
    )

    assert calls == 1
    assert evidence is capability


def test_new_initializer_success_consumes_post_commit_complete_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, build = _approved_identity()
    preflight = _installed_validation(state="PRECREATED_UNINITIALIZED")
    post_commit = _installed_validation()
    validations = iter((preflight, post_commit))
    calls = 0

    def complete_validation() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return next(validations)

    def fake_transaction(**kwargs: object) -> object:
        validator = kwargs["post_commit_validator"]
        assert callable(validator)
        authority = validator()
        assert authority is capability
        return initialization._production_evidence(
            authority,  # type: ignore[arg-type]
            initialization.SqliteDatabaseState.INITIALIZED_SUPPORTED,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(initialization.os, "name", "nt")
    monkeypatch.setattr(initialization, "require_administrator_token", lambda: None)
    monkeypatch.setattr(
        initialization, "load_approved_release_manifest", lambda: release
    )
    monkeypatch.setattr(
        initialization, "load_approved_sqlite_authority_build", lambda: build
    )
    monkeypatch.setattr(
        initialization, "validate_installed_authority_complete", complete_validation
    )
    capability = _test_capability()
    monkeypatch.setattr(
        initialization, "require_validated_production_authority", lambda _: capability
    )
    monkeypatch.setattr(
        initialization, "_initialize_database_transaction", fake_transaction
    )
    monkeypatch.setattr(
        initialization,
        "validate_production_authority_database_for_test",
        lambda *args, **kwargs: pytest.fail("SQLite-only production fallback was used"),
    )

    result = initialization.initialize_installed_authority_database()

    assert calls == 2
    assert result.state is initialization.SqliteDatabaseState.INITIALIZED_SUPPORTED


@pytest.mark.parametrize("mismatch", ["release", "sqlite"])
def test_new_initializer_rejects_post_commit_approval_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    selected_release, selected_build = _approved_identity()
    returned_release, returned_build = _approved_identity(
        release_digest="33" * 32 if mismatch == "release" else "11" * 32,
        sqlite_digest="44" * 32 if mismatch == "sqlite" else "22" * 32,
    )
    preflight = _installed_validation(state="PRECREATED_UNINITIALIZED")
    post_commit = _installed_validation()
    validations = iter((preflight, post_commit))
    success_effects: list[str] = []

    monkeypatch.setattr(initialization.os, "name", "nt")
    monkeypatch.setattr(initialization, "require_administrator_token", lambda: None)
    monkeypatch.setattr(
        initialization, "load_approved_release_manifest", lambda: selected_release
    )
    monkeypatch.setattr(
        initialization, "load_approved_sqlite_authority_build", lambda: selected_build
    )
    monkeypatch.setattr(
        initialization,
        "validate_installed_authority_complete",
        lambda: next(validations),
    )
    monkeypatch.setattr(
        initialization,
        "require_validated_production_authority",
        lambda _: _test_capability(
            release_digest=returned_release.digest.hex(),
            sqlite_digest=returned_build.digest.hex(),
        ),
    )

    def fake_transaction(**kwargs: object) -> object:
        validator = kwargs["post_commit_validator"]
        assert callable(validator)
        validator()
        success_effects.append("post-commit success")
        pytest.fail("mismatched post-commit approval was accepted")

    monkeypatch.setattr(
        initialization, "_initialize_database_transaction", fake_transaction
    )

    with pytest.raises(initialization.AuthorityInitializationError):
        initialization.initialize_installed_authority_database()
    assert success_effects == []


def test_idempotent_initializer_returns_the_complete_boundary_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, build = _approved_identity()
    validation = _installed_validation()
    calls = 0

    def complete_validation() -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return validation

    monkeypatch.setattr(initialization.os, "name", "nt")
    monkeypatch.setattr(initialization, "require_administrator_token", lambda: None)
    monkeypatch.setattr(
        initialization, "load_approved_release_manifest", lambda: release
    )
    monkeypatch.setattr(
        initialization, "load_approved_sqlite_authority_build", lambda: build
    )
    monkeypatch.setattr(
        initialization, "validate_installed_authority_complete", complete_validation
    )
    capability = _test_capability()
    monkeypatch.setattr(
        initialization, "require_validated_production_authority", lambda _: capability
    )
    monkeypatch.setattr(
        initialization,
        "validate_production_authority_database_for_test",
        lambda *args, **kwargs: pytest.fail("SQLite-only production fallback was used"),
    )

    result = initialization.initialize_installed_authority_database()

    assert calls == 1
    assert result.state is initialization.SqliteDatabaseState.INITIALIZED_SUPPORTED


@pytest.mark.parametrize("mismatch", ["release", "sqlite"])
def test_idempotent_initializer_rejects_approval_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    selected_release, selected_build = _approved_identity()
    returned_release, returned_build = _approved_identity(
        release_digest="33" * 32 if mismatch == "release" else "11" * 32,
        sqlite_digest="44" * 32 if mismatch == "sqlite" else "22" * 32,
    )
    validation = _installed_validation()
    transaction_calls = 0

    monkeypatch.setattr(initialization.os, "name", "nt")
    monkeypatch.setattr(initialization, "require_administrator_token", lambda: None)
    monkeypatch.setattr(
        initialization, "load_approved_release_manifest", lambda: selected_release
    )
    monkeypatch.setattr(
        initialization, "load_approved_sqlite_authority_build", lambda: selected_build
    )
    monkeypatch.setattr(
        initialization, "validate_installed_authority_complete", lambda: validation
    )
    monkeypatch.setattr(
        initialization,
        "require_validated_production_authority",
        lambda _: _test_capability(
            release_digest=returned_release.digest.hex(),
            sqlite_digest=returned_build.digest.hex(),
        ),
    )

    def unexpected_transaction(**kwargs: object) -> object:
        nonlocal transaction_calls
        transaction_calls += 1
        pytest.fail("idempotent approval mismatch reached database mutation")

    monkeypatch.setattr(
        initialization, "_initialize_database_transaction", unexpected_transaction
    )

    with pytest.raises(initialization.AuthorityInitializationError):
        initialization.initialize_installed_authority_database()
    assert transaction_calls == 0


@pytest.mark.parametrize(
    "change",
    [
        {"machine_authority_id": "machine-2"},
        {"authority_epoch_id": "epoch-2"},
        {"bootstrap_generation": 2},
        {"database_identity_digest": "database-2"},
        {"bootstrap_digest": "bootstrap-2"},
        {"trading_sid": "S-1-5-21-2"},
        {"state": "INITIALIZED_UNSUPPORTED"},
        {"database_path": "F:\\substituted\\authority.sqlite3"},
    ],
)
def test_post_commit_complete_validation_rejects_changed_authority_facts(
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
) -> None:
    expected = _installed_validation()
    actual = _installed_validation(**change)  # type: ignore[arg-type]
    release, build = _approved_identity()
    monkeypatch.setattr(
        initialization, "validate_installed_authority_complete", lambda: actual
    )

    with pytest.raises(initialization.AuthorityInitializationError):
        initialization._post_commit_installed_production_evidence(
            expected_validation=expected,
            selected_release=release,
            selected_build=build,
        )


@pytest.mark.parametrize("failure", ["root/reparse", "journal/security", "bootstrap"])
def test_post_commit_windows_revalidation_failure_cannot_fallback_to_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    expected = _installed_validation()
    release, build = _approved_identity()
    monkeypatch.setattr(
        initialization,
        "validate_installed_authority_complete",
        lambda: (_ for _ in ()).throw(
            initialization.WindowsAuthorityError(f"{failure} changed")
        ),
    )
    monkeypatch.setattr(
        initialization,
        "validate_production_authority_database_for_test",
        lambda *args, **kwargs: pytest.fail("SQLite-only fallback was used"),
    )
    with pytest.raises(initialization.AuthorityInitializationError):
        initialization._post_commit_installed_production_evidence(
            expected_validation=expected,
            selected_release=release,
            selected_build=build,
        )


def test_missing_approved_release_fails_before_production_database_ddl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(initialization.os, "name", "nt")
    monkeypatch.setattr(initialization, "require_administrator_token", lambda: None)
    monkeypatch.setattr(
        initialization,
        "load_approved_release_manifest",
        lambda: (_ for _ in ()).throw(
            InitializationBlockedError("release approval is absent")
        ),
    )
    monkeypatch.setattr(
        initialization,
        "_initialize_database_transaction",
        lambda **_: pytest.fail("DDL initializer was reached before approval"),
    )

    with pytest.raises(InitializationBlockedError, match="release approval"):
        initialization.initialize_installed_authority_database()
