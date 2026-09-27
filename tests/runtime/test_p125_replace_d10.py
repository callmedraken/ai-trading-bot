"""Fake-only orchestration and inert-entry tests for the P125-R1 operator."""

from __future__ import annotations

import ast
import builtins
import importlib
import io
import json
from pathlib import Path

import pytest

from scripts import d10_protected_replacement as r
from scripts import p125_replace_d10 as operator


def _namespace(canonical: str, staging: str, retired: str) -> r.NamespaceObservation:
    def root(path: str, state: str) -> r.RootObservation:
        if state == "ABSENT":
            return r.RootObservation(path, False)
        if state == "PARTIAL":
            return r.RootObservation(path, True)
        identity = r.OLD_IDENTITY if state == "OLD" else r.NEW_IDENTITY
        return r.RootObservation(path, True, identity)

    return r.NamespaceObservation(
        root(r.CANONICAL_PATH, canonical),
        root(r.STAGING_PATH, staging),
        root(r.RETIRED_PATH, retired),
        unexpected_reserved_names_absent=True,
    )


def _admission() -> r.AdmissionFacts:
    return r.AdmissionFacts(*([True] * len(r.AdmissionFacts.__dataclass_fields__)))


def _post_facts() -> r.PostPublicationFacts:
    return r.PostPublicationFacts(
        new_canonical_exact=True,
        staging_absent=True,
        old_retired_exact=True,
        canonical_trust_absent=True,
        activation_and_cache_absent=True,
        d5_capture_only_scheduler_exact=True,
        protected_parent_exact=True,
        same_local_ntfs_volume=True,
        unexpected_reserved_names_absent=True,
    )


class FakeSession:
    def __init__(
        self,
        events: list[object],
        *,
        first: r.MutationOutcome = r.MutationOutcome.SUCCESS,
        second: r.MutationOutcome = r.MutationOutcome.SUCCESS,
    ) -> None:
        self.events = events
        self.first = first
        self.second = second
        self.result = r.begin_replacement(
            _namespace("OLD", "NEW", "ABSENT"), _admission()
        )
        self.admission = object()
        self.first_calls = 0
        self.second_calls = 0

    def retire_old_root(self) -> r.MutationOutcome:
        self.events.append("rename-old-to-retired")
        self.first_calls += 1
        self.result = r.record_rename(
            self.result, r.RenameStep.OLD_TO_RETIRED, self.first
        )
        return self.first

    def publish_staged_root(self) -> r.MutationOutcome:
        self.events.append("rename-staging-to-canonical")
        self.second_calls += 1
        self.result = r.record_rename(
            self.result, r.RenameStep.STAGING_TO_CANONICAL, self.second
        )
        return self.second


class FakeOperations:
    def __init__(
        self,
        states: list[r.NamespaceObservation],
        *,
        session: FakeSession | None = None,
        staging_error: Exception | None = None,
        admission_error: Exception | None = None,
        post_facts: r.PostPublicationFacts | None = None,
        observe_error_on_call: int | None = None,
    ) -> None:
        self.states = states
        self.last_state = states[-1]
        self.events: list[object] = []
        self.repository_roots: list[Path] = []
        self.staging_error = staging_error
        self.admission_error = admission_error
        self.post_facts = post_facts or _post_facts()
        self.observe_error_on_call = observe_error_on_call
        self.observe_calls = 0
        self.session = session or FakeSession(self.events)

    def observe_namespace(self) -> r.NamespaceObservation:
        self.events.append("observe-namespace")
        self.observe_calls += 1
        if self.observe_calls == self.observe_error_on_call:
            raise OSError("unreadable host data must not be reported")
        if self.states:
            self.last_state = self.states.pop(0)
        return self.last_state

    def construct_fixed_staging(self, repository_root: Path) -> None:
        self.events.append("construct-fixed-staging")
        self.repository_roots.append(repository_root)
        if self.staging_error is not None:
            raise self.staging_error

    def begin_fixed_rename_session(self) -> FakeSession:
        self.events.append("fresh-full-admission-and-rename-session")
        if self.admission_error is not None:
            raise self.admission_error
        return self.session

    def observe_post_publication(
        self, admission: object
    ) -> tuple[r.NamespaceObservation, r.PostPublicationFacts]:
        self.events.append(("post-publication", admission))
        return _namespace("NEW", "ABSENT", "OLD"), self.post_facts


