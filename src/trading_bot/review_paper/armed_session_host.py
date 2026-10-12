"""Fixed 134-D1 host composition; native credential qualification is separate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.market_data import AlpacaDailySnapshotProvider
from trading_bot.review_paper.armed_session import (
    ARM_INTERLOCK,
    ArmedSessionPolicy,
    run_armed_production_paper_session,
)
from trading_bot.review_paper.armed_session_store import ArmedSessionStore
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.sdk_transport import RobinhoodMcpStreamableHttpTransport
from trading_bot.robinhood_mcp.windows_oauth import (
    create_windows_robinhood_oauth_factory,
)
from trading_bot.robinhood_paper_operator import admit_robinhood_paper_source
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract

BRANCH = "feature/robinhood-production-paper-mvp"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
RUNTIME_ROOT = Path(r"F:\AITradingBot\Arch134D1")
PAPER_PATH = RUNTIME_ROOT / "paper.sqlite"
SESSION_PATH = RUNTIME_ROOT / "armed-sessions.sqlite"


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("INVALID_ARGUMENTS")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Arm one current-product synthetic paper session.")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--arm", choices=(ARM_INTERLOCK,))
    parser.add_argument("--preflight", action="store_true")
    return parser


def create_current_product_alpaca_provider() -> AlpacaDailySnapshotProvider:
    """Narrow frozen credential-binding seam, intentionally fail closed.

    The retained native reader imports C1/C3 operational authority. D1 must not
    revive that graph, read environment credentials, or invent an unreviewed
    secret-store reader. A later protected qualification must bind this exact
    source-owned seam to the existing HTTPS/daily provider. No CLI plugin input.
    """
    raise RuntimeError("ALPACA_CREDENTIAL_BINDING_NOT_QUALIFIED")


def _forbid_interactive(_url: str) -> None:
    raise RuntimeError("interactive OAuth renewal forbidden")


class _QuoteOnly:
    def __init__(self, transport: RobinhoodMcpStreamableHttpTransport) -> None:
        self.transport = transport
        self.used = False

    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if self.used:
            raise RuntimeError("quote budget exhausted")
        self.used = True
        return self.transport.get_equity_quotes(arguments)

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        raise RuntimeError("quote-only boundary")

    def review_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        raise RuntimeError("quote-only boundary")

    def get_equity_historicals(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        raise RuntimeError("quote-only boundary")


def create_current_product_quote_adapter() -> RobinhoodReviewReadAdapter:
    oauth = create_windows_robinhood_oauth_factory(
        redirect_uri="http://127.0.0.1:8765/callback",
        browser_opener=_forbid_interactive,
    )
    return RobinhoodReviewReadAdapter(
        _QuoteOnly(RobinhoodMcpStreamableHttpTransport(oauth))
    )


def admit_armed_session_host(head: str, tree: str) -> tuple[Path, ...]:
    roots = admit_robinhood_paper_source(
        expected_branch=BRANCH, expected_head=head, expected_tree=tree
    )
    root = Path(__file__).resolve().parents[3]
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(
                root / "src"
            ):
                raise ValueError("mixed import roots")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()

    if (
        git("remote", "get-url", "origin") != ORIGIN
        or git("rev-parse", "origin/" + BRANCH) != head
        or git("rev-parse", "origin/" + BRANCH + "^{tree}") != tree
        or git("ls-remote", "origin", "refs/heads/" + BRANCH)
        != head + "\trefs/heads/" + BRANCH
    ):
        raise ValueError("remote source differs")
    return roots


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if (args.preflight and args.arm is not None) or (
            not args.preflight and not args.arm
        ):
            raise ValueError("INVALID_ARGUMENTS")
        roots = admit_armed_session_host(args.expected_head, args.expected_tree)
        output = args.evidence
        execution_output = output.with_name(output.name + ".execute.json")
        if (
            not output.is_absolute()
            or output.is_symlink()
            or not output.parent.is_dir()
            or output.exists()
            or execution_output.exists()
            or any(output.resolve().is_relative_to(root) for root in roots)
            or output.resolve().is_relative_to(RUNTIME_ROOT.resolve())
        ):
            raise ValueError("evidence admission failed")
        now = datetime.now(UTC)
        target = now.astimezone(ZoneInfo("America/New_York")).date()
        if NYSEPublishedRegularSessionAuthority().schedule_for(target) is None:
            raise ValueError("target date not published session")
        if not PAPER_PATH.is_file() or not RUNTIME_ROOT.is_dir():
            raise ValueError("qualified existing runtime/store required")
        contract = ProductionStrategyContract(
            target,
            args.expected_head,
            args.expected_tree,
            Symbol("SPY"),
            MovingAverageCrossoverConfig(2, 3, Decimal("1")),
        )
        if args.preflight:
            print(
                json.dumps(
                    {
                        "schema": "armed-paper-preflight/v1",
                        "status": "BLOCKED",
                        "reason": "ALPACA_CREDENTIAL_BINDING_NOT_QUALIFIED",
                        "provider_calls": 0,
                        "paper_mutations": 0,
                    },
                    sort_keys=True,
                )
            )
            return 3
        result = run_armed_production_paper_session(
            contract=contract,
            store=ReviewPaperStore(PAPER_PATH, starting_cash=Decimal("10000")),
            session_store=ArmedSessionStore(SESSION_PATH),
            policy=ArmedSessionPolicy(RiskLimits()),
            expected_branch=BRANCH,
            evidence_path=output,
            execute_evidence_path=execution_output,
            arm_interlock=args.arm,
            clock=lambda: datetime.now(UTC),
            sleeper=time.sleep,
            admit_source=lambda: admit_armed_session_host(
                args.expected_head, args.expected_tree
            ),
            alpaca_provider=create_current_product_alpaca_provider,
            quote_adapter=create_current_product_quote_adapter,
        )
        print(json.dumps(result, sort_keys=True))
        return (
            0
            if result["status"] in {"NO_SIGNAL", "PAPER_EXECUTED", "ALREADY_COMPLETED"}
            else 3
        )
    except Exception:
        print('{"schema":"armed-paper-host/v1","status":"BLOCKED"}', file=sys.stderr)
        return 3
