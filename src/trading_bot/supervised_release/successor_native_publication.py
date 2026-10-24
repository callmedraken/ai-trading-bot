"""D1S3-R5-only handle-relative no-replace publication; no installer API."""

from __future__ import annotations

import ctypes

from trading_bot.supervised_release.installation_contract import (
    InstalledEvidence,
    ReleasePaths,
)
from trading_bot.supervised_release.model import RELEASES_BASE
from trading_bot.supervised_release.native_read import (
    NativeObservationError,
    WindowsReadSession,
    bind,
    close_native_handle,
)
from trading_bot.supervised_release.observer import check_object, observe_parent
from trading_bot.supervised_release.successor_publication_recovery import (
    FINAL_PATH,
    PARENT_IDENTITY,
    RELEASE_ID,
    STAGING_IDENTITY,
    STAGING_PATH,
    require_administrator,
    validate_image,
)


class PublicationSession(WindowsReadSession):
    """Only exact preserved handles gain rename rights; all opens OPEN_EXISTING."""

    def __init__(self) -> None:
        super().__init__(ReleasePaths(RELEASE_ID))
        self.publication_requested = False

    def directory_access(self, path: str) -> int:
        if path == RELEASES_BASE:
            return 0x12008D
        if path == STAGING_PATH:
            return 0x130089
        return super().directory_access(path)

    def publish(self) -> bool:
        if self.publication_requested:
            raise NativeObservationError("one publication request only")
        self.publication_requested = True
        if self.paths != ReleasePaths(RELEASE_ID):
            raise NativeObservationError("fixed publication paths required")
        parent = observe_parent(self)
        staging = check_object(
            self.object(STAGING_PATH, directory=True),
            STAGING_PATH,
            directory=True,
            volume=PARENT_IDENTITY[0],
        )
        if (
            parent.identity != PARENT_IDENTITY
            or staging.identity != STAGING_IDENTITY
            or self.object(FINAL_PATH, directory=True) is not None
            or self.object(FINAL_PATH, directory=False) is not None
        ):
            raise NativeObservationError("fixed publication objects rejected")
        handle = self.handles.pop(STAGING_PATH)
        try:

            class Rename(ctypes.Structure):
                _fields_ = [
                    ("replace", ctypes.c_ubyte),
                    ("root", ctypes.c_void_p),
                    ("length", ctypes.c_uint32),
                    ("name", ctypes.c_uint16 * 1),
                ]

            encoded = RELEASE_ID.encode("utf-16-le")
            size = Rename.name.offset + len(encoded)
            buffer = ctypes.create_string_buffer(size)
            record = ctypes.cast(buffer, ctypes.POINTER(Rename)).contents
            record.replace = 0
            record.root = self.handles[RELEASES_BASE]
            record.length = len(encoded)
            ctypes.memmove(
                ctypes.addressof(buffer) + Rename.name.offset, encoded, len(encoded)
            )
            return bool(
                bind(
                    self.kernel,
                    "SetFileInformationByHandle",
                    [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
                    ctypes.c_int32,
                )(handle, 3, buffer, size)
            )
        finally:
            close_native_handle(self.kernel, handle)


def publish_preserved_image(evidence: InstalledEvidence) -> bool:
    """One exact rename request; caller owns independent repeated final replay."""
    validate_image(evidence)
    require_administrator()
    session = PublicationSession()
    try:
        return session.publish()
    finally:
        session.close()
