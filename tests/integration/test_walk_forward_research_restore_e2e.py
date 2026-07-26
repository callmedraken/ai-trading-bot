import shutil
from pathlib import Path

from tests.cli.test_research_session_archive import _bundle

from trading_bot.cli.research_session_archive import (
    create_walk_forward_research_bundle_archive,
)
from trading_bot.cli.research_session_manifest import (
    load_walk_forward_research_session_manifest,
    verify_walk_forward_research_session_manifest,
)
from trading_bot.cli.research_session_restore import (
    restore_walk_forward_research_bundle_archive,
)


def test_archive_restores_to_offline_verifiable_bundle(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    expected = {
        path.relative_to(bundle).as_posix(): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    archives = tmp_path / "archives"
    archives.mkdir()
    archive = create_walk_forward_research_bundle_archive(
        bundle_path=bundle,
        destination_directory=archives,
    )
    shutil.rmtree(bundle)

    restored = restore_walk_forward_research_bundle_archive(
        archive_path=archive.archive_path,
        destination=tmp_path / "restored",
    )

    actual = {
        path.relative_to(restored.bundle_path).as_posix(): path.read_bytes()
        for path in restored.bundle_path.rglob("*")
        if path.is_file()
    }
    assert actual == expected
    manifest = load_walk_forward_research_session_manifest(restored.manifest_path)
    assert verify_walk_forward_research_session_manifest(
        manifest, manifest_path=restored.manifest_path
    ).passed
