"""Fixed current-product D1 runtime qualification; no provider composition."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from trading_bot.arch133_verifier.credentials import persisted_oauth_availability
from trading_bot.review_paper.alpaca_windows_credentials import (
    read_current_product_alpaca_secrets,
)
from trading_bot.review_paper.armed_session_store import ArmedSessionStore
from trading_bot.review_paper.store import ReviewPaperStore

RUNTIME_ROOT = Path(r"F:\AITradingBot\Arch134D1")
PAPER_PATH = RUNTIME_ROOT / "paper.sqlite"
SESSION_PATH = RUNTIME_ROOT / "armed-sessions.sqlite"
QUALIFY_INTERLOCK = "QUALIFY_ARCH134_D1Q_RUNTIME_AND_FIXED_CREDENTIAL_READINESS"
PAPER_SCHEMA_SHA256 = "4c845637388c1fe7e3dff77183e4e6915e3e157be469c7c53e42959f04c9e2c9"


def _paths(*, complete: bool = True) -> None:
    if (
        not RUNTIME_ROOT.is_absolute()
        or PAPER_PATH != RUNTIME_ROOT / "paper.sqlite"
        or SESSION_PATH != RUNTIME_ROOT / "armed-sessions.sqlite"
    ):
        raise ValueError("runtime paths rejected")
    for path in (
        *reversed(RUNTIME_ROOT.parents),
        RUNTIME_ROOT,
        PAPER_PATH,
        SESSION_PATH,
    ):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("runtime redirection rejected")
        if path in (PAPER_PATH, SESSION_PATH) and (
            not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
        ):
            raise ValueError("runtime file rejected")
    if RUNTIME_ROOT.exists() and (
        not RUNTIME_ROOT.is_dir()
        or (
            complete
            and {p.name for p in RUNTIME_ROOT.iterdir()}
            != {"paper.sqlite", "armed-sessions.sqlite"}
        )
    ):
        raise ValueError("runtime contents rejected")


def _compatible() -> tuple[int, int]:
    with closing(
        sqlite3.connect(
            PAPER_PATH.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
        )
    ) as connection:
        rows = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
        ).fetchall()
        digest = hashlib.sha256(
            json.dumps(rows, separators=(",", ":")).encode()
        ).hexdigest()
        if digest != PAPER_SCHEMA_SHA256 or connection.execute(
            "PRAGMA integrity_check"
        ).fetchall() != [("ok",)]:
            raise ValueError("paper schema rejected")
    paper = ReviewPaperStore(PAPER_PATH, starting_cash=Decimal("10000"), read_only=True)
    paper.reconstruct_ledger()
    counts = len(paper.history()), ArmedSessionStore(SESSION_PATH).qualify()
    if any(count > 1000000 for count in counts):
        raise ValueError("runtime inventory exceeds evidence bound")
    return counts


def preflight_runtime() -> dict[str, object]:
    """Read-only filesystem/store inspection, without credential or provider reads."""
    result = {
        "schema": "production-paper-runtime-preflight/v1",
        "status": "BLOCKED",
        "paper_records": None,
        "session_reservations": None,
        "alpaca_credential_reads": 0,
        "robinhood_credential_reads": 0,
        "alpaca_http_calls": 0,
        "robinhood_application_calls": 0,
        "paper_trade_mutations": 0,
        "runtime_writes": 0,
        "scheduler_mutations": 0,
        "broker_mutations": 0,
    }
    try:
        _paths()
        if not RUNTIME_ROOT.exists():
            result["status"] = "ABSENT"
        else:
            records, reservations = _compatible()
            result.update(
                status="PRESENT_COMPATIBLE",
                paper_records=records,
                session_reservations=reservations,
            )
    except Exception:
        pass
    return result


def provision_runtime() -> dict[str, object]:
    """Protected fixed-store provisioning. Incompatible existing state is preserved."""
    before = preflight_runtime()
    if before["status"] == "BLOCKED":
        raise ValueError("runtime blocked")
    if before["status"] == "PRESENT_COMPATIBLE":
        return {
            "runtime_status": "ALREADY_PROVISIONED",
            "paper_records": before["paper_records"],
            "session_reservations": before["session_reservations"],
        }
    # Only this exact child is created. Parent storage provisioning is separate.
    if not RUNTIME_ROOT.parent.is_dir():
        raise ValueError("runtime parent absent")
    RUNTIME_ROOT.mkdir()
    _paths_before_creation = (PAPER_PATH, SESSION_PATH)
    if any(p.exists() for p in _paths_before_creation):
        raise ValueError("runtime changed")
    _paths(complete=False)
    with PAPER_PATH.open("xb"):
        pass
    _paths(complete=False)
    ReviewPaperStore(PAPER_PATH, starting_cash=Decimal("10000"))
    ArmedSessionStore(SESSION_PATH).initialize()
    _paths()
    records, reservations = _compatible()
    if records or reservations:
        raise ValueError("fresh stores not empty")
    for path in (PAPER_PATH, SESSION_PATH):
        with path.open("r+b") as stream:
            os.fsync(stream.fileno())
    return {
        "runtime_status": "PROVISIONED",
        "paper_records": 0,
        "session_reservations": 0,
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("INVALID_ARGUMENTS")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="Qualify fixed D1 runtime and credential readiness only."
    )
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--qualify", choices=(QUALIFY_INTERLOCK,))
    parser.add_argument("--evidence", type=Path)
    return parser


def _admit_source(head: str, tree: str) -> tuple[Path, ...]:
    from trading_bot.review_paper.armed_session_host import admit_armed_session_host

    return admit_armed_session_host(head, tree)


def _evidence_path(path: Path, roots: tuple[Path, ...]) -> None:
    if (
        not path.is_absolute()
        or path.exists()
        or path.is_symlink()
        or not path.parent.is_dir()
        or any(
            path.resolve().is_relative_to(root.resolve())
            for root in (*roots, RUNTIME_ROOT)
        )
    ):
        raise ValueError("evidence rejected")
    for ancestor in (path, *path.parents):
        if ancestor.exists() and (
            ancestor.is_symlink()
            or getattr(ancestor.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("evidence redirection rejected")


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if (args.preflight and args.evidence is not None) or (
            args.qualify and args.evidence is None
        ):
            raise ValueError("INVALID_ARGUMENTS")
        roots = _admit_source(args.expected_head, args.expected_tree)
        if args.preflight:
            result = preflight_runtime()
            result.update(
                source_head=args.expected_head, source_tree=args.expected_tree
            )
            print(json.dumps(result, sort_keys=True))
            return 3 if result["status"] == "BLOCKED" else 0
        _evidence_path(args.evidence, roots)
        result = {
            "schema": "production-paper-runtime-qualification/v1",
            "source_head": args.expected_head,
            "source_tree": args.expected_tree,
            "status": "BLOCKED",
            "runtime_status": "NOT_QUALIFIED",
            "paper_records": None,
            "session_reservations": None,
            "alpaca_credential_reads": None,
            "robinhood_credential_reads": None,
            "persisted_oauth_available": False,
            "alpaca_http_calls": 0,
            "robinhood_application_calls": 0,
            "paper_trade_mutations": 0,
            "scheduler_mutations": 0,
            "broker_mutations": 0,
            "effect_counts_complete": False,
        }
        # Exclusive evidence destination is reserved before any protected effects.
        with args.evidence.open("xb") as stream:
            try:
                result.update(provision_runtime())
                with read_current_product_alpaca_secrets():
                    pass
                result["alpaca_credential_reads"] = 2
                available = persisted_oauth_availability()
                if (
                    type(available.persisted_oauth_available) is not bool
                    or available.oauth_storage_reads != 2
                ):
                    raise ValueError("OAuth evidence rejected")
                result["robinhood_credential_reads"] = 2
                result["persisted_oauth_available"] = (
                    available.persisted_oauth_available
                )
                result["effect_counts_complete"] = True
                if available.persisted_oauth_available:
                    result["status"] = "READY_FOR_MANUAL_PAPER_SESSION"
            except Exception:
                pass
            payload = (
                json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode()
            if len(payload) > 4096:
                raise ValueError("evidence exceeds bound")
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "READY_FOR_MANUAL_PAPER_SESSION" else 3
    except Exception:
        print(
            '{"schema":"production-paper-runtime-qualification/v1","status":"BLOCKED"}',
            file=sys.stderr,
        )
        return 3
