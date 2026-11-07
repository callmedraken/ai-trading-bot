"""Effect-free interactive L41R2 Robinhood MCP schema discovery.

This additive successor preserves the consumed non-interactive L41R1 boundary.
It permits one source-owned browser authorization when the reviewed Windows
OAuth SDK requires it, and records only sanitized interface metadata.
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
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import (
    AbstractAsyncContextManager,
    ExitStack,
    contextmanager,
    redirect_stderr,
    redirect_stdout,
)
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from trading_bot.live_prototype.capability_operator import (
    SourceAdmission,
    _source_is_accepted,
    admit_l41_source,
)
from trading_bot.live_prototype.capability_schema_discovery import (
    InterfaceSchemaFacts,
    RobinhoodSchemaDiscoveryTransport,
    SchemaDiscoveryAttemptCounts,
    SchemaDiscoveryError,
    _validate_baseline,
)
from trading_bot.robinhood_mcp.windows_oauth import (
    create_windows_robinhood_oauth_factory,
)

L41R2_EVIDENCE_SCHEMA = "arch147-l41r2-interactive-interface-observation/v1"
L41R2_OBSERVATION = "L41R2_INTERACTIVE_SCHEMA_DISCOVERY"
_CANONICAL_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
_EVIDENCE_ROOT = Path(r"F:\AI\temp")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_DISCOVERY_PAGES = 20

_REASON_CODES = frozenset(
    {
        "L41R2_EVIDENCE_PATH_INVALID",
        "L41R2_SOURCE_ADMISSION_BLOCKED",
        "L41R2_OAUTH_FACTORY_FAILED",
        "L41R2_TRANSPORT_CREATE_FAILED",
        "L41R2_MCP_SESSION_OPEN_FAILED",
        "L41R2_TOOLS_LIST_FAILED",
        "L41R2_TOOL_INVENTORY_MALFORMED",
        "L41R2_TOOL_CURSOR_INVALID",
        "L41R2_TOOL_PAGINATION_BOUND_EXCEEDED",
        "L41R2_REQUIRED_SCHEMA_MISSING",
        "L41R2_DUPLICATE_SCHEMA",
        "L41R2_SCHEMA_CHANGED",
        "L41R2_SCHEMA_MALFORMED",
        "L41R2_SCHEMA_AMBIGUOUS",
        "L41R2_SCHEMA_BASELINE_INVALID",
        "L41R2_SESSION_CLOSE_FAILED",
        "L41R2_DISCOVERY_FAILED",
        "L41R2_ATTEMPT_COUNTS_INVALID",
        "L41R2_EVIDENCE_WRITE_FAILED",
        "L41R2_SCHEMA_METADATA_CAPTURED",
        "L41R2_SCHEMA_METADATA_CAPTURED_UNPINNED",
    }
)


class InteractiveSchemaDiscoveryError(RuntimeError):
    """Fixed diagnostic with no provider text or secret material."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in _REASON_CODES else "L41R2_DISCOVERY_FAILED"
        super().__init__(self.reason)


class _McpSchemaClient(Protocol):
    async def list_tools(self, *, cursor: str | None = None) -> object: ...


@dataclass(frozen=True, slots=True)
class InteractiveSchemaDiscoveryAttemptCounts:
    """Source-owned L41R2 counts; all broker and order calls stay zero."""

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
class InteractiveSchemaDiscoveryResult:
    """Sanitized result; CAPTURED_FOR_REVIEW grants no readiness or authority."""

    status: str
    reason: str
    evidence_path: Path | None
    source: SourceAdmission | None
    attempt_counts: InteractiveSchemaDiscoveryAttemptCounts
    schemas: tuple[InterfaceSchemaFacts, ...]


class _SessionFactory(Protocol):
    def __call__(
        self, oauth: object
    ) -> AbstractAsyncContextManager[_McpSchemaClient]: ...


class _OneShotBrowserOpener:
    """Permit one real browser open and retain no authorization URL."""

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
            raise RuntimeError("L41R2_BROWSER_LAUNCH_ALREADY_USED")
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


