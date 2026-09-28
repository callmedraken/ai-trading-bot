"""Fake-only R1G recovery authority and terminal transcript tests."""

from __future__ import annotations

import ast
import builtins
import importlib
import io
import json
from pathlib import Path

import pytest

from scripts import d10_protected_replacement as r
from scripts import p125_recover_d10 as operator


def _namespace(state: r.NamespaceState) -> r.NamespaceObservation:
    triples = {
        r.NamespaceState.CLEAN_INITIAL: ("OLD", "ABSENT", "ABSENT"),
        r.NamespaceState.OLD_CANONICAL: ("OLD", "NEW", "ABSENT"),
        r.NamespaceState.OLD_RETIRED: ("ABSENT", "NEW", "OLD"),
        r.NamespaceState.NEW_CANONICAL: ("NEW", "ABSENT", "OLD"),
        r.NamespaceState.CONFLICTING: ("OLD", "PARTIAL", "ABSENT"),
    }

    def root(path: str, value: str) -> r.RootObservation:
        return r.RootObservation(
            path,
            value != "ABSENT",
            {"OLD": r.OLD_IDENTITY, "NEW": r.NEW_IDENTITY}.get(value),
        )

    return r.NamespaceObservation(
        *(
            root(path, value)
            for path, value in zip(
                (r.CANONICAL_PATH, r.STAGING_PATH, r.RETIRED_PATH),
                triples[state],
                strict=True,
            )
        ),
        True,
    )


class FakeSession:
    def __init__(
        self,
        events: list[object],
        first=r.MutationOutcome.SUCCESS,
        second=r.MutationOutcome.SUCCESS,
    ):
        self.events = events
        self.first = first
        self.second = second
        self.result = r.begin_replacement(
            _namespace(r.NamespaceState.OLD_CANONICAL), r.AdmissionFacts(*([True] * 11))
        )
        self.admission = object()

    def retire_old_root(self) -> r.MutationOutcome:
        self.events.append("first")
        diagnostic = (
            r.RenameDiagnostic(
                r.RenameStep.OLD_TO_RETIRED, r.RenameFailureStage.NATIVE_FALSE, 5
            )
            if self.first is r.MutationOutcome.INDETERMINATE
            else None
        )
        self.result = r.record_rename(
            self.result, r.RenameStep.OLD_TO_RETIRED, self.first, diagnostic
        )
        return self.first

    def publish_staged_root(self) -> r.MutationOutcome:
        self.events.append("second-with-existing-revalidation")
        diagnostic = (
            r.RenameDiagnostic(
                r.RenameStep.STAGING_TO_CANONICAL,
                r.RenameFailureStage.NATIVE_FALSE,
                0xFFFFFFFF,
            )
            if self.second is r.MutationOutcome.INDETERMINATE
            else None
        )
        self.result = r.record_rename(
            self.result, r.RenameStep.STAGING_TO_CANONICAL, self.second, diagnostic
        )
        return self.second


class FakeOperations:
    def __init__(
        self,
        initial=r.NamespaceState.OLD_CANONICAL,
        *,
        first=r.MutationOutcome.SUCCESS,
        second=r.MutationOutcome.SUCCESS,
    ):
        self.state = initial
        self.events: list[object] = []
        self.session = FakeSession(self.events, first, second)
        self.material_error = False
        self.admission_error = False
        self.observe_error = False
        self.post_error = False
        self.post_namespace = _namespace(r.NamespaceState.NEW_CANONICAL)
        self.post_facts = r.PostPublicationFacts(*([True] * 9))

    def observe_namespace(self) -> r.NamespaceObservation:
        self.events.append("observe")
        if self.observe_error:
            raise OSError("private observation path")
        return _namespace(self.state)

    def validate_recovery_material(self, repository_root: Path) -> None:
        self.events.append(("validate-material", repository_root))
        if self.material_error:
            raise OSError("private material details")

    def construct_fixed_staging(self, _root: Path) -> None:
        pytest.fail("recovery may never construct or rewrite staging")

    def begin_fixed_rename_session(self) -> FakeSession:
        self.events.append("full-fresh-admission")
        if self.admission_error:
            raise OSError("private admission details")
        return self.session

    def observe_post_publication(self, admission: object):
        assert admission is self.session.admission
        self.events.append("post-verification")
        if self.post_error:
            raise OSError("private post-verification details")
        return self.post_namespace, self.post_facts


