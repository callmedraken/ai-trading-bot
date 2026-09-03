"""Pure administrator freeze reconciliation; no production freeze or effects."""

import builtins
import os
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timedelta, timezone
from decimal import Context, Decimal, localcontext
from hashlib import sha256

import pytest

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime import (
    personal_desktop_paper_account_provisioning as preparation,
)
from trading_bot.runtime import (
    personal_desktop_paper_account_publication as publication,
)
from trading_bot.runtime import (
    personal_desktop_paper_account_publication_freeze as freeze_module,
)
from trading_bot.runtime import windows_authority_validation as validation
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_publication_freeze import (
    PersonalDesktopPaperPublicationFreeze,
    require_production_paper_publication_freeze,
    verify_personal_desktop_paper_publication_freeze,
)
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
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    ProvisioningEvidence,
    ProvisioningState,
)

from .test_personal_desktop_paper_account_provisioning import bundle as bundle
from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)


@pytest.fixture
def freeze(bundle):
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    checkpoint = preparation.reconcile_personal_desktop_paper_account_artifacts(
        genesis_bytes=bundle.genesis_bytes,
        anchor_bytes=bundle.anchor_bytes,
        manifest_bytes=bundle.manifest_bytes,
    )
    return PersonalDesktopPaperPublicationFreeze(
        machine_authority_id=anchor.machine_authority_id,
        approved_trading_sid=anchor.approved_trading_sid,
        paper_account_id=anchor.paper_account_id,
        starting_cash=checkpoint.account_state.cash,
        genesis_as_of=checkpoint.account_state.as_of,
        genesis_sha256=sha256(bundle.genesis_bytes).hexdigest(),
        genesis_byte_length=len(bundle.genesis_bytes),
        anchor_sha256=sha256(bundle.anchor_bytes).hexdigest(),
        anchor_byte_length=len(bundle.anchor_bytes),
        manifest_sha256=sha256(bundle.manifest_bytes).hexdigest(),
        manifest_byte_length=len(bundle.manifest_bytes),
    )


@pytest.fixture
def administrator(freeze):
    # In-memory conformance evidence, not a runtime capability or real install.
    bootstrap = WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id=freeze.machine_authority_id,
        authority_epoch_id="11111111-1111-4111-8111-111111111111",
        signing_key_id="test-key/v1",
        approved_account_sid=freeze.approved_trading_sid,
        database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version="authority-policy/v1",
        claim_policy_version="claim-policy/v1",
        database_identity_digest="64" * 32,
    )
    return InstalledAuthorityValidation(
        provisioning=ProvisioningEvidence(
            state=ProvisioningState.VALIDATED,
            authority_root=str(PRODUCTION_AUTHORITY_PATHS.root),
            bootstrap_digest=bootstrap.digest,
            signing_key_id=bootstrap.signing_key_id,
            trading_sid=bootstrap.approved_account_sid,
            inspected_objects=("root", "bootstrap", "signature", "database", "journal"),
            database_present=True,
            journal_present=True,
            database_state="INITIALIZED_SUPPORTED",
        ),
        bootstrap_verification=BootstrapVerification(
            bootstrap, bootstrap.digest, bootstrap.signing_key_id, 64
        ),
        production_evidence=ProductionAuthorityEvidence(
            database_path=str(PRODUCTION_AUTHORITY_PATHS.database),
            schema_id=PRODUCTION_SCHEMA_ID,
            schema_version=PRODUCTION_SCHEMA_VERSION,
            schema_digest=PRODUCTION_SCHEMA_ARTIFACT_SHA256,
            metadata_digest="33" * 32,
            migration_id="migration/v1",
            release_manifest_digest="44" * 32,
            sqlite_build_manifest_digest="55" * 32,
        ),
    )


def test_matching_administrator_freeze_reconciles_without_p2_or_runtime_capability(
    bundle, freeze, administrator, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "pure freeze must not acquire/transfer authority or perform I/O"
        )

    with monkeypatch.context() as patch:
        for name in (
            "acquire_validated_production_authority",
            "acquire_validated_production_authority_for_test",
            "issue_validated_production_authority_for_test",
            "require_validated_production_authority",
            "validate_installed_authority_complete",
        ):
            patch.setattr(validation, name, forbidden)
        for name in (
            "prepare_personal_desktop_paper_account_bundle",
            "prepare_personal_desktop_paper_account_bundle_for_test",
            "verify_personal_desktop_paper_account_bundle",
            "require_selected_c3_snapshot_matches_authority",
        ):
            patch.setattr(preparation, name, forbidden)
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(os, "stat", forbidden)
        assert (
            verify_personal_desktop_paper_publication_freeze(
                bundle,
                freeze=freeze,
                administrator_validation=administrator,
            )
            is None
        )
    assert freeze_module.PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE is None


