import shutil
from pathlib import Path

from tests.cli.test_research_session_archive import _bundle

from trading_bot.cli.research_session_archive import (
    create_walk_forward_research_bundle_archive,
    verify_walk_forward_research_bundle_archive,
)


def test_completed_bundle_archives_reproducibly_and_verifies_offline(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    first_destination = tmp_path / "first"
    second_destination = tmp_path / "second"
    first_destination.mkdir()
    second_destination.mkdir()

    first = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=first_destination,
    )
    second = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=second_destination,
    )

    assert first.archive_path.read_bytes() == second.archive_path.read_bytes()
    assert first.archive_sha256 == second.archive_sha256
    assert first.archive_byte_length == second.archive_byte_length

    shutil.rmtree(bundle)
    verification = verify_walk_forward_research_bundle_archive(
        archive_path=first.archive_path,
        expected_sha256=first.archive_sha256,
        expected_byte_length=first.archive_byte_length,
    )
    assert verification.passed
    assert verification.manifest.manifest_id == first.manifest_id
