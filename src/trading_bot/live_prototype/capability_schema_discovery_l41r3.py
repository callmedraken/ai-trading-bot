"""Effect-free L41R3 MCP-v2 interface observation successor.

This additive boundary normalizes only the MCP tool fields needed by the
existing sanitized L41 schema parser. It preserves L41R1/L41R2 behavior and
records metadata for review without calling any MCP tool.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import stat
import sys
import warnings
import webbrowser
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from contextlib import (
    AbstractAsyncContextManager,
    ExitStack,
    asynccontextmanager,
    contextmanager,
    redirect_stderr,
    redirect_stdout,
)
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from trading_bot.live_prototype.capability_operator import (
    L41_FEATURE_BRANCH,
    SourceAdmission,
    admit_l41_source,
)
from trading_bot.live_prototype.capability_schema_discovery import (
    InterfaceSchemaFacts,
    RobinhoodSchemaDiscoveryTransport,
    SchemaDiscoveryAttemptCounts,
    SchemaDiscoveryError,
)
from trading_bot.robinhood_mcp.sdk_transport import ROBINHOOD_TRADING_MCP_URL
from trading_bot.robinhood_mcp.windows_oauth import (
    create_windows_robinhood_oauth_factory,
)

L41R3_EVIDENCE_SCHEMA = "arch147-l41r3-mcp-v2-interface-observation/v1"
L41R3_OBSERVATION = "L41R3_MCP_V2_SCHEMA_DISCOVERY"
_CANONICAL_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_DISCOVERY_PAGES = 20
_MISSING = object()
_INSPECTED_TOOLS = frozenset(
    {"review_equity_order", "place_equity_order", "get_equity_tradability"}
)

_REASON_CODES = frozenset(
    {
        "L41R3_EVIDENCE_PATH_INVALID",
        "L41R3_SOURCE_ADMISSION_BLOCKED",
        "L41R3_OAUTH_FACTORY_FAILED",
        "L41R3_TRANSPORT_CREATE_FAILED",
        "L41R3_MCP_SESSION_OPEN_FAILED",
        "L41R3_TOOLS_LIST_FAILED",
        "L41R3_TOOL_INVENTORY_MALFORMED",
        "L41R3_TOOL_CURSOR_INVALID",
        "L41R3_TOOL_PAGINATION_BOUND_EXCEEDED",
        "L41R3_REQUIRED_SCHEMA_MISSING",
        "L41R3_DUPLICATE_SCHEMA",
        "L41R3_SCHEMA_CHANGED",
        "L41R3_SCHEMA_MALFORMED",
        "L41R3_SCHEMA_AMBIGUOUS",
        "L41R3_SCHEMA_BASELINE_INVALID",
        "L41R3_SESSION_CLOSE_FAILED",
        "L41R3_DISCOVERY_FAILED",
        "L41R3_ATTEMPT_COUNTS_INVALID",
        "L41R3_EVIDENCE_WRITE_FAILED",
        "L41R3_SCHEMA_METADATA_CAPTURED",
        "L41R3_SCHEMA_METADATA_CAPTURED_UNPINNED",
    }
)


class L41R3SchemaDiscoveryError(RuntimeError):
    """Fixed diagnostic with no provider text or secret material."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in _REASON_CODES else "L41R3_DISCOVERY_FAILED"
        super().__init__(self.reason)


class _McpSchemaClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...


@dataclass(frozen=True, slots=True)
class L41R3SchemaDiscoveryAttemptCounts:
    """L41R3 attempts; every MCP tool invocation remains prohibited."""

    oauth_scope_entry_attempts: int = 0
    mcp_session_open_attempts: int = 0
    browser_launches: int = 0
    tools_list_attempts: int = 0
    mcp_tool_invocation_attempts: int = 0
    get_accounts_attempts: int = 0
    get_equity_tradability_attempts: int = 0
    get_positions_attempts: int = 0
    get_orders_attempts: int = 0
    get_portfolio_attempts: int = 0
    get_quotes_attempts: int = 0
    review_equity_order_attempts: int = 0
    place_equity_order_attempts: int = 0
    cancel_equity_order_attempts: int = 0
    other_tool_attempts: int = 0


