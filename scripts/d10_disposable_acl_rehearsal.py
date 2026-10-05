"""Explicit disposable NTFS rehearsal for D10 ACL creation and readback.

Importing this module has no host effect. Running it needs --run and a fresh,
operator-chosen root directly under F:\\AI\\temp; it never touches production.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import ntpath
import re
from ctypes import wintypes
from dataclasses import asdict

from scripts.d10_protected_deployment import (
    DeploymentBlocked,
    require_native_object,
)
from scripts.d10_protected_deployment_windows import WindowsDeploymentBackend

_DISPOSABLE_PREFIX = "F:\\AI\\temp\\p124-acl-rehearsal-"


def require_disposable_root(root: str) -> str:
    """Accept one direct child of the fixed disposable parent, never production."""
    if (
        type(root) is not str
        or not root.startswith(_DISPOSABLE_PREFIX)
        or ntpath.normpath(root) != root
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{7,63}", root[len(_DISPOSABLE_PREFIX) :])
    ):
        raise DeploymentBlocked("disposable_rehearsal_path_unreviewed")
    return root


class _DisposableBackend(WindowsDeploymentBackend):
    def __init__(self, root: str) -> None:
        self.root = require_disposable_root(root)
        self.installing_dir = root + r"\directory.installing"
        self.final_dir = root + r"\directory.final"
        self.installing_file = self.installing_dir + r"\file.installing"
        self.staged_file = self.installing_dir + r"\file.final"
        self.final_file = self.final_dir + r"\file.final"
        super().__init__()

    def _open_absence(self, path: str) -> int:
        if path != self.root:
            raise DeploymentBlocked("disposable_rehearsal_absence_path_unreviewed")
        create = self._bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            wintypes.HANDLE,
        )
        return create(
            path,
            0x80,
            1,
            None,
            3,
            0x00200000 | 0x02000000,  # no-follow, directory-capable
            None,
        )

    def _allowed_directory_create(self, path: str) -> bool:
        return path in {self.root, self.installing_dir}

    def _allowed_file_create(self, path: str) -> bool:
        return path == self.installing_file

    def _allowed_object_path(self, path: str, *, directory: bool) -> bool:
        allowed = (
            {self.root, self.installing_dir, self.final_dir}
            if directory
            else {self.installing_file, self.staged_file, self.final_file}
        )
        return path in allowed and ntpath.normpath(path) == path

    def publish_create_only(self, installing_path: str, final_path: str) -> None:
        if (installing_path, final_path) not in {
            (self.installing_file, self.staged_file),
            (self.installing_dir, self.final_dir),
        }:
            raise DeploymentBlocked("disposable_rehearsal_rename_unreviewed")
        move = self._bind(
            self._kernel,
            "MoveFileW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p],
            wintypes.BOOL,
        )
        if not move(installing_path, final_path):
            raise DeploymentBlocked("disposable_rehearsal_create_only_rename_failed")

    def report(self, path: str, *, directory: bool) -> dict[str, object]:
        handle = self._open_existing(path, directory=directory)
        try:
            before = self._inspect(handle)
            item = self._native_facts(path, before)
            require_native_object(item, path, directory=directory)
            after = self._inspect(handle)
            if before != after:
                raise DeploymentBlocked("disposable_rehearsal_identity_drift")
            return asdict(item)
        finally:
            self._close_handle(handle)


def rehearse(root: str) -> dict[str, object]:
    """Create only new disposable objects, then report exact persisted facts."""
    backend = _DisposableBackend(require_disposable_root(root))
    backend.require_administrator()
    backend.require_absent(backend.root)
    backend.create_directory(backend.root)
    root_facts = backend.report(backend.root, directory=True)
    backend.create_directory(backend.installing_dir)
    backend.create_file(backend.installing_file, b"D10 disposable ACL rehearsal\n")
    staged = (
        backend.report(backend.installing_dir, directory=True),
        backend.report(backend.installing_file, directory=False),
    )
    backend.publish_create_only(backend.installing_file, backend.staged_file)
    backend.report(backend.staged_file, directory=False)
    backend.publish_create_only(backend.installing_dir, backend.final_dir)
    final = (
        backend.report(backend.root, directory=True),
        backend.report(backend.final_dir, directory=True),
        backend.report(backend.final_file, directory=False),
    )
    if root_facts["volume_serial"] != final[0]["volume_serial"] or any(
        row["volume_serial"] != final[0]["volume_serial"] for row in (*staged, *final)
    ):
        raise DeploymentBlocked("disposable_rehearsal_volume_identity_drift")
    return {"root": root, "staged": staged, "final": final, "create_only_renames": 2}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(rehearse(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
