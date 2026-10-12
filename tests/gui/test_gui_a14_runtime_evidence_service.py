"""Bounded explicit JSON only: sanitized failures, one open, no capabilities."""

import ast
import inspect
import json
from io import BytesIO
from pathlib import Path

import pytest

from trading_bot.gui import (
    MAX_RUNTIME_EVIDENCE_BYTES,
    ProductionRuntimeEvidenceInspectionService,
    RuntimeDiagnostic,
    RuntimePageStatus,
)
from trading_bot.gui import runtime_evidence_service as module

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"
NAMES = {
    "acl": "acl-provisioned.json",
    "qualification": "qualification-ready.json",
    "session": "session-waiting.json",
}


def _selected(tmp_path, role, changes):
    value = json.loads((FIXTURES / NAMES[role]).read_text())
    value.update(changes)
    path = tmp_path / "selected.json"
    path.write_text(json.dumps(value))
    return ProductionRuntimeEvidenceInspectionService(
        **{role: path}
    ).get_runtime_state()


@pytest.mark.parametrize("role", NAMES)
def test_single_artifact_is_useful(role):
    state = ProductionRuntimeEvidenceInspectionService(
        **{role: FIXTURES / NAMES[role]}
    ).get_runtime_state()
    assert state.status is RuntimePageStatus.AVAILABLE


@pytest.mark.parametrize(
    "role,changes",
    [
        ("acl", {"runtime_sid_digest": "A" * 64}),
        ("acl", {"runtime_sid_digest": "a" * 63}),
        ("acl", {"acl_apply_attempts": True}),
        ("acl", {"status": "UNKNOWN"}),
        ("acl", {"result": "READY"}),
        ("qualification", {"source_head": "z" * 40}),
        ("qualification", {"source_tree": "c" * 39}),
        ("qualification", {"effect_counts_complete": 1}),
        ("qualification", {"persisted_oauth_available": 1}),
        ("qualification", {"paper_records": 1_000_001}),
        ("qualification", {"runtime_status": "UNKNOWN"}),
        ("session", {"contract_id": "not-a-uuid"}),
        ("session", {"operation_id": "11111111"}),
        ("session", {"order_id": "secret"}),
        ("session", {"target_session": "2026-02-30"}),
        ("session", {"wait_started_at": "2026-10-12T12:00:00"}),
        ("session", {"admitted_at": "2026-10-12"}),
        ("session", {"historical_sessions": ["2026-02-30"]}),
        ("session", {"historical_sessions": ["2026-10-09"] * 254}),
        ("session", {"snapshot_sha256": ["bad"]}),
        ("session", {"history_seed_sha256": "A" * 64}),
        ("session", {"broker_placement_count": 1}),
        ("session", {"strategy_outcome": "<script>"}),
        ("session", {"prepare_result": "RETRY"}),
        ("session", {"execute_result": "FAIL"}),
        ("session", {"status": "UNKNOWN"}),
    ],
)
def test_invalid_typed_fields_fail_closed(tmp_path, role, changes):
    state = _selected(tmp_path, role, changes)
    assert state.status is RuntimePageStatus.ATTENTION
    assert state.diagnostic is RuntimeDiagnostic.INVALID
    assert getattr(state, role) is None


@pytest.mark.parametrize("role", NAMES)
@pytest.mark.parametrize(
    "field",
    [
        "credential",
        "oauth_token",
        "provider_response",
        "exception",
        "path",
        "raw_sid",
        "username",
        "display_name",
        "acl",
    ],
)
def test_sensitive_unknown_fields_rejected_not_retained(tmp_path, role, field):
    state = _selected(tmp_path, role, {field: "PRIVATE-MATERIAL"})
    assert state.diagnostic is RuntimeDiagnostic.INVALID
    assert "PRIVATE-MATERIAL" not in repr(state)
    assert str(tmp_path) not in repr(state)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema":"x","schema":"y"}',
        b'{"nested":{"a":1,"a":2}}',
        b"[]",
        b"null",
        b"{",
        b"\xff",
        b'{"status":NaN}',
        b"[" * 2000 + b"]" * 2000,
        b" " * (MAX_RUNTIME_EVIDENCE_BYTES + 1),
    ],
    ids=[
        "duplicate",
        "nested-duplicate",
        "array",
        "null",
        "truncated",
        "encoding",
        "nan",
        "deep",
        "oversized",
    ],
)
def test_malformed_oversized_duplicate_deep_json_sanitized(tmp_path, payload):
    path = tmp_path / "input.json"
    path.write_bytes(payload)
    assert (
        ProductionRuntimeEvidenceInspectionService(acl=path)
        .get_runtime_state()
        .diagnostic
        is RuntimeDiagnostic.INVALID
    )


