"""134-B3Q one-attempt historical qualification; real execution is protected.

No provider semantics are accepted from argv. Evidence is an exclusive, bounded
canonical JSONL journal. The pre-call ambiguous record survives interrupted calls.
Free-form provider guide/errors are never persisted or exposed.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import warnings
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Final
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.strategy_market_history import (
    materialize_production_strategy_history,
)
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.historical import (
    RobinhoodDailyHistory,
    RobinhoodDailyHistoryRequest,
    parse_equity_historicals_response,
)
from trading_bot.robinhood_mcp.models import RobinhoodMcpSchemaError
from trading_bot.robinhood_mcp.sdk_transport import RobinhoodMcpStreamableHttpTransport
from trading_bot.robinhood_mcp.windows_oauth import (
    LoopbackOAuthError,
    create_windows_robinhood_oauth_factory,
)
from trading_bot.robinhood_paper_operator import admit_robinhood_paper_source
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract

BRANCH: Final = "feature/robinhood-production-strategy-live-paper"
ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
AUTHORIZATION: Final = "AUTHORIZE_ARCH134_B3Q_ONE_HISTORICAL_READ"
SYMBOL: Final = "SPY"
LONG_WINDOW: Final = 3
REDIRECT_URI: Final = "http://127.0.0.1:8765/callback"
MAX_EVIDENCE_BYTES: Final = 64 * 1024
_DATETIME_TYPE = datetime


class HistoryQualificationError(RuntimeError):
    """Fixed local error; no provider details, automatic retry or effect permit."""


def qualification_request(requested_at: datetime) -> RobinhoodDailyHistoryRequest:
    """Select completed history on one published XNYS target-session date."""
    request = RobinhoodDailyHistoryRequest(
        Symbol(SYMBOL),
        requested_at,
        LONG_WINDOW,
        BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
    )
    target = request.requested_at.astimezone(ZoneInfo("America/New_York")).date()
    if (
        not request.calendar.is_trading_session(request.requested_at)
        or NYSEPublishedRegularSessionAuthority().schedule_for(target) is None
    ):
        raise HistoryQualificationError(
            "Qualification requires a published session date"
        )
    return request


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()


def admit_history_qualification_source(head: str, tree: str) -> tuple[Path, ...]:
    """Exact source/local remote/live remote admission; never fetch or repair."""
    roots = admit_robinhood_paper_source(
        expected_branch=BRANCH,
        expected_head=head,
        expected_tree=tree,
    )
    root = Path(__file__).resolve().parents[2]
    ref = "refs/heads/" + BRANCH
    if (
        root not in roots
        or _git(root, "remote", "get-url", "origin") != ORIGIN
        or _git(root, "ls-remote", "origin", ref) != head + "\t" + ref
        or _git(root, "rev-parse", "origin/" + BRANCH) != head
        or _git(root, "rev-parse", "origin/" + BRANCH + "^{tree}") != tree
    ):
        raise HistoryQualificationError("Qualification source mismatch")
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(
                root / "src"
            ):
                raise HistoryQualificationError("Qualification import source mismatch")
    return roots


def _admit_output(path: Path, roots: tuple[Path, ...]) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise HistoryQualificationError("Qualification evidence path rejected")
    output = path.resolve()
    if (
        path.is_symlink()
        or output.exists()
        or not output.parent.is_dir()
        or any(output.is_relative_to(root) for root in roots)
    ):
        raise HistoryQualificationError("Qualification evidence path rejected")
    return output


def preflight_history_qualification(
    *,
    expected_head: str,
    expected_tree: str,
    evidence_path: Path,
) -> dict[str, object]:
    """Read-only/provider-free source, calendar and fresh evidence-path check."""
    try:
        roots = admit_history_qualification_source(expected_head, expected_tree)
        _admit_output(evidence_path, roots)
        request = qualification_request(datetime.now(UTC))
        return _facts(expected_head, expected_tree, request) | {
            "status": "PASS",
            "phase": "PREFLIGHT",
            "historical_attempts": 0,
        }
    except Exception:
        raise HistoryQualificationError("Qualification preflight blocked") from None


def _facts(
    head: str, tree: str, request: RobinhoodDailyHistoryRequest
) -> dict[str, object]:
    return {
        "schema": "robinhood-history-qualification/v1",
        "source_head": head,
        "source_tree": tree,
        "source_branch": BRANCH,
        "tool": "get_equity_historicals",
        "symbol": SYMBOL,
        "long_window": LONG_WINDOW,
        "requested_at": request.requested_at.isoformat(),
        "arguments": request.arguments(),
        "calendar": XNYS_CALENDAR_DESCRIPTOR.version,
        "sessions": [item.session_date.isoformat() for item in request.sessions()],
        "other_application_calls": 0,
        "retry_permitted": False,
    }


def _append(output: BinaryIO, facts: dict[str, object]) -> None:
    encoded = (
        json.dumps(
            facts,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    if output.tell() + len(encoded) > MAX_EVIDENCE_BYTES:
        raise HistoryQualificationError("Qualification evidence bound exceeded")
    output.write(encoded)
    output.flush()
    os.fsync(output.fileno())


def _forbid_browser(_url: str) -> object:
    raise LoopbackOAuthError("Interactive OAuth is forbidden")


class _HistoryOnlyTransport:
    """One exact request through the accepted transport; no other capabilities."""

    def __init__(
        self,
        transport: RobinhoodMcpStreamableHttpTransport,
        request: RobinhoodDailyHistoryRequest,
        output: BinaryIO,
        facts: dict[str, object],
    ) -> None:
        self.transport = transport
        self.request = request
        self.output = output
        self.facts = facts
        self.attempts = 0
        self.response_returned = False
        self.started_at: datetime | None = None
        self.captured_at: datetime | None = None

    def get_equity_historicals(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        if self.attempts or dict(arguments) != self.request.arguments():
            raise HistoryQualificationError("Historical qualification budget rejected")
        started_at = datetime.now(UTC)
        if (
            type(started_at) is not _DATETIME_TYPE
            or started_at.tzinfo is None
            or started_at.utcoffset() is None
            or started_at < self.request.requested_at
        ):
            raise HistoryQualificationError("Qualification call time rejected")
        self.started_at = started_at.astimezone(UTC)
        _append(
            self.output,
            self.facts
            | {
                "status": "AMBIGUOUS_PROVIDER_EFFECT",
                "phase": "CALL_STARTED",
                "historical_attempts": 1,
                "call_started_at": self.started_at.isoformat(),
            },
        )
        self.attempts = 1
        response = self.transport.get_equity_historicals(arguments)
        self.response_returned = True
        captured_at = datetime.now(UTC)
        if (
            type(captured_at) is not _DATETIME_TYPE
            or captured_at.tzinfo is None
            or captured_at.utcoffset() is None
        ):
            raise HistoryQualificationError("Qualification capture time rejected")
        self.captured_at = captured_at.astimezone(UTC)
        if self.captured_at < self.started_at:
            raise HistoryQualificationError("Qualification capture time rejected")
        return response


def _discard_log(*_args: object, **_kwargs: object) -> None:
    pass


@contextmanager
def _quiet_provider() -> Iterator[None]:
    streams = sys.stdout, sys.stderr
    for stream in streams:
        stream.flush()
    previous_disable, previous_handle = (
        logging.root.manager.disable,
        logging.Logger.handle,
    )
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        redirect_stdout(sink),
        redirect_stderr(sink),
        warnings.catch_warnings(),
        ExitStack() as stack,
    ):
        for descriptor in (1, 2):
            saved = os.dup(descriptor)
            stack.callback(os.close, saved)
            stack.callback(os.dup2, saved, descriptor)
            os.dup2(sink.fileno(), descriptor)
        try:
            logging.disable(sys.maxsize)
            logging.Logger.handle = _discard_log
            warnings.simplefilter("ignore")
            yield
        finally:
            try:
                for stream in streams:
                    stream.flush()
            finally:
                logging.Logger.handle = previous_handle
                logging.disable(previous_disable)


def run_history_qualification(
    *,
    authorization: str,
    expected_head: str,
    expected_tree: str,
    evidence_path: Path,
) -> str:
    """Protected one-shot execution. Never call in CI except with all edges faked.

    The last complete journal record is authoritative. CALL_STARTED means STOP
    and reconciliation if no complete terminal record follows. A returned response
    rejected by the strict parser is FAIL; transport uncertainty is ambiguous.
    """
    if type(authorization) is not str or authorization != AUTHORIZATION:
        raise HistoryQualificationError("B3Q authorization required")
    try:
        roots = admit_history_qualification_source(expected_head, expected_tree)
        output_path = _admit_output(evidence_path, roots)
        request = qualification_request(datetime.now(UTC))
        facts = _facts(expected_head, expected_tree, request)
        contract = ProductionStrategyContract(
            request.requested_at.astimezone(ZoneInfo("America/New_York")).date(),
            expected_head,
            expected_tree,
            request.symbol,
            MovingAverageCrossoverConfig(2, LONG_WINDOW, Decimal("1")),
        )
        with output_path.open("xb") as output:
            _append(
                output,
                facts
                | {
                    "status": "BLOCKED",
                    "phase": "RESERVED",
                    "historical_attempts": 0,
                },
            )
            bounded = None
            captured_at = None
            safe_response = None
            response_sha256 = None
            reason = "COMPOSITION_BLOCKED"
            status = "BLOCKED"
            try:
                with _quiet_provider():
                    oauth = create_windows_robinhood_oauth_factory(
                        redirect_uri=REDIRECT_URI,
                        browser_opener=_forbid_browser,
                    )
                    bounded = _HistoryOnlyTransport(
                        RobinhoodMcpStreamableHttpTransport(oauth),
                        request,
                        output,
                        facts,
                    )
                    history = RobinhoodReviewReadAdapter(bounded).equity_daily_history(
                        request
                    )
                    captured_at = bounded.captured_at
                    evidence = materialize_production_strategy_history(
                        contract,
                        history,
                        captured_at=captured_at,
                    )
                    # Persist only parser-validated typed market fields. guide is
                    # arbitrary provider text; retain its presence, never its bytes.
                    response = json.loads(evidence.history.response_bytes)
                    safe_response = {"data": response["data"], "guide_present": True}
                    response_sha256 = sha256(
                        evidence.history.response_bytes
                    ).hexdigest()
                    admit_history_qualification_source(expected_head, expected_tree)
                status, reason = "PASS", "STRICT_B3_MATERIALIZATION_PASSED"
            except RobinhoodMcpSchemaError:
                if bounded is not None and bounded.response_returned:
                    status, reason = "FAIL", "STRICT_B3_SCHEMA_REJECTED"
                else:
                    status, reason = (
                        "AMBIGUOUS_PROVIDER_EFFECT",
                        "CALL_RESULT_UNCLASSIFIED",
                    )
            except Exception:
                if bounded is not None and bounded.attempts:
                    if bounded.response_returned:
                        status, reason = "FAIL", "POST_RESPONSE_VALIDATION_REJECTED"
                    else:
                        status, reason = (
                            "AMBIGUOUS_PROVIDER_EFFECT",
                            "CALL_RESULT_UNCLASSIFIED",
                        )
            terminal = facts | {
                "status": status,
                "phase": "TERMINAL",
                "reason": reason,
                "historical_attempts": 0 if bounded is None else bounded.attempts,
                "captured_at": None
                if bounded is None or bounded.captured_at is None
                else bounded.captured_at.isoformat(),
                "response": safe_response,
                "canonical_response_sha256": response_sha256,
                "historical_data_sha256": None
                if safe_response is None
                else sha256(
                    json.dumps(
                        safe_response,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest(),
            }
            _append(output, terminal)
            return status
    except BaseException:
        # Interruptions may contain upstream exception text too. Keep the durable
        # CALL_STARTED fence and expose only this fixed local error.
        raise HistoryQualificationError(
            "Historical qualification stopped; preserve evidence"
        ) from None


def replay_history_qualification(
    journal: bytes,
    *,
    expected_head: str,
    expected_tree: str,
) -> RobinhoodDailyHistory:
    """Replay sanitized PASS market data through the unchanged B3 parser.

    guide is a required nonblank schema field, with no bar/adjustment authority.
    Only its presence is retained; a fixed replay disclosure replaces that omitted
    free text. This is evidence replay, never a fallback for a rejected live response.
    The original full-response digest is audit-only and cannot be reconstructed
    without the deliberately omitted guide. No OAuth/source/filesystem effects.
    """
    try:
        if type(journal) is not bytes or not 0 < len(journal) <= MAX_EVIDENCE_BYTES:
            raise ValueError
        records = [json.loads(line) for line in journal.splitlines()]
        if len(records) != 3:
            raise ValueError
        terminal = records[-1]
        requested_at = datetime.fromisoformat(terminal["requested_at"])
        request = qualification_request(requested_at)
        facts = _facts(expected_head, expected_tree, request)
        expected_keys = set(facts) | {
            "status",
            "phase",
            "reason",
            "historical_attempts",
            "captured_at",
            "response",
            "canonical_response_sha256",
            "historical_data_sha256",
        }
        if (
            set(terminal) != expected_keys
            or any(terminal[key] != value for key, value in facts.items())
            or terminal["status"] != "PASS"
            or terminal["phase"] != "TERMINAL"
            or terminal["reason"] != "STRICT_B3_MATERIALIZATION_PASSED"
            or type(terminal["historical_attempts"]) is not int
            or terminal["historical_attempts"] != 1
            or records[0]
            != facts
            | {
                "status": "BLOCKED",
                "phase": "RESERVED",
                "historical_attempts": 0,
            }
            or set(records[1])
            != set(facts)
            | {
                "status",
                "phase",
                "historical_attempts",
                "call_started_at",
            }
            or records[1]
            != facts
            | {
                "status": "AMBIGUOUS_PROVIDER_EFFECT",
                "phase": "CALL_STARTED",
                "historical_attempts": 1,
                "call_started_at": records[1]["call_started_at"],
            }
            or set(terminal["response"]) != {"data", "guide_present"}
            or terminal["response"]["guide_present"] is not True
        ):
            raise ValueError
        digest = terminal["canonical_response_sha256"]
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ValueError
        for line, record in zip(
            journal.splitlines(keepends=True), records, strict=True
        ):
            canonical = (
                json.dumps(
                    record,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            if line != canonical:
                raise ValueError
        if (
            terminal["historical_data_sha256"]
            != sha256(
                json.dumps(
                    terminal["response"],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
        ):
            raise ValueError
        captured = datetime.fromisoformat(terminal["captured_at"])
        started = datetime.fromisoformat(records[1]["call_started_at"])
        if started < request.requested_at or captured < started:
            raise ValueError
        history = parse_equity_historicals_response(
            {
                "data": terminal["response"]["data"],
                "guide": "B3Q evidence replay; original free-form guide withheld.",
            },
            request,
        )
        contract = ProductionStrategyContract(
            requested_at.astimezone(ZoneInfo("America/New_York")).date(),
            expected_head,
            expected_tree,
            request.symbol,
            MovingAverageCrossoverConfig(2, LONG_WINDOW, Decimal("1")),
        )
        materialize_production_strategy_history(contract, history, captured_at=captured)
        return history
    except Exception:
        raise HistoryQualificationError(
            "Qualification evidence replay rejected"
        ) from None
