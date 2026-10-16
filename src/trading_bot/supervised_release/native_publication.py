"""AJ-only fixed preserved-image rename; no materializer or installer capability."""

from __future__ import annotations

import ctypes

from trading_bot.supervised_release import installation_reconciliation as incident
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

STAGING_IDENTITY = (1855336320, 281474980566367)


class PublicationSession(WindowsReadSession):
    """Fixed namespaces only; inherited OPEN_EXISTING read handles, no creation."""

    def __init__(self) -> None:
        super().__init__(ReleasePaths(incident.EXPECTED_RELEASE_ID))
        self.publication_requested = False

    def directory_access(self, path: str) -> int:
        if path == RELEASES_BASE:
            return 0x12008D
        if path == self.paths.staging:
            return 0x130089
        return super().directory_access(path)

    def publish(self) -> bool:
        if self.publication_requested:
            raise NativeObservationError("one publication request only")
        self.publication_requested = True
        parent = observe_parent(self)
        staging = check_object(
            self.object(self.paths.staging, directory=True),
            self.paths.staging,
            directory=True,
            volume=parent.identity[0],
        )
        if (
            parent.identity != incident.EXPECTED_PARENT_IDENTITY
            or staging.identity != STAGING_IDENTITY
            or self.object(self.paths.final, directory=True) is not None
        ):
            raise NativeObservationError("fixed publication objects rejected")
        handle = self.handles.pop(self.paths.staging)
        try:

            class Rename(ctypes.Structure):
                _fields_ = [
                    ("replace", ctypes.c_ubyte),
                    ("root", ctypes.c_void_p),
                    ("length", ctypes.c_uint32),
                    ("name", ctypes.c_uint16 * 1),
                ]

            encoded = self.paths.release_id.encode("utf-16-le")
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
    """One no-replace request, then close; caller owns independent FINAL replay."""
    incident.validate_incident_image(evidence, image_identity=STAGING_IDENTITY)
    incident.require_administrator_host()
    session = PublicationSession()
    try:
        return session.publish()
    finally:
        session.close()
