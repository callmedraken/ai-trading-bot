from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.robinhood_mcp import (
    agent_initiated_partition_schema_observer as observer,
)
from trading_bot.robinhood_mcp.agent_initiated_partition_schema_observer import (
    AgentInitiatedPartitionObservationStatus as ObservationStatus,
)
from trading_bot.robinhood_mcp.agent_initiated_partition_schema_qualifier import (
    AgentInitiatedPartitionSchemaMatcher,
)

_REVIEW_MATCH = ObservationStatus.AUTHENTICATED_SCHEMA_MATCH_FOR_REVIEW

_CONTRACT = (
    "true returns every agent-initiated order from any agent; "
    "false returns every order with no agent involved; "
    "omit the parameter to return all orders."
)


def _tool() -> dict[str, object]:
    return {
        "name": "get_equity_orders",
        "description": "List equity orders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_number": {"type": "string"},
                "symbol": {"type": "string"},
                "agent_initiated": {
                    "type": ["null", "boolean"],
                    "description": _CONTRACT,
                },
            },
            "required": ["account_number"],
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "properties": {
                        "orders": {
                            "type": ["null", "array"],
                            "items": {
                                "type": ["null", "object"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "symbol": {"type": "string"},
                                    "agent_initiated": {"type": "boolean"},
                                },
                                "required": ["id", "symbol", "agent_initiated"],
                            },
                        }
                    },
                    "required": ["orders"],
                },
                "guide": {"type": "string"},
            },
            "required": ["data", "guide"],
        },
    }


async def _matching_schema():
    pages = {None: {"tools": [_tool()], "next_cursor": None, "result_type": "complete"}}
    matcher = AgentInitiatedPartitionSchemaMatcher(repo_root=Path(__file__).parents[2])

    async def list_tools(*, cursor: str | None) -> object:
        return pages[cursor]

    return await matcher.match(tools_list=list_tools)


