import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli.exceptions import (
    ResearchSessionManifestError,
    ResearchSessionManifestVerificationError,
)
from trading_bot.cli.research_session_manifest import (
    CompletedResearchArtifact,
    ResearchSessionArtifactKind,
    build_walk_forward_research_session_manifest,
    serialize_walk_forward_research_session_manifest_json,
    verify_walk_forward_research_session_manifest,
)
from trading_bot.portfolio import MetadataEntry

WALK_ID = UUID("11111111-1111-5111-8111-111111111111")
AGGREGATE_ID = UUID("22222222-2222-5222-8222-222222222222")


def _descriptor(
    destination: Path,
    kind: ResearchSessionArtifactKind,
    result_id: UUID = WALK_ID,
    content: bytes = b"exact artifact\n",
) -> CompletedResearchArtifact:
    return CompletedResearchArtifact(destination, kind, 1, result_id, content)


def test_manifest_hashes_exact_bytes_and_has_relocatable_identity(
    tmp_path: Path,
) -> None:
    first_parent = (tmp_path / "first").resolve()
    second_parent = (tmp_path / "second").resolve()
    first_parent.mkdir()
    second_parent.mkdir()
    first_artifacts = (
        _descriptor(
            first_parent / "walk.json",
            ResearchSessionArtifactKind.WALK_FORWARD_JSON,
        ),
        _descriptor(
            first_parent / "walk.csv",
            ResearchSessionArtifactKind.WALK_FORWARD_CSV,
            content=b'a,"b"\r\n',
        ),
        _descriptor(
            first_parent / "aggregate.json",
            ResearchSessionArtifactKind.AGGREGATE_JSON,
            AGGREGATE_ID,
        ),
    )
    second_artifacts = tuple(
        CompletedResearchArtifact(
            second_parent / item.destination.name,
            item.kind,
            item.artifact_schema_version,
            item.result_id,
            item.content,
        )
        for item in first_artifacts
    )
    metadata = (MetadataEntry("purpose", "reconciliation"),)
    first = build_walk_forward_research_session_manifest(
        manifest_path=first_parent / "manifest.json",
        walk_forward_config_schema_version=3,
        artifacts=first_artifacts,
        session_label="session",
        metadata=metadata,
    )
    second = build_walk_forward_research_session_manifest(
        manifest_path=second_parent / "manifest.json",
        walk_forward_config_schema_version=3,
        artifacts=second_artifacts,
        session_label="session",
        metadata=metadata,
    )

    assert first.manifest_id == second.manifest_id
    assert first.walk_forward_result_id == WALK_ID
    assert first.aggregate_result_id == AGGREGATE_ID
    assert first.stability_result_id is None
    assert [item.path for item in first.artifacts] == [
        "walk.json",
        "walk.csv",
        "aggregate.json",
    ]
    assert first.artifacts[1].byte_length == len(b'a,"b"\r\n')
    assert first.artifacts[1].content_hash == hashlib.sha256(b'a,"b"\r\n').hexdigest()

    compact = serialize_walk_forward_research_session_manifest_json(first)
    pretty = serialize_walk_forward_research_session_manifest_json(first, pretty=True)
    assert json.loads(compact) == json.loads(pretty)
    assert str(first.manifest_id) in compact
    assert str(first.manifest_id) in pretty
    assert compact.endswith("\n")
    assert pretty.endswith("\n")


def test_builder_enforces_exact_types_order_families_and_metadata(
    tmp_path: Path,
) -> None:
    parent = tmp_path.resolve()
    walk = _descriptor(
        parent / "walk.json", ResearchSessionArtifactKind.WALK_FORWARD_JSON
    )
    aggregate = _descriptor(
        parent / "aggregate.json",
        ResearchSessionArtifactKind.AGGREGATE_JSON,
        AGGREGATE_ID,
    )
    with pytest.raises(ResearchSessionManifestError, match="positive integer"):
        CompletedResearchArtifact(
            parent / "bad.json",
            ResearchSessionArtifactKind.WALK_FORWARD_JSON,
            True,
            WALK_ID,
            b"x",
        )
    with pytest.raises(ResearchSessionManifestError, match="canonical"):
        build_walk_forward_research_session_manifest(
            manifest_path=parent / "manifest.json",
            walk_forward_config_schema_version=3,
            artifacts=(aggregate, walk),
        )
    with pytest.raises(ResearchSessionManifestError, match="one result ID"):
        build_walk_forward_research_session_manifest(
            manifest_path=parent / "manifest.json",
            walk_forward_config_schema_version=3,
            artifacts=(
                walk,
                _descriptor(
                    parent / "walk.csv",
                    ResearchSessionArtifactKind.WALK_FORWARD_CSV,
                    AGGREGATE_ID,
                ),
            ),
        )
    with pytest.raises(ResearchSessionManifestError, match="reserved"):
        build_walk_forward_research_session_manifest(
            manifest_path=parent / "manifest.json",
            walk_forward_config_schema_version=3,
            artifacts=(walk,),
            metadata=(
                MetadataEntry("walk_forward_research_session_manifest_bad", "x"),
            ),
        )


def test_offline_verification_reads_only_exact_artifact_bytes(tmp_path: Path) -> None:
    parent = tmp_path.resolve()
    destination = parent / "walk.json"
    content = b"not parsed as json\n"
    destination.write_bytes(content)
    manifest = build_walk_forward_research_session_manifest(
        manifest_path=parent / "manifest.json",
        walk_forward_config_schema_version=1,
        artifacts=(
            _descriptor(
                destination,
                ResearchSessionArtifactKind.WALK_FORWARD_JSON,
                content=content,
            ),
        ),
    )
    verify_walk_forward_research_session_manifest(
        manifest, manifest_path=parent / "manifest.json"
    )
    destination.write_bytes(content + b"changed")
    with pytest.raises(
        ResearchSessionManifestVerificationError, match="byte length mismatch"
    ):
        verify_walk_forward_research_session_manifest(
            manifest, manifest_path=parent / "manifest.json"
        )
