from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts import d10_arch128_r2_signing as r2
from scripts import d10_protected_deployment as deployment
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    build_deployment_attestation,
)


def _attestation_bytes() -> bytes:
    value = build_deployment_attestation(
        certified_source_head=r2.EXPECTED_SOURCE_HEAD,
        certified_source_tree=r2.EXPECTED_SOURCE_TREE,
        production_python_version=r2.EXPECTED_PRODUCTION_PYTHON_VERSION,
        launch_guard_byte_length=r2.EXPECTED_GUARD_BYTE_LENGTH,
        launch_guard_sha256=r2.EXPECTED_GUARD_SHA256,
        executable_manifest_sha256=r2.EXPECTED_MANIFEST_SHA256,
        executable_file_count=r2.EXPECTED_EXECUTABLE_FILE_COUNT,
    )
    return value.canonical_bytes()


def _signature() -> bytes:
    return (1).to_bytes(32, "big") + (2).to_bytes(32, "big")


class FakeSigner:
    def __init__(
        self,
        *,
        identity: deployment.SigningIdentity | None = None,
        response: deployment.DetachedSignature | None = None,
        fail: bool = False,
    ):
        self._identity = identity or deployment.SigningIdentity(
            deployment.D10_SIGNING_KEY_ID,
            deployment.SIGNATURE_ALGORITHM,
            deployment.SIGNATURE_HASH,
            deployment.SIGNATURE_ENCODING,
            False,
        )
        self.response = response
        self.fail = fail
        self.requests: list[deployment.SigningRequest] = []

    @property
    def identity(self) -> deployment.SigningIdentity:
        return self._identity

    def sign_digest(
        self, request: deployment.SigningRequest
    ) -> deployment.DetachedSignature:
        self.requests.append(request)
        if self.fail:
            raise OSError("sign failed")
        return self.response or deployment.DetachedSignature(
            deployment.D10_SIGNING_KEY_ID,
            deployment.SIGNATURE_ALGORITHM,
            deployment.SIGNATURE_HASH,
            deployment.SIGNATURE_ENCODING,
            _signature(),
        )


class FakeVerifier:
    key_id = deployment.D10_SIGNING_KEY_ID

    def __init__(self, *, valid: bool = True):
        self.valid = valid
        self.calls: list[tuple[bytes, bytes]] = []

    def verify(self, message: bytes, signature: bytes) -> bool:
        self.calls.append((message, signature))
        return self.valid and signature == _signature()


def test_frozen_r1_attestation_facts_reconstruct_exact_bytes() -> None:
    data = _attestation_bytes()
    attestation = r2.require_exact_r1_attestation(data)

    assert len(data) == r2.EXPECTED_ATTESTATION_LENGTH == 1011
    assert hashlib.sha256(data).hexdigest() == r2.EXPECTED_ATTESTATION_SHA256
    assert attestation.deployment_id == r2.EXPECTED_DEPLOYMENT_ID
    assert attestation.certified_source_head == r2.EXPECTED_SOURCE_HEAD
    assert attestation.certified_source_tree == r2.EXPECTED_SOURCE_TREE
    assert attestation.executable_manifest_sha256 == r2.EXPECTED_MANIFEST_SHA256
    assert attestation.executable_file_count == 307
    assert attestation.launch_guard_sha256 == r2.EXPECTED_GUARD_SHA256
    assert attestation.launch_guard_byte_length == 112228


def test_signs_exact_digest_once_and_reverifies() -> None:
    data = _attestation_bytes()
    signer = FakeSigner()
    verifier = FakeVerifier()

    result = r2.sign_exact_r1_attestation(data, signer, verifier)

    assert len(signer.requests) == 1
    request = signer.requests[0]
    assert request.message_sha256 == hashlib.sha256(data).digest()
    assert request.key_id == deployment.D10_SIGNING_KEY_ID
    assert request.algorithm == "ECDSA-P256"
    assert request.digest_algorithm == "SHA-256"
    assert request.signature_encoding == "IEEE-P1363"
    assert result.signature == _signature()
    assert result.signature_sha256 == hashlib.sha256(_signature()).hexdigest()
    assert verifier.calls == [(data, _signature())]


