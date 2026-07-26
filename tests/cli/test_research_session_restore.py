import shutil
from pathlib import Path

import pytest
from tests.cli.test_research_session_archive import _bundle

from trading_bot.cli import research_session_restore
from trading_bot.cli.exceptions import (
    ResearchSessionArchiveArgumentError,
    ResearchSessionArchiveHashMismatchError,
    ResearchSessionArchiveStructureError,
    ResearchSessionRestoreOutputError,
)
from trading_bot.cli.research_session_archive import (
    create_walk_forward_research_bundle_archive,
)
from trading_bot.cli.research_session_manifest import (
    load_walk_forward_research_session_manifest,
    serialize_walk_forward_research_session_manifest_json,
    verify_walk_forward_research_session_manifest,
)
from trading_bot.cli.research_session_restore import (
    ResearchSessionArchiveRestoreEntryEvidence,
    restore_walk_forward_research_bundle_archive,
)


def _archive(tmp_path: Path):
    bundle = _bundle(tmp_path)
    archive_directory = tmp_path / "archives"
    archive_directory.mkdir()
    archive = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=archive_directory,
    )
    return bundle, archive


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_restore_preserves_exact_bytes_identity_and_offline_verification(
    tmp_path: Path,
) -> None:
    bundle, archive = _archive(tmp_path)
    expected_bytes = _tree_bytes(bundle)
    source_manifest_bytes = (bundle / "manifest.json").read_bytes()
    shutil.rmtree(bundle)
    destination = tmp_path / "restored"

    result = restore_walk_forward_research_bundle_archive(
        archive_path=archive.archive_path,
        destination=destination,
        expected_sha256=archive.archive_sha256,
        expected_byte_length=archive.archive_byte_length,
    )

    assert result.bundle_path == destination.resolve()
    assert result.manifest_path.read_bytes() == source_manifest_bytes
    assert _tree_bytes(result.bundle_path) == expected_bytes
    assert result.manifest.manifest_id == archive.manifest_id
    assert result.archive_verification.manifest == result.manifest
    assert result.verification.passed
    assert tuple(item.position for item in result.entries) == (1, 2, 3)
    assert tuple(path.name for path in result.bundle_path.iterdir()) == (
        "artifacts",
        "manifest.json",
    )
    loaded = load_walk_forward_research_session_manifest(result.manifest_path)
    assert loaded == result.manifest
    assert verify_walk_forward_research_session_manifest(
        loaded, manifest_path=result.manifest_path
    ).passed


def test_restore_does_not_reserialize_embedded_manifest(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = load_walk_forward_research_session_manifest(manifest_path)
    pretty_bytes = serialize_walk_forward_research_session_manifest_json(
        manifest, pretty=True
    ).encode("utf-8")
    manifest_path.write_bytes(pretty_bytes)
    archive_directory = tmp_path / "archives"
    archive_directory.mkdir()
    archive = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=archive_directory,
    )

    restored = restore_walk_forward_research_bundle_archive(
        archive_path=archive.archive_path,
        destination=tmp_path / "restored",
    )

    assert restored.manifest_path.read_bytes() == pretty_bytes