@dataclass(frozen=True, slots=True)
class L41R3SchemaDiscoveryResult:
    """Sanitized result; CAPTURED_FOR_REVIEW grants no operational authority."""

    status: str
    reason: str
    evidence_path: Path | None
    source: SourceAdmission | None
    attempt_counts: L41R3SchemaDiscoveryAttemptCounts
    schemas: tuple[InterfaceSchemaFacts, ...]


class _SessionFactory(Protocol):
    def __call__(
        self, oauth: object
    ) -> AbstractAsyncContextManager[_McpSchemaClient]: ...


class _OneShotBrowserOpener:
    """Permit one browser launch and retain no authorization URL."""

    __slots__ = ("_launch_count", "_opener")

    def __init__(self, opener: Callable[[str], object]) -> None:
        if not callable(opener):
            raise TypeError("browser opener must be callable")
        self._opener = opener
        self._launch_count = 0

    @property
    def launch_count(self) -> int:
        return self._launch_count

    def __call__(self, authorization_url: str) -> object:
        if self._launch_count != 0:
            raise RuntimeError("L41R3_BROWSER_LAUNCH_ALREADY_USED")
        self._launch_count = 1
        try:
            return self._opener(authorization_url)
        finally:
            del authorization_url


@dataclass(frozen=True, slots=True)
class _OAuthFactoryBundle:
    factory: Callable[[], object]
    browser_opener: _OneShotBrowserOpener


def _build_windows_oauth_factory() -> _OAuthFactoryBundle:
    browser_opener = _OneShotBrowserOpener(webbrowser.open)
    factory = create_windows_robinhood_oauth_factory(
        redirect_uri="http://127.0.0.1:8765/robinhood/callback",
        browser_opener=browser_opener,
    )
    return _OAuthFactoryBundle(factory, browser_opener)


class _NormalizedMcpClient:
    """Expose a minimal normalized tools/list projection to the old safe parser."""

    __slots__ = ("_client",)

    def __init__(self, client: _McpSchemaClient) -> None:
        self._client = client

    async def list_tools(self, *, cursor: str | None = None) -> object:
        listing = await self._client.list_tools(cursor=cursor)
        entries = _read_field(listing, "tools")
        if not isinstance(entries, Sequence) or isinstance(
            entries, (str, bytes, bytearray)
        ):
            raise SchemaDiscoveryError("L41R1_TOOL_INVENTORY_MALFORMED")
        normalized = [_normalize_tool(entry) for entry in entries]
        next_cursor = _read_cursor(listing)
        return {"tools": normalized, "next_cursor": next_cursor}


def _read_field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _read_present_field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name, _MISSING)
    return getattr(value, name, _MISSING)


def _normalize_tool(entry: object) -> dict[str, object]:
    name = _read_field(entry, "name")
    normalized: dict[str, object] = {"name": name}
    if type(name) is not str or name not in _INSPECTED_TOOLS:
        return normalized

    description = _read_field(entry, "description")
    if description is not None:
        normalized["description"] = description
    schema = _read_input_schema(entry)
    if schema is not _MISSING:
        normalized["inputSchema"] = schema
    return normalized


def _read_input_schema(entry: object) -> object:
    if isinstance(entry, Mapping):
        return entry.get("inputSchema", _MISSING)
    v2_schema = _read_present_field(entry, "input_schema")
    legacy_schema = _read_present_field(entry, "inputSchema")
    if v2_schema is not _MISSING and legacy_schema is not _MISSING:
        raise SchemaDiscoveryError("L41R1_SCHEMA_MALFORMED")
    if v2_schema is not _MISSING:
        return v2_schema
    return legacy_schema


def _read_cursor(listing: object) -> object:
    snake_cursor = _read_present_field(listing, "next_cursor")
    wire_cursor = _read_present_field(listing, "nextCursor")
    if snake_cursor is _MISSING:
        return None if wire_cursor is _MISSING else wire_cursor
    if wire_cursor is _MISSING:
        return snake_cursor
    if type(snake_cursor) is not str and snake_cursor is not None:
        raise SchemaDiscoveryError("L41R1_TOOL_CURSOR_INVALID")
    if type(wire_cursor) is not str and wire_cursor is not None:
        raise SchemaDiscoveryError("L41R1_TOOL_CURSOR_INVALID")
    if snake_cursor != wire_cursor:
        raise SchemaDiscoveryError("L41R1_TOOL_CURSOR_INVALID")
    return snake_cursor


