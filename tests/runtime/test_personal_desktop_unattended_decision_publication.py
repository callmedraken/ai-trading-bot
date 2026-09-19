"""Focused Architecture-113 D6 ordering, authority, and failure matrix."""

from __future__ import annotations

import ast
import ctypes
import gc
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.runtime import personal_desktop_paper_runtime_output as output
from trading_bot.runtime import personal_desktop_unattended_daily_cycle as daily
from trading_bot.runtime import personal_desktop_unattended_decision_publication as d6
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_intent as intent_module,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_publication as pub,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    require_selected_c3_strategy_history_binding,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    xnys_regular_open,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageClassification as Storage,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageDiagnostic as Diagnostic,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageReadResult as StorageResult,
)

from ._selected_c3_history_lifetime import (
    install_weak_selected_c3_history_reader,
)
from .test_personal_desktop_unattended_paper_decision_intent import (
    _decision_binding,
    _session_read,
)
from .test_personal_desktop_unattended_paper_decision_output import DecisionNative

Status = d6.PersonalDesktopUnattendedDecisionPublicationClassification
PublicationStatus = pub.PersonalDesktopUnattendedDecisionPublicationStatus
PublicationDiagnostic = pub.PersonalDesktopUnattendedDecisionPublicationDiagnostic
_OPEN_DISPOSABLE_WRITER = (
    output._open_personal_desktop_unattended_decision_output_capability_for_test
)
_NOW = datetime(2026, 8, 25, 8, tzinfo=UTC)
_DRIFT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


@pytest.fixture(autouse=True)
def forbid_native_and_unrelated_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("D6 source tests reached a production or unrelated effect")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    from trading_bot.runtime import (
        personal_desktop_unattended_market_data_capture as g5,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_operation_execution as execution,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_storage_provisioning as provisioning,
    )

    for module, name in (
        (daily, "run_personal_desktop_unattended_daily_cycle"),
        (daily, "reconcile_personal_desktop_unattended_market_data_capture"),
        (g5, "run_personal_desktop_unattended_market_data_capture"),
        (g5, "reconcile_personal_desktop_unattended_market_data_capture"),
        (execution, "execute_personal_desktop_unattended_paper_operation"),
        (provisioning, "provision_personal_desktop_unattended_storage"),
    ):
        monkeypatch.setattr(module, name, forbidden)


def _storage(binding, classification):
    diagnostics = {
        Storage.ABSENT: Diagnostic.VERIFIED_ABSENT,
        Storage.FINALIZED_IDENTICAL: Diagnostic.VERIFIED_FINALIZED_IDENTICAL,
        Storage.STAGING_PRESENT: Diagnostic.STAGING_PRESENT,
        Storage.CONFLICTING: Diagnostic.VERIFIED_CONFLICT,
        Storage.BLOCKED: Diagnostic.VERIFICATION_BLOCKED,
    }
    identical = classification is Storage.FINALIZED_IDENTICAL
    return StorageResult(
        classification,
        binding.decision.decision_id,
        int(identical),
        binding.decision.decision_id if identical else None,
        diagnostics[classification],
    )


