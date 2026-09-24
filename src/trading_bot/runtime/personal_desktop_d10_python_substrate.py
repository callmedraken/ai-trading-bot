"""Pure A124-4 qualification model. No production host access or authority."""

from __future__ import annotations

import ntpath
from dataclasses import dataclass
from enum import StrEnum

VOLUME = "F:\\"
ROOT = r"F:\AITradingBot"
RUNTIME = ROOT + r"\runtime"
PYTHON = RUNTIME + r"\python.exe"
LIB = RUNTIME + r"\Lib"
DLLS = RUNTIME + r"\DLLs"
SITE_PACKAGES = LIB + r"\site-packages"
ZIP = RUNTIME + r"\python314.zip"
VERSION = "3.14.3"
SYSTEM32 = r"C:\Windows\System32"
MUTATION_MASK = 0x000D0156
TRADING = "S-1-5-21-1397534616-3988210162-180023805-1009"
ADMIN = "S-1-5-32-544"
SYSTEM = "S-1-5-18"
ALL_ACCESS = 0x001F01FF
FILE_READ = 0x00120089
FILE_READ_EXECUTE = FILE_READ | 0x00000020
DIRECTORY_READ = 0x001200A9
FLAGS = ("-I", "-S", "-B", "-X", r"pycache_prefix=F:\AITradingBot\D10\no-pycache")
CONFIG_NAMES = (
    ROOT + r"\pyvenv.cfg",
    RUNTIME + r"\pyvenv.cfg",
    RUNTIME + r"\python._pth",
    RUNTIME + r"\python3._pth",
    RUNTIME + r"\python314._pth",
)
REQUIRED = frozenset((VOLUME, ROOT, RUNTIME, PYTHON, LIB, SITE_PACKAGES))


class SubstrateBlocked(ValueError):
    """Observed substrate cannot be accepted."""


class Kind(StrEnum):
    DIRECTORY = "directory"
    FILE = "file"


@dataclass(frozen=True, slots=True)
class Ace:
    sid: str
    mask: int
    ace_type: int = 0
    flags: int = 0


@dataclass(frozen=True, slots=True)
class ObjectEvidence:
    path: str
    final_path: str
    kind: Kind
    owner_sid: str
    dacl_protected: bool
    aces: tuple[Ace, ...]
    reparse: bool
    drive_type: int
    volume_root: str
    filesystem: str
    volume_serial: int
    file_index: int
    links: int
    children: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportEvidence:
    executable: str
    prefix: str
    base_prefix: str
    version: str
    flags: tuple[str, ...]
    isolated: bool
    no_site: bool
    dont_write_bytecode: bool
    pycache_prefix: str
    sys_path: tuple[str, ...]
    loaded_runtime_files: tuple[str, ...]
    # Windows KnownDLL/system DLL evidence is separately reviewed at P124-1.
    loaded_system_dlls: tuple[str, ...]
    purelib: str
    platlib: str
    site_main_called: bool
    pth_processed: bool


@dataclass(frozen=True, slots=True)
class TradingAccessEvidence:
    path: str
    tested_mask: int
    granted_mask: int
    rename_replace_denied: bool


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    objects: tuple[ObjectEvidence, ...]
    imports: ImportEvidence
    absent_configuration: tuple[str, ...]
    absent_search_roots: tuple[str, ...]
    signed_a123_python: str
    signed_a123_version: str
    trading_token_sid: str
    trading_token_non_admin: bool
    native_no_follow: bool
    native_pinned_and_rechecked: bool
    # The protected collector must prove actual effective Trading denial of
    # create/write/append/delete/delete-child/rename/WRITE_DAC/WRITE_OWNER
    # on every admitted object and its parents.
    trading_access: tuple[TradingAccessEvidence, ...]
    # These flags attest complete protected P124-1 observations, not just
    # successful parsing of whatever rows a collector happened to return.
    system_dlls_reviewed: bool
    system_dll_transcript_complete: bool
    runtime_dependency_transcript_complete: bool


@dataclass(frozen=True, slots=True)
class QualificationResult:
    """Sanitized description only; no handle, token or reusable authority."""

    python: str
    version: str
    runtime: str
    site_packages: str
    import_roots: tuple[str, ...]
    protected_object_count: int


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise SubstrateBlocked(reason)


