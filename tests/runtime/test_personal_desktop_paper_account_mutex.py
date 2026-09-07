from __future__ import annotations

import ctypes
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.runtime import personal_desktop_paper_account_mutex as mutex
from trading_bot.runtime import personal_desktop_paper_account_read_authority as reader
from trading_bot.runtime import (
    personal_desktop_paper_account_security as paper_security,
)
from trading_bot.runtime.personal_desktop_paper_account_publication_freeze import (
    PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE,
)
from trading_bot.runtime.windows_authority_security import (
    MUTEX_ALL_ACCESS,
    MUTEX_MODIFY_STATE,
    READ_CONTROL,
    SYNCHRONIZE,
    SecurityAce,
)

ACCOUNT_ID = "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
OTHER_ACCOUNT_ID = "1dbbe770-9587-40cb-9762-7fa13654df5e"
POISONED_RELEASE_ACCOUNT_ID = "7560de7c-dd3f-4f7b-bd03-d4fdd7890aa1"
TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
EXPECTED_MATERIAL = (
    b"39:personal-desktop-paper-account-mutex/v136:9415cd7b-bf36-5fba-bd58-a0f99119dc21"
)
EXPECTED_DIGEST = "6b8a5c4447683d4a814a19e02f8c7adf74603b4f9d02808d99b8b1a06efc4a20"
EXPECTED_NAME = "Global\\AITradingBot-PaperAccount-v1-" + EXPECTED_DIGEST


class FakeNativeApi:
    def __init__(
        self,
        *,
        wait_result: int = mutex.WAIT_OBJECT_0,
        creator_owner: str = TRADING_SID,
        inspected_owner: str | None = None,
        protected: bool = True,
        aces: tuple[SecurityAce, ...] | None = None,
        release_result: bool = True,
        inspect_error: BaseException | None = None,
    ) -> None:
        self.wait_result = wait_result
        self.creator_owner = creator_owner
        self.inspected_owner = inspected_owner or creator_owner
        self.protected = protected
        self.aces = aces
        self.release_result = release_result
        self.inspect_error = inspect_error
        self.events: list[object] = []
        self.created_name: str | None = None
        self.created_policy = None

    def creator_owner_sid(
        self, trading_sid: str, *, allow_elevated_administrator: bool
    ) -> str:
        self.events.append(("creator", trading_sid, allow_elevated_administrator))
        return self.creator_owner

    def create_mutex(self, name: str, policy) -> int:  # type: ignore[no-untyped-def]
        self.events.append("create")
        self.created_name = name
        self.created_policy = policy
        return 41

    def inspect_mutex(self, handle: int) -> tuple[str, bool, tuple[SecurityAce, ...]]:
        self.events.append("inspect")
        if self.inspect_error is not None:
            raise self.inspect_error
        aces = self.aces
        if aces is None:
            aces = mutex.paper_account_mutex_security_policy(
                TRADING_SID, owner_sid=self.inspected_owner
            ).aces
        return self.inspected_owner, self.protected, aces

    def wait(self, handle: int, milliseconds: int) -> int:
        self.events.append(("wait", milliseconds))
        return self.wait_result

    def release(self, handle: int) -> bool:
        self.events.append("release")
        return self.release_result

    def close(self, handle: int) -> None:
        self.events.append("close")


def scope(
    api: FakeNativeApi,
    account_id: str = ACCOUNT_ID,
    *,
    allow_admin: bool = False,
) -> mutex._PaperAccountMutex:
    return mutex._PaperAccountMutex(
        account_id,
        TRADING_SID,
        _api=api,
        _allow_elevated_administrative_creator=allow_admin,
    )


def registered_authority():  # type: ignore[no-untyped-def]
    authority = object.__new__(reader.ValidatedPersonalDesktopPaperAccount)
    evidence = SimpleNamespace(
        anchor=SimpleNamespace(
            paper_account_id=ACCOUNT_ID, approved_trading_sid=TRADING_SID
        )
    )
    with reader._REGISTRY_LOCK:
        reader._REGISTRY[authority] = evidence  # type: ignore[assignment]
    return authority


def unregister(authority) -> None:  # type: ignore[no-untyped-def]
    with reader._REGISTRY_LOCK:
        reader._REGISTRY.pop(authority, None)


def test_exact_framed_identity_digest_and_name() -> None:
    assert mutex.PAPER_ACCOUNT_MUTEX_LABEL == (
        "personal-desktop-paper-account-mutex/v1"
    )
    assert mutex.PAPER_ACCOUNT_MUTEX_PREFIX == ("Global\\AITradingBot-PaperAccount-v1-")
    assert mutex.canonical_paper_account_mutex_material(ACCOUNT_ID) == EXPECTED_MATERIAL
    assert mutex.paper_account_mutex_digest(ACCOUNT_ID) == EXPECTED_DIGEST
    assert mutex.paper_account_mutex_name(ACCOUNT_ID) == EXPECTED_NAME


