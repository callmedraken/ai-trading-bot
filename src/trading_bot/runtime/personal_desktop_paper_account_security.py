"""Architecture-103 fixed namespace, ACL roles, and read-only pinned handles.

This is independent of the C1 opener/path guards. No method creates, renames,
deletes, repairs, or sets security on an object. Test APIs observe the same
source-owned names in memory; they cannot redirect the production opener.
"""

from __future__ import annotations

import ctypes
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self
from uuid import UUID

from trading_bot.market_data import MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
)
from trading_bot.runtime.paper_account_checkpoint import (
    MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
)
from trading_bot.runtime.paper_operation import MAX_PAPER_OPERATION_RECEIPT_BYTES
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    AuthorityObjectError,
    AuthorityPathError,
    AuthoritySecurityError,
    require_windows_platform,
)
from trading_bot.runtime.windows_authority_security import (
    FILE_ALL_ACCESS,
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
    SecurityAce,
    SecurityInspection,
    SecurityPolicy,
    WindowsHandle,
    authority_security_policy,
    inspect_open_authority_object,
)

PERSONAL_DESKTOP_PAPER_V2_ROOT = r"F:\AITradingBot\Paper-v2"
PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT = r"F:\AITradingBot\.Paper-v2.provisioning"
PERSONAL_DESKTOP_PAPER_V2_RUNTIME = PERSONAL_DESKTOP_PAPER_V2_ROOT + r"\runtime"
PERSONAL_DESKTOP_PAPER_V2_OPERATIONS = (
    PERSONAL_DESKTOP_PAPER_V2_RUNTIME + r"\paper-operations"
)
PERSONAL_DESKTOP_PAPER_V2_ANCHOR = (
    PERSONAL_DESKTOP_PAPER_V2_ROOT + r"\personal-desktop-paper-account-authority.json"
)
PERSONAL_DESKTOP_PAPER_PARENT = r"F:\AITradingBot"
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = True
MAX_INSTALLED_PAPER_ANCHOR_BYTES = 4096
MAX_PAPER_V2_DIRECTORY_ENTRIES = 1024
MAX_PAPER_V2_PINNED_OBJECTS = 8192
MAX_PAPER_V2_READ_BYTES = 256 * 1024 * 1024

ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"
TRADING_FILE_READ = 0x120089  # READ_CONTROL, SYNCHRONIZE, read data/EA/attributes
TRADING_DIRECTORY_READ = TRADING_FILE_READ | 0x20  # traverse/list
TRADING_FILE_DATA = 0x13019F  # read/write/append/EA/attributes/delete; no DAC/owner
TRADING_DIRECTORY_DATA = TRADING_FILE_DATA | 0x20  # traverse; children have DELETE
TRADING_CONTAINER_DATA = TRADING_DIRECTORY_DATA & ~0x10000  # never delete containers
_FILE_DELETE_CHILD = 0x40
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_TRADING_SID = re.compile(
    r"S-1-5-21-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)"
)


class PaperObjectRole(StrEnum):
    VOLUME = "volume"
    PARENT = "parent"
    ROOT = "root"
    ANCHOR = "anchor"
    GENESIS_DIRECTORY = "genesis-directory"
    GENESIS_CHECKPOINT = "genesis-checkpoint"
    RUNTIME = "runtime"
    OPERATIONS = "paper-operations"
    OUTPUT_DIRECTORY = "output-directory"
    OUTPUT_FILE = "output-file"
    C1_ROOT = "c1-root"
    CAPTURE_OUTPUT = "capture-output"
    HISTORICAL_SNAPSHOT = "historical-snapshot"


@dataclass(frozen=True, slots=True)
class PaperObjectSpec:
    role: PaperObjectRole
    kind: AuthorityObjectKind
    maximum_bytes: int = 0