def _admission(match, **changes: object) -> observer._SourceAdmission:
    return replace(
        observer._SourceAdmission(
            root=str(observer._CANONICAL_WORKTREE),
            branch="feature/robinhood-live-prototype-current",
            source_head=match.source_head,
            source_tree=match.source_tree,
            origin="https://github.com/callmedraken/ai-trading-bot.git",
            remote_feature_head=match.source_head,
            remote_develop_head=match.source_head,
            feature_authority="PASS",
            prospective_develop_authority="PASS",
            reason=None,
        ),
        **changes,
    )


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch):
    match = asyncio.run(_matching_schema())
    state = SimpleNamespace(
        match=match,
        admission=_admission(match),
        events=[],
        observer=observer.RobinhoodAgentInitiatedPartitionSchemaObserver(),
    )

    def admit(*, repo_root: Path):
        state.events.append("admission")
        return state.admission

    def module_origins(*, repo_root: Path) -> bool:
        state.events.append("module-origins")
        return True

    async def run(attempts, repo_root):
        state.events.append("provider-session")
        attempts.oauth_scope_entry_attempts += 1
        attempts.mcp_session_open_attempts += 1
        attempts.tools_list_attempts += 1
        attempts.tools_list_pages_received += 1
        return state.match, False

    def reserve(path: Path) -> Path:
        path.mkdir()
        return path

    def write(path: Path, material: dict[str, object]):
        raw = (
            json.dumps(material, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        evidence_file = path / "evidence.json"
        evidence_file.write_bytes(raw)
        return evidence_file, hashlib.sha256(raw).hexdigest()

    monkeypatch.setattr(observer, "_admit_current_source", admit)
    monkeypatch.setattr(observer, "_module_origins_are_source_owned", module_origins)
    monkeypatch.setattr(observer, "_run_production_session", run)
    monkeypatch.setattr(observer, "_reserve_evidence_directory", reserve)
    monkeypatch.setattr(observer, "_write_evidence", write)
    monkeypatch.setattr(observer, "_suppress_external_output", nullcontext)
    return state


def _observe(harness, tmp_path: Path, name: str):
    return asyncio.run(harness.observer.observe(evidence_dir=tmp_path / name))


def _evidence(result: observer.AgentInitiatedPartitionObservationResult):
    assert result.evidence_file is not None
    return json.loads(result.evidence_file.read_text(encoding="ascii"))


def test_construction_is_inert_and_observe_has_no_injected_provider_seam() -> None:
    instance = observer.RobinhoodAgentInitiatedPartitionSchemaObserver()
    assert instance._used is False
    assert list(inspect.signature(instance.observe).parameters) == ["evidence_dir"]
    assert not hasattr(observer._MetadataOnlyTransport, "call_tool")


def test_source_admission_precedes_module_check_and_provider_construction(
    harness, tmp_path: Path
) -> None:
    harness.admission = replace(harness.admission, reason="SOURCE_AUTHORITY_BLOCKED")

    result = _observe(harness, tmp_path, "source-blocked")

    assert (
        result.status
        is observer.AgentInitiatedPartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED
    )
    assert harness.events == ["admission"]
    evidence = _evidence(result)
    assert evidence["metadata_source_authenticated"] is False
    assert evidence["attempt_counters"]["oauth_scope_entry_attempts"] == 0
    assert evidence["attempt_counters"]["mcp_session_open_attempts"] == 0
    assert evidence["attempt_counters"]["tools_list_attempts"] == 0


def test_module_origin_failure_blocks_before_provider_construction(
    harness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events = harness.events

    def wrong_origin(*, repo_root: Path) -> bool:
        events.append("module-origins")
        return False

    monkeypatch.setattr(observer, "_module_origins_are_source_owned", wrong_origin)
    result = _observe(harness, tmp_path, "wrong-module-origin")

    assert (
        result.status
        is observer.AgentInitiatedPartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED
    )
    assert events == ["admission", "module-origins"]
    assert _evidence(result)["attempt_counters"]["mcp_session_open_attempts"] == 0


def test_authenticated_metadata_match_is_review_only_and_separate_from_parser(
    harness, tmp_path: Path
) -> None:
    result = _observe(harness, tmp_path, "review-only")
    evidence = _evidence(result)
    assert result.status is _REVIEW_MATCH
    assert harness.events == ["admission", "module-origins", "provider-session"]
    assert evidence["classification"] == "AUTHENTICATED_METADATA_MATCH_FOR_REVIEW"
    assert evidence["classifier_output_authenticated"] is False
    assert evidence["metadata_source_authenticated"] is True
    assert evidence["production_order_scope_authority"] == "NOT_GRANTED"
    assert evidence["contract_version"] == "EXHAUSTIVE_AGENT_INITIATED_PARTITION/v1"
    assert evidence["metadata_validation_boundary"].endswith(
        "RAW_JSON_DUPLICATE_KEYS_UNOBSERVABLE"
    )
    assert evidence["attempt_counters"]["mcp_tool_invocation_attempts"] == 0
    assert evidence["attempt_counters"]["account_reads"] == 0
    assert evidence["attempt_counters"]["order_reads"] == 0
    assert harness.match.authenticated is False
    assert harness.match.semantic_match


def test_observer_is_one_use_and_does_not_retry_a_metadata_attempt(
    harness, tmp_path: Path
) -> None:
    first = _observe(harness, tmp_path, "first")
    second = _observe(harness, tmp_path, "second")
    assert first.status is _REVIEW_MATCH
    assert (
        second.status
        is observer.AgentInitiatedPartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED
    )
    assert second.reason == "OBSERVER_ATTEMPT_ALREADY_USED"
    assert harness.events == ["admission", "module-origins", "provider-session"]


def test_local_source_change_after_session_discards_match(
    harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = {
        ("rev-parse", "--show-toplevel"): str(observer._CANONICAL_WORKTREE),
        ("branch", "--show-current"): "feature/robinhood-live-prototype-current",
        ("rev-parse", "--verify", "HEAD"): harness.match.source_head,
        ("rev-parse", "--verify", "HEAD^{tree}"): harness.match.source_tree,
        ("status", "--porcelain=v1", "--untracked-files=all"): " M source.py",
    }
    monkeypatch.setattr(observer, "_git_text", lambda _root, *args: expected[args])

    assert not observer._local_source_still_clean(Path("F:/repo"), harness.match)


def test_metadata_observer_source_contains_no_provider_dispatch_surface() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")
    assert ".call_tool(" not in source
    assert "get_equity_positions" not in source
    assert "get_equity_orders" not in source


def test_distinct_evidence_namespace_is_not_the_consumed_schema_namespace() -> None:
    assert observer._EVIDENCE_NAME.fullmatch(
        "arch147-agent-initiated-partition-" + "a" * 32
    )
    assert not observer._EVIDENCE_NAME.fullmatch(
        "arch147-order-scope-schema-" + "a" * 32
    )
