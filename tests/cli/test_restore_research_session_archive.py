from pathlib import Path

from tests.cli.test_research_session_restore import _archive

from trading_bot.cli import restore_research_session_archive


def test_restore_cli_quiet_success(tmp_path: Path, capsys) -> None:
    _, archive = _archive(tmp_path)
    destination = tmp_path / "restored"

    assert (
        restore_research_session_archive.main(
            [
                "--archive",
                str(archive.archive_path),
                "--destination",
                str(destination),
                "--expected-sha256",
                archive.archive_sha256,
                "--expected-byte-length",
                str(archive.archive_byte_length),
                "--quiet",
            ]
        )
        == 0
    )
    assert capsys.readouterr() == ("", "")
    assert (destination / "manifest.json").is_file()


def test_restore_cli_preserves_archive_and_output_exit_codes(
    tmp_path: Path, capsys
) -> None:
    _, archive = _archive(tmp_path)

    assert (
        restore_research_session_archive.main(
            [
                "--archive",
                str(archive.archive_path),
                "--destination",
                str(tmp_path / "length"),
                "--expected-byte-length",
                str(archive.archive_byte_length + 1),
            ]
        )
        == 6
    )
    assert "byte length" in capsys.readouterr().err

    destination = tmp_path / "existing"
    destination.mkdir()
    assert (
        restore_research_session_archive.main(
            [
                "--archive",
                str(archive.archive_path),
                "--destination",
                str(destination),
            ]
        )
        == 9
    )
    assert "already exists" in capsys.readouterr().err
