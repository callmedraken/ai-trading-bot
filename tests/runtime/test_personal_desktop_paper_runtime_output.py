"""Architecture-107 fixed Paper-v2 runtime output policy coverage."""

from __future__ import annotations

import copy
import inspect
import pickle
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as recovery_execution,
)
from trading_bot.runtime import personal_desktop_paper_runtime_output as output
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as storage_provisioning,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
    AuthoritySecurityError,
)
from trading_bot.runtime.windows_authority_security import (
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
    SecurityAce,
    SecurityInspection,
    SecurityPolicy,
)

SID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
APPLICATION_ID = UUID("78a1bae8-51ac-5bf0-b159-500768c758fc")
OPERATION_ID = UUID("307f769a-f09a-539d-b12d-3fb51b973809")
RESULT_ID = UUID("81000000-0000-0000-0000-000000000001")
SUCCESSOR_ID = UUID("82000000-0000-0000-0000-000000000002")
RUNTIME_POLICY = security.paper_security_policy(
    security.PaperObjectRole.RUNTIME,
    SID,
)


def _observation(
    path: str,
    *,
    identity: tuple[int, int],
    byte_length: int = 0,
) -> security.PaperObjectObservation:
    spec = security.paper_object_spec(path)
    owner = (
        SID
        if spec.role
        in {
            security.PaperObjectRole.OUTPUT_DIRECTORY,
            security.PaperObjectRole.OUTPUT_FILE,
        }
        else None
    )
    policy = security.paper_security_policy(spec.role, SID, owner_sid=owner)
    return security.PaperObjectObservation(
        SecurityInspection(
            path,
            path,
            spec.kind,
            policy.owner_sid,
            policy.dacl_protected,
            policy.aces,
            False,
            "F:\\",
            "NTFS",
        ),
        identity,
        byte_length,
        1,
    )


class FakeNative:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []
        self._next_identity = 10
        self.objects = {
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME: _observation(
                security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
                identity=(1, 1),
            ),
            security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS: _observation(
                security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS,
                identity=(1, 2),
            ),
        }

    def open(self, path: str, kind: AuthorityObjectKind) -> object:
        self.events.append(("open", path, kind))
        if path not in self.objects:
            raise AuthorityObjectError("missing")
        return SimpleNamespace(path=path)

    def close(self, handle: object) -> None:
        self.events.append(("close", handle.path))

    def inspect(
        self, handle: object, path: str, kind: AuthorityObjectKind
    ) -> security.PaperObjectObservation:
        self.events.append(("inspect", path, kind))
        assert handle.path == path
        return self.objects[path]

    def _identity(self) -> tuple[int, int]:
        self._next_identity += 1
        return (1, self._next_identity)

    def create_directory(self, path: str, policy: SecurityPolicy) -> None:
        self.events.append(("create-directory", path, policy))
        assert path not in self.objects
        self.objects[path] = _observation(path, identity=self._identity())

    def write_file(self, path: str, payload: bytes, policy: SecurityPolicy) -> None:
        self.events.append(("write-file", path, payload, policy))
        assert path not in self.objects
        self.objects[path] = _observation(
            path,
            identity=self._identity(),
            byte_length=len(payload),
        )

    def rename_write_through(self, staging: str, final: str) -> None:
        self.events.append(("rename-write-through", staging, final))
        moved: dict[str, security.PaperObjectObservation] = {}
        for path, observation in tuple(self.objects.items()):
            if path == staging or path.startswith(staging + "\\"):
                replacement = final + path[len(staging) :]
                moved[replacement] = replace(
                    observation,
                    security=replace(
                        observation.security,
                        expected_path=replacement,
                        final_path=replacement,
                    ),
                )
                del self.objects[path]
        if not moved:
            raise AuthorityObjectError("missing staging")
        self.objects.update(moved)


def _capability(api: FakeNative):  # type: ignore[no-untyped-def]
    authority = output._open_disposable_paper_runtime_output_authority_for_test()
    return output._open_personal_desktop_paper_runtime_output_capability_for_test(
        api,
        authority=authority,
    )


def _recovery_capability(api: FakeNative):  # type: ignore[no-untyped-def]
    authority = (
        output._open_disposable_paper_receipt_recovery_output_authority_for_test()
    )
    return (
        output._open_personal_desktop_paper_receipt_recovery_output_capability_for_test(
            api,
            authority=authority,
        )
    )


