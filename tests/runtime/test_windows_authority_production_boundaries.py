from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from trading_bot.runtime import windows_authority_initialization as initialization
from trading_bot.runtime import windows_authority_provisioning as provisioning
from trading_bot.runtime.windows_authority_schema import (
    InitializationBlockedError,
    validate_production_authority_database_for_test,
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