@pytest.mark.parametrize(
    "mutation",
    ["length", "digest", "deployment", "head", "tree", "manifest", "guard"],
)
def test_any_r1_material_drift_blocks_before_signing(mutation: str) -> None:
    data = _attestation_bytes()
    if mutation == "length":
        changed = data + b"\n"
    elif mutation == "digest":
        changed = bytearray(data)
        changed[-2] ^= 1
        changed = bytes(changed)
    else:
        text = data.decode("utf-8")
        replacements = {
            "deployment": (
                r2.EXPECTED_DEPLOYMENT_ID,
                "00000000-0000-5000-8000-000000000000",
            ),
            "head": (r2.EXPECTED_SOURCE_HEAD, "f" * 40),
            "tree": (r2.EXPECTED_SOURCE_TREE, "e" * 40),
            "manifest": (r2.EXPECTED_MANIFEST_SHA256, "0" * 64),
            "guard": (r2.EXPECTED_GUARD_SHA256, "1" * 64),
        }
        old, new = replacements[mutation]
        changed = text.replace(old, new, 1).encode("utf-8")
    signer = FakeSigner()
    with pytest.raises(r2.R2Blocked):
        r2.sign_exact_r1_attestation(changed, signer, FakeVerifier())
    assert signer.requests == []


def test_wrong_signer_identity_blocks_before_signing() -> None:
    signer = FakeSigner(
        identity=deployment.SigningIdentity(
            "wrong",
            deployment.SIGNATURE_ALGORITHM,
            deployment.SIGNATURE_HASH,
            deployment.SIGNATURE_ENCODING,
            False,
        )
    )
    with pytest.raises(r2.R2Blocked, match="signer_identity_mismatch"):
        r2.sign_exact_r1_attestation(_attestation_bytes(), signer, FakeVerifier())
    assert signer.requests == []


def test_signer_failure_is_not_retried() -> None:
    signer = FakeSigner(fail=True)
    with pytest.raises(r2.R2Blocked, match="signing_operation_failed"):
        r2.sign_exact_r1_attestation(_attestation_bytes(), signer, FakeVerifier())
    assert len(signer.requests) == 1


def test_bad_signature_or_protocol_blocks() -> None:
    signer = FakeSigner(
        response=deployment.DetachedSignature(
            deployment.D10_SIGNING_KEY_ID,
            deployment.SIGNATURE_ALGORITHM,
            deployment.SIGNATURE_HASH,
            deployment.SIGNATURE_ENCODING,
            bytes(64),
        )
    )
    with pytest.raises(r2.R2Blocked, match="detached_signature_verification_failed"):
        r2.sign_exact_r1_attestation(_attestation_bytes(), signer, FakeVerifier())

    wrong = FakeSigner(
        response=deployment.DetachedSignature(
            "wrong",
            deployment.SIGNATURE_ALGORITHM,
            deployment.SIGNATURE_HASH,
            deployment.SIGNATURE_ENCODING,
            _signature(),
        )
    )
    with pytest.raises(r2.R2Blocked, match="signing_response_protocol_mismatch"):
        r2.sign_exact_r1_attestation(_attestation_bytes(), wrong, FakeVerifier())


def test_verifier_key_or_result_mismatch_blocks() -> None:
    wrong_key = FakeVerifier()
    wrong_key.key_id = "wrong"
    signer = FakeSigner()
    with pytest.raises(r2.R2Blocked, match="verifier_key_mismatch"):
        r2.sign_exact_r1_attestation(_attestation_bytes(), signer, wrong_key)
    assert signer.requests == []

    with pytest.raises(r2.R2Blocked, match="detached_signature_verification_failed"):
        r2.sign_exact_r1_attestation(
            _attestation_bytes(), FakeSigner(), FakeVerifier(valid=False)
        )


def test_operator_source_has_no_production_publication_or_key_enrollment_surface(
) -> None:
    source = Path(r2.__file__).read_text(encoding="utf-8")
    assert r"F:\AITradingBot" not in source
    assert "publish_signed_trust" not in source
    assert "WindowsDeploymentBackend" not in source
    assert "prepare_d10_signing_key" not in source
    assert "NCryptCreatePersistedKey" not in source
    assert "NCryptDeleteKey" not in source
    assert "NCryptExportKey" not in source
    assert "scheduler" in source
    assert r2.R1_ATTESTATION_PATH == Path(
        r"F:\AI\temp\arch128-r1-material-r2-20260929-014734"
        r"\deployment.attestation.unsigned.json"
    )


def test_cli_rejects_semantic_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r2.sys, "argv", ["r2", "unexpected"])
    assert r2.main() == 2
