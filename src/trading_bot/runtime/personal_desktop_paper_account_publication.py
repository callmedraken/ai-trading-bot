"""PD1C one-way publication. Production effects remain source-disabled.

The disposable seam runs the same algorithm but cannot issue installed account
authority. A failed invocation never cleans up, repairs, or relaunches itself.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from typing import Protocol

from trading_bot.runtime import (
    personal_desktop_paper_account_publication_freeze as publication_freeze,
)
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    PersonalDesktopPaperAccountBundle,
    reconcile_personal_desktop_paper_account_artifacts,
    verify_personal_desktop_paper_account_bundle_for_test,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    MAX_TOKEN_GROUPS,
    SE_GROUP_ENABLED,
    SE_GROUP_USE_FOR_DENY_ONLY,
    TradingTokenObservation,
    WindowsTradingTokenObserver,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
    AuthorityPrincipalError,
    WindowsAuthorityBootstrap,
    require_windows_platform,
)
from trading_bot.runtime.windows_authority_schema import ProductionAuthorityEvidence
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityPolicy,
)
from trading_bot.runtime.windows_authority_validation import (
    InstalledAuthorityValidation,
    validate_installed_authority_complete,
)


class PaperPublicationState(StrEnum):
    EMPTY = "EMPTY"
    STAGING_REQUIRES_REVIEW = "STAGING_REQUIRES_REVIEW"
    FINAL_REQUIRES_VALIDATION = "FINAL_REQUIRES_VALIDATION"
    CONFLICT = "CONFLICT"


def classify_paper_publication_state(
    *, final_present: bool, staging_present: bool
) -> PaperPublicationState:
    """Pure occupancy evidence; even EMPTY never grants retry authority."""
    if type(final_present) is not bool or type(staging_present) is not bool:
        raise PersonalDesktopPaperAccountError("occupancy must be exact booleans")
    return {
        (False, False): PaperPublicationState.EMPTY,
        (False, True): PaperPublicationState.STAGING_REQUIRES_REVIEW,
        (True, False): PaperPublicationState.FINAL_REQUIRES_VALIDATION,
        (True, True): PaperPublicationState.CONFLICT,
    }[final_present, staging_present]


class PaperPublicationStatus(StrEnum):
    BLOCKED = "BLOCKED"
    PUBLISHED_AND_VERIFIED = "PUBLISHED_AND_VERIFIED"


class PaperPublicationPhase(StrEnum):
    PREFLIGHT = "preflight"
    STAGING_CREATE = "staging-create"
    CHILD_CREATE = "child-create"
    ANCHOR_WRITE = "anchor-write"
    GENESIS_WRITE = "genesis-write"
    FLUSH = "flush"
    ACL = "acl"
    CLOSE_WRITES = "close-writes"
    STAGED_VERIFY = "staged-verify"
    RENAME = "rename"
    FINAL_REOPEN = "final-reopen"
    FINAL_VERIFY = "final-verify"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class PaperPublicationResult:
    """Observation only, never a production account capability or retry permit.

    None means occupancy could not be read. Flags are set BEFORE potentially
    durable calls, so even loss of a native response consumes this attempt.
    """

    status: PaperPublicationStatus
    phase: PaperPublicationPhase
    state: PaperPublicationState | None
    staging_may_have_begun: bool
    rename_may_have_begun: bool
    failure_type: str | None = None


@dataclass(frozen=True, slots=True)
class PaperPublicationEntry:
    relative: str
    spec: security.PaperObjectSpec


def paper_publication_layout(genesis_id: str) -> tuple[PaperPublicationEntry, ...]:
    """Reuse the PD1B source layout and role definitions, without path authority."""
    directory = f"paper-account-genesis-{genesis_id}"
    names = (
        "",
        "personal-desktop-paper-account-authority.json",
        directory,
        f"{directory}\\paper-account-checkpoint-{genesis_id}.json",
        "runtime",
        r"runtime\paper-operations",
    )
    return tuple(
        PaperPublicationEntry(
            name,
            security.paper_object_spec(
                security.PERSONAL_DESKTOP_PAPER_V2_ROOT + ("\\" + name if name else "")
            ),
        )
        for name in names
    )


def publication_entry_path(root: Path, entry: PaperPublicationEntry) -> str:
    return str(root.joinpath(*entry.relative.split("\\")))


class PaperPublicationApi(Protocol):
    """Native operations; injection is accepted ONLY by the disposable seam."""

    def occupied(self, path: str) -> bool: ...
    def create_directory(self, path: str) -> object: ...
    def create_file(self, path: str) -> object: ...
    def write(self, handle: object, payload: bytes) -> None: ...
    def flush(self, handle: object) -> None: ...
    def apply_policy(self, handle: object, policy: SecurityPolicy) -> None: ...
    def open(self, path: str, kind: AuthorityObjectKind) -> object: ...
    def close(self, handle: object) -> None: ...
    def inspect(
        self, handle: object, path: str, kind: AuthorityObjectKind
    ) -> security.PaperObjectObservation: ...
    def read(self, handle: object, maximum: int) -> bytes: ...
    def names(self, handle: object, path: str, maximum: int) -> tuple[str, ...]: ...
    def rename_no_clobber(self, staging: str, final: str) -> None: ...


def require_paper_publication_administrator(
    observation: TradingTokenObservation,
) -> None:
    """Administrator publication is distinct from the standard Trading gate."""
    if (
        type(observation) is not TradingTokenObservation
        or type(observation.user_sid) is not str
        or not observation.user_sid.startswith("S-1-")
        or type(observation.token_type) is not int
        or observation.token_type != 1
        or observation.thread_token_present is not False
        or observation.elevated is not True
        or type(observation.groups) is not tuple
        or len(observation.groups) > MAX_TOKEN_GROUPS
    ):
        raise AuthorityPrincipalError(
            "publisher requires elevated primary administrator"
        )
    seen: set[str] = set()
    administrator = False
    for entry in observation.groups:
        if (
            type(entry) is not tuple
            or len(entry) != 2
            or type(entry[0]) is not str
            or type(entry[1]) is not int
            or not 0 <= entry[1] <= 0xFFFFFFFF
            or entry[0] in seen
        ):
            raise AuthorityPrincipalError("publisher token group evidence is invalid")
        sid, attributes = entry
        seen.add(sid)
        if sid == security.ADMINISTRATORS_SID:
            administrator = bool(
                attributes & SE_GROUP_ENABLED
                and not attributes & SE_GROUP_USE_FOR_DENY_ONLY
            )
    if not administrator:
        raise AuthorityPrincipalError(
            "publisher requires enabled Administrators membership"
        )


def require_paper_publication_inputs(
    *,
    bundle: PersonalDesktopPaperAccountBundle,
) -> InstalledAuthorityValidation:
    """Read-only administrator admission against a source-owned PD1E freeze."""
    freeze = publication_freeze.require_production_paper_publication_freeze()
    require_windows_platform()
    require_paper_publication_administrator(WindowsTradingTokenObserver().observe())
    validation = validate_installed_authority_complete()
    publication_freeze.verify_personal_desktop_paper_publication_freeze(
        bundle,
        freeze=freeze,
        administrator_validation=validation,
    )
    return validation


def _occupancy(
    api: PaperPublicationApi, final: Path, staging: Path
) -> PaperPublicationState:
    return classify_paper_publication_state(
        final_present=api.occupied(str(final)),
        staging_present=api.occupied(str(staging)),
    )


def _check_object(
    path: str,
    entry: PaperPublicationEntry,
    observed: security.PaperObjectObservation,
    sid: str,
    *,
    final_policy: bool,
) -> None:
    facts = observed.security
    if (
        facts.expected_path != path
        or facts.final_path != path
        or facts.kind is not entry.spec.kind
        or facts.is_reparse_point is not False
        or type(observed.identity) is not tuple
        or len(observed.identity) != 2
        or any(type(n) is not int or n < 0 for n in observed.identity)
        or observed.identity[1] == 0
    ):
        raise AuthorityObjectError("publication object type/path/identity is unsafe")
    if entry.spec.kind is AuthorityObjectKind.FILE and (
        type(observed.links) is not int
        or observed.links != 1
        or type(observed.byte_length) is not int
        or not 0 <= observed.byte_length <= entry.spec.maximum_bytes
    ):
        raise AuthorityObjectError("publication file size/link count is unsafe")
    if final_policy:
        policy = security.paper_security_policy(entry.spec.role, sid)
        if (
            facts.owner_sid != policy.owner_sid
            or facts.dacl_protected is not True
            or len(facts.aces) != len(policy.aces)
            or set(facts.aces) != set(policy.aces)
        ):
            raise AuthorityObjectError("publication ACL differs from PD1B role policy")


def _verify_tree(
    api: PaperPublicationApi,
    root: Path,
    entries: tuple[PaperPublicationEntry, ...],
    bundle: PersonalDesktopPaperAccountBundle,
    sid: str,
    created: dict[str, tuple[int, int]],
    staged: dict[str, security.PaperObjectObservation] | None = None,
    *,
    root_handle: object | None = None,
) -> dict[str, security.PaperObjectObservation]:
    observations: dict[str, security.PaperObjectObservation] = {}
    payloads: dict[str, bytes] = {}
    with ExitStack() as handles:
        pinned = []
        for entry in entries:
            path = publication_entry_path(root, entry)
            handle = (
                root_handle
                if entry.relative == "" and root_handle is not None
                else api.open(path, entry.spec.kind)
            )
            if handle is not root_handle:
                handles.callback(api.close, handle)
            observed = api.inspect(handle, path, entry.spec.kind)
            _check_object(path, entry, observed, sid, final_policy=True)
            if observed.identity != created[entry.relative]:
                raise AuthorityObjectError("created publication object was replaced")
            if staged is not None:
                previous = staged[entry.relative]
                expected = replace(
                    previous,
                    security=replace(
                        previous.security, expected_path=path, final_path=path
                    ),
                )
                if observed != expected:
                    raise AuthorityObjectError(
                        "publication identity/security drift across rename"
                    )
            observations[entry.relative] = observed
            if entry.spec.kind is AuthorityObjectKind.DIRECTORY:
                expected_names = {
                    PureWindowsPath(child.relative).name
                    for child in entries
                    if child.relative
                    and str(PureWindowsPath(child.relative).parent)
                    == (entry.relative or ".")
                }
                names = api.names(handle, path, len(expected_names) + 1)
                if (
                    type(names) is not tuple
                    or len(names) != len(expected_names)
                    or set(names) != expected_names
                ):
                    raise AuthorityObjectError("publication layout is not exact")
                content = names
            else:
                content = api.read(handle, entry.spec.maximum_bytes)
                expected_bytes = (
                    bundle.anchor_bytes
                    if entry.spec.role is security.PaperObjectRole.ANCHOR
                    else bundle.genesis_bytes
                )
                if (
                    type(content) is not bytes
                    or content != expected_bytes
                    or len(content) != observed.byte_length
                ):
                    raise AuthorityObjectError("publication artifact bytes changed")
                payloads[entry.spec.role] = content
            pinned.append((entry, path, handle, observed, content))
        reconcile_personal_desktop_paper_account_artifacts(
            genesis_bytes=payloads[security.PaperObjectRole.GENESIS_CHECKPOINT],
            anchor_bytes=payloads[security.PaperObjectRole.ANCHOR],
            manifest_bytes=bundle.manifest_bytes,
        )
        # Reopen every name and reread each pinned object before releasing any
        # read handle. Compare inventory as a set, never enumeration order.
        for entry, path, handle, observed, content in pinned:
            if api.inspect(handle, path, entry.spec.kind) != observed:
                raise AuthorityObjectError("publication pinned identity/security drift")
            reopened = api.open(path, entry.spec.kind)
            try:
                if api.inspect(reopened, path, entry.spec.kind) != observed:
                    raise AuthorityObjectError("publication named object was replaced")
            finally:
                api.close(reopened)
            if entry.spec.kind is AuthorityObjectKind.FILE:
                if api.read(handle, entry.spec.maximum_bytes) != content:
                    raise AuthorityObjectError(
                        "publication staged/final reread mismatch"
                    )
            else:
                names = api.names(handle, path, len(content) + 1)
                if len(names) != len(content) or set(names) != set(content):
                    raise AuthorityObjectError("publication inventory drift")
    return observations


def _publish(
    api: PaperPublicationApi,
    *,
    final: Path,
    staging: Path,
    bundle: PersonalDesktopPaperAccountBundle,
    revalidate: Callable[[], None],
) -> PaperPublicationResult:
    phase = PaperPublicationPhase.PREFLIGHT
    begun = renamed = False
    try:
        bundle.__post_init__()
        anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
        entries = paper_publication_layout(anchor.genesis_checkpoint_id)
        sid = anchor.approved_trading_sid
        revalidate()
        if final.parent != staging.parent or final == staging:
            raise AuthorityPathError("publication requires distinct same-parent names")
        if _occupancy(api, final, staging) is not PaperPublicationState.EMPTY:
            raise AuthorityObjectError("publication final/staging already occupied")
        created: dict[str, tuple[int, int]] = {}
        with ExitStack() as writes:
            opened = []
            for entry in entries:
                path = publication_entry_path(staging, entry)
                phase = (
                    PaperPublicationPhase.STAGING_CREATE
                    if not entry.relative
                    else PaperPublicationPhase.CHILD_CREATE
                )
                if not entry.relative:
                    begun = True  # Set before create: the native response may be lost.
                handle = (
                    api.create_directory(path)
                    if entry.spec.kind is AuthorityObjectKind.DIRECTORY
                    else api.create_file(path)
                )
                writes.callback(api.close, handle)
                observed = api.inspect(handle, path, entry.spec.kind)
                _check_object(path, entry, observed, sid, final_policy=False)
                created[entry.relative] = observed.identity
                opened.append((entry, handle))
            for entry, handle in opened:
                if entry.spec.kind is AuthorityObjectKind.FILE:
                    is_anchor = entry.spec.role is security.PaperObjectRole.ANCHOR
                    phase = (
                        PaperPublicationPhase.ANCHOR_WRITE
                        if is_anchor
                        else PaperPublicationPhase.GENESIS_WRITE
                    )
                    api.write(
                        handle,
                        bundle.anchor_bytes if is_anchor else bundle.genesis_bytes,
                    )
            phase = PaperPublicationPhase.FLUSH
            for entry, handle in opened:
                if entry.spec.kind is AuthorityObjectKind.FILE:
                    api.flush(handle)
            phase = PaperPublicationPhase.ACL
            for entry, handle in opened:
                api.apply_policy(
                    handle, security.paper_security_policy(entry.spec.role, sid)
                )
            # Files support FlushFileBuffers; Windows provides no portable
            # directory fsync. Flush files again after applying their security.
            phase = PaperPublicationPhase.FLUSH
            for entry, handle in opened:
                if entry.spec.kind is AuthorityObjectKind.FILE:
                    api.flush(handle)
            phase = PaperPublicationPhase.CLOSE_WRITES
        phase = PaperPublicationPhase.STAGED_VERIFY
        staged = _verify_tree(api, staging, entries, bundle, sid, created)
        revalidate()
        phase = PaperPublicationPhase.RENAME
        renamed = True
        api.rename_no_clobber(str(staging), str(final))
        phase = PaperPublicationPhase.FINAL_REOPEN
        with ExitStack() as final_handles:
            root_handle = api.open(str(final), AuthorityObjectKind.DIRECTORY)
            final_handles.callback(api.close, root_handle)
            phase = PaperPublicationPhase.FINAL_VERIFY
            _verify_tree(
                api,
                final,
                entries,
                bundle,
                sid,
                created,
                staged,
                root_handle=root_handle,
            )
            revalidate()
            if (
                _occupancy(api, final, staging)
                is not PaperPublicationState.FINAL_REQUIRES_VALIDATION
            ):
                raise AuthorityObjectError("publication occupancy drift after rename")
        return PaperPublicationResult(
            PaperPublicationStatus.PUBLISHED_AND_VERIFIED,
            PaperPublicationPhase.COMPLETE,
            PaperPublicationState.FINAL_REQUIRES_VALIDATION,
            begun,
            renamed,
        )
    except Exception as error:
        try:
            state = _occupancy(api, final, staging)
        except Exception:
            state = None  # Read failure never implies absence or a safe retry.
        return PaperPublicationResult(
            PaperPublicationStatus.BLOCKED,
            phase,
            state,
            begun,
            renamed,
            type(error).__name__,
        )


def publish_personal_desktop_paper_account(
    *,
    bundle: PersonalDesktopPaperAccountBundle,
) -> PaperPublicationResult:
    """Fixed production destination; no caller path/API/enable flag is accepted."""
    # FIRST executable statement, before constructing even a native read object.
    if security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not True:
        raise PersonalDesktopPaperAccountError(
            "PD1C production publication is disabled"
        )
    validation = require_paper_publication_inputs(bundle=bundle)
    from trading_bot.runtime.personal_desktop_paper_account_publication_native import (
        WindowsPaperPublicationApi,
    )

    sid = validation.bootstrap_verification.bootstrap.approved_account_sid
    result = None
    try:
        with security.PinnedPaperReadSession(
            security.WindowsPaperReadNativeApi(), sid
        ) as parent:
            parent.pin(security.PERSONAL_DESKTOP_PAPER_PARENT)

            def revalidate() -> None:
                if require_paper_publication_inputs(bundle=bundle) != validation:
                    raise AuthorityObjectError(
                        "administrator C1 publication evidence drift"
                    )
                parent.finish()

            anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
            result = _publish(
                WindowsPaperPublicationApi(anchor.genesis_checkpoint_id),
                final=Path(security.PERSONAL_DESKTOP_PAPER_V2_ROOT),
                staging=Path(security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT),
                bundle=bundle,
                revalidate=revalidate,
            )
        return result
    except Exception as error:
        if result is None:
            raise  # Preflight failed; no publication invocation began.
        # Parent finish/close is part of acceptance, too. A failed parent
        # observation makes a new path-based occupancy probe untrustworthy.
        return replace(
            result,
            status=PaperPublicationStatus.BLOCKED,
            phase=(
                PaperPublicationPhase.FINAL_VERIFY
                if result.phase is PaperPublicationPhase.COMPLETE
                else result.phase
            ),
            state=None,
            failure_type=type(error).__name__,
        )


def require_disposable_paper_publication_root_for_test(root: Path) -> Path:
    """Reject production prefixes/aliases and unsafe ancestors BEFORE test DI."""
    if not isinstance(root, Path) or not root.is_absolute():
        raise AuthorityPathError(
            "test publication requires an absolute disposable root"
        )

    def check_text(value: str) -> None:
        windows = PureWindowsPath(value)
        if (
            str(windows)
            .casefold()
            .startswith(security.PERSONAL_DESKTOP_PAPER_PARENT.casefold())
            or str(windows).startswith("\\\\")
            or any(
                part in {".", ".."} or part.endswith((".", " ")) or "~" in part
                for part in windows.parts
            )
            or ":" in str(windows)[len(windows.anchor) :]
        ):
            raise AuthorityPathError(
                "test root overlaps or aliases a production namespace"
            )

    check_text(str(root))
    for component in (*reversed(root.parents), root):
        info = component.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 0x400
        ):
            raise AuthorityPathError(
                "test root has an unsafe directory/reparse ancestor"
            )
    resolved = root.resolve(strict=True)
    check_text(str(resolved))
    if resolved != root:
        raise AuthorityPathError("test root is not its canonical resolved path")
    with os.scandir(root) as entries:
        for entry in entries:
            if entry.name not in {"Paper-v2", ".Paper-v2.provisioning"}:
                raise AuthorityPathError(
                    "test root is not a dedicated disposable publication root"
                )
    return resolved


def publish_personal_desktop_paper_account_for_test(
    *,
    disposable_root: Path,
    native_api_factory_for_test: Callable[[Path, str], PaperPublicationApi],
    administrator_for_test: TradingTokenObservation,
    bundle: PersonalDesktopPaperAccountBundle,
    bootstrap: WindowsAuthorityBootstrap,
    bootstrap_digest: str,
    production_evidence: ProductionAuthorityEvidence,
    selected_snapshot: SelectedC3SnapshotReadResult,
    starting_cash: Decimal,
) -> PaperPublicationResult:
    """Explicit disposable-only DI; produces observations, never account authority.

    The test API models native security under this validated disposable root.
    Production never accepts this API or any destination supplied by a caller.
    """
    root = require_disposable_paper_publication_root_for_test(disposable_root)
    info = root.lstat()
    parent_identity = info.st_dev, info.st_ino
    verify_personal_desktop_paper_account_bundle_for_test(
        bundle,
        bootstrap=bootstrap,
        bootstrap_digest=bootstrap_digest,
        production_evidence=production_evidence,
        selected_snapshot=selected_snapshot,
        starting_cash=starting_cash,
    )
    require_paper_publication_administrator(administrator_for_test)
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    api = native_api_factory_for_test(root, anchor.genesis_checkpoint_id)

    def revalidate() -> None:
        require_disposable_paper_publication_root_for_test(root)
        current = root.lstat()
        if (current.st_dev, current.st_ino) != parent_identity:
            raise AuthorityObjectError("disposable publication parent identity drift")
        require_paper_publication_administrator(administrator_for_test)

    return _publish(
        api,
        final=root / "Paper-v2",
        staging=root / ".Paper-v2.provisioning",
        bundle=bundle,
        revalidate=revalidate,
    )
