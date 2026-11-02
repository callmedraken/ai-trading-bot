"""Registered P5B protected read operation; never used by source verification."""

from __future__ import annotations

import hashlib
import stat
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.desktop_paper.robinhood_reconciliation import (
    observe_robinhood_baseline,
)
from trading_bot.robinhood_mcp.current_read_transport import (
    READ_TOOLS,
    RobinhoodCurrentReadTransport,
)

SCHEMA = "arch147-p5b-robinhood-read-reconcile/v1"
PRODUCTION_FILES = (
    Path(r"F:\AI\desktop-bot-state\p5\simulated-paper.sqlite"),
    Path(r"F:\AI\desktop-bot-state\p5\lifecycle.jsonl"),
    Path(r"F:\AI\desktop-bot-state\p5\simulated-paper.sqlite-wal"),
    Path(r"F:\AI\desktop-bot-state\p5\simulated-paper.sqlite-shm"),
    Path(r"F:\AI\desktop-bot-state\p5\simulated-paper.sqlite-journal"),
)


def _production_identities() -> dict[str, object]:
    identities = {}
    for path in PRODUCTION_FILES:
        for ancestor in (*reversed(path.parents), path):
            try:
                fact = ancestor.lstat()
            except FileNotFoundError:
                continue
            if (
                stat.S_ISLNK(fact.st_mode)
                or getattr(fact, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise RuntimeError("PRODUCTION_ALIAS_REJECTED")
        try:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            identities[path.name] = {"exists": True, "sha256": digest.hexdigest()}
        except FileNotFoundError:
            identities[path.name] = {"exists": False, "sha256": None}
    return identities


def _transport() -> RobinhoodCurrentReadTransport:
    # Import/composition only occurs inside the separately reviewed preflight.
    from trading_bot.robinhood_mcp.windows_oauth import (
        create_windows_robinhood_oauth_factory,
    )

    return RobinhoodCurrentReadTransport(
        create_windows_robinhood_oauth_factory(
            redirect_uri="http://127.0.0.1:8765/robinhood/callback"
        )
    )


def preflight() -> dict[str, object]:
    """One attempt, sanitized even on parser, OAuth, transport, or state failure.

    The unified runner owns exact integrated-source admission and create-only
    external evidence. There is no CLI, retry, paper-account open, or SQL call.
    """
    before = None
    after = None
    transport = None
    observation = None
    attempted_at = datetime.now(UTC)
    diagnostic = "RECONCILIATION_FAILED"
    try:
        before = _production_identities()
        transport = _transport()
        observation = observe_robinhood_baseline(
            transport, observed_at=attempted_at
        ).sanitized()
        diagnostic = "NONE"
    except Exception:
        # Never serialize exception text, args, repr, traceback, or payloads.
        diagnostic = "RECONCILIATION_FAILED"
    finally:
        try:
            after = _production_identities()
        except Exception:
            diagnostic = "PRODUCTION_IDENTITY_UNAVAILABLE"
    unchanged = before is not None and after is not None and before == after
    if not unchanged:
        diagnostic = "PRODUCTION_STATE_CHANGED_OR_UNAVAILABLE"
    passed = diagnostic == "NONE" and unchanged and observation is not None
    return {
        "schema": SCHEMA,
        "attempted_at": attempted_at.isoformat(),
        "status": "PASS" if passed else "BLOCKED",
        "reconciliation_status": "READ_ONLY_CONNECTED"
        if passed
        else "RECONCILIATION_FAILED",
        "diagnostic": diagnostic,
        "observation": observation,
        "required_read_tools": list(READ_TOOLS),
        "observed_read_tools": []
        if transport is None
        else list(transport.observed_read_tools),
        "provider_call_counts": dict.fromkeys(READ_TOOLS, 0)
        if transport is None
        else dict(transport.call_counts),
        "mutation_call_count": 0,
        "order_review_count": 0,
        "order_preview_count": 0,
        "order_placement_count": 0,
        "order_cancel_count": 0,
        "p5_financial_state_mutation_count": 0,
        "final_holdout_access_count": 0,
        "alpaca_call_count": 0,
        "credential_values_exposed": False,
        "production_state_before": before,
        "production_state_after": after,
        "production_state_unchanged": unchanged,
    }