def test_expected_evidence_is_validated_before_archive_open(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "restored"

    with pytest.raises(ResearchSessionArchiveArgumentError):
        restore_walk_forward_research_bundle_archive(
            archive_path=tmp_path / "missing.tar",
            destination=destination,
            expected_sha256="INVALID",
        )

    assert not destination.exists()
    assert not (tmp_path / ".restored.staging").exists()


def test_invalid_archive_fails_before_staging_exists(tmp_path: Path) -> None:
    _, archive = _archive(tmp_path)
    archive.archive_path.write_bytes(archive.archive_path.read_bytes() + bytes(512))
    destination = tmp_path / "restored"

    with pytest.raises(ResearchSessionArchiveStructureError, match="trailing"):
        restore_walk_forward_research_bundle_archive(
            archive_path=archive.archive_path,
            destination=destination,
        )

    assert not destination.exists()
    assert not (tmp_path / ".restored.staging").exists()


def test_existing_destination_and_staging_are_never_changed(
    tmp_path: Path,
) -> None:
    _, archive = _archive(tmp_path)
    destination = tmp_path / "restored"
    destination.mkdir()
    retained = destination / "keep.txt"
    retained.write_bytes(b"keep")

    with pytest.raises(ResearchSessionRestoreOutputError, match="already exists"):
        restore_walk_forward_research_bundle_archive(
            archive_path=archive.archive_path,
            destination=destination,
        )
    assert retained.read_bytes() == b"keep"

    shutil.rmtree(destination)
    staging = tmp_path / ".restored.staging"
    staging.write_bytes(b"keep staging")
    with pytest.raises(ResearchSessionRestoreOutputError, match="staging"):
        restore_walk_forward_research_bundle_archive(
            archive_path=archive.archive_path,
            destination=destination,
        )
    assert staging.read_bytes() == b"keep staging"


def test_symlink_destination_parent_and_dangling_staging_are_rejected(
    tmp_path: Path,
) -> None:
    _, archive = _archive(tmp_path)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(ResearchSessionRestoreOutputError, match="parent"):
        restore_walk_forward_research_bundle_archive(
            archive_path=archive.archive_path,
            destination=linked_parent / "restored",
        )
    assert tuple(real_parent.iterdir()) == ()

    destination = tmp_path / "restored"
    staging = tmp_path / ".restored.staging"
    staging.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(ResearchSessionRestoreOutputError, match="staging"):
        restore_walk_forward_research_bundle_archive(
            archive_path=archive.archive_path,
            destination=destination,
        )
    assert staging.is_symlink()


def test_archive_mutation_between_passes_fails_closed_and_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, archive = _archive(tmp_path)
    destination = tmp_path / "restored"
    original_stream = (
        research_session_restore.stream_canonical_walk_forward_research_bundle_archive
    )

    def mutate_then_stream(**kwargs):
        changed = bytearray(archive.archive_path.read_bytes())
        manifest_length = archive.verification.entries[0].byte_length
        artifact_payload = 512 + manifest_length + (-manifest_length % 512) + 512
        changed[artifact_payload] ^= 1
        archive.archive_path.write_bytes(changed)
        return original_stream(**kwargs)

    monkeypatch.setattr(
        research_session_restore,
        "stream_canonical_walk_forward_research_bundle_archive",
        mutate_then_stream,
    )

    with pytest.raises(ResearchSessionArchiveHashMismatchError):
        restore_walk_forward_research_bundle_archive(
            archive_path=archive.archive_path,
            destination=destination,
        )
    assert not destination.exists()
    assert not (tmp_path / ".restored.staging").exists()


def test_cleanup_failure_preserves_primary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, archive = _archive(tmp_path)
    destination = tmp_path / "restored"

    def fail_second_pass(**kwargs):
        raise ResearchSessionArchiveHashMismatchError("changed archive")

    monkeypatch.setattr(
        research_session_restore,
        "stream_canonical_walk_forward_research_bundle_archive",
        fail_second_pass,
    )
    monkeypatch.setattr(
        research_session_restore,
        "_cleanup_staging",
        lambda path, identity: "cleanup failed",
    )

    with pytest.raises(ResearchSessionRestoreOutputError) as caught:
        restore_walk_forward_research_bundle_archive(
            archive_path=archive.archive_path,
            destination=destination,
        )
    assert isinstance(
        caught.value.primary_error, ResearchSessionArchiveHashMismatchError
    )
    assert caught.value.cleanup_message == "cleanup failed"
    assert not destination.exists()


def test_restore_entry_position_rejects_bool() -> None:
    with pytest.raises(TypeError, match="exact positive integer"):
        ResearchSessionArchiveRestoreEntryEvidence(
            position=True,
            path="manifest.json",
            byte_length=1,
            sha256="0" * 64,
        )