@asynccontextmanager
async def _production_session(oauth: object) -> AsyncIterator[_McpSchemaClient]:
    try:
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        raise L41R3SchemaDiscoveryError("L41R3_MCP_SESSION_OPEN_FAILED") from None

    try:
        async with httpx2.AsyncClient(auth=oauth, timeout=60) as http:
            async with Client(
                streamable_http_client(
                    ROBINHOOD_TRADING_MCP_URL,
                    http_client=http,
                )
            ) as client:
                yield client
    except SchemaDiscoveryError:
        raise
    except Exception:
        raise L41R3SchemaDiscoveryError("L41R3_MCP_SESSION_OPEN_FAILED") from None


class L41R3SchemaDiscoveryTransport:
    """One-use schema transport with bounded tools/list and no tool-call API."""

    __slots__ = ("_transport",)

    def __init__(
        self,
        oauth_factory: Callable[[], object],
        *,
        session_factory: _SessionFactory | None = None,
        expected_schema_digests: Mapping[str, str] | None = None,
    ) -> None:
        raw_session_factory = (
            _production_session if session_factory is None else session_factory
        )

        @asynccontextmanager
        async def normalized_session(oauth: object) -> AsyncIterator[_McpSchemaClient]:
            async with raw_session_factory(oauth) as client:
                yield _NormalizedMcpClient(client)

        self._transport = RobinhoodSchemaDiscoveryTransport(
            oauth_factory,
            session_factory=normalized_session,
            expected_schema_digests=expected_schema_digests,
        )

    @property
    def attempt_counts(self) -> SchemaDiscoveryAttemptCounts:
        return self._transport.attempt_counts

    @property
    def schemas(self) -> tuple[InterfaceSchemaFacts, ...]:
        return self._transport.schemas

    def __enter__(self) -> L41R3SchemaDiscoveryTransport:
        self._transport.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return self._transport.__exit__(exc_type, exc, traceback)

    def discover(self) -> tuple[InterfaceSchemaFacts, ...]:
        return self._transport.discover()


def _discard_log(*args: object, **kwargs: object) -> None:
    del args, kwargs


@contextmanager
def _quiet_provider() -> Iterator[None]:
    """Discard SDK prints/logs/warnings and native stdout/stderr descriptors."""

    streams = sys.stdout, sys.stderr
    for stream in streams:
        stream.flush()
    previous_disable = logging.root.manager.disable
    previous_handle = logging.Logger.handle
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        redirect_stdout(sink),
        redirect_stderr(sink),
        warnings.catch_warnings(),
        ExitStack() as descriptors,
    ):
        for descriptor in (1, 2):
            saved = os.dup(descriptor)
            descriptors.callback(os.close, saved)
            descriptors.callback(os.dup2, saved, descriptor)
            os.dup2(sink.fileno(), descriptor)
        try:
            logging.disable(sys.maxsize)
            logging.Logger.handle = _discard_log
            warnings.simplefilter("ignore")
            yield
        finally:
            for stream in streams:
                stream.flush()
            logging.Logger.handle = previous_handle
            logging.disable(previous_disable)


