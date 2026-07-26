"""CLI restoration of canonical walk-forward research-bundle archives."""

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
    ResearchSessionRestoreArgumentError,
    ResearchSessionRestoreOutputError,
)
from trading_bot.cli.research_session_restore import (
    restore_walk_forward_research_bundle_archive,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the deterministic archive-restoration parser."""

    parser = argparse.ArgumentParser(
        description="Restore a verified canonical USTAR research bundle."
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-byte-length", type=int)
    parser.add_argument("--quiet", action="store_true")
    return parser


def _exit_code(error: Exception) -> int:
    if isinstance(
        error,
        (ResearchSessionArchiveArgumentError, ResearchSessionRestoreArgumentError),
    ):
        return 2
    if isinstance(
        error,
        (
            ResearchSessionArchiveReadError,
            ResearchSessionManifestReadError,
            ResearchSessionManifestJsonError,
        ),
    ):
        return 3
    if isinstance(
        error,
        (ResearchSessionArchiveStructureError, ResearchSessionManifestError),
    ):
        return 4
    if isinstance(error, ResearchSessionArchiveByteLengthMismatchError):
        return 6
    if isinstance(error, ResearchSessionArchiveHashMismatchError):
        return 7
    return 9


def main(argv: list[str] | None = None) -> int:
    """Restore one canonical archive to one finalized portable bundle."""

    args = build_parser().parse_args(argv)
    try:
        result = restore_walk_forward_research_bundle_archive(
            archive_path=args.archive,
            destination=args.destination,
            expected_sha256=args.expected_sha256,
            expected_byte_length=args.expected_byte_length,
        )
    except (
        ResearchSessionArchiveArgumentError,
        ResearchSessionArchiveByteLengthMismatchError,
        ResearchSessionArchiveHashMismatchError,
        ResearchSessionArchiveReadError,
        ResearchSessionArchiveStructureError,
        ResearchSessionManifestError,
        ResearchSessionManifestJsonError,
        ResearchSessionManifestReadError,
        ResearchSessionRestoreArgumentError,
        ResearchSessionRestoreOutputError,
    ) as error:
        primary = (
            error.primary_error
            if isinstance(error, ResearchSessionRestoreOutputError)
            and error.primary_error is not None
            else error
        )
        print(f"error: {primary}", file=sys.stderr)
        if (
            isinstance(error, ResearchSessionRestoreOutputError)
            and error.cleanup_message is not None
        ):
            print(f"cleanup error: {error.cleanup_message}", file=sys.stderr)
        return _exit_code(primary)
    if not args.quiet:
        print("Walk-forward research-bundle archive restoration: PASS")
        print(f"  manifest ID: {result.manifest.manifest_id}")
        print(
            f"  destination: {json.dumps(str(result.bundle_path), ensure_ascii=False)}"
        )
        print(f"  entries restored: {len(result.entries)}")
        print(f"  bytes: {result.archive_byte_length}")
        print(f"  sha256: {result.archive_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
