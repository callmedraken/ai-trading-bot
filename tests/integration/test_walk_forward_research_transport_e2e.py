"""One real walk-forward run through every deterministic transport boundary."""

import json
import shutil
from pathlib import Path

from trading_bot.cli import walk_forward_experiment
from trading_bot.cli.research_session_archive import (
    create_walk_forward_research_bundle_archive,
    verify_walk_forward_research_bundle_archive,
)
from trading_bot.cli.research_session_bundle import (
    create_walk_forward_research_bundle,
)
from trading_bot.cli.research_session_manifest import (
    ResearchSessionArtifactKind,
    load_walk_forward_research_session_manifest,
    serialize_walk_forward_research_session_manifest_json,
    verify_walk_forward_research_session_manifest,
)
from trading_bot.cli.research_session_restore import (
    restore_walk_forward_research_bundle_archive,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tests" / "fixtures" / "cli" / "walk-forward-schema-2-e2e.json"
PRIMARY_NAMES = (
    "walk.json",
    "walk.csv",
    "aggregate.json",
    "aggregate.csv",
    "stability.json",
    "stability.csv",
)
EXPECTED_KINDS = tuple(ResearchSessionArtifactKind)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        item.relative_to(root).as_posix(): item.read_bytes()
        for item in root.rglob("*")
        if item.is_file()
    }


def _artifact_evidence(manifest) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            artifact.ordinal,
            artifact.kind,
            artifact.artifact_schema_version,
            artifact.result_id,
            artifact.byte_length,
            artifact.content_hash,
        )
        for artifact in manifest.artifacts
    )


def _schema_three_config(tmp_path: Path) -> Path:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = (CONFIG.parent / raw["historical_data"]["sources"][0]["path"]).resolve()
    data_directory = tmp_path / "input-data"
    data_directory.mkdir()
    (data_directory / "SPY.csv").write_bytes(source.read_bytes())
    raw["historical_data"]["sources"][0]["path"] = "input-data/SPY.csv"
    raw["schema_version"] = 3
    raw["stability_policy"] = {
        "policy_id": "00000000-0000-0000-0000-000000000640",
        "metrics": [
            {
                "metric": "SIMULATION_RETURN",
                "operations": [
                    "ADJACENT_ABSOLUTE_CHANGE",
                    "RANGE",
                    "MEDIAN_ABSOLUTE_DEVIATION",
                    "SIGN_CHANGE_COUNT",
                ],
                "comparability_rule": "EQUAL_TEST_DURATION",
            },
            {
                "metric": "TOTAL_ORDERS",
                "operations": [
                    "ADJACENT_ABSOLUTE_CHANGE",
                    "RANGE",
                    "MEDIAN_ABSOLUTE_DEVIATION",
                ],
                "comparability_rule": "EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT",
            },
        ],
        "metadata": [{"key": "purpose", "value": "transport-e2e"}],
    }
    config = tmp_path / "schema-three-transport.json"
    config.write_text(json.dumps(raw), encoding="utf-8")
    return config


def _run_one_real_workflow(destination: Path, config: Path) -> Path:
    destination.mkdir()
    manifest_path = destination / "source-manifest.json"
    assert (
        walk_forward_experiment.main(
            [
                "--config",
                str(config),
                "--json",
                str(destination / "walk.json"),
                "--csv",
                str(destination / "walk.csv"),
                "--aggregate-json",
                str(destination / "aggregate.json"),
                "--aggregate-csv",
                str(destination / "aggregate.csv"),
                "--stability-json",
                str(destination / "stability.json"),
                "--stability-csv",
                str(destination / "stability.csv"),
                "--manifest",
                str(manifest_path),
                "--session-label",
                "transport-e2e",
                "--session-metadata",
                "purpose=round-trip-transport",
                "--quiet",
            ]
        )
        == 0
    )
    return manifest_path


