import json
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli import verify_research_session_manifest
from trading_bot.cli.exceptions import (
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_manifest import (
    MAX_RESEARCH_SESSION_MANIFEST_BYTES,
    CompletedResearchArtifact,
    ResearchSessionArtifactKind,
    ResearchSessionArtifactVerificationStatus,
    build_walk_forward_research_session_manifest,
    parse_walk_forward_research_session_manifest_bytes,
    serialize_walk_forward_research_session_manifest_json,
    verify_walk_forward_research_session_manifest,
)

RESULT_ID = UUID("11111111-1111-5111-8111-111111111111")


def _write_manifest(
    tmp_path: Path,
    *,
    artifact_name: str = "opaque.json",
    content: bytes = b"not JSON and never parsed\n",
) -> tuple[Path, Path]:
    parent = tmp_path.resolve()
    artifact = parent / artifact_name
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(content)
    manifest_path = parent / "manifest.json"
    manifest = build_walk_forward_research_session_manifest(
        manifest_path=manifest_path,
        walk_forward_config_schema_version=3,
        artifacts=(
            CompletedResearchArtifact(
                artifact,
                ResearchSessionArtifactKind.WALK_FORWARD_JSON,
                1,
                RESULT_ID,
                content,
            ),
        ),
        session_label="retained session",
    )
    manifest_path.write_text(
        serialize_walk_forward_research_session_manifest_json(manifest),
        encoding="utf-8",
        newline="",
    )
    return manifest_path, artifact


def _raw_manifest(manifest_path: Path) -> dict[str, object]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def test_strict_bytes_parser_reconstructs_without_accessing_artifacts(
    tmp_path: Path,
) -> None:
    manifest_path, artifact = _write_manifest(tmp_path)
    content = manifest_path.read_bytes()
    artifact.unlink()

    manifest = parse_walk_forward_research_session_manifest_bytes(content)

    assert manifest.manifest_schema_version == 1
    assert manifest.artifacts[0].ordinal == 1
    assert manifest.artifacts[0].path == "opaque.json"


@pytest.mark.parametrize(
    ("content", "error_type", "match"),
    [
        (b"\xef\xbb\xbf{}", ResearchSessionManifestReadError, "BOM"),
        (b"\xff", ResearchSessionManifestReadError, "UTF-8"),
        (b'{"x":1,"x":2}', ResearchSessionManifestJsonError, "duplicate"),
        (b'{"x":NaN}', ResearchSessionManifestJsonError, "nonstandard"),
        (b"{", ResearchSessionManifestJsonError, "invalid JSON"),
    ],
)
def test_strict_bytes_parser_rejects_noncanonical_json_inputs(
    content: bytes, error_type: type[Exception], match: str
) -> None:
    with pytest.raises(error_type, match=match):
        parse_walk_forward_research_session_manifest_bytes(content)


def test_strict_bytes_parser_enforces_size_before_decoding() -> None:
    content = b"\xff" * (MAX_RESEARCH_SESSION_MANIFEST_BYTES + 1)
    with pytest.raises(ResearchSessionManifestReadError, match="maximum byte size"):
        parse_walk_forward_research_session_manifest_bytes(content)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda raw: raw.update({"unknown": None}),
            "unknown field",
        ),
        (
            lambda raw: raw.pop("schema_version"),
            "required field is missing",
        ),
        (
            lambda raw: raw.update({"schema_version": True}),
            "exact integer",
        ),
        (
            lambda raw: raw.update({"schema_version": 2}),
            "unsupported manifest schema version",
        ),
        (
            lambda raw: raw["walk_forward_research_session_manifest"].update(
                {"manifest_id": "AAAAAAAA-AAAA-5AAA-8AAA-AAAAAAAAAAAA"}
            ),
            "canonical UUID",
        ),
        (
            lambda raw: raw["walk_forward_research_session_manifest"]["artifacts"][
                0
            ].update({"kind": "UNKNOWN"}),
            "invalid enum",
        ),
        (
            lambda raw: raw["walk_forward_research_session_manifest"].update(
                {"manifest_id": str(RESULT_ID)}
            ),
            "does not reconcile",
        ),
    ],
)
def test_strict_parser_rejects_schema_and_identity_errors(
    tmp_path: Path, mutate, match: str
) -> None:
    manifest_path, _ = _write_manifest(tmp_path)
    raw = _raw_manifest(manifest_path)
    mutate(raw)

    with pytest.raises(ResearchSessionManifestError, match=match):
        parse_walk_forward_research_session_manifest_bytes(
            json.dumps(raw).encode("utf-8")
        )


def test_parser_rejects_duplicate_retained_paths_without_changing_model(
    tmp_path: Path,
) -> None:
    parent = tmp_path.resolve()
    first = parent / "walk.json"
    second = parent / "walk.csv"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    manifest = build_walk_forward_research_session_manifest(
        manifest_path=parent / "manifest.json",
        walk_forward_config_schema_version=1,
        artifacts=(
            CompletedResearchArtifact(
                first,
                ResearchSessionArtifactKind.WALK_FORWARD_JSON,
                1,
                RESULT_ID,
                b"a",
            ),
            CompletedResearchArtifact(
                second,
                ResearchSessionArtifactKind.WALK_FORWARD_CSV,
                1,
                RESULT_ID,
                b"b",
            ),
        ),
    )
    raw = json.loads(serialize_walk_forward_research_session_manifest_json(manifest))
    records = raw["walk_forward_research_session_manifest"]["artifacts"]
    records[1]["path"] = records[0]["path"]

    with pytest.raises(ResearchSessionManifestError, match="paths must be unique"):
        parse_walk_forward_research_session_manifest_bytes(
            json.dumps(raw).encode("utf-8")
        )