@pytest.mark.parametrize("state", ["CLEAN_INITIAL", "OLD_CANONICAL"])
def test_admitted_start_states_stage_only_when_clean_then_refresh_admission(
    state: str,
) -> None:
    initial = (
        _namespace("OLD", "ABSENT", "ABSENT")
        if state == "CLEAN_INITIAL"
        else _namespace("OLD", "NEW", "ABSENT")
    )
    states = [initial]
    if state == "CLEAN_INITIAL":
        states.append(_namespace("OLD", "NEW", "ABSENT"))
    operations = FakeOperations(states)
    repository_root = Path("C:/certified/source")

    result = operator.run_replacement(repository_root, operations)

    assert result.phase is r.Phase.PASS
    expected = (
        [
            "observe-namespace",
            "construct-fixed-staging",
            "fresh-full-admission-and-rename-session",
            "rename-old-to-retired",
            "rename-staging-to-canonical",
        ]
        if state == "CLEAN_INITIAL"
        else [
            "observe-namespace",
            "fresh-full-admission-and-rename-session",
            "rename-old-to-retired",
            "rename-staging-to-canonical",
        ]
    )
    assert operations.events[: len(expected)] == expected
    if state == "CLEAN_INITIAL":
        assert operations.repository_roots == [repository_root]
    else:
        assert operations.repository_roots == []
    assert operations.events[-1][0] == "post-publication"


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ("OLD_RETIRED", r.BlockReason.SEPARATE_RECOVERY_REQUIRED),
        ("NEW_CANONICAL", r.BlockReason.SEPARATE_RECOVERY_REQUIRED),
        ("CONFLICTING", r.BlockReason.NAMESPACE_CONFLICT),
    ],
)
def test_interrupted_or_conflicting_initial_states_do_not_continue(
    state: str, reason: r.BlockReason
) -> None:
    triples = {
        "OLD_RETIRED": ("ABSENT", "NEW", "OLD"),
        "NEW_CANONICAL": ("NEW", "ABSENT", "OLD"),
        "CONFLICTING": ("OLD", "PARTIAL", "ABSENT"),
    }
    operations = FakeOperations([_namespace(*triples[state])])

    result = operator.run_replacement(Path("C:/source"), operations)

    assert result.phase is r.Phase.BLOCKED
    assert result.reason_code is reason
    assert operations.events == ["observe-namespace"]


@pytest.mark.parametrize(
    ("after", "reason"),
    [
        ("CLEAN_INITIAL", r.BlockReason.STAGING_FAILED),
        ("OLD_CANONICAL", r.BlockReason.STAGING_FAILED),
        ("CONFLICTING", r.BlockReason.STAGING_FAILED),
        ("OLD_RETIRED", r.BlockReason.SEPARATE_RECOVERY_REQUIRED),
        ("NEW_CANONICAL", r.BlockReason.SEPARATE_RECOVERY_REQUIRED),
    ],
)
def test_staging_failure_is_terminal_and_classifies_remaining_namespace(
    after: str, reason: r.BlockReason
) -> None:
    after_state = {
        "CLEAN_INITIAL": ("OLD", "ABSENT", "ABSENT"),
        "OLD_CANONICAL": ("OLD", "NEW", "ABSENT"),
        "CONFLICTING": ("OLD", "PARTIAL", "ABSENT"),
        "OLD_RETIRED": ("ABSENT", "NEW", "OLD"),
        "NEW_CANONICAL": ("NEW", "ABSENT", "OLD"),
    }[after]
    operations = FakeOperations(
        [_namespace("OLD", "ABSENT", "ABSENT"), _namespace(*after_state)],
        staging_error=OSError("private path must not be reported"),
    )

    result = operator.run_replacement(Path("C:/source"), operations)

    assert result.phase is r.Phase.BLOCKED
    assert result.reason_code is reason
    assert result.highest_definitely_completed_state is r.NamespaceState(after)
    assert operations.events == [
        "observe-namespace",
        "construct-fixed-staging",
        "observe-namespace",
    ]
    transcript = result.canonical_transcript()
    assert b"private path" not in transcript
    assert json.loads(transcript)["reason_code"] == reason.value


