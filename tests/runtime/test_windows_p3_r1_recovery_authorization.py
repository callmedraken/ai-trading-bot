"""Focused Architecture-96 signed recovery authorization gates."""

import base64
import copy
import csv
import io
import json
import pickle
from dataclasses import replace
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

import trading_bot.runtime.windows_authority as w
import trading_bot.runtime.windows_p3_r1_recovery_authorization as a
import trading_bot.runtime.windows_paper_account_provisioning as p
from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR


def authorization(**changes):
    values = dict(
        schema=a.RECOVERY_AUTHORIZATION_SCHEMA,
        signing_key_id=a.RECOVERY_SIGNING_KEY_ID,
        machine_authority_id="223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1",
        approved_trading_sid="S-1-5-21-1397534616-3988210162-180023805-1009",
        administrator_operator_sid="S-1-5-21-1-2-3-1001",
        paper_account_id="d1510a4b-6ebf-58ef-92a4-e743ca91151e",
        genesis_checkpoint_id="7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7",
        bootstrap_sha256=(
            "53b8b72ab18b1c477c5eab50857e4dc2d47efc6e74030e380ed6a53387922ae4"
        ),
        authority_database_sha256=(
            "6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76"
        ),
        authority_database_bytes=331776,
        source_commit="1" * 40,
        source_tree="2" * 40,
        wheel_sha256="3" * 64,
        wheel_bytes=743531,
        installed_record_sha256="4" * 64,
        installed_record_bytes=1234,
        staging_root=r"F:\AITradingBot\.Paper.provisioning-v1",
        final_root=r"F:\AITradingBot\Paper",
    )
    values.update(changes)
    return a.P3R1RecoveryAuthorization(**values)


@pytest.fixture
def test_key_registry():
    public_key = bytes.fromhex(
        "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296"
        "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
    )
    return w.PinnedBootstrapKeyRegistry(
        (w.PinnedBootstrapKey(a.RECOVERY_SIGNING_KEY_ID, public_key),)
    )


def fake_signature(public_key, data):
    return sha256(public_key + data).digest() * 2


@pytest.fixture
def fake_signing(monkeypatch, test_key_registry):
    monkeypatch.setattr(a, "require_windows_platform", lambda: None)

    def verify(public_key, data, signature):
        if signature != fake_signature(public_key, data):
            raise w.BootstrapSignatureError("invalid test signature")

    monkeypatch.setattr(a, "verify_p256_p1363_sha256_signature", verify)
    return test_key_registry


def sign_recovery(model, registry):
    payload = model.canonical_bytes()
    public_key = registry.get(model.signing_key_id).public_key
    signature = fake_signature(public_key, a.p3_r1_recovery_signing_preimage(payload))
    return payload, signature


def test_exact_canonical_signed_authorization_verifies(fake_signing):
    model = authorization()
    payload, signature = sign_recovery(model, fake_signing)
    result = a.verify_p3_r1_recovery_authorization(
        payload, signature, key_registry=fake_signing
    )
    assert result.authorization == model
    assert result.authorization_sha256 == sha256(payload).hexdigest()
    assert result.signing_key_id == a.RECOVERY_SIGNING_KEY_ID
    assert a.p3_r1_recovery_signing_preimage(payload) == (
        len(a.RECOVERY_AUTHORIZATION_DOMAIN).to_bytes(2, "big")
        + a.RECOVERY_AUTHORIZATION_DOMAIN
        + len(payload).to_bytes(8, "big")
        + payload
    )


def test_valid_signed_authorization_can_reach_recovery_mutation_seam(
    fake_signing, monkeypatch
):
    model = authorization()
    payload, signature = sign_recovery(model, fake_signing)
    verified = a.verify_p3_r1_recovery_authorization(
        payload, signature, key_registry=fake_signing
    )
    permit = a.issue_disposable_p3_r1_recovery_permit_for_test(verified.authorization)
    reached = []
    monkeypatch.setattr(
        p,
        "consume_p3_r1_recovery_permit",
        a.consume_disposable_p3_r1_recovery_permit_for_test,
    )
    monkeypatch.setattr(
        p._WindowsPublicationSession,
        "rename_root",
        lambda _: reached.append("native-recovery-seam"),
    )
    p._WindowsPublicationSession(p._P3_R1_BUNDLE).rename_recovery_root(permit)
    assert reached == ["native-recovery-seam"]


