import subprocess
import sys
from pathlib import Path

from trading_bot.cli.research_session_bundle import (
    create_walk_forward_research_bundle,
)
from trading_bot.cli.research_session_manifest import (
    load_walk_forward_research_session_manifest,
    verify_walk_forward_research_session_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tests" / "fixtures" / "cli" / "walk-forward-schema-2-e2e.json"
SCRIPT = ROOT / "scripts" / "run_walk_forward_experiment.py"


def test_real_walk_forward_session_becomes_offline_portable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    manifest_path = source / "session.json"
    artifact_paths = tuple(
        source / name
        for name in ("walk.json", "walk.csv", "aggregate.json", "aggregate.csv")
    )
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(CONFIG),
            "--json",
            str(artifact_paths[0]),
            "--csv",
            str(artifact_paths[1]),
            "--aggregate-json",
            str(artifact_paths[2]),
            "--aggregate-csv",
            str(artifact_paths[3]),
            "--manifest",
            str(manifest_path),
            "--quiet",
        ],
        cwd=ROOT,
        check=True,
    )
    source_bytes = tuple(path.read_bytes() for path in artifact_paths)
    bundle = create_walk_forward_research_bundle(
        manifest_path=manifest_path,
        destination=tmp_path / "bundle",
    )

    copied_bytes = tuple(
        (bundle.bundle_path / item.bundle_relative_path).read_bytes()
        for item in bundle.artifacts
    )
    assert copied_bytes == source_bytes
    source_manifest = load_walk_forward_research_session_manifest(manifest_path)
    assert bundle.manifest.manifest_id == source_manifest.manifest_id

    for path in artifact_paths:
        path.unlink()
    retained = load_walk_forward_research_session_manifest(bundle.manifest_path)
    verification = verify_walk_forward_research_session_manifest(
        retained, manifest_path=bundle.manifest_path
    )
    assert verification.passed
