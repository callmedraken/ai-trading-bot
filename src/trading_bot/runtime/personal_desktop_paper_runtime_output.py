"""Architecture-103 output capability for the fixed Paper-v2 runtime."""

from __future__ import annotations

import ctypes
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Protocol, Self
from uuid import UUID

from trading_bot.cli.paper_operation_output_capability import (
    PaperOperationOutputCapability,
)
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PreOpenDecisionPublicationPermit,
    consume_disposable_pre_open_decision_publication_permit_for_test,
    consume_pre_open_decision_publication_permit,
    require_pre_open_decision_publication_permit,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    PersonalDesktopUnattendedDecisionStorageClassification,
    PersonalDesktopUnattendedDecisionStorageReadResult,
    require_validated_personal_desktop_unattended_decision_storage_read,
    unattended_paper_decision_artifact_name,
    unattended_paper_decision_directory_name,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    verify_personal_desktop_unattended_paper_invocation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation_storage import (
    PersonalDesktopUnattendedInvocationStorageClassification,
    PersonalDesktopUnattendedInvocationStorageReadResult,
    require_validated_personal_desktop_unattended_invocation_storage_read,
    unattended_paper_invocation_artifact_name,
    unattended_paper_invocation_directory_name,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
)
from trading_bot.runtime.windows_authority_security import (
    GENERIC_WRITE,
    AuthorityObjectKind,
    SecurityPolicy,
    WindowsHandle,
    build_security_attributes,
)
from trading_bot.runtime.windows_authority_validation import (
    require_validated_production_authority,
)

_MOVEFILE_WRITE_THROUGH = 0x8
_CREATE_NEW = 1
_FILE_ATTRIBUTE_NORMAL = 0x80
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_RUNTIME_OUTPUT_ISSUER = object()
_DISPOSABLE_RUNTIME_OUTPUT_ISSUER = object()
_DISPOSABLE_RUNTIME_OUTPUT_AUTHORITY_ISSUER = object()
_RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER = object()
_DISPOSABLE_RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER = object()
_DISPOSABLE_RECEIPT_RECOVERY_OUTPUT_AUTHORITY_ISSUER = object()
_UNATTENDED_RUNTIME_OUTPUT_ISSUER = object()
_UNATTENDED_INVOCATION_OUTPUT_ISSUER = object()
_DISPOSABLE_UNATTENDED_INVOCATION_OUTPUT_ISSUER = object()
_DISPOSABLE_UNATTENDED_INVOCATION_OUTPUT_AUTHORITY_ISSUER = object()
_UNATTENDED_DECISION_OUTPUT_ISSUER = object()
_DISPOSABLE_UNATTENDED_DECISION_OUTPUT_ISSUER = object()
_CANONICAL_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class PersonalDesktopPaperRuntimeOutputError(AuthorityObjectError):
    """The fixed production runtime output policy failed closed."""


class _PaperRuntimeOutputNativeApi(Protocol):
    def open(self, path: str, kind: AuthorityObjectKind) -> object: ...

    def close(self, handle: object) -> None: ...

    def inspect(
        self, handle: object, path: str, kind: AuthorityObjectKind
    ) -> security.PaperObjectObservation: ...

    def create_directory(self, path: str, policy: SecurityPolicy) -> None: ...

    def write_file(self, path: str, payload: bytes, policy: SecurityPolicy) -> None: ...

    def read(self, handle: object, maximum: int) -> bytes: ...

    def rename_write_through(self, staging: str, final: str) -> None: ...

    def rename_unattended_write_through(self, staging: str, final: str) -> None: ...


@dataclass(frozen=True, slots=True)
class _PinnedParent:
    path: str
    handle: object
    observation: security.PaperObjectObservation


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedInvocationPublicationResult:
    """Immutable non-authorizing evidence for one verified publication."""

    invocation_id: UUID
    artifact_sha256: str
    artifact_byte_length: int
    staging_created: bool
    finalized: bool
    artifact_verified: bool

    def __post_init__(self) -> None:
        if (
            type(self.invocation_id) is not UUID
            or type(self.artifact_sha256) is not str
            or len(self.artifact_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.artifact_sha256
            )
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length <= 0
            or self.staging_created is not True
            or self.finalized is not True
            or self.artifact_verified is not True
        ):
            raise ValueError("unattended invocation publication result is invalid")


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedDecisionPublicationResult:
    """Non-authorizing evidence of one verified durable decision publication."""

    decision_id: UUID
    artifact_sha256: str
    artifact_byte_length: int
    staging_created: bool
    finalized: bool
    artifact_verified: bool

    def __post_init__(self) -> None:
        if (
            type(self.decision_id) is not UUID
            or type(self.artifact_sha256) is not str
            or len(self.artifact_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.artifact_sha256
            )
            or type(self.artifact_byte_length) is not int
            or self.artifact_byte_length <= 0
            or self.staging_created is not True
            or self.finalized is not True
            or self.artifact_verified is not True
        ):
            raise ValueError("unattended decision publication result is invalid")