def run_l41r3_mcp_v2_schema_discovery(
    *,
    evidence_dir: Path,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> L41R3SchemaDiscoveryResult:
    """Run the separately named one-shot MCP-v2 metadata observation."""

    return _run_with_dependencies(
        evidence_dir=evidence_dir,
        source_admitter=admit_l41_source,
        oauth_factory_builder=_build_windows_oauth_factory,
        transport_builder=lambda oauth_factory: L41R3SchemaDiscoveryTransport(
            oauth_factory,
            expected_schema_digests=expected_schema_digests,
        ),
        repository_root_resolver=_repository_root,
        expected_schema_digests=expected_schema_digests,
    )


def _run_with_dependencies(
    *,
    evidence_dir: Path,
    source_admitter: Callable[[Path], SourceAdmission],
    oauth_factory_builder: Callable[[], _OAuthFactoryBundle],
    transport_builder: Callable[[object], object],
    repository_root_resolver: Callable[[], Path],
    expected_schema_digests: Mapping[str, str] | None = None,
) -> L41R3SchemaDiscoveryResult:
    if not _valid_schema_baseline(expected_schema_digests):
        return _result_without_file("BLOCKED", "L41R3_SCHEMA_BASELINE_INVALID")
    try:
        output_dir = _fresh_evidence_dir(evidence_dir)
    except Exception:
        return _result_without_file("BLOCKED", "L41R3_EVIDENCE_PATH_INVALID")

    empty_counts = L41R3SchemaDiscoveryAttemptCounts()
    source: SourceAdmission | None = None
    try:
        candidate = source_admitter(repository_root_resolver())
        if type(candidate) is not SourceAdmission or not _source_is_accepted(candidate):
            raise L41R3SchemaDiscoveryError("L41R3_SOURCE_ADMISSION_BLOCKED")
        source = candidate
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R3_SOURCE_ADMISSION_BLOCKED",
            source,
            empty_counts,
            (),
        )

    browser_opener: _OneShotBrowserOpener | None = None
    try:
        with _quiet_provider():
            bundle = oauth_factory_builder()
        if type(bundle) is not _OAuthFactoryBundle or not callable(bundle.factory):
            raise TypeError
        browser_opener = bundle.browser_opener
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R3_OAUTH_FACTORY_FAILED",
            source,
            empty_counts,
            (),
        )

    try:
        with _quiet_provider():
            transport = transport_builder(bundle.factory)
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R3_TRANSPORT_CREATE_FAILED",
            source,
            empty_counts,
            (),
        )

    status = "BLOCKED"
    reason = "L41R3_DISCOVERY_FAILED"
    schemas: tuple[InterfaceSchemaFacts, ...] = ()
    try:
        with _quiet_provider():
            with transport as boundary:
                try:
                    discovered = boundary.discover()
                    if type(discovered) is not tuple or any(
                        type(item) is not InterfaceSchemaFacts for item in discovered
                    ):
                        raise L41R3SchemaDiscoveryError("L41R3_SCHEMA_MALFORMED")
                    schemas = discovered
                    status = "CAPTURED_FOR_REVIEW"
                    reason = "L41R3_SCHEMA_METADATA_CAPTURED"
                except SchemaDiscoveryError as error:
                    reason = _map_reason(error.reason)
                    retained = getattr(boundary, "schemas", ())
                    if type(retained) is tuple and all(
                        type(item) is InterfaceSchemaFacts for item in retained
                    ):
                        schemas = retained
                except L41R3SchemaDiscoveryError as error:
                    reason = error.reason
                except Exception:
                    reason = "L41R3_DISCOVERY_FAILED"
    except SchemaDiscoveryError as error:
        reason = _map_reason(error.reason)
    except L41R3SchemaDiscoveryError as error:
        reason = error.reason
    except Exception:
        reason = "L41R3_DISCOVERY_FAILED"

    counts = _read_attempt_counts(transport, browser_opener)
    if counts is None or not _counts_valid(counts, completed=bool(schemas)):
        status = "BLOCKED"
        reason = "L41R3_ATTEMPT_COUNTS_INVALID"
        counts = empty_counts if counts is None else counts
    elif status == "CAPTURED_FOR_REVIEW":
        if not _required_schemas_present(schemas):
            status = "BLOCKED"
            reason = "L41R3_REQUIRED_SCHEMA_MISSING"
        elif expected_schema_digests is None:
            reason = "L41R3_SCHEMA_METADATA_CAPTURED_UNPINNED"

    return _write_result(output_dir, status, reason, source, counts, schemas)


def _source_is_accepted(source: SourceAdmission) -> bool:
    return (
        source.branch == L41_FEATURE_BRANCH
        and source.head == source.origin_feature_head == source.origin_develop_head
        and source.tree == source.origin_feature_tree == source.origin_develop_tree
        and source.feature_authority == "PASS"
        and source.prospective_develop_authority == "PASS"
    )


