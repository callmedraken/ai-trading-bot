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
from trading_bot.runtime import personal_desktop_paper_runtime_output as output
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