class _PersonalDesktopPaperRuntimeOutputCapability(PaperOperationOutputCapability):
    """One-use fixed-namespace capability held across one A67 invocation."""

    __slots__ = ("_api", "_closed", "_entered", "_finalizations", "_parents")

    def __init__(self, api: _PaperRuntimeOutputNativeApi, *, _issuer: object) -> None:
        if _issuer not in {
            _RUNTIME_OUTPUT_ISSUER,
            _DISPOSABLE_RUNTIME_OUTPUT_ISSUER,
            _RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER,
            _DISPOSABLE_RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER,
            _UNATTENDED_RUNTIME_OUTPUT_ISSUER,
        }:
            raise TypeError("Paper-v2 runtime output capability issuer is invalid")
        self._api = api
        self._closed = False
        self._entered = False
        self._parents: dict[str, _PinnedParent] = {}
        self._finalizations: set[tuple[str, str]] = set()

    def __enter__(self) -> Self:
        if self._entered or self._closed:
            raise PersonalDesktopPaperRuntimeOutputError(
                "Paper-v2 runtime output capability is one-shot"
            )
        self._entered = True
        try:
            for path in (
                security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
                security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS,
            ):
                self._pin_parent(path)
            self.verify_parent(Path(security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME))
            self.verify_parent(Path(security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS))
        except BaseException:
            self._close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if exc_type is None:
                self.verify_parent(Path(security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME))
                self.verify_parent(Path(security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS))
        finally:
            self._close()

    def _require_active(self) -> None:
        if not self._entered or self._closed:
            raise PersonalDesktopPaperRuntimeOutputError(
                "Paper-v2 runtime output capability is not active"
            )

    def _pin_parent(self, path: str) -> None:
        spec = security.paper_object_spec(path)
        if spec.role not in {
            security.PaperObjectRole.RUNTIME,
            security.PaperObjectRole.OPERATIONS,
        }:
            raise AuthorityPathError("runtime output parent is not source-owned")
        handle = self._api.open(path, spec.kind)
        try:
            observation = self._api.inspect(handle, path, spec.kind)
            self._verify_observation(path, observation)
        except BaseException:
            self._api.close(handle)
            raise
        self._parents[path] = _PinnedParent(path, handle, observation)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        first_error: BaseException | None = None
        for pinned in reversed(tuple(self._parents.values())):
            try:
                self._api.close(pinned.handle)
            except BaseException as error:
                if first_error is None:
                    first_error = error
        self._parents.clear()
        if first_error is not None:
            raise first_error

    def _verify_observation(
        self, path: str, observation: security.PaperObjectObservation
    ) -> None:
        spec = security.paper_object_spec(path)
        security.require_paper_object_security(
            path,
            spec,
            observation.security,
            PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
        )
        if (
            spec.role
            in {
                security.PaperObjectRole.OUTPUT_DIRECTORY,
                security.PaperObjectRole.OUTPUT_FILE,
            }
            and observation.security.owner_sid
            != PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
        ):
            raise PersonalDesktopPaperRuntimeOutputError(
                "Paper-v2 runtime output owner is not the exact Trading SID"
            )
        if (
            type(observation.identity) is not tuple
            or len(observation.identity) != 2
            or any(
                type(value) is not int or value < 0 for value in observation.identity
            )
            or observation.identity[1] == 0
            or (
                spec.kind is AuthorityObjectKind.FILE
                and (
                    type(observation.byte_length) is not int
                    or not 0 < observation.byte_length <= spec.maximum_bytes
                    or observation.links != 1
                )
            )
        ):
            raise PersonalDesktopPaperRuntimeOutputError(
                "Paper-v2 runtime output object identity is unsafe"
            )

    def _verify_named(self, path: Path, expected_kind: AuthorityObjectKind) -> None:
        self._require_active()
        text = str(path)
        spec = security.paper_object_spec(text)
        if spec.kind is not expected_kind:
            raise AuthorityPathError("runtime output object kind is invalid")
        handle = self._api.open(text, spec.kind)
        try:
            observation = self._api.inspect(handle, text, spec.kind)
            self._verify_observation(text, observation)
        finally:
            self._api.close(handle)

    def verify_parent(self, path: Path) -> None:
        self._require_active()
        text = str(path)
        pinned = self._parents.get(text)
        if pinned is None:
            raise AuthorityPathError("runtime output parent is not fixed")
        current = self._api.inspect(
            pinned.handle, text, pinned.observation.security.kind
        )
        self._verify_observation(text, current)
        if (
            current.identity != pinned.observation.identity
            or current.security != pinned.observation.security
        ):
            raise PersonalDesktopPaperRuntimeOutputError(
                "Paper-v2 runtime output parent changed"
            )
        reopened = self._api.open(text, pinned.observation.security.kind)
        try:
            observed = self._api.inspect(
                reopened, text, pinned.observation.security.kind
            )
            self._verify_observation(text, observed)
            if (
                observed.identity != pinned.observation.identity
                or observed.security != pinned.observation.security
            ):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "Paper-v2 runtime output parent was replaced"
                )
        finally:
            self._api.close(reopened)

    def create_staging_directory(self, path: Path) -> None:
        self._require_active()
        text = str(path)
        spec = security.paper_object_spec(text)
        if (
            spec.role is not security.PaperObjectRole.OUTPUT_DIRECTORY
            or not _is_staging(text)
        ):
            raise AuthorityPathError("runtime staging directory path is invalid")
        policy = security.paper_security_policy(
            spec.role,
            PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
            owner_sid=(
                PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
            ),
        )
        self._api.create_directory(text, policy)

    def write_staged_file(self, path: Path, payload: bytes) -> None:
        self._require_active()
        text = str(path)
        spec = security.paper_object_spec(text)
        if (
            spec.role is not security.PaperObjectRole.OUTPUT_FILE
            or not _is_under_staging(text)
            or type(payload) is not bytes
            or not 0 < len(payload) <= spec.maximum_bytes
        ):
            raise AuthorityPathError("runtime staged file path or payload is invalid")
        policy = security.paper_security_policy(
            spec.role,
            PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
            owner_sid=(
                PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
            ),
        )
        self._api.write_file(text, payload, policy)

    def verify_staged_directory(self, path: Path) -> None:
        if not _is_staging(str(path)):
            raise AuthorityPathError("runtime staged directory path is invalid")
        self._verify_named(path, AuthorityObjectKind.DIRECTORY)

    def verify_staged_file(self, path: Path) -> None:
        if not _is_under_staging(str(path)):
            raise AuthorityPathError("runtime staged file path is invalid")
        self._verify_named(path, AuthorityObjectKind.FILE)

    def finalize_directory(self, staging: Path, final: Path) -> None:
        self._require_active()
        source, destination = str(staging), str(final)
        if not _valid_finalization(source, destination):
            raise AuthorityPathError("runtime output finalization names are invalid")
        attempt = (source, destination)
        if attempt in self._finalizations:
            raise PersonalDesktopPaperRuntimeOutputError(
                "runtime output finalization attempt is already consumed"
            )
        self._finalizations.add(attempt)
        self._api.rename_write_through(source, destination)

    def verify_finalized_directory(self, path: Path) -> None:
        if _is_staging(str(path)):
            raise AuthorityPathError("runtime finalized directory path is invalid")
        self._verify_named(path, AuthorityObjectKind.DIRECTORY)

    def verify_finalized_file(self, path: Path) -> None:
        if _is_under_staging(str(path)):
            raise AuthorityPathError("runtime finalized file path is invalid")
        self._verify_named(path, AuthorityObjectKind.FILE)


