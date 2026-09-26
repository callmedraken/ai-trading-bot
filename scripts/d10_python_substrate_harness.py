"""Source-only P124-1 collector and strict A124-4 evidence assembly.

Importing this module performs no host inspection. Production paths are fixed
by the frozen qualification model. Native observations belong to the protected
administrator and actual non-admin Trading phases of a later run.
"""

from __future__ import annotations

import dataclasses
import json
import ntpath
from dataclasses import dataclass
from typing import Protocol

from trading_bot.runtime import personal_desktop_d10_python_substrate as q

SCHEMA = "personal-desktop-p124-1-native-transcript/v3"
MAX_OBJECTS = 100_000
MAX_DEPENDENCIES = 4_096
MAX_TRANSCRIPT_BYTES = 32 * 1024 * 1024
GUARD_IMPORTS = (
    "contextlib",
    "ctypes",
    "dataclasses",
    "datetime",
    "hashlib",
    "json",
    "ntpath",
    "os",
    "re",
    "subprocess",
    "sys",
    "uuid",
)
_DOS_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)


class CollectionBlocked(ValueError):
    """A required native observation is missing, changing, or rejected."""


@dataclass(frozen=True, slots=True)
class NativeObject:
    evidence: q.ObjectEvidence
    attributes: int
    ace_count: int
    parent_file_index: int | None


@dataclass(frozen=True, slots=True)
class NativeSnapshot:
    objects: tuple[NativeObject, ...]
    absent_configuration: tuple[str, ...]
    absent_search_roots: tuple[str, ...]
    no_follow: bool
    pinned_and_rechecked: bool
    inventory_complete: bool


@dataclass(frozen=True, slots=True)
class TokenObservation:
    sid: str
    non_admin: bool
    elevated: bool
    enabled_groups: tuple[str, ...]
    enabled_privileges: tuple[str, ...]
    groups_complete: bool
    privileges_complete: bool


@dataclass(frozen=True, slots=True)
class NativeAccess:
    evidence: q.TradingAccessEvidence
    access_check_succeeded: bool
    mutation_access_status: bool
    # DELETE on the volume object may succeed; protected objects must deny it.
    rename_access_status: bool
    # Parent FILE_DELETE_CHILD must deny replacement in both policies.
    replace_access_status: bool
    token_groups_accounted: bool
    token_privileges_accounted: bool
    acl_agrees: bool


@dataclass(frozen=True, slots=True)
class TradingObservation:
    token: TokenObservation
    access: tuple[NativeAccess, ...]


@dataclass(frozen=True, slots=True)
class Dependency:
    name: str
    origin: str
    final_path: str | None
    category: str


@dataclass(frozen=True, slots=True)
class RuntimeModulePath:
    reported_path: str
    final_path: str


@dataclass(frozen=True, slots=True)
class Diagnostic:
    imports: q.ImportEvidence
    argv: tuple[str, ...]
    dependencies: tuple[Dependency, ...]
    guard_imports_covered: tuple[str, ...]
    runtime_files_complete: bool
    site_hooks_not_processed: bool
    runtime_mappings: tuple[RuntimeModulePath, ...] = ()


@dataclass(frozen=True, slots=True)
class SystemDll:
    path: str
    final_path: str
    owner_sid: str
    dacl_protected: bool
    aces: tuple[q.Ace, ...]
    trading_mutation_granted: int
    access_check_succeeded: bool
    rename_replace_denied: bool
    direct_system32_child: bool


@dataclass(frozen=True, slots=True)
class SystemDllObservation:
    parent: q.ObjectEvidence
    parent_access: q.TradingAccessEvidence
    dlls: tuple[SystemDll, ...]
    complete: bool
    reviewed: bool
    known_dlls_complete: bool


@dataclass(frozen=True, slots=True)
class SignedA123Identity:
    """Output of the protected detached-signature verifier, never caller JSON."""

    python: str
    version: str
    attestation_sha256: str
    signature_verified: bool
    signing_key_id_verified: bool


class Collector(Protocol):
    """An implementation owns each observation, including signature proof."""

    def inventory(self) -> NativeSnapshot: ...
    def trading(self, paths: tuple[str, ...]) -> TradingObservation: ...
    def diagnostic(self) -> Diagnostic: ...
    def system_dlls(self, paths: tuple[str, ...]) -> SystemDllObservation: ...
    def signed_a123_identity(self) -> SignedA123Identity: ...


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CollectionBlocked(reason)