def test_fixed_capability_applies_exact_output_policies_and_reopens_final_names() -> (
    None
):
    api = FakeNative()
    transition = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
        + f"\\.paper-account-transition-{APPLICATION_ID}.staging"
    )
    final = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
        + f"\\paper-account-transition-{APPLICATION_ID}"
    )
    report = transition / f"checkpointed-paper-cycle-report-{RESULT_ID}.json"
    checkpoint = transition / f"paper-account-checkpoint-{SUCCESSOR_ID}.json"

    with _capability(api) as capability:
        capability.create_staging_directory(transition)
        capability.verify_staged_directory(transition)
        capability.write_staged_file(report, b"report")
        capability.verify_staged_file(report)
        capability.write_staged_file(checkpoint, b"checkpoint")
        capability.verify_staged_file(checkpoint)
        capability.finalize_directory(transition, final)
        capability.verify_finalized_directory(final)
        capability.verify_finalized_file(final / report.name)
        capability.verify_finalized_file(final / checkpoint.name)

    policies = [
        event[-1]
        for event in api.events
        if event[0] in {"create-directory", "write-file"}
    ]
    assert policies == [
        security.paper_security_policy(
            security.PaperObjectRole.OUTPUT_DIRECTORY,
            SID,
            owner_sid=SID,
        ),
        security.paper_security_policy(
            security.PaperObjectRole.OUTPUT_FILE,
            SID,
            owner_sid=SID,
        ),
        security.paper_security_policy(
            security.PaperObjectRole.OUTPUT_FILE,
            SID,
            owner_sid=SID,
        ),
    ]
    assert ("rename-write-through", str(transition), str(final)) in api.events
    for policy in policies:
        trading_ace = next(ace for ace in policy.aces if ace.principal_sid == SID)
        assert trading_ace.access_mask & (WRITE_DAC | WRITE_OWNER) == 0


@pytest.mark.parametrize(
    "change",
    [
        {"owner_sid": SID},
        {"dacl_protected": False},
        {"expected_path": r"F:\AITradingBot\Paper-v2\elsewhere"},
        {"kind": AuthorityObjectKind.FILE},
        {"is_reparse_point": True},
        {"filesystem": "ReFS"},
        {"aces": RUNTIME_POLICY.aces + (SecurityAce("S-1-5-32-545", 1),)},
        {
            "aces": (
                replace(RUNTIME_POLICY.aces[0], ace_flags=0x10),
                *RUNTIME_POLICY.aces[1:],
            )
        },
    ],
)
def test_existing_parent_security_path_type_and_reparse_drift_fail_closed(
    change: dict[str, object],
) -> None:
    api = FakeNative()
    path = security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
    observed = api.objects[path]
    api.objects[path] = replace(observed, security=replace(observed.security, **change))
    with pytest.raises((AuthorityObjectError, AuthoritySecurityError)):
        with _capability(api):
            pass


def test_existing_operations_parent_is_required() -> None:
    api = FakeNative()
    del api.objects[security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS]
    with pytest.raises(AuthorityObjectError, match="missing"):
        with _capability(api):
            pass
    assert not any(event[0] == "create-directory" for event in api.events)


@pytest.mark.parametrize(
    ("verification", "path", "byte_length"),
    [
        (
            "verify_staged_directory",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\.paper-account-transition-{APPLICATION_ID}.staging",
            0,
        ),
        (
            "verify_staged_file",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\.paper-account-transition-{APPLICATION_ID}.staging"
            + f"\\checkpointed-paper-cycle-report-{RESULT_ID}.json",
            1,
        ),
        (
            "verify_finalized_directory",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{APPLICATION_ID}",
            0,
        ),
        (
            "verify_finalized_file",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{APPLICATION_ID}"
            + f"\\checkpointed-paper-cycle-report-{RESULT_ID}.json",
            1,
        ),
    ],
)
def test_output_child_requires_exact_trading_owner_during_staged_and_final_checks(
    verification: str,
    path: str,
    byte_length: int,
) -> None:
    api = FakeNative()
    spec = security.paper_object_spec(path)
    policy = security.paper_security_policy(
        spec.role,
        SID,
        owner_sid=security.ADMINISTRATORS_SID,
    )
    api.objects[path] = security.PaperObjectObservation(
        SecurityInspection(
            path,
            path,
            spec.kind,
            policy.owner_sid,
            policy.dacl_protected,
            policy.aces,
            False,
            "F:\\",
            "NTFS",
        ),
        (1, 20),
        byte_length,
        1,
    )

    with _capability(api) as capability:
        with pytest.raises(
            output.PersonalDesktopPaperRuntimeOutputError,
            match="exact Trading SID",
        ):
            getattr(capability, verification)(Path(path))


