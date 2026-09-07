from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.runtime import personal_desktop_paper_account_mutex as mutex
from trading_bot.runtime import personal_desktop_paper_account_read_authority as reader
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import personal_desktop_supervised_paper_cycle as supervised
from trading_bot.runtime.personal_desktop_paper_account_publication_freeze import (
    PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE,
)
from trading_bot.runtime.windows_authority import WindowsAuthorityError

ACCOUNT_ID = "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
OTHER_ACCOUNT_ID = "1dbbe770-9587-40cb-9762-7fa13654df5e"
TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"


def registered_account(account_id: str, terminal: str):  # type: ignore[no-untyped-def]
    authority = object.__new__(reader.ValidatedPersonalDesktopPaperAccount)
    evidence = SimpleNamespace(
        anchor=SimpleNamespace(
            paper_account_id=account_id,
            approved_trading_sid=TRADING_SID,
        ),
        prior_checkpoint=terminal,
    )
    with reader._REGISTRY_LOCK:
        reader._REGISTRY[authority] = evidence  # type: ignore[assignment]
    return authority, evidence


def unregister(*authorities) -> None:  # type: ignore[no-untyped-def]
    with reader._REGISTRY_LOCK:
        for authority in authorities:
            reader._REGISTRY.pop(authority, None)


def acquisition(
    account_id: str = ACCOUNT_ID,
    state: mutex.PaperAccountMutexState = mutex.PaperAccountMutexState.OWNED,
) -> mutex.PaperAccountMutexAcquisition:
    return mutex.PaperAccountMutexAcquisition(
        account_id,
        mutex.paper_account_mutex_name(account_id),
        mutex.paper_account_mutex_digest(account_id),
        state,
    )


class FakeAdmission:
    def __init__(
        self,
        events: list[object],
        acquired: mutex.PaperAccountMutexAcquisition,
    ) -> None:
        self.events = events
        self._acquired = acquired
        self.acquisition: mutex.PaperAccountMutexAcquisition | None = None

    def __enter__(self):  # type: ignore[no-untyped-def]
        self.events.append("mutex-enter")
        self.acquisition = self._acquired
        return self

    def __exit__(self, exc_type, exc, traceback):  # type: ignore[no-untyped-def]
        self.events.append(("mutex-exit", exc_type))
        return False


def scope_case(
    accounts,
    *,
    acquired: mutex.PaperAccountMutexAcquisition | None = None,
    production_authority=None,
):  # type: ignore[no-untyped-def]
    events: list[object] = []
    remaining = list(accounts)
    c1 = production_authority or object()

    def read_account(authority, *, historical_cycle_configuration_payloads=()):  # type: ignore[no-untyped-def]
        events.append(("read", authority, historical_cycle_configuration_payloads))
        return remaining.pop(0)

    def admit_account(authority):  # type: ignore[no-untyped-def]
        events.append(("admit", authority))
        return FakeAdmission(events, acquired or acquisition())

    scope = supervised._supervised_personal_desktop_paper_cycle(
        c1,  # type: ignore[arg-type]
        historical_cycle_configuration_payloads=(b"configuration",),
        read_account=read_account,
        admit_account=admit_account,
    )
    return scope, events, c1


def test_public_boundary_requires_genuine_production_authority_before_read_or_mutex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        pytest.fail("invalid production authority reached a paper boundary")

    monkeypatch.setattr(supervised, "read_personal_desktop_paper_account", forbidden)
    monkeypatch.setattr(supervised, "supervised_paper_cycle_admission", forbidden)
    with pytest.raises(WindowsAuthorityError):
        supervised.supervised_personal_desktop_paper_cycle(object())  # type: ignore[arg-type]


def test_public_boundary_wires_the_same_validated_authority_to_both_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pre, _ = registered_account(ACCOUNT_ID, "pre")
    post, post_evidence = registered_account(ACCOUNT_ID, "post")
    c1 = object()
    events: list[object] = []
    accounts = [pre, post]

    def require_authority(value):  # type: ignore[no-untyped-def]
        events.append(("require-c1", value))
        assert value is c1
        return c1

    def read_account(authority, *, historical_cycle_configuration_payloads=()):  # type: ignore[no-untyped-def]
        events.append(("read", authority, historical_cycle_configuration_payloads))
        return accounts.pop(0)

    def admit_account(authority):  # type: ignore[no-untyped-def]
        events.append(("admit", authority))
        return FakeAdmission(events, acquisition())

    monkeypatch.setattr(
        supervised, "require_validated_production_authority", require_authority
    )
    monkeypatch.setattr(supervised, "read_personal_desktop_paper_account", read_account)
    monkeypatch.setattr(supervised, "supervised_paper_cycle_admission", admit_account)
    try:
        scope = supervised.supervised_personal_desktop_paper_cycle(
            c1,  # type: ignore[arg-type]
            historical_cycle_configuration_payloads=(b"configuration",),
        )
        with scope as context:
            assert context.account is post
            assert context.evidence is post_evidence
        reads = [event for event in events if event[0] == "read"]
        assert len(reads) == 2
        assert all(event[1] is c1 for event in reads)
        assert all(event[2] == (b"configuration",) for event in reads)
    finally:
        unregister(pre, post)


