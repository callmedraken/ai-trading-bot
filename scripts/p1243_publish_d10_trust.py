"""Protected P124-3 external signing and create-only trust publication boundary."""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts import d10_protected_deployment as d


def publish_signed_trust(
    repository_root: Path,
    backend: d.DeploymentBackend,
    signer: d.ExternalSigner,
    verifier: d.SignatureVerifier,
) -> d.OperationResult:
    """Sign exact builder bytes externally, verify, then publish only three files."""
    backend.require_administrator()
    material = d.build_certified_material(repository_root)

    # Admission proves P124-2 is complete and every P124-3 destination is absent.
    d.verify_provisioned_state(backend, material)
    try:
        identity = signer.identity
    except Exception:
        raise d.DeploymentBlocked("external_signer_identity_unavailable") from None
    d.require_signer_identity(identity)
    if getattr(verifier, "key_id", None) != d.D10_SIGNING_KEY_ID:
        raise d.DeploymentBlocked("signature_verifier_key_mismatch")

    attestation_bytes = material.build.unsigned_deployment_attestation_bytes
    if attestation_bytes != material.attestation.canonical_bytes():
        raise d.DeploymentBlocked("unsigned_attestation_not_canonical")
    request = d.SigningRequest(
        key_id=d.D10_SIGNING_KEY_ID,
        algorithm=d.SIGNATURE_ALGORITHM,
        digest_algorithm=d.SIGNATURE_HASH,
        signature_encoding=d.SIGNATURE_ENCODING,
        message_sha256=hashlib.sha256(attestation_bytes).digest(),
    )
    try:
        signed = signer.sign_digest(request)
    except Exception:
        raise d.DeploymentBlocked("external_signing_operation_failed") from None
    if type(signed) is not d.DetachedSignature:
        raise d.DeploymentBlocked("external_signing_response_type")
    if (
        signed.key_id != d.D10_SIGNING_KEY_ID
        or signed.algorithm != d.SIGNATURE_ALGORITHM
        or signed.digest_algorithm != d.SIGNATURE_HASH
        or signed.signature_encoding != d.SIGNATURE_ENCODING
    ):
        raise d.DeploymentBlocked("signed_response_identity_or_protocol_mismatch")
    d.verify_signature(verifier, attestation_bytes, signed.signature)

    # Re-run the frozen builder after the external boundary and reread the
    # provisioned files before any temporary/final trust object is created.
    current = d.build_certified_material(repository_root)
    if current != material:
        raise d.DeploymentBlocked("certified_source_changed_during_signing")
    d.verify_provisioned_state(backend, material)
    for path in (*d.TRUST_FINAL_PATHS, *d.TRUST_INSTALLING_PATHS):
        backend.require_absent(path)

    publication = (
        (d.D10_MANIFEST, material.build.executable_manifest_bytes),
        (d.D10_SIGNATURE, signed.signature),
        (d.D10_ATTESTATION, attestation_bytes),
    )
    for final_path, data in publication:
        installing_path = final_path + ".installing"
        backend.create_file(installing_path, data)

    # Publish the manifest and signature first. The attestation is the final
    # create-only name, so no partially published set can pass trust admission.
    for final_path, _ in publication:
        installing_path = final_path + ".installing"
        backend.require_absent(final_path)
        backend.publish_create_only(installing_path, final_path)

    trust_bytes = (
        attestation_bytes,
        signed.signature,
        material.build.executable_manifest_bytes,
    )
    d.verify_provisioned_state(backend, material, trust_bytes=trust_bytes)
    d.verify_signature(verifier, attestation_bytes, signed.signature)

    transcript = d.operation_transcript(
        "P124-3",
        material,
        paths=d.TRUST_FINAL_PATHS,
        signature=signed.signature,
    )
    return d.OperationResult(transcript)
