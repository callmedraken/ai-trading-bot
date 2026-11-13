"""A2 metadata eligibility is distinct from a runtime partition proof."""

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
from trading_bot.robinhood_mcp.agent_initiated_partition_schema_qualifier import (
    AgentInitiatedPartitionSchemaClassification,
    AgentInitiatedPartitionSchemaMatcher,
    AgentInitiatedRuntimePartitionSchemaMatcher,
)
from trading_bot.robinhood_mcp.agent_initiated_partition_schema_qualifier import (
    AgentInitiatedRuntimePartitionSchemaClassification as RuntimeClassification,
)

_HELPER_DESCRIPTION = (
    "true: only agent-initiated orders "
    "(any agent, incl. customer-approved in the app); "
    "false: only orders with no agent involved. Omit for all."
)
_REFERENCE_DESCRIPTION = (
    'true: only orders with an agent_id or placed_agent "agentic"; '
    "false: only those with neither; omit for all"
)
_CAPTURED_DESCRIPTION = (
    "true returns only agent-initiated orders (any agent, not just this one), "
    "whether an agent submitted them directly or the customer approved them in the "
    "Robinhood app; false returns only orders the customer created with no agent "
    "involved. Omit for all orders."
)
_V1_EXHAUSTIVE_DESCRIPTION = (
    "true returns every agent-initiated order from any agent; "
    "false returns every order with no agent involved; "
    "omit the parameter to return all orders."
)


def _input_schema(
    *,
    description: str = _HELPER_DESCRIPTION,
    agent_type: object = ["null", "boolean"],
    agent_required: bool = False,
    agent_default: object = ...,
) -> dict[str, object]:
    agent: dict[str, object] = {"type": agent_type, "description": description}
    if agent_default is not ...:
        agent["default"] = agent_default
    properties: dict[str, object] = {
        "account_number": {"type": "string"},
        "symbol": {"type": "string"},
        "cursor": {"type": "string"},
        "agent_initiated": agent,
    }
    return {
        "type": "object",
        "properties": properties,
        "required": ["account_number", "agent_initiated"]
        if agent_required
        else ["account_number"],
        "additionalProperties": False,
    }


def _output_schema(
    *, agent_type: object = "boolean", agent_required: bool = True
) -> dict[str, object]:
    row_required = ["id", "symbol"]
    if agent_required:
        row_required.append("agent_initiated")
    return {
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
                                "agent_initiated": {"type": agent_type},
                            },
                            "required": row_required,
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["orders"],
            },
            "guide": {"type": "string"},
        },
        "required": ["data", "guide"],
    }


def _tool(
    *,
    description: str = _HELPER_DESCRIPTION,
    input_schema: dict[str, object] | None = None,
    output_schema: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": "get_equity_orders",
        "description": "List equity orders.",
        "inputSchema": _input_schema(description=description)
        if input_schema is None
        else input_schema,
        "outputSchema": _output_schema() if output_schema is None else output_schema,
    }


def _page(
    tools: list[object], *, cursor: object = None, result_type: str = "complete"
) -> dict[str, object]:
    return {"tools": tools, "next_cursor": cursor, "result_type": result_type}


def _match(pages: dict[str | None, object], *, matcher=None):
    calls: list[str | None] = []

    def list_tools(*, cursor: str | None) -> object:
        calls.append(cursor)
        return pages[cursor]

    chosen = matcher or AgentInitiatedRuntimePartitionSchemaMatcher(
        repo_root=Path(__file__).parents[2]
    )
    result = asyncio.run(chosen.match(tools_list=list_tools))
    return result, calls


@pytest.mark.parametrize(
    "description",
    [_HELPER_DESCRIPTION, _CAPTURED_DESCRIPTION],
)
def test_known_public_wording_is_only_runtime_proof_eligible(description: str) -> None:
    result, _ = _match({None: _page([_tool(description=description)])})

    assert result.classification is RuntimeClassification.RUNTIME_PROOF_ELIGIBLE
    assert result.runtime_proof_eligible
    assert result.exhaustive_partition_proven is False
    assert result.authenticated is False
    assert result.contract_version == (
        "AGENT_INITIATED_RUNTIME_PARTITION_PROOF_ELIGIBLE/v1"
    )


