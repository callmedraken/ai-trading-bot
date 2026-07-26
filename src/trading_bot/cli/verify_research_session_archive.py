"""CLI verification of canonical USTAR walk-forward research archives."""

import argparse
import json
import sys
from pathlib import Path

from trading_bot.cli.exceptions import (
    ResearchSessionArchiveArgumentError,
    ResearchSessionArchiveByteLengthMismatchError,
    ResearchSessionArchiveHashMismatchError,
    ResearchSessionArchiveReadError,
    ResearchSessionArchiveStructureError,
    ResearchSessionManifestError,
    ResearchSessionManifestJsonError,
    ResearchSessionManifestReadError,
)
from trading_bot.cli.research_session_archive import (
    WalkForwardResearchArchiveVerificationResult,
    verify_walk_forward_research_bundle_archive,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the canonical archive verification parser."""

    parser = argparse.ArgumentParser(
        description="Verify a canonical USTAR walk-forward research archive."
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-byte-length", type=int)
    parser.add_argument("--quiet", action="store_true")
    return parser


def format_archive_verification(
    result: WalkForwardResearchArchiveVerificationResult,
) -> str:
    """Render deterministic successful archive evidence."""

    return (
        "Walk-forward research-bundle archive verification: PASS\n"
        f"  manifest ID: {result.manifest.manifest_id}\n"
        f"  format: {result.archive_format.value}\n"
        f"  entries verified: {len(result.entries)}\n"
        f"  bytes: {result.archive_byte_length}\n"
        f"  sha256: {result.archive_sha256}\n"
        f"  archive: {json.dumps(str(result.archive_path), ensure_ascii=False)}\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Verify one canonical archive without extraction."""

    args = build_parser().parse_args(argv)
    try:
        result = verify_walk_forward_research_bundle_archive(
            archive_path=args.archive,
            expected_sha256=args.expected_sha256,
            expected_byte_length=args.expected_byte_length,
        )
    except ResearchSessionArchiveArgumentError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except (
        ResearchSessionArchiveReadError,
        ResearchSessionManifestReadError,
        ResearchSessionManifestJsonError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except (
        ResearchSessionArchiveStructureError,
        ResearchSessionManifestError,
    ) as error:
        print(f"error: archive validation failed: {error}", file=sys.stderr)
        return 4
    except ResearchSessionArchiveByteLengthMismatchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 6
    except ResearchSessionArchiveHashMismatchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 7
    if not args.quiet:
        print(format_archive_verification(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