class Harness:
    def __init__(self, monkeypatch):
        self.binding = _decision_binding(monkeypatch)
        self.current = _session_read(date(2026, 8, 24), 105)
        self.events = []
        self.gates = [False] * 8
        self.held = False
        self.authority = object()
        self.history = object()
        self.account = SimpleNamespace(
            anchor=SimpleNamespace(
                paper_account_id=self.binding.decision.paper_account_id
            ),
            prior_checkpoint=self.binding.decision.prepared_decision.prior_checkpoint,
        )
        self.storage_state = Storage.ABSENT
        self.final_storage_state = Storage.FINALIZED_IDENTICAL
        self.account_reads = 0
        self.storage_reads = []
        self.failure = None
        self.writer = None
        self.times = None
        self.observed = _NOW
        self.drift_at = None

    def now(self):
        return next(self.times) if self.times is not None else self.observed

    def validate(self, authority):
        assert authority is self.authority
        assert self.gates == [False] * 8
        self.events.append("c1")
        return authority

    def read_account(self, authority, historical):
        assert authority is self.authority
        assert historical == (b"retained-configuration",)
        self.account_reads += 1
        assert self.held is (self.account_reads != 1)
        self.events.append(f"account:{self.account_reads}")
        if self.drift_at == self.account_reads:
            return SimpleNamespace(
                anchor=self.account.anchor,
                prior_checkpoint=SimpleNamespace(checkpoint_id=_DRIFT),
            )
        return self.account

    @contextmanager
    def admission(self, prelock):
        assert prelock is self.account
        assert self.account_reads == 1
        self.events.append("lock")
        self.held = True
        try:
            yield
        finally:
            self.events.append("release")
            self.held = False

    def read_selected(self, authority, session):
        assert self.held and authority is self.authority
        assert session == self.current.session
        self.events.append("selected")
        return self.current

    def build_history(self, authority, selected, config):
        assert self.held and authority is self.authority
        assert selected is self.current
        assert config == daily.personal_desktop_unattended_strategy_config()
        self.events.append("history")
        return self.history

    def build_decision(
        self, authority, selected, history, account, planning, config, policies
    ):
        assert self.held and authority is self.authority
        assert selected is self.current and history is self.history
        assert account is self.account
        assert planning == self.current.selected.verification.snapshot.audit.captured_at
        assert config == daily.personal_desktop_unattended_strategy_config()
        assert policies == daily.personal_desktop_unattended_paper_policies()
        self.events.append("decision")
        return self.binding

    def read_storage(self, authority, expected):
        assert self.held and authority is self.authority
        assert expected is self.binding
        assert self.gates == [False] * 8
        self.events.append("storage")
        state = (
            self.storage_state if not self.storage_reads else self.final_storage_state
        )
        result = _storage(expected, state)
        self.storage_reads.append(result)
        return result

    def require_storage(self, authority, expected, storage):
        assert authority is self.authority and expected is self.binding
        assert storage in self.storage_reads
        self.events.append("storage-proof")

    def qualify(self, authority, expected, observed):
        assert self.held and authority is self.authority and expected is self.binding
        assert self.gates == [False] * 8
        self.events.append("qualify")
        missed = observed >= xnys_regular_open(
            expected.decision.intended_execution_session
        )
        return pub.PersonalDesktopUnattendedDecisionPublicationQualificationResult(
            PublicationStatus.MISSED_DECISION_DEADLINE
            if missed
            else PublicationStatus.DECISION_READY_EFFECTS_DISABLED,
            PublicationDiagnostic.DEADLINE_REACHED
            if missed
            else PublicationDiagnostic.PUBLICATION_EFFECT_DISABLED,
            expected.decision.decision_id,
            Storage.ABSENT,
        )

    def permit(self, expected, storage, authority, session, observed):
        assert self.held and authority is self.authority
        assert self.gates == [False] * 8
        assert storage is self.storage_reads[0]
        self.events.append("permit")
        return pub.issue_disposable_pre_open_decision_publication_permit_for_test(
            expected, storage, session, observed
        )

    def set_gate(self, value):
        assert self.held
        self.events.append(f"gate:{value}")
        self.gates[1] = value

    def open_writer(self, storage, permit):
        assert self.held
        assert self.gates == [False, True, False, False, False, False, False, False]
        self.events.append("writer")
        if self.failure == "factory":
            raise RuntimeError("private factory failure")
        harness = self

        class Writer:
            real_effect_performed = False

            def __enter__(self):
                harness.events.append("enter")
                if harness.failure == "enter":
                    raise RuntimeError("private entry failure")
                return self

            def __exit__(self, *args):
                harness.events.append("exit")

            def publish(self, observed):
                assert harness.held
                assert harness.gates == [
                    False,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                    False,
                ]
                harness.events.append("publish")
                pub.consume_disposable_pre_open_decision_publication_permit_for_test(
                    permit, harness.binding, storage, observed
                )
                self.real_effect_performed = True
                if harness.failure == "publish":
                    raise RuntimeError("private write failure")
                return object()  # Deliberately carries no accepted publication proof.

        self.writer = Writer()
        return self.writer

    def dependencies(self):
        return d6.DisposableUnattendedDecisionPublicationDependencies(
            lambda: tuple(self.gates),
            self.set_gate,
            lambda: self.authority,
            self.validate,
            self.now,
            lambda c1: (b"retained-configuration",),
            self.read_account,
            lambda value: value,
            self.admission,
            self.read_selected,
            self.build_history,
            self.build_decision,
            self.read_storage,
            self.require_storage,
            self.qualify,
            self.permit,
            self.open_writer,
        )

    def run(self):
        result = d6.run_personal_desktop_unattended_decision_publication_for_test(
            self.dependencies()
        )
        assert not self.held
        return result