def test_disposable_runtime_output_authority_is_issuer_bound_and_one_shot() -> None:
    with pytest.raises(TypeError, match="test issuer"):
        output._DisposablePaperRuntimeOutputAuthorityForTest()

    authority = output._open_disposable_paper_runtime_output_authority_for_test()
    with output._open_personal_desktop_paper_runtime_output_capability_for_test(
        FakeNative(),
        authority=authority,
    ):
        pass

    with pytest.raises(TypeError, match="consumed"):
        output._open_personal_desktop_paper_runtime_output_capability_for_test(
            FakeNative(),
            authority=authority,
        )


def test_disposable_runtime_output_authority_cannot_be_copied_or_pickled() -> None:
    authority = output._open_disposable_paper_runtime_output_authority_for_test()

    with pytest.raises(TypeError, match="cannot be copied"):
        copy.copy(authority)
    with pytest.raises(TypeError, match="cannot be deep-copied"):
        copy.deepcopy(authority)
    with pytest.raises(TypeError, match="cannot be pickled"):
        pickle.dumps(authority)


def test_disposable_seam_rejects_genuine_native_without_initialization_or_effect() -> (
    None
):
    class NativeSubclass(output._WindowsPaperRuntimeOutputNativeApi):
        pass

    for native_type in (output._WindowsPaperRuntimeOutputNativeApi, NativeSubclass):
        native = object.__new__(native_type)
        authority = output._open_disposable_paper_runtime_output_authority_for_test()

        with pytest.raises(
            TypeError,
            match="genuine production native implementation",
        ):
            output._open_personal_desktop_paper_runtime_output_capability_for_test(
                native,
                authority=authority,
            )

        assert not hasattr(native, "_kernel")
        with output._open_personal_desktop_paper_runtime_output_capability_for_test(
            FakeNative(),
            authority=authority,
        ):
            pass


def test_alternate_output_path_and_kind_are_rejected_before_native_create() -> None:
    api = FakeNative()
    with _capability(api) as capability:
        with pytest.raises(AuthorityPathError):
            capability.create_staging_directory(
                Path(r"F:\AITradingBot\Paper-v2\runtime\alternate")
            )
        with pytest.raises(AuthorityPathError):
            capability.write_staged_file(
                Path(
                    security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
                    + f"\\paper-account-transition-{APPLICATION_ID}"
                ),
                b"x",
            )
    assert not any(
        event[0] in {"create-directory", "write-file"} for event in api.events
    )


def test_uncertain_native_finalization_is_consumed_without_retry() -> None:
    class UncertainNative(FakeNative):
        def rename_write_through(self, staging: str, final: str) -> None:
            self.events.append(("rename-write-through", staging, final))
            raise RuntimeError("response lost")

    api = UncertainNative()
    staging = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\.paper-operation-{OPERATION_ID}.staging"
    )
    final = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\paper-operation-{OPERATION_ID}"
    )
    with _capability(api) as capability:
        with pytest.raises(RuntimeError, match="response lost"):
            capability.finalize_directory(staging, final)
        with pytest.raises(
            output.PersonalDesktopPaperRuntimeOutputError,
            match="already consumed",
        ):
            capability.finalize_directory(staging, final)
    assert sum(event[0] == "rename-write-through" for event in api.events) == 1


@pytest.mark.parametrize(
    ("staging", "final"),
    [
        (
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{APPLICATION_ID}",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{APPLICATION_ID}",
        ),
        (
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\.paper-account-transition-{APPLICATION_ID}.staging",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{UUID(int=99)}",
        ),
        (
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\.paper-account-transition-{APPLICATION_ID}.staging",
            security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
            + f"\\paper-operation-{OPERATION_ID}",
        ),
    ],
)
def test_finalizer_rejects_wrong_or_cross_parent_names(
    staging: str,
    final: str,
) -> None:
    api = FakeNative()
    with _capability(api) as capability:
        with pytest.raises(AuthorityPathError):
            capability.finalize_directory(Path(staging), Path(final))
    assert not any(event[0] == "rename-write-through" for event in api.events)