def _valid_schema_baseline(baseline: Mapping[str, str] | None) -> bool:
    if baseline is None:
        return True
    required = {"review_equity_order", "place_equity_order"}
    if not isinstance(baseline, Mapping) or not required.issubset(baseline):
        return False
    if not set(baseline).issubset(_INSPECTED_TOOLS):
        return False
    return all(
        type(name) is str
        and type(digest) is str
        and _SHA256.fullmatch(digest) is not None
        for name, digest in baseline.items()
    )


def _map_reason(reason: str) -> str:
    if reason == "L41R1_SESSION_CLOSE_FAILED":
        return "L41R3_SESSION_CLOSE_FAILED"
    if reason.startswith("L41R1_"):
        mapped = "L41R3_" + reason.removeprefix("L41R1_")
        if mapped in _REASON_CODES:
            return mapped
    return "L41R3_DISCOVERY_FAILED"


def _read_attempt_counts(
    transport: object, browser_opener: _OneShotBrowserOpener | None
) -> L41R3SchemaDiscoveryAttemptCounts | None:
    try:
        counts = transport.attempt_counts
        launches = 0 if browser_opener is None else browser_opener.launch_count
    except Exception:
        return None
    if type(counts) is not SchemaDiscoveryAttemptCounts or type(launches) is not int:
        return None
    return L41R3SchemaDiscoveryAttemptCounts(
        oauth_scope_entry_attempts=counts.oauth_scope_entry_attempts,
        mcp_session_open_attempts=counts.mcp_session_open_attempts,
        browser_launches=launches,
        tools_list_attempts=counts.tools_list_attempts,
        mcp_tool_invocation_attempts=counts.mcp_tool_invocation_attempts,
        get_accounts_attempts=counts.get_accounts_attempts,
        get_equity_tradability_attempts=counts.get_equity_tradability_attempts,
        get_positions_attempts=counts.get_positions_attempts,
        get_orders_attempts=counts.get_orders_attempts,
        get_portfolio_attempts=counts.get_portfolio_attempts,
        get_quotes_attempts=counts.get_quotes_attempts,
        review_equity_order_attempts=counts.review_equity_order_attempts,
        place_equity_order_attempts=counts.place_equity_order_attempts,
        cancel_equity_order_attempts=counts.cancel_equity_order_attempts,
        other_tool_attempts=counts.other_tool_attempts,
    )


def _counts_valid(
    counts: L41R3SchemaDiscoveryAttemptCounts, *, completed: bool
) -> bool:
    positive = (
        counts.oauth_scope_entry_attempts,
        counts.mcp_session_open_attempts,
        counts.tools_list_attempts,
    )
    prohibited = (
        counts.mcp_tool_invocation_attempts,
        counts.get_accounts_attempts,
        counts.get_equity_tradability_attempts,
        counts.get_positions_attempts,
        counts.get_orders_attempts,
        counts.get_portfolio_attempts,
        counts.get_quotes_attempts,
        counts.review_equity_order_attempts,
        counts.place_equity_order_attempts,
        counts.cancel_equity_order_attempts,
        counts.other_tool_attempts,
    )
    if not all(type(value) is int and 0 <= value <= 1 for value in positive[:2]):
        return False
    if (
        type(counts.browser_launches) is not int
        or not 0 <= counts.browser_launches <= 1
    ):
        return False
    if type(positive[2]) is not int or not 0 <= positive[2] <= _MAX_DISCOVERY_PAGES:
        return False
    if any(type(value) is not int or value != 0 for value in prohibited):
        return False
    if completed:
        return positive[0] == 1 and positive[1] == 1 and positive[2] >= 1
    return True


def _required_schemas_present(schemas: Sequence[InterfaceSchemaFacts]) -> bool:
    return {schema.tool_name for schema in schemas} >= {
        "review_equity_order",
        "place_equity_order",
    }


def _repository_root() -> Path:
    root = Path(__file__).resolve().parents[3]
    if str(root).casefold() != str(_CANONICAL_ROOT).casefold():
        raise L41R3SchemaDiscoveryError("L41R3_SOURCE_ADMISSION_BLOCKED")
    return root