def test_v1_exhaustive_contract_keeps_its_original_meaning() -> None:
    a2, _ = _match({None: _page([_tool(description=_HELPER_DESCRIPTION)])})
    v1, _ = _match(
        {None: _page([_tool(description=_HELPER_DESCRIPTION)])},
        matcher=AgentInitiatedPartitionSchemaMatcher(
            repo_root=Path(__file__).parents[2]
        ),
    )
    exhaustive, _ = _match(
        {None: _page([_tool(description=_V1_EXHAUSTIVE_DESCRIPTION)])},
        matcher=AgentInitiatedPartitionSchemaMatcher(
            repo_root=Path(__file__).parents[2]
        ),
    )

    assert a2.runtime_proof_eligible
    assert (
        v1.classification
        is AgentInitiatedPartitionSchemaClassification.UNPROVEN_PROVIDER_SEMANTICS
    )
    assert exhaustive.classification is (
        AgentInitiatedPartitionSchemaClassification.UNAUTHENTICATED_SEMANTIC_MATCH
    )
    assert exhaustive.authenticated is False


@pytest.mark.parametrize(
    "description",
    [
        "true only agent-initiated orders; false only orders with no agent involved",
        (
            "true only this agent's orders; "
            "false only orders with no agent involved; omit for all"
        ),
        (
            "true only agent-initiated orders; "
            "false all agent-initiated orders; omit for all"
        ),
        (
            "true only agent-initiated orders; "
            "false only orders with no agent involved; omit for agent orders"
        ),
        (
            "true only agent-initiated orders; "
            "false only orders with no agent involved; "
            "omit for all; extra clause"
        ),
    ],
)
def test_missing_or_narrowed_field_owned_semantics_are_unproven(
    description: str,
) -> None:
    result, _ = _match({None: _page([_tool(description=description)])})
    assert (
        result.classification
        is RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )


def test_design_reference_filter_wording_does_not_supply_hosted_semantics() -> None:
    result, _ = _match({None: _page([_tool(description=_REFERENCE_DESCRIPTION)])})
    assert (
        result.classification
        is RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )


@pytest.mark.parametrize(
    "schema",
    [
        _input_schema(agent_type="string"),
        _input_schema(agent_type=["boolean", "string"]),
        _input_schema(agent_required=True),
        _input_schema(agent_type="boolean", agent_default=False),
        _input_schema(agent_type="boolean", agent_default=True),
        _input_schema(agent_type="boolean", agent_default=None),
    ],
)
def test_agent_initiated_input_is_optional_noncontradictory_boolean(schema):
    result, _ = _match({None: _page([_tool(input_schema=schema)])})
    assert (
        result.classification
        is RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )


def test_agent_initiated_input_accepts_only_compatible_null_default() -> None:
    schema = _input_schema(agent_default=None)
    result, _ = _match({None: _page([_tool(input_schema=schema)])})
    assert result.runtime_proof_eligible


@pytest.mark.parametrize(
    "schema",
    [
        _output_schema(agent_type="string"),
        _output_schema(agent_type=["boolean", "null"]),
        _output_schema(agent_required=False),
    ],
)
def test_output_rows_require_a_nonnullable_boolean(schema):
    result, _ = _match({None: _page([_tool(output_schema=schema)])})
    assert (
        result.classification
        is RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )


def test_nullable_order_items_remain_runtime_payload_validation() -> None:
    schema = _output_schema()
    item = schema["properties"]["data"]["properties"]["orders"]["items"]  # type: ignore[index]
    item["type"] = ["null", "object"]  # type: ignore[index]
    result, _ = _match({None: _page([_tool(output_schema=schema)])})
    assert result.runtime_proof_eligible