def paper_object_spec(path: str) -> PaperObjectSpec:
    """Admit exact source-owned names before any Windows path normalization."""
    if type(path) is not str or len(path) > 512:
        raise AuthorityPathError("PD1B path is not exact fixed-namespace text")
    directory = AuthorityObjectKind.DIRECTORY
    file = AuthorityObjectKind.FILE
    fixed = {
        "F:\\": PaperObjectRole.VOLUME,
        PERSONAL_DESKTOP_PAPER_PARENT: PaperObjectRole.PARENT,
        PERSONAL_DESKTOP_PAPER_V2_ROOT: PaperObjectRole.ROOT,
        PERSONAL_DESKTOP_PAPER_V2_RUNTIME: PaperObjectRole.RUNTIME,
        PERSONAL_DESKTOP_PAPER_V2_OPERATIONS: PaperObjectRole.OPERATIONS,
        str(PRODUCTION_AUTHORITY_PATHS.root): PaperObjectRole.C1_ROOT,
        str(PRODUCTION_AUTHORITY_PATHS.capture_output): PaperObjectRole.CAPTURE_OUTPUT,
    }
    if path in fixed:
        return PaperObjectSpec(fixed[path], directory)
    if path == PERSONAL_DESKTOP_PAPER_V2_ANCHOR:
        return PaperObjectSpec(
            PaperObjectRole.ANCHOR, file, MAX_INSTALLED_PAPER_ANCHOR_BYTES
        )
    root = re.escape(PERSONAL_DESKTOP_PAPER_V2_ROOT)
    if re.fullmatch(rf"{root}\\paper-account-genesis-({_UUID})", path):
        return PaperObjectSpec(PaperObjectRole.GENESIS_DIRECTORY, directory)
    if re.fullmatch(
        rf"{root}\\paper-account-genesis-({_UUID})\\paper-account-checkpoint-\1\.json",
        path,
    ):
        return PaperObjectSpec(
            PaperObjectRole.GENESIS_CHECKPOINT, file, MAX_PAPER_ACCOUNT_CHECKPOINT_BYTES
        )
    transition = (
        re.escape(PERSONAL_DESKTOP_PAPER_V2_RUNTIME)
        + rf"\\paper-account-transition-{_UUID}"
    )
    operation = (
        re.escape(PERSONAL_DESKTOP_PAPER_V2_OPERATIONS)
        + rf"\\paper-operation-({_UUID})"
    )
    if re.fullmatch(transition, path) or re.fullmatch(operation, path):
        return PaperObjectSpec(PaperObjectRole.OUTPUT_DIRECTORY, directory)
    for expression, maximum in (
        (
            transition + rf"\\checkpointed-paper-cycle-report-{_UUID}\.json",
            MAX_CHECKPOINTED_PAPER_CYCLE_REPORT_BYTES,
        ),
        (
            transition + rf"\\paper-account-checkpoint-{_UUID}\.json",
            MAX_PAPER_ACCOUNT_SUCCESSOR_CHECKPOINT_BYTES,
        ),
        (
            operation + r"\\paper-operation-receipt-\1\.json",
            MAX_PAPER_OPERATION_RECEIPT_BYTES,
        ),
    ):
        if re.fullmatch(expression, path):
            return PaperObjectSpec(PaperObjectRole.OUTPUT_FILE, file, maximum)
    snapshot = re.escape(str(PRODUCTION_AUTHORITY_PATHS.capture_output))
    if re.fullmatch(snapshot + rf"\\daily-market-data-snapshot-{_UUID}\.json", path):
        return PaperObjectSpec(
            PaperObjectRole.HISTORICAL_SNAPSHOT, file, MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
        )
    raise AuthorityPathError("PD1B path is outside the exact source-owned read layout")


def historical_snapshot_path(snapshot_id: UUID) -> str:
    """Derive a C1 capture-output dependency from canonical content identity only."""
    if type(snapshot_id) is not UUID:
        raise AuthorityPathError("historical snapshot identity must be an exact UUID")
    return (
        str(PRODUCTION_AUTHORITY_PATHS.capture_output)
        + f"\\daily-market-data-snapshot-{snapshot_id}.json"
    )


