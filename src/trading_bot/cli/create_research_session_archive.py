"""CLI creation of canonical USTAR walk-forward research archives."""

import argparse
import json
import sys
from pathlib import Path

from trading_bot.cli.exceptions import (
    ResearchSessionArchiveArgumentError,
    ResearchSessionArchiveOutputError,
    ResearchSessionArchiveReadError,
    ResearchSessionArchiveSourceEntryError,
    ResearchSessionArchiveSourceVerificationError,
    ResearchSessionArchiveStructureError,
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_archive import (
    create_walk_forward_research_bundle_archive,
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
    """Build the canonical archive creation parser."""

    parser = argparse.ArgumentParser(
        description="Create a canonical USTAR archive from a verified bundle."
    )
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _source_diagnostic(error: ResearchSessionArchiveSourceEntryError) -> str:
    return (
        "error: source bundle entry failed during archive creation: "
        f"path={_quoted(error.path)} status={error.status.value}"
    )


def main(argv: list[str] | None = None) -> int:
    """Create one canonical research-bundle archive."""

    args = build_parser().parse_args(argv)
    try:
        result = create_walk_forward_research_bundle_archive(
            bundle_path=args.bundle,
            destination_directory=args.destination,
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
    except (
        ResearchSessionArchiveArgumentError,
        ResearchSessionArchiveStructureError,
    ) as error:
        print(f"error: archive validation failed: {error}", file=sys.stderr)
        return 4
    except ResearchSessionArchiveSourceVerificationError as error:
        verification = error.result
        print(format_verification_result(verification), end="", file=sys.stderr)
        for item in verification.artifacts:
            if item.status is not ResearchSessionArtifactVerificationStatus.PASS:
                return _EXIT_BY_STATUS[item.status]
        raise RuntimeError("failed verification has no failed artifact") from error
    except ResearchSessionArchiveSourceEntryError as error:
        print(_source_diagnostic(error), file=sys.stderr)
        return _EXIT_BY_STATUS[error.status]
    except ResearchSessionArchiveReadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 8
    except ResearchSessionArchiveOutputError as error:
        primary = error.primary_error
        if isinstance(primary, ResearchSessionArchiveSourceEntryError):
            print(_source_diagnostic(primary), file=sys.stderr)
        else:
            print(f"error: {error}", file=sys.stderr)
        if error.cleanup_message is not None:
            print(f"cleanup error: {error.cleanup_message}", file=sys.stderr)
        if isinstance(primary, ResearchSessionArchiveSourceEntryError):
            return _EXIT_BY_STATUS[primary.status]
        return 9
    if not args.quiet:
        print("Walk-forward research-bundle archive creation: PASS")
        print(f"  manifest ID: {result.manifest_id}")
        print(f"  format: {result.verification.archive_format.value}")
        print(f"  archive: {_quoted(str(result.archive_path))}")
        print(f"  bytes: {result.archive_byte_length}")
        print(f"  sha256: {result.archive_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