@pytest.mark.parametrize(
    "mode", ["authorization", "signature", "unsigned", "raw-domain"]
)
def test_signature_or_canonical_byte_tampering_is_rejected(fake_signing, mode):
    model = authorization()
    payload, signature = sign_recovery(model, fake_signing)
    if mode == "authorization":
        values = model.to_dict()
        values["administrator_operator_sid"] = "S-1-5-21-4-5-6-1001"
        payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    elif mode == "signature":
        signature = signature[:-1] + bytes([signature[-1] ^ 1])
    elif mode == "unsigned":
        signature = b""
    else:
        signature = fake_signature(
            fake_signing.get(model.signing_key_id).public_key, payload
        )
    with pytest.raises(a.P3R1RecoveryAuthorizationError):
        a.verify_p3_r1_recovery_authorization(
            payload, signature, key_registry=fake_signing
        )


@pytest.mark.parametrize(
    "mode",
    [
        "unknown",
        "missing",
        "duplicate",
        "whitespace",
        "wrong-purpose",
        "wrong-version",
        "uppercase-digest",
        "alternate-path",
        "bool-length",
    ],
)
def test_schema_is_exact_and_noncanonical_material_is_rejected(mode):
    model = authorization()
    values = model.to_dict()
    if mode == "unknown":
        values["retry"] = False
    elif mode == "missing":
        del values["source_tree"]
    elif mode == "duplicate":
        payload = (
            b'{"schema":"p3-r1-recovery-authorization/v1",'
            + model.canonical_bytes()[1:]
        )
        with pytest.raises(a.P3R1RecoveryAuthorizationError):
            a.parse_p3_r1_recovery_authorization(payload)
        return
    elif mode == "whitespace":
        payload = json.dumps(values, sort_keys=True).encode()
        with pytest.raises(a.P3R1RecoveryAuthorizationSyntaxError):
            a.parse_p3_r1_recovery_authorization(payload)
        return
    elif mode == "wrong-purpose":
        values["schema"] = "other-recovery-authorization/v1"
    elif mode == "wrong-version":
        values["schema"] = "p3-r1-recovery-authorization/v2"
    elif mode == "uppercase-digest":
        values["wheel_sha256"] = ("a" * 64).upper()
    elif mode == "alternate-path":
        values["final_root"] = r"F:\AITradingBot\paper"
    else:
        values["wheel_bytes"] = True
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(a.P3R1RecoveryAuthorizationError):
        a.parse_p3_r1_recovery_authorization(payload)


def test_wrong_key_identity_is_rejected_before_crypto(fake_signing):
    payload, signature = sign_recovery(authorization(), fake_signing)
    wrong_registry = w.PinnedBootstrapKeyRegistry(
        (w.PinnedBootstrapKey("other/v1", fake_signing.keys[0].public_key),)
    )
    with pytest.raises(a.P3R1RecoveryAuthorizationSignatureError):
        a.verify_p3_r1_recovery_authorization(
            payload, signature, key_registry=wrong_registry
        )


def test_bootstrap_and_recovery_domains_are_not_interchangeable(
    fake_signing, monkeypatch
):
    recovery = authorization()
    recovery_bytes, recovery_signature = sign_recovery(recovery, fake_signing)
    monkeypatch.setattr(w, "_require_windows", lambda: None)
    with pytest.raises(w.BootstrapError):
        w.verify_bootstrap_signature(
            recovery_bytes, recovery_signature, key_registry=fake_signing
        )

    bootstrap = w.WindowsAuthorityBootstrap(
        bootstrap_schema=1,
        bootstrap_generation=1,
        machine_authority_id="223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1",
        authority_epoch_id="11111111-1111-4111-8111-111111111111",
        signing_key_id=a.RECOVERY_SIGNING_KEY_ID,
        approved_account_sid="S-1-5-21-1397534616-3988210162-180023805-1009",
        database_path=str(w.PRODUCTION_AUTHORITY_PATHS.database),
        output_root=str(w.PRODUCTION_AUTHORITY_PATHS.capture_output),
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        permitted_provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        authority_policy_version=w.SUPPORTED_AUTHORITY_POLICY_VERSION,
        claim_policy_version=w.SUPPORTED_CLAIM_POLICY_VERSION,
        database_identity_digest="5" * 64,
    )
    bootstrap_bytes = bootstrap.canonical_bytes()
    bootstrap_signature = fake_signature(
        fake_signing.get(bootstrap.signing_key_id).public_key, bootstrap_bytes
    )
    with pytest.raises(a.P3R1RecoveryAuthorizationError):
        a.verify_p3_r1_recovery_authorization(
            bootstrap_bytes, bootstrap_signature, key_registry=fake_signing
        )