def _discard_log(*args: object, **kwargs: object) -> None:
    del args, kwargs


@contextmanager
def _quiet_provider() -> Iterator[None]:
    """Discard upstream prints/logs/warnings and native FD output."""

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


def run_l41r2_interactive_schema_discovery(
    *,
    evidence_dir: Path,
    expected_schema_digests: Mapping[str, str] | None = None,
) -> InteractiveSchemaDiscoveryResult:
    """Run the one-shot additive L41R2 metadata-only observation."""

    return _run_with_dependencies(
        evidence_dir=evidence_dir,
        source_admitter=admit_l41_source,
        oauth_factory_builder=_build_windows_oauth_factory,
        transport_builder=lambda oauth_factory: RobinhoodSchemaDiscoveryTransport(
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
) -> InteractiveSchemaDiscoveryResult:
    """Injected seams are private to fake-only tests."""

    try:
        baseline = _validate_baseline(expected_schema_digests)
    except SchemaDiscoveryError as error:
        return _result_without_file("BLOCKED", _map_reason(error.reason))
    try:
        output_dir = _fresh_evidence_dir(evidence_dir)
    except Exception:
        return _result_without_file("BLOCKED", "L41R2_EVIDENCE_PATH_INVALID")

    empty_counts = InteractiveSchemaDiscoveryAttemptCounts()
    source: SourceAdmission | None = None
    try:
        candidate = source_admitter(repository_root_resolver())
        if type(candidate) is not SourceAdmission or not _source_is_accepted(candidate):
            raise InteractiveSchemaDiscoveryError("L41R2_SOURCE_ADMISSION_BLOCKED")
        source = candidate
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R2_SOURCE_ADMISSION_BLOCKED",
            source,
            empty_counts,
            (),
        )

    browser_opener: _OneShotBrowserOpener | None = None
    try:
        bundle = oauth_factory_builder()
        if type(bundle) is not _OAuthFactoryBundle or not callable(bundle.factory):
            raise TypeError
        browser_opener = bundle.browser_opener
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R2_OAUTH_FACTORY_FAILED",
            source,
            empty_counts,
            (),
        )

    try:
        transport = transport_builder(bundle.factory)
    except Exception:
        return _write_result(
            output_dir,
            "BLOCKED",
            "L41R2_TRANSPORT_CREATE_FAILED",
            source,
            empty_counts,
            (),
        )

    status = "BLOCKED"
    reason = "L41R2_DISCOVERY_FAILED"
    schemas: tuple[InterfaceSchemaFacts, ...] = ()
    try:
        with transport as boundary:
            try:
                with _quiet_provider():
                    discovered = boundary.discover()
                if type(discovered) is not tuple or any(
                    type(item) is not InterfaceSchemaFacts for item in discovered
                ):
                    raise InteractiveSchemaDiscoveryError("L41R2_SCHEMA_MALFORMED")
                schemas = discovered
                status = "CAPTURED_FOR_REVIEW"
                reason = "L41R2_SCHEMA_METADATA_CAPTURED"
            except SchemaDiscoveryError as error:
                reason = _map_reason(error.reason)
                retained = getattr(boundary, "schemas", ())
                if type(retained) is tuple and all(
                    type(item) is InterfaceSchemaFacts for item in retained
                ):
                    schemas = retained
            except InteractiveSchemaDiscoveryError as error:
                reason = error.reason
            except Exception:
                reason = "L41R2_DISCOVERY_FAILED"
    except SchemaDiscoveryError as error:
        reason = _map_reason(error.reason)
    except Exception:
        reason = "L41R2_DISCOVERY_FAILED"

    counts = _read_attempt_counts(transport, browser_opener)
    if counts is None or not _counts_valid(counts, completed=bool(schemas)):
        status = "BLOCKED"
        reason = "L41R2_ATTEMPT_COUNTS_INVALID"
        counts = empty_counts if counts is None else counts
    elif status == "CAPTURED_FOR_REVIEW":
        if not _required_schemas_present(schemas):
            status = "BLOCKED"
            reason = "L41R2_REQUIRED_SCHEMA_MISSING"
        elif baseline is None:
            reason = "L41R2_SCHEMA_METADATA_CAPTURED_UNPINNED"

    return _write_result(output_dir, status, reason, source, counts, schemas)