def _canonical(path: str) -> bool:
    if type(path) is not str or not path.startswith(VOLUME):
        return False
    if path != ntpath.normpath(path) or path.startswith("\\\\"):
        return False
    parts = path[3:].split("\\")
    return (
        all(
            part not in ("", ".", "..")
            and not part.endswith((" ", "."))
            and ":" not in part
            for part in parts
        )
        if path != VOLUME
        else True
    )


def _expected_aces(kind: Kind) -> tuple[Ace, ...]:
    read = DIRECTORY_READ if kind is Kind.DIRECTORY else FILE_READ_EXECUTE
    return (Ace(ADMIN, ALL_ACCESS), Ace(SYSTEM, ALL_ACCESS), Ace(TRADING, read))


def qualify_python_substrate(evidence: QualificationEvidence) -> QualificationResult:
    """Evaluate read-only observations from the later protected P124-1 collector."""
    _require(type(evidence) is QualificationEvidence, "evidence type")
    _require(
        evidence.native_no_follow and evidence.native_pinned_and_rechecked,
        "native collection proof absent",
    )
    _require(
        evidence.trading_token_sid == TRADING and evidence.trading_token_non_admin,
        "Trading identity differs",
    )
    _require(
        evidence.signed_a123_python == PYTHON
        and evidence.signed_a123_version == VERSION,
        "signed A123 Python identity differs",
    )
    _require(type(evidence.objects) is tuple, "object inventory type")
    by_path: dict[str, ObjectEvidence] = {}
    for item in evidence.objects:
        _require(type(item) is ObjectEvidence, "object fact type")
        path = item.path
        _require(
            _canonical(path)
            and path == item.final_path
            and path.casefold() not in by_path
            and (path in (VOLUME, ROOT, RUNTIME) or path.startswith(RUNTIME + "\\")),
            "path identity or final path differs",
        )
        _require(
            item.reparse is False
            and item.drive_type == 3
            and item.volume_root == VOLUME
            and item.filesystem == "NTFS"
            and type(item.volume_serial) is int
            and item.volume_serial > 0
            and type(item.file_index) is int
            and item.file_index > 0,
            "local NTFS no-follow identity differs",
        )
        if path != VOLUME:
            _require(
                item.owner_sid in (ADMIN, SYSTEM)
                and item.dacl_protected is True
                and item.aces == _expected_aces(item.kind),
                "owner or protected DACL differs",
            )
        else:
            # The existing volume root may have a broader host policy. Its
            # identity and actual Trading mutation denial are checked below.
            _require(
                type(item.owner_sid) is str
                and bool(item.owner_sid)
                and type(item.dacl_protected) is bool
                and type(item.aces) is tuple
                and all(type(ace) is Ace for ace in item.aces)
                and item.owner_sid != TRADING
                and not any(
                    ace.sid == TRADING
                    and ace.ace_type == 0
                    and ace.mask & (MUTATION_MASK | 0x50000000)
                    for ace in item.aces
                ),
                "volume parent security observation incomplete",
            )
        _require(
            item.links >= 1 and (item.kind is Kind.DIRECTORY or item.links == 1),
            "hard link or object kind differs",
        )
        _require(type(item.kind) is Kind, "object kind type")
        by_path[path.casefold()] = item

    _require(
        REQUIRED.issubset({item.path for item in evidence.objects}),
        "required runtime path missing",
    )
    for path in (VOLUME, ROOT, RUNTIME, LIB, SITE_PACKAGES):
        _require(
            by_path[path.casefold()].kind is Kind.DIRECTORY,
            "required directory differs",
        )
    _require(by_path[PYTHON.casefold()].kind is Kind.FILE, "interpreter file differs")
    serial = by_path[VOLUME.casefold()].volume_serial
    _require(
        all(item.volume_serial == serial for item in evidence.objects),
        "volume identity differs",
    )
    for item in evidence.objects:
        if item.kind is Kind.FILE:
            _require(not item.children, "file has child names")
            continue
        _require(
            type(item.children) is tuple
            and len(item.children) == len({name.casefold() for name in item.children}),
            "directory enumeration invalid",
        )
        if item.path == VOLUME:
            _require("AITradingBot" in item.children, "volume parent entry missing")
        elif item.path == ROOT:
            _require("runtime" in item.children, "root parent entry missing")
        else:
            actual = {ntpath.join(item.path, name).casefold() for name in item.children}
            expected = {
                path for path in by_path if ntpath.dirname(path) == item.path.casefold()
            }
            _require(actual == expected, "runtime subtree enumeration incomplete")
    _require(
        all(
            ntpath.dirname(item.path).casefold() in by_path
            for item in evidence.objects
            if item.path not in (VOLUME, ROOT)
        ),
        "parent is not protected",
    )
    _require(
        type(evidence.trading_access) is tuple
        and len(evidence.trading_access) == len(by_path)
        and all(
            type(entry) is TradingAccessEvidence for entry in evidence.trading_access
        )
        and {entry.path.casefold() for entry in evidence.trading_access} == set(by_path)
        and all(
            type(entry) is TradingAccessEvidence
            and entry.tested_mask == MUTATION_MASK
            and entry.granted_mask == 0
            and entry.rename_replace_denied is True
            for entry in evidence.trading_access
        ),
        "Trading mutation denial incomplete",
    )
    _require(
        type(evidence.absent_configuration) is tuple
        and set(evidence.absent_configuration) == set(CONFIG_NAMES)
        and len(evidence.absent_configuration) == len(CONFIG_NAMES)
        and not any(
            item.path.casefold().endswith(("._pth", r"\pyvenv.cfg"))
            for item in evidence.objects
        ),
        "startup configuration present or absence unproven",
    )
    imports = evidence.imports
    _require(type(imports) is ImportEvidence, "import observation type")
    _require(
        imports.executable == PYTHON
        and imports.prefix == RUNTIME
        and imports.base_prefix == RUNTIME
        and imports.version == VERSION
        and imports.flags == FLAGS
        and imports.isolated
        and imports.no_site
        and imports.dont_write_bytecode
        and imports.pycache_prefix == ROOT + r"\D10\no-pycache"
        and imports.purelib == SITE_PACKAGES
        and imports.platlib == SITE_PACKAGES
        and not imports.site_main_called
        and not imports.pth_processed,
        "interpreter startup differs",
    )
    _require(
        type(imports.sys_path) is tuple
        and bool(imports.sys_path)
        and len(imports.sys_path) == len(set(imports.sys_path))
        and all(path in (ZIP, DLLS, LIB, RUNTIME) for path in imports.sys_path)
        and LIB in imports.sys_path
        and SITE_PACKAGES not in imports.sys_path,
        "unreviewed import search root",
    )
    _require(
        type(evidence.absent_search_roots) is tuple
        and set(evidence.absent_search_roots).issubset({ZIP, DLLS})
        and len(evidence.absent_search_roots) == len(set(evidence.absent_search_roots)),
        "unreviewed absent search candidate",
    )
    for path, kind in ((ZIP, Kind.FILE), (DLLS, Kind.DIRECTORY)):
        present = path.casefold() in by_path
        absent = path in evidence.absent_search_roots
        _require(
            present != absent, "optional search root state unproven or contradictory"
        )
        if present:
            item = by_path[path.casefold()]
            _require(
                item.path == path and item.kind is kind,
                "optional search root identity or kind differs",
            )
    for path in imports.sys_path:
        _require(
            path.casefold() in by_path or path in evidence.absent_search_roots,
            "search entry neither protected nor proven absent",
        )
    _require(
        type(imports.loaded_runtime_files) is tuple
        and evidence.runtime_dependency_transcript_complete is True
        and PYTHON in imports.loaded_runtime_files
        and len(imports.loaded_runtime_files) == len(set(imports.loaded_runtime_files))
        and all(
            _canonical(path)
            and path.casefold() in by_path
            and by_path[path.casefold()].kind is Kind.FILE
            for path in imports.loaded_runtime_files
        ),
        "loaded module or DLL outside protected runtime",
    )
    _require(
        type(imports.loaded_system_dlls) is tuple
        and evidence.system_dlls_reviewed is True
        and evidence.system_dll_transcript_complete is True
        and bool(imports.loaded_system_dlls)
        and len(imports.loaded_system_dlls) == len(set(imports.loaded_system_dlls))
        and all(
            type(path) is str
            and ntpath.dirname(path).casefold() == SYSTEM32.casefold()
            and ntpath.basename(path).casefold().endswith(".dll")
            for path in imports.loaded_system_dlls
        ),
        "Windows DLL proof absent or path unreviewed",
    )
    return QualificationResult(
        PYTHON, VERSION, RUNTIME, SITE_PACKAGES, imports.sys_path, len(by_path)
    )