def test_pre_lock_then_mutex_then_post_lock_and_only_post_state_is_exposed() -> None:
    pre, pre_evidence = registered_account(ACCOUNT_ID, "pre-terminal")
    post, post_evidence = registered_account(ACCOUNT_ID, "post-terminal")
    try:
        scope, events, c1 = scope_case((pre, post))
        with scope as context:
            assert events == [
                ("read", c1, (b"configuration",)),
                ("admit", pre),
                "mutex-enter",
                ("read", c1, (b"configuration",)),
            ]
            assert context.account is post
            assert context.evidence is post_evidence
            assert context.evidence is not pre_evidence
            assert context.operation_root == security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            assert context.acquisition.state is mutex.PaperAccountMutexState.OWNED
            assert context.requires_abandoned_owner_reconciliation is False
        assert events[-1] == ("mutex-exit", None)
        with pytest.raises(supervised.SupervisedPersonalDesktopPaperCycleError):
            _ = scope.evidence
    finally:
        unregister(pre, post)


def test_changed_terminal_state_between_reads_selects_post_lock_state() -> None:
    pre, _ = registered_account(ACCOUNT_ID, "old-terminal")
    post, _ = registered_account(ACCOUNT_ID, "new-terminal")
    try:
        scope, _, _ = scope_case((pre, post))
        with scope as context:
            assert context.evidence.prior_checkpoint == "new-terminal"
    finally:
        unregister(pre, post)


def test_post_lock_account_mismatch_fails_closed_and_releases() -> None:
    pre, _ = registered_account(ACCOUNT_ID, "pre")
    post, _ = registered_account(OTHER_ACCOUNT_ID, "post")
    try:
        scope, events, _ = scope_case((pre, post))
        with pytest.raises(
            supervised.SupervisedPersonalDesktopPaperCycleError,
            match="post-lock paper-account identity",
        ):
            with scope:
                pytest.fail("identity mismatch exposed a supervised context")
        assert events[-1] == ("mutex-exit", None)
    finally:
        unregister(pre, post)


def test_mutex_acquisition_account_mismatch_fails_before_post_read_and_releases() -> (
    None
):
    pre, _ = registered_account(ACCOUNT_ID, "pre")
    post, _ = registered_account(ACCOUNT_ID, "post")
    try:
        scope, events, _ = scope_case(
            (pre, post), acquired=acquisition(OTHER_ACCOUNT_ID)
        )
        with pytest.raises(
            supervised.SupervisedPersonalDesktopPaperCycleError,
            match="mutex acquisition identity",
        ):
            with scope:
                pytest.fail("mutex identity mismatch exposed a supervised context")
        assert [event[0] for event in events if isinstance(event, tuple)].count(
            "read"
        ) == 1
        assert events[-1] == ("mutex-exit", None)
    finally:
        unregister(pre, post)


def test_abandoned_owner_state_remains_explicit_without_an_execution_api() -> None:
    pre, _ = registered_account(ACCOUNT_ID, "pre")
    post, _ = registered_account(ACCOUNT_ID, "post")
    try:
        scope, _, _ = scope_case(
            (pre, post),
            acquired=acquisition(state=mutex.PaperAccountMutexState.ABANDONED_OWNER),
        )
        with scope as context:
            assert context.acquisition.was_abandoned is True
            assert context.requires_abandoned_owner_reconciliation is True
            assert not hasattr(context, "execute_paper_operation_once")
    finally:
        unregister(pre, post)


def test_context_body_exception_still_releases_through_admission_scope() -> None:
    pre, _ = registered_account(ACCOUNT_ID, "pre")
    post, _ = registered_account(ACCOUNT_ID, "post")
    try:
        scope, events, _ = scope_case((pre, post))
        with pytest.raises(LookupError, match="body"):
            with scope:
                raise LookupError("body")
        assert events[-1] == ("mutex-exit", LookupError)
    finally:
        unregister(pre, post)


def test_public_signature_exposes_no_caller_selected_authority_material() -> None:
    parameters = inspect.signature(
        supervised.supervised_personal_desktop_paper_cycle
    ).parameters
    assert tuple(parameters) == (
        "authority",
        "historical_cycle_configuration_payloads",
    )
    prohibited = {
        "paper_account_id",
        "operation_root",
        "path",
        "mutex_name",
        "sid",
        "native_handle",
        "timeout",
        "checkpoint",
        "lineage_tip",
        "evidence",
    }
    assert prohibited.isdisjoint(parameters)


def test_pd2b1_has_no_architecture_67_mutation_or_external_effect_surface() -> None:
    source = Path(supervised.__file__).read_text(encoding="utf-8")
    imported_modules = {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    assert "execute_paper_operation_once" not in source
    assert "commit_paper_operation_receipt" not in source
    assert not any(
        boundary in module
        for module in imported_modules
        for boundary in ("paper_operation", "provider", "broker", "live")
    )
    assert "open(" not in source
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE is not None
    assert PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE.paper_account_id == ACCOUNT_ID
