"""Focused PD4-B2 unattended invocation publication containment tests."""

from __future__ import annotations

import copy
import ctypes
import inspect
import pickle
from dataclasses import FrozenInstanceError, fields, replace
from types import SimpleNamespace

import pytest
from tests.market_data.daily_snapshot_test_support import calendar
from tests.runtime.test_personal_desktop_paper_account_security import (
    SID as STORAGE_SID,
)
from tests.runtime.test_personal_desktop_paper_account_security import (
    MemoryReadApi,
)
from tests.runtime.test_personal_desktop_unattended_paper_invocation_storage import (
    Observer,
    _expected,
    _put_final,
)

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as recovery_execution,
)
from trading_bot.runtime import personal_desktop_paper_runtime_output as output
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised_execution,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_invocation_storage as storage,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended_execution,
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
    SecurityInspection,
    SecurityPolicy,
)

from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)

SID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid


@pytest.fixture(autouse=True)
def block_real_native(monkeypatch, prohibit_production_effects):
    def forbidden(*_args, **_kwargs):
        pytest.fail("PD4-B2 tests must never load a native DLL")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)


def _observation(
    path: str,
    identity: tuple[int, int],
    *,
    byte_length: int = 0,
) -> security.PaperObjectObservation:
    spec = security.paper_object_spec(path)
    owner = (
        SID
        if spec.role
        in {
            security.PaperObjectRole.UNATTENDED_INVOCATION_DIRECTORY,
            security.PaperObjectRole.UNATTENDED_INVOCATION_FILE,
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
    """In-memory exact-name writer with no filesystem or cleanup primitive."""

    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []
        self.objects: dict[
            str, tuple[security.PaperObjectObservation, bytes | None]
        ] = {
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME: (
                _observation(security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME, (7, 1)),
                None,
            ),
            security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS: (
                _observation(
                    security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
                    (7, 2),
                ),
                None,
            ),
        }
        self.open_handles: dict[int, object] = {}
        self.next_identity = 20
        self.create_error: BaseException | None = None
        self.write_error: BaseException | None = None
        self.tamper_staged_read = False
        self.tamper_final_read = False
        self.parent_drift_after_write: str | None = None
        self.parent_security_drift_after_write: str | None = None

    def open(self, path: str, kind: AuthorityObjectKind) -> object:
        self.events.append(("open", path, kind))
        if path not in self.objects:
            raise AuthorityObjectError("missing")
        handle = SimpleNamespace(path=path)
        self.open_handles[id(handle)] = handle
        return handle

    def close(self, handle: object) -> None:
        self.events.append(("close", handle.path))
        assert self.open_handles.pop(id(handle)) is handle

    def inspect(
        self, handle: object, path: str, kind: AuthorityObjectKind
    ) -> security.PaperObjectObservation:
        self.events.append(("inspect", path, kind))
        assert handle.path == path
        return self.objects[path][0]

    def create_directory(self, path: str, policy: SecurityPolicy) -> None:
        self.events.append(("create-directory", path, policy))
        if self.create_error is not None:
            raise self.create_error
        assert path not in self.objects
        assert str(path.rsplit("\\", 1)[0]) in self.objects
        self.objects[path] = (_observation(path, self._identity()), None)

    def write_file(self, path: str, payload: bytes, policy: SecurityPolicy) -> None:
        self.events.append(("write-file", path, payload, policy))
        if self.write_error is not None:
            raise self.write_error
        assert path not in self.objects
        assert path.rsplit("\\", 1)[0] in self.objects
        self.objects[path] = (
            _observation(path, self._identity(), byte_length=len(payload)),
            payload,
        )
        if self.parent_drift_after_write is not None:
            observation, parent_payload = self.objects[self.parent_drift_after_write]
            self.objects[self.parent_drift_after_write] = (
                replace(observation, identity=(99, 99)),
                parent_payload,
            )
        if self.parent_security_drift_after_write is not None:
            parent = self.parent_security_drift_after_write
            observation, parent_payload = self.objects[parent]
            self.objects[parent] = (
                replace(
                    observation,
                    security=replace(
                        observation.security,
                        dacl_protected=False,
                    ),
                ),
                parent_payload,
            )

    def read(self, handle: object, maximum: int) -> bytes:
        self.events.append(("read", handle.path, maximum))
        payload = self.objects[handle.path][1]
        assert type(payload) is bytes and len(payload) <= maximum
        if (
            self.tamper_staged_read and ".unattended-paper-invocation-" in handle.path
        ) or (
            self.tamper_final_read
            and "\\unattended-paper-invocation-" in handle.path
            and "\\.unattended-paper-invocation-" not in handle.path
        ):
            return bytes((payload[0] ^ 1,)) + payload[1:]
        return payload

    def rename_unattended_write_through(self, staging: str, final: str) -> None:
        self.events.append(("rename-unattended-write-through", staging, final))
        if final in self.objects:
            raise AuthorityObjectError("no-clobber collision")
        moved: dict[str, tuple[security.PaperObjectObservation, bytes | None]] = {}
        for path, (observation, payload) in tuple(self.objects.items()):
            if path == staging or path.startswith(staging + "\\"):
                replacement = final + path[len(staging) :]
                moved[replacement] = (
                    replace(
                        observation,
                        security=replace(
                            observation.security,
                            expected_path=replacement,
                            final_path=replacement,
                        ),
                    ),
                    payload,
                )
                del self.objects[path]
        if not moved:
            raise AuthorityObjectError("missing staging")
        self.objects.update(moved)

    def rename_write_through(self, staging: str, final: str) -> None:
        pytest.fail(f"unattended capability reached A67 rename: {staging} -> {final}")

    def _identity(self) -> tuple[int, int]:
        self.next_identity += 1
        return (7, self.next_identity)


def _paths(binding):  # type: ignore[no-untyped-def]
    identity = binding.invocation.invocation_id
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
    staging = (
        parent
        + "\\"
        + storage.unattended_paper_invocation_directory_name(identity, staging=True)
    )
    final = parent + "\\" + storage.unattended_paper_invocation_directory_name(identity)
    artifact = storage.unattended_paper_invocation_artifact_name(identity)
    return staging, final, staging + "\\" + artifact, final + "\\" + artifact


def _capability(binding, api):  # type: ignore[no-untyped-def]
    authority = (
        output._open_disposable_unattended_invocation_output_authority_for_test()
    )
    return (
        output._open_personal_desktop_unattended_invocation_output_capability_for_test(
            binding,
            api,
            authority=authority,
        )
    )


def _trusted_storage_read(monkeypatch, binding, *, finalized=False):  # type: ignore[no-untyped-def]
    api = MemoryReadApi()
    api.trading_runtime = True
    if finalized:
        _put_final(api, binding)
    else:
        api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)
    c1 = SimpleNamespace(approved_account_sid=STORAGE_SID)

    def require(authority):  # type: ignore[no-untyped-def]
        assert authority is c1
        return c1

    monkeypatch.setattr(storage, "require_validated_production_authority", require)
    monkeypatch.setattr(output, "require_validated_production_authority", require)
    monkeypatch.setattr(storage, "WindowsTradingTokenObserver", Observer)
    monkeypatch.setattr(storage, "WindowsPaperReadNativeApi", lambda: api)
    monkeypatch.setattr(storage, "BoundMarketCalendar", lambda *_args: calendar())
    result = storage.read_personal_desktop_unattended_invocation_storage(c1, binding)
    assert result.classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL
        if finalized
        else storage.PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
    )
    return result