def test_real_walk_forward_six_artifact_transport_round_trip(tmp_path: Path) -> None:
    source_manifest_path = _run_one_real_workflow(
        tmp_path / "source", _schema_three_config(tmp_path)
    )
    source_manifest = load_walk_forward_research_session_manifest(source_manifest_path)
    source_manifest_bytes = source_manifest_path.read_bytes()
    pretty_source_manifest_path = source_manifest_path.with_name(
        "source-manifest-pretty.json"
    )
    pretty_source_manifest_bytes = (
        serialize_walk_forward_research_session_manifest_json(
            source_manifest, pretty=True
        ).encode("utf-8")
    )
    pretty_source_manifest_path.write_bytes(pretty_source_manifest_bytes)
    pretty_source_manifest = load_walk_forward_research_session_manifest(
        pretty_source_manifest_path
    )

    assert (
        source_manifest_bytes
        == serialize_walk_forward_research_session_manifest_json(
            source_manifest
        ).encode("utf-8")
    )
    assert pretty_source_manifest_bytes != source_manifest_bytes
    assert pretty_source_manifest == source_manifest
    assert pretty_source_manifest.manifest_id == source_manifest.manifest_id
    assert tuple(item.kind for item in source_manifest.artifacts) == EXPECTED_KINDS
    assert tuple(item.ordinal for item in source_manifest.artifacts) == tuple(
        range(1, 7)
    )
    assert tuple(item.path for item in source_manifest.artifacts) == PRIMARY_NAMES
    assert {item.name for item in source_manifest_path.parent.iterdir()} >= set(
        (*PRIMARY_NAMES, "source-manifest.json")
    )

    bundle_parent = tmp_path / "bundles"
    bundle_parent.mkdir()
    compact_bundle = create_walk_forward_research_bundle(
        manifest_path=source_manifest_path,
        destination=bundle_parent / "compact",
    )
    pretty_source_bundle = create_walk_forward_research_bundle(
        manifest_path=pretty_source_manifest_path,
        destination=bundle_parent / "pretty-source",
    )
    compact_snapshot = _tree_bytes(compact_bundle.bundle_path)

    assert compact_bundle.verification.passed
    assert pretty_source_bundle.verification.passed
    assert compact_bundle.manifest.manifest_id == source_manifest.manifest_id
    assert pretty_source_bundle.manifest.manifest_id == source_manifest.manifest_id
    assert _tree_bytes(pretty_source_bundle.bundle_path) == compact_snapshot
    assert _artifact_evidence(compact_bundle.manifest) == _artifact_evidence(
        source_manifest
    )
    assert tuple(item.path for item in compact_bundle.manifest.artifacts) == (
        "artifacts/01-walk-forward.json",
        "artifacts/02-walk-forward.csv",
        "artifacts/03-aggregate.json",
        "artifacts/04-aggregate.csv",
        "artifacts/05-stability.json",
        "artifacts/06-stability.csv",
    )

    pretty_bundle_manifest_bytes = (
        serialize_walk_forward_research_session_manifest_json(
            pretty_source_bundle.manifest, pretty=True
        ).encode("utf-8")
    )
    pretty_source_bundle.manifest_path.write_bytes(pretty_bundle_manifest_bytes)
    pretty_bundle_manifest = load_walk_forward_research_session_manifest(
        pretty_source_bundle.manifest_path
    )
    pretty_bundle_verification = verify_walk_forward_research_session_manifest(
        pretty_bundle_manifest,
        manifest_path=pretty_source_bundle.manifest_path,
    )
    assert pretty_bundle_verification.passed
    assert pretty_bundle_manifest == compact_bundle.manifest
    assert pretty_bundle_manifest.manifest_id == source_manifest.manifest_id
    assert _tree_bytes(pretty_source_bundle.bundle_path) != compact_snapshot

    first_archive_directory = tmp_path / "archives-first"
    second_archive_directory = tmp_path / "archives-second"
    pretty_archive_directory = tmp_path / "archives-pretty"
    first_archive_directory.mkdir()
    second_archive_directory.mkdir()
    pretty_archive_directory.mkdir()
    first_archive = create_walk_forward_research_bundle_archive(
        bundle_path=compact_bundle.bundle_path,
        destination_directory=first_archive_directory,
    )
    second_archive = create_walk_forward_research_bundle_archive(
        bundle_path=compact_bundle.bundle_path,
        destination_directory=second_archive_directory,
    )
    pretty_archive = create_walk_forward_research_bundle_archive(
        bundle_path=pretty_source_bundle.bundle_path,
        destination_directory=pretty_archive_directory,
    )
    verified_archive = verify_walk_forward_research_bundle_archive(
        archive_path=first_archive.archive_path,
        expected_sha256=first_archive.archive_sha256,
        expected_byte_length=first_archive.archive_byte_length,
    )

    assert (
        first_archive.archive_path.read_bytes()
        == second_archive.archive_path.read_bytes()
    )
    assert first_archive.archive_sha256 == second_archive.archive_sha256
    assert first_archive.archive_byte_length == second_archive.archive_byte_length
    assert first_archive.manifest_id == source_manifest.manifest_id
    assert second_archive.manifest_id == source_manifest.manifest_id
    assert (
        first_archive.archive_path.read_bytes()
        != pretty_archive.archive_path.read_bytes()
    )
    assert first_archive.archive_sha256 != pretty_archive.archive_sha256
    assert verified_archive.passed
    assert verified_archive.manifest.manifest_id == source_manifest.manifest_id
    assert _artifact_evidence(verified_archive.manifest) == _artifact_evidence(
        source_manifest
    )

    shutil.rmtree(compact_bundle.bundle_path)
    assert not compact_bundle.bundle_path.exists()
    restored_one = restore_walk_forward_research_bundle_archive(
        archive_path=first_archive.archive_path,
        destination=tmp_path / "restored-one",
        expected_sha256=first_archive.archive_sha256,
        expected_byte_length=first_archive.archive_byte_length,
    )
    restored_two = restore_walk_forward_research_bundle_archive(
        archive_path=first_archive.archive_path,
        destination=tmp_path / "restored-two",
    )

    assert _tree_bytes(restored_one.bundle_path) == compact_snapshot
    assert _tree_bytes(restored_two.bundle_path) == compact_snapshot
    assert _tree_bytes(restored_one.bundle_path) == _tree_bytes(
        restored_two.bundle_path
    )
    for restored in (restored_one, restored_two):
        reloaded = load_walk_forward_research_session_manifest(restored.manifest_path)
        offline_verification = verify_walk_forward_research_session_manifest(
            reloaded, manifest_path=restored.manifest_path
        )
        assert offline_verification.passed
        assert reloaded == compact_bundle.manifest
        assert restored.manifest.manifest_id == source_manifest.manifest_id
        assert (
            restored.archive_verification.manifest.manifest_id
            == source_manifest.manifest_id
        )
        assert restored.verification.passed
        assert _artifact_evidence(restored.manifest) == _artifact_evidence(
            source_manifest
        )
        assert tuple(
            (item.position, item.path, item.byte_length, item.sha256)
            for item in restored.entries
        ) == tuple(
            (item.position, item.path, item.byte_length, item.sha256)
            for item in verified_archive.entries
        )
