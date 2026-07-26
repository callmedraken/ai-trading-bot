"""Deterministic offline verification of retained research-session manifests."""

import argparse
import json
import sys
from pathlib import Path

from trading_bot.cli.exceptions import (
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_manifest import (
    ResearchSessionArtifactVerificationResult,
    ResearchSessionArtifactVerificationStatus,
    ResearchSessionManifestVerificationResult,
    load_walk_forward_research_session_manifest,
    verify_walk_forward_research_session_manifest,
)

_EXIT_BY_STATUS = {
    ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR: 5,
    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO: 8,
    ResearchSessionArtifactVerificationStatus.BYTE_LENGTH_MISMATCH: 6,
    ResearchSessionArtifactVerificationStatus.SHA256_MISMATCH: 7,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the dedicated offline verifier argument parser."""

    parser = argparse.ArgumentParser(
        description="Verify a walk-forward research-session manifest offline."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _artifact_line(item: ResearchSessionArtifactVerificationResult) -> str:
    artifact = item.artifact
    prefix = (
        f"  [{artifact.ordinal}] {artifact.kind.value} {item.status.value} "
        f"path={_quoted(artifact.path)}"
    )
    if item.status is ResearchSessionArtifactVerificationStatus.PASS:
        return (
            f"{prefix} bytes={item.actual_byte_length} "
            f"sha256={item.actual_content_hash}"
        )
    if item.status is ResearchSessionArtifactVerificationStatus.BYTE_LENGTH_MISMATCH:
        return (
            f"{prefix} expected={artifact.byte_length} actual={item.actual_byte_length}"
        )
    if item.status is ResearchSessionArtifactVerificationStatus.SHA256_MISMATCH:
        return (
            f"{prefix} expected={artifact.content_hash} "
            f"actual={item.actual_content_hash}"
        )
    return prefix


def format_verification_result(
    result: ResearchSessionManifestVerificationResult,
) -> str:
    """Render a stable human-readable report from immutable evidence."""

    outcome = "PASS" if result.passed else "FAIL"
    passed = sum(
        item.status is ResearchSessionArtifactVerificationStatus.PASS
        for item in result.artifacts
    )
    lines = [
        f"Walk-forward research-session manifest verification: {outcome}",
        f"  manifest ID: {result.manifest.manifest_id}",
        f"  manifest schema version: {result.manifest.manifest_schema_version}",
    ]
    if result.manifest.session_label is not None:
        lines.append(f"  session label: {_quoted(result.manifest.session_label)}")
    if result.passed:
        lines.append(f"  artifacts verified: {len(result.artifacts)}")
    else:
        lines.append(f"  artifacts verified: {passed} of {len(result.artifacts)}")
    lines.extend(_artifact_line(item) for item in result.artifacts)
    return "\n".join(lines) + "\n"


def _normalized(path: Path) -> Path:
    return path.resolve(strict=False)


def main(argv: list[str] | None = None) -> int:
    """Run the deterministic offline verifier."""

    args = build_parser().parse_args(argv)
    manifest_path = _normalized(args.manifest)
    try:
        manifest = load_walk_forward_research_session_manifest(manifest_path)
    except ResearchSessionManifestReadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except ResearchSessionManifestJsonError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except ResearchSessionManifestError as error:
        print(f"error: manifest validation failed: {error}", file=sys.stderr)
        return 4
    result = verify_walk_forward_research_session_manifest(
        manifest, manifest_path=manifest_path
    )
    if result.passed:
        if not args.quiet:
            print(format_verification_result(result), end="")
        return 0
    print(format_verification_result(result), end="", file=sys.stderr)
    for item in result.artifacts:
        if item.status is not ResearchSessionArtifactVerificationStatus.PASS:
            return _EXIT_BY_STATUS[item.status]
    raise RuntimeError("failed verification result has no failed artifact")


if __name__ == "__main__":
    raise SystemExit(main())
