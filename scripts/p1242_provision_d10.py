"""Protected P124-2 Administrator provisioning operation; never run at import."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts import d10_protected_deployment as d


def _layout(
    material: d.CertifiedMaterial,
) -> tuple[tuple[str, ...], tuple[tuple[str, bytes], ...]]:
    directories = {d.D10_SOURCE_INSTALLING}
    files: list[tuple[str, bytes]] = []
    for item in material.files:
        parts = item.relative_path.split("/")
        parent = d.D10_SOURCE_INSTALLING
        for part in parts[:-1]:
            parent += "\\" + part
            directories.add(parent)
        files.append((parent + "\\" + parts[-1], item.data))
    return (
        tuple(sorted(directories, key=lambda p: (p.count("\\"), p))),
        tuple(sorted(files)),
    )


def provision_sealed_deployment(
    repository_root: Path,
    backend: d.DeploymentBackend,
) -> d.OperationResult:
    """Install only the fixed sealed guard/source namespace, create-only."""
    backend.require_administrator()
    material = d.build_certified_material(repository_root)
    parent = backend.list_directory(d.D10_PARENT)
    d.require_native_object(parent.identity, d.D10_PARENT, directory=True)
    if parent.stable is not True:
        raise d.DeploymentBlocked("d10_parent_identity_unstable")

    # Bind every source write to the exact manifest before touching the D10 namespace.
    backend.bind_source_inventory(tuple(item.relative_path for item in material.files))

    # Probe all fixed names before creating the root. This leaves no empty root
    # behind when a reserved, installing, lease, cache, or trust object exists.
    backend.require_absent(d.D10_ROOT)
    for path in d.P1242_RESERVED_PATHS:
        backend.require_absent(path)

    backend.create_directory(d.D10_ROOT)
    root = backend.list_directory(d.D10_ROOT)
    d.require_directory(root, d.D10_ROOT, set())
    backend.create_file(d.D10_GUARD_INSTALLING, material.guard_bytes)
    directories, files = _layout(material)
    for path in directories:
        backend.create_directory(path)
    for path, data in files:
        backend.create_file(path, data)

    # Each same-volume rename is atomic and fails if its final name exists.
    backend.publish_create_only(d.D10_GUARD_INSTALLING, d.D10_GUARD)
    backend.publish_create_only(d.D10_SOURCE_INSTALLING, d.D10_SOURCE)
    d.verify_provisioned_state(backend, material)

    transcript = d.operation_transcript(
        "P124-2",
        material,
        paths=(d.D10_ROOT, d.D10_GUARD, d.D10_SOURCE),
    )
    return d.OperationResult(transcript)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument(
        "--execute-protected-p124-2",
        action="store_true",
        help="explicitly run the Administrator-only create-only provisioning operation",
    )
    arguments = parser.parse_args(argv)
    if not arguments.execute_protected_p124_2:
        parser.error("P124-2 remains inert without --execute-protected-p124-2")
    from scripts.d10_protected_deployment_windows import WindowsDeploymentBackend

    try:
        result = provision_sealed_deployment(
            arguments.repository_root, WindowsDeploymentBackend()
        )
    except d.DeploymentBlocked as exc:
        payload = d.canonical_transcript(
            {
                "schema": "personal-desktop-d10-protected-deployment/v1",
                "operation": "P124-2",
                "status": "BLOCKED",
                "reason_code": exc.code,
                "activation_authority": "NONE",
                "scheduler_authority": "NONE",
                "trading_authority": "NONE",
            }
        )
        sys.stdout.buffer.write(payload)
        return 1
    except Exception:
        payload = d.canonical_transcript(
            {
                "schema": "personal-desktop-d10-protected-deployment/v1",
                "operation": "P124-2",
                "status": "BLOCKED",
                "reason_code": "provisioning_internal_failure",
                "activation_authority": "NONE",
                "scheduler_authority": "NONE",
                "trading_authority": "NONE",
            }
        )
        sys.stdout.buffer.write(payload)
        return 1
    sys.stdout.buffer.write(result.transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