def test_verification_statuses_and_retained_order(tmp_path: Path) -> None:
    parent = tmp_path.resolve()
    paths = [parent / name for name in ("one", "two", "three", "four")]
    contents = (b"pass", b"length", b"hash-a", b"missing")
    kinds = tuple(ResearchSessionArtifactKind)[:4]
    for path, content in zip(paths, contents, strict=True):
        path.write_bytes(content)
    manifest = build_walk_forward_research_session_manifest(
        manifest_path=parent / "manifest.json",
        walk_forward_config_schema_version=3,
        artifacts=tuple(
            CompletedResearchArtifact(path, kind, 1, RESULT_ID, content)
            for path, kind, content in zip(paths, kinds, contents, strict=True)
        ),
    )
    paths[1].write_bytes(b"longer!")
    paths[2].write_bytes(b"hash-b")
    paths[3].unlink()

    result = verify_walk_forward_research_session_manifest(
        manifest, manifest_path=parent / "manifest.json"
    )

    assert [item.artifact.ordinal for item in result.artifacts] == [1, 2, 3, 4]
    assert [item.status for item in result.artifacts] == [
        ResearchSessionArtifactVerificationStatus.PASS,
        ResearchSessionArtifactVerificationStatus.BYTE_LENGTH_MISMATCH,
        ResearchSessionArtifactVerificationStatus.SHA256_MISMATCH,
        ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR,
    ]


def test_verification_rejects_final_symlink_when_supported(tmp_path: Path) -> None:
    manifest_path, artifact = _write_manifest(tmp_path)
    manifest = parse_walk_forward_research_session_manifest_bytes(
        manifest_path.read_bytes()
    )
    target = tmp_path / "target"
    artifact.replace(target)
    try:
        artifact.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    result = verify_walk_forward_research_session_manifest(
        manifest, manifest_path=manifest_path.resolve()
    )

    assert result.artifacts[0].status is (
        ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR
    )


def test_verification_classifies_unexpected_artifact_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path, artifact = _write_manifest(tmp_path)
    manifest = parse_walk_forward_research_session_manifest_bytes(
        manifest_path.read_bytes()
    )
    original_open = Path.open

    def failing_open(path: Path, *args, **kwargs):
        if path == artifact:
            raise PermissionError
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    result = verify_walk_forward_research_session_manifest(
        manifest, manifest_path=manifest_path.resolve()
    )

    assert result.artifacts[0].status is (
        ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO
    )


def test_cli_quiet_success_and_deterministic_failure_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path, artifact = _write_manifest(tmp_path)
    assert (
        verify_research_session_manifest.main(
            ["--manifest", str(manifest_path), "--quiet"]
        )
        == 0
    )
    assert capsys.readouterr() == ("", "")

    artifact.write_bytes(b"different byte length")
    first = verify_research_session_manifest.main(
        ["--manifest", str(manifest_path), "--quiet"]
    )
    first_output = capsys.readouterr()
    second = verify_research_session_manifest.main(
        ["--manifest", str(manifest_path), "--quiet"]
    )
    second_output = capsys.readouterr()

    assert first == second == 6
    assert first_output.out == second_output.out == ""
    assert first_output.err == second_output.err
    assert "BYTE_LENGTH_MISMATCH" in first_output.err
    assert 'path="opaque.json"' in first_output.err


@pytest.mark.parametrize(
    ("change", "exit_code", "status"),
    [
        ("missing", 5, "MISSING_OR_NONREGULAR"),
        ("length", 6, "BYTE_LENGTH_MISMATCH"),
        ("hash", 7, "SHA256_MISMATCH"),
    ],
)
def test_cli_exit_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    change: str,
    exit_code: int,
    status: str,
) -> None:
    manifest_path, artifact = _write_manifest(tmp_path, content=b"same")
    if change == "missing":
        artifact.unlink()
    elif change == "length":
        artifact.write_bytes(b"different")
    else:
        artifact.write_bytes(b"else")

    assert (
        verify_research_session_manifest.main(["--manifest", str(manifest_path)])
        == exit_code
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert status in captured.err


def test_cli_parse_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    assert (
        verify_research_session_manifest.main(
            ["--manifest", str(invalid_json), "--quiet"]
        )
        == 3
    )
    assert "invalid JSON" in capsys.readouterr().err

    manifest_path, _ = _write_manifest(tmp_path / "schema")
    raw = _raw_manifest(manifest_path)
    raw["schema_version"] = 2
    manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    assert (
        verify_research_session_manifest.main(
            ["--manifest", str(manifest_path), "--quiet"]
        )
        == 4
    )
    assert "unsupported manifest schema version" in capsys.readouterr().err