class _PersonalDesktopPaperReceiptRecoveryOutputCapability(
    _PersonalDesktopPaperRuntimeOutputCapability
):
    """One-use capability restricted to one Architecture-67 receipt layout."""

    __slots__ = ()

    def __init__(self, api: _PaperRuntimeOutputNativeApi, *, _issuer: object) -> None:
        if _issuer not in {
            _RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER,
            _DISPOSABLE_RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER,
        }:
            raise TypeError("Paper-v2 receipt-recovery output issuer is invalid")
        super().__init__(api, _issuer=_issuer)

    def create_staging_directory(self, path: Path) -> None:
        _require_receipt_directory(path, staging=True)
        super().create_staging_directory(path)

    def write_staged_file(self, path: Path, payload: bytes) -> None:
        _require_receipt_file(path, staging=True)
        super().write_staged_file(path, payload)

    def verify_staged_directory(self, path: Path) -> None:
        _require_receipt_directory(path, staging=True)
        super().verify_staged_directory(path)

    def verify_staged_file(self, path: Path) -> None:
        _require_receipt_file(path, staging=True)
        super().verify_staged_file(path)

    def finalize_directory(self, staging: Path, final: Path) -> None:
        staging_id = _require_receipt_directory(staging, staging=True)
        final_id = _require_receipt_directory(final, staging=False)
        if staging_id != final_id:
            raise AuthorityPathError(
                "receipt-recovery finalization identities do not match"
            )
        super().finalize_directory(staging, final)

    def verify_finalized_directory(self, path: Path) -> None:
        _require_receipt_directory(path, staging=False)
        super().verify_finalized_directory(path)

    def verify_finalized_file(self, path: Path) -> None:
        _require_receipt_file(path, staging=False)
        super().verify_finalized_file(path)


class _PersonalDesktopUnattendedInvocationOutputCapability:
    """Publish exactly one bound PD4-A artifact into the fixed B1 namespace."""

    __slots__ = (
        "_api",
        "_calendar",
        "_closed",
        "_entered",
        "_expected",
        "_parents",
        "_published",
    )

    def __init__(
        self,
        api: _PaperRuntimeOutputNativeApi,
        expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
        *,
        _issuer: object,
    ) -> None:
        if _issuer not in {
            _UNATTENDED_INVOCATION_OUTPUT_ISSUER,
            _DISPOSABLE_UNATTENDED_INVOCATION_OUTPUT_ISSUER,
        }:
            raise TypeError("unattended invocation output issuer is invalid")
        if (
            type(expected)
            is not PersonalDesktopUnattendedPaperInvocationArtifactBinding
        ):
            raise TypeError("unattended invocation output binding is invalid")
        self._api = api
        self._calendar = BoundMarketCalendar(
            XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()
        )
        self._expected = expected
        self._parents: dict[str, _PinnedParent] = {}
        self._entered = False
        self._closed = False
        self._published = False

    def __enter__(self) -> Self:
        if self._entered or self._closed:
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended invocation output capability is one-shot"
            )
        self._entered = True
        try:
            for path in (
                security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
                security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
            ):
                self._pin_parent(path)
            self._verify_parents()
        except BaseException:
            self._close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if not self._closed:
                self._verify_parents()
        finally:
            self._close()

    def __copy__(self) -> object:
        raise TypeError("unattended invocation output capabilities cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(
            "unattended invocation output capabilities cannot be deep-copied"
        )

    def __reduce__(self) -> object:
        raise TypeError(
            "unattended invocation output capabilities cannot be serialized"
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("unattended invocation output capabilities cannot be pickled")

    def publish(self) -> PersonalDesktopUnattendedInvocationPublicationResult:
        """Publish only the artifact captured from trusted admission evidence."""

        self._require_active()
        if self._published:
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended invocation publication attempt is already consumed"
            )
        self._published = True
        try:
            self._verify_parents()
            expected = self._replay_expected()
            invocation_id = expected.invocation.invocation_id
            parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
            staging = (
                parent
                + "\\"
                + unattended_paper_invocation_directory_name(
                    invocation_id, staging=True
                )
            )
            final = (
                parent
                + "\\"
                + unattended_paper_invocation_directory_name(invocation_id)
            )
            artifact_name = unattended_paper_invocation_artifact_name(invocation_id)
            staged_artifact = staging + "\\" + artifact_name
            final_artifact = final + "\\" + artifact_name

            directory_spec = security.paper_object_spec(staging)
            if (
                directory_spec.role
                is not security.PaperObjectRole.UNATTENDED_INVOCATION_DIRECTORY
            ):
                raise AuthorityPathError(
                    "unattended invocation staging role is invalid"
                )
            self._api.create_directory(
                staging,
                security.paper_security_policy(
                    directory_spec.role,
                    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
                ),
            )

            staging_handle, staging_observation = self._open_verified(staging)
            try:
                file_spec = security.paper_object_spec(staged_artifact)
                if (
                    file_spec.role
                    is not security.PaperObjectRole.UNATTENDED_INVOCATION_FILE
                ):
                    raise AuthorityPathError(
                        "unattended invocation artifact role is invalid"
                    )
                self._api.write_file(
                    staged_artifact,
                    expected.artifact_bytes,
                    security.paper_security_policy(
                        file_spec.role,
                        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
                    ),
                )
                staged_file_observation = self._read_and_verify_artifact(
                    staged_artifact, expected
                )
                self._reverify_open_object(staging_handle, staging, staging_observation)
            finally:
                self._api.close(staging_handle)

            self._verify_parents()
            self._api.rename_unattended_write_through(staging, final)

            final_handle, final_observation = self._open_verified(final)
            try:
                self._require_renamed_object_identity(
                    staging_observation,
                    final_observation,
                    "unattended invocation directory",
                )
                final_file_observation = self._read_and_verify_artifact(
                    final_artifact, expected
                )
                self._require_renamed_object_identity(
                    staged_file_observation,
                    final_file_observation,
                    "unattended invocation artifact",
                )
                self._reverify_open_object(final_handle, final, final_observation)
                self._verify_parents()
            finally:
                self._api.close(final_handle)

            return PersonalDesktopUnattendedInvocationPublicationResult(
                invocation_id=invocation_id,
                artifact_sha256=expected.artifact_sha256,
                artifact_byte_length=expected.artifact_byte_length,
                staging_created=True,
                finalized=True,
                artifact_verified=True,
            )
        except BaseException as error:
            try:
                self._close()
            except BaseException as close_error:
                raise close_error from error
            raise

    def _require_active(self) -> None:
        if not self._entered or self._closed:
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended invocation output capability is not active"
            )

    def _pin_parent(self, path: str) -> None:
        spec = security.paper_object_spec(path)
        expected_roles = {
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME: (
                security.PaperObjectRole.RUNTIME
            ),
            security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS: (
                security.PaperObjectRole.UNATTENDED_INVOCATIONS
            ),
        }
        if expected_roles.get(path) is not spec.role:
            raise AuthorityPathError(
                "unattended invocation output parent is not source-owned"
            )
        handle = self._api.open(path, spec.kind)
        try:
            observation = self._api.inspect(handle, path, spec.kind)
            self._verify_observation(path, observation)
        except BaseException:
            self._api.close(handle)
            raise
        self._parents[path] = _PinnedParent(path, handle, observation)

    def _verify_parents(self) -> None:
        self._require_active()
        expected_paths = (
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
            security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
        )
        if set(self._parents) != set(expected_paths):
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended invocation output parents are incomplete"
            )
        for path in expected_paths:
            pinned = self._parents[path]
            current = self._api.inspect(
                pinned.handle, path, pinned.observation.security.kind
            )
            self._verify_observation(path, current)
            if not self._same_open_object(current, pinned.observation):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "unattended invocation output parent changed"
                )
            reopened = self._api.open(path, pinned.observation.security.kind)
            try:
                observed = self._api.inspect(
                    reopened, path, pinned.observation.security.kind
                )
                self._verify_observation(path, observed)
                if not self._same_open_object(observed, pinned.observation):
                    raise PersonalDesktopPaperRuntimeOutputError(
                        "unattended invocation output parent was replaced"
                    )
            finally:
                self._api.close(reopened)

    def _open_verified(
        self, path: str
    ) -> tuple[object, security.PaperObjectObservation]:
        spec = security.paper_object_spec(path)
        handle = self._api.open(path, spec.kind)
        try:
            observation = self._api.inspect(handle, path, spec.kind)
            self._verify_observation(path, observation)
        except BaseException:
            self._api.close(handle)
            raise
        return handle, observation

    def _read_and_verify_artifact(
        self,
        path: str,
        expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    ) -> security.PaperObjectObservation:
        handle, observation = self._open_verified(path)
        try:
            spec = security.paper_object_spec(path)
            payload = self._api.read(handle, spec.maximum_bytes)
            if (
                type(payload) is not bytes
                or payload != expected.artifact_bytes
                or len(payload) != expected.artifact_byte_length
                or observation.byte_length != expected.artifact_byte_length
            ):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "unattended invocation artifact bytes differ from the binding"
                )
            replayed = verify_personal_desktop_unattended_paper_invocation(
                payload,
                self._calendar,
                expected_invocation_id=expected.invocation.invocation_id,
                expected_artifact_sha256=expected.artifact_sha256,
                expected_artifact_byte_length=expected.artifact_byte_length,
            )
            if replayed != expected:
                raise PersonalDesktopPaperRuntimeOutputError(
                    "unattended invocation artifact replay differs from the binding"
                )
            self._reverify_open_object(handle, path, observation)
            return observation
        finally:
            self._api.close(handle)

    def _reverify_open_object(
        self,
        handle: object,
        path: str,
        expected: security.PaperObjectObservation,
    ) -> None:
        spec = security.paper_object_spec(path)
        current = self._api.inspect(handle, path, spec.kind)
        self._verify_observation(path, current)
        if not self._same_open_object(current, expected):
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended invocation output object changed"
            )
        reopened = self._api.open(path, spec.kind)
        try:
            observed = self._api.inspect(reopened, path, spec.kind)
            self._verify_observation(path, observed)
            if not self._same_open_object(observed, expected):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "unattended invocation output object was replaced"
                )
        finally:
            self._api.close(reopened)

    @staticmethod
    def _same_open_object(
        left: security.PaperObjectObservation,
        right: security.PaperObjectObservation,
    ) -> bool:
        return (
            left.identity == right.identity
            and left.security == right.security
            and (
                left.security.kind is not AuthorityObjectKind.FILE
                or (left.byte_length == right.byte_length and left.links == right.links)
            )
        )

    def _verify_observation(
        self, path: str, observation: security.PaperObjectObservation
    ) -> None:
        spec = security.paper_object_spec(path)
        security.require_paper_object_security(
            path,
            spec,
            observation.security,
            PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
        )
        if (
            type(observation.identity) is not tuple
            or len(observation.identity) != 2
            or any(
                type(value) is not int or value < 0 for value in observation.identity
            )
            or observation.identity[1] == 0
            or (
                spec.kind is AuthorityObjectKind.FILE
                and (
                    type(observation.byte_length) is not int
                    or not 0 < observation.byte_length <= spec.maximum_bytes
                    or observation.links != 1
                )
            )
        ):
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended invocation output object identity is unsafe"
            )

    def _replay_expected(
        self,
    ) -> PersonalDesktopUnattendedPaperInvocationArtifactBinding:
        expected = self._expected
        replayed = verify_personal_desktop_unattended_paper_invocation(
            expected.artifact_bytes,
            self._calendar,
            expected_invocation_id=expected.invocation.invocation_id,
            expected_artifact_sha256=expected.artifact_sha256,
            expected_artifact_byte_length=expected.artifact_byte_length,
        )
        if replayed != expected:
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended invocation output binding differs from exact replay"
            )
        return replayed

    def _require_renamed_object_identity(
        self,
        before: security.PaperObjectObservation,
        after: security.PaperObjectObservation,
        label: str,
    ) -> None:
        if (
            before.identity != after.identity
            or before.byte_length != after.byte_length
            or before.links != after.links
            or before.security.owner_sid != after.security.owner_sid
            or before.security.dacl_protected != after.security.dacl_protected
            or before.security.aces != after.security.aces
            or before.security.kind is not after.security.kind
            or before.security.is_reparse_point != after.security.is_reparse_point
            or before.security.volume_root != after.security.volume_root
            or before.security.filesystem != after.security.filesystem
        ):
            raise PersonalDesktopPaperRuntimeOutputError(
                f"{label} identity/security changed during finalization"
            )

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        first_error: BaseException | None = None
        for pinned in reversed(tuple(self._parents.values())):
            try:
                self._api.close(pinned.handle)
            except BaseException as error:
                if first_error is None:
                    first_error = error
        self._parents.clear()
        if first_error is not None:
            raise first_error