@pytest.mark.parametrize(
    "state",
    [
        state
        for state in r.NamespaceState
        if state is not r.NamespaceState.OLD_CANONICAL
    ],
)
def test_recovery_rejects_every_other_start_state_before_material_or_admission(
    state: r.NamespaceState,
) -> None:
    operations = FakeOperations(state)
    result = operator.run_recovery(Path("C:/source"), operations)
    assert result.phase is r.Phase.BLOCKED
    assert result.highest_definitely_completed_state is state
    assert operations.events == ["observe"]
    assert result.next_rename is None and result.completed_renames == ()


def test_exact_old_canonical_recovery_uses_existing_sequence_and_post_proof() -> None:
    operations = FakeOperations()
    root = Path("C:/certified/source")
    result = operator.run_recovery(root, operations)
    assert result.phase is r.Phase.PASS
    assert operations.events == [
        "observe",
        ("validate-material", root),
        "full-fresh-admission",
        "first",
        "second-with-existing-revalidation",
        "post-verification",
    ]
    assert result.rename_diagnostic is None
    payload = json.loads(result.canonical_transcript())
    assert payload["canonical_trust_disposition"] == "ABSENT"
    assert payload["retired_tree_verification"] == "PASS"
    for key in (
        "activation_authority",
        "scheduler_authority",
        "trading_authority",
        "retirement_cleanup_authority",
    ):
        assert payload[key] == "NONE"


@pytest.mark.parametrize("after", list(r.NamespaceState))
def test_first_indeterminate_stops_even_after_new_exact_read_only_classification(
    after: r.NamespaceState,
) -> None:
    operations = FakeOperations(first=r.MutationOutcome.INDETERMINATE)
    first = operations.session.retire_old_root

    def fail_first():
        outcome = first()
        operations.state = after
        return outcome

    operations.session.retire_old_root = fail_first
    result = operator.run_recovery(Path("C:/source"), operations)
    assert result.reason_code is r.BlockReason.INDETERMINATE_MUTATION
    assert result.highest_definitely_completed_state is r.NamespaceState.OLD_CANONICAL
    assert result.completed_renames == () and result.next_rename is None
    assert result.rename_diagnostic == r.RenameDiagnostic(
        r.RenameStep.OLD_TO_RETIRED, r.RenameFailureStage.NATIVE_FALSE, 5
    )
    assert operations.events[-2:] == ["first", "observe"]
    assert operations.events.count("first") == 1
    assert "second-with-existing-revalidation" not in operations.events
    assert "post-verification" not in operations.events


def test_second_indeterminate_preserves_highest_definite_old_retired_evidence() -> None:
    operations = FakeOperations(second=r.MutationOutcome.INDETERMINATE)
    result = operator.run_recovery(Path("C:/source"), operations)
    assert result.reason_code is r.BlockReason.INDETERMINATE_MUTATION
    assert result.highest_definitely_completed_state is r.NamespaceState.OLD_RETIRED
    assert result.completed_renames == (r.RenameStep.OLD_TO_RETIRED,)
    assert result.rename_diagnostic.step is r.RenameStep.STAGING_TO_CANONICAL
    assert result.rename_diagnostic.win32_error == 0xFFFFFFFF
    assert operations.events[-1] == "observe"
    assert (
        operations.events.count("first")
        == operations.events.count("second-with-existing-revalidation")
        == 1
    )
    assert "post-verification" not in operations.events