def test_fresh_absent_one_shot_and_mutex_order(monkeypatch):
    h = Harness(monkeypatch)
    result = h.run()
    assert result.classification is Status.DECISION_PUBLISHED
    assert result.real_effect_performed is True
    assert h.events == [
        "c1",
        "account:1",
        "lock",
        "c1",
        "account:2",
        "selected",
        "history",
        "decision",
        "storage",
        "storage-proof",
        "qualify",
        "permit",
        "gate:True",
        "writer",
        "enter",
        "publish",
        "exit",
        "gate:False",
        "storage",
        "account:3",
        "c1",
        "storage-proof",
        "release",
    ]
    assert h.storage_reads[0] is not h.storage_reads[1]
    assert h.gates == [False] * 8


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("value", [True, 0, 1, None, "False"])
def test_each_initial_open_or_nonbool_gate_blocks(monkeypatch, index, value):
    h = Harness(monkeypatch)
    h.gates[index] = value
    result = h.run()
    assert result.classification is Status.BLOCKED
    assert result.real_effect_performed is False
    assert h.events == []


@pytest.mark.parametrize(
    "offset", [timedelta(seconds=-1), timedelta(0), timedelta(seconds=1)]
)
def test_finalized_identical_zero_write_even_after_deadline(monkeypatch, offset):
    h = Harness(monkeypatch)
    h.storage_state = Storage.FINALIZED_IDENTICAL
    h.observed = (
        xnys_regular_open(h.binding.decision.intended_execution_session) + offset
    )
    result = h.run()
    assert result.classification is Status.DECISION_ALREADY_FINALIZED
    assert result.real_effect_performed is False
    assert h.account_reads == 3 and len(h.storage_reads) == 2
    assert not set(h.events) & {"qualify", "permit", "writer", "publish", "gate:True"}
    assert h.gates == [False] * 8


@pytest.mark.parametrize(
    "state", [Storage.STAGING_PRESENT, Storage.CONFLICTING, Storage.BLOCKED]
)
def test_unsafe_storage_blocks_before_permit(monkeypatch, state):
    h = Harness(monkeypatch)
    h.storage_state = state
    assert h.run().classification is Status.BLOCKED
    assert "permit" not in h.events and "gate:True" not in h.events


@pytest.mark.parametrize(
    "malformed", [None, object(), SimpleNamespace(classification="ABSENT")]
)
def test_unknown_or_malformed_storage_blocks(monkeypatch, malformed):
    h = Harness(monkeypatch)
    h.read_storage = lambda *args: malformed
    assert h.run().classification is Status.BLOCKED
    assert "permit" not in h.events


@pytest.mark.parametrize(
    "offset", [timedelta(microseconds=-1), timedelta(0), timedelta(microseconds=1)]
)
def test_strict_deadline_before_permit(monkeypatch, offset):
    h = Harness(monkeypatch)
    h.observed = (
        xnys_regular_open(h.binding.decision.intended_execution_session) + offset
    )
    missed = offset >= timedelta(0)
    if missed:
        h.final_storage_state = Storage.ABSENT
    assert h.run().classification is (
        Status.MISSED_DECISION_DEADLINE if missed else Status.DECISION_PUBLISHED
    )
    assert h.events.count("permit") == h.events.count("writer") == (not missed)
    assert h.gates == [False] * 8


@pytest.mark.parametrize("crossing", ["permit", "publish"])
def test_deadline_crossing_stops_without_publish(monkeypatch, crossing):
    h = Harness(monkeypatch)
    deadline = xnys_regular_open(h.binding.decision.intended_execution_session)
    h.times = iter(
        [_NOW, _NOW, deadline] if crossing == "permit" else [_NOW, _NOW, _NOW, deadline]
    )
    h.final_storage_state = Storage.ABSENT
    result = h.run()
    assert result.classification is Status.MISSED_DECISION_DEADLINE
    assert result.real_effect_performed is False
    assert "publish" not in h.events
    assert h.gates == [False] * 8
    assert h.events.count("permit") == (crossing == "publish")