class _PersonalDesktopUnattendedDecisionOutputCapability(
    _PersonalDesktopUnattendedInvocationOutputCapability
):
    """Publish one exact G4 decision with a consumed pre-open permit."""

    __slots__ = (
        "_authority",
        "_disposable",
        "_permit",
        "_storage_read",
        "_real_effect_performed",
    )

    def __init__(
        self,
        api: _PaperRuntimeOutputNativeApi,
        expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
        storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
        permit: PreOpenDecisionPublicationPermit,
        *,
        authority: object | None,
        _issuer: object,
    ) -> None:
        if _issuer not in {
            _UNATTENDED_DECISION_OUTPUT_ISSUER,
            _DISPOSABLE_UNATTENDED_DECISION_OUTPUT_ISSUER,
        }:
            raise TypeError("unattended decision output issuer is invalid")
        if (
            type(expected)
            is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
            or type(storage_read)
            is not PersonalDesktopUnattendedDecisionStorageReadResult
            or type(permit) is not PreOpenDecisionPublicationPermit
        ):
            raise TypeError("unattended decision output evidence is invalid")
        self._api = api
        self._calendar = personal_desktop_unattended_decision_calendar()
        self._expected = expected
        self._storage_read = storage_read
        self._permit = permit
        self._authority = authority
        self._disposable = _issuer is _DISPOSABLE_UNATTENDED_DECISION_OUTPUT_ISSUER
        self._real_effect_performed = False
        self._parents = {}
        self._entered = False
        self._closed = False
        self._published = False

    @property
    def real_effect_performed(self) -> bool:
        """Diagnostic: the native staging-creation boundary was crossed.

        True includes an attempted native effect with an uncertain outcome; it
        does not prove durable publication or grant authority for another attempt.
        """

        return self._real_effect_performed

    def __enter__(self) -> Self:
        if self._entered or self._closed:
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended decision output capability is one-shot"
            )
        self._entered = True
        try:
            for path in (
                security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
                security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS,
            ):
                self._pin_parent(path)
            self._verify_parents()
        except BaseException:
            self._close()
            raise
        return self

    def publish(
        self, publication_observed_at: datetime
    ) -> PersonalDesktopUnattendedDecisionPublicationResult:
        """Recheck the deadline, consume admission, and attempt finalization once."""

        self._require_active()
        if self._published:
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended decision publication attempt is already consumed"
            )
        self._published = True
        try:
            self._verify_parents()
            expected = self._replay_expected()
            if self._disposable:
                consume_disposable_pre_open_decision_publication_permit_for_test(
                    self._permit,
                    expected,
                    self._storage_read,
                    publication_observed_at,
                )
            else:
                consume_pre_open_decision_publication_permit(
                    self._permit,
                    expected,
                    self._storage_read,
                    self._authority,
                    publication_observed_at,
                )
            decision_id = expected.decision.decision_id
            parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
            staging = (
                parent
                + "\\"
                + unattended_paper_decision_directory_name(decision_id, staging=True)
            )
            final = (
                parent + "\\" + unattended_paper_decision_directory_name(decision_id)
            )
            artifact_name = unattended_paper_decision_artifact_name(decision_id)
            staged_artifact = staging + "\\" + artifact_name
            final_artifact = final + "\\" + artifact_name
            directory_spec = security.paper_object_spec(staging)
            if (
                directory_spec.role
                is not security.PaperObjectRole.UNATTENDED_DECISION_DIRECTORY
            ):
                raise AuthorityPathError("unattended decision staging role is invalid")
            self._real_effect_performed = True
            self._api.create_directory(
                staging,
                security.paper_security_policy(
                    directory_spec.role,
                    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
                ),
            )
            staging_handle, staging_observation = self._open_verified(staging)
            try:
                file_spec = security.paper_object_spec(staged_artifact)
                if (
                    file_spec.role
                    is not security.PaperObjectRole.UNATTENDED_DECISION_FILE
                ):
                    raise AuthorityPathError(
                        "unattended decision artifact role is invalid"
                    )
                self._api.write_file(
                    staged_artifact,
                    expected.artifact_bytes,
                    security.paper_security_policy(
                        file_spec.role,
                        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
                    ),
                )
                staged_file_observation = self._read_and_verify_artifact(
                    staged_artifact, expected
                )
                self._reverify_open_object(staging_handle, staging, staging_observation)
            finally:
                self._api.close(staging_handle)
            self._verify_parents()
            self._api.rename_unattended_write_through(staging, final)
            final_handle, final_observation = self._open_verified(final)
            try:
                self._require_renamed_object_identity(
                    staging_observation,
                    final_observation,
                    "unattended decision directory",
                )
                final_file_observation = self._read_and_verify_artifact(
                    final_artifact, expected
                )
                self._require_renamed_object_identity(
                    staged_file_observation,
                    final_file_observation,
                    "unattended decision artifact",
                )
                self._reverify_open_object(final_handle, final, final_observation)
                self._verify_parents()
            finally:
                self._api.close(final_handle)
            return PersonalDesktopUnattendedDecisionPublicationResult(
                decision_id,
                expected.artifact_sha256,
                expected.artifact_byte_length,
                True,
                True,
                True,
            )
        except BaseException as error:
            try:
                self._close()
            except BaseException as close_error:
                raise close_error from error
            raise

    def _pin_parent(self, path: str) -> None:
        spec = security.paper_object_spec(path)
        expected_roles = {
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME: (
                security.PaperObjectRole.RUNTIME
            ),
            security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS: (
                security.PaperObjectRole.UNATTENDED_DECISIONS
            ),
        }
        if expected_roles.get(path) is not spec.role:
            raise AuthorityPathError("unattended decision parent is not source-owned")
        handle = self._api.open(path, spec.kind)
        try:
            observation = self._api.inspect(handle, path, spec.kind)
            self._verify_observation(path, observation)
        except BaseException:
            self._api.close(handle)
            raise
        self._parents[path] = _PinnedParent(path, handle, observation)

    def _verify_parents(self) -> None:
        self._require_active()
        expected_paths = (
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
            security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS,
        )
        if set(self._parents) != set(expected_paths):
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended decision output parents are incomplete"
            )
        for path in expected_paths:
            pinned = self._parents[path]
            current = self._api.inspect(
                pinned.handle, path, pinned.observation.security.kind
            )
            self._verify_observation(path, current)
            if not self._same_open_object(current, pinned.observation):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "unattended decision output parent changed"
                )
            reopened = self._api.open(path, pinned.observation.security.kind)
            try:
                observed = self._api.inspect(
                    reopened, path, pinned.observation.security.kind
                )
                self._verify_observation(path, observed)
                if not self._same_open_object(observed, pinned.observation):
                    raise PersonalDesktopPaperRuntimeOutputError(
                        "unattended decision output parent was replaced"
                    )
            finally:
                self._api.close(reopened)

    def _read_and_verify_artifact(
        self,
        path: str,
        expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    ) -> security.PaperObjectObservation:
        handle, observation = self._open_verified(path)
        try:
            spec = security.paper_object_spec(path)
            payload = self._api.read(handle, spec.maximum_bytes)
            if (
                type(payload) is not bytes
                or payload != expected.artifact_bytes
                or len(payload) != expected.artifact_byte_length
                or observation.byte_length != expected.artifact_byte_length
            ):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "unattended decision artifact differs from its binding"
                )
            replayed = verify_personal_desktop_unattended_paper_decision_intent(
                payload,
                self._calendar,
                expected_decision_id=expected.decision.decision_id,
                expected_artifact_sha256=expected.artifact_sha256,
                expected_artifact_byte_length=expected.artifact_byte_length,
            )
            if replayed != expected:
                raise PersonalDesktopPaperRuntimeOutputError(
                    "unattended decision replay differs from its binding"
                )
            self._reverify_open_object(handle, path, observation)
            return observation
        finally:
            self._api.close(handle)

    def _replay_expected(
        self,
    ) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding:
        expected = self._expected
        replayed = verify_personal_desktop_unattended_paper_decision_intent(
            expected.artifact_bytes,
            self._calendar,
            expected_decision_id=expected.decision.decision_id,
            expected_artifact_sha256=expected.artifact_sha256,
            expected_artifact_byte_length=expected.artifact_byte_length,
        )
        if replayed != expected:
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended decision output binding differs from exact replay"
            )
        return replayed