def test_five_production_effect_gates_are_committed_false() -> None:
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        supervised_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        recovery_execution.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        unattended_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED
        is False
    )


def test_production_opener_accepts_only_one_b1_result_and_rejects_untrusted(
    monkeypatch,
) -> None:
    assert tuple(
        inspect.signature(
            output.open_personal_desktop_unattended_invocation_output_capability
        ).parameters
    ) == ("storage_read_result",)
    binding = _expected()
    constructed = storage.PersonalDesktopUnattendedInvocationStorageReadResult(
        storage.PersonalDesktopUnattendedInvocationStorageClassification.ABSENT,
        binding.invocation.invocation_id,
        0,
        None,
        storage.PersonalDesktopUnattendedInvocationStorageDiagnostic.VERIFIED_ABSENT,
    )
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)
    disposable = storage._read_personal_desktop_unattended_invocation_storage_for_test(
        binding,
        STORAGE_SID,
        api=api,
        observer=Observer(),
        calendar=calendar(),
    )
    monkeypatch.setattr(
        output,
        "_WindowsPaperRuntimeOutputNativeApi",
        lambda: pytest.fail("untrusted B1 evidence constructed a native writer"),
    )
    for result in (constructed, disposable):
        with pytest.raises(storage.PersonalDesktopUnattendedInvocationStorageError):
            output.open_personal_desktop_unattended_invocation_output_capability(result)