@pytest.mark.parametrize("failure", ["factory", "enter", "publish"])
def test_exception_closes_gate_rereads_and_never_retries(monkeypatch, failure):
    h = Harness(monkeypatch)
    h.failure = failure
    result = h.run()
    assert result.classification is Status.PUBLICATION_OUTCOME_AMBIGUOUS
    assert result.real_effect_performed is (failure == "publish")
    assert h.events.count("permit") == h.events.count("writer") == 1
    assert h.events.count("publish") <= 1
    assert h.account_reads == 3 and len(h.storage_reads) == 2
    assert h.gates == [False] * 8


@pytest.mark.parametrize("state", list(Storage))
def test_writer_return_never_replaces_fresh_finalized_proof(monkeypatch, state):
    h = Harness(monkeypatch)
    h.final_storage_state = state
    result = h.run()
    assert result.classification is (
        Status.DECISION_PUBLISHED
        if state is Storage.FINALIZED_IDENTICAL
        else Status.PUBLICATION_OUTCOME_AMBIGUOUS
    )
    assert result.real_effect_performed is True
    assert h.account_reads == 3


@pytest.mark.parametrize("initial", [Storage.ABSENT, Storage.FINALIZED_IDENTICAL])
def test_final_predecessor_drift_prevents_clean_success(monkeypatch, initial):
    h = Harness(monkeypatch)
    h.storage_state = initial
    h.drift_at = 3
    result = h.run()
    assert result.classification is (
        Status.PUBLICATION_OUTCOME_AMBIGUOUS
        if initial is Storage.ABSENT
        else Status.BLOCKED
    )
    assert h.events.index("account:3") < h.events.index("release")


def test_postlock_predecessor_is_used_or_blocks(monkeypatch):
    h = Harness(monkeypatch)
    h.drift_at = 2
    h.build_decision = lambda *args: h.binding
    assert h.run().classification is Status.BLOCKED
    assert "permit" not in h.events


def test_different_current_selected_c3_cannot_publish_a_valid_other_decision(
    monkeypatch,
):
    h = Harness(monkeypatch)
    h.current = _session_read(date(2026, 8, 24), 106)
    assert h.run().classification is Status.BLOCKED
    assert "permit" not in h.events


def test_wrong_c3_selection_identity_blocks_even_with_identical_snapshot(monkeypatch):
    h = Harness(monkeypatch)
    audit = replace(h.current.selected.audit, selection_id=_DRIFT)
    h.current = replace(h.current, selected=replace(h.current.selected, audit=audit))
    assert h.run().classification is Status.BLOCKED
    assert "permit" not in h.events


@pytest.mark.parametrize(
    "error,status",
    [
        (daily.InsufficientAuthoritativeC3History(), Status.DECISION_NOT_READY),
        (daily.AuthoritativeC3HistorySessionGap(), Status.SESSION_GAP),
        (ValueError("invalid provenance"), Status.BLOCKED),
    ],
)
def test_history_not_ready_gap_or_invalid(monkeypatch, error, status):
    h = Harness(monkeypatch)

    def fail(*args):
        raise error

    h.build_history = fail
    assert h.run().classification is status
    assert "decision" not in h.events and "permit" not in h.events


def test_zero_arguments_and_bounded_non_authorizing_result(monkeypatch):
    assert not inspect.signature(
        d6.run_personal_desktop_unattended_decision_publication
    ).parameters
    h = Harness(monkeypatch)
    result = h.run()
    assert {f.name for f in fields(result)} == {
        "classification",
        "decision_id",
        "selected_session",
        "intended_execution_session",
        "real_effect_performed",
    }
    assert not hasattr(result, "__dict__")
    with pytest.raises(ValueError):
        replace(result, real_effect_performed=1)


def test_production_storage_provenance_cannot_be_forged(monkeypatch):
    h = Harness(monkeypatch)
    dependencies = d6._production_dependencies()
    with pytest.raises(Exception, match="provenance"):
        dependencies.require_storage(
            h.authority, h.binding, _storage(h.binding, Storage.ABSENT)
        )