def test_native_finalizer_uses_write_through_only() -> None:
    calls: list[tuple[str, str, int]] = []

    class Move:
        argtypes = None
        restype = None

        def __call__(self, staging: str, final: str, flags: int) -> int:
            calls.append((staging, final, flags))
            return 1

    native = object.__new__(output._WindowsPaperRuntimeOutputNativeApi)
    native._kernel = SimpleNamespace(MoveFileExW=Move())
    staging = (
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
        + f"\\.paper-account-transition-{APPLICATION_ID}.staging"
    )
    final = (
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
        + f"\\paper-account-transition-{APPLICATION_ID}"
    )
    native.rename_write_through(staging, final)
    assert calls == [(staging, final, 0x8)]


def test_production_factory_exposes_no_root_or_sid_override_and_gate_is_false() -> None:
    assert (
        tuple(
            inspect.signature(
                output.open_personal_desktop_paper_runtime_output_capability
            ).parameters
        )
        == ()
    )
    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError,
        match="effect-gate state is invalid",
    ):
        output.open_personal_desktop_paper_runtime_output_capability()


def test_receipt_recovery_capability_allows_only_exact_receipt_commit_layout() -> None:
    api = FakeNative()
    staging = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\.paper-operation-{OPERATION_ID}.staging"
    )
    final = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\paper-operation-{OPERATION_ID}"
    )
    receipt_name = f"paper-operation-receipt-{OPERATION_ID}.json"

    with _recovery_capability(api) as capability:
        capability.verify_parent(Path(security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME))
        capability.verify_parent(Path(security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS))
        capability.create_staging_directory(staging)
        capability.verify_staged_directory(staging)
        capability.write_staged_file(staging / receipt_name, b"receipt")
        capability.verify_staged_file(staging / receipt_name)
        capability.finalize_directory(staging, final)
        capability.verify_finalized_directory(final)
        capability.verify_finalized_file(final / receipt_name)

    assert ("rename-write-through", str(staging), str(final)) in api.events
    policies = [
        event[-1]
        for event in api.events
        if event[0] in {"create-directory", "write-file"}
    ]
    assert [policy.owner_sid for policy in policies] == [SID, SID]
    assert all(policy.dacl_protected for policy in policies)
    assert all(
        next(ace for ace in policy.aces if ace.principal_sid == SID).access_mask
        & (WRITE_DAC | WRITE_OWNER)
        == 0
        for policy in policies
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        (
            "create_staging_directory",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\.paper-account-transition-{APPLICATION_ID}.staging",
        ),
        (
            "verify_finalized_directory",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{APPLICATION_ID}",
        ),
    ],
)
def test_receipt_recovery_capability_rejects_transition_directories(
    method: str, path: str
) -> None:
    api = FakeNative()
    with _recovery_capability(api) as capability:
        with pytest.raises(AuthorityPathError):
            getattr(capability, method)(Path(path))
    assert not any(
        event[0] in {"create-directory", "write-file", "rename-write-through"}
        for event in api.events
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        (
            "write_staged_file",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\.paper-account-transition-{APPLICATION_ID}.staging"
            + f"\\checkpointed-paper-cycle-report-{RESULT_ID}.json",
        ),
        (
            "verify_staged_file",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\.paper-account-transition-{APPLICATION_ID}.staging"
            + f"\\paper-account-checkpoint-{SUCCESSOR_ID}.json",
        ),
        (
            "verify_finalized_file",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{APPLICATION_ID}"
            + f"\\checkpointed-paper-cycle-report-{RESULT_ID}.json",
        ),
        (
            "verify_finalized_file",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + f"\\paper-account-transition-{APPLICATION_ID}"
            + f"\\paper-account-checkpoint-{SUCCESSOR_ID}.json",
        ),
    ],
)
def test_receipt_recovery_capability_rejects_all_transition_files(
    method: str, path: str
) -> None:
    api = FakeNative()
    with _recovery_capability(api) as capability:
        with pytest.raises(AuthorityPathError):
            if method == "write_staged_file":
                getattr(capability, method)(Path(path), b"forbidden")
            else:
                getattr(capability, method)(Path(path))
    assert not any(
        event[0] in {"create-directory", "write-file", "rename-write-through"}
        for event in api.events
    )