def test_finalized_identical_and_disabled_gate_stop_before_native_construction(
    monkeypatch,
) -> None:
    binding = _expected()
    finalized = _trusted_storage_read(monkeypatch, binding, finalized=True)
    monkeypatch.setattr(
        output,
        "_WindowsPaperRuntimeOutputNativeApi",
        lambda: pytest.fail("non-ABSENT B1 evidence constructed a native writer"),
    )
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError, match="ABSENT"):
        output.open_personal_desktop_unattended_invocation_output_capability(finalized)

    absent = _trusted_storage_read(monkeypatch, binding)
    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError,
        match="effect-gate state is invalid",
    ):
        output.open_personal_desktop_unattended_invocation_output_capability(absent)


def test_bound_capability_publishes_exact_names_bytes_policies_and_evidence() -> None:
    binding = _expected()
    api = FakeNative()
    staging, final, staged_artifact, final_artifact = _paths(binding)

    with _capability(binding, api) as capability:
        assert tuple(inspect.signature(capability.publish).parameters) == ()
        result = capability.publish()
        with pytest.raises(
            output.PersonalDesktopPaperRuntimeOutputError, match="already consumed"
        ):
            capability.publish()

    assert api.open_handles == {}
    assert api.objects[final_artifact][1] == binding.artifact_bytes
    assert staging not in api.objects and staged_artifact not in api.objects
    assert ("rename-unattended-write-through", staging, final) in api.events
    assert [event[1] for event in api.events if event[0] == "create-directory"] == [
        staging
    ]
    writes = [event for event in api.events if event[0] == "write-file"]
    assert [(event[1], event[2]) for event in writes] == [
        (staged_artifact, binding.artifact_bytes)
    ]
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
    assert [event[1] for event in api.events if event[0] == "read"] == [
        staged_artifact,
        final_artifact,
    ]
    assert not any(
        security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS in str(value)
        for event in api.events
        for value in event
    )
    for parent in (
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
    ):
        assert (
            sum(event[0] == "open" and event[1] == parent for event in api.events) >= 5
        )
    assert result.invocation_id == binding.invocation.invocation_id
    assert result.artifact_sha256 == binding.artifact_sha256
    assert result.artifact_byte_length == binding.artifact_byte_length
    assert (
        result.staging_created is result.finalized is result.artifact_verified is True
    )
    assert {field.name for field in fields(result)} == {
        "invocation_id",
        "artifact_sha256",
        "artifact_byte_length",
        "staging_created",
        "finalized",
        "artifact_verified",
    }
    with pytest.raises(FrozenInstanceError):
        result.finalized = False
    with pytest.raises(storage.PersonalDesktopUnattendedInvocationStorageError):
        storage.require_validated_personal_desktop_unattended_invocation_storage_read(
            result  # type: ignore[arg-type]
        )


def test_staged_tamper_and_failed_canonical_replay_block_before_rename(
    monkeypatch,
) -> None:
    binding = _expected()
    tampered_api = FakeNative()
    tampered_api.tamper_staged_read = True
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError):
        with _capability(binding, tampered_api) as capability:
            capability.publish()
    staging, final, staged_artifact, _ = _paths(binding)
    assert staging in tampered_api.objects and staged_artifact in tampered_api.objects
    assert final not in tampered_api.objects
    assert not any(
        event[0] == "rename-unattended-write-through" for event in tampered_api.events
    )
    assert tampered_api.open_handles == {}

    replay_api = FakeNative()
    real_verify = output.verify_personal_desktop_unattended_paper_invocation
    calls = 0

    def verify(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("staged canonical replay rejected")
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(
        output, "verify_personal_desktop_unattended_paper_invocation", verify
    )
    with pytest.raises(ValueError, match="canonical replay"):
        with _capability(binding, replay_api) as capability:
            capability.publish()
    assert staging in replay_api.objects and staged_artifact in replay_api.objects
    assert final not in replay_api.objects
    assert not any(
        event[0] == "rename-unattended-write-through" for event in replay_api.events
    )
    assert replay_api.open_handles == {}


def test_tampered_final_read_blocks_success_and_leaves_final_evidence() -> None:
    binding = _expected()
    api = FakeNative()
    api.tamper_final_read = True
    staging, final, staged_artifact, final_artifact = _paths(binding)

    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError, match="bytes differ"
    ):
        with _capability(binding, api) as capability:
            capability.publish()

    assert staging not in api.objects and staged_artifact not in api.objects
    assert final in api.objects and final_artifact in api.objects
    assert api.open_handles == {}


