import hashlib
import io
import tarfile
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli import research_session_archive
from trading_bot.cli.exceptions import (
    ResearchSessionArchiveArgumentError,
    ResearchSessionArchiveByteLengthMismatchError,
    ResearchSessionArchiveHashMismatchError,
    ResearchSessionArchiveOutputError,
    ResearchSessionArchiveSourceEntryError,
    ResearchSessionArchiveStructureError,
)
from trading_bot.cli.research_session_archive import (
    USTAR_BLOCK_SIZE,
    CanonicalUstarEntry,
    ResearchSessionArchiveEntryEvidence,
    build_canonical_ustar_header,
    create_walk_forward_research_bundle_archive,
    stream_canonical_walk_forward_research_bundle_archive,
    verify_walk_forward_research_bundle_archive,
)
from trading_bot.cli.research_session_bundle import (
    create_walk_forward_research_bundle,
)
from trading_bot.cli.research_session_manifest import (
    CompletedResearchArtifact,
    ResearchSessionArtifactKind,
    ResearchSessionArtifactVerificationStatus,
    build_walk_forward_research_session_manifest,
    serialize_walk_forward_research_session_manifest_json,
)

WALK_ID = UUID("11111111-1111-5111-8111-111111111111")
AGGREGATE_ID = UUID("22222222-2222-5222-8222-222222222222")


def _bundle(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    artifacts = (
        CompletedResearchArtifact(
            (source / "original.json").resolve(),
            ResearchSessionArtifactKind.WALK_FORWARD_JSON,
            1,
            WALK_ID,
            b"exact walk bytes\n",
        ),
        CompletedResearchArtifact(
            (source / "aggregate.csv").resolve(),
            ResearchSessionArtifactKind.AGGREGATE_CSV,
            1,
            AGGREGATE_ID,
            b'\x00,"opaque"\r\n',
        ),
    )
    for artifact in artifacts:
        artifact.destination.write_bytes(artifact.content)
    manifest_path = (source / "source-manifest.json").resolve()
    manifest = build_walk_forward_research_session_manifest(
        manifest_path=manifest_path,
        walk_forward_config_schema_version=3,
        artifacts=artifacts,
        session_label="archive-golden",
    )
    manifest_path.write_text(
        serialize_walk_forward_research_session_manifest_json(manifest),
        encoding="utf-8",
        newline="",
    )
    bundle = (tmp_path / "bundle").resolve()
    create_walk_forward_research_bundle(
        manifest_path=manifest_path,
        destination=bundle,
    )
    return bundle


def test_canonical_header_has_exact_fields_and_checksum() -> None:
    header = build_canonical_ustar_header("manifest.json", 17)

    assert len(header) == USTAR_BLOCK_SIZE
    assert header[0:100] == b"manifest.json" + bytes(87)
    assert header[100:108] == b"0000644\0"
    assert header[108:116] == b"0000000\0"
    assert header[116:124] == b"0000000\0"
    assert header[124:136] == b"00000000021\0"
    assert header[136:148] == b"00000000000\0"
    assert header[156:157] == b"0"
    assert header[257:263] == b"ustar\0"
    assert header[263:265] == b"00"
    checksum_header = bytearray(header)
    stored = int(header[148:154], 8)
    checksum_header[148:156] = b" " * 8
    assert stored == sum(checksum_header)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute",
        "./dot",
        "../parent",
        "a/../b",
        "a\\b",
        "unicod\u00e9",
        "a//b",
    ],
)
def test_canonical_header_rejects_unsafe_names(path: str) -> None:
    with pytest.raises(ResearchSessionArchiveStructureError):
        build_canonical_ustar_header(path, 1)