def _require_receipt_directory(path: Path, *, staging: bool) -> str:
    text = str(path)
    candidate = PureWindowsPath(text)
    if str(candidate.parent) != security.PERSONAL_DESKTOP_PAPER_V2_OPERATIONS:
        raise AuthorityPathError(
            "receipt-recovery directory is outside the fixed operations parent"
        )
    expression = (
        r"^\.paper-operation-([0-9a-f-]+)\.staging$"
        if staging
        else r"^paper-operation-([0-9a-f-]+)$"
    )
    match = re.fullmatch(expression, candidate.name)
    if match is None or _CANONICAL_UUID.fullmatch(match.group(1)) is None:
        raise AuthorityPathError("receipt-recovery directory name is invalid")
    return match.group(1)


def _require_receipt_file(path: Path, *, staging: bool) -> str:
    text = str(path)
    candidate = PureWindowsPath(text)
    operation_id = _require_receipt_directory(
        Path(str(candidate.parent)), staging=staging
    )
    if candidate.name != f"paper-operation-receipt-{operation_id}.json":
        raise AuthorityPathError("receipt-recovery file name is invalid")
    return operation_id


def _is_staging(path: str) -> bool:
    name = PureWindowsPath(path).name
    return name.startswith(".") and name.endswith(".staging")


