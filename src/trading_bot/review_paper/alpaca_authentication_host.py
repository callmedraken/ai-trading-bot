"""Noninteractive D1R4 host; one external evidence file, no D1 launch."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path

from trading_bot.market_data.alpaca_http import StdlibAlpacaHistoricalBarsTransport
from trading_bot.review_paper.alpaca_authentication_qualification import (
    QUALIFY_AUTH_INTERLOCK,
    qualify_alpaca_authentication,
    serialize_authentication_qualification,
)
from trading_bot.review_paper.alpaca_credential_generation import (
    MAX_JOURNAL_BYTES,
    ROLES,
    GenerationJournal,
    clear_credential,
    credential_witness,
    parse_generation_journal,
)
from trading_bot.review_paper.alpaca_credential_native import WindowsV3Exclusion
from trading_bot.review_paper.alpaca_windows_credentials import (
    ScopedAlpacaSecrets,
    read_current_product_alpaca_secrets,
)

BRANCH = "feature/robinhood-production-paper-alpaca-auth-qualification"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-alpaca-auth-qualification"
)
PRODUCTION_ROOT = Path(r"F:\AITradingBot")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid qualification arguments")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="D1R4: qualify one fixed v3 Alpaca history authentication probe."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--generation-evidence", required=True, type=Path)
    parser.add_argument("--generation-sha256", required=True)
    parser.add_argument(
        "--qualify-auth", required=True, choices=(QUALIFY_AUTH_INTERLOCK,)
    )
    return parser


def admit_authentication_source(head: str, tree: str) -> tuple[Path, ...]:
    """Exact executing/local/live-origin source, with unmixed package roots."""
    root = Path(__file__).resolve().parents[3]
    for value in (head, tree):
        if (
            type(value) is not str
            or len(value) != 40
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError("invalid source identity")
    if os.name != "nt" or root != WORKTREE.resolve():
        raise ValueError("qualification host mismatch")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()

    if (
        Path(git("rev-parse", "--show-toplevel")).resolve() != root
        or git("branch", "--show-current") != BRANCH
        or git("rev-parse", "HEAD") != head
        or git("rev-parse", "HEAD^{tree}") != tree
        or git("status", "--porcelain=v1", "--untracked-files=all")
        or git("remote", "get-url", "origin") != ORIGIN
        or git("rev-parse", "origin/" + BRANCH) != head
        or git("rev-parse", "origin/" + BRANCH + "^{tree}") != tree
        or git("ls-remote", "origin", "refs/heads/" + BRANCH)
        != head + "\trefs/heads/" + BRANCH
    ):
        raise ValueError("qualification source mismatch")
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(
                root / "src"
            ):
                raise ValueError("mixed qualification import roots")
    roots = tuple(
        Path(line.removeprefix("worktree ")).resolve()
        for line in git("worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )
    if root not in roots:
        raise ValueError("qualification repository boundaries unavailable")
    return roots


def admit_authentication_evidence(path: Path, roots: tuple[Path, ...]) -> Path:
    """Existing real external parent, fresh file, no linked/reparse ancestors."""
    if not isinstance(path, Path) or not path.is_absolute() or path.suffix != ".json":
        raise ValueError("invalid qualification evidence destination")
    resolved = path.resolve()
    if any(resolved.is_relative_to(root.resolve()) for root in roots) or (
        resolved.is_relative_to(PRODUCTION_ROOT.resolve())
    ):
        raise ValueError("qualification evidence must be external")
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("qualification evidence must be fresh")
    for parent in path.parents:
        metadata = parent.lstat()
        if stat.S_ISLNK(metadata.st_mode) or (
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("linked qualification evidence parent")
    return resolved


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        roots = admit_authentication_source(args.expected_head, args.expected_tree)
        destination = admit_authentication_evidence(args.evidence, roots)
        generation = args.generation_evidence
        if not generation.is_absolute() or generation.is_symlink():
            raise ValueError("invalid generation evidence")
        admit_authentication_evidence(
            generation.parent / (generation.name + ".read-check.json"), roots
        )
        # Reserve exclusive evidence ownership BEFORE any credentials or provider read.
        # Failure/crash consumes this destination; never reopen or overwrite it.
        with destination.open("xb") as output:
            mutex = WindowsV3Exclusion()
            if not mutex.acquire():
                raise ValueError("concurrent generation operator")
            try:
                if mutex.abandoned:
                    raise ValueError("abandoned generation requires reconciliation")
                with generation.open("r+b") as record:
                    original = record.read(MAX_JOURNAL_BYTES + 1)
                    preserved = parse_generation_journal(original)
                    if (
                        hashlib.sha256(original).hexdigest() != args.generation_sha256
                        or preserved.truncated
                        or preserved.provider_fenced
                        or not preserved.pair_accepted
                    ):
                        raise ValueError("generation staging unavailable")
                    journal = GenerationJournal(record, preserved.head, preserved.tree)
                    journal.witnesses = preserved.witnesses
                    journal.seq = original.count(b"\n")
                    journal.size = len(original)

                    def reader() -> ScopedAlpacaSecrets:
                        secrets = read_current_product_alpaca_secrets()
                        failed = False
                        try:

                            def compare(key: str, secret: str) -> None:
                                values = (
                                    bytearray(key.encode()),
                                    bytearray(secret.encode()),
                                )
                                try:
                                    pair = tuple(
                                        credential_witness(role, value)
                                        for role, value in zip(
                                            ROLES, values, strict=True
                                        )
                                    )
                                    if pair != preserved.witnesses or not mutex.owned:
                                        raise ValueError("generation readback mismatch")
                                finally:
                                    for value in values:
                                        clear_credential(value)

                            secrets.use(compare)
                            admit_authentication_source(
                                args.expected_head, args.expected_tree
                            )
                            # Durable freeze before the sole provider attempt.
                            journal.record("V3_PROVIDER_EFFECT_INTENT")
                        except Exception:
                            failed = True
                        if failed:
                            secrets.close()
                            raise ValueError("generation readiness failed")
                        return secrets

                    result = qualify_alpaca_authentication(
                        expected_head=args.expected_head,
                        expected_tree=args.expected_tree,
                        qualify_auth=args.qualify_auth,
                        admit_source=lambda: admit_authentication_source(
                            args.expected_head, args.expected_tree
                        ),
                        transport=StdlibAlpacaHistoricalBarsTransport(),
                        credential_reader=reader,
                    )
                    payload = serialize_authentication_qualification(result)
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
            finally:
                mutex.release()
        print(payload.decode("utf-8"), end="")
        return 0 if result.status == "PASS" else 1
    except Exception:
        # Never format an exception, source command output, path, or upstream text.
        print("ALPACA_AUTH_QUALIFICATION_HOST_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
