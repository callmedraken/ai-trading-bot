import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli import research_session_bundle
from trading_bot.cli.exceptions import (
    ResearchSessionBundleOutputError,
    ResearchSessionBundleSourceArtifactError,
    ResearchSessionBundleSourceVerificationError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_bundle import (
    create_walk_forward_research_bundle,
    relocate_walk_forward_research_session_manifest_for_bundle,
)
from trading_bot.cli.research_session_manifest import (
    CompletedResearchArtifact,
    ResearchSessionArtifactKind,
    build_walk_forward_research_session_manifest,
    serialize_walk_forward_research_session_manifest_json,
    verify_walk_forward_research_session_manifest,
)

RESULT_ID = UUID("11111111-1111-5111-8111-111111111111")
AGGREGATE_ID = UUID("22222222-2222-5222-8222-222222222222")


def _session(
    parent: Path,
    artifacts: tuple[tuple[str, ResearchSessionArtifactKind, UUID, bytes], ...] = (
        (
            "original-name.json",
            ResearchSessionArtifactKind.WALK_FORWARD_JSON,
            RESULT_ID,
            b"opaque walk-forward bytes\n",
        ),
        (
            "another.csv",
            ResearchSessionArtifactKind.AGGREGATE_CSV,
            AGGREGATE_ID,
            b'\x00,"not interpreted"\r\n',
        ),
    ),
) -> tuple[Path, tuple[Path, ...]]:
    parent.mkdir(parents=True, exist_ok=True)
    manifest_path = (parent / "source-manifest.json").resolve()
    paths = tuple((parent / name).resolve() for name, _, _, _ in artifacts)
    for path, (_, _, _, content) in zip(paths, artifacts, strict=True):
        path.write_bytes(content)
    manifest = build_walk_forward_research_session_manifest(
        manifest_path=manifest_path,
        walk_forward_config_schema_version=3,
        artifacts=tuple(
            CompletedResearchArtifact(path, kind, 1, result_id, content)
            for path, (_, kind, result_id, content) in zip(
                paths, artifacts, strict=True
            )
        ),
        session_label="portable",
    )
    manifest_path.write_text(
        serialize_walk_forward_research_session_manifest_json(manifest, pretty=True),
        encoding="utf-8",
        newline="",
    )
    return manifest_path, paths


def test_pure_relocation_preserves_ordinals_fields_and_identity(tmp_path: Path) -> None:
    manifest_path, _ = _session(tmp_path)
    raw_before = manifest_path.read_bytes()
    from trading_bot.cli.research_session_manifest import (
        load_walk_forward_research_session_manifest,
    )

    source = load_walk_forward_research_session_manifest(manifest_path)
    relocated = relocate_walk_forward_research_session_manifest_for_bundle(source)

    assert manifest_path.read_bytes() == raw_before
    assert relocated.manifest_id == source.manifest_id
    assert [item.ordinal for item in relocated.artifacts] == [1, 2]
    assert [item.path for item in relocated.artifacts] == [
        "artifacts/01-walk-forward.json",
        "artifacts/02-aggregate.csv",
    ]
    for old, new in zip(source.artifacts, relocated.artifacts, strict=True):
        assert old.ordinal == new.ordinal
        assert old.kind == new.kind
        assert old.artifact_schema_version == new.artifact_schema_version
        assert old.result_id == new.result_id
        assert old.hash_algorithm == new.hash_algorithm
        assert old.content_hash == new.content_hash
        assert old.byte_length == new.byte_length


def test_bundle_copies_exact_bytes_and_is_offline_verifiable(tmp_path: Path) -> None:
    manifest_path, source_paths = _session(tmp_path / "source")
    destination = (tmp_path / "portable").resolve()

    result = create_walk_forward_research_bundle(
        manifest_path=manifest_path,
        destination=destination,
    )

    assert result.bundle_path == destination
    assert result.verification.passed
    assert result.manifest.manifest_id == result.verification.manifest.manifest_id
    assert sorted(path.name for path in destination.iterdir()) == [
        "artifacts",
        "manifest.json",
    ]
    copied_paths = tuple(
        destination / item.bundle_relative_path for item in result.artifacts
    )
    assert [path.read_bytes() for path in copied_paths] == [
        path.read_bytes() for path in source_paths
    ]
    assert all(
        item.copied_content_hash == hashlib.sha256(path.read_bytes()).hexdigest()
        for item, path in zip(result.artifacts, copied_paths, strict=True)
    )

    for source in source_paths:
        source.unlink()
    verification = verify_walk_forward_research_session_manifest(
        result.manifest, manifest_path=destination / "manifest.json"
    )
    assert verification.passed


def test_repeat_bundles_have_identical_file_bytes(tmp_path: Path) -> None:
    manifest_path, _ = _session(tmp_path / "source")
    first = (tmp_path / "first").resolve()
    second = (tmp_path / "second").resolve()

    create_walk_forward_research_bundle(manifest_path=manifest_path, destination=first)
    create_walk_forward_research_bundle(manifest_path=manifest_path, destination=second)

    first_files = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files
    assert not json.loads(first_files["manifest.json"])[
        "walk_forward_research_session_manifest"
    ]["artifacts"][0]["path"].startswith("original")


@pytest.mark.parametrize("existing_kind", ["directory", "file", "dangling"])
def test_existing_destination_entries_are_never_replaced(
    tmp_path: Path, existing_kind: str
) -> None:
    manifest_path, _ = _session(tmp_path / "source")
    destination = (tmp_path / "destination").resolve()
    if existing_kind == "directory":
        destination.mkdir()
    elif existing_kind == "file":
        destination.write_bytes(b"keep")
    else:
        try:
            destination.symlink_to(tmp_path / "missing-target")
        except OSError:
            pytest.skip("symlink creation is unavailable")

    with pytest.raises(ResearchSessionBundleOutputError, match="already exists"):
        create_walk_forward_research_bundle(
            manifest_path=manifest_path,
            destination=destination,
        )

    if existing_kind == "dangling":
        assert destination.is_symlink()
    else:
        assert destination.exists()


def test_preexisting_staging_is_not_deleted(tmp_path: Path) -> None:
    manifest_path, _ = _session(tmp_path / "source")
    destination = (tmp_path / "destination").resolve()
    staging = tmp_path / ".destination.staging"
    staging.mkdir()
    marker = staging / "owned-by-someone-else"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(ResearchSessionBundleOutputError, match="staging"):
        create_walk_forward_research_bundle(
            manifest_path=manifest_path,
            destination=destination,
        )

    assert marker.read_text(encoding="utf-8") == "keep"


def test_failed_source_verification_creates_no_staging(tmp_path: Path) -> None:
    manifest_path, source_paths = _session(tmp_path / "source")
    source_paths[0].write_bytes(b"changed length")
    destination = (tmp_path / "destination").resolve()

    with pytest.raises(ResearchSessionBundleSourceVerificationError):
        create_walk_forward_research_bundle(
            manifest_path=manifest_path,
            destination=destination,
        )

    assert not destination.exists()
    assert not (tmp_path / ".destination.staging").exists()


def test_copy_revalidates_source_and_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path, source_paths = _session(tmp_path / "source")
    destination = (tmp_path / "destination").resolve()

    def mutate_after_verification(manifest):
        relocated = relocate_walk_forward_research_session_manifest_for_bundle(manifest)
        source_paths[0].write_bytes(b"mutated after verification")
        return relocated

    monkeypatch.setattr(
        research_session_bundle,
        "relocate_walk_forward_research_session_manifest_for_bundle",
        mutate_after_verification,
    )

    with pytest.raises(ResearchSessionBundleSourceArtifactError):
        create_walk_forward_research_bundle(
            manifest_path=manifest_path,
            destination=destination,
        )

    assert not destination.exists()
    assert not (tmp_path / ".destination.staging").exists()


def test_staged_manifest_reload_failure_is_bundle_output_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path, _ = _session(tmp_path / "source")
    destination = (tmp_path / "destination").resolve()
    original_load = research_session_bundle.load_walk_forward_research_session_manifest
    calls = 0

    def fail_second_load(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ResearchSessionManifestReadError("staged failure")
        return original_load(path)

    monkeypatch.setattr(
        research_session_bundle,
        "load_walk_forward_research_session_manifest",
        fail_second_load,
    )

    with pytest.raises(ResearchSessionBundleOutputError, match="reload or verify"):
        create_walk_forward_research_bundle(
            manifest_path=manifest_path,
            destination=destination,
        )

    assert not destination.exists()
    assert not (tmp_path / ".destination.staging").exists()


def test_cleanup_failure_preserves_primary_source_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path, source_paths = _session(tmp_path / "source")
    destination = (tmp_path / "destination").resolve()

    def mutate_after_verification(manifest):
        relocated = relocate_walk_forward_research_session_manifest_for_bundle(manifest)
        source_paths[0].write_bytes(b"mutated after verification")
        return relocated

    monkeypatch.setattr(
        research_session_bundle,
        "relocate_walk_forward_research_session_manifest_for_bundle",
        mutate_after_verification,
    )
    monkeypatch.setattr(
        research_session_bundle,
        "_cleanup_staging",
        lambda path: f"could not remove staging directory: {path}",
    )

    with pytest.raises(ResearchSessionBundleOutputError) as caught:
        create_walk_forward_research_bundle(
            manifest_path=manifest_path,
            destination=destination,
        )

    assert isinstance(
        caught.value.primary_error, ResearchSessionBundleSourceArtifactError
    )
    assert caught.value.cleanup_message is not None