def _is_under_staging(path: str) -> bool:
    return _is_staging(str(PureWindowsPath(path).parent))


def _valid_finalization(staging: str, final: str) -> bool:
    source = PureWindowsPath(staging)
    destination = PureWindowsPath(final)
    if source.parent != destination.parent or not _is_staging(staging):
        return False
    if source.name != f".{destination.name}.staging":
        return False
    try:
        source_spec = security.paper_object_spec(staging)
        final_spec = security.paper_object_spec(final)
    except AuthorityPathError:
        return False
    return (
        source_spec.role is security.PaperObjectRole.OUTPUT_DIRECTORY
        and final_spec.role is security.PaperObjectRole.OUTPUT_DIRECTORY
    )


def _valid_unattended_finalization(staging: str, final: str) -> bool:
    source = PureWindowsPath(staging)
    destination = PureWindowsPath(final)
    if destination.parent != source.parent:
        return False
    if source.parent == PureWindowsPath(
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
    ):
        prefix = ".unattended-paper-invocation-"
        name_builder = unattended_paper_invocation_directory_name
        expected_role = security.PaperObjectRole.UNATTENDED_INVOCATION_DIRECTORY
    elif source.parent == PureWindowsPath(
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
    ):
        prefix = ".unattended-paper-decision-"
        name_builder = unattended_paper_decision_directory_name
        expected_role = security.PaperObjectRole.UNATTENDED_DECISION_DIRECTORY
    else:
        return False
    suffix = ".staging"
    if not source.name.startswith(prefix) or not source.name.endswith(suffix):
        return False
    identity_text = source.name[len(prefix) : -len(suffix)]
    if _CANONICAL_UUID.fullmatch(identity_text) is None:
        return False
    identity = UUID(identity_text)
    if source.name != name_builder(
        identity, staging=True
    ) or destination.name != name_builder(identity):
        return False
    try:
        source_spec = security.paper_object_spec(staging)
        final_spec = security.paper_object_spec(final)
    except AuthorityPathError:
        return False
    return source_spec.role is expected_role and final_spec.role is expected_role


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


class _WindowsPaperRuntimeOutputNativeApi(security.WindowsPaperReadNativeApi):
    """Exact-ACL create/write plus one-flag native directory publication."""

    def create_directory(self, path: str, policy: SecurityPolicy) -> None:
        create = _bind(
            self._kernel,
            "CreateDirectoryW",
            [ctypes.c_wchar_p, ctypes.c_void_p],
            ctypes.c_int32,
        )
        with build_security_attributes(policy) as attributes:
            if not create(path, ctypes.byref(attributes.attributes)):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "cannot exclusively create runtime staging directory"
                )

    def write_file(self, path: str, payload: bytes, policy: SecurityPolicy) -> None:
        create = _bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
            ],
            ctypes.c_void_p,
        )
        with build_security_attributes(policy) as attributes:
            value = create(
                path,
                GENERIC_WRITE,
                1,
                ctypes.byref(attributes.attributes),
                _CREATE_NEW,
                _FILE_ATTRIBUTE_NORMAL | _FILE_FLAG_OPEN_REPARSE_POINT,
                None,
            )
        if value in (None, 0, -1, ctypes.c_void_p(-1).value):
            raise PersonalDesktopPaperRuntimeOutputError(
                "cannot exclusively create runtime staged file"
            )
        handle = WindowsHandle(value)
        try:
            write = _bind(
                self._kernel,
                "WriteFile",
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.c_void_p,
                ],
                ctypes.c_int32,
            )
            buffer = ctypes.create_string_buffer(payload)
            offset = 0
            while offset < len(payload):
                count = ctypes.c_uint32()
                if (
                    not write(
                        handle.value,
                        ctypes.byref(buffer, offset),
                        len(payload) - offset,
                        ctypes.byref(count),
                        None,
                    )
                    or not 0 < count.value <= len(payload) - offset
                ):
                    raise PersonalDesktopPaperRuntimeOutputError(
                        "runtime staged file write was incomplete"
                    )
                offset += count.value
            flush = _bind(
                self._kernel,
                "FlushFileBuffers",
                [ctypes.c_void_p],
                ctypes.c_int32,
            )
            if not flush(handle.value):
                raise PersonalDesktopPaperRuntimeOutputError(
                    "runtime staged file flush failed"
                )
        finally:
            handle.close()

    def rename_write_through(self, staging: str, final: str) -> None:
        if not _valid_finalization(staging, final):
            raise AuthorityPathError("native runtime rename names are invalid")
        move = _bind(
            self._kernel,
            "MoveFileExW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32],
            ctypes.c_int32,
        )
        if not move(staging, final, _MOVEFILE_WRITE_THROUGH):
            raise PersonalDesktopPaperRuntimeOutputError(
                "runtime same-parent no-clobber write-through rename failed"
            )

    def rename_unattended_write_through(self, staging: str, final: str) -> None:
        if not _valid_unattended_finalization(staging, final):
            raise AuthorityPathError(
                "native unattended publication rename names are invalid"
            )
        move = _bind(
            self._kernel,
            "MoveFileExW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32],
            ctypes.c_int32,
        )
        if not move(staging, final, _MOVEFILE_WRITE_THROUGH):
            raise PersonalDesktopPaperRuntimeOutputError(
                "unattended publication same-parent no-clobber write-through "
                "rename failed"
            )


