"""CLI adapter for deterministic portable walk-forward research bundles."""

import argparse
import json
import sys
from pathlib import Path

from trading_bot.cli.exceptions import (
    ResearchSessionBundleOutputError,
    ResearchSessionBundlePlanError,
    ResearchSessionBundleSourceArtifactError,
    ResearchSessionBundleSourceVerificationError,
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_bundle import (
    create_walk_forward_research_bundle,
)
from trading_bot.cli.research_session_manifest import (
    ResearchSessionArtifactVerificationStatus,
)
from trading_bot.cli.verify_research_session_manifest import (
    format_verification_result,
)

_EXIT_BY_STATUS = {
    ResearchSessionArtifactVerificationStatus.MISSING_OR_NONREGULAR: 5,
    ResearchSessionArtifactVerificationStatus.UNEXPECTED_IO: 8,
    ResearchSessionArtifactVerificationStatus.BYTE_LENGTH_MISMATCH: 6,
    ResearchSessionArtifactVerificationStatus.SHA256_MISMATCH: 7,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the dedicated portable research-bundle parser."""

    parser = argparse.ArgumentParser(
        description="Create a portable walk-forward research bundle offline."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _print_source_artifact_error(
    error: ResearchSessionBundleSourceArtifactError,
) -> None:
    artifact = error.artifact
    print(
        "error: source artifact failed during copying: "
        f"ordinal={artifact.ordinal} kind={artifact.kind.value} "
        f"path={_quoted(artifact.path)} status={error.status.value}",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    """Create one verified portable research bundle."""

    args = build_parser().parse_args(argv)
    try:
        result = create_walk_forward_research_bundle(
            manifest_path=args.manifest,
            destination=args.destination,
        )
    except (
        ResearchSessionManifestReadError,
        ResearchSessionManifestJsonError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except ResearchSessionManifestError as error:
        print(f"error: manifest validation failed: {error}", file=sys.stderr)
        return 4
    except ResearchSessionBundlePlanError as error:
        print(f"error: bundle plan failed: {error}", file=sys.stderr)
        return 4
    except ResearchSessionBundleSourceVerificationError as error:
        verification = error.result
        print(format_verification_result(verification), end="", file=sys.stderr)
        for item in verification.artifacts:
            if item.status is not ResearchSessionArtifactVerificationStatus.PASS:
                return _EXIT_BY_STATUS[item.status]
        raise RuntimeError(
            "failed verification result has no failed artifact"
        ) from error
    except ResearchSessionBundleSourceArtifactError as error:
        _print_source_artifact_error(error)
        return _EXIT_BY_STATUS[error.status]
    except ResearchSessionBundleOutputError as error:
        primary = error.primary_error
        if isinstance(primary, ResearchSessionBundleSourceArtifactError):
            _print_source_artifact_error(primary)
        else:
            print(f"error: {error}", file=sys.stderr)
        if error.cleanup_message is not None:
            print(f"cleanup error: {error.cleanup_message}", file=sys.stderr)
        if isinstance(primary, ResearchSessionBundleSourceArtifactError):
            return _EXIT_BY_STATUS[primary.status]
        return 9
    if not args.quiet:
        print("Walk-forward portable research bundle: PASS")
        print(f"  manifest ID: {result.manifest.manifest_id}")
        print(f"  destination: {_quoted(str(result.bundle_path))}")
        print(f"  artifacts copied: {len(result.artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
