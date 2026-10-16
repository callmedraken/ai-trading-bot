"""Read-only namespace/parent admission, separate from the lazy native writer."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from pathlib import Path

from trading_bot.arch133_acl import read_only
from trading_bot.arch133_reprovision import reads
from trading_bot.arch133_reprovision.generation import ACTIVE, ARCHIVE, STAGING_PARENT

PARENTS = ("F:\\", r"F:\AITradingBot")


VOLUME_NON_ADMIN_RIGHTS = 0x1301BF
VOLUME_ACE_FLAGS = 0x1B
INHERIT_ONLY_ACE = 0x08


def require_parent_acl(path: str, observation: read_only.DirectoryObservation) -> None:
    """Apply the frozen host policy or the concrete volume namespace policy."""
    if path == PARENTS[0]:
        for sid, mask, ace_type, flags in observation.aces:
            if ace_type != 0 or flags & ~VOLUME_ACE_FLAGS:
                raise ValueError("volume ACE unsupported")
            if flags & INHERIT_ONLY_ACE:
                if not flags & 0x03:  # OBJECT_INHERIT or CONTAINER_INHERIT
                    raise ValueError("volume template lacks inheritance")
                continue
            if (
                sid not in (read_only.ADMINISTRATORS_SID, read_only.SYSTEM_SID)
                and mask & ~VOLUME_NON_ADMIN_RIGHTS
            ):
                raise ValueError("volume rights rejected")
    elif path == PARENTS[1]:
        # Keep the accepted Architecture-133 immediate-parent predicate exact.
        if any(
            sid not in (read_only.ADMINISTRATORS_SID, read_only.SYSTEM_SID)
            and not flags & 8
            and mask & 0xD0046
            for sid, mask, _, flags in observation.aces
        ):
            raise ValueError("parent writable")
    else:
        raise ValueError("parent role rejected")


def require_parent_policy(
    path: str, observation: read_only.DirectoryObservation
) -> None:
    """Read-only role policy shared by production guard and staged diagnosis."""
    reparse_rejected = (
        observation.reparse is not False if path == PARENTS[0] else observation.reparse
    )
    if (
        observation.filesystem != "NTFS"
        or reparse_rejected
        or observation.owner_sid != read_only.ADMINISTRATORS_SID
    ):
        raise ValueError("parent rejected")
    require_parent_acl(path, observation)


@contextmanager
def parent_guard() -> Iterator[dict]:
    with ExitStack() as held:
        observations = []
        for path in PARENTS:
            handle = read_only.open_directory(path)
            held.callback(read_only.close_handle, handle)
            observation, security = read_only.inspect_directory_security(handle, path)
            require_parent_policy(path, observation)
            observations.append((path, handle, observation, security))
        yield {
            path: {"identity": list(observation.identity), "security_sha256": security}
            for path, _, observation, security in observations
        }
        for path, handle, observation, security in observations:
            if read_only.inspect_directory_security(handle, path) != (
                observation,
                security,
            ):
                raise ValueError("parent changed")


def require_vacant() -> None:
    for path in (ARCHIVE, STAGING_PARENT):
        try:
            Path(path).lstat()
        except FileNotFoundError:
            continue
        raise ValueError("reprovision namespace already occupied")


def final_namespace() -> dict:
    if Path(STAGING_PARENT).is_symlink() or list(Path(STAGING_PARENT).iterdir()):
        raise ValueError("staging namespace changed")
    with ExitStack() as held:
        handles = []
        for path in (ACTIVE, ARCHIVE, STAGING_PARENT):
            handle = reads.open_generation_directory(path)
            held.callback(read_only.close_handle, handle)
            observation, security = read_only.inspect_directory_security(handle, path)
            classification = (
                "EXACT_INTENDED_ROOT" if path == ACTIVE else "ADMIN_SYSTEM_ONLY"
            )
            if (
                observation.classification() != classification
                or observation.reparse
                or observation.filesystem != "NTFS"
            ):
                raise ValueError("final namespace rejected")
            handles.append((path, asdict(observation), security))
        return {
            path: {"observation": observation, "security_sha256": security}
            for path, observation, security in handles
        }


@contextmanager
def staging_guard() -> Iterator[None]:
    handle = read_only.open_directory(STAGING_PARENT)
    try:
        observation, security = read_only.inspect_directory_security(
            handle, STAGING_PARENT
        )
        if (
            observation.classification() != "ADMIN_SYSTEM_ONLY"
            or observation.reparse
            or observation.filesystem != "NTFS"
            or tuple(p.name for p in Path(STAGING_PARENT).iterdir()) != ("generation",)
        ):
            raise ValueError("staging parent rejected")
        yield
        if read_only.inspect_directory_security(handle, STAGING_PARENT) != (
            observation,
            security,
        ):
            raise ValueError("staging parent changed")
    finally:
        read_only.close_handle(handle)
