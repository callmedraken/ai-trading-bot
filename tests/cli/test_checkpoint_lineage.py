"""Focused strict-manifest full-lineage command coverage."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tests.runtime.test_paper_account_lineage_verification import _one_edge, _two_edges

from trading_bot.cli.checkpoint_lineage import main, verify_lineage_manifest
from trading_bot.cli.checkpoint_lineage_config import (
    PaperAccountLineageManifestReadError,
    PaperAccountLineageManifestValidationError,
    load_paper_account_lineage_manifest,
)
from trading_bot.runtime import PaperAccountLineageVerificationStatus


def _reference(artifact, path: str) -> dict[str, object]:
    return {
        "artifact_id": str(artifact.artifact_id),
        "path": path,
        "sha256": artifact.sha256,
        "byte_length": artifact.byte_length,
    }


def _write_manifest(root: Path, lineage, *, duplicate: bool = False) -> Path:
    root.mkdir()
    genesis_name = "genesis.json"
    (root / genesis_name).write_bytes(lineage.genesis.payload)
    successor_refs = []
    for index, artifact in enumerate(lineage.successors):
        name = f"successor-{index}.json"
        (root / name).write_bytes(artifact.payload)
        successor_refs.append(_reference(artifact, name))
    report_refs = []
    for index, artifact in enumerate(lineage.reports):
        name = f"report-{index}.json"
        (root / name).write_bytes(artifact.payload)
        report_refs.append(_reference(artifact, name))
    snapshot_refs = []
    for index, artifact in enumerate(lineage.snapshots):
        name = f"snapshot-{index}.json"
        (root / name).write_bytes(artifact.payload)
        snapshot_refs.append(_reference(artifact, name))
    if duplicate and successor_refs:
        successor_refs.append(dict(successor_refs[0]))
        report_refs.append(dict(report_refs[0]))
        snapshot_refs.append(dict(snapshot_refs[0]))
    manifest = {
        "schema_version": 1,
        "genesis_checkpoint": _reference(lineage.genesis, genesis_name),
        "terminal_checkpoint_id": str(lineage.terminal_id),
        "successor_checkpoints": successor_refs,
        "cycle_reports": report_refs,
        "snapshots": snapshot_refs,
    }
    path = root / "lineage-manifest.json"
    path.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    return path


def test_manifest_verifies_same_evidence_from_different_filesystem_roots(
    tmp_path: Path,
) -> None:
    lineage = _two_edges()
    first_path = _write_manifest(tmp_path / "first", lineage)
    second_path = _write_manifest(tmp_path / "second", lineage, duplicate=True)
    (tmp_path / "second" / "unlisted-hostile-looking.json").write_bytes(b"not json")

    first = verify_lineage_manifest(first_path).verification
    second = verify_lineage_manifest(second_path).verification

    assert first.status is PaperAccountLineageVerificationStatus.PASS
    assert second.status is PaperAccountLineageVerificationStatus.PASS
    assert first.evidence == second.evidence


def test_command_accepts_genesis_only_manifest_quietly(tmp_path: Path) -> None:
    lineage = _one_edge()
    genesis_only = type(lineage)(
        lineage.genesis,
        lineage.genesis.artifact_id,
        (),
        (),
        (),
    )
    manifest = _write_manifest(tmp_path / "genesis", genesis_only)

    assert main(["--manifest", str(manifest), "--quiet"]) == 0


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    lineage = _one_edge()
    manifest = _write_manifest(tmp_path / "invalid", lineage)
    tree = json.loads(manifest.read_text(encoding="utf-8"))
    tree["unexpected"] = True
    manifest.write_text(json.dumps(tree), encoding="utf-8")

    with pytest.raises(PaperAccountLineageManifestValidationError):
        load_paper_account_lineage_manifest(manifest)


def test_manifest_rejects_directory_instead_of_regular_artifact(tmp_path: Path) -> None:
    lineage = _one_edge()
    manifest = _write_manifest(tmp_path / "unsafe", lineage)
    tree = json.loads(manifest.read_text(encoding="utf-8"))
    directory = tmp_path / "unsafe" / "directory"
    directory.mkdir()
    tree["genesis_checkpoint"]["path"] = "directory"
    manifest.write_text(json.dumps(tree), encoding="utf-8")

    with pytest.raises(PaperAccountLineageManifestReadError):
        load_paper_account_lineage_manifest(manifest)


def test_manifest_rejects_symlinked_artifact(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    lineage = _one_edge()
    manifest = _write_manifest(tmp_path / "links", lineage)
    root = manifest.parent
    link = root / "genesis-link.json"
    try:
        link.symlink_to(root / "genesis.json")
    except OSError:
        pytest.skip("symlink creation unavailable")
    tree = json.loads(manifest.read_text(encoding="utf-8"))
    tree["genesis_checkpoint"]["path"] = link.name
    manifest.write_text(json.dumps(tree), encoding="utf-8")

    with pytest.raises(PaperAccountLineageManifestReadError):
        load_paper_account_lineage_manifest(manifest)