@pytest.mark.parametrize(
    "path",
    [
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\.paper-operation-{UUID(int=99)}.staging"
        + f"\\paper-operation-receipt-{OPERATION_ID}.json",
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\.PAPER-operation-{OPERATION_ID}.staging"
        + f"\\paper-operation-receipt-{OPERATION_ID}.json",
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
        + f"\\.paper-operation-{OPERATION_ID}.staging"
        + f"\\paper-operation-receipt-{OPERATION_ID}.json",
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\.paper-operation-{OPERATION_ID}.staging"
        + f"\\paper-operation-receipt-{str(OPERATION_ID).upper()}.json",
    ],
)
def test_receipt_recovery_capability_rejects_wrong_uuid_case_or_parent(
    path: str,
) -> None:
    api = FakeNative()
    with _recovery_capability(api) as capability:
        with pytest.raises(AuthorityPathError):
            capability.write_staged_file(Path(path), b"forbidden")
    assert not any(event[0] == "write-file" for event in api.events)


def test_receipt_recovery_finalization_requires_same_exact_uuid() -> None:
    api = FakeNative()
    staging = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\.paper-operation-{OPERATION_ID}.staging"
    )
    wrong_final = Path(
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\paper-operation-{UUID(int=99)}"
    )
    with _recovery_capability(api) as capability:
        with pytest.raises(AuthorityPathError, match="identities"):
            capability.finalize_directory(staging, wrong_final)
    assert not any(event[0] == "rename-write-through" for event in api.events)


def test_receipt_recovery_capability_is_one_shot() -> None:
    api = FakeNative()
    authority = (
        output._open_disposable_paper_receipt_recovery_output_authority_for_test()
    )
    capability = (
        output._open_personal_desktop_paper_receipt_recovery_output_capability_for_test(
            api,
            authority=authority,
        )
    )
    with capability:
        pass
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError, match="one-shot"):
        with capability:
            pass
    with pytest.raises(TypeError, match="consumed"):
        output._open_personal_desktop_paper_receipt_recovery_output_capability_for_test(
            FakeNative(),
            authority=authority,
        )


def test_receipt_recovery_parent_identity_drift_blocks() -> None:
    api = FakeNative()
    with _recovery_capability(api) as capability:
        path = security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        original = api.objects[path]
        try:
            api.objects[path] = replace(original, identity=(9, 9))
            with pytest.raises(
                output.PersonalDesktopPaperRuntimeOutputError, match="parent changed"
            ):
                capability.verify_parent(Path(path))
        finally:
            api.objects[path] = original


def test_receipt_recovery_parent_security_drift_blocks() -> None:
    api = FakeNative()
    with _recovery_capability(api) as capability:
        path = security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        original = api.objects[path]
        try:
            api.objects[path] = replace(
                original,
                security=replace(original.security, dacl_protected=False),
            )
            with pytest.raises(AuthoritySecurityError):
                capability.verify_parent(Path(path))
        finally:
            api.objects[path] = original


def test_receipt_recovery_child_requires_exact_trading_owner_and_acl() -> None:
    api = FakeNative()
    path = (
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS
        + f"\\.paper-operation-{OPERATION_ID}.staging"
    )
    spec = security.paper_object_spec(path)
    policy = security.paper_security_policy(
        spec.role,
        SID,
        owner_sid=security.ADMINISTRATORS_SID,
    )
    api.objects[path] = security.PaperObjectObservation(
        SecurityInspection(
            path,
            path,
            spec.kind,
            policy.owner_sid,
            policy.dacl_protected,
            policy.aces,
            False,
            "F:\\",
            "NTFS",
        ),
        (1, 20),
        0,
        1,
    )
    with _recovery_capability(api) as capability:
        with pytest.raises(
            output.PersonalDesktopPaperRuntimeOutputError,
            match="exact Trading SID",
        ):
            capability.verify_staged_directory(Path(path))