def _valid_reported_path(path: str, root: str, *, direct_child: bool = False) -> bool:
    if (
        type(path) is not str
        or path.startswith("\\\\")
        or path != ntpath.normpath(path)
        or not path.casefold().startswith(root.casefold() + "\\")
    ):
        return False
    parts = path[len(root) + 1 :].split("\\")
    if not parts or (direct_child and len(parts) != 1):
        return False
    for part in parts:
        stem = part.split(".", 1)[0].casefold()
        numbered_device = (
            len(stem) == 4
            and stem[:3] in ("com", "lpt")
            and (stem[3].isdigit() or stem[3] in "¹²³")
        )
        if (
            part in ("", ".", "..")
            or ":" in part
            or part.endswith((" ", "."))
            or stem in _DOS_DEVICE_NAMES
            or numbered_device
        ):
            return False
    return True


def _valid_runtime_path(path: str) -> bool:
    return _valid_reported_path(path, q.RUNTIME)


def _valid_system32_path(path: str) -> bool:
    return _valid_reported_path(path, q.SYSTEM32, direct_child=True) and (
        ntpath.basename(path).casefold().endswith(".dll")
    )


def _same_path_modulo_case(left: str, right: str) -> bool:
    return ntpath.normcase(ntpath.normpath(left)) == ntpath.normcase(
        ntpath.normpath(right)
    )


def _zip_module_origin(path: str) -> bool:
    return _valid_runtime_path(path) and path.casefold().startswith(
        q.ZIP.casefold() + "\\"
    )


def _objects(snapshot: NativeSnapshot) -> tuple[q.ObjectEvidence, ...]:
    _require(type(snapshot) is NativeSnapshot, "snapshot type")
    _require(
        snapshot.no_follow is True
        and snapshot.pinned_and_rechecked is True
        and snapshot.inventory_complete is True,
        "native inventory proof incomplete",
    )
    _require(0 < len(snapshot.objects) <= MAX_OBJECTS, "object count bound")
    by_path: dict[str, q.ObjectEvidence] = {}
    for row in snapshot.objects:
        _require(type(row) is NativeObject, "object row type")
        item = row.evidence
        _require(type(item) is q.ObjectEvidence, "object evidence type")
        _require(item.path == item.final_path, "final path differs")
        _require(row.ace_count == len(item.aces), "ACE inventory incomplete")
        _require(
            type(row.attributes) is int
            and row.attributes >= 0
            and bool(row.attributes & 0x10) == (item.kind is q.Kind.DIRECTORY)
            and bool(row.attributes & 0x400) == item.reparse,
            "native attributes, kind, or reparse state differs",
        )
        key = item.path.casefold()
        _require(key not in by_path, "case-colliding object")
        by_path[key] = item
    for row in snapshot.objects:
        item = row.evidence
        if item.path != q.VOLUME:
            parent = by_path.get(ntpath.dirname(item.path).casefold())
            _require(
                parent is not None and row.parent_file_index == parent.file_index,
                "pinned parent identity differs",
            )
        if item.kind is q.Kind.DIRECTORY:
            _require(
                len(item.children) == len({name.casefold() for name in item.children}),
                "case-colliding child names",
            )
    return tuple(row.evidence for row in snapshot.objects)


def _access(
    observation: TradingObservation, paths: set[str]
) -> tuple[q.TradingAccessEvidence, ...]:
    _require(type(observation) is TradingObservation, "Trading observation type")
    token = observation.token
    _require(
        type(token) is TokenObservation
        and token.sid == q.TRADING
        and token.non_admin is True
        and token.elevated is False
        and token.groups_complete is True
        and token.privileges_complete is True
        and q.ADMIN not in token.enabled_groups
        and "SeChangeNotifyPrivilege" in token.enabled_privileges,
        "actual non-admin Trading token or bypass-traverse privilege unproven",
    )
    _require(len(observation.access) == len(paths), "Trading coverage count")
    seen: set[str] = set()
    for row in observation.access:
        _require(type(row) is NativeAccess, "AccessCheck row type")
        path = row.evidence.path.casefold()
        _require(path in paths and path not in seen, "AccessCheck path coverage")
        seen.add(path)
        _require(
            q.trading_access_denied(row.evidence)
            and row.access_check_succeeded is True
            and row.mutation_access_status is False
            and (
                row.evidence.policy is q.AccessPolicy.VOLUME_NAMESPACE
                or row.rename_access_status is False
            )
            and row.replace_access_status is False
            and row.token_groups_accounted is True
            and row.token_privileges_accounted is True
            and row.acl_agrees is True,
            "Trading mutation or rename/replace denial unproven",
        )
    _require(seen == paths, "Trading coverage differs")
    return tuple(row.evidence for row in observation.access)


