"""Bounded immutable release images and deterministic, externally pinned verification.

Object facts are evidence supplied by a future observer, not native ACL proof.
Completeness is checked against a separately admitted source namespace.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass

from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    ReleaseInventoryEntry,
    ReleaseManifest,
)

BUNDLE_SCHEMA = "arch133-supervised-release-bundle/v1"
MAX_FILES = 10000
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_BUNDLE_BYTES = 64 * 1024 * 1024


def canonical_json(value: object) -> str:
    """The canonical transport spelling; never a new domain identity input."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def source_name(name: str) -> str:
    """Admit only the frozen complete-runtime policy and foundation path rules."""
    ReleaseInventoryEntry(name, "0" * 64)
    if name not in {"pyproject.toml", LAUNCHER_RELATIVE_PATH} and not (
        name.startswith("src/trading_bot/")
        and name.endswith((".py", ".json", ".sql"))
        and not any(
            part.startswith(".") or part == "__pycache__" for part in name.split("/")
        )
    ):
        raise ValueError("unsupported release material")
    return name


def source_namespace(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Require sorted unique canonical names, including project and launcher."""
    if type(paths) is not tuple or not 2 <= len(paths) <= MAX_FILES:
        raise ValueError("bounded immutable source namespace required")
    for path in paths:
        source_name(path)
    if (
        paths != tuple(sorted(paths))
        or len({path.casefold() for path in paths}) != len(paths)
        or "pyproject.toml" not in paths
        or LAUNCHER_RELATIVE_PATH not in paths
    ):
        raise ValueError("noncanonical or incomplete source namespace")
    return paths


@dataclass(frozen=True, slots=True)
class ReleaseFile:
    relative_path: str
    data: bytes
    object_type: str = "regular"
    is_symlink: bool = False
    is_reparse: bool = False

    def __post_init__(self) -> None:
        if type(self.relative_path) is not str:
            raise ValueError("exact relative path text required")
        if self.relative_path != "manifest.json":
            source_name(self.relative_path)
        if type(self.data) is not bytes or len(self.data) > MAX_FILE_BYTES:
            raise ValueError("bounded immutable file bytes required")
        if (
            self.object_type != "regular"
            or type(self.object_type) is not str
            or type(self.is_symlink) is not bool
            or type(self.is_reparse) is not bool
            or self.is_symlink
            or self.is_reparse
        ):
            raise ValueError("regular non-symlink non-reparse file required")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True, slots=True)
class ReleaseBundle:
    files: tuple[ReleaseFile, ...]

    def __post_init__(self) -> None:
        if type(self.files) is not tuple or not 3 <= len(self.files) <= MAX_FILES + 1:
            raise ValueError("bounded immutable release files required")
        if any(type(item) is not ReleaseFile for item in self.files):
            raise ValueError("exact release files required")
        if sum(len(item.data) for item in self.files) > MAX_BUNDLE_BYTES:
            raise ValueError("release byte budget exceeded")
        names = tuple(item.relative_path for item in self.files)
        if names != tuple(sorted(names)) or len({n.casefold() for n in names}) != len(
            names
        ):
            raise ValueError("sorted unique release names required")
        if names.count("manifest.json") != 1:
            raise ValueError("exactly one canonical manifest required")
        source_namespace(tuple(n for n in names if n != "manifest.json"))

    def to_json(self) -> str:
        return canonical_json(
            {
                "schema": BUNDLE_SCHEMA,
                "files": [
                    {
                        "relative_path": item.relative_path,
                        "data_base64": base64.b64encode(item.data).decode("ascii"),
                        "object_type": item.object_type,
                        "is_symlink": item.is_symlink,
                        "is_reparse": item.is_reparse,
                    }
                    for item in self.files
                ],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> ReleaseBundle:
        """Decode canonical bounded transport; verification still requires pins."""
        if type(text) is not str or len(text) > MAX_BUNDLE_BYTES * 2:
            raise ValueError("bounded bundle JSON required")
        try:
            raw = json.loads(text)
            if (
                type(raw) is not dict
                or set(raw) != {"schema", "files"}
                or raw["schema"] != BUNDLE_SCHEMA
            ):
                raise ValueError("invalid bundle schema")
            if type(raw["files"]) is not list or len(raw["files"]) > MAX_FILES + 1:
                raise ValueError("bounded file array required")
            files = []
            for item in raw["files"]:
                if type(item) is not dict or set(item) != {
                    "relative_path",
                    "data_base64",
                    "object_type",
                    "is_symlink",
                    "is_reparse",
                }:
                    raise ValueError("exact file fields required")
                if (
                    type(item["data_base64"]) is not str
                    or len(item["data_base64"]) > MAX_FILE_BYTES * 2
                ):
                    raise ValueError("bounded base64 bytes required")
                data = base64.b64decode(item["data_base64"], validate=True)
                files.append(
                    ReleaseFile(
                        item["relative_path"],
                        data,
                        item["object_type"],
                        item["is_symlink"],
                        item["is_reparse"],
                    )
                )
            result = cls(tuple(files))
            if result.to_json() != text:
                raise ValueError("noncanonical bundle JSON")
            return result
        except (KeyError, TypeError, UnicodeError) as exc:
            raise ValueError("malformed bundle") from exc


@dataclass(frozen=True, slots=True)
class VerifiedRelease:
    """Replayable verified evidence; constructor validates against external pins.

    Pins must come from reviewed source authority, never the image under test.
    This is integrity evidence, not a signature or installed-host observation.
    """

    bundle: ReleaseBundle
    expected_manifest_sha256: str
    expected_source_head: str
    expected_source_tree: str
    expected_source_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.bundle) is not ReleaseBundle:
            raise ValueError("exact bundle required")
        if any(
            type(pin) is not str
            for pin in (
                self.expected_manifest_sha256,
                self.expected_source_head,
                self.expected_source_tree,
            )
        ):
            raise ValueError("exact source authority text required")
        expected = source_namespace(self.expected_source_paths)
        files = {item.relative_path: item for item in self.bundle.files}
        if set(files) != {"manifest.json", *expected}:
            raise ValueError("missing or extra release files")
        manifest_file = files["manifest.json"]
        if manifest_file.sha256 != self.expected_manifest_sha256:
            raise ValueError("manifest hash mismatch")
        manifest = ReleaseManifest.from_json(manifest_file.data.decode("utf-8"))
        if manifest.to_json().encode("utf-8") != manifest_file.data:
            raise ValueError("noncanonical manifest bytes")
        if (manifest.source_head, manifest.source_tree) != (
            self.expected_source_head,
            self.expected_source_tree,
        ):
            raise ValueError("source HEAD/tree mismatch")
        inventory = tuple(
            ReleaseInventoryEntry(path, files[path].sha256) for path in expected
        )
        if inventory != manifest.source_inventory:
            raise ValueError("source inventory names/order/bytes mismatch")
        if files[LAUNCHER_RELATIVE_PATH].sha256 != manifest.launcher_sha256:
            raise ValueError("launcher mismatch")

    @property
    def manifest(self) -> ReleaseManifest:
        item = next(
            item for item in self.bundle.files if item.relative_path == "manifest.json"
        )
        return ReleaseManifest.from_json(item.data.decode("utf-8"))


def verify_release_bundle(
    bundle: ReleaseBundle,
    *,
    expected_manifest_sha256: str,
    expected_source_head: str,
    expected_source_tree: str,
    expected_source_paths: tuple[str, ...],
) -> VerifiedRelease:
    """Verify all bytes, facts and identities without reading a host filesystem."""
    return VerifiedRelease(
        bundle,
        expected_manifest_sha256,
        expected_source_head,
        expected_source_tree,
        expected_source_paths,
    )