def test_archive_is_reproducible_streamed_and_standard_readable(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    first_parent = tmp_path / "first"
    second_parent = tmp_path / "second"
    first_parent.mkdir()
    second_parent.mkdir()

    first = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=first_parent,
    )
    second = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=second_parent,
    )

    first_bytes = first.archive_path.read_bytes()
    assert first_bytes == second.archive_path.read_bytes()
    assert first.archive_sha256 == second.archive_sha256
    assert first.archive_byte_length == len(first_bytes)
    assert first.archive_sha256 == hashlib.sha256(first_bytes).hexdigest()
    assert first.verification.archive_path == first.archive_path
    assert first_bytes[-1024:] == bytes(1024)
    assert len(first_bytes) % USTAR_BLOCK_SIZE == 0
    with tarfile.open(fileobj=io.BytesIO(first_bytes), mode="r:") as archive:
        assert archive.getnames() == [
            "manifest.json",
            "artifacts/01-walk-forward.json",
            "artifacts/02-aggregate.csv",
        ]
        assert all(item.isfile() for item in archive.getmembers())

    verified = verify_walk_forward_research_bundle_archive(
        archive_path=first.archive_path,
        expected_sha256=first.archive_sha256,
        expected_byte_length=first.archive_byte_length,
    )
    assert verified.passed
    assert verified.manifest.manifest_id == first.manifest_id


def test_golden_archive_length_and_sha256(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()

    result = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )

    assert result.archive_byte_length == 5120
    assert result.archive_sha256 == (
        "12d33bf0b7b614c18aae3627daf76aee5575c5f3e390d9ffaed352c5f5bb0359"
    )


def test_public_stream_reader_preserves_verifier_behavior(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()
    archive = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )
    started: list[CanonicalUstarEntry] = []
    finished: list[ResearchSessionArchiveEntryEvidence] = []
    chunks: list[tuple[str, int]] = []

    class Consumer:
        def start_entry(self, entry: CanonicalUstarEntry) -> None:
            started.append(entry)

        def consume_payload_chunk(
            self, entry: CanonicalUstarEntry, chunk: bytes
        ) -> None:
            chunks.append((entry.path, len(chunk)))

        def finish_entry(
            self,
            entry: CanonicalUstarEntry,
            evidence: ResearchSessionArchiveEntryEvidence,
            manifest,
        ) -> None:
            finished.append(evidence)

    direct = stream_canonical_walk_forward_research_bundle_archive(
        archive_path=archive.archive_path,
        expected_sha256=archive.archive_sha256,
        expected_byte_length=archive.archive_byte_length,
        consumer=Consumer(),
    )
    wrapped = verify_walk_forward_research_bundle_archive(
        archive_path=archive.archive_path,
        expected_sha256=archive.archive_sha256,
        expected_byte_length=archive.archive_byte_length,
    )

    assert direct == wrapped
    assert tuple(item.path for item in started) == tuple(
        item.path for item in wrapped.entries
    )
    assert tuple(finished) == wrapped.entries
    assert chunks
    assert all(0 < size <= 64 * 1024 for _, size in chunks)


def test_outer_evidence_mismatches_are_distinct(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()
    result = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )

    with pytest.raises(ResearchSessionArchiveByteLengthMismatchError):
        verify_walk_forward_research_bundle_archive(
            archive_path=result.archive_path,
            expected_byte_length=result.archive_byte_length + 1,
        )
    with pytest.raises(ResearchSessionArchiveHashMismatchError):
        verify_walk_forward_research_bundle_archive(
            archive_path=result.archive_path,
            expected_sha256="0" * 64,
        )


def test_expected_evidence_is_validated_before_archive_open(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.tar"
    with pytest.raises(ResearchSessionArchiveArgumentError):
        verify_walk_forward_research_bundle_archive(
            archive_path=missing,
            expected_sha256="INVALID",
        )
    with pytest.raises(ResearchSessionArchiveArgumentError):
        verify_walk_forward_research_bundle_archive(
            archive_path=missing,
            expected_byte_length=-1,
        )


def test_noncanonical_padding_and_trailing_data_are_rejected(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()
    result = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )
    original = result.archive_path.read_bytes()

    result.archive_path.write_bytes(original + bytes(512))
    with pytest.raises(ResearchSessionArchiveStructureError, match="trailing"):
        verify_walk_forward_research_bundle_archive(archive_path=result.archive_path)


def test_noncanonical_header_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()
    result = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )
    changed = bytearray(result.archive_path.read_bytes())
    changed[156] = ord("2")
    result.archive_path.write_bytes(changed)

    with pytest.raises(ResearchSessionArchiveStructureError, match="canonical"):
        verify_walk_forward_research_bundle_archive(archive_path=result.archive_path)