@pytest.mark.parametrize("role", NAMES)
def test_schema_mismatch_and_missing_field(tmp_path, role):
    assert (
        _selected(tmp_path, role, {"schema": "wrong/v1"}).diagnostic
        is RuntimeDiagnostic.INVALID
    )
    value = json.loads((FIXTURES / NAMES[role]).read_text())
    del value["status"]
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(value))
    assert (
        ProductionRuntimeEvidenceInspectionService(**{role: path})
        .get_runtime_state()
        .diagnostic
        is RuntimeDiagnostic.INVALID
    )


def test_each_selected_file_opened_once_with_cached_reuse(monkeypatch):
    paths = {role: FIXTURES / name for role, name in NAMES.items()}
    original = Path.open
    calls = []

    def recording(path, mode="r", *args, **kwargs):
        assert mode == "rb"
        calls.append(path)
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording)
    service = ProductionRuntimeEvidenceInspectionService(**paths)
    first = service.get_runtime_state()
    assert service.get_runtime_state() is first
    assert calls == list(paths.values())


def test_no_selection_zero_io_and_no_discovery(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Forbidden discovery or I/O")

    for name in ("open", "glob", "rglob", "iterdir"):
        monkeypatch.setattr(Path, name, forbidden)
    assert (
        ProductionRuntimeEvidenceInspectionService().get_runtime_state().status
        is RuntimePageStatus.UNAVAILABLE
    )


def test_failure_sanitized_and_not_retried(monkeypatch):
    calls = []

    def fail(path, *args, **kwargs):
        calls.append(path)
        raise OSError("SECRET-TOKEN F:\\private\\evidence.json")

    monkeypatch.setattr(Path, "open", fail)
    service = ProductionRuntimeEvidenceInspectionService(acl=Path("selected.json"))
    state = service.get_runtime_state()
    assert service.get_runtime_state() is state
    assert len(calls) == 1
    assert "SECRET" not in repr(state) and "private" not in repr(state)


def test_directory_rejected_and_duplicate_roles_not_reopened(tmp_path, monkeypatch):
    assert (
        ProductionRuntimeEvidenceInspectionService(acl=tmp_path)
        .get_runtime_state()
        .diagnostic
        is RuntimeDiagnostic.INVALID
    )
    calls = []
    original = Path.open

    def recording(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording)
    path = FIXTURES / NAMES["acl"]
    state = ProductionRuntimeEvidenceInspectionService(
        acl=path, qualification=path
    ).get_runtime_state()
    assert state.status is RuntimePageStatus.ATTENTION
    assert calls == [path]


@pytest.mark.parametrize("field", ["source_head", "source_tree"])
def test_source_conflict_blocks_without_reconciliation(tmp_path, field):
    value = json.loads((FIXTURES / NAMES["session"]).read_text())
    value[field] = "d" * 40
    path = tmp_path / "conflicting.json"
    path.write_text(json.dumps(value))
    state = ProductionRuntimeEvidenceInspectionService(
        qualification=FIXTURES / NAMES["qualification"], session=path
    ).get_runtime_state()
    assert state.diagnostic is RuntimeDiagnostic.CONFLICTING
    assert state.status is RuntimePageStatus.ATTENTION


@pytest.mark.parametrize(
    "role,changes",
    [
        ("acl", {"status": "NEEDS_PROVISIONING"}),
        ("acl", {"provider_calls": 1}),
        ("qualification", {"paper_store_write_readiness": "BLOCKED"}),
        ("qualification", {"alpaca_credential_reads": None}),
        ("qualification", {"effect_counts_complete": False}),
        ("session", {"status": "BLOCKED"}),
        ("session", {"status": "EXECUTE_STARTED"}),
        ("session", {"paper_mutations": None, "effect_counts_complete": False}),
    ],
)
def test_blocking_and_unknown_effects_visible(tmp_path, role, changes):
    state = _selected(tmp_path, role, changes)
    assert state.diagnostic is RuntimeDiagnostic.BLOCKED
    assert getattr(state, role) is not None


def test_service_has_no_effect_capability():
    tree = ast.parse(inspect.getsource(module))
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    imports += [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert set(imports) <= {
        "__future__",
        "json",
        "re",
        "dataclasses",
        "datetime",
        "pathlib",
        "uuid",
        "trading_bot.gui.runtime_models",
    }
    forbidden = {
        "glob",
        "rglob",
        "walk",
        "iterdir",
        "write_text",
        "write_bytes",
        "chmod",
        "connect",
        "run",
        "Popen",
        "getenv",
    }
    assert (
        not {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        & forbidden
    )


def test_reader_requests_only_bound_plus_one_rejection_byte(monkeypatch):
    reads = []

    class BoundedStream(BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    def selected_open(path, mode="r"):
        assert path == Path("selected.json") and mode == "rb"
        return BoundedStream(b" " * (MAX_RUNTIME_EVIDENCE_BYTES + 2))

    monkeypatch.setattr(Path, "open", selected_open)
    state = ProductionRuntimeEvidenceInspectionService(
        acl=Path("selected.json")
    ).get_runtime_state()
    assert state.diagnostic is RuntimeDiagnostic.INVALID
    assert reads == [MAX_RUNTIME_EVIDENCE_BYTES + 1]
