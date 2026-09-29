"""Architecture-128 R2 exact-material sign-only operator.

Importing this module is inert. The protected entry point signs exactly the
accepted R1 unsigned deployment attestation with the existing fixed D10 v3
machine key and writes only detached-signature evidence below F:\\AI\\temp.
It never publishes production trust files or mutates Task Scheduler.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from scripts import d10_protected_deployment as deployment
from scripts import d10_protected_deployment_windows as windows
from scripts import d10_signing_key_windows as cng
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    DeploymentAttestation,
    parse_deployment_attestation,
)

R1_ATTESTATION_PATH = Path(
    r"F:\AI\temp\arch128-r1-material-r2-20260929-014734"
    r"\deployment.attestation.unsigned.json"
)
EVIDENCE_PARENT = Path(r"F:\AI\temp")
EVIDENCE_PREFIX = "arch128-r2-signing-"

EXPECTED_ATTESTATION_SHA256 = (
    "3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"
)
EXPECTED_ATTESTATION_LENGTH = 1011
EXPECTED_DEPLOYMENT_ID = "d2071f25-5a7c-5293-a28f-5b722c9917a2"
EXPECTED_SOURCE_HEAD = "0f9551e13486ef65b35a5a9633da19081571144b"
EXPECTED_SOURCE_TREE = "1186e92669af100542c055368c1b72495c36bc11"
EXPECTED_MANIFEST_SHA256 = (
    "080c622035c7c8492a66ba5d5aa9a48c9020933fb16f85a7604010d529bd06e2"
)
EXPECTED_EXECUTABLE_FILE_COUNT = 307
EXPECTED_GUARD_SHA256 = (
    "ab80233a6ce59a579653008609753441864f74592ac52d12ec65c6dc714eabf7"
)
EXPECTED_GUARD_BYTE_LENGTH = 112228
EXPECTED_PRODUCTION_PYTHON_VERSION = "3.14.3"
SUMMARY_SCHEMA = "arch128-r2-signing/v1"


class R2Blocked(RuntimeError):
    """The R2 sign-only boundary cannot continue."""


class _Signer(Protocol):
    @property
    def identity(self) -> deployment.SigningIdentity: ...

    def sign_digest(
        self, request: deployment.SigningRequest
    ) -> deployment.DetachedSignature: ...


class _Verifier(Protocol):
    key_id: str

    def verify(self, message: bytes, signature: bytes) -> bool: ...


@dataclass(frozen=True, slots=True)
class R2SignedMaterial:
    attestation: DeploymentAttestation
    signature: bytes
    signature_sha256: str


def _read_stable_regular_file(path: Path) -> bytes:
    try:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or bool(
                getattr(before, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            )
            or before.st_nlink != 1
        ):
            raise R2Blocked("r1_attestation_not_regular_single_link")
        data = path.read_bytes()
        after = path.lstat()
    except R2Blocked:
        raise
    except OSError:
        raise R2Blocked("r1_attestation_unavailable") from None
    if (
        not stat.S_ISREG(after.st_mode)
        or stat.S_ISLNK(after.st_mode)
        or bool(
            getattr(after, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        or after.st_nlink != 1
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(data) != after.st_size
    ):
        raise R2Blocked("r1_attestation_identity_or_content_drift")
    return data


def require_exact_r1_attestation(data: bytes) -> DeploymentAttestation:
    if type(data) is not bytes or len(data) != EXPECTED_ATTESTATION_LENGTH:
        raise R2Blocked("r1_attestation_length_mismatch")
    if hashlib.sha256(data).hexdigest() != EXPECTED_ATTESTATION_SHA256:
        raise R2Blocked("r1_attestation_digest_mismatch")
    try:
        attestation = parse_deployment_attestation(data)
    except Exception:
        raise R2Blocked("r1_attestation_not_canonical") from None
    if (
        attestation.canonical_bytes() != data
        or attestation.deployment_id != EXPECTED_DEPLOYMENT_ID
        or attestation.certified_source_head != EXPECTED_SOURCE_HEAD
        or attestation.certified_source_tree != EXPECTED_SOURCE_TREE
        or attestation.executable_manifest_sha256 != EXPECTED_MANIFEST_SHA256
        or attestation.executable_file_count != EXPECTED_EXECUTABLE_FILE_COUNT
        or attestation.launch_guard_sha256 != EXPECTED_GUARD_SHA256
        or attestation.launch_guard_byte_length != EXPECTED_GUARD_BYTE_LENGTH
        or attestation.production_python_version != EXPECTED_PRODUCTION_PYTHON_VERSION
        or attestation.signing_key_id != deployment.D10_SIGNING_KEY_ID
    ):
        raise R2Blocked("r1_attestation_fields_mismatch")
    return attestation


def build_signing_request(data: bytes) -> deployment.SigningRequest:
    require_exact_r1_attestation(data)
    return deployment.SigningRequest(
        deployment.D10_SIGNING_KEY_ID,
        deployment.SIGNATURE_ALGORITHM,
        deployment.SIGNATURE_HASH,
        deployment.SIGNATURE_ENCODING,
        hashlib.sha256(data).digest(),
    )


def sign_exact_r1_attestation(
    data: bytes, signer: _Signer, verifier: _Verifier
) -> R2SignedMaterial:
    attestation = require_exact_r1_attestation(data)
    try:
        identity = signer.identity
    except Exception:
        raise R2Blocked("signer_identity_unavailable") from None
    try:
        deployment.require_signer_identity(identity)
    except Exception:
        raise R2Blocked("signer_identity_mismatch") from None
    if getattr(verifier, "key_id", None) != deployment.D10_SIGNING_KEY_ID:
        raise R2Blocked("verifier_key_mismatch")

    request = build_signing_request(data)
    try:
        signed = signer.sign_digest(request)
    except Exception:
        raise R2Blocked("signing_operation_failed") from None
    if type(signed) is not deployment.DetachedSignature:
        raise R2Blocked("signing_response_type")
    if (
        signed.key_id != deployment.D10_SIGNING_KEY_ID
        or signed.algorithm != deployment.SIGNATURE_ALGORITHM
        or signed.digest_algorithm != deployment.SIGNATURE_HASH
        or signed.signature_encoding != deployment.SIGNATURE_ENCODING
    ):
        raise R2Blocked("signing_response_protocol_mismatch")
    try:
        deployment.verify_signature(verifier, data, signed.signature)
    except Exception:
        raise R2Blocked("detached_signature_verification_failed") from None
    return R2SignedMaterial(
        attestation,
        signed.signature,
        hashlib.sha256(signed.signature).hexdigest(),
    )


def _new_evidence_directory() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    path = EVIDENCE_PARENT / f"{EVIDENCE_PREFIX}{stamp}"
    try:
        path.mkdir(parents=False, exist_ok=False)
    except OSError:
        raise R2Blocked("evidence_directory_create_failed") from None
    return path


def require_evidence_directory(evidence: Path) -> None:
    """Require one fresh evidence directory below the fixed external parent."""
    if (
        not isinstance(evidence, Path)
        or evidence.parent != EVIDENCE_PARENT
        or not evidence.name.startswith(EVIDENCE_PREFIX)
        or not evidence.is_dir()
    ):
        raise R2Blocked("evidence_directory_invalid")
    try:
        if any(evidence.iterdir()):
            raise R2Blocked("evidence_directory_not_empty")
    except R2Blocked:
        raise
    except OSError:
        raise R2Blocked("evidence_directory_unavailable") from None


def protected_sign_fixed_r1_material(
    evidence: Path,
) -> dict[str, object]:
    """One protected signature over the exact accepted R1 attestation."""
    if os.name != "nt":
        raise R2Blocked("windows_required")
    require_evidence_directory(evidence)

    data = _read_stable_regular_file(R1_ATTESTATION_PATH)
    attestation = require_exact_r1_attestation(data)

    # Read-only fixed-key qualification before the one signature operation.
    qualification = cng.qualify_existing_d10_signing_key_after_attempt2()
    if (
        qualification.status != "PASS"
        or qualification.public_key is None
        or qualification.public_key != windows.PUBLIC_KEY
        or qualification.public_key_sha256
        != hashlib.sha256(windows.PUBLIC_KEY).hexdigest()
    ):
        raise R2Blocked("fixed_signing_key_qualification_failed")

    signer = cng.WindowsCngExternalSigner()
    verifier = windows.WindowsCngVerifier()
    result = sign_exact_r1_attestation(data, signer, verifier)

    signature_path = evidence / "deployment.attestation.sig"
    summary_path = evidence / "summary.json"
    try:
        with signature_path.open("xb") as stream:
            stream.write(result.signature)
            stream.flush()
            os.fsync(stream.fileno())
        summary = {
            "schema": SUMMARY_SCHEMA,
            "status": "PASS",
            "attestation_path": str(R1_ATTESTATION_PATH),
            "attestation_sha256": EXPECTED_ATTESTATION_SHA256,
            "attestation_byte_length": EXPECTED_ATTESTATION_LENGTH,
            "deployment_id": attestation.deployment_id,
            "certified_source_head": attestation.certified_source_head,
            "certified_source_tree": attestation.certified_source_tree,
            "executable_manifest_sha256": attestation.executable_manifest_sha256,
            "executable_file_count": attestation.executable_file_count,
            "launch_guard_sha256": attestation.launch_guard_sha256,
            "launch_guard_byte_length": attestation.launch_guard_byte_length,
            "signing_key_id": deployment.D10_SIGNING_KEY_ID,
            "signing_algorithm": deployment.SIGNATURE_ALGORITHM,
            "digest_algorithm": deployment.SIGNATURE_HASH,
            "signature_encoding": deployment.SIGNATURE_ENCODING,
            "signature_byte_length": len(result.signature),
            "signature_sha256": result.signature_sha256,
            "public_key_sha256": qualification.public_key_sha256,
            "signature_verification": "PASS",
            "private_key_export": "NOT_RUN",
            "key_enrollment": "NOT_RUN",
            "production_filesystem": "NOT_RUN",
            "scheduler": "NOT_RUN",
            "provider": "NOT_RUN",
            "paper_v2": "NOT_RUN",
            "broker": "NOT_RUN",
            "live": "NOT_RUN",
        }
        with summary_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(summary, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise R2Blocked("evidence_write_failed_after_signature") from None

    if (
        signature_path.read_bytes() != result.signature
        or hashlib.sha256(signature_path.read_bytes()).hexdigest()
        != result.signature_sha256
    ):
        raise R2Blocked("signature_evidence_reread_mismatch")
    try:
        deployment.verify_signature(verifier, data, signature_path.read_bytes())
    except Exception:
        raise R2Blocked("signature_evidence_reverification_failed") from None
    return summary


def main() -> int:
    if len(sys.argv) != 1:
        print("R2 STOP: arguments are not accepted", file=sys.stderr)
        return 2
    try:
        evidence = _new_evidence_directory()
    except R2Blocked as error:
        print(f"R2 STOP: {error}", file=sys.stderr)
        return 1
    print(f"ARCH128_R2_EVIDENCE={evidence}")
    try:
        summary = protected_sign_fixed_r1_material(evidence)
    except R2Blocked as error:
        print(f"R2 STOP: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("D10_ARCH128_R2_SIGNING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