def test_staging_failure_with_unreadable_namespace_reports_conflict() -> None:
    operations = FakeOperations(
        [_namespace("OLD", "ABSENT", "ABSENT")],
        staging_error=OSError("partial write"),
        observe_error_on_call=2,
    )

    result = operator.run_replacement(Path("C:/source"), operations)

    assert result.phase is r.Phase.BLOCKED
    assert result.reason_code is r.BlockReason.STAGING_FAILED
    assert result.highest_definitely_completed_state is r.NamespaceState.CONFLICTING
    assert operations.events == [
        "observe-namespace",
        "construct-fixed-staging",
        "observe-namespace",
    ]
    assert result.canonical_transcript() == result.canonical_transcript()


def test_admission_failure_is_closed_and_uses_fresh_namespace_state() -> None:
    operations = FakeOperations(
        [
            _namespace("OLD", "ABSENT", "ABSENT"),
            _namespace("OLD", "NEW", "ABSENT"),
        ],
        admission_error=RuntimeError("raw admission details"),
    )
    result = operator.run_replacement(Path("C:/source"), operations)
    assert result.phase is r.Phase.BLOCKED
    assert result.reason_code is r.BlockReason.ADMISSION_FAILED
    assert result.highest_definitely_completed_state is r.NamespaceState.OLD_CANONICAL
    assert "rename-old-to-retired" not in operations.events


def test_first_indeterminate_stops_without_second_rename_or_retry() -> None:
    session_events: list[object] = []
    session = FakeSession(session_events, first=r.MutationOutcome.INDETERMINATE)
    operations = FakeOperations([_namespace("OLD", "NEW", "ABSENT")], session=session)

    result = operator.run_replacement(Path("C:/source"), operations)

    assert result.phase is r.Phase.BLOCKED
    assert result.reason_code is r.BlockReason.INDETERMINATE_MUTATION
    assert result.highest_definitely_completed_state is r.NamespaceState.OLD_CANONICAL
    assert session_events == ["rename-old-to-retired"]
    assert session.first_calls == 1 and session.second_calls == 0
    assert "post-publication" not in operations.events


def test_second_indeterminate_stops_without_retry_rollback_or_cleanup() -> None:
    session_events: list[object] = []
    session = FakeSession(session_events, second=r.MutationOutcome.INDETERMINATE)
    operations = FakeOperations([_namespace("OLD", "NEW", "ABSENT")], session=session)

    result = operator.run_replacement(Path("C:/source"), operations)

    assert result.phase is r.Phase.BLOCKED
    assert result.reason_code is r.BlockReason.INDETERMINATE_MUTATION
    assert result.highest_definitely_completed_state is r.NamespaceState.OLD_RETIRED
    assert result.completed_renames == (r.RenameStep.OLD_TO_RETIRED,)
    assert session_events == ["rename-old-to-retired", "rename-staging-to-canonical"]
    assert session.first_calls == 1 and session.second_calls == 1
    assert "post-publication" not in operations.events


