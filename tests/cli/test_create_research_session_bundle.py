from pathlib import Path
from uuid import UUID

from trading_bot.cli import create_research_session_bundle
from trading_bot.cli.research_session_manifest import (
    CompletedResearchArtifact,
    ResearchSessionArtifactKind,
    build_walk_forward_research_session_manifest,
    serialize_walk_forward_research_session_manifest_json,
)

RESULT_ID = UUID("11111111-1111-5111-8111-111111111111")


def _manifest(tmp_path: Path) -> tuple[Path, Path]:
    artifact = (tmp_path / "opaque.json").resolve()
    artifact.write_bytes(b"opaque\n")
    manifest_path = (tmp_path / "manifest-source.json").resolve()
    manifest = build_walk_forward_research_session_manifest(
        manifest_path=manifest_path,
        walk_forward_config_schema_version=1,
        artifacts=(
            CompletedResearchArtifact(
                artifact,
                ResearchSessionArtifactKind.WALK_FORWARD_JSON,
                1,
                RESULT_ID,
                b"opaque\n",
            ),
        ),
    )
    manifest_path.write_text(
        serialize_walk_forward_research_session_manifest_json(manifest),
        encoding="utf-8",
        newline="",
    )
    return manifest_path, artifact


def test_cli_quiet_success(tmp_path: Path, capsys) -> None:
    manifest, _ = _manifest(tmp_path)
    destination = tmp_path / "bundle"

    assert (
        create_research_session_bundle.main(
            [
                "--manifest",
                str(manifest),
                "--destination",
                str(destination),
                "--quiet",
            ]
        )
        == 0
    )
    assert capsys.readouterr() == ("", "")


def test_cli_reuses_source_verification_exit_code(tmp_path: Path, capsys) -> None:
    manifest, artifact = _manifest(tmp_path)
    artifact.write_bytes(b"different length")

    assert (
        create_research_session_bundle.main(
            [
                "--manifest",
                str(manifest),
                "--destination",
                str(tmp_path / "bundle"),
            ]
        )
        == 6
    )
    assert "BYTE_LENGTH_MISMATCH" in capsys.readouterr().err


def test_cli_uses_exit_nine_for_existing_destination(tmp_path: Path, capsys) -> None:
    manifest, _ = _manifest(tmp_path)
    destination = tmp_path / "bundle"
    destination.mkdir()

    assert (
        create_research_session_bundle.main(
            [
                "--manifest",
                str(manifest),
                "--destination",
                str(destination),
            ]
        )
        == 9
    )
    assert "already exists" in capsys.readouterr().err