def test_final_canonical_replay_and_security_are_mandatory(monkeypatch) -> None:
    binding = _expected()
    _, final, _, final_artifact = _paths(binding)
    real_verify = output.verify_personal_desktop_unattended_paper_invocation
    calls = 0

    def reject_final_replay(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ValueError("final canonical replay rejected")
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(
        output,
        "verify_personal_desktop_unattended_paper_invocation",
        reject_final_replay,
    )
    replay_api = FakeNative()
    with pytest.raises(ValueError, match="final canonical replay"):
        with _capability(binding, replay_api) as capability:
            capability.publish()
    assert final in replay_api.objects and final_artifact in replay_api.objects
    assert replay_api.open_handles == {}

    monkeypatch.setattr(
        output,
        "verify_personal_desktop_unattended_paper_invocation",
        real_verify,
    )

    class FinalSecurityDriftNative(FakeNative):
        def rename_unattended_write_through(
            self, staging: str, final_path: str
        ) -> None:
            super().rename_unattended_write_through(staging, final_path)
            observation, payload = self.objects[final_artifact]
            self.objects[final_artifact] = (
                replace(
                    observation,
                    security=replace(
                        observation.security,
                        dacl_protected=False,
                    ),
                ),
                payload,
            )

    security_api = FinalSecurityDriftNative()
    with pytest.raises(AuthoritySecurityError, match="DACL"):
        with _capability(binding, security_api) as capability:
            capability.publish()
    assert final in security_api.objects and final_artifact in security_api.objects
    assert security_api.open_handles == {}


@pytest.mark.parametrize(
    "parent",
    (
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
    ),
)
def test_pinned_parent_identity_drift_blocks_before_rename(parent: str) -> None:
    binding = _expected()
    api = FakeNative()
    api.parent_drift_after_write = parent
    staging, final, staged_artifact, _ = _paths(binding)

    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError, match="parent changed"
    ):
        with _capability(binding, api) as capability:
            capability.publish()

    assert staging in api.objects and staged_artifact in api.objects
    assert final not in api.objects
    assert api.open_handles == {}


def test_missing_unattended_parent_is_never_created() -> None:
    binding = _expected()
    api = FakeNative()
    del api.objects[security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS]

    with pytest.raises(AuthorityObjectError, match="missing"):
        with _capability(binding, api):
            pass

    assert not any(event[0] == "create-directory" for event in api.events)
    assert api.open_handles == {}


def test_pinned_parent_security_drift_blocks_before_rename() -> None:
    binding = _expected()
    api = FakeNative()
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
    api.parent_security_drift_after_write = parent
    staging, final, staged_artifact, _ = _paths(binding)

    with pytest.raises(AuthoritySecurityError, match="DACL"):
        with _capability(binding, api) as capability:
            capability.publish()

    assert staging in api.objects and staged_artifact in api.objects
    assert final not in api.objects
    assert api.open_handles == {}


@pytest.mark.parametrize("target", ("directory", "artifact"))
def test_final_identity_is_reverified_against_staged_identity(target: str) -> None:
    binding = _expected()
    _, final, _, final_artifact = _paths(binding)

    class FinalIdentityDriftNative(FakeNative):
        def rename_unattended_write_through(
            self, staging: str, final_path: str
        ) -> None:
            super().rename_unattended_write_through(staging, final_path)
            path = final_path if target == "directory" else final_artifact
            observation, payload = self.objects[path]
            self.objects[path] = (replace(observation, identity=(88, 88)), payload)

    api = FinalIdentityDriftNative()
    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError,
        match="identity/security changed",
    ):
        with _capability(binding, api) as capability:
            capability.publish()

    assert final in api.objects and final_artifact in api.objects
    assert api.open_handles == {}


def test_create_and_post_staging_failures_are_consumed_without_cleanup() -> None:
    binding = _expected()
    staging, _, staged_artifact, _ = _paths(binding)

    create_api = FakeNative()
    create_api.create_error = RuntimeError("create failed")
    capability = _capability(binding, create_api)
    with capability:
        with pytest.raises(RuntimeError, match="create failed"):
            capability.publish()
        with pytest.raises(
            output.PersonalDesktopPaperRuntimeOutputError, match="not active"
        ):
            capability.publish()
    assert staging not in create_api.objects
    assert sum(event[0] == "create-directory" for event in create_api.events) == 1
    assert create_api.open_handles == {}

    write_api = FakeNative()
    write_api.write_error = RuntimeError("write failed")
    with pytest.raises(RuntimeError, match="write failed"):
        with _capability(binding, write_api) as capability:
            capability.publish()
    assert staging in write_api.objects and staged_artifact not in write_api.objects
    assert not any("delete" in str(event[0]) for event in write_api.events)
    assert write_api.open_handles == {}