def _fresh_evidence_dir(candidate: Path) -> Path:
    path = Path(candidate)
    parent_root = _EVIDENCE_ROOT.resolve(strict=True)
    if (
        not path.is_absolute()
        or path.drive.casefold() != "f:"
        or path.exists()
        or path.is_symlink()
    ):
        raise ValueError("L41R3_EVIDENCE_PATH_INVALID")
    parent = path.parent.resolve(strict=True)
    if path.parent != parent or not parent.is_relative_to(parent_root):
        raise ValueError("L41R3_EVIDENCE_PATH_INVALID")
    current = parent
    while True:
        if current.resolve(strict=True) != current or _has_reparse_point(current):
            raise ValueError("L41R3_EVIDENCE_PATH_INVALID")
        if current == parent_root:
            break
        if current.parent == current or not current.is_relative_to(parent_root):
            raise ValueError("L41R3_EVIDENCE_PATH_INVALID")
        current = current.parent
    path.mkdir()
    return path


def _has_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _result_without_file(status: str, reason: str) -> L41R3SchemaDiscoveryResult:
    return L41R3SchemaDiscoveryResult(
        status,
        reason,
        None,
        None,
        L41R3SchemaDiscoveryAttemptCounts(),
        (),
    )


def _write_result(
    output_dir: Path,
    status: str,
    reason: str,
    source: SourceAdmission | None,
    attempt_counts: L41R3SchemaDiscoveryAttemptCounts,
    schemas: tuple[InterfaceSchemaFacts, ...],
) -> L41R3SchemaDiscoveryResult:
    if reason not in _REASON_CODES:
        status = "BLOCKED"
        reason = "L41R3_DISCOVERY_FAILED"
    path = output_dir / "evidence.json"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(
                json.dumps(
                    _evidence_payload(status, reason, source, attempt_counts, schemas),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                )
                + "\n"
            )
    except Exception:
        return L41R3SchemaDiscoveryResult(
            "BLOCKED",
            "L41R3_EVIDENCE_WRITE_FAILED",
            None,
            source,
            attempt_counts,
            schemas,
        )
    return L41R3SchemaDiscoveryResult(
        status, reason, path, source, attempt_counts, schemas
    )


def _source_payload(source: SourceAdmission | None) -> dict[str, object] | None:
    if source is None:
        return None
    return {
        "branch": source.branch,
        "head": source.head,
        "tree": source.tree,
        "origin_feature_head": source.origin_feature_head,
        "origin_feature_tree": source.origin_feature_tree,
        "origin_develop_head": source.origin_develop_head,
        "origin_develop_tree": source.origin_develop_tree,
        "feature_authority": source.feature_authority,
        "prospective_develop_authority": source.prospective_develop_authority,
    }


def _evidence_payload(
    status: str,
    reason: str,
    source: SourceAdmission | None,
    attempt_counts: L41R3SchemaDiscoveryAttemptCounts,
    schemas: tuple[InterfaceSchemaFacts, ...],
) -> dict[str, object]:
    return {
        "schema": L41R3_EVIDENCE_SCHEMA,
        "observation": L41R3_OBSERVATION,
        "one_shot": True,
        "status": status,
        "reason": reason,
        "source": _source_payload(source),
        "attempt_counts": {
            name: getattr(attempt_counts, name)
            for name in L41R3SchemaDiscoveryAttemptCounts.__dataclass_fields__
        },
        "browser_launches": attempt_counts.browser_launches,
        "schemas": [
            {
                name: getattr(schema, name)
                for name in InterfaceSchemaFacts.__dataclass_fields__
            }
            for schema in schemas
        ],
        "native_credential_read_count": None,
        "native_credential_write_count": None,
        "credential_store_accounting": "SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED",
        "trusted_binding": False,
        "provider_numeric_rules_derived": False,
        "automatic_retry": "FORBIDDEN",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture sanitized MCP-v2 Robinhood interface metadata (L41R3)."
    )
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        metavar="PATH",
        help="fresh absolute external F:\\AI\\temp evidence directory",
    )
    arguments = parser.parse_args(argv)
    result = run_l41r3_mcp_v2_schema_discovery(evidence_dir=arguments.evidence_dir)
    print(
        json.dumps(
            {
                "evidence_path": None
                if result.evidence_path is None
                else str(result.evidence_path),
                "reason": result.reason,
                "status": result.status,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if result.status == "CAPTURED_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