@pytest.mark.parametrize(
    "mutate",
    [
        lambda schema: schema["properties"].pop("agent_initiated"),
        lambda schema: schema["properties"].pop("symbol"),
        lambda schema: schema["properties"]["symbol"].update({"type": "integer"}),
        lambda schema: schema["required"].append("symbol"),
        lambda schema: schema["required"].append("state"),
        lambda schema: schema.update({"allOf": []}),
        lambda schema: schema["properties"]["symbol"].update({"default": "SPY"}),
        lambda schema: schema["properties"]["cursor"].update({"default": "page-2"}),
    ],
)
def test_scope_inputs_and_optional_filters_fail_closed_on_hidden_narrowing(mutate):
    schema = _input_schema()
    mutate(schema)
    result, _ = _match({None: _page([_tool(input_schema=schema)])})
    assert (
        result.classification
        is RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"enum": [True]},
        {"const": True},
        {"if": {"properties": {"symbol": {"const": "SPY"}}}},
    ],
)
def test_field_schema_narrowing_keywords_are_unproven(extra: dict[str, object]):
    schema = _input_schema()
    schema["properties"]["agent_initiated"].update(extra)  # type: ignore[index]
    result, _ = _match({None: _page([_tool(input_schema=schema)])})
    assert (
        result.classification
        is RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )


def test_placed_agent_is_optional_and_cannot_silently_narrow_scope() -> None:
    schema = _input_schema()
    schema["properties"]["placed_agent"] = {"type": "string", "default": "agentic"}  # type: ignore[index]
    result, _ = _match({None: _page([_tool(input_schema=schema)])})
    assert (
        result.classification
        is RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )

    schema = _input_schema()
    schema["properties"]["placed_agent"] = {  # type: ignore[index]
        "type": ["string", "null"],
        "default": None,
    }
    assert _match({None: _page([_tool(input_schema=schema)])})[0].runtime_proof_eligible

    schema["required"] = ["account_number", "placed_agent"]
    assert _match({None: _page([_tool(input_schema=schema)])})[0].classification is (
        RuntimeClassification.UNPROVEN_RUNTIME_PROOF_ELIGIBILITY
    )


def test_injected_metadata_never_authenticates_and_pagination_is_bounded() -> None:
    unrelated = {
        "name": "get_accounts",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }
    result, calls = _match(
        {
            None: _page([unrelated], cursor="page-2"),
            "page-2": _page([_tool()]),
        }
    )
    assert result.runtime_proof_eligible
    assert result.authenticated is False
    assert result.tools_list_pages == 2
    assert calls == [None, "page-2"]

    result, _ = _match(
        {None: _page([_tool()], cursor="repeat"), "repeat": _page([], cursor="repeat")}
    )
    assert result.classification is RuntimeClassification.SCHEMA_MALFORMED
    assert result.pagination_exhaustive is False


@pytest.mark.parametrize(
    "page",
    [
        _page([_tool()], result_type="incomplete"),
        {"tools": [_tool()], "next_cursor": None},
        _page([_tool(), _tool()]),
    ],
)
def test_malformed_aliases_duplicate_tools_and_incomplete_lists_fail_closed(page):
    result, _ = _match({None: page})
    assert result.classification is RuntimeClassification.SCHEMA_MALFORMED


def test_duplicate_schema_aliases_are_malformed() -> None:
    tool = _tool()
    tool["input_schema"] = tool["inputSchema"]
    result, _ = _match({None: _page([tool])})
    assert result.classification is RuntimeClassification.SCHEMA_MALFORMED


def test_invalid_unicode_tool_description_is_malformed_not_an_exception() -> None:
    tool = _tool()
    tool["description"] = "bad \ud800 description"
    result, _ = _match({None: _page([tool])})
    assert result.classification is RuntimeClassification.SCHEMA_MALFORMED


def test_source_identity_failure_precedes_metadata_seam(tmp_path: Path) -> None:
    calls: list[str | None] = []

    def forbidden(*, cursor: str | None) -> object:
        calls.append(cursor)
        raise AssertionError("metadata seam must not run")

    result = asyncio.run(
        AgentInitiatedRuntimePartitionSchemaMatcher(repo_root=tmp_path).match(
            tools_list=forbidden
        )
    )
    assert result.classification is RuntimeClassification.SOURCE_AUTHORITY_FAILED
    assert calls == []