def test_unconfigured_freeze_blocks_read_only_admission_before_native_validation(
    bundle, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "unconfigured freeze must stop before administrator/native calls"
        )

    monkeypatch.setattr(publication, "validate_installed_authority_complete", forbidden)
    monkeypatch.setattr(publication, "require_windows_platform", forbidden)
    monkeypatch.setattr(publication.WindowsTradingTokenObserver, "observe", forbidden)
    monkeypatch.setenv("PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE", "configured")
    with pytest.raises(WindowsAuthorityError, match="unconfigured"):
        require_production_paper_publication_freeze()
    with pytest.raises(WindowsAuthorityError, match="unconfigured"):
        publication.require_paper_publication_inputs(bundle=bundle)


@pytest.mark.parametrize(
    "field",
    [
        "machine_authority_id",
        "approved_trading_sid",
        "paper_account_id",
        "starting_cash",
        "genesis_as_of",
        "genesis_sha256",
        "genesis_byte_length",
        "anchor_sha256",
        "anchor_byte_length",
        "manifest_sha256",
        "manifest_byte_length",
    ],
)
def test_each_exact_freeze_binding_mismatch_fails(bundle, freeze, administrator, field):
    if field in {"machine_authority_id", "paper_account_id"}:
        changed = "33333333-3333-4333-8333-333333333333"
    elif field == "approved_trading_sid":
        changed = "S-1-5-21-1-2-3-1010"
    elif field == "starting_cash":
        changed = freeze.starting_cash + Decimal("0.01")
    elif field == "genesis_as_of":
        changed = freeze.genesis_as_of + timedelta(microseconds=1)
    elif field.endswith("_sha256"):
        changed = "00" * 32
    else:
        changed = getattr(freeze, field) + 1
    with pytest.raises(WindowsAuthorityError):
        verify_personal_desktop_paper_publication_freeze(
            bundle,
            freeze=replace(freeze, **{field: changed}),
            administrator_validation=administrator,
        )


@pytest.mark.parametrize("field", ["machine_authority_id", "approved_account_sid"])
def test_consistent_but_different_administrator_c1_binding_is_rejected(
    bundle, freeze, administrator, field
):
    changed = (
        "33333333-3333-4333-8333-333333333333"
        if field == "machine_authority_id"
        else "S-1-5-21-1-2-3-1010"
    )
    bootstrap = replace(
        administrator.bootstrap_verification.bootstrap, **{field: changed}
    )
    alternate = replace(
        administrator,
        bootstrap_verification=replace(
            administrator.bootstrap_verification,
            bootstrap=bootstrap,
            bootstrap_digest=bootstrap.digest,
        ),
        provisioning=replace(
            administrator.provisioning,
            bootstrap_digest=bootstrap.digest,
            trading_sid=bootstrap.approved_account_sid,
        ),
    )
    with pytest.raises(WindowsAuthorityError, match="identity/opening"):
        verify_personal_desktop_paper_publication_freeze(
            bundle, freeze=freeze, administrator_validation=alternate
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("machine_authority_id", "ABCDEFAB-1234-4234-8234-ABCDEFABCDEF"),
        ("paper_account_id", "not-a-uuid"),
        ("paper_account_id", None),
        ("approved_trading_sid", "Trading"),
        ("starting_cash", 10000),
        ("starting_cash", 10000.0),
        ("starting_cash", True),
        ("starting_cash", Decimal("0")),
        ("starting_cash", Decimal("-1")),
        ("starting_cash", Decimal("NaN")),
        ("starting_cash", Decimal("Infinity")),
        ("genesis_as_of", "2026-08-29T12:00:01Z"),
        ("genesis_as_of", datetime(2026, 8, 29)),
        ("genesis_as_of", datetime(2026, 8, 29, tzinfo=timezone(timedelta(hours=1)))),
        ("anchor_sha256", "AB" * 32),
        ("genesis_sha256", b"00" * 32),
        ("manifest_sha256", "00"),
        ("anchor_byte_length", True),
        ("genesis_byte_length", 0),
        ("manifest_byte_length", -1),
    ],
)
def test_freeze_model_rejects_noncanonical_types_and_values(freeze, field, value):
    with pytest.raises(WindowsAuthorityError):
        replace(freeze, **{field: value})