def open_personal_desktop_paper_runtime_output_capability() -> (
    _PersonalDesktopPaperRuntimeOutputCapability
):
    """Open the fixed capability only behind the source-owned supervised gate."""

    from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
    )

    if (
        PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is not True
        or security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is not False
    ):
        raise PersonalDesktopPaperRuntimeOutputError(
            "Paper-v2 runtime output effect-gate state is invalid"
        )
    return _PersonalDesktopPaperRuntimeOutputCapability(
        _WindowsPaperRuntimeOutputNativeApi(),
        _issuer=_RUNTIME_OUTPUT_ISSUER,
    )


def open_personal_desktop_paper_receipt_recovery_output_capability() -> (
    _PersonalDesktopPaperReceiptRecoveryOutputCapability
):
    """Open receipt-only output for the exact source-owned four-gate state."""

    from trading_bot.runtime.personal_desktop_paper_receipt_recovery_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
    )

    if (
        PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED is not True
        or security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is not False
    ):
        raise PersonalDesktopPaperRuntimeOutputError(
            "Paper-v2 receipt-recovery output effect-gate state is invalid"
        )
    return _PersonalDesktopPaperReceiptRecoveryOutputCapability(
        _WindowsPaperRuntimeOutputNativeApi(),
        _issuer=_RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER,
    )


def open_personal_desktop_unattended_paper_runtime_output_capability() -> (
    _PersonalDesktopPaperRuntimeOutputCapability
):
    """Open A67 output only for the exact unattended-only six-gate state."""

    from trading_bot.runtime.personal_desktop_paper_receipt_recovery_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_unattended_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_unattended_paper_storage_provisioning import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )

    if (
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED is not True
        or PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED
        is not False
    ):
        raise PersonalDesktopPaperRuntimeOutputError(
            "unattended Paper-v2 runtime output effect-gate state is invalid"
        )
    return _PersonalDesktopPaperRuntimeOutputCapability(
        _WindowsPaperRuntimeOutputNativeApi(),
        _issuer=_UNATTENDED_RUNTIME_OUTPUT_ISSUER,
    )


def open_personal_desktop_unattended_invocation_output_capability(
    storage_read_result: PersonalDesktopUnattendedInvocationStorageReadResult,
) -> _PersonalDesktopUnattendedInvocationOutputCapability:
    """Open publication only from genuine B1 ABSENT production provenance."""

    verified = require_validated_personal_desktop_unattended_invocation_storage_read(
        storage_read_result
    )
    if (
        verified.classification
        is not PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
    ):
        raise PersonalDesktopPaperRuntimeOutputError(
            "unattended invocation publication requires exact ABSENT storage"
        )
    if verified.authority is None:
        raise PersonalDesktopPaperRuntimeOutputError(
            "unattended invocation publication lacks retained C1 authority"
        )
    require_validated_production_authority(verified.authority)

    from trading_bot.runtime.personal_desktop_paper_receipt_recovery_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_unattended_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_unattended_paper_storage_provisioning import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )

    if (
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED is not True
        or PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED
        is not False
    ):
        raise PersonalDesktopPaperRuntimeOutputError(
            "unattended invocation publication effect-gate state is invalid"
        )
    return _PersonalDesktopUnattendedInvocationOutputCapability(
        _WindowsPaperRuntimeOutputNativeApi(),
        verified.expected,
        _issuer=_UNATTENDED_INVOCATION_OUTPUT_ISSUER,
    )


def open_personal_desktop_unattended_decision_output_capability(
    storage_read_result: PersonalDesktopUnattendedDecisionStorageReadResult,
    permit: PreOpenDecisionPublicationPermit,
) -> _PersonalDesktopUnattendedDecisionOutputCapability:
    """Open the fixed G4 writer only for the exact isolated gate state."""

    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_unattended_market_data_capture as capture,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_decision_publication as publication,
    )

    verified = require_validated_personal_desktop_unattended_decision_storage_read(
        storage_read_result
    )
    if (
        verified.classification
        is not PersonalDesktopUnattendedDecisionStorageClassification.ABSENT
        or verified.authority is None
    ):
        raise PersonalDesktopPaperRuntimeOutputError(
            "unattended decision publication requires exact ABSENT production storage"
        )
    authority = require_validated_production_authority(verified.authority)
    require_pre_open_decision_publication_permit(
        permit, verified.expected, storage_read_result, authority
    )

    from trading_bot.runtime.personal_desktop_paper_receipt_recovery_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_supervised_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_unattended_paper_operation_execution import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
    )
    from trading_bot.runtime.personal_desktop_unattended_paper_storage_provisioning import (  # noqa: E501, PLC0415
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )

    if (
        publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED
        is not True
        or capture.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED
        is not False
        or security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not False
        or security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED is not False
        or PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED
        is not False
    ):
        raise PersonalDesktopPaperRuntimeOutputError(
            "unattended decision publication effect-gate state is invalid"
        )
    return _PersonalDesktopUnattendedDecisionOutputCapability(
        _WindowsPaperRuntimeOutputNativeApi(),
        verified.expected,
        storage_read_result,
        permit,
        authority=authority,
        _issuer=_UNATTENDED_DECISION_OUTPUT_ISSUER,
    )