@pytest.mark.parametrize(
    "value",
    [
        "not-a-uuid",
        "9415CD7B-BF36-5FBA-BD58-A0F99119DC21",
        "{9415cd7b-bf36-5fba-bd58-a0f99119dc21}",
        "9415cd7bbf365fbabd58a0f99119dc21",
    ],
)
def test_malformed_or_noncanonical_account_id_is_rejected(value: str) -> None:
    with pytest.raises(mutex.PaperAccountMutexError, match="canonical"):
        mutex.canonical_paper_account_mutex_material(value)


def test_identity_is_account_scoped_and_deterministic() -> None:
    assert mutex.paper_account_mutex_name(ACCOUNT_ID) == mutex.paper_account_mutex_name(
        ACCOUNT_ID
    )
    assert mutex.paper_account_mutex_name(ACCOUNT_ID) != mutex.paper_account_mutex_name(
        OTHER_ACCOUNT_ID
    )


def test_no_mutex_name_timeout_or_handle_is_caller_supplied() -> None:
    signature = inspect.signature(mutex.supervised_paper_cycle_admission)
    assert tuple(signature.parameters) == ("authority",)
    low_level = inspect.signature(mutex._PaperAccountMutex)
    assert "name" not in low_level.parameters
    assert "timeout" not in low_level.parameters
    assert "handle" not in low_level.parameters


def test_windows_native_create_requests_only_exact_mutex_rights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeFunction:
        argtypes: object
        restype: object

        def __init__(self, name: str, result: object) -> None:
            self.name = name
            self.result = result

        def __call__(self, *args: object) -> object:
            calls.append((self.name, args))
            return self.result

    class FakeKernel32:
        CreateMutexExW = FakeFunction("CreateMutexExW", ctypes.c_void_p(41))
        WaitForSingleObject = FakeFunction("WaitForSingleObject", mutex.WAIT_OBJECT_0)
        ReleaseMutex = FakeFunction("ReleaseMutex", True)
        CloseHandle = FakeFunction("CloseHandle", True)

    class FakeAttributes:
        attributes = ctypes.c_int()

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(mutex, "require_windows_platform", lambda: None)
    monkeypatch.setattr(
        mutex, "build_security_attributes", lambda policy: FakeAttributes()
    )
    monkeypatch.setattr(
        mutex.ctypes,
        "WinDLL",
        lambda name, use_last_error: FakeKernel32(),
        raising=False,
    )
    api = mutex._WindowsPaperAccountMutexNativeApi()
    policy = mutex.paper_account_mutex_security_policy(
        TRADING_SID, owner_sid=TRADING_SID
    )
    assert api.create_mutex(EXPECTED_NAME, policy) == 41
    create_args = next(args for name, args in calls if name == "CreateMutexExW")
    assert create_args[1:] == (
        EXPECTED_NAME,
        0,
        MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE,
    )


def test_windows_native_creator_owner_selection_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = mutex._WindowsPaperAccountMutexNativeApi()
    monkeypatch.setattr(mutex, "require_windows_platform", lambda: None)
    monkeypatch.setattr(mutex, "resolve_current_token_sid", lambda: TRADING_SID)
    assert (
        api.creator_owner_sid(TRADING_SID, allow_elevated_administrator=False)
        == TRADING_SID
    )
    monkeypatch.setattr(
        mutex, "resolve_current_token_sid", lambda: mutex.ADMINISTRATORS_SID
    )
    monkeypatch.setattr(mutex, "is_current_token_elevated", lambda: True)
    monkeypatch.setattr(mutex, "is_current_token_administrator", lambda: True)
    with pytest.raises(mutex.PaperAccountMutexSecurityError):
        api.creator_owner_sid(TRADING_SID, allow_elevated_administrator=False)
    assert (
        api.creator_owner_sid(TRADING_SID, allow_elevated_administrator=True)
        == mutex.ADMINISTRATORS_SID
    )


def test_fixed_bounded_wait_and_owned_evidence() -> None:
    api = FakeNativeApi()
    acquired_scope = scope(api)
    evidence = acquired_scope.acquire()
    try:
        assert mutex.PAPER_ACCOUNT_MUTEX_WAIT_MILLISECONDS == 30_000
        assert mutex.PAPER_ACCOUNT_MUTEX_WAIT_MILLISECONDS != mutex.INFINITE
        assert ("wait", 30_000) in api.events
        assert evidence == mutex.PaperAccountMutexAcquisition(
            ACCOUNT_ID,
            EXPECTED_NAME,
            EXPECTED_DIGEST,
            mutex.PaperAccountMutexState.OWNED,
        )
        assert evidence.was_abandoned is False
    finally:
        acquired_scope.release()


