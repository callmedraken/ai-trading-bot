"""Focused tests for the pre-cutover project-history archive utility."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import archive_project_history as archive


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _make_repository(
    root: Path,
    *,
    handoff: bytes | None = "handoff\r\n📌\r\n".encode(),
    status: bytes | None = "status\n📊\n".encode(),
    gitattributes: bytes | None = b"docs/history/legacy/** -text\n",
) -> Path:
    repository = root / "repository"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Archive Test")
    _git(repository, "config", "user.email", "archive-test@example.invalid")
    _git(repository, "config", "core.autocrlf", "false")

    history = repository / "docs" / "history"
    history.mkdir(parents=True)
    if gitattributes is not None:
        (repository / ".gitattributes").write_bytes(gitattributes)
    if handoff is not None:
        handoff_path = repository / archive.CANONICAL_SOURCE_PATHS[0]
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_bytes(handoff)
    if status is not None:
        status_path = repository / archive.CANONICAL_SOURCE_PATHS[1]
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_bytes(status)
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "archive utility fixture")
    return repository


def test_dry_run_is_read_only_and_reports_raw_measurements(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = _make_repository(tmp_path)
    source_bytes = {
        path: (repository / path).read_bytes()
        for path in archive.CANONICAL_SOURCE_PATHS
    }

    inventory = archive.inspect_repository(repository, cutover_id="HIST-2A")
    assert (
        archive.main(
            [
                "--dry-run",
                "--cutover-id",
                "HIST-2A",
                "--repo-root",
                str(repository),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out

    assert not (repository / archive.LEGACY_ROOT).exists()
    assert "PROPOSED DESTINATION docs/history/legacy/HIST-2A" in output
    assert "LINES" in output
    assert "NO WRITES" in output
    assert [record.source_path for record in inventory.files] == [
        path.as_posix() for path in archive.CANONICAL_SOURCE_PATHS
    ]
    assert [record.data for record in inventory.files] == list(source_bytes.values())
    assert inventory.destination == repository / archive.LEGACY_ROOT / "HIST-2A"
    for record in inventory.files:
        assert record.byte_count == len(record.data)
        assert record.sha256 == hashlib.sha256(record.data).hexdigest()
        assert record.line_count == len(record.data.splitlines())


def test_dry_run_without_cutover_id_uses_lexical_placeholder(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _make_repository(tmp_path)
    original_resolve = Path.resolve

    def reject_placeholder_resolve(path: Path, *args: object, **kwargs: object) -> Path:
        if path.name == "<cutover-id>":
            raise AssertionError("synthetic placeholder must not be resolved")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", reject_placeholder_resolve)

    assert archive.main(["--dry-run", "--repo-root", str(repository)]) == 0
    output = capsys.readouterr().out

    assert "PROPOSED DESTINATION docs/history/legacy/<cutover-id>/" in output
    assert "NO WRITES" in output
    assert not (repository / archive.LEGACY_ROOT).exists()


def test_inventory_rejects_source_dirtied_during_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _make_repository(tmp_path)
    original_record = archive._record_source

    def dirty_after_capture(root: Path, relative_path: Path) -> archive.SourceRecord:
        record = original_record(root, relative_path)
        if relative_path == archive.CANONICAL_SOURCE_PATHS[0]:
            (root / relative_path).write_bytes(record.data + b"late change")
        return record

    monkeypatch.setattr(archive, "_record_source", dirty_after_capture)

    with pytest.raises(archive.ArchiveError, match="repository is dirty"):
        archive.inspect_repository(repository, cutover_id="HIST-2A")

    assert not (repository / archive.LEGACY_ROOT).exists()


def test_inventory_rejects_head_tree_change_during_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _make_repository(tmp_path)
    original_identity = archive._read_repository_identity
    calls = 0

    def moving_identity(root: Path) -> archive.RepositoryIdentity:
        nonlocal calls
        calls += 1
        identity = original_identity(root)
        if calls == 2:
            return archive.RepositoryIdentity(
                head=identity.head,
                tree="0" * 40,
            )
        return identity

    monkeypatch.setattr(archive, "_read_repository_identity", moving_identity)

    with pytest.raises(archive.ArchiveError, match="inventory capture"):
        archive.inspect_repository(repository, cutover_id="HIST-2A")


def test_archive_preserves_exact_bytes_and_records_manifest_identity(
    tmp_path: Path,
) -> None:
    repository = _make_repository(
        tmp_path,
        handoff=b"caf\xc3\xa9\r\nraw\x00bytes\r\n",
        status=b"line one\r\nline two\r\n",
    )
    original = {
        path: (repository / path).read_bytes()
        for path in archive.CANONICAL_SOURCE_PATHS
    }
    archive_paths = tuple(
        (archive.LEGACY_ROOT / "HIST-2A" / path.name).as_posix()
        for path in archive.CANONICAL_SOURCE_PATHS
    ) + ((archive.LEGACY_ROOT / "HIST-2A" / archive.MANIFEST_NAME).as_posix(),)
    assert _git(
        repository, "check-attr", "text", "--", *archive_paths
    ).splitlines() == [f"{path}: text: unset" for path in archive_paths]

    result = archive.archive_repository(repository, "HIST-2A")

    for path, data in original.items():
        assert (repository / path).read_bytes() == data
        archived = result.destination / Path(path).name
        assert archived.read_bytes() == data
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == archive.MANIFEST_SCHEMA
    assert manifest["version"] == archive.MANIFEST_VERSION
    assert manifest["cutover_id"] == "HIST-2A"
    assert manifest["source_head"] == _git(repository, "rev-parse", "HEAD")
    assert manifest["source_tree"] == _git(repository, "rev-parse", "HEAD^{tree}")
    assert manifest["files"] == [
        {
            "source_path": path.as_posix(),
            "archive_path": (archive.LEGACY_ROOT / "HIST-2A" / path.name).as_posix(),
            "byte_count": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for path, data in original.items()
    ]


def test_archive_requires_legacy_paths_to_be_explicitly_non_text(
    tmp_path: Path,
) -> None:
    repository = _make_repository(tmp_path, gitattributes=None)

    with pytest.raises(archive.ArchiveError, match="text normalization"):
        archive.archive_repository(repository, "HIST-2A")

    assert not (repository / archive.LEGACY_ROOT / "HIST-2A").exists()


def test_archive_rejects_conflicting_text_attribute_before_writes(
    tmp_path: Path,
) -> None:
    repository = _make_repository(
        tmp_path,
        gitattributes=(
            b"docs/history/legacy/** -text\n"
            b"docs/history/legacy/HIST-2A/PROJECT_STATUS.md text\n"
        ),
    )

    with pytest.raises(archive.ArchiveError, match="text normalization"):
        archive.archive_repository(repository, "HIST-2A")

    assert not (repository / archive.LEGACY_ROOT / "HIST-2A").exists()


def test_archive_rejects_repository_dirtied_before_final_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _make_repository(tmp_path)
    original_manifest = archive._manifest_bytes

    def dirty_before_manifest(
        cutover_id: str,
        identity: archive.RepositoryIdentity,
        records: tuple[archive.SourceRecord, ...],
    ) -> bytes:
        manifest = original_manifest(cutover_id, identity, records)
        (repository / "late-dirty-file.txt").write_bytes(b"unexpected")
        return manifest

    monkeypatch.setattr(archive, "_manifest_bytes", dirty_before_manifest)

    with pytest.raises(archive.ArchiveError, match="repository is dirty"):
        archive.archive_repository(repository, "HIST-2A")

    assert not (repository / archive.LEGACY_ROOT / "HIST-2A").exists()


def test_archive_rejects_head_tree_change_before_final_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _make_repository(tmp_path)
    original_identity = archive._read_repository_identity
    calls = 0

    def moving_identity(root: Path) -> archive.RepositoryIdentity:
        nonlocal calls
        calls += 1
        identity = original_identity(root)
        if calls == 3:
            return archive.RepositoryIdentity(
                head="0" * 40,
                tree=identity.tree,
            )
        return identity

    monkeypatch.setattr(archive, "_read_repository_identity", moving_identity)

    with pytest.raises(archive.ArchiveError, match="during archive"):
        archive.archive_repository(repository, "HIST-2A")

    assert not (repository / archive.LEGACY_ROOT / "HIST-2A").exists()


@pytest.mark.parametrize(
    "cutover_id",
    [
        "",
        ".",
        "..",
        "../escape",
        r"..\escape",
        "nested/id",
        "C:escape",
        "-starts-with-punctuation",
        "has space",
        "a" * 65,
    ],
)
def test_malformed_cutover_ids_are_rejected(cutover_id: str) -> None:
    with pytest.raises(archive.ArchiveError, match="malformed cutover"):
        archive.validate_cutover_id(cutover_id)


def test_traversal_id_cannot_place_archive_outside_legacy_root(tmp_path: Path) -> None:
    repository = _make_repository(tmp_path)

    with pytest.raises(archive.ArchiveError, match="malformed cutover"):
        archive.archive_repository(repository, "../outside")

    assert not (repository / "docs" / "history" / "outside").exists()
    assert not (repository / "docs" / "outside").exists()


def test_existing_destination_is_rejected_without_overwrite(tmp_path: Path) -> None:
    repository = _make_repository(tmp_path)
    destination = repository / archive.LEGACY_ROOT / "HIST-2A"
    destination.mkdir(parents=True)
    sentinel = destination / "sentinel.txt"
    sentinel.write_bytes(b"keep me")
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "existing archive fixture")

    with pytest.raises(archive.ArchiveError, match="already exists"):
        archive.archive_repository(repository, "HIST-2A")

    assert sentinel.read_bytes() == b"keep me"
    assert not (destination / "manifest.json").exists()


def test_copy_verification_failure_does_not_leave_a_partial_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _make_repository(tmp_path)
    original_write = archive._write_exclusive

    def corrupt_first_source(path: Path, data: bytes) -> None:
        if path.name == Path(archive.CANONICAL_SOURCE_PATHS[0]).name:
            original_write(path, b"corrupted")
        else:
            original_write(path, data)

    monkeypatch.setattr(archive, "_write_exclusive", corrupt_first_source)

    with pytest.raises(archive.ArchiveError, match="verification failed"):
        archive.archive_repository(repository, "HIST-2A")

    assert not (repository / archive.LEGACY_ROOT / "HIST-2A").exists()


def test_missing_source_fails_before_any_archive_write(tmp_path: Path) -> None:
    repository = _make_repository(tmp_path, status=None)

    with pytest.raises(archive.ArchiveError, match="missing canonical source"):
        archive.archive_repository(repository, "HIST-2A")

    assert not (repository / archive.LEGACY_ROOT / "HIST-2A").exists()


def test_dirty_repository_is_rejected_before_archive_write(tmp_path: Path) -> None:
    repository = _make_repository(tmp_path)
    (repository / archive.CANONICAL_SOURCE_PATHS[0]).write_bytes(b"changed")

    with pytest.raises(archive.ArchiveError, match="repository is dirty"):
        archive.archive_repository(repository, "HIST-2A")

    assert not (repository / archive.LEGACY_ROOT / "HIST-2A").exists()