def _diagnostic(value: Diagnostic) -> q.ImportEvidence:
    _require(type(value) is Diagnostic, "diagnostic type")
    _require(
        value.argv == (q.PYTHON, *q.FLAGS, "-c")
        and value.runtime_files_complete is True
        and value.site_hooks_not_processed is True
        and value.guard_imports_covered == GUARD_IMPORTS,
        "diagnostic invocation or coverage incomplete",
    )
    _require(0 < len(value.dependencies) <= MAX_DEPENDENCIES, "dependency bound")
    names: set[str] = set()
    runtime_files: set[str] = set()
    for row in value.dependencies:
        _require(type(row) is Dependency and row.name not in names, "dependency row")
        names.add(row.name)
        _require(row.category in ("builtin", "frozen", "runtime"), "dependency kind")
        if row.category in ("builtin", "frozen"):
            _require(
                row.origin == row.category and row.final_path is None,
                "builtin/frozen origin",
            )
        else:
            origin_is_runtime = _valid_runtime_path(row.origin)
            final_is_runtime = _valid_runtime_path(row.final_path)
            ordinary_path_matches = (
                origin_is_runtime
                and final_is_runtime
                and _same_path_modulo_case(row.origin, row.final_path)
            )
            zip_path_matches = (
                _zip_module_origin(row.origin)
                and final_is_runtime
                and _same_path_modulo_case(row.final_path, q.ZIP)
            )
            _require(
                row.final_path is not None
                and final_is_runtime
                and (ordinary_path_matches or zip_path_matches),
                "runtime dependency final path",
            )
            runtime_files.add(row.final_path)
    _require(
        type(value.runtime_mappings) is tuple
        and bool(value.runtime_mappings)
        and len(value.runtime_mappings) <= MAX_DEPENDENCIES
        and all(
            type(row) is RuntimeModulePath
            and _valid_runtime_path(row.reported_path)
            and _valid_runtime_path(row.final_path)
            and _same_path_modulo_case(row.reported_path, row.final_path)
            for row in value.runtime_mappings
        ),
        "runtime loader path transcript invalid",
    )
    _require(
        any(
            _same_path_modulo_case(row.final_path, q.PYTHON)
            for row in value.runtime_mappings
        ),
        "fixed interpreter loader mapping absent",
    )
    _require(
        {row.final_path.casefold() for row in value.runtime_mappings}.issubset(
            {path.casefold() for path in value.imports.loaded_runtime_files}
        ),
        "runtime loader final path omitted from dependency inventory",
    )
    _require(set(GUARD_IMPORTS).issubset(names), "guard import transcript incomplete")
    _require(
        runtime_files.issubset(set(value.imports.loaded_runtime_files))
        and q.PYTHON in value.imports.loaded_runtime_files,
        "runtime file transcript incomplete",
    )
    return value.imports


def _system_dlls(value: SystemDllObservation, imports: q.ImportEvidence) -> None:
    _require(type(value) is SystemDllObservation, "System32 observation type")
    _require(
        value.complete is True
        and value.reviewed is True
        and value.known_dlls_complete is True
        and bool(value.dlls),
        "System32/KnownDLL transcript incomplete",
    )
    parent = value.parent
    parent_access = value.parent_access
    _require(
        type(parent) is q.ObjectEvidence
        and parent.path == q.SYSTEM32
        and parent.final_path == q.SYSTEM32
        and parent.kind is q.Kind.DIRECTORY
        and parent.reparse is False
        and parent.drive_type == 3
        and parent.volume_root == "C:\\"
        and parent.filesystem == "NTFS"
        and parent.owner_sid != q.TRADING
        and bool(parent.owner_sid)
        and parent.dacl_protected is True
        and bool(parent.aces)
        and type(parent_access) is q.TradingAccessEvidence
        and parent_access.path == q.SYSTEM32
        and parent_access.tested_mask == q.MUTATION_MASK
        and parent_access.granted_mask == 0
        and parent_access.rename_replace_denied is True,
        "System32 parent security or Trading denial differs",
    )
    paths = {row.path for row in value.dlls}
    _require(
        len(paths) == len(value.dlls)
        and len({path.casefold() for path in paths}) == len(paths)
        and paths == set(imports.loaded_system_dlls),
        "System32 loaded-DLL inventory differs",
    )
    for row in value.dlls:
        _require(
            type(row) is SystemDll
            and _valid_system32_path(row.path)
            and _valid_system32_path(row.final_path)
            and _same_path_modulo_case(row.path, row.final_path)
            and row.owner_sid != q.TRADING
            and bool(row.owner_sid)
            and bool(row.aces)
            and row.dacl_protected is True
            and row.trading_mutation_granted == 0
            and row.access_check_succeeded is True
            and row.rename_replace_denied is True
            and row.direct_system32_child is True,
            "System32 DLL origin or security differs",
        )