@pytest.mark.parametrize(
    ("wait_result", "error_type"),
    [
        (mutex.WAIT_TIMEOUT, mutex.PaperAccountMutexBusyError),
        (mutex.WAIT_FAILED, mutex.PaperAccountMutexWaitError),
        (7, mutex.PaperAccountMutexWaitError),
    ],
)
def test_nonownership_wait_results_fail_closed_and_close_without_release(
    wait_result: int, error_type: type[BaseException]
) -> None:
    api = FakeNativeApi(wait_result=wait_result)
    with pytest.raises(error_type):
        scope(api).acquire()
    assert api.events[-1] == "close"
    assert "release" not in api.events


def test_abandoned_owner_is_preserved_as_distinct_owned_evidence() -> None:
    api = FakeNativeApi(wait_result=mutex.WAIT_ABANDONED_0)
    acquired_scope = scope(api)
    evidence = acquired_scope.acquire()
    try:
        assert evidence.state is mutex.PaperAccountMutexState.ABANDONED_OWNER
        assert evidence.was_abandoned is True
    finally:
        acquired_scope.release()
    assert api.events[-2:] == ["release", "close"]


@pytest.mark.parametrize(
    ("owner", "allow_admin"),
    [
        (TRADING_SID, False),
        (mutex.SYSTEM_SID, False),
        (mutex.ADMINISTRATORS_SID, True),
    ],
)
def test_exact_reviewed_owner_and_dacl_policies_are_accepted(
    owner: str, allow_admin: bool
) -> None:
    api = FakeNativeApi(creator_owner=owner)
    with scope(api, allow_admin=allow_admin):
        pass
    assert api.created_policy.owner_sid == owner
    assert api.created_policy.dacl_protected is True
    assert api.created_policy.aces == (
        SecurityAce(mutex.ADMINISTRATORS_SID, MUTEX_ALL_ACCESS),
        SecurityAce(mutex.SYSTEM_SID, MUTEX_ALL_ACCESS),
        SecurityAce(TRADING_SID, MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE),
    )


def test_administrator_owner_requires_explicit_diagnostic_allowance() -> None:
    api = FakeNativeApi(creator_owner=mutex.ADMINISTRATORS_SID)
    with pytest.raises(mutex.PaperAccountMutexSecurityError):
        scope(api).acquire()
    assert "create" not in api.events


@pytest.mark.parametrize(
    ("owner", "protected", "aces"),
    [
        ("S-1-5-21-1-2-3-999", True, None),
        (TRADING_SID, False, None),
        (
            TRADING_SID,
            True,
            (SecurityAce(mutex.ADMINISTRATORS_SID, MUTEX_ALL_ACCESS),),
        ),
        (
            TRADING_SID,
            True,
            mutex.paper_account_mutex_security_policy(
                TRADING_SID, owner_sid=TRADING_SID
            ).aces
            + (SecurityAce("S-1-5-21-1-2-3-999", READ_CONTROL),),
        ),
    ],
)
def test_outsider_owner_unprotected_and_nonexact_aces_fail_closed(
    owner: str, protected: bool, aces: tuple[SecurityAce, ...] | None
) -> None:
    api = FakeNativeApi(inspected_owner=owner, protected=protected, aces=aces)
    with pytest.raises(mutex.PaperAccountMutexSecurityError):
        scope(api).acquire()
    assert api.events[-1] == "close"
    assert not any(
        isinstance(event, tuple) and event[0] == "wait" for event in api.events
    )


def test_security_inspection_failure_closes_before_any_wait() -> None:
    api = FakeNativeApi(
        inspect_error=mutex.PaperAccountMutexSecurityError("inspection failed")
    )
    with pytest.raises(mutex.PaperAccountMutexSecurityError, match="inspection"):
        scope(api).acquire()
    assert api.events == [
        ("creator", TRADING_SID, False),
        "create",
        "inspect",
        "close",
    ]


def test_duplicate_acquire_on_one_scope_is_rejected() -> None:
    api = FakeNativeApi()
    acquired_scope = scope(api)
    acquired_scope.acquire()
    try:
        with pytest.raises(mutex.PaperAccountMutexReentrantError):
            acquired_scope.acquire()
        assert api.events.count("create") == 1
    finally:
        acquired_scope.release()


def test_second_active_same_account_scope_cannot_use_win32_recursive_ownership() -> (
    None
):
    first_api = FakeNativeApi()
    second_api = FakeNativeApi()
    first = scope(first_api)
    first.acquire()
    try:
        with pytest.raises(mutex.PaperAccountMutexReentrantError, match="in-process"):
            scope(second_api).acquire()
        assert second_api.events == []
    finally:
        first.release()