def test_header_length_and_payload_hash_mismatches_are_distinct(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()
    result = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )
    original = result.archive_path.read_bytes()
    manifest_length = result.verification.entries[0].byte_length
    artifact_header = 512 + manifest_length + (-manifest_length % 512)
    artifact = result.verification.manifest.artifacts[0]

    wrong_header = build_canonical_ustar_header(artifact.path, artifact.byte_length + 1)
    changed = bytearray(original)
    changed[artifact_header : artifact_header + 512] = wrong_header
    result.archive_path.write_bytes(changed)
    with pytest.raises(ResearchSessionArchiveByteLengthMismatchError):
        verify_walk_forward_research_bundle_archive(archive_path=result.archive_path)

    changed = bytearray(original)
    changed[artifact_header + 512] ^= 1
    result.archive_path.write_bytes(changed)
    with pytest.raises(ResearchSessionArchiveHashMismatchError):
        verify_walk_forward_research_bundle_archive(archive_path=result.archive_path)


def test_unexpected_bundle_entry_fails_before_staging(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "unexpected.txt").write_bytes(b"unexpected")
    destination = tmp_path / "archives"
    destination.mkdir()

    with pytest.raises(ResearchSessionArchiveStructureError, match="layout"):
        create_walk_forward_research_bundle_archive(
            bundle_path=bundle,
            destination_directory=destination,
        )

    assert tuple(destination.iterdir()) == ()


def test_existing_archive_and_staging_are_never_replaced(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()
    first = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )
    original = first.archive_path.read_bytes()

    with pytest.raises(ResearchSessionArchiveOutputError, match="already exists"):
        create_walk_forward_research_bundle_archive(
            bundle_path=bundle,
            destination_directory=destination,
        )
    assert first.archive_path.read_bytes() == original

    first.archive_path.unlink()
    staging = destination / f".{first.archive_path.name}.staging"
    staging.write_bytes(b"keep")
    with pytest.raises(ResearchSessionArchiveOutputError, match="staging"):
        create_walk_forward_research_bundle_archive(
            bundle_path=bundle,
            destination_directory=destination,
        )
    assert staging.read_bytes() == b"keep"


def test_copy_failure_cleans_only_created_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()

    def fail_copy(*args, **kwargs):
        raise ResearchSessionArchiveSourceEntryError(
            "manifest.json",
            ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
        )

    monkeypatch.setattr(research_session_archive, "_write_source_entry", fail_copy)
    with pytest.raises(ResearchSessionArchiveSourceEntryError):
        create_walk_forward_research_bundle_archive(
            bundle_path=bundle,
            destination_directory=destination,
        )
    assert tuple(destination.iterdir()) == ()


def test_cleanup_failure_retains_primary_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()

    def fail_copy(*args, **kwargs):
        raise ResearchSessionArchiveSourceEntryError(
            "manifest.json",
            ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO,
        )

    monkeypatch.setattr(research_session_archive, "_write_source_entry", fail_copy)
    monkeypatch.setattr(
        research_session_archive,
        "_cleanup_staging",
        lambda path: f"could not remove archive staging file: {path}",
    )
    with pytest.raises(ResearchSessionArchiveOutputError) as caught:
        create_walk_forward_research_bundle_archive(
            bundle_path=bundle,
            destination_directory=destination,
        )
    assert isinstance(
        caught.value.primary_error, ResearchSessionArchiveSourceEntryError
    )
    assert caught.value.cleanup_message is not None