def test_rename_collision_is_no_clobber_one_attempt_and_leaves_staging() -> None:
    binding = _expected()
    api = FakeNative()
    staging, final, staged_artifact, final_artifact = _paths(binding)
    original = b"pre-existing"
    api.objects[final] = (_observation(final, (7, 50)), None)
    api.objects[final_artifact] = (
        _observation(final_artifact, (7, 51), byte_length=len(original)),
        original,
    )

    with pytest.raises(AuthorityObjectError, match="no-clobber"):
        with _capability(binding, api) as capability:
            capability.publish()

    assert staging in api.objects and staged_artifact in api.objects
    assert api.objects[final_artifact][1] == original
    assert (
        sum(event[0] == "rename-unattended-write-through" for event in api.events) == 1
    )
    assert not any("delete" in str(event[0]) for event in api.events)
    assert api.open_handles == {}


def test_capability_and_disposable_authority_are_one_shot_and_nonserializable() -> None:
    binding = _expected()
    api = FakeNative()
    authority = (
        output._open_disposable_unattended_invocation_output_authority_for_test()
    )
    capability = (
        output._open_personal_desktop_unattended_invocation_output_capability_for_test(
            binding,
            api,
            authority=authority,
        )
    )
    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError, match="not active"
    ):
        capability.publish()
    for value in (authority, capability):
        with pytest.raises(TypeError):
            copy.copy(value)
        with pytest.raises(TypeError):
            copy.deepcopy(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)
    with capability:
        pass
    with pytest.raises(output.PersonalDesktopPaperRuntimeOutputError, match="one-shot"):
        with capability:
            pass
    with pytest.raises(
        output.PersonalDesktopPaperRuntimeOutputError, match="not active"
    ):
        capability.publish()
    with pytest.raises(TypeError, match="consumed"):
        output._open_personal_desktop_unattended_invocation_output_capability_for_test(
            binding,
            FakeNative(),
            authority=authority,
        )


def test_disposable_seam_rejects_genuine_native_and_exposes_publish_only() -> None:
    binding = _expected()
    native = object.__new__(output._WindowsPaperRuntimeOutputNativeApi)
    authority = (
        output._open_disposable_unattended_invocation_output_authority_for_test()
    )
    with pytest.raises(TypeError, match="genuine production native implementation"):
        output._open_personal_desktop_unattended_invocation_output_capability_for_test(
            binding,
            native,
            authority=authority,
        )
    capability = (
        output._open_personal_desktop_unattended_invocation_output_capability_for_test(
            binding,
            FakeNative(),
            authority=authority,
        )
    )
    public_callables = {
        name
        for name, value in inspect.getmembers(type(capability), callable)
        if not name.startswith("_")
    }
    assert public_callables == {"publish"}
    assert not hasattr(native, "_kernel")


def test_distinct_native_unattended_finalizer_is_exact_and_write_through() -> None:
    binding = _expected()
    staging, final, _, _ = _paths(binding)
    calls: list[tuple[str, str, int]] = []

    class Move:
        argtypes = None
        restype = None

        def __call__(self, source: str, destination: str, flags: int) -> int:
            calls.append((source, destination, flags))
            return 1

    native = object.__new__(output._WindowsPaperRuntimeOutputNativeApi)
    native._kernel = SimpleNamespace(MoveFileExW=Move())
    native.rename_unattended_write_through(staging, final)
    assert calls == [(staging, final, 0x8)]

    wrong_id = _expected(caller_key="different-id").invocation.invocation_id
    wrong_final = (
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
        + "\\"
        + storage.unattended_paper_invocation_directory_name(wrong_id)
    )
    with pytest.raises(AuthorityPathError):
        native.rename_unattended_write_through(staging, wrong_final)
    with pytest.raises(AuthorityPathError):
        native.rename_unattended_write_through(
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + "\\.paper-account-transition-"
            + str(binding.invocation.invocation_id)
            + ".staging",
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
            + "\\paper-account-transition-"
            + str(binding.invocation.invocation_id),
        )
    assert calls == [(staging, final, 0x8)]
