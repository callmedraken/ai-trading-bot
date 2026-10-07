"""Fixed Q133-2 Win32 backend; no alternate roots or recovery API.

Reuse only A103's no-follow reader/pinned parent and binary security primitives.
No D10 provisioning, task, deployment, lease, or scheduler object is constructed.
The new root starts Administrator/SYSTEM-only; Trading admission is last.
"""

from __future__ import annotations

import ctypes
import hashlib
import subprocess
import sys
from collections.abc import Iterator
from contextlib import ExitStack, closing, contextmanager
from dataclasses import asdict
from pathlib import Path

from trading_bot.arch133_acl import primitive as root_acl
from trading_bot.review_paper import unattended_host_identity as identity
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation
from trading_bot.review_paper.unattended_publication import (
    FINAL_NAMES,
    MAX_MATERIAL_BYTES,
    TARGET_HEAD,
    TARGET_TREE,
    PublicationError,
)
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityAce,
    SecurityPolicy,
    WindowsHandle,
    apply_security_policy,
    build_security_attributes,
    require_administrator_token,
    require_security_policy,
    require_trading_standard_account,
    resolve_current_token_sid,
    sqlite_trading_file_rights,
)

PUBLISHER_BRANCH = "feature/robinhood-unattended-review-paper-133h"
PUBLISHER_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133h")
PUBLISHER_LAUNCHER = PUBLISHER_ROOT / "scripts" / "run_arch133_host_publication.py"
ADMIN_POLICY = SecurityPolicy(
    security.ADMINISTRATORS_SID,
    (
        SecurityAce(security.ADMINISTRATORS_SID, security.FILE_ALL_ACCESS),
        SecurityAce(security.SYSTEM_SID, security.FILE_ALL_ACCESS),
    ),
)


def publication_policy(name: str) -> SecurityPolicy:
    """Immutable semantic files; mutable DB bytes; journal/evidence creation only.

    Root grants add-file/list/traverse, never delete-child, delete-root, DAC or
    owner. Inherit-only ACEs give newly created SQLite journals/evidence data and
    DELETE rights. Explicit protected final-file DACLs exclude that inheritance.
    """
    if name == "root":
        aces = tuple(SecurityAce(*ace) for ace in root_acl.ROOT_ACES[2:])
    elif name in {"activation.json", "host-binding.json"}:
        aces = (SecurityAce(identity.TRADING_SID, security.TRADING_FILE_READ),)
    elif name in {"paper.sqlite", "wake.sqlite"}:
        aces = (SecurityAce(identity.TRADING_SID, sqlite_trading_file_rights()),)
    else:
        raise PublicationError("publication ACL role rejected")
    return SecurityPolicy(ADMIN_POLICY.owner_sid, ADMIN_POLICY.aces + aces)


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


def apply_publication_root_policy(handle: int, policy: SecurityPolicy) -> None:
    """Install only the exact 133-H root owner/protected inheritable DACL.

    The shared creation-attributes builder intentionally admits no inheritance.
    This local boundary uses SDDL revision 1 and SetSecurityInfo on the already
    held root handle. OIIO is exactly OBJECT_INHERIT | INHERIT_ONLY (9).
    """
    if (
        type(policy) is not SecurityPolicy
        or type(policy.owner_sid) is not str
        or policy.dacl_protected is not True
        or type(policy.aces) is not tuple
        or any(
            type(ace) is not SecurityAce
            or type(ace.principal_sid) is not str
            or any(
                type(value) is not int
                for value in (ace.access_mask, ace.ace_type, ace.ace_flags)
            )
            for ace in policy.aces
        )
        or policy != publication_policy("root")
    ):
        raise PublicationError("publication root policy rejected")
    try:
        if root_acl.apply_root_policy_status(handle) != 0:
            raise PublicationError("publication root ACL application failed")
    except root_acl.RootAclError:
        raise PublicationError("publication root ACL application failed") from None


class PublicationReadApi(security.WindowsPaperReadNativeApi):
    """A103 reader admitted only to the exact Q133-2 names and shared runtime."""

    def object_spec(self, path: str) -> security.PaperObjectSpec:
        if path in {"F:\\", r"F:\AITradingBot"}:
            return security.paper_object_spec(path)
        if path in {str(identity.HOST_ROOT), str(identity.PRODUCTION_PYTHON.parent)}:
            return security.PaperObjectSpec(
                security.PaperObjectRole.PARENT, AuthorityObjectKind.DIRECTORY
            )
        if path == str(identity.PRODUCTION_PYTHON) or path in {
            str(identity.HOST_ROOT / name) for name in FINAL_NAMES
        }:
            return security.PaperObjectSpec(
                security.PaperObjectRole.ANCHOR,
                AuthorityObjectKind.FILE,
                MAX_MATERIAL_BYTES,
            )
        raise PublicationError("publication read path rejected")