def test_receipt_recovery_gate_is_false_and_production_opener_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        recovery_execution.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        tuple(
            inspect.signature(
                output.open_personal_desktop_paper_receipt_recovery_output_capability
            ).parameters
        )
        == ()
    )

    def forbidden_native() -> None:
        pytest.fail("disabled receipt-recovery opener constructed native output")

    monkeypatch.setattr(output, "_WindowsPaperRuntimeOutputNativeApi", forbidden_native)
    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError,
        match="receipt-recovery output effect-gate state is invalid",
    ):
        output.open_personal_desktop_paper_receipt_recovery_output_capability()


def test_disposable_receipt_authority_cannot_enter_production_opener() -> None:
    authority = (
        output._open_disposable_paper_receipt_recovery_output_authority_for_test()
    )
    assert (
        "authority"
        not in inspect.signature(
            output.open_personal_desktop_paper_receipt_recovery_output_capability
        ).parameters
    )
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError):
        output.open_personal_desktop_paper_receipt_recovery_output_capability()
    with (
        output._open_personal_desktop_paper_receipt_recovery_output_capability_for_test(
            FakeNative(),
            authority=authority,
        )
    ):
        pass


def test_disposable_receipt_seam_rejects_genuine_native() -> None:
    native = object.__new__(output._WindowsPaperRuntimeOutputNativeApi)
    authority = (
        output._open_disposable_paper_receipt_recovery_output_authority_for_test()
    )
    with pytest.raises(TypeError, match="genuine production native implementation"):
        output._open_personal_desktop_paper_receipt_recovery_output_capability_for_test(
            native,
            authority=authority,
        )
    with (
        output._open_personal_desktop_paper_receipt_recovery_output_capability_for_test(
            FakeNative(),
            authority=authority,
        )
    ):
        pass


@pytest.mark.parametrize("capability_factory", (_capability, _recovery_capability))
def test_existing_output_capabilities_cannot_mutate_unattended_namespace(
    capability_factory,  # type: ignore[no-untyped-def]
) -> None:
    api = FakeNative()
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
    staging = Path(parent + f"\\.unattended-paper-invocation-{OPERATION_ID}.staging")
    final = Path(parent + f"\\unattended-paper-invocation-{OPERATION_ID}")
    artifact = staging / (
        f"personal-desktop-unattended-paper-invocation-{OPERATION_ID}.json"
    )

    with capability_factory(api) as capability:
        with pytest.raises(AuthorityPathError):
            capability.create_staging_directory(staging)
        with pytest.raises(AuthorityPathError):
            capability.write_staged_file(artifact, b"forbidden")
        with pytest.raises(AuthorityPathError):
            capability.finalize_directory(staging, final)

    assert not any(
        event[0] in {"create-directory", "write-file", "rename-write-through"}
        for event in api.events
    )


def test_unattended_a67_opener_accepts_only_exact_unattended_six_gate_state(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        output, "_WindowsPaperRuntimeOutputNativeApi", lambda: FakeNative()
    )

    def set_gates(state):  # type: ignore[no-untyped-def]
        publication, recovery, supervised, receipt, unattended, provisioning = state
        monkeypatch.setattr(
            security,
            "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED",
            publication,
        )
        monkeypatch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", recovery
        )
        monkeypatch.setattr(
            supervised_execution,
            "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
            supervised,
        )
        monkeypatch.setattr(
            recovery_execution,
            "PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED",
            receipt,
        )
        monkeypatch.setattr(
            unattended_execution,
            "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED",
            unattended,
        )
        monkeypatch.setattr(
            storage_provisioning,
            "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED",
            provisioning,
        )

    set_gates((False, False, False, False, True, False))
    capability = (
        output.open_personal_desktop_unattended_paper_runtime_output_capability()
    )
    assert type(capability) is output._PersonalDesktopPaperRuntimeOutputCapability

    invalid_states = [
        (False, False, False, False, False, False),
        (True, False, False, False, True, False),
        (False, True, False, False, True, False),
        (False, False, True, False, True, False),
        (False, False, False, True, True, False),
        (False, False, False, False, True, True),
    ]
    for state in invalid_states:
        set_gates(state)
        with pytest.raises(
            output.PersonalDesktopPaperRuntimeOutputError,
            match="effect-gate state is invalid",
        ):
            output.open_personal_desktop_unattended_paper_runtime_output_capability()