def paper_security_policy(
    role: PaperObjectRole, trading_sid: str, *, owner_sid: str | None = None
) -> SecurityPolicy:
    """Exact protected v2 DACL policy, including future runtime-created objects."""
    if (
        type(role) is not PaperObjectRole
        or type(trading_sid) is not str
        or not _TRADING_SID.fullmatch(trading_sid)
    ):
        raise AuthoritySecurityError("PD1B policy role/Trading SID is invalid")
    owners = {ADMINISTRATORS_SID}
    if role in {PaperObjectRole.ROOT, PaperObjectRole.GENESIS_DIRECTORY}:
        rights = TRADING_DIRECTORY_READ
    elif role in {PaperObjectRole.ANCHOR, PaperObjectRole.GENESIS_CHECKPOINT}:
        rights = TRADING_FILE_READ
    elif role in {PaperObjectRole.RUNTIME, PaperObjectRole.OPERATIONS}:
        rights = TRADING_CONTAINER_DATA
    elif role in {PaperObjectRole.OUTPUT_DIRECTORY, PaperObjectRole.OUTPUT_FILE}:
        owners.add(trading_sid)
        rights = (
            TRADING_DIRECTORY_DATA
            if role is PaperObjectRole.OUTPUT_DIRECTORY
            else TRADING_FILE_DATA
        )
    else:
        raise AuthoritySecurityError("role is not a v2 ACL policy role")
    owner = ADMINISTRATORS_SID if owner_sid is None else owner_sid
    if owner not in owners:
        raise AuthoritySecurityError("PD1B object owner violates its role")
    return SecurityPolicy(
        owner,
        (
            SecurityAce(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
            SecurityAce(SYSTEM_SID, FILE_ALL_ACCESS),
            SecurityAce(trading_sid, rights),
        ),
    )


def _require_parent_security(
    inspection: SecurityInspection, role: PaperObjectRole
) -> None:
    if role is PaperObjectRole.VOLUME:
        # Sibling-create/data rights and DELETE on the volume root do not grant
        # deletion of its governed child. Accept concrete file rights only, so
        # generic/unknown masks cannot hide replacement or security authority.
        non_admin_rights = FILE_ALL_ACCESS & ~(
            _FILE_DELETE_CHILD | WRITE_DAC | WRITE_OWNER
        )
    elif role is PaperObjectRole.PARENT:
        # Keep the immediate parent conservatively read-only for unrelated
        # principals, including no DELETE on the parent component itself.
        non_admin_rights = TRADING_DIRECTORY_READ
    else:
        raise AuthoritySecurityError("unsupported fixed parent role")
    if inspection.owner_sid not in {ADMINISTRATORS_SID, SYSTEM_SID}:
        raise AuthoritySecurityError("fixed parent owner is untrusted")
    full: set[str] = set()
    for ace in inspection.aces:
        allowed_flags = 0x1B if role is PaperObjectRole.VOLUME else 0x13
        if ace.ace_type != 0 or ace.ace_flags & ~allowed_flags:
            raise AuthoritySecurityError("fixed parent ACE is unsupported")
        if role is PaperObjectRole.VOLUME and ace.ace_flags & 0x08:
            if not ace.ace_flags & 0x03:  # OBJECT_INHERIT or CONTAINER_INHERIT
                raise AuthoritySecurityError(
                    "volume inherit-only ACE lacks inheritance"
                )
            # Templates are not effective on the volume or its independently
            # verified governed parent. They grant no effective full control.
            continue
        if ace.principal_sid in {ADMINISTRATORS_SID, SYSTEM_SID}:
            if ace.access_mask == FILE_ALL_ACCESS and not ace.ace_flags & 0x8:
                full.add(ace.principal_sid)
        elif ace.access_mask & ~non_admin_rights:
            raise AuthoritySecurityError("fixed parent permits non-admin replacement")
    if full != {ADMINISTRATORS_SID, SYSTEM_SID}:
        raise AuthoritySecurityError("fixed parent lacks SYSTEM/Administrators control")


def require_paper_object_security(
    path: str, spec: PaperObjectSpec, inspection: SecurityInspection, trading_sid: str
) -> None:
    """Check exact path/type and role without broadening the existing C1 policy."""
    if (
        inspection.expected_path != path
        or inspection.final_path != path
        or inspection.kind is not spec.kind
        or inspection.is_reparse_point is not False
        or inspection.volume_root != "F:\\"
        or inspection.filesystem != "NTFS"
    ):
        raise AuthorityObjectError("PD1B object type/path/volume is unsafe")
    if spec.role in {PaperObjectRole.VOLUME, PaperObjectRole.PARENT}:
        _require_parent_security(inspection, spec.role)
        return
    if spec.role is PaperObjectRole.HISTORICAL_SNAPSHOT:
        # C3 artifact security belongs to C1/C3. The held read handle, exact
        # fixed path, transport evidence, A66 replay, and final security equality
        # protect this dependency without silently replacing C3's ACL policy.
        return
    if spec.role in {PaperObjectRole.C1_ROOT, PaperObjectRole.CAPTURE_OUTPUT}:
        role = "root" if spec.role is PaperObjectRole.C1_ROOT else "capture-output"
        policy = authority_security_policy(role, trading_sid)
    else:
        policy = paper_security_policy(
            spec.role, trading_sid, owner_sid=inspection.owner_sid
        )
    if (
        inspection.owner_sid != policy.owner_sid
        or inspection.dacl_protected is not True
        or len(inspection.aces) != len(policy.aces)
        or set(inspection.aces) != set(policy.aces)
    ):
        raise AuthoritySecurityError("PD1B object DACL violates its exact role policy")


@dataclass(frozen=True, slots=True)
class PaperObjectObservation:
    security: SecurityInspection
    identity: tuple[int, int]
    byte_length: int
    links: int


class PaperReadNativeApi(Protocol):
    def open(self, path: str, kind: AuthorityObjectKind) -> object: ...
    def close(self, handle: object) -> None: ...
    def inspect(
        self, handle: object, path: str, kind: AuthorityObjectKind
    ) -> PaperObjectObservation: ...
    def read(self, handle: object, maximum: int) -> bytes: ...
    def names(self, handle: object, path: str, maximum: int) -> tuple[str, ...]: ...


def _function(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


class WindowsPaperReadNativeApi:
    """No-follow OPEN_EXISTING only; files deny shared write and all deny delete."""

    def __init__(self) -> None:
        require_windows_platform()
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    def open(self, path: str, kind: AuthorityObjectKind) -> WindowsHandle:
        spec = paper_object_spec(path)
        if kind is not spec.kind:
            raise AuthorityObjectError("PD1B open kind does not match its source role")
        create = _function(
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
        handle = create(
            path,
            0x20081,
            3 if kind is AuthorityObjectKind.DIRECTORY else 1,
            None,
            3,
            0x02200000,
            None,
        )
        if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
            raise AuthorityObjectError("cannot pin PD1B object read-only")
        return WindowsHandle(handle)

    def close(self, handle: WindowsHandle) -> None:
        handle.close()

    def inspect(
        self, handle: WindowsHandle, path: str, kind: AuthorityObjectKind
    ) -> PaperObjectObservation:
        security = inspect_open_authority_object(handle.value, path, kind)
        # Volume checks include local fixed media and persistent ACL support.
        drive = _function(
            self._kernel, "GetDriveTypeW", [ctypes.c_wchar_p], ctypes.c_uint32
        )
        volume = _function(
            self._kernel,
            "GetVolumeInformationW",
            [
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_wchar_p,
                ctypes.c_uint32,
            ],
            ctypes.c_int32,
        )
        flags = ctypes.c_uint32()
        if (
            drive("F:\\") != 3
            or not volume("F:\\", None, 0, None, None, ctypes.byref(flags), None, 0)
            or not flags.value & 0x8
        ):
            raise AuthorityObjectError(
                "PD1B requires local fixed persistent-ACL storage"
            )

        class FileInformation(ctypes.Structure):
            _fields_ = [
                ("attributes", ctypes.c_uint32),
                ("times", ctypes.c_uint32 * 6),
                ("volume", ctypes.c_uint32),
                ("size_high", ctypes.c_uint32),
                ("size_low", ctypes.c_uint32),
                ("links", ctypes.c_uint32),
                ("index_high", ctypes.c_uint32),
                ("index_low", ctypes.c_uint32),
            ]

        query = _function(
            self._kernel,
            "GetFileInformationByHandle",
            [ctypes.c_void_p, ctypes.c_void_p],
            ctypes.c_int32,
        )
        info = FileInformation()
        if not query(handle.value, ctypes.byref(info)):
            raise AuthorityObjectError("PD1B file identity is unavailable")
        return PaperObjectObservation(
            security,
            (info.volume, (info.index_high << 32) | info.index_low),
            (info.size_high << 32) | info.size_low,
            info.links,
        )

    def read(self, handle: WindowsHandle, maximum: int) -> bytes:
        size = ctypes.c_int64()
        get_size = _function(
            self._kernel,
            "GetFileSizeEx",
            [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)],
            ctypes.c_int32,
        )
        if (
            not get_size(handle.value, ctypes.byref(size))
            or not 0 < size.value <= maximum
        ):
            raise AuthorityObjectError("installed PD1B artifact exceeds byte bound")
        seek = _function(
            self._kernel,
            "SetFilePointerEx",
            [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_uint32],
            ctypes.c_int32,
        )
        if not seek(handle.value, 0, None, 0):
            raise AuthorityObjectError("cannot seek pinned PD1B artifact")
        read = _function(
            self._kernel,
            "ReadFile",
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_void_p,
            ],
            ctypes.c_int32,
        )
        buffer = ctypes.create_string_buffer(size.value)
        offset = 0
        while offset < size.value:
            count = ctypes.c_uint32()
            remaining = size.value - offset
            if (
                not read(
                    handle.value,
                    ctypes.byref(buffer, offset),
                    remaining,
                    ctypes.byref(count),
                    None,
                )
                or not 0 < count.value <= remaining
            ):
                raise AuthorityObjectError("pinned PD1B artifact read is incomplete")
            offset += count.value
        after = ctypes.c_int64()
        if not get_size(handle.value, ctypes.byref(after)) or after.value != size.value:
            raise AuthorityObjectError("pinned PD1B artifact size drifted")
        return buffer.raw

    def names(self, handle: WindowsHandle, path: str, maximum: int) -> tuple[str, ...]:
        del handle  # The session holds every ancestor with delete sharing denied.
        names: list[str] = []
        with os.scandir(path) as entries:
            for entry in entries:
                if len(names) >= maximum:
                    raise AuthorityObjectError(
                        "PD1B directory inventory bound exceeded"
                    )
                names.append(entry.name)
        return tuple(names)


@dataclass(slots=True)
class _Pinned:
    handle: object
    spec: PaperObjectSpec
    observation: PaperObjectObservation
    payload: bytes | None = None
    names: tuple[str, ...] | None = None


class PinnedPaperReadSession:
    """Bounded read interval; all handles survive until final drift validation."""

    def __init__(self, api: PaperReadNativeApi, trading_sid: str) -> None:
        self._api = api
        self._sid = trading_sid
        self._objects: dict[str, _Pinned] = {}
        self._read_bytes = 0
        self._closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if exc_type is None:
                self.finish()
        finally:
            self._closed = True
            for pinned in reversed(tuple(self._objects.values())):
                self._api.close(pinned.handle)

    def pin(self, path: str) -> _Pinned:
        spec = paper_object_spec(path)
        if self._closed:
            raise AuthorityObjectError("PD1B read session is closed")
        if path in self._objects:
            return self._objects[path]
        if len(self._objects) >= MAX_PAPER_V2_PINNED_OBJECTS:
            raise AuthorityObjectError("PD1B pinned-object bound exceeded")
        if path != "F:\\":
            parent = path.rsplit("\\", 1)[0]
            if parent == "F:":
                parent += "\\"
            self.pin(parent)
        if len(self._objects) >= MAX_PAPER_V2_PINNED_OBJECTS:
            raise AuthorityObjectError("PD1B pinned-object bound exceeded")
        handle = self._api.open(path, spec.kind)
        try:
            observation = self._api.inspect(handle, path, spec.kind)
            self._check(path, spec, observation)
        except BaseException:
            self._api.close(handle)
            raise
        pinned = _Pinned(handle, spec, observation)
        self._objects[path] = pinned
        return pinned

    def _check(
        self, path: str, spec: PaperObjectSpec, observation: PaperObjectObservation
    ) -> None:
        require_paper_object_security(path, spec, observation.security, self._sid)
        if (
            type(observation.identity) is not tuple
            or len(observation.identity) != 2
            or any(
                type(value) is not int or value < 0 for value in observation.identity
            )
            or observation.identity[1] == 0
        ):
            raise AuthorityObjectError("PD1B file identity is invalid")
        if spec.kind is AuthorityObjectKind.FILE and (
            type(observation.byte_length) is not int
            or not 0 < observation.byte_length <= spec.maximum_bytes
            or observation.links != 1
        ):
            raise AuthorityObjectError("PD1B artifact length/hard-link count is unsafe")

    def read(self, path: str) -> bytes:
        pinned = self.pin(path)
        if pinned.spec.kind is not AuthorityObjectKind.FILE:
            raise AuthorityObjectError("PD1B cannot read a directory as an artifact")
        if pinned.payload is None:
            length = pinned.observation.byte_length
            if self._read_bytes + length > MAX_PAPER_V2_READ_BYTES:
                raise AuthorityObjectError(
                    "PD1B aggregate artifact byte bound exceeded"
                )
            payload = self._api.read(pinned.handle, pinned.spec.maximum_bytes)
            if type(payload) is not bytes or len(payload) != length:
                raise AuthorityObjectError("PD1B artifact changed during bounded read")
            self._read_bytes += length
            pinned.payload = payload
        return pinned.payload

    def names(self, path: str) -> tuple[str, ...]:
        pinned = self.pin(path)
        if pinned.spec.kind is not AuthorityObjectKind.DIRECTORY:
            raise AuthorityObjectError("PD1B inventory requires a directory")
        names = self._api.names(pinned.handle, path, MAX_PAPER_V2_DIRECTORY_ENTRIES)
        if (
            type(names) is not tuple
            or len(names) > MAX_PAPER_V2_DIRECTORY_ENTRIES
            or any(
                type(name) is not str
                or not name
                or len(name) > 255
                or name in {".", ".."}
                or any(c in name for c in "\\/:\x00")
                for name in names
            )
            or len({name.casefold() for name in names}) != len(names)
        ):
            raise AuthorityObjectError(
                "PD1B inventory contains unsafe names/collisions"
            )
        if pinned.names is not None and set(names) != set(pinned.names):
            raise AuthorityObjectError("PD1B inventory changed during pinned read")
        pinned.names = names
        return names

    def finish(self) -> None:
        """Reread pinned content/security and independently reopen every exact name."""
        if self._closed:
            raise AuthorityObjectError("PD1B read session is closed")
        for path, pinned in self._objects.items():
            current = self._api.inspect(pinned.handle, path, pinned.spec.kind)
            self._check(path, pinned.spec, current)
            if current != pinned.observation:
                raise AuthorityObjectError("PD1B pinned identity/security drift")
            reopened = self._api.open(path, pinned.spec.kind)
            try:
                if self._api.inspect(reopened, path, pinned.spec.kind) != current:
                    raise AuthorityObjectError("PD1B named object was replaced")
            finally:
                self._api.close(reopened)
            if (
                pinned.payload is not None
                and self._api.read(pinned.handle, pinned.spec.maximum_bytes)
                != pinned.payload
            ):
                raise AuthorityObjectError("PD1B pinned content drift")
            if pinned.names is not None:
                self.names(path)