def _matching_schema():
    return _match({None: _page([_tool()])})[0]


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
    match = _matching_schema()
    state = SimpleNamespace(
        match=match,
        admission=_admission(match),
        events=[],
        observer=observer.RobinhoodAgentInitiatedRuntimePartitionSchemaObserver(),
    )

    def admit(*, repo_root: Path):
        state.events.append("admission")
        return state.admission

    def module_origins(*, repo_root: Path) -> bool:
        state.events.append("module-origins")
        return True

    async def run(attempts, repo_root):
        state.events.append("metadata-session")
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
    monkeypatch.setattr(observer, "_run_runtime_production_session", run)
    monkeypatch.setattr(observer, "_reserve_runtime_evidence_directory", reserve)
    monkeypatch.setattr(observer, "_write_evidence", write)
    monkeypatch.setattr(observer, "_suppress_external_output", nullcontext)
    return state


def _observe(harness, tmp_path: Path, name: str):
    return asyncio.run(harness.observer.observe(evidence_dir=tmp_path / name))


def _evidence(result: observer.AgentInitiatedPartitionObservationResult):
    assert result.evidence_file is not None
    return json.loads(result.evidence_file.read_text(encoding="ascii"))


def test_a2_observer_is_inert_and_has_no_tool_call_surface() -> None:
    instance = observer.RobinhoodAgentInitiatedRuntimePartitionSchemaObserver()
    assert instance._used is False
    assert list(inspect.signature(instance.observe).parameters) == ["evidence_dir"]
    assert not hasattr(observer._MetadataOnlyTransport, "call_tool")


def test_a2_source_admission_blocks_before_oauth_or_metadata_session(
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


def test_a2_authenticated_metadata_is_review_only_and_not_partition_proof(
    harness, tmp_path: Path
) -> None:
    result = _observe(harness, tmp_path, "review-only")
    evidence = _evidence(result)

    assert result.status is observer._RUNTIME_REVIEW_MATCH
    assert harness.events == ["admission", "module-origins", "metadata-session"]
    assert (
        evidence["classification"]
        == "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW"
    )
    assert evidence["classifier_output_authenticated"] is False
    assert evidence["metadata_source_authenticated"] is True
    assert evidence["runtime_proof_eligibility"] == "ELIGIBLE"
    assert evidence["partition_equality_proof"] == "NOT_PROVEN"
    assert evidence["production_order_scope_authority"] == "NOT_GRANTED"
    assert (
        evidence["contract_version"]
        == "AGENT_INITIATED_RUNTIME_PARTITION_PROOF_ELIGIBLE/v1"
    )
    assert evidence["attempt_counters"]["mcp_tool_invocation_attempts"] == 0
    assert evidence["attempt_counters"]["account_reads"] == 0
    assert evidence["attempt_counters"]["order_reads"] == 0
    assert harness.match.authenticated is False
    assert harness.match.exhaustive_partition_proven is False


def test_a2_observer_is_one_use_and_does_not_retry(harness, tmp_path: Path) -> None:
    first = _observe(harness, tmp_path, "first")
    second = _observe(harness, tmp_path, "second")

    assert first.status is observer._RUNTIME_REVIEW_MATCH
    assert (
        second.status
        is observer.AgentInitiatedPartitionObservationStatus.SOURCE_AUTHORITY_BLOCKED
    )
    assert second.reason == "OBSERVER_ATTEMPT_ALREADY_USED"
    assert harness.events == ["admission", "module-origins", "metadata-session"]


def test_a2_evidence_namespace_is_distinct_from_v1_and_consumed_placed_agent():
    assert observer._RUNTIME_EVIDENCE_NAME.fullmatch(
        "arch147-agent-initiated-runtime-proof-eligible-" + "a" * 32
    )
    assert not observer._RUNTIME_EVIDENCE_NAME.fullmatch(
        "arch147-agent-initiated-partition-" + "a" * 32
    )
    assert not observer._RUNTIME_EVIDENCE_NAME.fullmatch(
        "arch147-order-scope-schema-" + "a" * 32
    )


def test_a2_observer_source_has_no_provider_tool_dispatch() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")
    assert ".call_tool(" not in source
    assert "get_equity_orders" not in source
    assert "get_equity_positions" not in source