class WindowsPublication:
    """One backend lifetime, one root attempt, fixed no-clobber publications."""

    def __init__(self) -> None:
        self.api = PublicationReadApi()
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._held = ExitStack()
        self._parent = None
        self._attempted = False
        self._paper_attempted = False
        self._state_attempted = False
        self._published: set[str] = set()
        self._trading_root = False
        self._root_handle = None
        self._armed = False

    def __enter__(self) -> WindowsPublication:
        return self

    def __exit__(self, *exc: object) -> None:
        self._held.close()

    @contextmanager
    def parent_guard(self) -> Iterator[None]:
        require_administrator_token()
        if resolve_current_token_sid() in {identity.TRADING_SID, security.SYSTEM_SID}:
            raise PublicationError("publication principal rejected")
        if require_trading_standard_account() != identity.TRADING_SID:
            raise PublicationError("publication Trading identity rejected")
        with security.PinnedPaperPublicationParent(
            self.api, identity.TRADING_SID
        ) as parent:
            self._parent = parent
            try:
                yield
            finally:
                self._parent = None

    def finish(self) -> None:
        if self._parent is None:
            raise PublicationError("publication parent guard required")
        self._parent.finish()

    def _parent_facts(self) -> list[dict]:
        facts = []
        for path in ("F:\\", r"F:\AITradingBot"):
            with closing(self.api.open(path, AuthorityObjectKind.DIRECTORY)) as handle:
                observed = self.api.inspect(handle, path, AuthorityObjectKind.DIRECTORY)
                security.require_paper_object_security(
                    path,
                    security.paper_object_spec(path),
                    observed.security,
                    identity.TRADING_SID,
                )
                # Parent size/link counts change when unrelated siblings appear;
                # only security and stable volume/file identity are authority.
                facts.append(
                    {
                        "security": asdict(observed.security),
                        "identity": observed.identity,
                    }
                )
        return facts

    def _absent(self, path: Path) -> None:
        # Under the pinned, admitted parent only exact child FILE_NOT_FOUND is
        # absence. GetFileAttributesW sees reparse and wrong-kind occupancy.
        attributes = _bind(
            self.kernel, "GetFileAttributesW", [ctypes.c_wchar_p], ctypes.c_uint32
        )
        if attributes(str(path)) != 0xFFFFFFFF or ctypes.get_last_error() != 2:
            raise PublicationError("publication namespace absent unproven")

    def _git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            input="",
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()

    def _source(
        self, root: Path, branch: str, head: str | None = None, tree: str | None = None
    ) -> dict:
        if (
            Path(self._git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
            != root.resolve(strict=True)
            or self._git(root, "branch", "--show-current") != branch
            or self._git(root, "status", "--porcelain=v1", "--untracked-files=all")
            or self._git(root, "remote", "get-url", "origin")
            != "https://github.com/callmedraken/ai-trading-bot.git"
        ):
            raise PublicationError("publication source rejected")
        observed = {
            "branch": branch,
            "head": self._git(root, "rev-parse", "HEAD"),
            "tree": self._git(root, "rev-parse", "HEAD^{tree}"),
        }
        if head is not None and (observed["head"], observed["tree"]) != (head, tree):
            raise PublicationError("publication source target rejected")
        return observed

    def observe_absent(self, runtime: identity.HostRuntimeIdentity) -> dict:
        self.finish()
        self._absent(identity.HOST_ROOT)
        if (
            sys.platform != "win32"
            or not sys.flags.isolated
            or not sys.dont_write_bytecode
            or Path(sys.executable).resolve(strict=True)
            != identity.PRODUCTION_PYTHON.resolve(strict=True)
            or ".".join(map(str, sys.version_info[:3]))
            != identity.PRODUCTION_PYTHON_VERSION
            or Path(sys.argv[0]).resolve(strict=True)
            != PUBLISHER_LAUNCHER.resolve(strict=True)
            or Path(__file__).resolve().parents[3]
            != PUBLISHER_ROOT.resolve(strict=True)
            or (runtime.source_head, runtime.source_tree) != (TARGET_HEAD, TARGET_TREE)
            or runtime.python_version != identity.PRODUCTION_PYTHON_VERSION
            or runtime.python_sha256 != identity.PRODUCTION_PYTHON_SHA256
        ):
            raise PublicationError("publication runtime rejected")
        with ExitStack() as held:
            runtime_facts = []
            for path, kind in (
                (identity.PRODUCTION_PYTHON.parent, AuthorityObjectKind.DIRECTORY),
                (identity.PRODUCTION_PYTHON, AuthorityObjectKind.FILE),
            ):
                handle = self.api.open(str(path), kind)
                held.callback(self.api.close, handle)
                observed = self.api.inspect(handle, str(path), kind)
                spec = security.PaperObjectSpec(security.PaperObjectRole.PARENT, kind)
                security.require_paper_object_security(
                    str(path), spec, observed.security, identity.TRADING_SID
                )
                if observed.links != 1 and kind is AuthorityObjectKind.FILE:
                    raise PublicationError("publication runtime hardlink rejected")
                runtime_facts.append(asdict(observed))
            if (
                hashlib.sha256(identity.PRODUCTION_PYTHON.read_bytes()).hexdigest()
                != identity.PRODUCTION_PYTHON_SHA256
            ):
                raise PublicationError("publication executable rejected")
        if (
            hashlib.sha256(identity.LAUNCHER.read_bytes()).hexdigest()
            != runtime.launcher_sha256
        ):
            raise PublicationError("publication launcher rejected")
        facts = {
            "parents": self._parent_facts(),
            "target": self._source(
                identity.SOURCE_ROOT, identity.SOURCE_BRANCH, TARGET_HEAD, TARGET_TREE
            ),
            "publisher": self._source(PUBLISHER_ROOT, PUBLISHER_BRANCH),
            "administrator_sid": resolve_current_token_sid(),
            "trading_sid": identity.TRADING_SID,
            "runtime": runtime_facts,
            "python_path": str(identity.PRODUCTION_PYTHON),
            "python_version": identity.PRODUCTION_PYTHON_VERSION,
            "python_sha256": identity.PRODUCTION_PYTHON_SHA256,
            "host_root_absent": True,
        }
        self._absent(identity.HOST_ROOT)
        self.finish()
        return facts

    def _open_mutable(self, path: Path, *, create_new: bool = False) -> WindowsHandle:
        if not self._armed or path not in {
            identity.HOST_ROOT,
            *(identity.HOST_ROOT / name for name in FINAL_NAMES),
            identity.HOST_ROOT / ".activation.json.pending",
            identity.HOST_ROOT / ".host-binding.json.pending",
        }:
            raise PublicationError("publication native mutation rejected")
        if path == identity.HOST_ROOT:
            return WindowsHandle(root_acl.open_directory(str(path), mutable=True))
        create = _bind(
            self.kernel,
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
        with build_security_attributes(ADMIN_POLICY) as bundle:
            value = create(
                str(path),
                0xC00E0081,
                3,
                ctypes.byref(bundle.attributes) if create_new else None,
                1 if create_new else 3,
                0x02200000,
                None,
            )
        if value in (None, 0, -1, ctypes.c_void_p(-1).value):
            raise PublicationError("publication create/open failed")
        return WindowsHandle(value)

    def arm_once(self, reviewed: str, authorization: str) -> None:
        import re

        self.finish()
        if (
            self._armed
            or self._attempted
            or re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
            or authorization != "AUTHORIZE Q133-2 " + reviewed
        ):
            raise PublicationError("publication authorization rejected")
        self._armed = True

    def create_root_once(self) -> None:
        self.finish()
        if self._attempted or not self._armed:
            raise PublicationError("publication already attempted")
        self._attempted = True  # Loss of acknowledgement grants no second call.
        self._absent(identity.HOST_ROOT)
        root_acl.create_admin_directory(str(identity.HOST_ROOT))
        self._root_handle = self._open_mutable(identity.HOST_ROOT)
        self._held.callback(self._root_handle.close)
        require_security_policy(
            self.api.inspect(
                self._root_handle,
                str(identity.HOST_ROOT),
                AuthorityObjectKind.DIRECTORY,
            ).security,
            ADMIN_POLICY,
        )

    def _require_new(self, name: str) -> Path:
        self.finish()
        if (
            not self._attempted
            or self._root_handle is None
            or self._trading_root
            or name not in FINAL_NAMES
        ):
            raise PublicationError("publication mutation boundary rejected")
        path = identity.HOST_ROOT / name
        self._absent(path)
        return path

    def initialize_paper(self, activation: ReviewPaperActivation) -> None:
        path = self._require_new("paper.sqlite")
        if self._paper_attempted:
            raise PublicationError("publication paper already attempted")
        self._paper_attempted = True
        ReviewPaperStore(path, starting_cash=activation.starting_cash)

    def admit_ready(self, activation: ReviewPaperActivation) -> None:
        path = self._require_new("wake.sqlite")
        if self._state_attempted:
            raise PublicationError("publication state already attempted")
        self._state_attempted = True
        UnattendedStateStore(path).admit(activation)

    def publish_once(self, name: str, payload: bytes) -> None:
        destination = self._require_new(name)
        if (
            name not in {"activation.json", "host-binding.json"}
            or name in self._published
            or type(payload) is not bytes
            or not 0 < len(payload) <= MAX_MATERIAL_BYTES
        ):
            raise PublicationError("publication file boundary rejected")
        self._published.add(name)
        temporary = identity.HOST_ROOT / ("." + name + ".pending")
        with closing(self._open_mutable(temporary, create_new=True)) as handle:
            write = _bind(
                self.kernel,
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
            count = ctypes.c_uint32()
            buffer = ctypes.create_string_buffer(payload)
            if not write(
                handle.value, buffer, len(payload), ctypes.byref(count), None
            ) or count.value != len(payload):
                raise PublicationError("publication exact write failed")
            flush = _bind(
                self.kernel, "FlushFileBuffers", [ctypes.c_void_p], ctypes.c_int32
            )
            if not flush(handle.value):
                raise PublicationError("publication flush failed")
            require_security_policy(
                self.api.inspect(
                    handle, str(temporary), AuthorityObjectKind.FILE
                ).security,
                ADMIN_POLICY,
            )
            if self.api.read(handle, MAX_MATERIAL_BYTES) != payload:
                raise PublicationError("publication staged bytes disagreement")
        move = _bind(
            self.kernel,
            "MoveFileExW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32],
            ctypes.c_int32,
        )
        # WRITE_THROUGH only; never REPLACE_EXISTING, COPY_ALLOWED or delayed move.
        if not move(str(temporary), str(destination), 8):
            raise PublicationError("publication no-clobber rename failed")

    def seal_files(self) -> None:
        if self._trading_root or self._published != {
            "activation.json",
            "host-binding.json",
        }:
            raise PublicationError("publication seal boundary rejected")
        for name in sorted(FINAL_NAMES):
            with closing(self._open_mutable(identity.HOST_ROOT / name)) as handle:
                apply_security_policy(handle.value, publication_policy(name))

    def admit_trading_root(self) -> None:
        if self._root_handle is None or self._trading_root:
            raise PublicationError("publication root admission rejected")
        policy = publication_policy("root")
        apply_publication_root_policy(self._root_handle.value, policy)
        require_security_policy(
            self.api.inspect(
                self._root_handle,
                str(identity.HOST_ROOT),
                AuthorityObjectKind.DIRECTORY,
            ).security,
            policy,
        )
        observed = root_acl.inspect_directory(
            self._root_handle.value, str(identity.HOST_ROOT)
        )
        if observed.classification() != "EXACT_INTENDED_ROOT":
            raise PublicationError("publication root readback rejected")
        self._trading_root = True

    @contextmanager
    def pin_complete(self) -> Iterator[CompletePublication]:
        with CompletePublication(self) as pinned:
            yield pinned


class CompletePublication:
    """Independent no-follow reopen; deny write/delete during verifier interval."""

    def __init__(self, backend: WindowsPublication) -> None:
        self.backend = backend
        self.held = ExitStack()
        self.objects = {}

    def __enter__(self) -> CompletePublication:
        try:
            for name in ("root", *sorted(FINAL_NAMES)):
                path = (
                    identity.HOST_ROOT if name == "root" else identity.HOST_ROOT / name
                )
                kind = (
                    AuthorityObjectKind.DIRECTORY
                    if name == "root"
                    else AuthorityObjectKind.FILE
                )
                handle = self.backend.api.open(str(path), kind)
                self.held.callback(self.backend.api.close, handle)
                observed = self.backend.api.inspect(handle, str(path), kind)
                policy = (
                    ADMIN_POLICY
                    if name == "root" and not self.backend._trading_root
                    else publication_policy(name)
                )
                require_security_policy(observed.security, policy)
                if name != "root" and (
                    observed.links != 1
                    or not 0 < observed.byte_length <= 16 * 1024 * 1024
                ):
                    raise PublicationError("publication file shape rejected")
                self.objects[name] = (handle, path, kind, observed)
            return self
        except BaseException:
            self.held.close()
            raise

    def __exit__(self, *exc: object) -> None:
        self.held.close()

    def names(self) -> frozenset[str]:
        handle = self.objects["root"][0]
        return frozenset(self.backend.api.names(handle, str(identity.HOST_ROOT), 8))

    def read(self, name: str) -> bytes:
        if name not in {"activation.json", "host-binding.json"}:
            raise PublicationError("publication byte read rejected")
        return self.backend.api.read(self.objects[name][0], MAX_MATERIAL_BYTES)

    def finish(self) -> None:
        if self.names() != FINAL_NAMES:
            raise PublicationError("publication namespace drift")
        for handle, path, kind, before in self.objects.values():
            if self.backend.api.inspect(handle, str(path), kind) != before:
                raise PublicationError("publication held identity drift")
            with closing(self.backend.api.open(str(path), kind)) as reopened:
                if self.backend.api.inspect(reopened, str(path), kind) != before:
                    raise PublicationError("publication reopened identity drift")
        self.backend.finish()