@pytest.mark.parametrize(
    "field",
    [field for field in r.PostPublicationFacts.__dataclass_fields__],
)
def test_every_post_publication_fact_is_required(field: str) -> None:
    session = FakeSession([])
    operations = FakeOperations(
        [_namespace("OLD", "NEW", "ABSENT")],
        session=session,
        post_facts=r.PostPublicationFacts(
            **{
                **{name: True for name in r.PostPublicationFacts.__dataclass_fields__},
                field: False,
            }
        ),
    )
    result = operator.run_replacement(Path("C:/source"), operations)
    assert result.phase is r.Phase.BLOCKED
    assert result.reason_code is r.BlockReason.POST_PUBLICATION_VERIFICATION_FAILED
    assert result.highest_definitely_completed_state is r.NamespaceState.NEW_CANONICAL


def test_post_publication_pass_and_terminal_transcripts_are_deterministic() -> None:
    operations = FakeOperations([_namespace("OLD", "NEW", "ABSENT")])
    result = operator.run_replacement(Path("C:/source"), operations)
    transcript = result.canonical_transcript()
    assert result.phase is r.Phase.PASS
    assert transcript == result.canonical_transcript()
    payload = json.loads(transcript)
    assert payload["completed_renames"] == [
        "OLD_TO_RETIRED",
        "STAGING_TO_CANONICAL",
    ]
    assert payload["highest_definitely_completed_namespace_state"] == "NEW_CANONICAL"
    for key in (
        "activation_authority",
        "scheduler_authority",
        "trading_authority",
        "retirement_cleanup_authority",
    ):
        assert payload[key] == "NONE"

    blocked = operator.run_replacement(
        Path("C:/source"),
        FakeOperations([_namespace("OLD", "PARTIAL", "ABSENT")]),
    )
    blocked_transcript = blocked.canonical_transcript()
    assert blocked_transcript == blocked.canonical_transcript()
    assert json.loads(blocked_transcript)["reason_code"] == "NAMESPACE_CONFLICT"
    assert b"C:/source" not in transcript + blocked_transcript


def test_import_and_cli_are_inert_without_the_protected_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    importlib.reload(operator)
    assert "d10_protected_replacement_windows" not in operator.__dict__
    original_import = builtins.__import__

    def deny_windows_import(name, *args, **kwargs):
        if name == "scripts.d10_protected_replacement_windows":
            raise AssertionError("native adapter imported before explicit flag")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny_windows_import)
    with pytest.raises(SystemExit) as error:
        operator.main(["--repository-root", "C:/source"])
    assert error.value.code == 2
    assert "--execute-protected-p125-r1" in capsys.readouterr().err


def test_cli_accepts_only_repository_source_and_explicit_execution_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import d10_protected_replacement_windows as windows

    stream = io.BytesIO()
    fake_stdout = type("FakeStdout", (), {"buffer": stream})()
    monkeypatch.setattr(operator.sys, "stdout", fake_stdout)
    seen: list[Path] = []
    result = r.ReplacementResult(
        r.Phase.BLOCKED,
        r.NamespaceState.OLD_RETIRED,
        reason_code=r.BlockReason.SEPARATE_RECOVERY_REQUIRED,
    )

    def fake_run(repository_root: Path, operations: object) -> r.ReplacementResult:
        assert operations is windows
        seen.append(repository_root)
        return result

    monkeypatch.setattr(operator, "run_replacement", fake_run)
    exit_code = operator.main(
        [
            "--repository-root",
            "C:/certified/source",
            "--execute-protected-p125-r1",
        ]
    )
    assert exit_code == 1
    assert seen == [Path("C:/certified/source")]
    assert stream.getvalue() == result.canonical_transcript()


def test_entry_point_exposes_no_unreviewed_effect_surfaces() -> None:
    source_path = Path(operator.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls.intersection(
        {
            "delete",
            "rollback",
            "sign",
            "sign_digest",
            "activate",
            "register_task",
            "set_scheduled_task",
            "submit_order",
            "place_order",
        }
    )
    for forbidden in ("activation.lease", "provider", "broker", "live trading"):
        assert forbidden not in source.casefold()