class _DisposablePaperRuntimeOutputAuthorityForTest:
    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _DISPOSABLE_RUNTIME_OUTPUT_AUTHORITY_ISSUER:
            raise TypeError(
                "disposable runtime output authority requires its test issuer"
            )
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        with self._lock:
            if (
                self._issuer is not _DISPOSABLE_RUNTIME_OUTPUT_AUTHORITY_ISSUER
                or self._used
            ):
                raise TypeError(
                    "disposable runtime output authority is invalid or consumed"
                )
            self._used = True

    def __copy__(self) -> object:
        raise TypeError("disposable runtime output authorities cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("disposable runtime output authorities cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("disposable runtime output authorities cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("disposable runtime output authorities cannot be pickled")


def _open_disposable_paper_runtime_output_authority_for_test() -> (
    _DisposablePaperRuntimeOutputAuthorityForTest
):
    return _DisposablePaperRuntimeOutputAuthorityForTest(
        _issuer=_DISPOSABLE_RUNTIME_OUTPUT_AUTHORITY_ISSUER
    )


def _open_personal_desktop_paper_runtime_output_capability_for_test(
    api: _PaperRuntimeOutputNativeApi,
    *,
    authority: _DisposablePaperRuntimeOutputAuthorityForTest,
) -> _PersonalDesktopPaperRuntimeOutputCapability:
    if type(authority) is not _DisposablePaperRuntimeOutputAuthorityForTest:
        raise TypeError("disposable runtime output authority is invalid")
    if isinstance(api, _WindowsPaperRuntimeOutputNativeApi):
        raise TypeError(
            "the disposable runtime output seam rejects the genuine production "
            "native implementation"
        )
    authority._consume()
    return _PersonalDesktopPaperRuntimeOutputCapability(
        api,
        _issuer=_DISPOSABLE_RUNTIME_OUTPUT_ISSUER,
    )


class _DisposablePaperReceiptRecoveryOutputAuthorityForTest:
    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _DISPOSABLE_RECEIPT_RECOVERY_OUTPUT_AUTHORITY_ISSUER:
            raise TypeError(
                "disposable receipt-recovery output authority requires its test issuer"
            )
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        with self._lock:
            if (
                self._issuer is not _DISPOSABLE_RECEIPT_RECOVERY_OUTPUT_AUTHORITY_ISSUER
                or self._used
            ):
                raise TypeError(
                    "disposable receipt-recovery output authority is invalid "
                    "or consumed"
                )
            self._used = True

    def __copy__(self) -> object:
        raise TypeError(
            "disposable receipt-recovery output authorities cannot be copied"
        )

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(
            "disposable receipt-recovery output authorities cannot be deep-copied"
        )

    def __reduce__(self) -> object:
        raise TypeError(
            "disposable receipt-recovery output authorities cannot be serialized"
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError(
            "disposable receipt-recovery output authorities cannot be pickled"
        )


def _open_disposable_paper_receipt_recovery_output_authority_for_test() -> (
    _DisposablePaperReceiptRecoveryOutputAuthorityForTest
):
    return _DisposablePaperReceiptRecoveryOutputAuthorityForTest(
        _issuer=_DISPOSABLE_RECEIPT_RECOVERY_OUTPUT_AUTHORITY_ISSUER
    )


def _open_personal_desktop_paper_receipt_recovery_output_capability_for_test(
    api: _PaperRuntimeOutputNativeApi,
    *,
    authority: _DisposablePaperReceiptRecoveryOutputAuthorityForTest,
) -> _PersonalDesktopPaperReceiptRecoveryOutputCapability:
    if type(authority) is not _DisposablePaperReceiptRecoveryOutputAuthorityForTest:
        raise TypeError("disposable receipt-recovery output authority is invalid")
    if isinstance(api, _WindowsPaperRuntimeOutputNativeApi):
        raise TypeError(
            "the disposable receipt-recovery output seam rejects the genuine "
            "production native implementation"
        )
    authority._consume()
    return _PersonalDesktopPaperReceiptRecoveryOutputCapability(
        api,
        _issuer=_DISPOSABLE_RECEIPT_RECOVERY_RUNTIME_OUTPUT_ISSUER,
    )


class _DisposableUnattendedInvocationOutputAuthorityForTest:
    """Private one-shot issuer for fake-native publication tests."""

    __slots__ = ("_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object | None = None) -> None:
        if _issuer is not _DISPOSABLE_UNATTENDED_INVOCATION_OUTPUT_AUTHORITY_ISSUER:
            raise TypeError(
                "disposable unattended invocation output authority requires "
                "its test issuer"
            )
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False

    def _consume(self) -> None:
        with self._lock:
            if (
                self._issuer
                is not _DISPOSABLE_UNATTENDED_INVOCATION_OUTPUT_AUTHORITY_ISSUER
                or self._used
            ):
                raise TypeError(
                    "disposable unattended invocation output authority is "
                    "invalid or consumed"
                )
            self._used = True

    def __copy__(self) -> object:
        raise TypeError(
            "disposable unattended invocation output authorities cannot be copied"
        )

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(
            "disposable unattended invocation output authorities cannot be deep-copied"
        )

    def __reduce__(self) -> object:
        raise TypeError(
            "disposable unattended invocation output authorities cannot be serialized"
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError(
            "disposable unattended invocation output authorities cannot be pickled"
        )


def _open_disposable_unattended_invocation_output_authority_for_test() -> (
    _DisposableUnattendedInvocationOutputAuthorityForTest
):
    return _DisposableUnattendedInvocationOutputAuthorityForTest(
        _issuer=_DISPOSABLE_UNATTENDED_INVOCATION_OUTPUT_AUTHORITY_ISSUER
    )


def _open_personal_desktop_unattended_invocation_output_capability_for_test(
    expected: PersonalDesktopUnattendedPaperInvocationArtifactBinding,
    api: _PaperRuntimeOutputNativeApi,
    *,
    authority: _DisposableUnattendedInvocationOutputAuthorityForTest,
) -> _PersonalDesktopUnattendedInvocationOutputCapability:
    if type(authority) is not _DisposableUnattendedInvocationOutputAuthorityForTest:
        raise TypeError("disposable unattended invocation output authority is invalid")
    if type(expected) is not PersonalDesktopUnattendedPaperInvocationArtifactBinding:
        raise TypeError("disposable unattended invocation output binding is invalid")
    if isinstance(api, _WindowsPaperRuntimeOutputNativeApi):
        raise TypeError(
            "the disposable unattended invocation output seam rejects the genuine "
            "production native implementation"
        )
    authority._consume()
    return _PersonalDesktopUnattendedInvocationOutputCapability(
        api,
        expected,
        _issuer=_DISPOSABLE_UNATTENDED_INVOCATION_OUTPUT_ISSUER,
    )


def _open_personal_desktop_unattended_decision_output_capability_for_test(
    expected: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    storage_read: PersonalDesktopUnattendedDecisionStorageReadResult,
    permit: PreOpenDecisionPublicationPermit,
    api: _PaperRuntimeOutputNativeApi,
) -> _PersonalDesktopUnattendedDecisionOutputCapability:
    """Open only a fake-native writer from disposable permit provenance."""

    if (
        type(expected)
        is not PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding
        or type(storage_read) is not PersonalDesktopUnattendedDecisionStorageReadResult
        or storage_read.classification
        is not PersonalDesktopUnattendedDecisionStorageClassification.ABSENT
        or storage_read.expected_decision_id != expected.decision.decision_id
        or type(permit) is not PreOpenDecisionPublicationPermit
    ):
        raise TypeError("disposable unattended decision output evidence is invalid")
    if isinstance(api, _WindowsPaperRuntimeOutputNativeApi):
        raise TypeError(
            "the disposable decision output seam rejects the production native API"
        )
    return _PersonalDesktopUnattendedDecisionOutputCapability(
        api,
        expected,
        storage_read,
        permit,
        authority=None,
        _issuer=_DISPOSABLE_UNATTENDED_DECISION_OUTPUT_ISSUER,
    )