def test_different_account_mutex_scopes_remain_independent() -> None:
    first, second = scope(FakeNativeApi()), scope(FakeNativeApi(), OTHER_ACCOUNT_ID)
    first.acquire()
    try:
        second.acquire()
        second.release()
    finally:
        first.release()


def test_release_only_when_owned_and_handle_always_closes() -> None:
    timeout_api = FakeNativeApi(wait_result=mutex.WAIT_TIMEOUT)
    with pytest.raises(mutex.PaperAccountMutexBusyError):
        scope(timeout_api).acquire()
    assert "release" not in timeout_api.events
    owned_api = FakeNativeApi()
    acquired_scope = scope(owned_api)
    acquired_scope.acquire()
    acquired_scope.release()
    assert owned_api.events[-2:] == ["release", "close"]


def test_release_failure_closes_and_permanently_poisons_only_that_account() -> None:
    api = FakeNativeApi(release_result=False)
    acquired_scope = scope(api, POISONED_RELEASE_ACCOUNT_ID)
    acquired_scope.acquire()
    with pytest.raises(mutex.PaperAccountMutexReleaseError):
        acquired_scope.release()
    assert api.events[-2:] == ["release", "close"]

    events_after_failure = list(api.events)
    acquired_scope.release()
    assert api.events == events_after_failure

    retry_api = FakeNativeApi()
    with pytest.raises(mutex.PaperAccountMutexPoisonedError, match="uncertain"):
        scope(retry_api, POISONED_RELEASE_ACCOUNT_ID).acquire()
    assert retry_api.events == []

    independent_api = FakeNativeApi()
    with scope(independent_api, OTHER_ACCOUNT_ID):
        pass
    assert independent_api.events[-2:] == ["release", "close"]


def test_successful_release_allows_later_same_account_acquisition() -> None:
    first_api = FakeNativeApi()
    with scope(first_api):
        pass

    second_api = FakeNativeApi()
    with scope(second_api):
        pass
    assert second_api.events == [
        ("creator", TRADING_SID, False),
        "create",
        "inspect",
        ("wait", 30_000),
        "release",
        "close",
    ]


def test_context_manager_closes_on_success_and_body_exception() -> None:
    success_api = FakeNativeApi()
    with scope(success_api):
        pass
    assert success_api.events[-2:] == ["release", "close"]
    exception_api = FakeNativeApi()
    with pytest.raises(LookupError, match="body"):
        with scope(exception_api):
            raise LookupError("body")
    assert exception_api.events[-2:] == ["release", "close"]


def test_supervised_admission_uses_only_registered_authority_account_identity() -> None:
    authority = registered_authority()
    api = FakeNativeApi()
    try:
        admission = mutex._supervised_paper_cycle_admission(authority, api=api)
        with admission:
            assert admission.acquisition is not None
            assert admission.acquisition.paper_account_id == ACCOUNT_ID
            assert admission.acquisition.name == EXPECTED_NAME
        assert api.created_name == EXPECTED_NAME
    finally:
        unregister(authority)


def test_arbitrary_or_unregistered_objects_cannot_mint_admission() -> None:
    api = FakeNativeApi()
    with pytest.raises(
        reader.PersonalDesktopPaperAccountError, match="production read provenance"
    ):
        mutex._supervised_paper_cycle_admission(object(), api=api)  # type: ignore[arg-type]
    forged = object.__new__(reader.ValidatedPersonalDesktopPaperAccount)
    with pytest.raises(
        reader.PersonalDesktopPaperAccountError, match="production read provenance"
    ):
        mutex._supervised_paper_cycle_admission(forged, api=api)
    with pytest.raises(mutex.PaperAccountMutexError, match="registered"):
        mutex.SupervisedPaperCycleAdmission(scope(api), _key=object())
    assert api.events == []


def test_admission_has_no_filesystem_or_architecture_67_effect() -> None:
    authority = registered_authority()
    api = FakeNativeApi()
    try:
        with mutex._supervised_paper_cycle_admission(authority, api=api):
            pass
    finally:
        unregister(authority)
    assert api.events == [
        ("creator", TRADING_SID, False),
        "create",
        "inspect",
        ("wait", 30_000),
        "release",
        "close",
    ]
    source = Path(mutex.__file__).read_text(encoding="utf-8")
    assert "paper_operation import" not in source
    assert "PERSONAL_DESKTOP_PAPER_V2_ROOT" not in source
    assert "open(" not in source


def test_effect_gates_remain_false_and_publication_freeze_is_unchanged() -> None:
    assert paper_security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert paper_security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE is not None
    assert PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE.paper_account_id == ACCOUNT_ID