def _plain(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _plain(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (q.Kind, q.AccessPolicy)):
        return value.value
    if type(value) in (str, int, bool) or value is None:
        return value
    raise CollectionBlocked("transcript contains native capability or unknown type")


def canonical_transcript(value: dict[str, object]) -> bytes:
    """Stable JSON with no handles, tokens, or native capability objects."""
    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "status",
            "before",
            "trading",
            "diagnostic",
            "system_dlls",
            "after",
            "signed_a123",
            "qualification",
        }
        and value["schema"] == SCHEMA
        and value["status"] == "PASS",
        "transcript schema or field set differs",
    )
    raw = json.dumps(
        _plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    _require(len(raw) <= MAX_TRANSCRIPT_BYTES, "transcript size bound")
    return raw + b"\n"


def _ordered_snapshot(snapshot: NativeSnapshot) -> NativeSnapshot:
    """Only set-like transcript fields are sorted; ACE and sys.path order remain."""
    rows = tuple(
        sorted(
            (
                dataclasses.replace(
                    row,
                    evidence=dataclasses.replace(
                        row.evidence,
                        children=tuple(sorted(row.evidence.children)),
                    ),
                )
                for row in snapshot.objects
            ),
            key=lambda row: row.evidence.path,
        )
    )
    return dataclasses.replace(
        snapshot,
        objects=rows,
        absent_configuration=tuple(sorted(snapshot.absent_configuration)),
        absent_search_roots=tuple(sorted(snapshot.absent_search_roots)),
    )


def collect(collector: Collector) -> bytes:
    """Collect, reobserve, then call the existing frozen qualification policy."""
    try:
        before = collector.inventory()
        _objects(before)
        before = _ordered_snapshot(before)
        ordered = tuple(row.evidence for row in before.objects)
        trading = collector.trading(tuple(item.path for item in ordered))
        access = _access(trading, {item.path.casefold() for item in ordered})
        trading = dataclasses.replace(
            trading,
            token=dataclasses.replace(
                trading.token,
                enabled_groups=tuple(sorted(trading.token.enabled_groups)),
                enabled_privileges=tuple(sorted(trading.token.enabled_privileges)),
            ),
            access=tuple(sorted(trading.access, key=lambda row: row.evidence.path)),
        )
        diagnostic = collector.diagnostic()
        imports = _diagnostic(diagnostic)
        imports = dataclasses.replace(
            imports,
            loaded_runtime_files=tuple(sorted(imports.loaded_runtime_files)),
            loaded_system_dlls=tuple(sorted(imports.loaded_system_dlls)),
        )
        diagnostic = dataclasses.replace(
            diagnostic,
            imports=imports,
            dependencies=tuple(
                sorted(diagnostic.dependencies, key=lambda row: row.name)
            ),
        )
        dlls = collector.system_dlls(imports.loaded_system_dlls)
        _system_dlls(dlls, imports)
        dlls = dataclasses.replace(
            dlls, dlls=tuple(sorted(dlls.dlls, key=lambda row: row.path))
        )
        after = collector.inventory()
        _objects(after)
        after = _ordered_snapshot(after)
        _require(before == after, "before/after native inventory drift")
        signed = collector.signed_a123_identity()
        _require(
            type(signed) is SignedA123Identity
            and signed.signature_verified is True
            and signed.signing_key_id_verified is True
            and len(signed.attestation_sha256) == 64
            and all(c in "0123456789abcdef" for c in signed.attestation_sha256),
            "signed A123 identity unverified",
        )
        evidence = q.QualificationEvidence(
            ordered,
            imports,
            before.absent_configuration,
            before.absent_search_roots,
            signed.python,
            signed.version,
            trading.token.sid,
            trading.token.non_admin,
            trading.token.elevated,
            trading.token.enabled_groups,
            trading.token.enabled_privileges,
            before.no_follow,
            before.pinned_and_rechecked,
            tuple(sorted(access, key=lambda item: item.path)),
            dlls.reviewed,
            dlls.complete,
            diagnostic.runtime_files_complete,
        )
        result = q.qualify_python_substrate(evidence)
        return canonical_transcript(
            {
                "schema": SCHEMA,
                "status": "PASS",
                "before": before,
                "trading": trading,
                "diagnostic": diagnostic,
                "system_dlls": dlls,
                "after": after,
                "signed_a123": signed,
                "qualification": result,
            }
        )
    except Exception as exc:
        raise CollectionBlocked(f"P124-1 collection blocked: {exc}") from exc