def test_production_dependencies_use_existing_pd2a_and_no_g6(monkeypatch):
    h = Harness(monkeypatch)
    dependencies = d6._production_dependencies()
    assert dependencies.admission is d6.supervised_paper_cycle_admission
    assert (
        dependencies.build_history is daily.build_personal_desktop_unattended_c3_history
    )
    assert (
        dependencies.build_decision
        is daily.build_personal_desktop_unattended_next_decision
    )
    assert dependencies.issue_permit is pub.issue_pre_open_decision_publication_permit
    assert (
        dependencies.open_writer
        is output.open_personal_desktop_unattended_decision_output_capability
    )
    tree = ast.parse(Path(d6.__file__).read_text())
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not calls & {
        "run_personal_desktop_unattended_daily_cycle",
        "run_personal_desktop_unattended_market_data_capture",
        "reconcile_personal_desktop_unattended_market_data_capture",
        "execute_personal_desktop_unattended_paper_operation",
        "provision_personal_desktop_unattended_storage",
    }
    assert h.run().classification is Status.DECISION_PUBLISHED


@pytest.mark.parametrize(
    "failure", ["staging", "write", "flush", "finalize", "readback"]
)
def test_native_failure_matrix_spends_permit_and_d6_never_repairs(monkeypatch, failure):
    h = Harness(monkeypatch)

    class Native(DecisionNative):
        def create_directory(self, path, policy):
            assert h.gates[1] is True and h.held
            super().create_directory(path, policy)
            if failure == "staging":
                raise RuntimeError("staging failure")

        def write_file(self, path, payload, policy):
            assert h.gates == [False, True, False, False, False, False, False, False]
            if failure == "write":
                raise RuntimeError("write failure")
            super().write_file(path, payload, policy)
            if failure == "flush":
                raise RuntimeError("flush failure")

        def rename_unattended_write_through(self, staging, final):
            if failure == "finalize":
                raise RuntimeError("finalization failure")
            super().rename_unattended_write_through(staging, final)

        def read(self, handle, maximum):
            payload = super().read(handle, maximum)
            if failure == "readback" and "\\unattended-paper-decision-" in handle.path:
                return b"corrupt"
            return payload

    api = Native()
    saved = {}

    def open_writer(storage, permit):
        h.events.append("writer")
        saved["permit"] = permit
        writer = _OPEN_DISPOSABLE_WRITER(h.binding, storage, permit, api)
        saved["writer"] = writer
        return writer

    h.open_writer = open_writer
    h.final_storage_state = (
        Storage.STAGING_PRESENT
        if failure != "readback"
        else Storage.FINALIZED_IDENTICAL
    )
    result = h.run()
    assert result.classification is Status.PUBLICATION_OUTCOME_AMBIGUOUS
    assert result.real_effect_performed is True
    assert h.events.count("permit") == h.events.count("writer") == 1
    assert h.gates == [False] * 8 and h.account_reads == 3
    assert sum(event[0] == "create-directory" for event in api.events) == 1
    assert api.open_handles == {}
    with pytest.raises(
        pub.PersonalDesktopUnattendedDecisionPublicationError, match="consumed"
    ):
        pub.consume_disposable_pre_open_decision_publication_permit_for_test(
            saved["permit"], h.binding, h.storage_reads[0], _NOW
        )