@pytest.mark.parametrize(
    "boundary", ["material_error", "admission_error", "observe_error"]
)
def test_read_only_recovery_admission_failures_never_attempt_rename(
    boundary: str,
) -> None:
    operations = FakeOperations()
    setattr(operations, boundary, True)
    result = operator.run_recovery(Path("C:/source"), operations)
    assert result.phase is r.Phase.BLOCKED
    assert "first" not in operations.events
    assert b"private" not in result.canonical_transcript()


@pytest.mark.parametrize("field", list(r.PostPublicationFacts.__dataclass_fields__))
def test_pass_requires_every_unchanged_post_publication_fact(field: str) -> None:
    from dataclasses import replace

    operations = FakeOperations()
    operations.post_facts = replace(operations.post_facts, **{field: False})
    result = operator.run_recovery(Path("C:/source"), operations)
    assert result.reason_code is r.BlockReason.POST_PUBLICATION_VERIFICATION_FAILED
    assert result.highest_definitely_completed_state is r.NamespaceState.NEW_CANONICAL


@pytest.mark.parametrize("failure", ["exception", "namespace"])
def test_publication_observation_failure_never_claims_pass(failure: str) -> None:
    operations = FakeOperations()
    if failure == "exception":
        operations.post_error = True
    else:
        operations.post_namespace = _namespace(r.NamespaceState.CONFLICTING)
    result = operator.run_recovery(Path("C:/source"), operations)
    assert result.reason_code is r.BlockReason.POST_PUBLICATION_VERIFICATION_FAILED
    assert b"private" not in result.canonical_transcript()


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--execute-protected-p125-r1"],
        ["--execute-protected-p125-r1g"],
        ["--execute-protected-p125-r1g-recovery", "--staging-path", "C:/arbitrary"],
    ],
)
def test_cli_import_is_inert_and_rejects_missing_wrong_abbreviated_or_path_flags(
    monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    importlib.reload(operator)
    original = builtins.__import__

    def deny_native(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "scripts.d10_protected_replacement_windows" or (
            name == "scripts" and "d10_protected_replacement_windows" in fromlist
        ):
            pytest.fail("native import before exact explicit recovery flag")
        return original(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", deny_native)
    with pytest.raises(SystemExit) as error:
        operator.main(["--repository-root", "C:/source", *extra])
    assert error.value.code == 2


@pytest.mark.parametrize("passed", [True, False])
def test_exact_cli_flag_imports_native_only_then_emits_shared_canonical_transcript(
    monkeypatch: pytest.MonkeyPatch, passed: bool
) -> None:
    from scripts import d10_protected_replacement_windows as windows

    operations = FakeOperations(
        first=r.MutationOutcome.SUCCESS if passed else r.MutationOutcome.INDETERMINATE
    )
    result = operator.run_recovery(Path("C:/source"), operations)
    stream = io.BytesIO()
    monkeypatch.setattr(
        operator.sys, "stdout", type("Stdout", (), {"buffer": stream})()
    )
    seen = []

    def fake_run(root, effects):
        assert effects is windows
        seen.append(root)
        return result

    monkeypatch.setattr(operator, "run_recovery", fake_run)
    code = operator.main(
        [
            "--repository-root",
            "C:/certified/source",
            "--execute-protected-p125-r1g-recovery",
        ]
    )
    assert code == (0 if passed else 1)
    assert seen == [Path("C:/certified/source")]
    assert stream.getvalue() == result.canonical_transcript()
    assert b"C:/" not in stream.getvalue()


def test_recovery_source_exposes_only_reviewed_effect_methods() -> None:
    source = Path(operator.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "operations"
    }
    assert methods == {"observe_namespace", "validate_recovery_material"}
    assert "run_admitted_replacement(operations)" in source
    for forbidden in (
        "construct_fixed_staging",
        "sign_digest",
        "activate",
        "register_task",
        "rollback",
        "cleanup",
        "provider",
        "paper-v2",
        "broker",
        "live trading",
    ):
        assert forbidden not in source.casefold()