@pytest.fixture
def installed_release(monkeypatch):
    files = {}
    rows = []
    package_names = set()
    for name, module in tuple(a.sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            current = PureWindowsPath(module.__file__)
            relative = "/".join(current.parts[current.parts.index("trading_bot") :])
            target = str(a._SITE_PACKAGES / relative)
            monkeypatch.setattr(module, "__file__", target)
            payload = name.encode("utf-8")
            files[target] = payload
            package_names.add(relative)
            digest = base64.urlsafe_b64encode(sha256(payload).digest()).rstrip(b"=")
            rows.append((relative, "sha256=" + digest.decode(), str(len(payload))))
    rows.append((a._RECORD_NAME, "", ""))
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    record = stream.getvalue().encode("utf-8")
    record_path = str(a._SITE_PACKAGES / a._RECORD_NAME)
    files[record_path] = record
    model = authorization(
        installed_record_sha256=sha256(record).hexdigest(),
        installed_record_bytes=len(record),
    )

    monkeypatch.setattr(a, "require_windows_platform", lambda: None)
    monkeypatch.setattr(a, "require_administrator_token", lambda: None)
    monkeypatch.setattr(
        a, "resolve_current_token_sid", lambda: model.administrator_operator_sid
    )
    monkeypatch.setattr(a.sys, "executable", str(a._RUNTIME / "python.exe"))
    monkeypatch.setattr(Path, "read_bytes", lambda path: files[str(path)])
    monkeypatch.setattr(
        a, "_enumerate_installed_package_payloads", lambda: package_names
    )
    validation = SimpleNamespace(
        bootstrap_verification=SimpleNamespace(
            bootstrap=SimpleNamespace(
                machine_authority_id=model.machine_authority_id,
                approved_account_sid=model.approved_trading_sid,
            ),
            bootstrap_digest=model.bootstrap_sha256,
        )
    )
    monkeypatch.setattr(a, "validate_installed_authority_complete", lambda: validation)
    monkeypatch.setattr(
        a, "require_initialized_supported_authority_evidence", lambda _: None
    )
    monkeypatch.setattr(a, "_ATTEMPTED_AUTHORIZATIONS", set())

    def install_verification(selected):
        monkeypatch.setattr(
            a,
            "verify_p3_r1_recovery_authorization",
            lambda authorization_bytes, signature: (
                a.P3R1RecoveryAuthorizationVerification(
                    selected,
                    sha256(authorization_bytes).hexdigest(),
                    selected.signing_key_id,
                    len(signature),
                )
            ),
        )

    install_verification(model)
    return SimpleNamespace(
        model=model,
        files=files,
        package_names=package_names,
        record_path=record_path,
        validation=validation,
        install_verification=install_verification,
    )


def test_verified_operator_c1_and_release_issue_production_permit(installed_release):
    model = installed_release.model
    permit = a.authorize_p3_r1_recovery(model.canonical_bytes(), b"x" * 64)
    assert a.require_p3_r1_recovery_permit(permit) is model
    assert a.consume_p3_r1_recovery_permit(permit) is model
    with pytest.raises(a.P3R1RecoveryPermitError):
        a.consume_p3_r1_recovery_permit(permit)
    with pytest.raises(a.P3R1RecoveryPermitError):
        a.authorize_p3_r1_recovery(model.canonical_bytes(), b"x" * 64)


@pytest.mark.parametrize(
    "mode",
    ["admin", "operator", "runtime", "source", "c1", "record", "payload", "unlisted"],
)
def test_operator_and_installed_release_drift_block_permit(
    installed_release, monkeypatch, mode
):
    case = installed_release
    model = case.model
    if mode == "admin":
        monkeypatch.setattr(
            a,
            "require_administrator_token",
            lambda: (_ for _ in ()).throw(ValueError("not elevated")),
        )
    elif mode == "operator":
        monkeypatch.setattr(
            a, "resolve_current_token_sid", lambda: "S-1-5-21-9-9-9-1001"
        )
    elif mode == "runtime":
        monkeypatch.setattr(a.sys, "executable", "elsewhere")
    elif mode == "source":
        monkeypatch.setattr(a, "__file__", "elsewhere")
    elif mode == "c1":
        case.validation.bootstrap_verification.bootstrap.machine_authority_id = "wrong"
    elif mode == "record":
        model = replace(model, installed_record_sha256="0" * 64)
        case.install_verification(model)
    elif mode == "payload":
        payload_path = next(
            path
            for path in case.files
            if "trading_bot" in path and path != case.record_path
        )
        case.files[payload_path] += b"altered"
    else:
        case.package_names.add("trading_bot/unlisted.py")
    with pytest.raises((ValueError, a.P3R1RecoveryAuthorizationError)):
        a.authorize_p3_r1_recovery(model.canonical_bytes(), b"x" * 64)


@pytest.mark.parametrize(
    "mode",
    [
        "duplicate",
        "case-duplicate",
        "escape",
        "absolute",
        "trailing-dot",
        "unhashed",
        "missing",
        "size",
        "record-hashed",
    ],
)
def test_record_cannot_redirect_omit_or_unhash_payload(
    installed_release, monkeypatch, mode
):
    case = installed_release
    rows = list(csv.reader(io.StringIO(case.files[case.record_path].decode())))
    if mode == "duplicate":
        rows.append(rows[0])
    elif mode == "case-duplicate":
        rows.append([rows[0][0].upper(), rows[0][1], rows[0][2]])
    elif mode in {"escape", "absolute"}:
        rows.insert(
            0,
            [
                "../outside.py" if mode == "escape" else "F:/outside.py",
                "sha256=" + "a" * 43,
                "3",
            ],
        )
    elif mode == "trailing-dot":
        rows.insert(0, ["trading_bot/alias.py.", "sha256=" + "a" * 43, "3"])
    elif mode == "unhashed":
        rows[0][1:] = ["", ""]
    elif mode == "missing":
        rows.pop(0)
    elif mode == "record-hashed":
        rows[-1][1:] = ["sha256=" + "a" * 43, "3"]
    else:
        rows[0][2] = "99999"
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    record = stream.getvalue().encode()
    case.files[case.record_path] = record
    model = replace(
        case.model,
        installed_record_sha256=sha256(record).hexdigest(),
        installed_record_bytes=len(record),
    )
    case.install_verification(model)
    with pytest.raises(a.P3R1RecoveryAuthorizationError):
        a.authorize_p3_r1_recovery(model.canonical_bytes(), b"x" * 64)


def test_reconstructed_fields_cannot_mint_or_substitute_for_permit():
    model = authorization()
    with pytest.raises(TypeError):
        a.P3R1RecoveryPermit()
    forged = object.__new__(a.P3R1RecoveryPermit)
    with pytest.raises(a.P3R1RecoveryPermitError):
        a.require_p3_r1_recovery_permit(forged)
    with pytest.raises(a.P3R1RecoveryPermitError):
        a.consume_p3_r1_recovery_permit(model)
    assert not hasattr(p, "P3R1RecoveryDeploymentExpectation")


def test_process_local_permit_is_immutable_nonserializable_and_provenance_bound():
    model = authorization()
    permit = a.issue_disposable_p3_r1_recovery_permit_for_test(model)
    with pytest.raises(a.P3R1RecoveryPermitError):
        a.require_p3_r1_recovery_permit(permit)
    for operation in (
        lambda: copy.copy(permit),
        lambda: copy.deepcopy(permit),
        lambda: pickle.dumps(permit),
        lambda: setattr(permit, "value", 1),
        lambda: delattr(permit, "__weakref__"),
    ):
        with pytest.raises((TypeError, AttributeError)):
            operation()
    assert a.consume_disposable_p3_r1_recovery_permit_for_test(permit) is model
    with pytest.raises(a.P3R1RecoveryPermitError):
        a.consume_disposable_p3_r1_recovery_permit_for_test(permit)


def test_native_recovery_mutation_rejects_raw_or_forged_authority(monkeypatch):
    session = p._WindowsPublicationSession(p._P3_R1_BUNDLE)
    monkeypatch.setattr(
        p._WindowsPublicationSession,
        "rename_root",
        lambda _: pytest.fail("native rename reached without permit"),
    )
    for candidate in (authorization(), b"authorization", object()):
        with pytest.raises(a.P3R1RecoveryPermitError):
            session.rename_recovery_root(candidate)


def test_native_regression_uses_pytest_managed_scratch():
    source = (
        Path(p.__file__).parents[3]
        / "tests/runtime/test_windows_paper_account_rename_native.py"
    )
    text = source.read_text(encoding="utf-8")
    assert "tmp_path" in text
    assert 'repository / ".pytest_cache"' not in text