def _map_reason(reason: str) -> str:
    if reason == "L41R1_SESSION_CLOSE_FAILED":
        return "L41R2_SESSION_CLOSE_FAILED"
    if reason.startswith("L41R1_"):
        mapped = "L41R2_" + reason.removeprefix("L41R1_")
        if mapped in _REASON_CODES:
            return mapped
    return "L41R2_DISCOVERY_FAILED"


def _read_attempt_counts(
    transport: object, browser_opener: _OneShotBrowserOpener | None
) -> InteractiveSchemaDiscoveryAttemptCounts | None:
    try:
        counts = transport.attempt_counts
        launches = 0 if browser_opener is None else browser_opener.launch_count
    except Exception:
        return None
    if type(counts) is not SchemaDiscoveryAttemptCounts or type(launches) is not int:
        return None
    return InteractiveSchemaDiscoveryAttemptCounts(
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
    counts: InteractiveSchemaDiscoveryAttemptCounts, *, completed: bool
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
        raise InteractiveSchemaDiscoveryError("L41R2_SOURCE_ADMISSION_BLOCKED")
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
        raise ValueError("L41R2_EVIDENCE_PATH_INVALID")
    parent = path.parent.resolve(strict=True)
    if path.parent != parent or not parent.is_relative_to(parent_root):
        raise ValueError("L41R2_EVIDENCE_PATH_INVALID")
    current = parent
    while True:
        if current.resolve(strict=True) != current or _has_reparse_point(current):
            raise ValueError("L41R2_EVIDENCE_PATH_INVALID")
        if current == parent_root:
            break
        if current.parent == current or not current.is_relative_to(parent_root):
            raise ValueError("L41R2_EVIDENCE_PATH_INVALID")
        current = current.parent
    path.mkdir()
    return path


def _has_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _result_without_file(status: str, reason: str) -> InteractiveSchemaDiscoveryResult:
    return InteractiveSchemaDiscoveryResult(
        status,
        reason,
        None,
        None,
        InteractiveSchemaDiscoveryAttemptCounts(),
        (),
    )


def _write_result(
    output_dir: Path,
    status: str,
    reason: str,
    source: SourceAdmission | None,
    attempt_counts: InteractiveSchemaDiscoveryAttemptCounts,
    schemas: tuple[InterfaceSchemaFacts, ...],
) -> InteractiveSchemaDiscoveryResult:
    if reason not in _REASON_CODES:
        status = "BLOCKED"
        reason = "L41R2_DISCOVERY_FAILED"
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
        return InteractiveSchemaDiscoveryResult(
            "BLOCKED",
            "L41R2_EVIDENCE_WRITE_FAILED",
            None,
            source,
            attempt_counts,
            schemas,
        )
    return InteractiveSchemaDiscoveryResult(
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
    attempt_counts: InteractiveSchemaDiscoveryAttemptCounts,
    schemas: tuple[InterfaceSchemaFacts, ...],
) -> dict[str, object]:
    return {
        "schema": L41R2_EVIDENCE_SCHEMA,
        "observation": L41R2_OBSERVATION,
        "one_shot": True,
        "status": status,
        "reason": reason,
        "source": _source_payload(source),
        "attempt_counts": {
            name: getattr(attempt_counts, name)
            for name in InteractiveSchemaDiscoveryAttemptCounts.__dataclass_fields__
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
        description="Capture sanitized Robinhood MCP interface metadata (L41R2)."
    )
    parser.add_argument("--evidence-dir", type=Path, required=True)
    arguments = parser.parse_args(argv)
    result = run_l41r2_interactive_schema_discovery(evidence_dir=arguments.evidence_dir)
    print(
        json.dumps(
            {
                "status": result.status,
                "reason": result.reason,
                "evidence_path": (
                    None if result.evidence_path is None else str(result.evidence_path)
                ),
            },
            sort_keys=True,
        )
    )
    return 0 if result.status == "CAPTURED_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