def test_exact_history_and_decision_reconstruction_are_wake_time_independent(
    monkeypatch,
):
    h = Harness(monkeypatch)
    selected = tuple(
        _session_read(day, 100 + i)
        for i, day in enumerate(
            [
                date(2026, 8, 17),
                date(2026, 8, 18),
                date(2026, 8, 19),
                date(2026, 8, 20),
                date(2026, 8, 21),
                date(2026, 8, 24),
            ]
        )
    )
    reader_refs, _ = install_weak_selected_c3_history_reader(
        monkeypatch,
        authority=h.authority,
        selected=(*selected[:-1], h.current),
        current=h.current,
        config=daily.personal_desktop_unattended_strategy_config(),
    )

    from .test_manual_paper_strategy_plan import _prior

    h.account.prior_checkpoint = _prior()
    monkeypatch.setattr(
        intent_module,
        "require_selected_c3_strategy_history_binding",
        require_selected_c3_strategy_history_binding,
    )
    h.build_history = daily.build_personal_desktop_unattended_c3_history
    h.build_decision = daily.build_personal_desktop_unattended_next_decision
    first = []
    original_storage = h.read_storage

    def capture_storage(c1, expected):
        h.binding = expected
        first.append(expected)
        return original_storage(c1, expected)

    h.read_storage = capture_storage
    result = h.run()
    assert result.classification is Status.DECISION_PUBLISHED
    binding = first[0]
    assert len(binding.decision.history_c3) == 5
    assert tuple(
        item.snapshot_artifact for item in binding.decision.history_c3
    ) == tuple(item.selected.snapshot_bytes for item in selected[:-1])
    assert (
        binding.decision.current_c3.snapshot_artifact
        == selected[-1].selected.snapshot_bytes
    )
    assert (
        binding.decision.prepared_decision.planning_at
        == h.current.selected.verification.snapshot.audit.captured_at
    )
    gc.collect()
    assert reader_refs and all(reference() is None for reference in reader_refs)
    # A new wake re-derives the same exact artifact, without a previous G6 result.
    h.events.clear()
    h.account_reads = 0
    h.storage_reads.clear()
    h.storage_state = Storage.FINALIZED_IDENTICAL
    h.observed += timedelta(hours=1)
    assert h.run().classification is Status.DECISION_ALREADY_FINALIZED
    assert first[-1].artifact_bytes == binding.artifact_bytes


def test_all_committed_gate_values_false_and_only_publication_is_assigned():
    assert daily.personal_desktop_unattended_effect_gate_state() == (False,) * 8
    tree = ast.parse(Path(d6.__file__).read_text())
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and node.attr.endswith("EFFECTS_ENABLED")
    ]
    assert [node.attr for node in assignments] == [
        "PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED"
    ]
    for node in assignments:
        assert isinstance(node.value, ast.Name) and node.value.id == "publication"


def test_final_read_exception_still_rereads_account_under_mutex(monkeypatch):
    h = Harness(monkeypatch)
    original = h.read_storage

    def read(c1, expected):
        if h.storage_reads:
            raise RuntimeError("final read failure")
        return original(c1, expected)

    h.read_storage = read
    result = h.run()
    assert result.classification is Status.PUBLICATION_OUTCOME_AMBIGUOUS
    assert result.real_effect_performed is True
    assert h.account_reads == 3 and h.events[-2:] == ["c1", "release"]
    assert h.gates == [False] * 8


def test_final_c1_drift_prevents_clean_publication(monkeypatch):
    h = Harness(monkeypatch)
    original = h.validate

    def validate(c1):
        if h.account_reads == 3:
            raise ValueError("C1 changed")
        return original(c1)

    h.validate = validate
    assert h.run().classification is Status.PUBLICATION_OUTCOME_AMBIGUOUS
    assert h.gates == [False] * 8


@pytest.mark.parametrize(
    "component", ["authority", "expected", "classification", "same-session-conflict"]
)
def test_production_storage_reconciliation_rejects_drift(monkeypatch, component):
    h = Harness(monkeypatch)
    storage = _storage(h.binding, Storage.ABSENT)
    conflicting = _decision_binding(monkeypatch, caller_key="conflicting-same-session")
    verified = SimpleNamespace(
        authority=h.authority,
        expected=h.binding,
        classification=Storage.ABSENT,
        finalized=(),
    )
    if component == "authority":
        verified.authority = object()
    elif component == "expected":
        verified.expected = conflicting
    elif component == "classification":
        verified.classification = Storage.FINALIZED_IDENTICAL
    else:
        verified.finalized = (conflicting,)
    monkeypatch.setattr(
        d6, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        d6,
        "require_validated_personal_desktop_unattended_decision_storage_read",
        lambda value: verified,
    )
    with pytest.raises(ValueError, match="provenance"):
        d6._production_dependencies().require_storage(h.authority, h.binding, storage)


