"""133-AG fixed production declaration and installation-only composition.

No CLI, environment policy, alternate destination or trading composition.
The checkpoint runner owns source/remote admission and durable attempt authority.
Private composition seams exist only to test disposable native surfaces.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    MAX_FILE_BYTES,
    VerifiedRelease,
    source_namespace,
)
from trading_bot.supervised_release.collector import collect_release_bundle
from trading_bot.supervised_release.installation_contract import (
    IMAGE_ACES,
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstallDisposition,
    InstalledEvidence,
    InstallReason,
    InstallResult,
    InstallStatus,
    ObserverNative,
    ReleasePaths,
)
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    PRODUCTION_PYTHON,
    RELEASES_BASE,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
)
from trading_bot.supervised_release.native_read import (
    WindowsObserver,
    windows_libraries,
)
from trading_bot.supervised_release.observer import (
    check_object,
    observe_installed_release,
    observe_parent,
    replay_inputs,
)

WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-supervised-release-installation-operator"
)
BRANCH = "feature/robinhood-supervised-release-installation-operator"
BASE_HEAD = "36a24bbcb9ee4ee5c41f1599306cd9d8ba5a19c4"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
AUTH_ENV = "AI_TRADING_BOT_ARCH133_AG_INSTALL_AUTHORIZATION"
AUTH_VALUE = "ARCH133_AG_ONE_IMMUTABLE_RELEASE_INSTALLATION_AUTHORIZED"
# Release declarations only; they grant no activation or risk/execution authority.
STRATEGY_CONFIG = MovingAverageCrossoverConfig(5, 20, Decimal("1"))
RISK_POLICY_ID = "arch133-long-only-review-paper"
RISK_POLICY_VERSION = "1.0.0"
RISK_POLICY_MATERIAL = (
    b'{"schema":"arch133-installation-risk-declaration/v1",'
    b'"mode":"paper","instruments":"US-stocks-ETFs","long_only":true,'
    b'"margin":false,"leverage":false,"options":false,"shorts":false,'
    b'"crypto":false,"deterministic_risk_required":true}'
)


def _git(*arguments: str) -> str:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1")
    result = subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(WORKTREE),
            *arguments,
        ],
        capture_output=True,
        check=False,
        timeout=30,
        env=environment,
    )
    if result.returncode:
        raise ValueError("installation source observation rejected")
    return result.stdout.decode("utf-8").strip()


def _derive_release() -> tuple[VerifiedRelease, RuntimeBinding]:
    """Derive a complete declaration; collect and independently replay both inputs."""
    for path in reversed((WORKTREE, *WORKTREE.parents)):
        facts = path.lstat()
        if (
            not stat.S_ISDIR(facts.st_mode)
            or stat.S_ISLNK(facts.st_mode)
            or getattr(facts, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("installation checkout ancestor rejected")
    if (
        Path(_git("rev-parse", "--show-toplevel")).resolve() != WORKTREE.resolve()
        or _git("branch", "--show-current") != BRANCH
        or _git("remote", "get-url", "origin") != ORIGIN
        or _git("status", "--porcelain=v1", "--untracked-files=all")
        or _git("merge-base", BASE_HEAD, "HEAD") != BASE_HEAD
    ):
        raise ValueError("installation checkout admission rejected")
    head, tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    names = source_namespace(
        tuple(
            sorted(
                name
                for name in _git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
                if name in {"pyproject.toml", LAUNCHER_RELATIVE_PATH}
                or name.startswith("src/trading_bot/")
            )
        )
    )
    # Collection below independently rejects links, filters, drift and oversized
    # namespaces/bytes. These hashes declare the exact checkout byte convention.
    inventory = []
    for name in names:
        path = WORKTREE / name
        for ancestor in reversed(path.relative_to(WORKTREE).parents):
            facts = (WORKTREE / ancestor).lstat()
            if (
                not stat.S_ISDIR(facts.st_mode)
                or stat.S_ISLNK(facts.st_mode)
                or getattr(facts, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise ValueError("source declaration ancestor rejected")
        facts = path.lstat()
        if (
            not stat.S_ISREG(facts.st_mode)
            or stat.S_ISLNK(facts.st_mode)
            or getattr(facts, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or facts.st_size > MAX_FILE_BYTES
        ):
            raise ValueError("source declaration object rejected")
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        if len(data) != facts.st_size:
            raise ValueError("source declaration bytes rejected")
        inventory.append(ReleaseInventoryEntry(name, hashlib.sha256(data).hexdigest()))
    entries = tuple(inventory)
    launcher = next(
        item for item in entries if item.relative_path == LAUNCHER_RELATIVE_PATH
    )
    declaration = ReleaseManifest(
        head,
        tree,
        PYTHON_VERSION,
        PYTHON_SHA256,
        LAUNCHER_RELATIVE_PATH,
        launcher.sha256,
        entries,
        STRATEGY_ID,
        STRATEGY_VERSION,
        STRATEGY_CONFIG,
        RISK_POLICY_ID,
        RISK_POLICY_VERSION,
        hashlib.sha256(RISK_POLICY_MATERIAL).hexdigest(),
    )
    release = collect_release_bundle(WORKTREE, declaration=declaration)
    if release.manifest != declaration:
        raise ValueError("source declaration drift")
    binding = RuntimeBinding(release)
    replay_inputs(release, binding)
    if (head, tree) != (_git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")):
        raise ValueError("installation source identity drift")
    return release, binding


def _administrator_host() -> None:
    windows_libraries()
    administrator_sid()


@dataclass(frozen=True, slots=True)
class Readiness:
    paths: ReleasePaths
    parent_identity: tuple[int, int]
    python_identity: tuple[int, int]
    installed: InstalledEvidence | None


class ReadinessBlocked(ValueError):
    """Carry a closed reason only; never retain a native exception or capability."""

    def __init__(self, reason: InstallReason) -> None:
        super().__init__("installation readiness rejected")
        self.reason = reason


def _readiness(
    release: VerifiedRelease, binding: RuntimeBinding, native: ObserverNative
) -> Readiness:
    paths = replay_inputs(release, binding)
    with native.read_session(paths) as session:
        parent = observe_parent(session)
        runtime = r"F:\AITradingBot\runtime"
        facts = tuple(
            check_object(
                session.object(path, directory=path == runtime),
                path,
                directory=path == runtime,
                volume=parent.identity[0],
                image_policy=False,
            )
            for path in (runtime, PRODUCTION_PYTHON)
        )
        for fact in facts:
            if fact.owner not in {IMAGE_ACES[0][0], IMAGE_ACES[1][0]} or any(
                kind != 0
                or flags & ~0x13
                or (
                    sid not in {IMAGE_ACES[0][0], IMAGE_ACES[1][0]} and mask & ~0x1200A9
                )
                for sid, mask, kind, flags in fact.aces
            ):
                raise ValueError("production Python security rejected")
        python = facts[1]
        data = session.read(PRODUCTION_PYTHON, MAX_FILE_BYTES)
        if (
            len(data) != python.size
            or hashlib.sha256(data).hexdigest() != PYTHON_SHA256
            or session.python_version() != PYTHON_VERSION
        ):
            raise ValueError("production Python identity rejected")
        names = session.names(RELEASES_BASE)
        if (
            type(names) is not tuple
            or len(names) > 4096
            or any(type(name) is not str for name in names)
        ):
            raise ValueError("release namespace budget rejected")
        # Other canonical retained releases are independent. Case/path aliases,
        # orphan staging and malformed release-like siblings are ambiguous.
        if len({name.casefold() for name in names}) != len(names):
            raise ReadinessBlocked(InstallReason.FINAL_CONFLICT)
        if session.object(paths.staging, directory=True) is not None:
            raise ReadinessBlocked(InstallReason.STAGING_EXISTS)
        for name in names:
            try:
                ReleasePaths(name)
            except ValueError:
                raise ReadinessBlocked(InstallReason.FINAL_CONFLICT) from None
        final = session.object(paths.final, directory=True)
        if (paths.release_id in names) != (final is not None):
            raise ValueError("release namespace classification drift")
        try:
            installed = (
                observe_installed_release(release, binding, native=native)
                if final is not None
                else None
            )
        except (Exception, KeyboardInterrupt):
            raise ReadinessBlocked(InstallReason.FINAL_CONFLICT) from None
        if installed is not None and (
            installed.parent_identity != parent.identity
            or installed.python_identity != python.identity
        ):
            raise ValueError("installed observation identity drift")
        if (
            observe_parent(session) != parent
            or session.names(RELEASES_BASE) != names
            or any(
                session.object(fact.path, directory=fact.kind == "directory") != fact
                for fact in facts
            )
            or session.object(paths.final, directory=True) != final
            or session.object(paths.staging, directory=True) is not None
        ):
            raise ValueError("read-only installation observation drift")
    return Readiness(paths, parent.identity, python.identity, installed)


def _sanitized(result: InstallResult) -> dict[str, object]:
    if (
        type(result) is not InstallResult
        or type(result.status) is not InstallStatus
        or type(result.disposition) is not InstallDisposition
        or type(result.reason) is not InstallReason
    ):
        raise ValueError("installation result shape rejected")
    primary: dict[str, object] = {
        "status": result.status.value,
        "disposition": result.disposition.value,
        "reason": result.reason.value,
    }
    if result.evidence is not None:
        if type(result.evidence) is not InstalledEvidence:
            raise ValueError("installation evidence shape rejected")
        evidence = result.evidence
        ReleasePaths(evidence.release_id)
        if (
            any(
                type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None
                for value in (evidence.manifest_sha256, evidence.binding_sha256)
            )
            or any(
                type(identity) is not tuple
                or len(identity) != 2
                or any(type(value) is not int or value <= 0 for value in identity)
                for identity in (
                    evidence.parent_identity,
                    evidence.image_identity,
                    evidence.python_identity,
                )
            )
            or (
                evidence.python_version,
                evidence.python_sha256,
                evidence.dependency_closure,
            )
            != (PYTHON_VERSION, PYTHON_SHA256, "UNPROVEN")
        ):
            raise ValueError("installation evidence material rejected")
        primary.update(asdict(result.evidence))
    verified = result.status in {
        InstallStatus.INSTALLED_VERIFIED,
        InstallStatus.ALREADY_INSTALLED_VERIFIED,
    }
    if verified and (
        result.evidence is None
        or result.disposition is not InstallDisposition.VERIFIED
        or result.reason is not InstallReason.VERIFIED
    ):
        raise ValueError("installation success evidence rejected")
    if not verified and (
        result.evidence is not None
        or (result.status, result.disposition)
        not in {
            (InstallStatus.BLOCKED, InstallDisposition.NO_INSTALLATION_EFFECT),
            (
                InstallStatus.INDETERMINATE,
                InstallDisposition.PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY,
            ),
        }
    ):
        raise ValueError("installation failure evidence rejected")
    return {
        "status": "PASS" if verified else result.status.value,
        "primary": primary,
        "effect_disposition": "CONFIRMED"
        if verified
        else (
            "NOT_STARTED"
            if result.disposition is InstallDisposition.NO_INSTALLATION_EFFECT
            else "MAY_HAVE_OCCURRED"
        ),
        "automatic_retry": "NOT_AUTHORIZED",
    }


def _preflight() -> dict[str, object]:
    reason = InstallReason.INPUT
    try:
        release, binding = _derive_release()
        reason = InstallReason.HOST
        _administrator_host()
        reason = InstallReason.PARENT
        readiness = _readiness(release, binding, WindowsObserver())
        return {
            "status": "PASS",
            "effect_disposition": "NOT_STARTED",
            "primary": {
                "status": "ALREADY_INSTALLED_VERIFIED"
                if readiness.installed
                else "READY",
                "release_id": release.manifest.release_id,
                "manifest_sha256": release.expected_manifest_sha256,
                "binding_sha256": binding.sha256,
                "final": readiness.paths.final,
                "staging": readiness.paths.staging,
                "parent_identity": readiness.parent_identity,
                "python_identity": readiness.python_identity,
                "python_version": PYTHON_VERSION,
                "python_sha256": PYTHON_SHA256,
                "dependency_closure": "UNPROVEN",
                **(
                    {"image_identity": readiness.installed.image_identity}
                    if readiness.installed is not None
                    else {}
                ),
            },
        }
    except (Exception, KeyboardInterrupt) as exc:
        return _sanitized(
            InstallResult(
                InstallStatus.BLOCKED,
                InstallDisposition.NO_INSTALLATION_EFFECT,
                exc.reason if type(exc) is ReadinessBlocked else reason,
            )
        )


def _execute_once(consume_attempt: Callable[[], None]) -> dict[str, object]:
    """Runner-private callback; no executable transport or caller-selected policy."""
    entered = False
    try:
        release, binding = _derive_release()
        _administrator_host()
        _readiness(release, binding, WindowsObserver())
        # Persist the one-shot latch before entering the sole installation engine.
        # No other invocation/token can erase or replace this fixed latch.
        consume_attempt()
        entered = True
        from trading_bot.supervised_release.installer import install_release

        result = install_release(release, binding)
        if result.evidence is not None and (
            result.evidence.release_id != release.manifest.release_id
            or result.evidence.manifest_sha256 != release.expected_manifest_sha256
            or result.evidence.binding_sha256 != binding.sha256
        ):
            raise ValueError("installation acknowledgement mismatch")
        return _sanitized(result)
    except (Exception, KeyboardInterrupt) as exc:
        return _sanitized(
            InstallResult(
                InstallStatus.INDETERMINATE if entered else InstallStatus.BLOCKED,
                InstallDisposition.PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY
                if entered
                else InstallDisposition.NO_INSTALLATION_EFFECT,
                InstallReason.FINAL_VERIFICATION
                if entered
                else (
                    exc.reason if type(exc) is ReadinessBlocked else InstallReason.INPUT
                ),
            )
        )