def test_freeze_is_immutable_exact_type_and_revalidated_on_consumption(
    bundle, freeze, administrator
):
    with pytest.raises(FrozenInstanceError):
        freeze.starting_cash = Decimal("1")

    class Subclass(PersonalDesktopPaperPublicationFreeze):
        pass

    for value in (None, asdict(freeze), Subclass(**asdict(freeze))):
        with pytest.raises(WindowsAuthorityError, match="exact publication freeze"):
            verify_personal_desktop_paper_publication_freeze(
                bundle, freeze=value, administrator_validation=administrator
            )
    object.__setattr__(freeze, "manifest_byte_length", True)
    with pytest.raises(WindowsAuthorityError, match="length"):
        verify_personal_desktop_paper_publication_freeze(
            bundle, freeze=freeze, administrator_validation=administrator
        )


@pytest.mark.parametrize("artifact", ["genesis", "anchor", "manifest"])
def test_corrupt_bundle_is_reconciled_even_if_transport_hashes_match(
    bundle, freeze, administrator, artifact
):
    altered = object.__new__(type(bundle))
    for name in ("genesis_bytes", "anchor_bytes", "manifest_bytes"):
        object.__setattr__(
            altered,
            name,
            getattr(bundle, name) + (b" " if name == artifact + "_bytes" else b""),
        )
    payload = getattr(altered, artifact + "_bytes")
    matching_hash = replace(
        freeze,
        **{
            artifact + "_sha256": sha256(payload).hexdigest(),
            artifact + "_byte_length": len(payload),
        },
    )
    with pytest.raises(WindowsAuthorityError):
        verify_personal_desktop_paper_publication_freeze(
            altered, freeze=matching_hash, administrator_validation=administrator
        )


@pytest.mark.parametrize(
    "invalid",
    [
        "missing-production",
        "unsupported",
        "no-database",
        "no-journal",
        "unvalidated",
        "wrong-root",
        "bootstrap-digest",
        "signing-key",
        "verification-key",
        "signature-length",
        "production-schema",
        "production-path",
        "evidence-type",
    ],
)
def test_incomplete_or_inconsistent_administrator_evidence_is_rejected(
    bundle, freeze, administrator, invalid
):
    changes = {
        "unsupported": {"database_state": "NOT_PRESENT"},
        "no-database": {"database_present": False},
        "no-journal": {"journal_present": False},
        "unvalidated": {"state": ProvisioningState.PROVISIONED},
        "wrong-root": {"authority_root": "test-root"},
        "bootstrap-digest": {"bootstrap_digest": "00" * 32},
        "signing-key": {"signing_key_id": "different-key"},
    }
    if invalid in changes:
        administrator = replace(
            administrator,
            provisioning=replace(administrator.provisioning, **changes[invalid]),
        )
    elif invalid == "missing-production":
        administrator = replace(administrator, production_evidence=None)
    elif invalid in {"verification-key", "signature-length"}:
        change = (
            {"signing_key_id": "different-key"}
            if invalid == "verification-key"
            else {"signature_length": True}
        )
        administrator = replace(
            administrator,
            bootstrap_verification=replace(
                administrator.bootstrap_verification, **change
            ),
        )
    elif invalid.startswith("production-"):
        change = (
            {"schema_id": "unsupported"}
            if invalid == "production-schema"
            else {"database_path": "test.sqlite"}
        )
        administrator = replace(
            administrator,
            production_evidence=replace(administrator.production_evidence, **change),
        )
    else:
        administrator = object()
    with pytest.raises(WindowsAuthorityError):
        verify_personal_desktop_paper_publication_freeze(
            bundle, freeze=freeze, administrator_validation=administrator
        )


def test_administrator_evidence_and_runtime_authority_are_not_interchangeable(
    bundle, freeze, administrator
):
    with pytest.raises(WindowsAuthorityError):
        validation.require_validated_production_authority(administrator)
    bootstrap = administrator.bootstrap_verification.bootstrap
    capability = validation.issue_validated_production_authority_for_test(
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap.digest,
        production_evidence=administrator.production_evidence,
    )
    with pytest.raises(WindowsAuthorityError, match="administrator C1 evidence"):
        verify_personal_desktop_paper_publication_freeze(
            bundle, freeze=freeze, administrator_validation=capability
        )


def test_freeze_verification_does_not_depend_on_ambient_decimal_context(
    bundle, freeze, administrator
):
    for precision in (1, 7, 50):
        with localcontext(Context(prec=precision)):
            assert (
                verify_personal_desktop_paper_publication_freeze(
                    bundle, freeze=freeze, administrator_validation=administrator
                )
                is None
            )
