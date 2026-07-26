from pathlib import Path

from tests.cli.test_research_session_archive import _bundle

from trading_bot.cli import (
    create_research_session_archive,
    verify_research_session_archive,
)
from trading_bot.cli.research_session_archive import (
    create_walk_forward_research_bundle_archive,
)


def test_create_and_verify_cli_quiet_success(tmp_path: Path, capsys) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()

    assert (
        create_research_session_archive.main(
            [
                "--bundle",
                str(bundle),
                "--destination",
                str(destination),
                "--quiet",
            ]
        )
        == 0
    )
    assert capsys.readouterr() == ("", "")
    archive = next(destination.iterdir())
    assert (
        verify_research_session_archive.main(["--archive", str(archive), "--quiet"])
        == 0
    )
    assert capsys.readouterr() == ("", "")


def test_verify_cli_length_and_hash_exit_codes(tmp_path: Path, capsys) -> None:
    bundle = _bundle(tmp_path)
    destination = tmp_path / "archives"
    destination.mkdir()
    result = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=destination,
    )

    assert (
        verify_research_session_archive.main(
            [
                "--archive",
                str(result.archive_path),
                "--expected-byte-length",
                str(result.archive_byte_length + 1),
            ]
        )
        == 6
    )
    assert "byte length" in capsys.readouterr().err
    assert (
        verify_research_session_archive.main(
            [
                "--archive",
                str(result.archive_path),
                "--expected-sha256",
                "0" * 64,
            ]
        )
        == 7
    )
    assert "SHA-256" in capsys.readouterr().err
