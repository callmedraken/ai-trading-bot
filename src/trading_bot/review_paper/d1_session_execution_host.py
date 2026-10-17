"""Fixed D1R8 composition; importing this module performs no operation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.review_paper import d1_session_authorization as prerequisite
from trading_bot.review_paper import d1_session_execution as consumer
from trading_bot.review_paper.d1_session_execution_store import (
    BRANCH,
    PRODUCER_HEAD,
    PRODUCER_TREE,
)

WORKTREE = Path(r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-execution")
PRODUCER_WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-d1-session-authorization"
)
RUNTIME_ROOT = Path(r"F:\AITradingBot\Arch134D1")


def admit_source(source: prerequisite.Source) -> tuple[Path, ...]:
    """Read-only local/tracking/live/registry/import checks on both frozen sources."""
    if (
        os.name != "nt"
        or source.branch != BRANCH
        or Path(__file__).resolve().parents[3] != WORKTREE.resolve()
    ):
        raise ValueError("fixed Windows consumer source required")
    roots = None
    for root, branch, head, tree in (
        (WORKTREE, BRANCH, source.head, source.tree),
        (PRODUCER_WORKTREE, prerequisite.BRANCH, PRODUCER_HEAD, PRODUCER_TREE),
    ):
        prerequisite.checked_path(root)

        def git(*args: str, root=root) -> str:
            return subprocess.run(
                ["git", "-C", str(root), *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.strip()

        checks = (
            (("branch", "--show-current"), branch),
            (("rev-parse", "HEAD"), head),
            (("rev-parse", "HEAD^{tree}"), tree),
            (("status", "--porcelain=v1", "--untracked-files=all"), ""),
            (("remote", "get-url", "origin"), prerequisite.ORIGIN),
            (("remote", "get-url", "--push", "origin"), prerequisite.ORIGIN),
            (
                ("rev-parse", "--symbolic-full-name", "@{upstream}"),
                "refs/remotes/origin/" + branch,
            ),
            (("rev-parse", "origin/" + branch), head),
            (("rev-parse", "origin/" + branch + "^{tree}"), tree),
            (
                ("ls-remote", "origin", "refs/heads/" + branch),
                head + "\trefs/heads/" + branch,
            ),
        )
        if Path(git("rev-parse", "--show-toplevel")).resolve() != root.resolve() or any(
            git(*args) != expected for args, expected in checks
        ):
            raise ValueError("source admission rejected")
        registry = tuple(
            Path(line[9:]).resolve()
            for line in git("worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        )
        if root.resolve() not in registry or (roots is not None and roots != registry):
            raise ValueError("worktree registry changed")
        roots = registry
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            locations = [
                getattr(module, "__file__", None),
                *getattr(module, "__path__", ()),
            ]
            if any(
                not p
                or not Path(p).resolve().is_relative_to(WORKTREE.resolve() / "src")
                for p in locations
            ):
                raise ValueError("mixed consumer imports")
    return roots


def persisted_auth(records: tuple[bytearray, ...]) -> object:
    """Public SDK models + single-yield bearer Auth, with no OAuth provider."""
    import httpx2
    from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("credential duplicate")
            value[key] = item
        return value

    if len(records) != 2:
        raise ValueError("fixed persisted pair required")
    token, client = (
        model.model_validate(json.loads(blob, object_pairs_hook=unique), strict=True)
        for blob, model in zip(
            records, (OAuthToken, OAuthClientInformationFull), strict=True
        )
    )
    if (
        not token.access_token
        or token.token_type.casefold() != "bearer"
        or not client.client_id
        or (token.expires_in is not None and token.expires_in <= 0)
    ):
        raise ValueError("persisted authentication rejected")
    access_token = token.access_token

    class PersistedBearer(httpx2.Auth):
        def __repr__(self) -> str:
            return "D1R8PersistedBearer(<redacted>)"

        __str__ = __repr__

        def auth_flow(self, request):
            if (
                request.url.scheme != "https"
                or request.url.host != "agent.robinhood.com"
                or request.url.path != "/mcp/trading"
            ):
                raise ValueError("fixed bearer endpoint required")
            request.headers["Authorization"] = "Bearer " + access_token
            yield request  # No response-driven retry, refresh or reacquisition.

    return PersistedBearer()


class FixedRuntime:
    """Lazy, fixed capabilities; construction reads no stores or credentials."""

    parent = prerequisite.PARENT
    paper_path = RUNTIME_ROOT / "paper.sqlite"
    session_path = RUNTIME_ROOT / "armed-sessions.sqlite"

    def __init__(self) -> None:
        self.read_targets = set()

    def clock(self) -> datetime:
        return datetime.now(UTC)

    def admit_source(self, source: prerequisite.Source) -> tuple[Path, ...]:
        return admit_source(source)

    def admit_runtime(self) -> None:
        from trading_bot.review_paper.production_paper_runtime import preflight_runtime

        if preflight_runtime()["status"] != "PRESENT_COMPATIBLE":
            raise ValueError("existing runtime required")

    def write_readiness(self) -> None:
        from trading_bot.review_paper.production_paper_runtime import (
            qualify_runtime_write_readiness,
        )

        result = qualify_runtime_write_readiness()
        if set(result.values()) != {"WRITE_READY"}:
            raise ValueError("rollback readiness rejected")

    def read_credential(self, target: str) -> bytearray:
        from trading_bot.arch133_verifier.credentials import WindowsCredentialReader
        from trading_bot.review_paper.alpaca_windows_credentials import (
            API_KEY_TARGET,
            API_SECRET_TARGET,
            read_fixed_current_product_credential,
        )

        if target in self.read_targets or target not in {
            API_KEY_TARGET,
            API_SECRET_TARGET,
            consumer.TOKEN_TARGET,
            consumer.CLIENT_TARGET,
        }:
            raise ValueError("credential target consumed or rejected")
        self.read_targets.add(target)
        if target in {API_KEY_TARGET, API_SECRET_TARGET}:
            return read_fixed_current_product_credential(target)
        return WindowsCredentialReader().read_generic(target)

    def alpaca_transport(self) -> object:
        from trading_bot.market_data.alpaca_http import (
            StdlibAlpacaHistoricalBarsTransport,
        )

        return StdlibAlpacaHistoricalBarsTransport()

    def robinhood(self, records: tuple[bytearray, ...]) -> tuple:
        from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
        from trading_bot.robinhood_mcp.sdk_transport import (
            RobinhoodMcpStreamableHttpTransport,
            create_robinhood_agentic_account_resolver,
        )

        auth = persisted_auth(records)
        transport = RobinhoodMcpStreamableHttpTransport(lambda: auth)
        return RobinhoodReviewReadAdapter(
            transport
        ), create_robinhood_agentic_account_resolver(transport)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("D1R8 arguments rejected")


def build_parser() -> argparse.ArgumentParser:
    """Only reviewed proof assertions, never semantic selectors or destinations."""
    parser = _Parser(allow_abbrev=False)
    parser.add_argument("--accepted-head", required=True)
    parser.add_argument("--accepted-tree", required=True)
    parser.add_argument("--reviewed-d1r7-bytes", required=True, type=int)
    parser.add_argument("--reviewed-d1r7-sha256", required=True)
    parser.add_argument("--publication-confirmed", required=True, choices=("YES",))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Future separately reviewed operation only; absent from runner dispatch."""
    try:
        args = build_parser().parse_args(argv)
        proof = consumer.ReviewedProof(
            prerequisite.Source(BRANCH, args.accepted_head, args.accepted_tree),
            args.reviewed_d1r7_bytes,
            args.reviewed_d1r7_sha256,
            args.publication_confirmed == "YES",
        )
        if not sys.stdin.isatty():
            raise ValueError("interactive D1R8 authorization required")
        interlock = input("D1R8 separate session authorization: ")
        result = consumer.run_session(FixedRuntime(), proof, interlock)
        print(result)
        return 0 if result in {"NO_SIGNAL", "RISK_REJECTED", "PAPER_EXECUTED"} else 2
    except (Exception, KeyboardInterrupt):
        print("D1R8_STOP_CONSUMED_OR_UNADMITTED", file=sys.stderr)
        return 2
