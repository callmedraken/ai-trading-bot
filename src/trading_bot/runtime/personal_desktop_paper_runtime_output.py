"""Architecture-103 output capability for the fixed Paper-v2 runtime."""

from __future__ import annotations

import ctypes
import threading
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Protocol, Self

from trading_bot.cli.paper_operation_output_capability import (
    PaperOperationOutputCapability,
)
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
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

_MOVEFILE_WRITE_THROUGH = 0x8
_CREATE_NEW = 1
_FILE_ATTRIBUTE_NORMAL = 0x80
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_RUNTIME_OUTPUT_ISSUER = object()
_DISPOSABLE_RUNTIME_OUTPUT_ISSUER = object()
_DISPOSABLE_RUNTIME_OUTPUT_AUTHORITY_ISSUER = object()


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

    def rename_write_through(self, staging: str, final: str) -> None: ...


@dataclass(frozen=True, slots=True)
class _PinnedParent:
    path: str
    handle: object
    observation: security.PaperObjectObservation


class _PersonalDesktopPaperRuntimeOutputCapability(PaperOperationOutputCapability):
    """One-use fixed-namespace capability held across one A67 invocation."""

    __slots__ = ("_api", "_closed", "_entered", "_finalizations", "_parents")

    def __init__(self, api: _PaperRuntimeOutputNativeApi, *, _issuer: object) -> None:
        if _issuer not in {
            _RUNTIME_OUTPUT_ISSUER,
            _DISPOSABLE_RUNTIME_OUTPUT_ISSUER,
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