def test_concurrent_duplicate_invocations_serialize_and_publish_once(monkeypatch):
    first, second = Harness(monkeypatch), Harness(monkeypatch)
    mutex = threading.Lock()
    barrier = threading.Barrier(2)
    gates = [False] * 8
    state = [Storage.ABSENT]
    for h in (first, second):
        h.gates = gates
        original_account = h.read_account
        original_writer = h.open_writer

        def read_account(c1, historical, *, harness=h, original=original_account):
            account = original(c1, historical)
            if harness.account_reads == 1:
                barrier.wait(timeout=10)
            return account

        @contextmanager
        def admission(prelock, *, harness=h):
            with mutex:
                harness.held = True
                try:
                    yield
                finally:
                    harness.held = False

        def read_storage(c1, expected, *, harness=h):
            assert harness.held and gates == [False] * 8
            result = _storage(expected, state[0])
            harness.storage_reads.append(result)
            return result

        def open_writer(storage, permit, *, original=original_writer):
            writer = original(storage, permit)
            publish = writer.publish

            def finalize(observed):
                result = publish(observed)
                state[0] = Storage.FINALIZED_IDENTICAL
                return result

            writer.publish = finalize
            return writer

        h.read_account, h.admission, h.read_storage, h.open_writer = (
            read_account,
            admission,
            read_storage,
            open_writer,
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda harness: harness.run(), (first, second)))
    assert {result.classification for result in results} == {
        Status.DECISION_PUBLISHED,
        Status.DECISION_ALREADY_FINALIZED,
    }
    assert sum(result.real_effect_performed for result in results) == 1
    assert sum(h.events.count("permit") for h in (first, second)) == 1
    assert sum(h.events.count("writer") for h in (first, second)) == 1
    assert sum(h.events.count("publish") for h in (first, second)) == 1


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("value", [True, 0, None])
def test_native_factory_uses_current_owning_module_and_all_eight_gates(
    monkeypatch, index, value
):
    from trading_bot.runtime import personal_desktop_paper_account_security as security
    from trading_bot.runtime import (
        personal_desktop_paper_receipt_recovery_execution as recovery,
    )
    from trading_bot.runtime import (
        personal_desktop_supervised_paper_operation_execution as supervised,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_market_data_capture as capture,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_operation_execution as execution,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_storage_provisioning as provisioning,
    )

    gates = [
        (capture, "PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED"),
        (pub, "PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED"),
        (security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED"),
        (security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED"),
        (supervised, "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED"),
        (recovery, "PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED"),
        (execution, "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED"),
        (
            provisioning,
            "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED",
        ),
    ]
    # Source remains false, while process-local publication authority is dynamic.
    for module, name in gates:
        tree = ast.parse(Path(module.__file__).read_text())
        initial = [
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            )
        ]
        assert len(initial) == 1 and initial[0].value is False
    monkeypatch.setattr(pub, gates[1][1], True)
    monkeypatch.setattr(*gates[index], value)
    h = Harness(monkeypatch)
    storage = _storage(h.binding, Storage.ABSENT)
    verified = SimpleNamespace(
        authority=h.authority, expected=h.binding, classification=Storage.ABSENT
    )
    monkeypatch.setattr(
        output, "require_validated_production_authority", lambda value: value
    )
    monkeypatch.setattr(
        output,
        "require_validated_personal_desktop_unattended_decision_storage_read",
        lambda value: verified,
    )
    monkeypatch.setattr(
        output, "require_pre_open_decision_publication_permit", lambda *args: None
    )
    api = DecisionNative()
    constructions = []

    def native():
        constructions.append(True)
        return api

    monkeypatch.setattr(output, "_WindowsPaperRuntimeOutputNativeApi", native)
    permit = pub.issue_disposable_pre_open_decision_publication_permit_for_test(
        h.binding, storage, h.binding.decision.intended_execution_session, _NOW
    )
    allowed = index == 1 and value is True
    if allowed:
        with output.open_personal_desktop_unattended_decision_output_capability(
            storage, permit
        ) as writer:
            assert writer.real_effect_performed is False
        assert constructions == [True]
    else:
        with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError, match="gate"):
            output.open_personal_desktop_unattended_decision_output_capability(
                storage, permit
            )
        assert constructions == []
    assert not any(event[0] == "create-directory" for event in api.events)
